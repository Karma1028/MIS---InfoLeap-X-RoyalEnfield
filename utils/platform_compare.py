"""Platform Comparison page — pick any 2 CC platforms, head-to-head."""
import copy
import streamlit as st
import pandas as pd
from utils.visuals import (
    render_chart_with_table, _render_html_table, render_collapsible_brand_table,
    render_collapsible_reasons_table, open_end_tree_to_excel,
    BRAND_CONSIDERED_COLOR, REASONS_COLOR,
)
from utils.stat_engine import calculate_significance, Z_95, Z_HIGHER_LIGHT
from utils.compare import _prune_tree_cols, _align_tree_order, _inject_cross_model_reasons_sig

_PLATFORMS = ["350CC", "450CC", "650CC"]
_PLATFORM_LABELS = {"350CC": "350 CC", "450CC": "450 CC", "650CC": "650 CC"}
_PLATFORM_COLORS = {"350CC": "#2E3192", "450CC": "#C8102E", "650CC": "#1A7A4A"}

_SEGMENT_MAP = {
    "All": "All",
    "Acceptors": "Acceptor",
    "Rejectors": "Rejector",
    "Booked but Cancelled": "Cancelled",
}

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


# ── Sig markers: Platform A vs Platform B ────────────────────────────────────
def _plat_vs_plat_sig(tbl_a, tbl_b):
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
                p_b = float(rows_b.iloc[i][col]) / 100 if i < len(rows_b) else 0.0
                res = calculate_significance(p_a, n_a, p_b, n_b)
                z = res["z_score"]
                if z >= Z_95:
                    col_markers.append("▲")
                elif z >= Z_HIGHER_LIGHT:
                    col_markers.append("△")
                else:
                    col_markers.append("")
            except Exception:
                col_markers.append("")
        markers[col] = col_markers
    return markers


# ── Hero card ────────────────────────────────────────────────────────────────
def _platform_hero(label, n, color):
    return (
        f"<div style='background:{color};border-radius:12px;padding:18px 16px 14px;"
        f"margin-bottom:14px;text-align:center;box-shadow:0 4px 18px {color}33;'>"
        f"<div style='font-size:0.62rem;text-transform:uppercase;letter-spacing:0.14em;"
        f"color:rgba(255,255,255,0.65);font-weight:700;margin-bottom:4px;'>CC Platform</div>"
        f"<div style='font-size:2rem;font-weight:900;color:#fff;letter-spacing:-0.02em;line-height:1;'>{label}</div>"
        f"<div style='font-size:0.9rem;color:rgba(255,255,255,0.75);margin-top:6px;'>n = {n:,}</div>"
        f"</div>"
    )


def _stat_row(label, value, sub, color):
    sub_html = (f'<div style="font-size:0.68rem;color:#9CA3AF;font-weight:400;margin-top:1px;">{sub}</div>'
                if sub else '')
    return (
        f"<div style='display:flex;align-items:center;justify-content:space-between;"
        f"padding:8px 10px;border-bottom:1px solid #F0EDE8;'>"
        f"<div style='font-size:0.72rem;color:#6B7280;font-weight:600;"
        f"text-transform:uppercase;letter-spacing:0.05em;'>{label}{sub_html}</div>"
        f"<div style='font-size:1.1rem;font-weight:800;color:{color};'>{value}</div>"
        f"</div>"
    )


def _kpi_card(stats_html, color):
    return (
        f"<div style='background:#fff;border:1px solid #E5E7EB;border-left:4px solid {color};"
        f"border-radius:10px;overflow:hidden;margin-bottom:14px;'>{stats_html}</div>"
    )


def _col_heading(label, color):
    return (
        f"<div style='font-size:0.75rem;font-weight:700;color:{color};"
        f"padding:4px 0 6px;border-bottom:2px solid {color}33;margin-bottom:8px;'>"
        f"◼ {label}</div>"
    )


# ── Main render ───────────────────────────────────────────────────────────────
def render_platform_compare_page(engine):
    st.markdown(
        "<div style='border-left:4px solid #C8102E;padding-left:14px;margin-bottom:4px;'>"
        "<h1 style='margin:0;font-size:2rem;'>Platform Comparison</h1>"
        "<p style='margin:4px 0 0;color:#7A7670;font-size:0.9rem;'>"
        "Head-to-head: pick any two CC platforms</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    st.sidebar.markdown("### Platform Comparison")

    seg_label = st.sidebar.selectbox("Segment", list(_SEGMENT_MAP.keys()), key="plat_cmp_segment")
    seg_val = _SEGMENT_MAP[seg_label]

    plat_a = st.sidebar.selectbox(
        "Platform A", _PLATFORMS, index=0, key="plat_cmp_a",
        format_func=lambda p: _PLATFORM_LABELS[p],
    )
    plat_b_options = [p for p in _PLATFORMS if p != plat_a]
    plat_b = st.sidebar.selectbox(
        "Platform B", plat_b_options, index=0, key="plat_cmp_b",
        format_func=lambda p: _PLATFORM_LABELS[p],
    )

    # ── Year / Month multiselect (same as model comparison) ──────────────────
    st.sidebar.markdown("### Time Period")
    month_order = engine.month_order
    _mo_parsed = [_parse_mo(m) for m in month_order]
    _avail_years = sorted(set(yr for _, yr in _mo_parsed))
    _avail_months = list(dict.fromkeys(mn for mn, _ in _mo_parsed))

    _latest_year  = _avail_years[-1]  if _avail_years  else None
    _latest_month = _avail_months[-1] if _avail_months else None

    if "plat_cmp_years" not in st.session_state:
        st.session_state["plat_cmp_years"] = [_latest_year] if _latest_year else []
    if "plat_cmp_month_names" not in st.session_state:
        st.session_state["plat_cmp_month_names"] = [_latest_month] if _latest_month else []

    if st.sidebar.button("Reset to latest month", key="plat_cmp_reset"):
        st.session_state["plat_cmp_years"] = [_latest_year] if _latest_year else []
        st.session_state["plat_cmp_month_names"] = [_latest_month] if _latest_month else []
        st.rerun()

    selected_years = st.sidebar.multiselect("Year", _avail_years, key="plat_cmp_years")
    selected_month_names = st.sidebar.multiselect("Month", _avail_months, key="plat_cmp_month_names")

    _user_cleared = (not selected_years) or (not selected_month_names)
    selected_months = [
        m for m, (mn, yr) in zip(month_order, _mo_parsed)
        if yr in selected_years and mn in selected_month_names
    ]
    if not selected_months:
        selected_months = [month_order[-1]] if month_order else []

    show_sig = st.sidebar.toggle("Significance A vs B (95%/90%)", value=True, key="plat_cmp_sig")

    color_a = _PLATFORM_COLORS[plat_a]
    color_b = _PLATFORM_COLORS[plat_b]
    label_a = _PLATFORM_LABELS[plat_a]
    label_b = _PLATFORM_LABELS[plat_b]

    # ── Build per-platform dfs (all months for "All" col, filtered for month cols) ──
    df_a_full = engine.filter_df(segment=seg_val, platform=plat_a)
    df_b_full = engine.filter_df(segment=seg_val, platform=plat_b)
    df_a = df_a_full[df_a_full["month_label"].isin(selected_months)]
    df_b = df_b_full[df_b_full["month_label"].isin(selected_months)]

    n_a, n_b = len(df_a), len(df_b)

    # ── Hero row ──────────────────────────────────────────────────────────────
    col_a, col_vs, col_b = st.columns([5, 1, 5])
    with col_a:
        st.markdown(_platform_hero(label_a, n_a, color_a), unsafe_allow_html=True)
        if n_a == 0:
            st.warning("No data for Platform A with selected filters.")
    with col_vs:
        st.markdown(
            "<div style='display:flex;align-items:center;justify-content:center;"
            "height:100%;font-size:1.6rem;font-weight:900;color:#9CA3AF;padding-top:24px;'>VS</div>",
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(_platform_hero(label_b, n_b, color_b), unsafe_allow_html=True)
        if n_b == 0:
            st.warning("No data for Platform B with selected filters.")

    if n_a == 0 or n_b == 0:
        return

    # KPI stat cards
    kpi_col_a, _, kpi_col_b = st.columns([5, 1, 5])

    def _build_kpi_stats(df, color):
        stats = []
        _AGE_MP = {1.0: 21.5, 2.0: 30.5, 3.0: 40.5, 4.0: 50.0}
        avg_age = df["age_grp"].map(_AGE_MP).mean()
        if avg_age == avg_age:
            stats.append(_stat_row("Avg Age", f"{avg_age:.1f} yrs", "", color))
        ftb_n = df["dq1a"].isin([3.0, 4.0]).sum()
        ftb_base = df["dq1a"].notna().sum()
        ftb_pct = ftb_n / ftb_base * 100 if ftb_base else 0
        stats.append(_stat_row("First-Time Buyers", f"{ftb_pct:.0f}%", f"{int(ftb_n):,} of {int(ftb_base):,}", color))
        inc_tbl = engine.household_income_table(df, base_label=seg_val, numeric=True)
        _inc_rows = inc_tbl.iloc[1:]
        if not _inc_rows.empty:
            try:
                _modal = str(_inc_rows.loc[_inc_rows["All"].astype(float).idxmax(), "Unnamed: 0"])
                stats.append(_stat_row("Household Income", _modal, "most common bracket", color))
            except Exception:
                pass
        edu_tbl = engine.education_table(df, base_label=seg_val, numeric=True)
        _edu_rows = edu_tbl.iloc[1:]
        if not _edu_rows.empty:
            try:
                _modal = str(_edu_rows.loc[_edu_rows["All"].astype(float).idxmax(), "Unnamed: 0"])
                stats.append(_stat_row("Education", _modal, "most common level", color))
            except Exception:
                pass
        return stats

    with kpi_col_a:
        stats = _build_kpi_stats(df_a, color_a)
        if stats:
            st.markdown(_kpi_card("".join(stats), color_a), unsafe_allow_html=True)
    with kpi_col_b:
        stats = _build_kpi_stats(df_b, color_b)
        if stats:
            st.markdown(_kpi_card("".join(stats), color_b), unsafe_allow_html=True)

    st.divider()

    # ── Caption ───────────────────────────────────────────────────────────────
    _sel_lbl = ", ".join(selected_months) if selected_months else "none"
    st.caption(f"All column = full survey period (unfiltered). Selected months: {_sel_lbl}.")

    # ── Trim helper ───────────────────────────────────────────────────────────
    def _cmp_trim(tbl):
        keep = ["Unnamed: 0", "All"] + [m for m in selected_months if m in tbl.columns]
        return tbl[[c for c in keep if c in tbl.columns]]

    # ── Metric sections ───────────────────────────────────────────────────────
    _metrics = [
        ("Age Distribution",  lambda e, d, s: e.age_table(d, base_label=s, numeric=True)),
        ("Household Income",  lambda e, d, s: e.household_income_table(d, base_label=s, numeric=True)),
        ("Education",         lambda e, d, s: e.education_table(d, base_label=s, numeric=True)),
        ("Occupation",        lambda e, d, s: e.occupation_table(d, base_label=s, numeric=True)),
        ("Type of Buyer",     lambda e, d, s: e.type_of_buyer_table(d, base_label=s, numeric=True)),
    ]
    if seg_val in ("All", "Acceptor"):
        _metrics += [
            ("Additional + Replaced — CC Wise",
             lambda e, d, s: e.additional_replaced_table(d, by="cc", base_label=s, numeric=True)),
        ]

    for metric_name, builder in _metrics:
        tbl_a = builder(engine, df_a_full, seg_val)
        tbl_b = builder(engine, df_b_full, seg_val)
        if tbl_a is None or tbl_b is None or tbl_a.empty or tbl_b.empty:
            continue

        tbl_a_t = _cmp_trim(tbl_a)
        tbl_b_t = _cmp_trim(tbl_b)

        sig_a, sig_b = None, None
        if show_sig:
            try:
                sig_a_raw = _plat_vs_plat_sig(tbl_a_t, tbl_b_t)
                sig_b_raw = _plat_vs_plat_sig(tbl_b_t, tbl_a_t)
                sig_a = {col: [m if m in ("▲", "△") else "" for m in markers] for col, markers in sig_a_raw.items()}
                sig_b = {col: [m if m in ("▲", "△") else "" for m in markers] for col, markers in sig_b_raw.items()}
            except Exception:
                pass

        with st.container(border=True):
            st.markdown(f"**{metric_name}**")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(_col_heading(label_a, color_a), unsafe_allow_html=True)
                render_chart_with_table(
                    tbl_a_t, f"{label_a} — {metric_name}",
                    color=color_a,
                    key=f"plat_cmp_{metric_name}_{plat_a}_chart",
                    chart_type="stacked_bar",
                    col_sig_markers=sig_a,
                    allow_all_sig=True,
                )
            with c2:
                st.markdown(_col_heading(label_b, color_b), unsafe_allow_html=True)
                render_chart_with_table(
                    tbl_b_t, f"{label_b} — {metric_name}",
                    color=color_b,
                    key=f"plat_cmp_{metric_name}_{plat_b}_chart",
                    chart_type="stacked_bar",
                    col_sig_markers=sig_b,
                    allow_all_sig=True,
                )

    # ── Brand Wise (collapsible) ──────────────────────────────────────────────
    if seg_val in ("All", "Acceptor"):
        bw_a = engine.additional_replaced_table(df_a_full, by="brand", base_label=seg_val, numeric=True)
        bw_b = engine.additional_replaced_table(df_b_full, by="brand", base_label=seg_val, numeric=True)
        if bw_a is not None and bw_b is not None and not bw_a.empty and not bw_b.empty:
            _bw_rollups = set(engine.manufacturers())
            bw_a_t = _cmp_trim(bw_a)
            bw_b_t = _cmp_trim(bw_b)
            with st.container(border=True):
                st.markdown("**Additional + Replaced — Brand Wise**")
                bw_col_a, bw_col_b = st.columns(2)
                with bw_col_a:
                    st.markdown(_col_heading(label_a, color_a), unsafe_allow_html=True)
                    render_collapsible_brand_table(
                        bw_a_t, title=label_a, rollup_labels=_bw_rollups,
                        accent=color_a, key_suffix=f"plat_bw_a_{plat_a}",
                    )
                with bw_col_b:
                    st.markdown(_col_heading(label_b, color_b), unsafe_allow_html=True)
                    render_collapsible_brand_table(
                        bw_b_t, title=label_b, rollup_labels=_bw_rollups,
                        accent=color_b, key_suffix=f"plat_bw_b_{plat_b}",
                    )

    # ── Open-Ended Netting Comparison ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💬 Open-Ended Netting Comparison")
    st.caption("Side-by-side 4-level netting taxonomy for the selected platforms.")

    _reasons_tables_to_show = []
    if seg_val == "Acceptor":
        _reasons_tables_to_show.append(("Key Buying Factors (Why Bought)", "mq2a", REASONS_COLOR))
    elif seg_val in ("Rejector", "Cancelled"):
        _reasons_tables_to_show.append(("Why They Considered RE First", "mq2c", BRAND_CONSIDERED_COLOR))
        _rej_lbl = "Reasons for Rejection" if seg_val == "Rejector" else "Reasons for Cancelling"
        _reasons_tables_to_show.append((_rej_lbl, "mq3a", REASONS_COLOR))
    else:
        _reasons_tables_to_show.append(("Acceptors — Key Buying Factors", "mq2a", REASONS_COLOR))
        _reasons_tables_to_show.append(("Rejectors — Reasons for Rejection", "mq3a", REASONS_COLOR))
        _reasons_tables_to_show.append(("Booked & Cancelled — Reasons for Cancelling", "mq3a", REASONS_COLOR))

    _keep_cols = {"All"} | set(selected_months)
    _plat_pairs = [(plat_a, label_a, color_a, df_a_full), (plat_b, label_b, color_b, df_b_full)]

    for _tbl_idx, (_tbl_title, _prefix, _tbl_color) in enumerate(_reasons_tables_to_show):
        with st.expander(f"💬 {_tbl_title}", expanded=True):
            st.markdown(f"#### {_tbl_title}")
            _p_cols = st.columns(2)

            _trees = {}
            _tree_base_ns = {}
            for _plat_key, _plat_lbl, _plat_color, _plat_df in _plat_pairs:
                _seg_lbl = seg_val
                _mdf = _plat_df.copy()
                if seg_val in ("All", "Overview"):
                    if "Key Buying Factors" in _tbl_title:
                        _seg_lbl = "Acceptor"
                    elif "Rejection" in _tbl_title:
                        _seg_lbl = "Rejector"
                    else:
                        _seg_lbl = "Cancelled"
                    _mdf = _mdf[_mdf["segment"] == _seg_lbl]
                if len(_mdf) > 0:
                    _r_tree = copy.deepcopy(engine.reasons_tree_data(_mdf, base_label=_seg_lbl, broad_prefix=_prefix))
                    _prune_tree_cols(_r_tree, _keep_cols)
                    _trees[_plat_key] = (_r_tree, _seg_lbl)
                    _tree_base_ns[_plat_key] = _r_tree.get("col_bases", {}).get("All", 0)

            # Align order + inject cross-platform sig
            if plat_a in _trees and plat_b in _trees:
                _align_tree_order(_trees[plat_a][0], _trees[plat_b][0])
                _inject_cross_model_reasons_sig(
                    _trees[plat_a][0], _trees[plat_b][0],
                    _tree_base_ns[plat_a], _tree_base_ns[plat_b],
                )

            for _ci, (_plat_key, _plat_lbl, _plat_color, _) in enumerate(_plat_pairs):
                with _p_cols[_ci]:
                    st.markdown(_col_heading(_plat_lbl, _plat_color), unsafe_allow_html=True)
                    if _plat_key in _trees:
                        _r_tree, _seg_lbl = _trees[_plat_key]
                        with st.container(border=True):
                            render_collapsible_reasons_table(
                                _r_tree,
                                f"{_plat_lbl} — {_tbl_title}",
                                color=_tbl_color,
                                key_suffix=f"plat_cmp_{_prefix}_{_tbl_idx}_{_plat_key}",
                            )
                        _xl = open_end_tree_to_excel(_r_tree, f"{_plat_lbl} — {_tbl_title}"[:31], show_sig=True)
                        if _xl:
                            st.download_button(
                                "⬇ Excel", _xl,
                                f"{_prefix}_{_plat_key.lower()}_{_tbl_idx}.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"dl_plat_tree_{_prefix}_{_tbl_idx}_{_plat_key}",
                            )
                    else:
                        st.caption("No data.")
