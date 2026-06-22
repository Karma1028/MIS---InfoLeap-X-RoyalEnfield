"""Model-wise comparison view — MIS_Dashboard_Requirements.docx 5.2:
'Side-by-side model comparison... Bullet 350 and Classic 350 data should be
viewable on the same window pane simultaneously... support selection of any
two or more models within the same or across CC platforms.'

Per user direction (2026-06-18): this page must carry the SAME filter set
(Month Range/Quarter) and the SAME metric coverage as the Acceptor/
Rejector/Cancelled pages, not a stripped-down subset.
"""
import streamlit as st
import pandas as pd
from utils.data_engine import RE_MODEL_LABELS, month_label_to_fy_quarter
from utils.visuals import render_chart_with_table, overlay_radar_chart, overlay_grouped_bar, overlay_trend_chart
from utils.stat_engine import calculate_significance

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
    st.caption("Compare any two or more Royal Enfield models side by side, within the same or across CC platforms — same filters and metrics as the segment pages.")

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

    # Brand filter — per user request, all 124 brand/model codes are
    # browsable (not just RE's 14), AND multiple brands can be selected at
    # once so models from different manufacturers (e.g. a Royal Enfield
    # model vs a Hero model) can land in the same overlay chart together.
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
    selected_models = st.multiselect("Models to compare", all_models, default=default_models, max_selections=4)

    if len(selected_models) < 2:
        st.info("Select at least 2 models to compare.")
        return

    metric_builders = _metric_builders_for(segment_for_compare)
    metric_choice = st.selectbox("Data point", list(metric_builders.keys()))
    builder, _ = metric_builders[metric_choice]
    overlay_type = st.radio("Overlay chart type", ["Spider (Radar)", "Grouped Bar"], horizontal=True, key="cmp_overlay_type")

    tables = {}
    bases = {}
    kpi_cols = st.columns(len(selected_models))
    for col, model_name in zip(kpi_cols, selected_models):
        model_brand, code = name_to_info[model_name]
        if model_brand == "Royal Enfield":
            mdf = engine.filter_df(segment=segment_for_compare, model_code=code)
        else:
            mdf = engine.filter_df(segment=segment_for_compare, owned_brand_code=code)
        mdf = mdf[mdf['month_label'].isin(selected_months)]
        bases[model_name] = len(mdf)
        with col:
            st.metric(model_name.replace("Royal Enfield ", ""), f"N = {len(mdf):,}")
            if len(mdf) == 0:
                st.warning("No respondents for this model under the current filters.")
                continue
            tbl = builder(engine, mdf, segment_for_compare)
            if time_mode != "All Months":
                keep_cols = ["Unnamed: 0", "All"] + [m for m in selected_months if m in tbl.columns]
                tbl = tbl[keep_cols]
            tables[model_name] = tbl

    if len(tables) >= 2:
        st.markdown(f"### {metric_choice} — Overlaid Across Models")
        st.caption("All selected models on one shared chart with one legend — directly comparable shape, not separate charts per model.")
        if overlay_type == "Spider (Radar)":
            st.plotly_chart(overlay_radar_chart(tables, metric_choice), use_container_width=True, config={"displayModeBar": False})
        else:
            st.plotly_chart(overlay_grouped_bar(tables, metric_choice), use_container_width=True, config={"displayModeBar": False})

        with st.expander(f"Per-model data tables — {metric_choice}"):
            tcols = st.columns(len(tables))
            for tcol, (name, tbl) in zip(tcols, tables.items()):
                with tcol:
                    render_chart_with_table(tbl, name.replace("Royal Enfield ", ""), key=f"cmp_tbl_{metric_choice}_{name}")

    if len(tables) >= 2:
        st.markdown("### Pairwise Significance (95% Confidence, unpooled Z-test)")
        st.caption(
            "Comparisons with either base under 30 for the chosen month are shown as '—' (the n<30 rule), "
            "and 'n.s.' means tested but not significant — cells are never left blank so the table doesn't "
            "look broken/empty when nothing crosses the threshold. Per explicit instruction, significance "
            "never runs on the aggregate 'All' column — only on individual months."
        )
        model_names = list(tables.keys())
        sig_test_col = st.selectbox("Test month", selected_months, key="cmp_sig_col")
        rows_index = tables[model_names[0]].iloc[1:]["Unnamed: 0"].tolist()
        sig_rows = []
        for row_label in rows_index:
            row_out = {"Category": row_label}
            base_vals = {}
            n_vals = {}
            for m in model_names:
                t = tables[m]
                if sig_test_col not in t.columns:
                    continue
                match = t[t["Unnamed: 0"] == row_label]
                base_vals[m] = float(match[sig_test_col].values[0]) / 100 if len(match) else None
                n_vals[m] = float(t.iloc[0][sig_test_col])
            for i, m1 in enumerate(model_names):
                for m2 in model_names[i + 1:]:
                    p1, p2 = base_vals.get(m1), base_vals.get(m2)
                    n1, n2 = n_vals.get(m1), n_vals.get(m2)
                    col_label = f"{m1} vs {m2}"
                    if p1 is None or p2 is None or n1 is None or n2 is None:
                        row_out[col_label] = "—"
                        continue
                    if n1 < 30 or n2 < 30:
                        row_out[col_label] = "—"
                        continue
                    res = calculate_significance(p1, n1, p2, n2)
                    if res["tier"] == "95":
                        row_out[col_label] = f"Sig 95% ({'+' if res['z_score'] > 0 else '-'}{m1 if res['z_score'] > 0 else m2})"
                    elif res["tier"] == "90":
                        row_out[col_label] = "Directional (90%)"
                    else:
                        row_out[col_label] = "n.s."
            sig_rows.append(row_out)
        st.dataframe(pd.DataFrame(sig_rows), use_container_width=True, hide_index=True)

        st.markdown("### Month-over-Month Trend — Overlaid Across Models")
        st.caption("Each model's top category trended together on one chart, per 'overlapping at once... like area charts'.")
        st.altair_chart(overlay_trend_chart(tables, selected_months), use_container_width=True)
