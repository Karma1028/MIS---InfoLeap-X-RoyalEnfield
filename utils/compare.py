"""Model-wise comparison view — Head-to-Head Model Benchmark Page:
Side-by-side model comparison for any 2 selected models across CC platforms.
Combines pristine stacked-bar charts, full data tables, significance testing,
and 4-level open-ended netting taxonomy trees.
"""
import base64
import html as _html
import re
import streamlit as st
import pandas as pd
from utils.data_engine import RE_MODEL_LABELS, month_label_to_fy_quarter
from utils.visuals import (
    render_chart_with_table, _lighten, _pct_label, MUTED, INFOLEAP_GREEN, RE_RED, INFOLEAP_ORANGE,
    BRAND_CONSIDERED_COLOR, REASONS_COLOR, render_collapsible_reasons_table
)
from utils.stat_engine import calculate_significance, compare_to_baseline_by_column
from utils.ai_providers import call_llm, get_active_provider
from utils.ai_summary import render_chart_ai_blurb
from utils.model_images import model_image_path


@st.cache_data(show_spinner=False)
def _img_b64(path):
    """Base64-encode a product photo for embedding as a fixed-height <img>."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _img_mime(path):
    ext = path.rsplit(".", 1)[-1].lower()
    return {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "png")


DEMOGRAPHIC_BUILDERS = {
    "Age": (lambda engine, df, seg: engine.age_table(df, base_label=seg, numeric=True), "bar"),
    "Education": (lambda engine, df, seg: engine.education_table(df, base_label=seg, numeric=True), "bar"),
    "Occupation": (lambda engine, df, seg: engine.occupation_table(df, base_label=seg, numeric=True), "donut"),
    "Household Income": (lambda engine, df, seg: engine.household_income_table(df, base_label=seg, numeric=True), "donut"),
    "Type of Buyer": (lambda engine, df, seg: engine.type_of_buyer_table(df, base_label=seg, numeric=True), "donut"),
}
ACCEPTOR_BUILDERS = {
    "Additional + Replaced — Brand Wise": (lambda engine, df, seg: engine.cap_rows(
        engine.additional_replaced_table(df, by="brand", base_label=seg, numeric=True), max_rows=8), "bar"),
    "Brand Considered — Brand Wise": (lambda engine, df, seg: engine.cap_rows(
        engine.brand_considered_table(df, by="brand", base_label=seg, numeric=True), max_rows=8), "bar"),
}
REJECTOR_BUILDERS = {
    "Brand Owned — Brand Wise": (lambda engine, df, seg: engine.cap_rows(
        engine.brand_owned_table(df, by="brand", base_label=seg, numeric=True), max_rows=8), "bar"),
}


def _metric_builders_for(segment_for_compare):
    builders = dict(DEMOGRAPHIC_BUILDERS)
    if segment_for_compare in ("All", "Acceptor"):
        builders.update(ACCEPTOR_BUILDERS)
    if segment_for_compare in ("All", "Rejector", "Cancelled"):
        builders.update(REJECTOR_BUILDERS)
    return builders


def render_comparison_page(engine):
    st.markdown("<h1>Model Comparison</h1>", unsafe_allow_html=True)
    st.caption("Compare exactly 2 models side by side, within the same or across CC platforms — same filters and metrics as the segment pages.")

    st.sidebar.markdown("### Comparison Filters")
    segment_for_compare = st.sidebar.selectbox("Segment context", ["All", "Acceptor", "Rejector", "Cancelled"], key="cmp_segment")

    st.sidebar.markdown("### Time Period")
    time_mode = st.sidebar.radio("View by", ["All Months", "Month Range", "Quarter (Financial Calendar)"],
                                  label_visibility="collapsed", key="time_mode")
    month_order, fy_quarter_order = engine.month_order, engine.fy_quarter_order
    month_short = [m.split("'")[0][:3] + "'" + m.split("'")[1][2:] for m in month_order]
    selected_months = month_order
    if time_mode == "Month Range":
        lo, hi = st.sidebar.select_slider("Month range", options=month_short, value=(month_short[0], month_short[-1]), key="month_range")
        lo_i, hi_i = month_short.index(lo), month_short.index(hi)
        selected_months = month_order[lo_i:hi_i + 1]
    elif time_mode == "Quarter (Financial Calendar)":
        quarters = st.sidebar.multiselect("Quarter (Apr-Mar FY)", fy_quarter_order, default=fy_quarter_order, key="quarters")
        selected_months = [m for m in month_order if month_label_to_fy_quarter(m) in quarters]

    with st.container(border=True):
        manufacturers = engine.manufacturers()
        default_brands = ["Royal Enfield"] if "Royal Enfield" in manufacturers else manufacturers[:1]
        brands = st.multiselect("Brands", manufacturers, default=default_brands)
        if not brands:
            st.info("Select at least one brand.")
            return
        has_competitor = any(b != "Royal Enfield" for b in brands)
        if has_competitor:
            st.caption("Competitor brand models are tracked via 'what they actually bought' (no rejected/cancelled concept for competitor brands in this dataset) — counts may legitimately be 0 for segments where that doesn't apply.")

        name_to_info = {}
        all_models = []
        for brand in brands:
            if brand == "Royal Enfield":
                brand_models = {RE_MODEL_LABELS[c]: c for c in sorted(RE_MODEL_LABELS)}
            else:
                brand_models = engine.models_for_manufacturer(brand)
            prefix_needed = len(brands) > 1 and brand != "Royal Enfield"
            for model_name, code in brand_models.items():
                display_name = f"{brand} — {model_name}" if prefix_needed else model_name
                name_to_info[display_name] = (brand, code)
                all_models.append(display_name)

        default_models = [m for m in ["Royal Enfield Bullet 350", "Royal Enfield Classic 350"] if m in all_models]
        if not default_models:
            default_models = all_models[:2]
        selected_models = st.multiselect("Models to compare", all_models, default=default_models, max_selections=2)

    # Product-image + headline stats gallery — one card per selected model.
    if selected_models:
        _gal_cols = st.columns(len(selected_models))
        for _gi, _model_name in enumerate(selected_models):
            _m_brand, _m_code = name_to_info[_model_name]
            if _m_brand == "Royal Enfield":
                _m_df = engine.filter_df(segment=segment_for_compare, model_code=_m_code)
            else:
                _m_df = engine.filter_df(segment=segment_for_compare, owned_brand_code=_m_code)
            _m_df = _m_df[_m_df['month_label'].isin(selected_months)]
            _m_img_path = model_image_path(_model_name)
            with _gal_cols[_gi]:
                with st.container(border=True):
                    if _m_img_path:
                        st.markdown(
                            f"<div style='width:100%;height:260px;border-radius:8px;background:#F7F5F2;"
                            f"display:flex;align-items:center;justify-content:center;overflow:hidden;'>"
                            f"<img src='data:image/{_img_mime(_m_img_path)};base64,{_img_b64(_m_img_path)}' "
                            f"style='max-width:100%;max-height:100%;object-fit:contain;'/></div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            "<div style='width:100%;height:260px;border-radius:8px;background:#F3F1ED;"
                            "display:flex;align-items:center;justify-content:center;color:#9A958D;font-size:0.82rem;'>"
                            "No product image available</div>",
                            unsafe_allow_html=True,
                        )
                    st.markdown(f"**{_model_name}**")
                    if len(_m_df) > 0:
                        _age_tbl = engine.age_table(_m_df, base_label=segment_for_compare, numeric=True)
                        _income_tbl = engine.household_income_table(_m_df, base_label=segment_for_compare, numeric=True)
                        _buyer_tbl = engine.type_of_buyer_table(_m_df, base_label=segment_for_compare, numeric=True)
                        for _label, _tbl in [("Top Age", _age_tbl), ("Top Income", _income_tbl), ("Buyer Type", _buyer_tbl)]:
                            _rows = _tbl.iloc[1:]
                            if len(_rows):
                                _top = _rows.loc[_rows["All"].astype(float).idxmax()]
                                st.caption(f"**{_label}:** {_top['Unnamed: 0']} ({float(_top['All']):.0f}%)")
                    else:
                        st.caption("No respondents match the current filters for this model.")

    if len(selected_models) < 2:
        st.info("Select 2 models to compare.")
        return

    # Load model DataFrames ONCE
    model_dfs = {}
    short_names = {}
    for model_name in selected_models:
        model_brand, code = name_to_info[model_name]
        if model_brand == "Royal Enfield":
            mdf = engine.filter_df(segment=segment_for_compare, model_code=code)
        else:
            mdf = engine.filter_df(segment=segment_for_compare, owned_brand_code=code)
        mdf = mdf[mdf['month_label'].isin(selected_months)]
        model_dfs[model_name] = mdf
        short_names[model_name] = model_name.replace("Royal Enfield ", "")

    # Segment split bar removed per user instruction for clean benchmark comparison

    # Clean 2-Column Model Benchmark Comparison — 5 Core Demographic Metrics
    st.markdown("### Model Benchmark — Core Profile Metrics")
    st.caption("Side-by-side comparison of 2 selected models comparing Category All vs Last Selected Month.")

    last_selected_month = selected_months[-1] if selected_months else engine.month_order[-1]
    m1_name, m2_name = selected_models[0], selected_models[1]
    m1_short, m2_short = short_names[m1_name], short_names[m2_name]
    m1_df, m2_df = model_dfs[m1_name], model_dfs[m2_name]

    for metric_name, (builder, _) in DEMOGRAPHIC_BUILDERS.items():
        st.markdown(f"#### {metric_name}")
        tbl1 = builder(engine, m1_df, segment_for_compare)
        tbl2 = builder(engine, m2_df, segment_for_compare)

        def _format_two_col_table(tbl):
            if tbl.empty:
                return tbl
            keep_cols = ['Unnamed: 0']
            if 'All' in tbl.columns:
                keep_cols.append('All')
            if last_selected_month in tbl.columns and last_selected_month != 'All':
                keep_cols.append(last_selected_month)
            return tbl[keep_cols].copy()

        f_tbl1 = _format_two_col_table(tbl1)
        f_tbl2 = _format_two_col_table(tbl2)

        from utils.visuals import _render_html_table
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{m1_short}**")
            _render_html_table(f_tbl1, accent="#2E3192")
        with c2:
            st.markdown(f"**{m2_short}**")
            _render_html_table(f_tbl2, accent="#1B8A8A")
        st.markdown("<div style='margin-bottom:1.2rem;'></div>", unsafe_allow_html=True)

    # Open-Ended Netting Comparison Section
    st.markdown("---")
    st.markdown("### 💬 Open-Ended Netting Comparison (Taxonomy & Reasons)")
    st.caption("Side-by-side 4-level netting taxonomy comparison for the selected models across Key Buying Factors, Reasons for Rejection, and Reasons for Cancelling.")

    _reasons_tables_to_show = []
    if segment_for_compare == "Acceptor":
        _reasons_tables_to_show.append(("Key Buying Factors (Why Bought)", "mq2a", REASONS_COLOR))
    elif segment_for_compare in ("Rejector", "Cancelled"):
        _reasons_tables_to_show.append(("Why They Considered RE First", "mq2c", BRAND_CONSIDERED_COLOR))
        _rej_lbl = "Reasons for Rejection" if segment_for_compare == "Rejector" else "Reasons for Cancelling"
        _reasons_tables_to_show.append((_rej_lbl, "mq3a", REASONS_COLOR))
    else:
        _reasons_tables_to_show.append(("Acceptors — Key Buying Factors", "mq2a", REASONS_COLOR))
        _reasons_tables_to_show.append(("Rejectors — Reasons for Rejection", "mq3a", REASONS_COLOR))
        _reasons_tables_to_show.append(("Booked & Cancelled — Reasons for Cancelling", "mq3a", REASONS_COLOR))

    for _tbl_idx, (_tbl_title, _prefix, _tbl_color) in enumerate(_reasons_tables_to_show):
        with st.expander(f"💬 {_tbl_title}", expanded=True):
            st.markdown(f"#### {_tbl_title}")
            _m_cols = st.columns(len(selected_models))
            for _mi, model_name in enumerate(selected_models):
                mdf = model_dfs[model_name]
                _seg_lbl = segment_for_compare
                if segment_for_compare in ("All", "Overview"):
                    if "Key Buying Factors" in _tbl_title:
                        _seg_lbl = "Acceptor"
                    elif "Rejection" in _tbl_title:
                        _seg_lbl = "Rejector"
                    else:
                        _seg_lbl = "Cancelled"
                    mdf = mdf[mdf['segment'] == _seg_lbl]

                with _m_cols[_mi]:
                    st.markdown(f"**{short_names[model_name]}**")
                    if len(mdf) > 0:
                        _r_tree = engine.reasons_tree_data(mdf, base_label=_seg_lbl, broad_prefix=_prefix)
                        with st.container(border=True):
                            render_collapsible_reasons_table(
                                _r_tree,
                                f"{short_names[model_name]} — {_tbl_title}",
                                color=_tbl_color,
                                key_suffix=f"cmp_{_prefix}_{_tbl_idx}_{model_name.replace(' ', '_')}_{_mi}"
                            )
                    else:
                        st.caption(f"No respondents match the current filters for {short_names[model_name]}.")

    # AI Model Positioning Analysis
    st.markdown("---")
    st.markdown("### 🤖 AI Model Positioning Analysis")
    _ai_key = f"cmp_ai_{'_'.join(short_names[m] for m in selected_models)}"
    if st.button("Generate AI Positioning Analysis", key=_ai_key, type="secondary"):
        with st.spinner("Analyzing model profiles..."):
            _fact_lines = []
            for _sn, _facts in _ai_facts.items():
                if _facts:
                    _fact_lines.append(f"**{_sn}**: " + " | ".join(f"{k}: {v}" for k, v in _facts.items()))
            if _fact_lines:
                _prompt = (
                    f"You are an expert market research analyst for Royal Enfield India. "
                    f"Below are top-category profiles for {len(selected_models)} motorcycle models "
                    f"based on survey respondents in the '{segment_for_compare}' segment.\n\n"
                    + "\n".join(_fact_lines) +
                    "\n\nIn 3–5 concise bullet points, explain how these models differ in their buyer "
                    "profiles and what that implies for Royal Enfield's positioning strategy. "
                    "Be specific, data-driven, and actionable. No filler."
                )
                try:
                    provider = get_active_provider()
                    model_id = st.session_state.get("or_model_choice") if provider == "openrouter" else None
                    _response = call_llm(provider, model_id,
                                         "You are a concise market research analyst. Return bullet points only.",
                                         _prompt, max_tokens=400, temperature=0.3)
                    st.markdown(_response)
                except Exception as _e:
                    st.warning(f"AI analysis unavailable: {_e}")
            else:
                st.caption("No metric data available to analyze.")
