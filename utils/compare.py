"""Model-wise comparison view — Head-to-Head Model Benchmark Page:
Side-by-side model comparison for any 2 selected models across CC platforms.
Combines pristine stacked-bar charts, full data tables, significance testing,
and 4-level open-ended netting taxonomy trees.
"""
import base64
import copy
import html as _html
import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.data_engine import RE_MODEL_LABELS, month_label_to_fy_quarter
from utils.visuals import (
    render_chart_with_table, _lighten, _pct_label, MUTED, INFOLEAP_GREEN, RE_RED, INFOLEAP_ORANGE,
    BRAND_CONSIDERED_COLOR, REASONS_COLOR, render_collapsible_reasons_table, PLOTLY_CONFIG
)
from utils.stat_engine import calculate_significance, compare_to_baseline_by_column
from utils.ai_providers import call_llm, get_active_provider
from utils.ai_summary import render_chart_ai_blurb
from utils.model_images import model_image_path

# Palette: two distinct, accessible colors for the two models
_CMP_COLOR_A = "#2E3192"   # deep navy/indigo
_CMP_COLOR_B = "#C8102E"   # RE red


def _comparison_bar_chart(tbl1, tbl2, m1_short, m2_short, title, col="All"):
    """Grouped horizontal bar chart: Model A vs Model B for every category."""
    cat_rows1 = tbl1.iloc[1:].copy()
    cat_rows2 = tbl2.iloc[1:].copy()

    def _pcts(rows, c):
        out = []
        for _, r in rows.iterrows():
            try:
                out.append(float(str(r[c]).rstrip('%')))
            except (ValueError, TypeError):
                out.append(0.0)
        return out

    cats1 = cat_rows1['Unnamed: 0'].tolist()
    vals1 = _pcts(cat_rows1, col)
    vals2_map = {}
    for _, r in cat_rows2.iterrows():
        try:
            vals2_map[r['Unnamed: 0']] = float(str(r[col]).rstrip('%'))
        except (ValueError, TypeError):
            vals2_map[r['Unnamed: 0']] = 0.0
    vals2 = [vals2_map.get(c, 0.0) for c in cats1]

    # Sort by average descending
    order = sorted(range(len(cats1)), key=lambda i: (vals1[i] + vals2[i]) / 2, reverse=True)
    cats_sorted  = [cats1[i] for i in order]
    vals1_sorted = [vals1[i] for i in order]
    vals2_sorted = [vals2[i] for i in order]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=m1_short, y=cats_sorted, x=vals1_sorted,
        orientation='h', marker_color=_CMP_COLOR_A,
        text=[f"{v:.0f}%" for v in vals1_sorted], textposition='outside',
        textfont=dict(size=11, color=_CMP_COLOR_A, family="Inter,sans-serif"),
        hovertemplate=f"<b>{m1_short}</b><br>%{{y}}: %{{x:.1f}}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name=m2_short, y=cats_sorted, x=vals2_sorted,
        orientation='h', marker_color=_CMP_COLOR_B,
        text=[f"{v:.0f}%" for v in vals2_sorted], textposition='outside',
        textfont=dict(size=11, color=_CMP_COLOR_B, family="Inter,sans-serif"),
        hovertemplate=f"<b>{m2_short}</b><br>%{{y}}: %{{x:.1f}}%<extra></extra>",
    ))
    max_val = max(max(vals1_sorted or [0]), max(vals2_sorted or [0]), 1)
    n_cats = len(cats_sorted)
    chart_h = max(220, n_cats * 42 + 60)
    fig.update_layout(
        barmode='group',
        height=chart_h,
        margin=dict(l=0, r=60, t=28, b=10),
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='left', x=0,
                    font=dict(size=12, family="Inter,sans-serif")),
        xaxis=dict(range=[0, max_val * 1.25], showgrid=True, gridcolor='#F0EDE8',
                   ticksuffix='%', tickfont=dict(size=11, family="Inter,sans-serif"),
                   zeroline=False),
        yaxis=dict(tickfont=dict(size=11, family="Inter,sans-serif"), autorange='reversed'),
        font=dict(family="Inter,sans-serif"),
        title=dict(text=f"<b>{title}</b>", font=dict(size=13, color='#1E293B'), x=0, xanchor='left'),
    )
    return fig


def _delta_badge_html(val1, val2, label):
    """Gap badge: Model A vs Model B difference in pp."""
    diff = val1 - val2
    if abs(diff) < 1:
        return ""
    color = _CMP_COLOR_A if diff > 0 else _CMP_COLOR_B
    name = label.split()[-1][:10]
    arrow = "↑" if diff > 0 else "↓"
    return (f"<span style='font-size:0.7rem;padding:2px 7px;border-radius:4px;"
            f"background:{color}15;color:{color};font-weight:700;'>"
            f"{arrow} {abs(diff):.0f}pp</span>")


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
}
REJECTOR_BUILDERS = {}


def _metric_builders_for(segment_for_compare):
    builders = dict(DEMOGRAPHIC_BUILDERS)
    if segment_for_compare in ("All", "Acceptor"):
        builders.update(ACCEPTOR_BUILDERS)
    if segment_for_compare in ("All", "Rejector", "Cancelled"):
        builders.update(REJECTOR_BUILDERS)
    return builders


def _model_vs_model_sig_markers(tbl_a, tbl_b):
    """For each value column, for each category row: 2-prop Z-test Model A vs Model B.
    Returns dict {col: [marker_per_data_row, ...]} for tbl_a (▲ = A higher, ▼ = A lower).
    Base n is tbl.iloc[0][col]. Skips cols missing from either table."""
    data_cols = [c for c in tbl_a.columns if c not in ("Unnamed: 0",)]
    base_a = tbl_a.iloc[0]
    base_b = tbl_b.iloc[0]
    rows_a = tbl_a.iloc[1:].reset_index(drop=True)
    rows_b = tbl_b.iloc[1:].reset_index(drop=True)
    markers = {}
    for col in data_cols:
        if col not in tbl_b.columns:
            continue
        try:
            n_a = int(float(base_a[col]))
            n_b = int(float(base_b[col]))
        except (ValueError, TypeError):
            continue
        col_markers = []
        for i in range(len(rows_a)):
            try:
                p_a = float(rows_a.iloc[i][col]) / 100
                if i < len(rows_b):
                    p_b = float(rows_b.iloc[i][col]) / 100
                else:
                    p_b = 0.0
                res = calculate_significance(p_a, n_a, p_b, n_b)
                z = res["z_score"]
                from utils.stat_engine import Z_95, Z_HIGHER_LIGHT
                if z >= Z_95:
                    col_markers.append("▲")
                elif z >= Z_HIGHER_LIGHT:
                    col_markers.append("△")
                elif z <= -Z_95:
                    col_markers.append("▼")
                else:
                    col_markers.append("")
            except Exception:
                col_markers.append("")
        markers[col] = col_markers
    return markers


def _prune_tree_cols(tree, keep_cols):
    """Remove time columns not in keep_cols from every item in the tree."""
    keep_set = set(keep_cols)
    tree['columns'] = [c for c in tree.get('columns', []) if c in keep_set]
    if 'col_bases' in tree:
        tree['col_bases'] = {k: v for k, v in tree['col_bases'].items() if k in keep_set}

    def _prune(item):
        for field in ('pcts', 'numeric_pcts', 'sig_markers'):
            if field in item:
                item[field] = {k: v for k, v in item[field].items() if k in keep_set}
        for child_key in ('nets', 'subnets', 'items'):
            for child in item.get(child_key, []):
                _prune(child)

    for s in tree.get('supernets', []):
        _prune(s)


def _align_tree_order(ref_tree, other_tree):
    """Reorder other_tree's supernets/nets/subnets to match ref_tree's order.
    Items present in other but not in ref are appended at end."""
    def _reorder(ref_list, other_list, key='name'):
        ref_order = [item[key] for item in ref_list]
        other_map = {item[key]: item for item in other_list}
        ordered = [other_map[k] for k in ref_order if k in other_map]
        extra = [item for item in other_list if item[key] not in set(ref_order)]
        return ordered + extra

    ref_supers = ref_tree.get('supernets', [])
    other_supers = other_tree.get('supernets', [])
    other_super_map = {s['name']: s for s in other_supers}

    new_supers = []
    for rs in ref_supers:
        os = other_super_map.get(rs['name'])
        if os:
            ref_nets = rs.get('nets', [])
            other_nets = os.get('nets', [])
            other_net_map = {n['name']: n for n in other_nets}
            new_nets = []
            for rn in ref_nets:
                on = other_net_map.get(rn['name'])
                if on:
                    ref_subs = rn.get('subnets', [])
                    on['subnets'] = _reorder(ref_subs, on.get('subnets', []))
                    new_nets.append(on)
            extra_nets = [n for n in other_nets if n['name'] not in {rn['name'] for rn in ref_nets}]
            os['nets'] = new_nets + extra_nets
            new_supers.append(os)
    extra_supers = [s for s in other_supers if s['name'] not in {rs['name'] for rs in ref_supers}]
    other_tree['supernets'] = new_supers + extra_supers


def _inject_cross_model_reasons_sig(tree_a, tree_b, n_a, n_b):
    """Inject cross-model sig into 'All' column of each tree item. Higher direction only."""
    from utils.stat_engine import Z_95, Z_HIGHER_LIGHT

    def _markers(pct_a, pct_b):
        if n_a < 30 or n_b < 30:
            return "", ""
        try:
            res = calculate_significance(pct_a / 100, n_a, pct_b / 100, n_b)
            z = res["z_score"]
            if z >= Z_95:
                return "▲", ""
            elif z >= Z_HIGHER_LIGHT:
                return "△", ""
            elif z <= -Z_95:
                return "", "▲"
            elif z <= -Z_HIGHER_LIGHT:
                return "", "△"
        except Exception:
            pass
        return "", ""

    def _patch(item_a, item_b):
        pa = item_a.get('numeric_pcts', {}).get('All', 0)
        pb = item_b.get('numeric_pcts', {}).get('All', 0)
        ma, mb = _markers(pa, pb)
        for item, m in ((item_a, ma), (item_b, mb)):
            item['sig_markers']['All'] = m
            base_str = f"{item['numeric_pcts'].get('All', 0):.0f}%"
            item['pcts']['All'] = f"{base_str} {m}".strip() if m else base_str

    sb_map = {s['name']: s for s in tree_b.get('supernets', [])}
    for sa in tree_a.get('supernets', []):
        sb = sb_map.get(sa['name'])
        if not sb:
            continue
        _patch(sa, sb)
        nb_map = {n['name']: n for n in sb.get('nets', [])}
        for na in sa.get('nets', []):
            nb = nb_map.get(na['name'])
            if not nb:
                continue
            _patch(na, nb)
            subb_map = {sub['name']: sub for sub in nb.get('subnets', [])}
            for sub_a in na.get('subnets', []):
                sub_b = subb_map.get(sub_a['name'])
                if not sub_b:
                    continue
                _patch(sub_a, sub_b)


def render_comparison_page(engine):
    st.markdown("<h1>Model Comparison</h1>", unsafe_allow_html=True)
    st.caption("Compare exactly 2 models side by side, within the same or across CC platforms — same filters and metrics as the segment pages.")

    st.sidebar.markdown("### Comparison Filters")
    segment_for_compare = st.sidebar.selectbox("Segment context", ["All", "Acceptor", "Rejector", "Cancelled"], key="cmp_segment")

    st.sidebar.markdown("### Time Period")
    month_order = engine.month_order

    # Parse month_order entries like "August'2025" → (month_abbr, year)
    _MN_ABBR = {
        "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
        "May": "May", "June": "Jun", "July": "Jul", "August": "Aug",
        "September": "Sep", "October": "Oct", "November": "Nov", "December": "Dec",
    }
    def _parse_mo(m):
        parts = m.split("'")
        full_yr = "20" + parts[1] if len(parts[1]) == 2 else parts[1]
        abbr = _MN_ABBR.get(parts[0], parts[0][:3])
        return abbr, full_yr

    _mo_parsed = [_parse_mo(m) for m in month_order]
    _avail_years = sorted(set(yr for _, yr in _mo_parsed))
    _avail_months = list(dict.fromkeys(mn for mn, _ in _mo_parsed))  # order-preserving unique

    _latest_year = _avail_years[-1] if _avail_years else None
    _latest_month = _avail_months[-1] if _avail_months else None

    # Initialize session state on first load so default = latest month only
    if "cmp_years" not in st.session_state:
        st.session_state["cmp_years"] = [_latest_year] if _latest_year else []
    if "cmp_months" not in st.session_state:
        st.session_state["cmp_months"] = [_latest_month] if _latest_month else []

    if st.sidebar.button("Reset to latest month", key="cmp_reset"):
        st.session_state["cmp_years"] = [_latest_year] if _latest_year else []
        st.session_state["cmp_months"] = [_latest_month] if _latest_month else []
        st.rerun()

    selected_years = st.sidebar.multiselect("Year", _avail_years, key="cmp_years")
    selected_month_names = st.sidebar.multiselect("Month", _avail_months, key="cmp_months")

    _user_cleared = (not selected_years) or (not selected_month_names)
    selected_months = [
        m for m, (mn, yr) in zip(month_order, _mo_parsed)
        if yr in selected_years and mn in selected_month_names
    ]
    if not selected_months:
        selected_months = [month_order[-1]] if month_order else []

    # If user explicitly deselected all years or months, show only the All column
    # (no current-month column). Otherwise show All + current month.
    current_month = "" if _user_cleared else (selected_months[-1] if selected_months else "")

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

    # Load model DataFrames ONCE — two versions per model:
    #   model_dfs_full : unfiltered by month → "All" column always shows all-time totals
    #   model_dfs      : filtered by selected months → used for open-ended netting counts
    model_dfs_full = {}
    model_dfs = {}
    short_names = {}
    for model_name in selected_models:
        model_brand, code = name_to_info[model_name]
        if model_brand == "Royal Enfield":
            mdf = engine.filter_df(segment=segment_for_compare, model_code=code)
        else:
            mdf = engine.filter_df(segment=segment_for_compare, owned_brand_code=code)
        model_dfs_full[model_name] = mdf                                     # all months
        model_dfs[model_name] = mdf[mdf['month_label'].isin(selected_months)]  # filtered
        short_names[model_name] = model_name.replace("Royal Enfield ", "")

    # Segment split bar removed per user instruction for clean benchmark comparison

    # Clean 2-Column Model Benchmark Comparison — 5 Core Demographic Metrics
    st.markdown("### Model Benchmark — Core Profile Metrics")
    _sel_lbl = ", ".join(selected_months) if selected_months else "none"
    st.caption(f"All column = full survey period (unfiltered). Selected months: {_sel_lbl}.")

    m1_name, m2_name = selected_models[0], selected_models[1]
    m1_short, m2_short = short_names[m1_name], short_names[m2_name]
    # Use FULL (unfiltered) dfs so "All" column always reflects entire survey period
    m1_df, m2_df = model_dfs_full[m1_name], model_dfs_full[m2_name]

    def _cmp_trim(tbl, cur_month):
        """Keep category + All (unfiltered all-time) + all selected months."""
        keep = ["Unnamed: 0", "All"] + [m for m in selected_months if m in tbl.columns]
        return tbl[[c for c in keep if c in tbl.columns]]

    all_builders = _metric_builders_for(segment_for_compare)
    for metric_name, (builder, chart_type) in all_builders.items():
        tbl1 = builder(engine, m1_df, segment_for_compare)
        tbl2 = builder(engine, m2_df, segment_for_compare)
        if tbl1.empty and tbl2.empty:
            continue
        tbl1_t = _cmp_trim(tbl1, current_month)
        tbl2_t = _cmp_trim(tbl2, current_month)

        # Sig markers: Model A vs Model B, column by column — higher only, no lower
        _sig_a = _model_vs_model_sig_markers(tbl1_t, tbl2_t)  # ▲/△ = A higher than B
        # B markers: flip — where A was higher, B shows nothing; where A was lower, B shows higher
        _sig_b_raw = _model_vs_model_sig_markers(tbl2_t, tbl1_t)
        # Strip ▼ from both (only show higher direction per user request)
        _sig_a = {col: [m if m in ("▲", "△") else "" for m in markers] for col, markers in _sig_a.items()}
        _sig_b = {col: [m if m in ("▲", "△") else "" for m in markers] for col, markers in _sig_b_raw.items()}

        # Insight: top category per model (from All column)
        def _top_cat_info(tbl):
            rows = tbl.iloc[1:]
            if rows.empty:
                return None, 0.0
            try:
                r = rows.loc[rows['All'].astype(float).idxmax()]
                return str(r['Unnamed: 0']), float(r['All'])
            except Exception:
                return None, 0.0

        cat1, pct1 = _top_cat_info(tbl1)
        cat2, pct2 = _top_cat_info(tbl2)

        _is_brand_wise = "Brand Wise" in metric_name
        with st.container(border=True):
            st.markdown(f"**{metric_name}**")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(
                    f"<div style='font-size:0.75rem;font-weight:700;color:{_CMP_COLOR_A};"
                    f"padding:4px 0 6px;border-bottom:2px solid {_CMP_COLOR_A}33;margin-bottom:8px;'>"
                    f"◼ {m1_short}</div>",
                    unsafe_allow_html=True,
                )
                if _is_brand_wise:
                    from utils.visuals import _render_html_table
                    _render_html_table(tbl1_t, accent=_CMP_COLOR_A)
                else:
                    render_chart_with_table(
                        tbl1_t, f"{m1_short} — {metric_name}",
                        color=_CMP_COLOR_A,
                        key=f"cmp_{metric_name}_{m1_short}_chart",
                        chart_type="stacked_bar",
                        col_sig_markers=_sig_a,
                        allow_all_sig=True,
                    )
            with c2:
                st.markdown(
                    f"<div style='font-size:0.75rem;font-weight:700;color:{_CMP_COLOR_B};"
                    f"padding:4px 0 6px;border-bottom:2px solid {_CMP_COLOR_B}33;margin-bottom:8px;'>"
                    f"◼ {m2_short}</div>",
                    unsafe_allow_html=True,
                )
                if _is_brand_wise:
                    from utils.visuals import _render_html_table
                    _render_html_table(tbl2_t, accent=_CMP_COLOR_B)
                else:
                    render_chart_with_table(
                        tbl2_t, f"{m2_short} — {metric_name}",
                        color=_CMP_COLOR_B,
                        key=f"cmp_{metric_name}_{m2_short}_chart",
                        chart_type="stacked_bar",
                        col_sig_markers=_sig_b,
                        allow_all_sig=True,
                    )
            # Bottom insight line
            if cat1 and cat2:
                if cat1 == cat2:
                    _ins = (f"Both models share <b>{cat1}</b> as top {metric_name.lower()} — "
                            f"gap <b>{abs(pct1-pct2):.0f}pp</b> "
                            f"({'higher for ' + m1_short if pct1 > pct2 else 'higher for ' + m2_short}).")
                else:
                    _ins = (f"<b style='color:{_CMP_COLOR_A};'>{m1_short}</b> skews "
                            f"<b>{cat1}</b> ({pct1:.0f}%) vs "
                            f"<b style='color:{_CMP_COLOR_B};'>{m2_short}</b> at "
                            f"<b>{cat2}</b> ({pct2:.0f}%) — distinct buyer profiles.")
                st.markdown(
                    f"<div style='font-size:0.72rem;color:#4A5568;padding:6px 8px;border-top:1px solid #F0EDE8;"
                    f"margin-top:6px;background:#FAFAF9;border-radius:0 0 8px 8px;'>{_ins}</div>",
                    unsafe_allow_html=True,
                )

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

            # Build all trees first so we can compute cross-model sig before rendering.
            # Use full (all-time) df so "All" column = complete base n.
            # After building, prune to "All" + selected_months so display matches
            # chart/table sections (only selected months shown as time columns).
            _keep_cols = {"All"} | set(selected_months)
            _trees = {}
            _tree_base_ns = {}
            for _mi, model_name in enumerate(selected_models):
                _seg_lbl = segment_for_compare
                mdf = model_dfs_full[model_name]
                if segment_for_compare in ("All", "Overview"):
                    if "Key Buying Factors" in _tbl_title:
                        _seg_lbl = "Acceptor"
                    elif "Rejection" in _tbl_title:
                        _seg_lbl = "Rejector"
                    else:
                        _seg_lbl = "Cancelled"
                    mdf = mdf[mdf['segment'] == _seg_lbl]
                if len(mdf) > 0:
                    _r_tree = copy.deepcopy(engine.reasons_tree_data(mdf, base_label=_seg_lbl, broad_prefix=_prefix))
                    _prune_tree_cols(_r_tree, _keep_cols)
                    _trees[model_name] = (_r_tree, _seg_lbl)
                    _tree_base_ns[model_name] = _r_tree.get('col_bases', {}).get('All', 0)

            # Align all trees to model[0] order; inject cross-model sig for 2-model pairs
            _ref_model = selected_models[0]
            if _ref_model in _trees:
                for _other in selected_models[1:]:
                    if _other in _trees:
                        _align_tree_order(_trees[_ref_model][0], _trees[_other][0])
            if len(selected_models) == 2:
                _mn_a, _mn_b = selected_models[0], selected_models[1]
                if _mn_a in _trees and _mn_b in _trees:
                    _inject_cross_model_reasons_sig(
                        _trees[_mn_a][0], _trees[_mn_b][0],
                        _tree_base_ns[_mn_a], _tree_base_ns[_mn_b]
                    )

            for _mi, model_name in enumerate(selected_models):
                with _m_cols[_mi]:
                    _model_color = _CMP_COLOR_A if _mi == 0 else _CMP_COLOR_B
                    st.markdown(
                        f"<div style='font-size:0.75rem;font-weight:700;color:{_model_color};"
                        f"padding:4px 0 6px;border-bottom:2px solid {_model_color}33;margin-bottom:8px;'>"
                        f"◼ {short_names[model_name]}</div>",
                        unsafe_allow_html=True,
                    )
                    if model_name in _trees:
                        _r_tree, _seg_lbl = _trees[model_name]
                        with st.container(border=True):
                            render_collapsible_reasons_table(
                                _r_tree,
                                f"{short_names[model_name]} — {_tbl_title}",
                                color=_tbl_color,
                                key_suffix=f"cmp_{_prefix}_{_tbl_idx}_{model_name.replace(' ', '_')}_{_mi}"
                            )
                    else:
                        st.caption("No data.")

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
