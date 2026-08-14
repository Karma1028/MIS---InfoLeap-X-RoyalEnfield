"""Platform Comparison page — 350CC vs 450CC vs 650CC side-by-side.

Shows key demographic and buying-factor metrics for each CC platform
in three parallel columns so cross-platform differences are immediately
visible without toggling the main sidebar filter.
"""
import streamlit as st
import pandas as pd
from utils.visuals import _render_html_table, RE_RED, INFOLEAP_GREEN, INFOLEAP_ORANGE

_PLATFORMS = ["350CC", "450CC", "650CC"]
_PLATFORM_LABELS = {"350CC": "350 CC", "450CC": "450 CC", "650CC": "650 CC"}
_PLATFORM_COLORS = {"350CC": "#2E3192", "450CC": "#C8102E", "650CC": "#1A7A4A"}

_SEGMENT_MAP = {
    "All": "All",
    "Acceptors": "Acceptor",
    "Rejectors": "Rejector",
    "Booked but Cancelled": "Cancelled",
}


def _top_row(tbl):
    """Label and % of the highest 'All' data row (skips base row)."""
    rows = tbl.iloc[1:]
    if rows.empty:
        return None, 0.0
    try:
        best = rows.loc[rows["All"].astype(float).idxmax()]
        return str(best["Unnamed: 0"]), float(best["All"])
    except Exception:
        return None, 0.0


def _kpi_tile(label, value, sub="", color="#C8102E"):
    return (
        f"<div style='background:#fff;border:1px solid #ECE9E4;border-top:3px solid {color};"
        f"border-radius:10px;padding:12px 16px;margin-bottom:10px;'>"
        f"<div style='font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;"
        f"color:#9A958D;font-weight:700;margin-bottom:4px;'>{label}</div>"
        f"<div style='font-size:1.35rem;font-weight:800;color:#1A1A1A;'>{value}</div>"
        f"{'<div style=\"font-size:0.78rem;color:#7A7670;margin-top:2px;\">'+sub+'</div>' if sub else ''}"
        f"</div>"
    )


def render_platform_compare_page(engine):
    st.markdown("<h1>Platform Comparison</h1>", unsafe_allow_html=True)
    st.caption("350 CC · 450 CC · 650 CC — key metrics side by side.")

    st.sidebar.markdown("### Platform Comparison")
    seg_label = st.sidebar.selectbox(
        "Segment", list(_SEGMENT_MAP.keys()), key="plat_cmp_segment"
    )
    seg_val = _SEGMENT_MAP[seg_label]

    month_order = engine.month_order
    _mo_short = [m.split("'")[0][:3] + "'" + m.split("'")[1][2:] for m in month_order]
    _default_lo = _mo_short[-12] if len(_mo_short) >= 12 else _mo_short[0]

    if "plat_cmp_months" not in st.session_state:
        lo_i = _mo_short.index(_default_lo)
        st.session_state["plat_cmp_months"] = (_default_lo, _mo_short[-1])

    lo, hi = st.sidebar.select_slider(
        "Month range", options=_mo_short,
        value=st.session_state.get("plat_cmp_months", (_default_lo, _mo_short[-1])),
        key="plat_cmp_months",
    )
    lo_i, hi_i = _mo_short.index(lo), _mo_short.index(hi)
    sel_months = month_order[lo_i: hi_i + 1]

    # Build per-platform dataframes
    plat_dfs = {}
    for plat in _PLATFORMS:
        pdf = engine.filter_df(segment=seg_val, platform=plat)
        pdf = pdf[pdf["month_label"].isin(sel_months)]
        plat_dfs[plat] = pdf

    # ── KPI summary row ──────────────────────────────────────────────────
    st.markdown("#### Segment Profile at a Glance")
    cols = st.columns(3)
    for ci, plat in enumerate(_PLATFORMS):
        pdf = plat_dfs[plat]
        color = _PLATFORM_COLORS[plat]
        with cols[ci]:
            st.markdown(
                f"<div style='font-size:0.8rem;font-weight:800;color:{color};"
                f"border-bottom:3px solid {color};padding-bottom:4px;margin-bottom:10px;'>"
                f"{_PLATFORM_LABELS[plat]}</div>",
                unsafe_allow_html=True,
            )
            n = len(pdf)
            st.markdown(_kpi_tile("Respondents", f"{n:,}", color=color), unsafe_allow_html=True)
            if n == 0:
                st.caption("No data for selected filters.")
                continue

            # Average age
            _AGE_MP = {1.0: 21.5, 2.0: 30.5, 3.0: 40.5, 4.0: 50.0}
            avg_age = pdf["age_grp"].map(_AGE_MP).mean()
            if avg_age == avg_age:  # not NaN
                st.markdown(_kpi_tile("Avg Age", f"{avg_age:.1f} yrs", color=color), unsafe_allow_html=True)

            # FTB %
            ftb_pct = pdf["dq1a"].isin([3.0, 4.0]).sum() / n * 100
            st.markdown(_kpi_tile("First-Time Buyers", f"{ftb_pct:.0f}%", color=color), unsafe_allow_html=True)

            # Top income
            inc_tbl = engine.household_income_table(pdf, base_label=seg_val, numeric=True)
            top_inc, inc_pct = _top_row(inc_tbl)
            if top_inc:
                st.markdown(_kpi_tile("Top Income", f"{inc_pct:.0f}%", sub=top_inc, color=color), unsafe_allow_html=True)

            # Top education
            edu_tbl = engine.education_table(pdf, base_label=seg_val, numeric=True)
            top_edu, edu_pct = _top_row(edu_tbl)
            if top_edu:
                st.markdown(_kpi_tile("Top Education", f"{edu_pct:.0f}%", sub=top_edu, color=color), unsafe_allow_html=True)

    # ── Detailed metric tables ────────────────────────────────────────────
    _metrics = [
        ("Age Distribution", lambda e, d, s: e.age_table(d, base_label=s, numeric=True)),
        ("Household Income", lambda e, d, s: e.household_income_table(d, base_label=s, numeric=True)),
        ("Education", lambda e, d, s: e.education_table(d, base_label=s, numeric=True)),
        ("Occupation", lambda e, d, s: e.occupation_table(d, base_label=s, numeric=True)),
        ("Type of Buyer", lambda e, d, s: e.type_of_buyer_table(d, base_label=s, numeric=True)),
    ]
    if seg_val in ("All", "Acceptor"):
        _metrics.append((
            "Additional + Replaced — Brand Wise",
            lambda e, d, s: e.cap_rows(e.additional_replaced_table(d, by="brand", base_label=s, numeric=True), max_rows=8),
        ))

    for metric_name, builder in _metrics:
        tbls = {}
        for plat in _PLATFORMS:
            pdf = plat_dfs[plat]
            if len(pdf) > 0:
                tbls[plat] = builder(engine, pdf, seg_val)

        if not tbls:
            continue

        with st.container(border=True):
            st.markdown(f"**{metric_name}**")
            mcols = st.columns(3)
            _is_brand_wise = "Brand Wise" in metric_name
            _bw_rollups = set(engine.manufacturers()) if _is_brand_wise else None

            for ci, plat in enumerate(_PLATFORMS):
                color = _PLATFORM_COLORS[plat]
                with mcols[ci]:
                    st.markdown(
                        f"<div style='font-size:0.72rem;font-weight:800;color:{color};"
                        f"border-bottom:2px solid {color}33;padding-bottom:4px;margin-bottom:6px;'>"
                        f"{_PLATFORM_LABELS[plat]}</div>",
                        unsafe_allow_html=True,
                    )
                    tbl = tbls.get(plat)
                    if tbl is None or tbl.empty:
                        st.caption("No data.")
                        continue
                    # Trim to All column only for compact view
                    keep = ["Unnamed: 0", "All"]
                    tbl_trim = tbl[[c for c in keep if c in tbl.columns]]
                    _render_html_table(tbl_trim, accent=color, rollup_labels=_bw_rollups)
