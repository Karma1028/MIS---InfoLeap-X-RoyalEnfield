"""Model-wise comparison view — MIS_Dashboard_Requirements.docx 5.2:
'Side-by-side model comparison... Bullet 350 and Classic 350 data should be
viewable on the same window pane simultaneously... support selection of any
two or more models within the same or across CC platforms.'

Per user direction (2026-06-18): this page must carry the SAME filter set
(Month Range/Quarter) and the SAME metric coverage as the Acceptor/
Rejector/Cancelled pages, not a stripped-down subset.

Per later user direction (2026-07-22): brand and model selection are now
locked to strictly 2 each (max_selections=2 on both multiselects below) —
this page is a head-to-head comparison, not an open-ended overlay.
"""
import base64
import streamlit as st
import pandas as pd
from utils.data_engine import RE_MODEL_LABELS, month_label_to_fy_quarter
from utils.visuals import render_chart_with_table
from utils.stat_engine import calculate_significance, compare_to_baseline_by_column
from utils.ai_providers import call_llm, get_active_provider
from utils.ai_summary import render_chart_ai_blurb
from utils.model_images import model_image_path


@st.cache_data(show_spinner=False)
def _img_b64(path):
    """Base64-encode a product photo for embedding as a fixed-height
    <img> — st.image can't crop/contain to a uniform aspect ratio on its
    own, so the gallery's two cards (portrait vs. landscape source
    photos) ended up visibly different heights."""
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

    # Per user instruction (2026-06-18): "filters will be same across all
    # segments from the side bar" — Time Period uses the SAME widget keys
    # as the segment pages (no cmp_ prefix) so switching between Model
    # Comparison and Overview/Acceptors/etc. keeps the same selection
    # instead of resetting. Segment context stays comparison-specific (it
    # means something different here: which population each model's stats
    # are drawn from, not "which page"). Zone filter removed per explicit
    # instruction (2026-06-19).
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

    # Brand + model pickers — wrapped in one bordered card so this filter
    # block reads as a distinct panel, matching the card treatment used
    # everywhere else in the app (Overview narrative, segment hero cards)
    # instead of sitting as bare, disconnected widgets.
    #
    # Brands: any number (per 2026-07-27 request -- picking brands just
    # widens the model pool below, it's not itself the comparison).
    # Models: locked to strictly 2 -- this page is a head-to-head
    # comparison, not an open-ended multi-model overlay.
    with st.container(border=True):
        manufacturers = engine.manufacturers()
        default_brands = ["Royal Enfield"] if "Royal Enfield" in manufacturers else manufacturers[:1]
        brands = st.multiselect("Brands", manufacturers, default=default_brands)
        if not brands:
            st.info("Select at least one brand.")
            return
        has_competitor = any(b != "Royal Enfield" for b in brands)
        if has_competitor:
            st.caption("Competitor brand models are tracked via 'what they actually bought' (no rejected/cancelled concept for competitor brands in this dataset) — counts may legitimately be 0 for segments where that doesn't apply (e.g. Acceptors never bought a competitor model).")

        # name_to_info maps the (possibly brand-prefixed, for disambiguation) display
        # name to (brand, model_code) so each model's filter_df call can route through
        # the right column (model_code for RE, owned_brand_code for competitors).
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
    # Photos are embedded as a fixed-height, object-fit:cover <img> (not
    # st.image, which can't crop) so both cards line up at the same
    # height even when the two source photos have different aspect ratios.
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
                        # object-fit:contain (not cover) -- per user report
                        # the bike was getting cropped/cut off; a light
                        # background fills the letterboxed space instead of
                        # cutting off wheels/handlebars to force-fill the box.
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

    # ── Load model DataFrames ONCE — reused across all metrics ─────────────
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

    # ── M2: Segment split bar — Acc/Rej/Can per model ─────────────────────
    # Shows conversion profile per model before any demographic deep-dive.
    # Segments overlap (G3-A: 50%+ Rej are also Acc) — use unique base via concat+dedup.
    st.markdown("### Segment Profile per Model")
    st.caption("% of unique respondents per model in each segment. Does NOT sum to 100% — segments overlap by survey design.")
    try:
        import plotly.graph_objects as go
        _seg_rows = []
        for model_name in selected_models:
            model_brand, code = name_to_info[model_name]
            _ma = engine.filter_df(segment="Acceptor", model_code=code if model_brand == "Royal Enfield" else None,
                                   owned_brand_code=code if model_brand != "Royal Enfield" else None)
            _mr = engine.filter_df(segment="Rejector", model_code=code if model_brand == "Royal Enfield" else None,
                                   owned_brand_code=code if model_brand != "Royal Enfield" else None)
            _mc = engine.filter_df(segment="Cancelled", model_code=code if model_brand == "Royal Enfield" else None,
                                   owned_brand_code=code if model_brand != "Royal Enfield" else None)
            for _df in (_ma, _mr, _mc):
                _df = _df[_df['month_label'].isin(selected_months)] if not _df.empty else _df
            _mall = pd.concat([_ma, _mr, _mc]).drop_duplicates()
            _base = max(len(_mall), 1)
            _seg_rows.append({
                "model": short_names[model_name], "unique_n": len(_mall),
                "acc_pct": len(_ma[_ma['month_label'].isin(selected_months)]) / _base * 100,
                "rej_pct": len(_mr[_mr['month_label'].isin(selected_months)]) / _base * 100,
                "can_pct": len(_mc[_mc['month_label'].isin(selected_months)]) / _base * 100,
            })
        _sp_models = [f"{r['model']} (n={r['unique_n']:,})" for r in _seg_rows]
        _sp_fig = go.Figure()
        _sp_fig.add_trace(go.Bar(name="Acceptors", y=_sp_models, x=[r["acc_pct"] for r in _seg_rows],
            orientation='h', marker_color='#39B54A', text=[f"{r['acc_pct']:.0f}%" for r in _seg_rows], textposition='outside', cliponaxis=False))
        _sp_fig.add_trace(go.Bar(name="Rejectors", y=_sp_models, x=[r["rej_pct"] for r in _seg_rows],
            orientation='h', marker_color='#C8102E', text=[f"{r['rej_pct']:.0f}%" for r in _seg_rows], textposition='outside', cliponaxis=False))
        _sp_fig.add_trace(go.Bar(name="Cancelled", y=_sp_models, x=[r["can_pct"] for r in _seg_rows],
            orientation='h', marker_color='#F7941D', text=[f"{r['can_pct']:.0f}%" for r in _seg_rows], textposition='outside', cliponaxis=False))
        _max_sp = max(max(r["acc_pct"], r["rej_pct"], r["can_pct"]) for r in _seg_rows) if _seg_rows else 80
        _sp_fig.update_layout(barmode='group', height=max(220, 60 * len(_seg_rows)),
            margin=dict(l=10, r=60, t=10, b=20),
            xaxis=dict(range=[0, min(_max_sp * 1.3, 110)], ticksuffix='%', showgrid=True, gridcolor='#F0EDE8', title=None),
            yaxis=dict(autorange='reversed', tickfont=dict(size=12)),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5, font=dict(size=11)),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(_sp_fig, use_container_width=True, config={"displayModeBar": False}, key="cmp_seg_split")
    except Exception as _e:
        st.caption(f"Segment split unavailable: {_e}")

    # ── M1: All metrics in expanders — no dropdown, scroll to compare all ──
    st.markdown("### Demographic Comparison — All Metrics")
    st.caption("Each metric shown below in its own section. Scroll to compare profiles across all dimensions simultaneously.")

    metric_builders = _metric_builders_for(segment_for_compare)

    _sig_cols_row = st.columns([2, 2])
    with _sig_cols_row[0]:
        sig_test_col = st.selectbox("Significance test month", [m for m in selected_months], key="cmp_sig_col",
                                    help="Which month's column to run pairwise Z-tests on (N≥30 required).")
    with _sig_cols_row[1]:
        sig_mode = st.radio("Significance baseline", ["Model vs Model", "Model vs Overall Market"],
                            key="cmp_sig_mode", horizontal=True,
                            help="'Model vs Overall Market' flags where a model over/under-indexes vs all respondents in this segment.")

    # Build overall-market baseline table once (reused across all metrics when sig_mode = Overall)
    _baseline_df = engine.filter_df(segment=segment_for_compare)
    _baseline_df = _baseline_df[_baseline_df['month_label'].isin(selected_months)]

    # Accumulate top-category facts per model per metric for AI summary
    _ai_facts = {short_names[m]: {} for m in selected_models}

    for _mi, (metric_name, (builder, _)) in enumerate(metric_builders.items()):
        with st.expander(f"📊 {metric_name}", expanded=(_mi == 0)):
            # Build table per model for this metric
            tables = {}
            for model_name, mdf in model_dfs.items():
                if len(mdf) == 0:
                    continue
                try:
                    tbl = builder(engine, mdf, segment_for_compare)
                    if time_mode != "All Months":
                        keep_cols = ["Unnamed: 0", "All"] + [m for m in selected_months if m in tbl.columns]
                        tbl = tbl[[c for c in keep_cols if c in tbl.columns]]
                    tables[model_name] = tbl
                    # Capture top category for AI summary
                    _data_rows = tbl.iloc[1:]
                    if len(_data_rows) and "All" in tbl.columns:
                        _top = _data_rows.loc[_data_rows["All"].astype(float).idxmax()]
                        _ai_facts[short_names[model_name]][metric_name] = f"{_top['Unnamed: 0']} ({float(_top['All']):.0f}%)"
                except Exception:
                    pass

            if len(tables) < 2:
                st.caption("Insufficient data for this metric under current filters.")
                continue

            # Per user request: one consistent chart shape across the whole
            # app — each model gets its OWN stacked-bar chart + table
            # (same render_chart_with_table/stacked_bar_chart used on every
            # segment page), side by side, instead of a single overlaid
            # grouped-bar comparison chart. (Stacking the two models'
            # percentages into one shared bar isn't meaningful — they're
            # independent, non-summing populations — so "same chart shape"
            # means each panel individually, not merged into one bar.)
            _chart_cols = st.columns(len(tables))
            for _ccol, (model_name, tbl) in zip(_chart_cols, tables.items()):
                with _ccol:
                    render_chart_with_table(tbl, short_names[model_name], chart_type="stacked_bar",
                                             key=f"cmp_chart_{metric_name}_{model_name}")

            _metric_facts = {
                "chart": metric_name, "segment_context": segment_for_compare,
                "filters": {"time_period": time_mode, "months_included": selected_months},
                "models_compared": {short_names[m]: _ai_facts[short_names[m]].get(metric_name)
                                     for m in tables if _ai_facts[short_names[m]].get(metric_name)},
            }
            render_chart_ai_blurb(_metric_facts,
                                   key=f"cmp_aiblurb_{metric_name}_{'_'.join(short_names[m] for m in tables)}")

            model_names = list(tables.keys())
            _sig_month = sig_test_col
            _any_sig = False

            if sig_mode == "Model vs Model":
                # Pairwise significance
                rows_index = tables[model_names[0]].iloc[1:]["Unnamed: 0"].tolist()
                sig_rows = []
                for row_label in rows_index:
                    row_out = {"Category": row_label}
                    base_vals, n_vals = {}, {}
                    for m in model_names:
                        t = tables[m]
                        if _sig_month not in t.columns:
                            continue
                        match = t[t["Unnamed: 0"] == row_label]
                        base_vals[m] = float(match[_sig_month].values[0]) / 100 if len(match) else None
                        n_vals[m] = float(t.iloc[0][_sig_month]) if _sig_month in t.columns else 0
                    for i, m1 in enumerate(model_names):
                        for m2 in model_names[i + 1:]:
                            p1, p2 = base_vals.get(m1), base_vals.get(m2)
                            n1, n2 = n_vals.get(m1, 0), n_vals.get(m2, 0)
                            col_label = f"{short_names[m1]} vs {short_names[m2]}"
                            if p1 is None or p2 is None or n1 < 30 or n2 < 30:
                                row_out[col_label] = "—"
                            else:
                                res = calculate_significance(p1, n1, p2, n2)
                                if res["tier"] == "95":
                                    winner = short_names[m1] if res['z_score'] > 0 else short_names[m2]
                                    row_out[col_label] = f"{winner} higher ✓"
                                    _any_sig = True
                                elif res["tier"] == "90":
                                    winner = short_names[m1] if res['z_score'] > 0 else short_names[m2]
                                    row_out[col_label] = f"{winner} higher ~"
                                    _any_sig = True
                                else:
                                    row_out[col_label] = "Similar"
                    sig_rows.append(row_out)

                with st.expander(f"Significance — {metric_name} ({_sig_month})" + (" ⚡" if _any_sig else ""), expanded=False):
                    st.caption("✓ = significantly different (95% confidence) · ~ = likely different (90%) · Similar = no clear difference · — = too few respondents (n<30). Unpooled Z-test.")
                    _sig_df = pd.DataFrame(sig_rows)
                    def _color_sig_cells(val):
                        if isinstance(val, str):
                            if "✓" in val: return "background-color:#E8F5E9;color:#1B5E20"
                            if "~" in val: return "background-color:#F1F8E9;color:#33691E"
                        return ""
                    st.dataframe(_sig_df.style.map(_color_sig_cells, subset=[c for c in _sig_df.columns if c != "Category"]),
                                 use_container_width=True, hide_index=True)

            else:
                # Model vs Overall Market — each model compared to full-segment baseline
                try:
                    baseline_tbl = builder(engine, _baseline_df, segment_for_compare)
                    if time_mode != "All Months":
                        keep_cols = ["Unnamed: 0", "All"] + [m for m in selected_months if m in baseline_tbl.columns]
                        baseline_tbl = baseline_tbl[[c for c in keep_cols if c in baseline_tbl.columns]]
                    _ov_sig_rows = []
                    rows_index = baseline_tbl.iloc[1:]["Unnamed: 0"].tolist()
                    for row_label in rows_index:
                        row_out = {"Category": row_label}
                        _bl_match = baseline_tbl[baseline_tbl["Unnamed: 0"] == row_label]
                        _bl_p = float(_bl_match[_sig_month].values[0]) / 100 if (len(_bl_match) and _sig_month in baseline_tbl.columns) else None
                        _bl_n = float(baseline_tbl.iloc[0][_sig_month]) if _sig_month in baseline_tbl.columns else 0
                        for m in model_names:
                            t = tables[m]
                            match = t[t["Unnamed: 0"] == row_label]
                            _mp = float(match[_sig_month].values[0]) / 100 if (len(match) and _sig_month in t.columns) else None
                            _mn = float(t.iloc[0][_sig_month]) if _sig_month in t.columns else 0
                            col_label = short_names[m]
                            if _bl_p is None or _mp is None or _bl_n < 30 or _mn < 30:
                                row_out[col_label] = "—"
                            else:
                                res = calculate_significance(_mp, _mn, _bl_p, _bl_n)
                                if res["tier"] == "95":
                                    row_out[col_label] = "Above avg ✓" if res['z_score'] > 0 else "Below avg ✓"
                                    _any_sig = True
                                elif res["tier"] == "90":
                                    row_out[col_label] = "Trending above" if res['z_score'] > 0 else "Trending below"
                                    _any_sig = True
                                else:
                                    row_out[col_label] = "Similar"
                        _ov_sig_rows.append(row_out)

                    with st.expander(f"vs Overall Market — {metric_name} ({_sig_month})" + (" ⚡" if _any_sig else ""), expanded=False):
                        st.caption("✓ = significantly above/below market average (95%) · Trending = likely different (90%) · Similar = no clear gap · — = too few (n<30).")
                        _ov_df = pd.DataFrame(_ov_sig_rows)
                        def _color_ov(val):
                            if isinstance(val, str):
                                if "Above avg ✓" in val: return "background-color:#E8F5E9;color:#1B5E20"
                                if "Trending above" in val: return "background-color:#F1F8E9;color:#33691E"
                                if "Below avg ✓" in val: return "background-color:#FFEBEE;color:#B71C1C"
                                if "Trending below" in val: return "background-color:#FFF3E0;color:#E65100"
                            return ""
                        _ov_cols = [c for c in _ov_df.columns if c != "Category"]
                        st.dataframe(_ov_df.style.map(_color_ov, subset=_ov_cols),
                                     use_container_width=True, hide_index=True)
                except Exception as _e:
                    st.caption(f"Baseline comparison unavailable: {_e}")


    # ── Iteration 7: AI Model Positioning Analysis ──────────────────────────
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
