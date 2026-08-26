import os
import time
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed — read .env manually
    _env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(_env_path):
        for _line in open(_env_path):
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

import streamlit as st
# st.html replaces st.components.v1.html (deprecated after 2026-06-01)
from auth import render_login, render_landing
from styles.theme import render_theme_css, SEGMENT_COLORS
from utils.data_engine import DataEngine, RE_MODEL_PLATFORM, RE_MODEL_LABELS, month_label_to_fy_quarter
from utils.visuals import render_chart_with_table, month_trend_chart, segment_trend_chart, render_sig_legend, segment_comparison_bar, PLOTLY_CONFIG, filter_sig_markers, render_collapsible_reasons_table, render_collapsible_brand_table, open_end_tree_to_excel
from utils.stat_engine import compare_to_baseline_by_column, calculate_significance, gaps_by_column
from utils.compare import render_comparison_page
from utils.settings_page import render_settings_page
from utils.overview_intro import render_overview_intro
from utils.branding import re_logo_img_html, sidebar_brand_html
from utils.model_images import model_image_path

st.set_page_config(page_title="RE Intelligence Portal | Infoleap", layout="wide", initial_sidebar_state="expanded")

if not render_login():
    st.stop()
if not render_landing():
    st.stop()


def _masterfile_mtime():
    import os
    from pathlib import Path
    try:
        if not Path("data/RE_MIS_Master.xlsx").exists():
            from utils.data_engine import _sync_from_drive
            _sync_from_drive()
        return os.path.getmtime("data/RE_MIS_Master.xlsx")
    except Exception:
        return 0

@st.cache_resource(hash_funcs={float: lambda x: x})
def load_engine_v2(_mtime: float = 0.0):
    engine = DataEngine()
    engine.load_data()
    return engine


@st.cache_data(show_spinner=False, ttl=60)
def _master_config_mtime():
    """Returns mtime of RE_MIS_Master.xlsx — used to bust cache when the
    master config is edited. TTL=60s so changes propagate within 1 minute
    without needing a manual Streamlit restart."""
    from utils.data_engine import MASTER_CONFIG_PATH
    import os
    try:
        return os.path.getmtime(str(MASTER_CONFIG_PATH))
    except OSError:
        return 0


_current_mtime = _masterfile_mtime()
engine = load_engine_v2(_mtime=_current_mtime)

# Show Drive sync warning if last load_data() failed to reach Drive
if st.session_state.get("_drive_sync_warning"):
    st.warning(st.session_state.pop("_drive_sync_warning"))

# Bust @st.cache_data when Excel file changed (engine reloaded).
# The @st.cache_data wrappers below capture engine from closure — they
# don't take engine as a parameter, so Streamlit can't detect engine change.
# Tracking mtime in session_state lets us clear stale cached table results.
_prev_mtime = st.session_state.get("_engine_mtime", None)
if _prev_mtime != _current_mtime:
    st.cache_data.clear()
    st.session_state["_engine_mtime"] = _current_mtime

_master_config_mtime()  # warm cache; result unused but ensures mtime is tracked

# Cached wrappers for the most expensive per-rerun operations.
# @st.cache_data persists across reruns — same filter = cache hit, not a full
# recompute. Calling engine methods directly (uncached) costs ~15-30ms each;
# the hash check on a cached hit costs ~2-5ms. On Overview, section() loops
# over 3 segments × 5 demographic sections = 15 table calls; Block D does
# 14 models × 3 segments = 42 filter_df calls. Without cache: ~600-900ms per
# rerun. With cache after first run for a given filter: ~50-100ms.
@st.cache_data(show_spinner=False, max_entries=600, ttl=3600)
def _tbl_filter(segment, platform, model_code, months_tuple):
    _df = engine.filter_df(segment=segment, platform=platform, model_code=model_code)
    return _df[_df['month_label'].isin(set(months_tuple))].copy()

@st.cache_data(show_spinner=False, max_entries=600, ttl=3600)
def _tbl_age(df, base_label="All", numeric=False, extra_groups=None):
    return engine.age_table(df, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

@st.cache_data(show_spinner=False, max_entries=600, ttl=3600)
def _tbl_education(df, base_label="All", numeric=False, extra_groups=None):
    return engine.education_table(df, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

@st.cache_data(show_spinner=False, max_entries=600, ttl=3600)
def _tbl_occupation(df, base_label="All", numeric=False, extra_groups=None):
    return engine.occupation_table(df, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

@st.cache_data(show_spinner=False, max_entries=600, ttl=3600)
def _tbl_income(df, base_label="All", numeric=False, extra_groups=None):
    return engine.household_income_table(df, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

@st.cache_data(show_spinner=False, max_entries=600, ttl=3600)
def _tbl_type_of_buyer(df, base_label="All", numeric=False, extra_groups=None):
    return engine.type_of_buyer_table(df, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

@st.cache_data(show_spinner=False, max_entries=200, ttl=3600)
def _tbl_brand_owned(df, by="brand", base_label="All", numeric=False, extra_groups=None):
    return engine.brand_owned_table(df, by=by, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

# ----------------------------------------------------------------------
# Sidebar — segment + filters (identical filter set on every segment page)
# ----------------------------------------------------------------------
SEGMENT_LABELS = {"Overview": "All", "Overall": "All", "Acceptors": "Acceptor", "Rejectors": "Rejector", "Booked but Cancelled": "Cancelled"}
SEGMENT_ICONS = {"Overview": "🏠", "Overall": "👥", "Acceptors": "✅", "Rejectors": "❌", "Booked but Cancelled": "🚫"}

# Real Infoleap + Royal Enfield logo images (utils/branding.py) —
# replaces the earlier CSS-mock (3 colored squares) now that both real
# logos exist as assets, sourced from the client's own PPT (2026-07-27).
# Per user report (2026-07-28): a scaled-down copy of the login page's
# centered lockup wasn't visible in the sidebar (see sidebar_brand_html()
# docstring for why) -- uses a dedicated compact, left-aligned version
# sized for the sidebar from the start instead.
st.sidebar.markdown(sidebar_brand_html(), unsafe_allow_html=True)

st.sidebar.markdown("### Segment")
EXTRA_PAGES = ["📊 Model Comparison", "🔲 Platform Comparison", "⚙️ Settings"]
nav_options = [f"{SEGMENT_ICONS[k]} {k}" for k in SEGMENT_LABELS] + EXTRA_PAGES
nav_choice = st.sidebar.radio("Page", nav_options, label_visibility="collapsed")
segment_nav = nav_choice.split(" ", 1)[1] if nav_choice not in EXTRA_PAGES else nav_choice

if nav_choice in EXTRA_PAGES:
    render_theme_css()
    if "Model Comparison" in nav_choice:
        render_comparison_page(engine)
    elif "Platform Comparison" in nav_choice:
        from utils.platform_compare import render_platform_compare_page
        render_platform_compare_page(engine)
        st.stop()
    elif "Settings" in nav_choice:
        render_settings_page()
    if st.sidebar.button("Log out", type="secondary", key="logout_extra"):
        st.session_state["authenticated"] = False
        st.session_state["entered_dashboard"] = False
        st.rerun()
    st.stop()

segment_value = SEGMENT_LABELS[segment_nav]
accent = SEGMENT_COLORS.get(segment_value, SEGMENT_COLORS["All"])
# True only on Overview (comparison hub). Overall + segment pages = deep-dive stacked bars.
_overview_is_comparison = (segment_nav == "Overview")
render_theme_css(accent=accent)

_latest_month = engine.month_order[-1] if engine.month_order else "—"
_load_ts = engine.load_timestamp if hasattr(engine, 'load_timestamp') else None
_freshness = f"Data as of <b>{_latest_month}</b>"
if _load_ts:
    _freshness += f" &nbsp;|&nbsp; Loaded {_load_ts}"

_stripe_color = accent if not _overview_is_comparison else "#C8102E"
_seg_badge = (
    f"<span style='display:inline-block;margin-left:14px;padding:3px 12px;"
    f"border-radius:20px;font-size:0.72rem;font-weight:700;letter-spacing:0.06em;"
    f"text-transform:uppercase;background:{accent}18;color:{accent};"
    f"border:1px solid {accent}40;vertical-align:middle;'>{segment_nav}</span>"
    if segment_nav not in ("Overview",) else ""
)
_re_logo_html = re_logo_img_html(34, extra_style="margin-right:10px;")
st.markdown(
    f"<div style='height:3px;border-radius:0 2px 2px 0;margin-bottom:0.75rem;"
    f"background:linear-gradient(90deg,{_stripe_color} 0%,{_stripe_color} 55%,rgba(200,16,46,0.10) 100%);'></div>"
    f"<h1 style='margin-top:0;'>{_re_logo_html}Royal Enfield{_seg_badge}</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:0.3rem;'>"
    f"<span style='color:#7A7670;font-size:0.85rem;'>Intelligence Portal &mdash; built by Infoleap for Royal Enfield</span>"
    f"<span style='color:#9A958D;font-size:0.78rem;'>{_freshness}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

st.sidebar.markdown("### Report Filters")
_reset_col, _reload_col = st.sidebar.columns(2)
if _reset_col.button("↺ Reset Filters", key="reset_filters", help="Clear all filters to defaults", use_container_width=True):
    for _k in ["platform_filter", "model_filter", "time_mode", "month_range", "quarters",
               "custom_years", "custom_months", "custom_col_label"]:
        st.session_state.pop(_k, None)
    for _k in list(st.session_state.keys()):
        if _k.startswith("_tbl_"):
            del st.session_state[_k]
    st.rerun()
_reload_cooldown = 30  # seconds
_reload_last = st.session_state.get("_reload_last_ts", 0)
_reload_elapsed = time.time() - _reload_last
_reload_ready = _reload_elapsed >= _reload_cooldown
if _reload_col.button("⟳ Reload Data", key="reload_data", disabled=not _reload_ready,
                      help="Re-download & reload master file (fetches latest from Drive if configured)",
                      use_container_width=True):
    st.session_state["_reload_last_ts"] = time.time()
    # Force fresh download BEFORE clearing pickle cache — otherwise
    # load_data() reads old xlsx mtime → pickle cache hit → stale engine.
    from utils.data_engine import _sync_from_drive
    _sync_from_drive()
    load_engine_v2.clear()
    st.cache_data.clear()
    st.session_state.pop("_engine_mtime", None)
    # Also clear section-level table cache stored in session_state
    for _k in [k for k in st.session_state if k.startswith("_tbl_")]:
        del st.session_state[_k]
    st.rerun()

# Live site names these "J Platform (350CC)" / "K Platform (450CC)" /
# "P Platform (650CC)" (confirmed via the scraped tab keys) — display labels
# match that, while the underlying filter value stays the plain "350CC" etc.
# Use engine instance attrs (survive module reload) with module global fallback
from utils.data_engine import RE_PLATFORM_LABELS
_ml = getattr(engine, 'model_labels', None) or RE_MODEL_LABELS
_mp = getattr(engine, 'model_platform', None) or RE_MODEL_PLATFORM
_pl = getattr(engine, 'platform_labels', None) or RE_PLATFORM_LABELS
_all_platforms = sorted({p for p in _mp.values() if p and str(p) != "nan"})
PLATFORM_DISPLAY = {"All": "All", **{p: _pl.get(p, p) for p in _all_platforms}}
platform = st.sidebar.selectbox("Platform (CC)", ["All"] + _all_platforms,
                                  format_func=lambda p: PLATFORM_DISPLAY.get(p, p),
                                  key="platform_filter")
model_options = ["All"]
if platform != "All":
    model_options += sorted(_ml[code] for code, plat in _mp.items() if plat == platform and code in _ml)
model = st.sidebar.selectbox("Model", model_options, key="model_filter")

st.sidebar.markdown("### Time Period")
time_mode = st.sidebar.radio("View by", ["All Months", "Month Range", "Quarter (Financial Calendar)"], label_visibility="collapsed", key="time_mode")

MONTH_ORDER = engine.month_order
FY_QUARTER_ORDER = engine.fy_quarter_order
month_short = [m.split("'")[0][:3] + "'" + m.split("'")[1][2:] for m in MONTH_ORDER]
selected_months = MONTH_ORDER
if time_mode == "Month Range":
    _default_lo = month_short[-12] if len(month_short) >= 12 else month_short[0]
    lo, hi = st.sidebar.select_slider("Month range", options=month_short, value=(_default_lo, month_short[-1]), key="month_range")
    lo_i, hi_i = month_short.index(lo), month_short.index(hi)
    selected_months = MONTH_ORDER[lo_i:hi_i + 1]
elif time_mode == "Quarter (Financial Calendar)":
    quarters = st.sidebar.multiselect("Quarter  —  AMJ=Apr-Jun · JAS=Jul-Sep · OND=Oct-Dec · JFM=Jan-Mar", FY_QUARTER_ORDER, default=FY_QUARTER_ORDER, key="quarters")
    selected_months = [m for m in MONTH_ORDER if month_label_to_fy_quarter(m) in quarters]

# Quarter combined columns: active when Quarter time period is selected.
# Shows one pooled column per selected quarter (e.g. "JAS'25") instead of
# individual monthly columns — requested 2026-08-06.
show_quarter_cols = (time_mode == "Quarter (Financial Calendar)")

# Custom Year+Month combined comparison column — per later, separate user
# request: alongside (not replacing) the "View by" control above, pick any
# mix of years and months and get ONE extra column at the end of every
# table/chart showing that combination's combined base, named by the user,
# highlighted distinctly for comparison against the regular per-month
# columns. Computed fresh per script run from the widget state, never
# stored on the cached `engine` singleton (see quarter_combined_groups()
# docstring for why that would leak across concurrent sessions).
custom_col_name = None
custom_group = {}
with st.sidebar.expander("Custom Combined Column", expanded=False):
    st.caption("Pick specific years + months to merge into one extra column — useful for YoY or seasonal comparisons.")
    _available_years = sorted({m.split("'")[1] for m in MONTH_ORDER})
    _available_month_names = list(dict.fromkeys(m.split("'")[0] for m in MONTH_ORDER))
    custom_years = st.multiselect("Years", _available_years, default=[], key="custom_years")
    custom_month_names = st.multiselect("Months", _available_month_names, default=[], key="custom_months")
    if custom_years and custom_month_names:
        custom_months = [m for m in MONTH_ORDER if m.split("'")[0] in custom_month_names and m.split("'")[1] in custom_years]
        if custom_months:
            custom_label_input = st.text_input("Column label", value="Custom Combined", key="custom_col_label").strip()
            custom_col_name = custom_label_input or "Custom Combined"
            custom_group = {custom_col_name: custom_months}
            custom_months_short = [m.split("'")[0][:3] + "'" + m.split("'")[1][2:] for m in custom_months]
            st.caption(f"Combines: {', '.join(custom_months_short)}")

# Quarter combined groups for the active quarters (empty when not in quarter mode).
# Keys use the FY quarter label (e.g. "Q2 FY25-26") so the column header matches
# what the user selected in the sidebar filter.
_active_q_groups = {}
if show_quarter_cols:
    _q_month_map = {}
    for m in MONTH_ORDER:
        _q_month_map.setdefault(month_label_to_fy_quarter(m), []).append(m)
    _active_q_groups = {q: _q_month_map[q] for q in quarters if q in _q_month_map}
# Merged extra groups passed to every table builder: quarter cols + custom col.
effective_extra_groups = {**_active_q_groups, **(custom_group or {})}

show_sig = st.sidebar.toggle("Significance vs Rest of Sample (95%/90%)", value=True,
                              help="Marks each category as significantly higher than the OTHER segments combined (e.g. Acceptor vs Rejector+Cancelled) — a true 'this group vs the rest' test, not diluted by including the group in its own baseline.")
# Per user request: no user-facing 95%/90% or Both/High/Low controls.
# "Both" reverted back to "High only" (2026-07-30): per explicit user
# request, app should only surface significantly-HIGHER markers (▲/△),
# suppressing ▼/▽ drops, even though the live site itself colors both
# directions (confirmed via DOM scrape: dark green = drop Z<=-1.95, light
# green = rise Z>=1.28 uncapped — see stat_engine.py docstring). This is a
# deliberate app-vs-site divergence, not a formula mismatch.
sig_confidence = 0.95
sig_direction = "High only"
with st.sidebar.popover("ℹ️ What do the colors mean?", use_container_width=True):
    render_sig_legend(active_confidence=sig_confidence)
if show_sig and segment_value == "All" and platform == "All" and model == "All":
    st.sidebar.caption(
        "On Overview with no Platform/Model filter, there's no 'rest of sample' to compare against "
        "(it IS the whole sample) — pick a Model above to compare that slice against everyone, "
        "or switch to Acceptors/Rejectors/Booked but Cancelled to see segment-vs-rest markers."
    )

model_code = None
if model != "All":
    model_code = next(c for c, n in _ml.items() if n == model)

_months_t = tuple(sorted(selected_months))
df = _tbl_filter(segment_value, platform, model_code, _months_t)

if segment_value == "All":
    baseline_df = _tbl_filter("All", None, None, _months_t)
else:
    other_segments = [s for s in ("Acceptor", "Rejector", "Cancelled") if s != segment_value]
    _everyone = _tbl_filter("All", platform, model_code, _months_t)
    baseline_df = _everyone[_everyone['segment'].isin(other_segments)]
base_n = len(df)

_seg_label_map = {"All": "Overview", "Acceptor": "Acceptors", "Rejector": "Rejectors", "Cancelled": "Cancelled"}
_seg_dfs = {}
for _seg in ("All", "Acceptor", "Rejector", "Cancelled"):
    _sdf = _tbl_filter(_seg, platform, model_code, _months_t)
    if len(_sdf) >= 30:
        _seg_dfs[_seg_label_map[_seg]] = _sdf

st.sidebar.markdown("---")
if st.sidebar.button("Log out", type="secondary", key="logout_main"):
    st.session_state["authenticated"] = False
    st.session_state["entered_dashboard"] = False
    st.rerun()

# ----------------------------------------------------------------------
# Main content — compact KPI chips (replaces oversized st.metric cards)
# ----------------------------------------------------------------------

def _sig_best_row(table_full, target_col, confidence=0.95):
    """Return (best_row, is_sig_high, z_score).
    Prefer the row whose current-month % is significantly higher than its own
    All-column average (pooled Z-test, same formula as stat_engine).
    If none qualify, return the max-value row with is_sig_high=False."""
    from utils.stat_engine import calculate_significance
    _rest = table_full.iloc[1:]
    if _rest.empty:
        return table_full.iloc[0], False, 0.0
    col = target_col if target_col in table_full.columns else 'All'
    base_row = table_full.iloc[0]
    try:
        n_col = float(base_row.get(col, 0) or 0)
        n_all = float(base_row.get('All', 0) or 0)
    except (TypeError, ValueError):
        n_col, n_all = 0, 0

    sig_candidates = []
    if col != 'All' and n_col >= 30 and n_all >= 30:
        for _, row in _rest.iterrows():
            try:
                p_col = float(row[col]) / 100
                p_all = float(row['All']) / 100
                if p_col > p_all:
                    res = calculate_significance(p_col, n_col, p_all, n_all, confidence)
                    if res["is_significant"] and res["z_score"] > 0:
                        sig_candidates.append((row, res["z_score"]))
            except (KeyError, ValueError, TypeError):
                pass

    if sig_candidates:
        best = max(sig_candidates, key=lambda x: x[1])
        return best[0], True, best[1]

    try:
        best_row = _rest.loc[_rest[col].astype(float).idxmax()]
        return best_row, False, 0.0
    except Exception:
        return _rest.iloc[0], False, 0.0


if base_n == 0:
    st.warning(
        f"No respondents match this combination: Segment={segment_nav}, Platform={platform}, "
        f"Model={model}, Time={time_mode}. Try widening one of the filters in the sidebar "
        "— most commonly the Model filter holds a selection from a different segment that doesn't exist here."
    )
    st.stop()

total_n = len(engine.df)

# Determine the last month in current selection
_last_selected_month = selected_months[-1] if selected_months else engine.month_order[-1]

# Calculate metrics for last selected month
# Filter to current month; fall back to most recent month with data if empty
_df_cur = df[df['month_label'] == _last_selected_month]
_display_month = _last_selected_month
if len(_df_cur) == 0:
    for _fb_m in reversed(engine.month_order):
        _df_cur = df[df['month_label'] == _fb_m]
        if len(_df_cur) > 0:
            _display_month = _fb_m
            break
    if len(_df_cur) == 0:
        _df_cur = df
        _display_month = _last_selected_month
_base_cur = base_n if time_mode == "All Months" else (len(_df_cur) if len(_df_cur) > 0 else base_n)

# Card 1: Average Age — use raw numeric age (dq7 → age_numeric) when available,
# fall back to age_grp midpoints so the KPI never breaks on older data cuts.
_AGE_MIDPOINTS = {1.0: 21.5, 2.0: 30.5, 3.0: 40.5, 4.0: 50.0}
_AGE_BRACKET_LABELS = {1.0: "18–25 Yrs", 2.0: "26–35 Yrs", 3.0: "36–45 Yrs", 4.0: "46+ Yrs"}
_AGE_RAW_COL  = engine.F.get('age_raw',  'age_numeric')
_AGE_BAND_COL = engine.F.get('age_band', 'age_grp')
_HAS_AGE_NUMERIC = _AGE_RAW_COL in df.columns
def _mean_age(d):
    if _HAS_AGE_NUMERIC:
        import pandas as _pd
        return _pd.to_numeric(d[_AGE_RAW_COL], errors='coerce').mean()
    return d[_AGE_BAND_COL].map(_AGE_MIDPOINTS).mean()
_age_src_df = df if time_mode == "All Months" else (_df_cur if len(_df_cur) > 0 else df)
avg_age = _mean_age(_age_src_df)
avg_age = float(avg_age) if not (avg_age != avg_age) else 0.0  # NaN guard
# Dominant age bracket for KPI card display
_dom_age_code = _age_src_df[_AGE_BAND_COL].value_counts().idxmax() if len(_age_src_df) > 0 else 2.0
_dom_age_label = _AGE_BRACKET_LABELS.get(float(_dom_age_code), "26–35 Yrs")
# age base = respondents with valid age answer (may be 1 less than total if one null)
import pandas as _pd_age
if _HAS_AGE_NUMERIC:
    _age_base_n = int(_pd_age.to_numeric(_age_src_df[_AGE_RAW_COL], errors='coerce').notna().sum())
else:
    _age_base_n = int(_age_src_df[_AGE_BAND_COL].notna().sum())

# When All Months selected, KPI values use the full period ('All' column),
# not just the latest month — so the headline number matches the aggregate view.
_kpi_col = 'All' if time_mode == "All Months" else _display_month

# Card 2: Household Income
income_table_full = engine.household_income_table(df, base_label=segment_value, numeric=True)
top_income_row, income_is_sig, _inc_z = _sig_best_row(income_table_full, _kpi_col)
top_income_val = float(top_income_row[_kpi_col if _kpi_col in income_table_full.columns else 'All'])

# Card 3: First-Time Buyer count and % — full filtered df (already month-scoped by df)
_ftb_df = df if time_mode == "All Months" else _df_cur
_dq1a = engine.F.get('buyer_type', 'dq1a')
_ftb_mask = _ftb_df[_dq1a].isin([3.0, 4.0])
ftb_count = int(_ftb_mask.sum())
_ftb_base = int(_ftb_df[_dq1a].notna().sum())
ftb_pct = ftb_count / _ftb_base * 100 if _ftb_base else 0.0

# Card 4: Education
edu_table_full = engine.education_table(df, base_label=segment_value, numeric=True)
top_edu_row, edu_is_sig, _edu_z = _sig_best_row(edu_table_full, _kpi_col)
top_edu_val = float(top_edu_row[_kpi_col if _kpi_col in edu_table_full.columns else 'All'])

# Keep age_table_full for section rendering below
age_table_full = engine.age_table(df, base_label=segment_value, numeric=True)

# Per-month % of respondents in dominant age bracket (for sparkline)
_avg_age_monthly = []
for _m in engine.month_order:
    _mdf = df[df['month_label'] == _m]
    if len(_mdf) > 0:
        _band_counts = _mdf[_AGE_BAND_COL].value_counts()
        _total = _band_counts.sum()
        if _total > 0:
            _dom_pct = round(100 * _band_counts.get(float(_dom_age_code), 0) / _total, 1)
            _avg_age_monthly.append((_m, _dom_pct))
# Limit sparkline to last 12 months (or selected period window)
_avg_age_monthly = _avg_age_monthly[-12:]

# Current-period dominant bracket % for KPI card display
_dom_age_pct = None
_age_band_src = _age_src_df[_AGE_BAND_COL].value_counts()
_age_band_total = _age_band_src.sum()
if _age_band_total > 0:
    _dom_age_pct = round(100 * _age_band_src.get(float(_dom_age_code), 0) / _age_band_total, 1)

# Per-month series for FTB % sparkline
_ftb_monthly = []
for _m in engine.month_order:
    _mdf = df[df['month_label'] == _m]
    _mn = len(_mdf)
    if _mn > 0:
        _mftb = _mdf[engine.F.get('buyer_type', 'dq1a')].isin([3.0, 4.0]).sum() / _mn * 100
        _ftb_monthly.append((_m, float(_mftb)))

seg_pct = base_n / total_n * 100

_chip_deltas = {}
_overall_df_chip = _seg_dfs.get("Overview")
if _overall_df_chip is not None and segment_value not in ("All",):
    try:
        _ov_age_avg = _overall_df_chip['age_grp'].map(_AGE_MIDPOINTS).mean()
        if _ov_age_avg == _ov_age_avg:  # not NaN
            _chip_deltas['age'] = avg_age - float(_ov_age_avg)
    except Exception:
        pass
    try:
        _ov_inc = engine.household_income_table(_overall_df_chip, base_label="All", numeric=True)
        _ov_inc_row = _ov_inc[_ov_inc['Unnamed: 0'] == top_income_row['Unnamed: 0']]
        if len(_ov_inc_row):
            _chip_deltas['income'] = top_income_val - float(_ov_inc_row.iloc[0]['All'])
    except Exception:
        pass
    try:
        _ov_ftb_count = _overall_df_chip['dq1a'].isin([3.0, 4.0]).sum()
        _ov_base = len(_overall_df_chip)
        if _ov_base:
            _chip_deltas['ftb'] = ftb_pct - (_ov_ftb_count / _ov_base * 100)
    except Exception:
        pass
    try:
        _ov_edu = engine.education_table(_overall_df_chip, base_label="All", numeric=True)
        _ov_edu_row = _ov_edu[_ov_edu['Unnamed: 0'] == top_edu_row['Unnamed: 0']]
        if len(_ov_edu_row):
            _chip_deltas['edu'] = top_edu_val - float(_ov_edu_row.iloc[0]['All'])
    except Exception:
        pass


def _delta_badge(delta):
    if delta is None:
        return ""
    sign = "+" if delta >= 0 else ""
    col = "#1B8A3F" if delta >= 2 else ("#C8102E" if delta <= -2 else "#7A7670")
    return (f"<span style='font-size:0.7rem;font-weight:700;color:{col};"
            f"background:{col}18;border-radius:4px;padding:1px 5px;margin-left:4px;'>"
            f"{sign}{delta:.0f}pp</span>")


def _mini_bar(pct, color):
    return (f"<div style='margin-top:7px;background:#F0EDE8;border-radius:3px;height:5px;width:100%;'>"
            f"<div style='background:{color};height:5px;border-radius:3px;"
            f"width:{min(pct, 100):.0f}%;'></div></div>")


_SEGMENT_FRAME = {
    "Overview": "Full sample — compare all three segments side-by-side. Go deeper by clicking a segment below.",
    "Overall": "All respondents (full sample) deep-dive. Unfiltered view of the complete survey population.",
    "Acceptors": "Confirmed RE buyers — respondents who completed a purchase. Deep-dive into who they are.",
    "Rejectors": "Lost prospects — considered RE but bought a competitor. Compare with Acceptors to spot the gaps.",
    "Booked but Cancelled": "Warm leads who booked but cancelled before delivery — distinct from Rejectors.",
}
_frame_text = _SEGMENT_FRAME.get(segment_nav, "")

if _overview_is_comparison:
    render_overview_intro(engine=engine)
    st.stop()

else:
    _model_img_card_html = ""
    if model != "All":
        import base64 as _b64m
        _mip2 = model_image_path(model)
        if _mip2:
            with open(_mip2, "rb") as _mf2:
                _mib642 = _b64m.b64encode(_mf2.read()).decode("ascii")
            _mime2 = {"jpg":"jpeg","jpeg":"jpeg","png":"png","webp":"webp"}.get(_mip2.rsplit(".",1)[-1].lower(),"png")
            _model_name_short = model.replace("Royal Enfield ", "")
            _model_img_card_html = (
                f"<div style='flex:1;background:transparent;border:1px solid #ECE9E4;border-radius:12px;"
                f"padding:14px 18px 8px;display:flex;flex-direction:column;align-items:center;"
                f"justify-content:center;min-height:180px;'>"
                f"<div style='font-size:1.1rem;font-weight:800;text-transform:uppercase;letter-spacing:0.12em;"
                f"color:#1A1A1A;margin-bottom:10px;'>{_model_name_short}</div>"
                f"<img src='data:image/{_mime2};base64,{_mib642}' "
                f"style='max-width:100%;max-height:260px;object-fit:contain;object-position:center;"
                f"mix-blend-mode:multiply;'/>"
                f"</div>"
            )

    _active_seg_card = (
        f"<div style='flex:1;min-width:200px;background:{accent}0D;border:1.5px solid {accent}40;"
        f"border-left:5px solid {accent};border-radius:12px;padding:18px 22px;'>"
        f"<div style='font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:{accent};font-weight:700;margin-bottom:6px;'>Active Segment</div>"
        f"<div style='font-size:2.6rem;font-weight:800;color:{accent};font-family:Oswald,sans-serif;line-height:1;'>{segment_nav.upper()}</div>"
        f"<div style='font-size:1rem;font-weight:700;color:#1A1A1A;margin-top:8px;'>"
        f"{base_n:,} respondents &nbsp;·&nbsp; <span style='color:#7A7670;font-weight:500;'>{seg_pct:.0f}% of {total_n:,} total</span>"
        f"</div>"
        f"<div style='font-size:0.85rem;color:#4A4644;margin-top:8px;line-height:1.6;'>{_frame_text}</div>"
        f"</div>"
    )

    def _sparkline_svg(month_vals, current_month, color, unit="%"):
        """Inline SVG sparkline with CSS-hover tooltips on every data point."""
        if not month_vals or len(month_vals) < 2:
            return ""
        vals = [v for m, v in month_vals]
        mn, mx = min(vals), max(vals)
        rng = mx - mn if mx != mn else 1
        avg = sum(vals) / len(vals)
        W, H = 460, 280
        PAD_L, PAD_R, PAD_T, PAD_B = 16, 16, 60, 60
        chart_w = W - PAD_L - PAD_R
        chart_h = H - PAD_T - PAD_B
        def xp(i): return PAD_L + i * chart_w / max(len(vals) - 1, 1)
        def yp(v): return PAD_T + (mx - v) / rng * chart_h
        _fmt = lambda v: f"{v:.1f}{unit}" if unit != "%" else f"{v:.0f}%"

        pts = " ".join(f"{xp(i):.1f},{yp(v):.1f}" for i, v in enumerate(vals))
        avg_y = yp(avg)
        max_i = vals.index(mx)
        min_i = vals.index(mn)

        avg_line = (
            f"<line x1='{PAD_L}' y1='{avg_y:.1f}' x2='{W - PAD_R}' y2='{avg_y:.1f}' "
            f"stroke='#94A3B8' stroke-width='2' stroke-dasharray='7,4' opacity='0.7'/>"
            f"<text x='{PAD_L + 6}' y='{avg_y + 20:.1f}' text-anchor='start' "
            f"font-size='20' fill='#94A3B8' font-weight='700'>avg {_fmt(avg)}</text>"
        )

        def _safe_label_y(cy, prefer_above, margin=18):
            candidate = cy - margin if prefer_above else cy + margin
            if abs(candidate - avg_y) < 12:
                candidate = cy + margin if prefer_above else cy - margin
            return candidate

        # CSS inside SVG for hover tooltips and grow effect
        TT_W, TT_H = 310, 125
        _style = (
            "<style>"
            ".spk-pt { cursor: crosshair; }"
            ".spk-pt .spk-tt { visibility: hidden; opacity: 0; transition: opacity 0.15s; }"
            ".spk-pt:hover .spk-tt { visibility: visible; opacity: 1; }"
            ".spk-pt .spk-dot { transition: r 0.12s; }"
            ".spk-pt:hover .spk-dot { r: 18; }"
            "</style>"
        )

        # Monthly sample bases for tooltip highlight
        _m_bases_lookup = {}
        try:
            _m_bases_lookup = df['month_label'].value_counts().to_dict()
        except Exception:
            pass

        # Two-pass render: dots layer first, tooltips layer on top (SVG z-order)
        dot_layer = ""
        tooltip_layer = ""
        for i, (m, v) in enumerate(month_vals):
            cx, cy = xp(i), yp(v)
            is_current = (m == current_month)
            is_max = (i == max_i) and not is_current
            is_min = (i == min_i) and not is_current

            if is_current:
                dot_r, dot_fill, dot_stroke = 13, color, "#fff"
                ly = _safe_label_y(cy, prefer_above=True)
                static_label = (f"<text x='{cx:.1f}' y='{ly:.1f}' text-anchor='middle' "
                                f"font-size='24' font-weight='900' fill='{color}'>{_fmt(v)}</text>")
            elif is_max:
                dot_r, dot_fill, dot_stroke = 10, "#1B8A3F", "#fff"
                ly = _safe_label_y(cy, prefer_above=True)
                static_label = (f"<text x='{cx:.1f}' y='{ly:.1f}' text-anchor='middle' "
                                f"font-size='21' fill='#1B8A3F' font-weight='800'>{_fmt(v)}</text>")
            elif is_min:
                dot_r, dot_fill, dot_stroke = 8, "#9CA3AF", "#fff"
                ly = _safe_label_y(cy, prefer_above=False)
                static_label = (f"<text x='{cx:.1f}' y='{ly:.1f}' text-anchor='middle' "
                                f"font-size='20' fill='#6B7280' font-weight='700'>{_fmt(v)}</text>")
            else:
                dot_r, dot_fill, dot_stroke = 6, color, "#fff"
                static_label = ""

            # Tooltip position: above point, clamped to SVG bounds
            tt_x = max(0, min(cx - TT_W / 2, W - TT_W))
            tt_y = cy - TT_H - 14
            if tt_y < 2:
                tt_y = cy + 14

            delta_val = v - avg
            delta_str = (f"+{delta_val:.1f}" if delta_val >= 0 else f"{delta_val:.1f}") + (
                "pp" if unit == "%" else unit)
            delta_col = "#4ADE80" if delta_val >= 0 else "#F87171"
            m_base_n = _m_bases_lookup.get(m, 0)

            # Dot layer: hit area + visible dot + static label
            dot_layer += (
                f"<g class='spk-pt' data-idx='{i}'>"
                f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='22' fill='transparent'/>"
                f"<circle class='spk-dot' cx='{cx:.1f}' cy='{cy:.1f}' r='{dot_r}' "
                f"fill='{dot_fill}' stroke='{dot_stroke}' stroke-width='2'/>"
                f"{static_label}"
                f"</g>"
            )

            # Tooltip layer: rendered after ALL dots so always on top
            tooltip_layer += (
                f"<g class='spk-tt' data-idx='{i}' style='visibility:hidden;opacity:0;transition:opacity 0.15s;pointer-events:none;'>"
                f"<rect x='{tt_x:.1f}' y='{tt_y:.1f}' width='{TT_W}' height='{TT_H}' "
                f"rx='10' fill='#1E293B' opacity='0.97'/>"
                f"<text x='{tt_x + TT_W/2:.1f}' y='{tt_y + 30:.1f}' text-anchor='middle' "
                f"font-size='30' font-weight='700' fill='#E2E8F0'>{m}</text>"
                f"<text x='{tt_x + TT_W/2:.1f}' y='{tt_y + 68:.1f}' text-anchor='middle' "
                f"font-size='36' font-weight='900' fill='#fff'>{_fmt(v)} "
                f"<tspan fill='{delta_col}' font-size='28' font-weight='700'>({delta_str})</tspan>"
                f"</text>"
                f"<rect x='{tt_x + TT_W/2 - 65:.1f}' y='{tt_y + 82:.1f}' width='130' height='30' rx='15' fill='#C8102E' />"
                f"<text x='{tt_x + TT_W/2:.1f}' y='{tt_y + 103:.1f}' text-anchor='middle' "
                f"font-size='22' font-weight='800' fill='#fff'>Base: {m_base_n:,}</text>"
                f"</g>"
            )

        # JS wires dot hover → matching tooltip (same data-idx), keeps CSS fallback
        _hover_js = (
            "<script>"
            "(function(){"
            "var svg=document.currentScript.closest('svg');"
            "if(!svg)return;"
            "svg.querySelectorAll('.spk-pt').forEach(function(pt){"
            "var idx=pt.getAttribute('data-idx');"
            "var tt=svg.querySelector('.spk-tt[data-idx=\"'+idx+'\"]');"
            "if(!tt)return;"
            "pt.addEventListener('mouseenter',function(){tt.style.visibility='visible';tt.style.opacity='1';});"
            "pt.addEventListener('mouseleave',function(){tt.style.visibility='hidden';tt.style.opacity='0';});"
            "});"
            "})();"
            "</script>"
        )

        return (
            f"<svg viewBox='0 0 {W} {H}' width='100%' height='auto' "
            f"style='overflow:visible;margin-top:8px;display:block;min-height:170px;'>"
            f"{_style}"
            f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='4' opacity='0.75' stroke-linejoin='round'/>"
            f"{avg_line}{dot_layer}{tooltip_layer}{_hover_js}</svg>"
        )

    def _ai_headline(label, value_label, month_vals, current_month, delta, unit="%", n_cur=None, current_override=None):
        """Concise executive KPI insight: signal badge + one-line trend fact + segment differentiator."""
        if not month_vals or len(month_vals) < 2:
            return ""
        vals_dict = dict(month_vals)
        vals = list(vals_dict.values())
        avg = sum(vals) / len(vals)
        peak_m = max(month_vals, key=lambda x: x[1])
        trough_m = min(month_vals, key=lambda x: x[1])
        cur = current_override if current_override is not None else vals_dict.get(current_month)
        if cur is None:
            return ""

        is_pct = unit == "%"
        _momentum_thresh = 2.0 if is_pct else 1.0

        def _fmt_val(v):
            return f"{v:.1f}%" if is_pct else f"{v:.1f}{unit}"

        def _fmt_delta(d):
            sign = "+" if d >= 0 else ""
            return f"{sign}{d:.1f}pp" if is_pct else f"{sign}{d:.1f}{unit}"

        trend_window = vals[-3:] if len(vals) >= 3 else vals
        _3m_move = trend_window[-1] - trend_window[0]
        rising  = _3m_move > _momentum_thresh
        falling = _3m_move < -_momentum_thresh
        b = lambda t: f"<b style='color:#1E293B;'>{t}</b>"

        # ── Signal badge ──────────────────────────────────────────────────
        if rising:
            _sc, _sb, _si, _st = "#1B8A3F", "#E8F5E9", "▲", "Rising (last 3 months)"
        elif falling:
            _sc, _sb, _si, _st = "#C8102E", "#FEECEC", "▼", "Falling (last 3 months)"
        else:
            _sc, _sb, _si, _st = "#64748B", "#F8FAFC", "—", "No clear trend"

        _badge = (
            f"<span style='display:inline-block;font-size:0.6rem;font-weight:800;"
            f"letter-spacing:0.07em;padding:2px 7px;border-radius:4px;"
            f"background:{_sb};color:{_sc};border:1px solid {_sc}30;'>"
            f"{_si} {_st}</span>"
        )

        # ── One-line trend fact ───────────────────────────────────────────
        if rising:
            _fact = (f"{b(_fmt_delta(_3m_move))} over 3 months. "
                     f"High: {b(_fmt_val(peak_m[1]))} in {peak_m[0]}.")
        elif falling:
            _fact = (f"{b(_fmt_delta(_3m_move))} over 3 months. "
                     f"Low: {b(_fmt_val(trough_m[1]))} in {trough_m[0]}.")
        else:
            _fact = (f"Range across study: {b(_fmt_val(trough_m[1]))} – {b(_fmt_val(peak_m[1]))}. "
                     f"No directional momentum.")

        # ── Segment vs overall (only when material) ───────────────────────
        _seg_line = ""
        if delta is not None and abs(delta) >= 2:
            _dir = "above" if delta > 0 else "below"
            _seg_line = (f"<span style='color:#7A7670;'> · {_fmt_delta(delta)} {_dir} overall.</span>")

        return (
            f"<div style='margin-top:8px;border-top:1px solid #F0EDE8;padding-top:6px;"
            f"display:flex;flex-direction:column;gap:4px;'>"
            f"{_badge}"
            f"<div style='font-size:0.72rem;color:#4A5568;line-height:1.6;'>"
            f"{_fact}{_seg_line}</div>"
            f"</div>"
        )

    def _build_month_series(full_table, row_label_val):
        """Extract per-month % series for a given category row."""
        month_cols = [c for c in engine.month_order if c in full_table.columns]
        row = full_table[full_table['Unnamed: 0'] == row_label_val]
        if row.empty:
            return []
        r = row.iloc[0]
        result = []
        for m in month_cols:
            try:
                result.append((m, float(str(r[m]).rstrip('%'))))
            except (KeyError, ValueError, TypeError):
                pass
        return result

    def _stat_card(label, value_label, pct, delta_key, n_approx, full_table=None, row_label_val=None, is_sig_high=False, unit="%", month_vals_override=None, pill_label="TOP VALUE", current_override=None):
        if month_vals_override is not None:
            month_vals = month_vals_override
        else:
            month_vals = _build_month_series(full_table, row_label_val) if full_table is not None and row_label_val is not None else []
        delta = _chip_deltas.get(delta_key)
        spark = _sparkline_svg(month_vals, _display_month, accent, unit=unit)
        headline = _ai_headline(label, value_label, month_vals, _display_month, delta, unit=unit, n_cur=n_approx, current_override=current_override)

        # Left-border: red if segment notably below overall, else segment accent
        if delta is not None and delta <= -2:
            border_css = f"border-left:4px solid #C8102E;"
        else:
            border_css = f"border-left:4px solid {accent}40;"

        # Segment-vs-overall delta badge
        sig_note = ""
        if delta is not None and delta >= 2:
            sig_note = (f"<span style='font-size:0.65rem;color:#1B8A3F;font-weight:700;"
                        f"margin-left:4px;'>▲ vs overall</span>")
        elif delta is not None and delta <= -2:
            sig_note = (f"<span style='font-size:0.65rem;color:#C8102E;font-weight:700;"
                        f"margin-left:4px;'>▼ vs overall</span>")

        return (
            f"<div style='flex:1;min-width:185px;background:#fff;border:1px solid #E2E8F0;"
            f"{border_css}border-radius:14px;padding:16px 18px 12px;box-sizing:border-box;"
            f"box-shadow:0 2px 12px rgba(0,0,0,0.06);display:flex;flex-direction:column;gap:0;'>"
            f"<div style='margin-bottom:4px;'>"
            f"<div style='font-size:9.5px;text-transform:uppercase;letter-spacing:0.08em;color:#94A3B8;font-weight:700;'>{label}</div>"
            f"</div>"
            f"<div style='font-size:0.9rem;font-weight:700;color:#1E293B;line-height:1.3;margin-bottom:3px;'>{value_label}</div>"
            f"<div style='display:flex;align-items:baseline;gap:4px;'>"
            f"<span style='font-size:2rem;font-weight:800;color:{accent};line-height:1;"
            f"font-family:Oswald,sans-serif;letter-spacing:-0.01em;'>{pct if isinstance(pct, str) else (f'{pct:.1f}' if unit != '%' else f'{pct:.0f}')}{unit}</span>"
            f"{_delta_badge(delta)}{sig_note}</div>"
            f"{spark}"
            f"{headline}"
            f"<div style='font-size:0.67rem;color:#CBD5E1;margin-top:6px;display:flex;gap:8px;'>"
            f"<span>n&#8776;{n_approx:,}</span><span>&#183;</span><span>{'All Months' if time_mode == 'All Months' else _display_month}</span>"
            f"</div>"
            f"</div>"
        )

    _four_cards_html = (
        f"<div style='display:flex;gap:12px;flex-wrap:wrap;margin-top:10px;align-items:stretch;justify-content:flex-start;'>"
        + _stat_card("Age Bracket", _dom_age_label, _dom_age_pct if _dom_age_pct is not None else 0, 'age', _age_base_n,
                     unit="%", month_vals_override=_avg_age_monthly,
                     current_override=_dom_age_pct if time_mode == "All Months" else None)
        + _stat_card("Household Income", top_income_row['Unnamed: 0'], top_income_val, 'income', round(_base_cur*top_income_val/100),
                     full_table=income_table_full, row_label_val=top_income_row['Unnamed: 0'],
                     current_override=top_income_val if time_mode == "All Months" else None)
        + _stat_card("First-Time Buyer", "1st 2W Purchase", ftb_pct, 'ftb', base_n,
                     month_vals_override=_ftb_monthly,
                     current_override=ftb_pct if time_mode == "All Months" else None)
        + _stat_card("Education", top_edu_row['Unnamed: 0'], top_edu_val, 'edu', round(_base_cur*top_edu_val/100),
                     full_table=edu_table_full, row_label_val=top_edu_row['Unnamed: 0'],
                     current_override=top_edu_val if time_mode == "All Months" else None)
        + f"</div>"
    )

    if _model_img_card_html:
        st.markdown(
            f"<div style='display:flex;gap:14px;align-items:stretch;margin-bottom:0;'>"
            f"<div style='flex:0 0 65%;max-width:65%;display:flex;'>{_model_img_card_html}</div>"
            f"<div style='flex:0 0 35%;max-width:35%;display:flex;'>{_active_seg_card}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(_four_cards_html + "<div style='margin-bottom:0.5rem;'></div>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:0.5rem;align-items:stretch;justify-content:flex-start;'>"
            + _active_seg_card
            + _stat_card("Age Bracket", _dom_age_label, _dom_age_pct if _dom_age_pct is not None else 0, 'age', _base_cur,
                         unit="%", month_vals_override=_avg_age_monthly,
                         current_override=_dom_age_pct if time_mode == "All Months" else None)
            + _stat_card("Household Income", top_income_row['Unnamed: 0'], top_income_val, 'income', round(_base_cur*top_income_val/100),
                         full_table=income_table_full, row_label_val=top_income_row['Unnamed: 0'],
                         current_override=top_income_val if time_mode == "All Months" else None)
            + _stat_card("First-Time Buyers", "Buying first bike", ftb_pct, 'ftb', base_n,
                         month_vals_override=_ftb_monthly,
                         current_override=ftb_pct if time_mode == "All Months" else None)
            + _stat_card("Education", top_edu_row['Unnamed: 0'], top_edu_val, 'edu', round(_base_cur*top_edu_val/100),
                         full_table=edu_table_full, row_label_val=top_edu_row['Unnamed: 0'],
                         current_override=top_edu_val if time_mode == "All Months" else None)
            + f"</div>",
            unsafe_allow_html=True,
        )

regen_key = f"regen_nonce_{segment_nav}"
st.session_state.setdefault(regen_key, 0)

# ----------------------------------------------------------------------
# Pie-Chart Summary — one donut per category, aggregate ("All" column)
# only, no month breakdown (the stacked-bar sections further down give
# the month-level detail). Placed right after the summary cards, before
# the section-jump nav pills, per client request.
#
# Reuses the exact same table-fetching logic as each corresponding
# chart_type="stacked_bar" section further down (see those `section(...)`
# calls for provenance of every lambda below) — same df/baseline_df,
# segment/platform/model/time context. extra_groups is omitted here
# (vs. custom_group passed to the stacked_bar versions): verified against
# distribution_table()'s implementation (utils/data_engine.py) that the
# 'All' column is computed from `df` BEFORE any extra_groups/quarter
# columns are appended — so the 'All' percentages are identical either
# way, extra_groups only changes which extra per-period columns exist,
# which this pie never reads.
#
# Same segment-specific gating as the corresponding stacked_bar sections:
# Brand Considered / Competitor CC / AQ5b / Test Ride / Brand Resilience /
# Post-Cancellation are all inside `if not _overview_is_comparison:`
# further down (never rendered on the Overview comparison hub), so they're
# gated the same way here. On Overview, segment_value == "All" already
# (see SEGMENT_LABELS), so `df` there IS the unfiltered/baseline aggregate
# view a supervisor would expect from an "Overall" page — no separate
# code path needed.

# P4: Section jump nav — anchor pills scroll to major sections
def _nav_pill(label, anchor):
    return (
        f"<a href='#{anchor}' data-sec='{anchor}' style='text-decoration:none;'>"
        f"<span class='jp' style='display:inline-block;padding:5px 14px;border-radius:20px;font-size:0.78rem;"
        f"font-weight:600;background:{accent}12;color:{accent};border:1px solid {accent}35;"
        f"cursor:pointer;white-space:nowrap;transition:all 0.2s;'>{label}</span></a>"
    )
# Build nav pills from sections that actually exist for this segment
_nav_section_map = [
    ("Demographics", "sec-demographics"),
    ("Buyer Type", "sec-buyer-type"),
    ("Additional & Replaced", "sec-addrepl"),
]
if segment_value in ("Rejector", "Cancelled"):
    _nav_section_map.append(("Brand Owned", "sec-brand-owned"))
if segment_value == "Acceptor":
    _nav_section_map.append(("Brand Considered", "sec-brand-considered"))
if segment_value in ("Rejector", "Cancelled"):
    _nav_section_map.append(("Why Considered RE", "sec-reasons-considered"))
_nav_section_map.append(("Reasons", "sec-reasons"))

_nav_pills_html = (
    f"<div id='jump-nav-bar' style='display:flex;gap:8px;flex-wrap:wrap;align-items:center;"
    f"margin:0.6rem 0 0.6rem;position:sticky;top:3.2rem;z-index:90;"
    f"background:rgba(250,250,248,0.96);backdrop-filter:blur(6px);"
    f"padding:6px 0 8px;margin-left:-0.5rem;padding-left:0.5rem;'>"
    + "".join(_nav_pill(lbl, anchor) for lbl, anchor in _nav_section_map)
    + "</div>"
)

st.markdown(_nav_pills_html, unsafe_allow_html=True)

# Active-pill scroll observer (same-origin iframe → parent DOM)
st.html(
    f"""<script>
(function(){{
  var ac='{accent}';
  var secs={str([anchor for _, anchor in _nav_section_map])};
  function activate(id){{
    var pdoc=document;
    pdoc.querySelectorAll('a[data-sec] span.jp').forEach(function(s){{
      var sec=s.parentNode.getAttribute('data-sec');
      if(sec===id){{
        s.style.background=ac+'33';s.style.fontWeight='800';
        s.style.borderColor=ac+'90';s.style.boxShadow='0 1px 6px '+ac+'30';
      }}else{{
        s.style.background=ac+'12';s.style.fontWeight='600';
        s.style.borderColor=ac+'35';s.style.boxShadow='none';
      }}
    }});
  }}
  function init(){{
    var pdoc=document;
    var obs=new IntersectionObserver(function(entries){{
      entries.forEach(function(e){{if(e.isIntersecting)activate(e.target.id);}});
    }},{{threshold:0.1,rootMargin:'-60px 0px -60% 0px'}});
    secs.forEach(function(id){{var el=pdoc.getElementById(id);if(el)obs.observe(el);}});
  }}
  setTimeout(init,1200);
}})();
</script>""",
)

# ── Overview-only insight blocks ────────────────────────────────────────────
if _overview_is_comparison:
    _ov_acc = _seg_dfs.get("Acceptors")
    _ov_rej = _seg_dfs.get("Rejectors")
    _ov_can = _seg_dfs.get("Cancelled")

    # Block B — Key Insight Cards (2×2 grid, visual metric cards)
    # Block A (proportion strips) removed — hero cards above already show N/% per segment.
    _bcard_css = (
        "flex:1;min-width:240px;background:#fff;border:1px solid #ECE9E4;"
        "border-radius:12px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.04);"
    )
    def _kpi_card(accent, icon, label, big, sub, source=""):
        _src = f"<div style='font-size:0.67rem;color:#B0A8A0;margin-top:8px;'>{source}</div>" if source else ""
        return (
            f"<div style='{_bcard_css}border-top:3px solid {accent};'>"
            f"<div style='font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;"
            f"color:{accent};font-weight:700;margin-bottom:8px;'>{icon} &nbsp;{label}</div>"
            f"<div style='font-size:2.0rem;font-weight:900;color:#1A1A1A;line-height:1.1;'>{big}</div>"
            f"<div style='font-size:0.82rem;color:#4A4644;margin-top:6px;line-height:1.5;'>{sub}</div>"
            f"{_src}</div>"
        )

    _b_cards = []

    # Card 1: Dealership CSAT gap (Q5 + Q6a)
    try:
        _acc_csat_n = _ov_acc.loc[_ov_acc['q5'] == 1.0, 'q6a'].dropna() if _ov_acc is not None else []
        _rej_csat_n = _ov_rej.loc[_ov_rej['q5'] == 1.0, 'q6a'].dropna() if _ov_rej is not None else []
        _can_csat_n = _ov_can.loc[_ov_can['q5'] == 1.0, 'q6a'].dropna() if _ov_can is not None else []
        if len(_acc_csat_n) >= 30 and len(_can_csat_n) >= 30:
            _acc_cs = (_acc_csat_n.mean() - 1) / 4 * 100
            _rej_cs = (_rej_csat_n.mean() - 1) / 4 * 100 if len(_rej_csat_n) >= 30 else None
            _can_cs = (_can_csat_n.mean() - 1) / 4 * 100
            _cs_delta = round(_acc_cs - _can_cs, 1)
            _rej_row = f"Rej&nbsp;<strong style='color:#C8102E'>{_rej_cs:.0f}</strong> &nbsp;·&nbsp; " if _rej_cs else ""
            _b_cards.append(_kpi_card(
                "#C8102E", "🏬", "Dealership CSAT (out of 100)",
                f"<span style='color:#39B54A'>{_acc_cs:.0f}</span>&nbsp;<span style='font-size:1.1rem;color:#9A958D'>vs</span>&nbsp;<span style='color:#F7941D'>{_can_cs:.0f}</span>",
                f"Acc&nbsp;<strong style='color:#39B54A'>{_acc_cs:.0f}</strong> &nbsp;·&nbsp; {_rej_row}Can&nbsp;<strong style='color:#F7941D'>{_can_cs:.0f}</strong><br>"
                f"<strong style='color:#C8102E'>{_cs_delta:.0f}-pt drop</strong> from Acceptors to Cancelled — showroom experience drives cancellations.",
                source="Source: Q5 (visited showroom) + Q6a (satisfaction 1–5 scale)"
            ))
    except Exception:
        pass

    # Card 2: Closest miss — top RE model Rejectors considered (AQ5b)
    try:
        if _ov_rej is not None:
            _aq5b_vals = _ov_rej['aq5b'].dropna()
            if len(_aq5b_vals) >= 30:
                _vc = _aq5b_vals.astype(int).value_counts()
                _top_code = int(_vc.index[0])
                _top_n = int(_vc.iloc[0])
                _top_label = RE_MODEL_LABELS.get(_top_code, f"Model {_top_code}").replace("Royal Enfield ", "")
                _rej_total = len(_ov_rej)
                _pct_of_all_rej = _top_n / _rej_total * 100 if _rej_total > 0 else 0
                _b_cards.append(_kpi_card(
                    "#C8102E", "🎯", "Closest Miss — Top Leaking Model",
                    f"{_pct_of_all_rej:.0f}%",
                    f"<strong>{_top_label}</strong> was the RE model most seriously considered by Rejectors "
                    f"({_top_n:,} of {_rej_total:,} Rejectors). Highest-ROI retention target.",
                    source="Source: AQ5b (which RE model did Rejectors most consider?)"
                ))
    except Exception:
        pass

    # Card 3: Brand Resilience — AQ5c (would Rejectors still pick RE if available?)
    try:
        if _ov_rej is not None and 'aq5c' in _ov_rej.columns:
            _aq5c_rej = _ov_rej['aq5c'].dropna()
            if len(_aq5c_rej) >= 30:
                _rej_yes = int((_aq5c_rej == 1).sum())
                _rej_resilience = _rej_yes / len(_aq5c_rej) * 100
                _acc_resilience = None
                if _ov_acc is not None and 'aq5c' in _ov_acc.columns:
                    _aq5c_acc = _ov_acc['aq5c'].dropna()
                    if len(_aq5c_acc) >= 30:
                        _acc_resilience = int((_aq5c_acc == 1).sum()) / len(_aq5c_acc) * 100
                _acc_txt = f"Acc&nbsp;<strong style='color:#39B54A'>{_acc_resilience:.0f}%</strong> &nbsp;·&nbsp; " if _acc_resilience else ""
                _b_cards.append(_kpi_card(
                    "#39B54A", "💚", "Brand Resilience — Rejector Loyalty",
                    f"{_rej_resilience:.0f}%",
                    f"{_acc_txt}Rej&nbsp;<strong style='color:#C8102E'>{_rej_resilience:.0f}%</strong><br>"
                    f"of Rejectors say they'd <strong>still choose RE</strong> if the model they wanted were available — strong brand lock-in signal.",
                    source="Source: AQ5c (would still pick RE if available?)"
                ))
    except Exception:
        pass

    # Card 4: Buyer profile — biggest cross-segment differentiator (Type of Buyer)
    try:
        if _ov_acc is not None and _ov_rej is not None and _ov_can is not None:
            _tob_a = _tbl_type_of_buyer(_ov_acc, base_label="Acceptor", numeric=True)
            _tob_r = _tbl_type_of_buyer(_ov_rej, base_label="Rejector", numeric=True)
            _tob_c = _tbl_type_of_buyer(_ov_can, base_label="Cancelled", numeric=True)
            _tob_gaps = []
            for _, _row in _tob_a.iloc[1:].iterrows():
                _cat = _row['Unnamed: 0']
                _rm = _tob_r[_tob_r['Unnamed: 0'] == _cat]
                _cm = _tob_c[_tob_c['Unnamed: 0'] == _cat]
                if not _rm.empty and not _cm.empty:
                    _av = float(_row['All']); _rv = float(_rm.iloc[0]['All']); _cv = float(_cm.iloc[0]['All'])
                    _tob_gaps.append((max(abs(_av-_rv), abs(_av-_cv), abs(_rv-_cv)), _cat, _av, _rv, _cv))
            if _tob_gaps:
                _tob_gaps.sort(reverse=True)
                _tg, _tcat, _ta_v, _tr_v, _tc_v = _tob_gaps[0]
                _tcat_short = _tcat.replace("Buyer of 2W (No one in family owns a 2W)", "First-time (no prior 2W)")
                _tcat_short = _tcat_short.replace("This is my ", "")
                _b_cards.append(_kpi_card(
                    "#F7941D", "👥", "Buyer Profile — Biggest Segment Gap",
                    f"{_tg:.0f} pp",
                    f"<strong>{_tcat_short.capitalize()[:45]}</strong><br>"
                    f"Acc&nbsp;<strong style='color:#39B54A'>{_ta_v:.0f}%</strong> &nbsp;·&nbsp; "
                    f"Rej&nbsp;<strong style='color:#C8102E'>{_tr_v:.0f}%</strong> &nbsp;·&nbsp; "
                    f"Can&nbsp;<strong style='color:#F7941D'>{_tc_v:.0f}%</strong>",
                    source="Source: Type of Buyer table — largest pp gap across all categories"
                ))
    except Exception:
        pass

    # Card 5: Win-Back Opportunity — Post-Cancellation Trajectory (aq1b)
    try:
        if _ov_can is not None and 'aq1b' in _ov_can.columns:
            _aq1b = _ov_can['aq1b'].dropna()
            if len(_aq1b) >= 30:
                _still_n = (_aq1b == 3.0).sum()
                _still_pct = _still_n / len(_aq1b) * 100
                _bought_pct = (_aq1b == 1.0).sum() / len(_aq1b) * 100
                _b_cards.append(_kpi_card(
                    "#E17055", "🎯", "Win-Back Opportunity — Cancelled",
                    f"{_still_pct:.0f}%",
                    f"<strong>{_still_pct:.0f}%</strong> of cancelled bookers are "
                    f"<strong>still actively searching</strong> for a two-wheeler — "
                    f"immediate RE re-engagement opportunity. "
                    f"Only {_bought_pct:.0f}% switched to another 2W.",
                    source="Source: AQ1B — post-cancellation action (n="
                           f"{len(_aq1b):,})"
                ))
    except Exception:
        pass

    if _b_cards:
        _rows = [_b_cards[i:i+2] for i in range(0, len(_b_cards), 2)]
        _grid_html = ""
        for _row_cards in _rows:
            _grid_html += f"<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px;'>{''.join(_row_cards)}</div>"
        st.markdown(_grid_html, unsafe_allow_html=True)

    # CSAT MoM trend sparkline
    try:
        import plotly.graph_objects as _cgo
        _csat_series = {}
        for _csl, _cdf, _ccolor in [
            ("Acceptors", _ov_acc, "#39B54A"),
            ("Rejectors", _ov_rej, "#C8102E"),
            ("Cancelled", _ov_can, "#F7941D"),
        ]:
            if _cdf is not None and 'q5' in _cdf.columns and 'q6a' in _cdf.columns and 'month_label' in _cdf.columns:
                _grp = _cdf[_cdf['q5'] == 1.0].groupby('month_label')['q6a'].agg(['mean', 'count'])
                _grp['csat'] = (_grp['mean'] - 1) / 4 * 100
                _grp = _grp[_grp['count'] >= 10]
                if len(_grp) >= 2:
                    _csat_series[_csl] = {'color': _ccolor, 'data': _grp}
        if len(_csat_series) >= 2:
            _cfig = _cgo.Figure()
            for _csl, _sd in _csat_series.items():
                _mo = [m for m in engine.month_order if m in _sd['data'].index]
                _cfig.add_trace(_cgo.Scatter(
                    x=_mo, y=[_sd['data'].loc[m, 'csat'] for m in _mo],
                    mode='lines+markers', name=_csl,
                    line=dict(color=_sd['color'], width=2),
                    marker=dict(size=5),
                    hovertemplate='%{y:.0f}<extra>' + _csl + '</extra>',
                ))
            _cfig.update_layout(
                height=200, margin=dict(l=0, r=0, t=8, b=0),
                legend=dict(orientation='h', y=1.15, x=0),
                yaxis=dict(range=[40, 100], ticksuffix=' ', gridcolor='#F0EDE8'),
                xaxis=dict(tickangle=-30),
                plot_bgcolor='#FAFAF8', paper_bgcolor='#FAFAF8',
                font=dict(size=11),
            )
            with st.expander("Dealership CSAT — Month-over-Month Trend", expanded=False):
                st.caption("Monthly CSAT (Q6a, 1–5 → 0–100) for showroom visitors per segment. Months with <10 visitors excluded.")
                st.plotly_chart(_cfig, use_container_width=True, config=PLOTLY_CONFIG)
    except Exception:
        pass

    # Block C — Competitive Intelligence (what brands Rejectors actually bought)
    with st.container(border=True):
        st.markdown("#### Competitive Intelligence — What Rejectors Bought Instead")
        st.caption(f"Brands purchased by the {len(_ov_rej):,} respondents who considered RE but chose a competitor. Source: AQ3 (purchased model), validated against live dashboard.")
        try:
            _bo_rej = _tbl_brand_owned(_ov_rej, by="brand", base_label="Rejector", numeric=True)
            # Manufacturer-level rows only: exclude base row + RE aggregate + individual RE model rows.
            # Competitor manufacturer rows have Unnamed: 0 in engine.manufacturers() minus RE.
            _comp_mfrs = set(engine.manufacturers()) - {"Royal Enfield"}
            _bo_data = _bo_rej[_bo_rej['Unnamed: 0'].isin(_comp_mfrs)].copy()
            _bo_data['_pct'] = _bo_data['All'].astype(float)
            _bo_data = _bo_data.sort_values('_pct', ascending=False).head(8)
            if not _bo_data.empty:
                import plotly.graph_objects as go
                _ci_fig = go.Figure(go.Bar(
                    x=_bo_data['_pct'].tolist(),
                    y=_bo_data['Unnamed: 0'].tolist(),
                    orientation='h',
                    marker_color='#C8102E',
                    text=[f"{v:.0f}%" for v in _bo_data['_pct']],
                    textposition='outside',
                ))
                _ci_fig.update_layout(
                    height=280, margin=dict(l=10, r=60, t=10, b=20),
                    xaxis=dict(showgrid=False, showticklabels=False, range=[0, _bo_data['_pct'].max()*1.25]),
                    yaxis=dict(autorange='reversed', tickfont=dict(size=12)),
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                )
                from utils.visuals import PLOTLY_CONFIG
                st.plotly_chart(_ci_fig, use_container_width=True, config=PLOTLY_CONFIG,
                                key=f"ci_chart_{platform}_{model}_{time_mode}")
            # Model-level drill-down (G3-C): top competitor models, not just manufacturers.
            with st.expander("🔍 Model-Level Breakdown — Top Competitor Models"):
                st.caption("Specific models Rejectors chose. Source: brand_owned_table(by='model'). Top 15 competitor models by % of all Rejectors.")
                try:
                    _bo_rej_model = _tbl_brand_owned(_ov_rej, by="model", base_label="Rejector", numeric=True)
                    _re_models = set(engine.re_model_names()) if hasattr(engine, 're_model_names') else set()
                    _bom_data = _bo_rej_model.iloc[1:].copy()
                    _bom_data['_pct'] = _bom_data['All'].astype(float)
                    # Exclude RE models — we want competitor models only
                    _bom_data = _bom_data[~_bom_data['Unnamed: 0'].str.startswith('Royal Enfield', na=False)]
                    _bom_data = _bom_data[_bom_data['_pct'] >= 0.5].sort_values('_pct', ascending=False).head(15)
                    if not _bom_data.empty:
                        import plotly.graph_objects as _go2
                        _bom_fig = _go2.Figure(_go2.Bar(
                            x=_bom_data['_pct'].tolist(),
                            y=_bom_data['Unnamed: 0'].tolist(),
                            orientation='h',
                            marker_color='#8C1A2E',
                            text=[f"{v:.0f}%" for v in _bom_data['_pct']],
                            textposition='outside', cliponaxis=False,
                        ))
                        _bom_fig.update_layout(
                            height=max(300, 28 * len(_bom_data)),
                            margin=dict(l=10, r=60, t=10, b=10),
                            xaxis=dict(showgrid=False, showticklabels=False,
                                       range=[0, _bom_data['_pct'].max() * 1.3]),
                            yaxis=dict(autorange='reversed', tickfont=dict(size=11)),
                            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                        )
                        st.plotly_chart(_bom_fig, use_container_width=True, config=PLOTLY_CONFIG,
                                        key=f"ci_model_chart_{platform}_{model}_{time_mode}")
                except Exception:
                    st.caption("Model-level data unavailable.")
        except Exception:
            st.caption("Competitive data unavailable for current filter.")

    # Block D — Model Acceptance Rate grouped by RE platform (J/K/P)
    with st.container(border=True):
        st.markdown("#### RE Model Acceptance Rate by Platform")
        st.caption(
            "% of unique respondents per model appearing in each segment. "
            "Bars don't sum to 100% — segments overlap by design. "
            "Platform view (top) → model detail (expander below)."
        )
        try:
            import pandas as _pd
            from utils.data_engine import RE_MODEL_PLATFORM
            _mar_rows = []
            _mar_plat = platform if platform != "All" else None
            _months_t = tuple(sorted(selected_months))
            for _mc, _ml in RE_MODEL_LABELS.items():
                _ma = _tbl_filter("Acceptor", _mar_plat, _mc, _months_t)
                _mr = _tbl_filter("Rejector", _mar_plat, _mc, _months_t)
                _mca = _tbl_filter("Cancelled", _mar_plat, _mc, _months_t)
                _mall = _pd.concat([_ma, _mr, _mca]).drop_duplicates()
                _mt_unique = max(len(_mall), 1)
                if _mt_unique >= 30:
                    _mar_rows.append({
                        "model": _ml.replace("Royal Enfield ", ""),
                        "platform": RE_PLATFORM_LABELS.get(RE_MODEL_PLATFORM.get(_mc, ""), RE_MODEL_PLATFORM.get(_mc, "Other")),
                        "unique_n": _mt_unique,
                        "acc_pct": len(_ma) / _mt_unique * 100,
                        "rej_pct": len(_mr) / _mt_unique * 100,
                        "can_pct": len(_mca) / _mt_unique * 100,
                    })

            if _mar_rows:
                import plotly.graph_objects as _go
                # Platform-level aggregation (weighted by unique_n)
                _plat_agg = {}
                for r in _mar_rows:
                    p = r["platform"]
                    if p not in _plat_agg:
                        _plat_agg[p] = {"n": 0, "acc": 0, "rej": 0, "can": 0}
                    _plat_agg[p]["n"] += r["unique_n"]
                    _plat_agg[p]["acc"] += r["acc_pct"] * r["unique_n"]
                    _plat_agg[p]["rej"] += r["rej_pct"] * r["unique_n"]
                    _plat_agg[p]["can"] += r["can_pct"] * r["unique_n"]
                _plat_order = [v for v in _PLAT_LABELS.values() if v in _plat_agg]
                _p_labels = [f"{p} (n={_plat_agg[p]['n']:,})" for p in _plat_order]
                _p_acc = [_plat_agg[p]["acc"] / _plat_agg[p]["n"] for p in _plat_order]
                _p_rej = [_plat_agg[p]["rej"] / _plat_agg[p]["n"] for p in _plat_order]
                _p_can = [_plat_agg[p]["can"] / _plat_agg[p]["n"] for p in _plat_order]
                _pfig = _go.Figure()
                _pfig.add_trace(_go.Bar(name="Acceptors", y=_p_labels, x=_p_acc, orientation='h',
                    marker_color='#39B54A', text=[f"{v:.0f}%" for v in _p_acc],
                    textposition='outside', cliponaxis=False))
                _pfig.add_trace(_go.Bar(name="Rejectors", y=_p_labels, x=_p_rej, orientation='h',
                    marker_color='#C8102E', text=[f"{v:.0f}%" for v in _p_rej],
                    textposition='outside', cliponaxis=False))
                _pfig.add_trace(_go.Bar(name="Cancelled", y=_p_labels, x=_p_can, orientation='h',
                    marker_color='#F7941D', text=[f"{v:.0f}%" for v in _p_can],
                    textposition='outside', cliponaxis=False))
                _pfig.update_layout(
                    barmode='group', height=220,
                    margin=dict(l=10, r=60, t=10, b=20),
                    xaxis=dict(range=[0, 110], ticksuffix='%', showgrid=True,
                               gridcolor='#F0EDE8', title=None),
                    yaxis=dict(autorange='reversed', tickfont=dict(size=12)),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02,
                                xanchor='center', x=0.5, font=dict(size=11)),
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                )
                st.plotly_chart(_pfig, use_container_width=True, config=PLOTLY_CONFIG,
                                key=f"mar_plat_{platform}_{time_mode}")

                # Model-level detail in expander
                with st.expander("Model-level breakdown", expanded=False):
                    for _plat_name in _plat_order:
                        _pm = [r for r in _mar_rows if r["platform"] == _plat_name]
                        _pm.sort(key=lambda x: -x["acc_pct"])
                        if not _pm:
                            continue
                        st.caption(f"**{_plat_name}**")
                        _mfig = _go.Figure()
                        _mm_labels = [f"{r['model']} (n={r['unique_n']:,})" for r in _pm]
                        _mfig.add_trace(_go.Bar(name="Acc", y=_mm_labels,
                            x=[r["acc_pct"] for r in _pm], orientation='h',
                            marker_color='#39B54A', text=[f"{r['acc_pct']:.0f}%" for r in _pm],
                            textposition='outside', cliponaxis=False))
                        _mfig.add_trace(_go.Bar(name="Rej", y=_mm_labels,
                            x=[r["rej_pct"] for r in _pm], orientation='h',
                            marker_color='#C8102E', text=[f"{r['rej_pct']:.0f}%" for r in _pm],
                            textposition='outside', cliponaxis=False))
                        _mfig.add_trace(_go.Bar(name="Can", y=_mm_labels,
                            x=[r["can_pct"] for r in _pm], orientation='h',
                            marker_color='#F7941D', text=[f"{r['can_pct']:.0f}%" for r in _pm],
                            textposition='outside', cliponaxis=False))
                        _mfig.update_layout(
                            barmode='group', height=max(160, 55 * len(_pm)),
                            margin=dict(l=10, r=60, t=5, b=5),
                            xaxis=dict(range=[0, 110], ticksuffix='%', showgrid=True,
                                       gridcolor='#F0EDE8', title=None),
                            yaxis=dict(autorange='reversed', tickfont=dict(size=11)),
                            showlegend=False,
                            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                        )
                        st.plotly_chart(_mfig, use_container_width=True, config=PLOTLY_CONFIG,
                                        key=f"mar_model_{_plat_name}_{platform}_{time_mode}")
        except Exception as _e:
            st.caption(f"Model acceptance data unavailable: {_e}")

# _overview_is_comparison is set at top of page based on segment_nav == "Overview".
# Overview = comparison hub (cross-segment grouped bars + scorecard).
# Overall = All-respondents deep-dive (same stacked-bar format as Acceptors/Rejectors/Cancelled).

trend_map = {}


def _trim_to_selected_months(tbl):
    """Bug fix: table generators always emit every month column from
    MONTH_ORDER regardless of the Time Period filter, so picking 'Quarter'
    silently showed all 10 months instead of just that quarter's (e.g.
    April/May/June for Q1) — exactly the live site's own per-month columns,
    just scoped to the chosen window. Quarter-COMBINED columns (JAS'25 etc,
    distinct from the Quarter time-period filter) only make sense in the
    full 'All Months' view — dropped here otherwise, and also droppable via
    the 'Show Quarter-Combined Columns' toggle."""
    _q_col_set = set(_active_q_groups.keys())
    if time_mode == "All Months":
        # No quarter combined cols in all-months view — strip any that leaked in.
        cols = [c for c in tbl.columns if c not in _q_col_set]
    elif time_mode == "Quarter (Financial Calendar)":
        # Show quarter combined cols only; strip individual month columns.
        cols = ["Unnamed: 0", "All"] + [c for c in tbl.columns if c in _q_col_set]
    else:
        # Month Range — individual months, no quarter cols.
        cols = ["Unnamed: 0", "All"] + [m for m in selected_months if m in tbl.columns]
    # The custom Year+Month combined column is independent of the "View by"
    # time-period filter above — always keep it if present, regardless of
    # which month-window mode is active. Placed right after 'All' (not at
    # the end) per user request, so it sits next to the column it's most
    # directly comparable to.
    if custom_col_name and custom_col_name in tbl.columns:
        cols = [c for c in cols if c != custom_col_name]
        insert_at = cols.index("All") + 1
        cols = cols[:insert_at] + [custom_col_name] + cols[insert_at:]
    return tbl[cols]


def _filter_brand_table(tbl, selected_brands, rollup_labels):
    """Keeps the Base row + only the brand-rollup-and-its-members runs whose
    rollup is in `selected_brands` — per user request to let people narrow
    a long brand-wise table to a few brands rather than always rendering
    every brand at once (default selection is still every brand, so the
    full data stays one click away, not hidden)."""
    keep_idx = [0]
    showing = False
    for i in range(1, len(tbl)):
        label = tbl.iloc[i]['Unnamed: 0']
        if label in rollup_labels:
            showing = label in selected_brands
        if showing:
            keep_idx.append(i)
    return tbl.iloc[keep_idx].reset_index(drop=True)


def _back_to_top():
    """Small 'Back to top' button using JS to scroll Streamlit's main container."""
    import streamlit.components.v1 as _c
    _c.html(
        "<button onclick=\"(window.parent.document.querySelector('.stMain')"
        "||window.parent.document.querySelector('section.main')"
        "||window.parent.document.body).scrollTo({top:0,behavior:'smooth'})\" "
        "style='font-size:10px;color:#999;background:none;border:1px solid #ddd;"
        "border-radius:10px;padding:2px 10px;cursor:pointer;float:right;"
        "margin-bottom:4px'>↑ Top</button>",
        height=28,
    )


def section(title, table_fn, caption=None, chart_type="bar", cap_chart=None, brand_filter_labels=None, color=None, show_chart=True):
    """Renders one metric: chart + data table + significance markers vs the
    unfiltered Overview baseline.
    cap_chart: optional {"max_rows": N, "exclude_labels": [...]} — per user
    request ('brand wise data is not showing the full table'), treemaps cap
    to ~8 rows + 'Other' so the CHART stays readable, but the data table
    below it should always show every row. When given, the chart plots the
    capped subset while the table renders the full, uncapped data.
    brand_filter_labels: optional list of brand-rollup labels — renders a
    multiselect (default = every brand, i.e. unchanged full-data behavior)
    so a long brand-wise table can be narrowed to a few brands at a time,
    per 'add some kind of filter... ofc user will have the liberty to see
    the whole data'. Also switches the table to the live site's nested
    rollup+member look (indented member rows)."""
    _ck = f"_tbl_{title}_{segment_value}_{platform}_{model}_{time_mode}_{','.join(sorted(selected_months))}_{custom_col_name or ''}"
    if _ck not in st.session_state or (_ck + "_b") not in st.session_state:
        st.session_state[_ck] = _trim_to_selected_months(table_fn(df, segment_value))
        st.session_state[_ck + "_b"] = _trim_to_selected_months(table_fn(baseline_df, "All"))
    tbl = st.session_state[_ck]
    baseline_tbl = st.session_state[_ck + "_b"]
    rollup_set = set(brand_filter_labels) if brand_filter_labels else None
    if brand_filter_labels:
        selected = st.multiselect(f"Brands shown in '{title}'", brand_filter_labels, default=brand_filter_labels, key=f"brandfilter_{title}")
        tbl = _filter_brand_table(tbl, selected, rollup_set)
        baseline_tbl = _filter_brand_table(baseline_tbl, selected, rollup_set)
    # Per explicit user instruction: significance NEVER runs on the
    # aggregate 'All' column, anywhere — only on individual month columns
    # (and the quarter-combined columns, same rule, same n>=30 gate —
    # their base is always well over 30 so they're virtually always
    # eligible when shown).
    # vs_own_all=True (2026-07-29): matches the live MIS site's own
    # methodology (each month vs that table's own 'All' column) instead of
    # vs other segments, per user request -- keeps our n>=30 gate, unlike
    # the live site which has none.
    sig_cols = (list(_active_q_groups.keys()) if show_quarter_cols else selected_months) + ([custom_col_name] if custom_col_name else [])
    col_markers = compare_to_baseline_by_column(tbl, baseline_tbl, sig_cols, confidence=sig_confidence, vs_own_all=True) if show_sig else None
    col_markers = filter_sig_markers(col_markers, sig_direction)
    # Per user request ("if one section is significant how much
    # significant it is it should be shown") — gaps_by_column() mirrors
    # compare_to_baseline_by_column()'s exact row/column alignment, so it
    # zips directly against col_markers by index.
    col_gaps = gaps_by_column(tbl, baseline_tbl, sig_cols, vs_own_all=True) if show_sig else None
    chart_tbl = engine.cap_rows(tbl, **cap_chart) if cap_chart else tbl
    current_seg_label = _seg_label_map.get(segment_value, "Overview")
    seg_tables = {}  # populated on Overview for P5 so-what gap analysis
    with st.container(border=True):
        if caption:
            st.caption(caption)
        # Overview only: cross-segment comparison bar (Acc vs Rej vs Can side-by-side).
        # Segment pages use their own stacked bar / donut via render_chart_with_table below.
        if _overview_is_comparison and chart_type in ("stacked_bar", "bar", "donut") and len(_seg_dfs) >= 2:
            for seg_label, seg_df in _seg_dfs.items():
                try:
                    seg_tbl = table_fn(seg_df, list(_seg_label_map.keys())[list(_seg_label_map.values()).index(seg_label)])
                    if float(seg_tbl.iloc[0]['All']) >= 30:
                        seg_tables[seg_label] = seg_tbl
                except Exception:
                    pass
            if seg_tables:
                fig_cmp = segment_comparison_bar(seg_tables, title, current_seg=current_seg_label)
                if fig_cmp:
                    st.plotly_chart(fig_cmp, use_container_width=True, config=PLOTLY_CONFIG, key=f"cmpbar_{title}_{segment_value}_{platform}_{model}_{time_mode}")
                    st.caption("↑/↓ on bars = segment significantly higher/lower vs others — see Significance Guide in sidebar")
            with st.expander("📊 Data Table", expanded=False):
                # On Overview comparison mode: table must match chart → show cross-segment
                # breakdown (Acc% | Rej% | Can%) not the blended "All" single-column table.
                if seg_tables and len(seg_tables) >= 2:
                    import pandas as pd
                    _segs_in_order = [s for s in ("Acceptors", "Rejectors", "Cancelled") if s in seg_tables]
                    _seg_labels_short = {"Acceptors": "Acceptors", "Rejectors": "Rejectors", "Cancelled": "Cancelled"}
                    _first_tbl = seg_tables[_segs_in_order[0]]
                    _cats = list(_first_tbl.iloc[1:]['Unnamed: 0'])
                    # Pre-compute bases for pairwise Acc vs Rej sig test
                    _n_acc_xseg = float(seg_tables["Acceptors"].iloc[0]['All']) if "Acceptors" in seg_tables else 0
                    _n_rej_xseg = float(seg_tables["Rejectors"].iloc[0]['All']) if "Rejectors" in seg_tables else 0
                    _can_do_sig = _n_acc_xseg >= 30 and _n_rej_xseg >= 30
                    _xrows = []
                    for _cat in _cats:
                        _row = {"Category": _cat}
                        _vals = []
                        _p_acc_cat = _p_rej_cat = None
                        for _sl in _segs_in_order:
                            _st = seg_tables[_sl]
                            _r = _st[_st['Unnamed: 0'] == _cat]
                            _v = float(_r.iloc[0]['All']) if not _r.empty else 0.0
                            _vals.append(_v)
                            if _sl == "Acceptors":
                                _p_acc_cat = _v
                            elif _sl == "Rejectors":
                                _p_rej_cat = _v
                        # Pairwise Acc vs Rej significance marker on Acceptors column
                        _sig_marker = ""
                        if _can_do_sig and _p_acc_cat is not None and _p_rej_cat is not None:
                            try:
                                _sig = calculate_significance(
                                    _p_acc_cat / 100, _n_acc_xseg,
                                    _p_rej_cat / 100, _n_rej_xseg,
                                    confidence=sig_confidence,
                                )
                                if _sig.get('is_significant'):
                                    _sig_marker = " ▲" if _p_acc_cat > _p_rej_cat else " ▼"
                            except Exception:
                                pass
                        for _i, _sl in enumerate(_segs_in_order):
                            _v = _vals[_i]
                            if _sl == "Acceptors" and _sig_marker:
                                _row[_seg_labels_short[_sl]] = f"{_v:.0f}%{_sig_marker}"
                            else:
                                _row[_seg_labels_short[_sl]] = f"{_v:.0f}%"
                        if len(_vals) >= 2:
                            _row["Max Gap"] = f"{max(_vals) - min(_vals):.0f} pp"
                        _xrows.append(_row)
                    _bases = {"Category": f"Base (n)"}
                    for _sl in _segs_in_order:
                        _bases[_seg_labels_short[_sl]] = f"{int(float(seg_tables[_sl].iloc[0]['All'])):,}"
                    _bases["Max Gap"] = "—"
                    _xdf = pd.DataFrame([_bases] + _xrows)
                    st.dataframe(_xdf, use_container_width=True, hide_index=True)
                    st.caption("↑/↓ = significantly higher/lower vs other segments — see Significance Guide in sidebar")
                    st.download_button("⬇ CSV", data=_xdf.to_csv(index=False),
                                       file_name=f"{title.lower().replace(' ','_')}_cross_seg.csv",
                                       mime="text/csv", key=f"dl_xseg_{title}")
                else:
                    from utils.visuals import _render_html_table
                    _render_html_table(tbl, accent=(color or accent), col_sig_markers=col_markers, rollup_labels=rollup_set, highlight_col=custom_col_name)
                    st.download_button("⬇ CSV", data=tbl.to_csv(index=False),
                                       file_name=f"{title.lower().replace(' ','_')}.csv",
                                       mime="text/csv", key=f"dl_{title}")
        else:
            if show_chart:
                render_chart_with_table(chart_tbl, title, color=(color or accent), key=f"chart_{title}", chart_type=chart_type, col_sig_markers=col_markers, table_df_html=tbl, rollup_labels=rollup_set, highlight_col=custom_col_name, col_sig_gaps=col_gaps)
            else:
                from utils.visuals import _render_html_table
                _render_html_table(tbl, accent=(color or accent), col_sig_markers=col_markers, rollup_labels=rollup_set, highlight_col=custom_col_name)
                st.download_button("⬇ CSV", data=tbl.to_csv(index=False),
                                   file_name=f"{title.lower().replace(' ','_')}.csv",
                                   mime="text/csv", key=f"dl_{title}")
        cat_rows = tbl.iloc[1:]
        top_row = cat_rows.loc[cat_rows['All'].astype(float).idxmax()]
        # P5: "So what?" — auto-computed 1-line insight below each chart.
        # On Overview: surface biggest cross-segment gap. On segment pages:
        # state the dominant category plainly.
        try:
            _top_cat = str(top_row['Unnamed: 0'])
            _top_pct = float(top_row['All'])
            _base_title = title.split(" —")[0].strip()
            _so_what = ""
            if seg_tables and len(seg_tables) >= 2:
                _max_gap, _gap_cat, _high_seg, _low_seg = 0, None, "", ""
                _all_cats = list(list(seg_tables.values())[0].iloc[1:]['Unnamed: 0'])
                for _cat in _all_cats:
                    _vals = {}
                    for _sl, _st in seg_tables.items():
                        _r = _st[_st['Unnamed: 0'] == _cat]
                        if len(_r):
                            _vals[_sl] = float(_r.iloc[0]['All'])
                    if len(_vals) >= 2:
                        _gap = max(_vals.values()) - min(_vals.values())
                        if _gap > _max_gap:
                            _max_gap = _gap
                            _gap_cat = _cat
                            _high_seg = max(_vals, key=lambda k: _vals[k])
                            _low_seg = min(_vals, key=lambda k: _vals[k])
                if _gap_cat and _max_gap >= 4:
                    _so_what = f"Biggest gap: <b>{_gap_cat}</b> — {_high_seg} leads {_low_seg} by <b>{_max_gap:.0f} pp</b>"
            else:
                _single = {
                    "Age": f"<b>{_top_cat}</b> is dominant age group ({_top_pct:.0f}%)",
                    "Education": f"{_top_pct:.0f}% are <b>{_top_cat}</b>",
                    "Occupation": f"<b>{_top_pct:.0f}%</b> are {_top_cat}",
                    "Household Income": f"Core income band: <b>{_top_cat}</b> ({_top_pct:.0f}%)",
                    "Type of Buyer": ("Mostly fleet expansion" if "Additional" in _top_cat else "Mostly replacement buying") + f" — {_top_pct:.0f}%",
                    "Additional + Replaced — CC Wise": f"Most common prior CC: <b>{_top_cat}</b> ({_top_pct:.0f}%)",
                    "Brand Owned — CC Wise": f"Most own <b>{_top_cat}</b> segment ({_top_pct:.0f}%)",
                    "Brand Considered — CC Wise": f"Also considering: <b>{_top_cat}</b> ({_top_pct:.0f}%)",
                }
                _so_what = _single.get(_base_title, f"<b>{_top_cat}</b> leads ({_top_pct:.0f}%)")
            if _so_what:
                st.markdown(
                    f"<div style='font-size:0.8rem;color:#4A4644;background:#F7F6F4;"
                    f"border-left:3px solid {accent};border-radius:0 6px 6px 0;"
                    f"padding:6px 12px;margin:6px 0 2px;line-height:1.4;'>"
                    f"💡 {_so_what}</div>",
                    unsafe_allow_html=True,
                )
        except Exception:
            pass
        # Per user feedback ("vague... not based on the table being shown,
        # not keeping in mind brand context, range of months and proper
        # analysis with significance values undermined") — the facts
        # payload now carries the actual filter context and the exact
        # month range. Significant findings are now per-month only (no
        # 'All' column testing), so each hit names which month it's
        # significant in.
        sig_hits = []
        for col, col_marker_list in (col_markers or {}).items():
            for i, m in enumerate(col_marker_list):
                if not m:
                    continue
                cat_label = cat_rows.iloc[i]['Unnamed: 0']
                this_pct = float(cat_rows.iloc[i][col])
                base_match = baseline_tbl[baseline_tbl['Unnamed: 0'] == cat_label]
                rest_pct = round(float(base_match.iloc[0][col]), 1) if len(base_match) and col in base_match.columns else None
                sig_hits.append({
                    "category": cat_label, "month": col,
                    "this_segment_pct": round(this_pct, 1),
                    "rest_of_sample_pct": rest_pct,
                    "gap_points": round(this_pct - rest_pct, 1) if rest_pct is not None else None,
                    "direction": "higher" if m in ('▲', '△') else "lower",
                    "confidence": "95%" if m in ('▲', '▼') else "90% directional",
                })
    trend_map[title] = tbl


def brand_wise_section(title, table_fn, color, caption=None, chart_type="stacked_bar", show_chart=True):
    """Bespoke renderer for the three brand-wise tables (Additional+Replaced/
    Brand Owned/Brand Considered) — per user request: CC-wise chart goes
    ABOVE this section (caller's responsibility, see layout below), and
    THIS section shows a brand-ROLLUP-only comparison bar on top, then the
    full member-level table below it sorted descending with the 'Other'
    catch-all pinned to the very end — replacing the earlier capped
    treemap approach. Each of the three sections gets its own distinct
    color (passed in), not the segment's shared accent."""
    _ck = f"_tbl_{title}_{segment_value}_{platform}_{model}_{time_mode}_{','.join(sorted(selected_months))}_{custom_col_name or ''}"
    if _ck not in st.session_state or (_ck + "_b") not in st.session_state:
        st.session_state[_ck] = _trim_to_selected_months(table_fn(df, segment_value))
        st.session_state[_ck + "_b"] = _trim_to_selected_months(table_fn(baseline_df, "All"))
    tbl = st.session_state[_ck]
    baseline_tbl = st.session_state[_ck + "_b"]
    rollup_set = set(ROLLUP_LABELS)
    selected_brands = st.multiselect("Brands", ROLLUP_LABELS, default=ROLLUP_LABELS, key=f"brandfilter_{title}")
    tbl = _filter_brand_table(tbl, selected_brands, rollup_set)
    baseline_tbl = _filter_brand_table(baseline_tbl, selected_brands, rollup_set)
    if len(tbl) <= 1:
        st.info(f"{title}: no brands selected.")
        return

    sig_cols = (list(_active_q_groups.keys()) if show_quarter_cols else selected_months) + ([custom_col_name] if custom_col_name else [])
    col_markers = compare_to_baseline_by_column(tbl, baseline_tbl, sig_cols, confidence=sig_confidence, vs_own_all=True) if show_sig else None
    col_markers = filter_sig_markers(col_markers, sig_direction)
    col_gaps = gaps_by_column(tbl, baseline_tbl, sig_cols, vs_own_all=True) if show_sig else None

    sorted_tbl = engine.sort_brand_table(tbl, rollup_set)
    rollup_tbl = engine.rollup_only_table(tbl, rollup_set)

    orig_labels = tbl.iloc[1:]['Unnamed: 0'].tolist()
    label_order = sorted_tbl.iloc[1:]['Unnamed: 0'].tolist()
    sorted_col_markers = None
    if col_markers:
        sorted_col_markers = {}
        for col, mk in col_markers.items():
            m_by_label = dict(zip(orig_labels, mk))
            sorted_col_markers[col] = [m_by_label.get(l, '') for l in label_order]
    sorted_col_gaps = None
    if col_gaps:
        sorted_col_gaps = {}
        for col, gp in col_gaps.items():
            g_by_label = dict(zip(orig_labels, gp))
            sorted_col_gaps[col] = [g_by_label.get(l) for l in label_order]

    with st.expander(title, expanded=True):
        if caption:
            st.caption(caption)
        if show_chart:
            render_chart_with_table(rollup_tbl, title, color=color, key=f"chart_{title}",
                                     chart_type=chart_type, col_sig_markers=sorted_col_markers,
                                     table_df_html=sorted_tbl, rollup_labels=rollup_set, highlight_col=custom_col_name,
                                     col_sig_gaps=sorted_col_gaps)
        else:
            _safe_key = title.lower().replace(' ', '_').replace('+', 'n').replace('—', '').replace('/', '_')
            render_collapsible_brand_table(
                sorted_tbl, title=title, color=color,
                rollup_labels=rollup_set,
                col_sig_markers=sorted_col_markers,
                col_sig_gaps=sorted_col_gaps,
                highlight_col=custom_col_name,
                accent=color,
                key_suffix=_safe_key,
            )
            st.download_button("⬇ CSV", data=sorted_tbl.to_csv(index=False),
                               file_name=f"{title.lower().replace(' ','_')}.csv",
                               mime="text/csv", key=f"dl_{title}")
        cat_rows = sorted_tbl.iloc[1:]
        sig_hits = []
        for col, col_marker_list in (sorted_col_markers or {}).items():
            for i, m in enumerate(col_marker_list):
                if not m:
                    continue
                cat_label = cat_rows.iloc[i]['Unnamed: 0']
                this_pct = float(cat_rows.iloc[i][col])
                base_match = baseline_tbl[baseline_tbl['Unnamed: 0'] == cat_label]
                rest_pct = round(float(base_match.iloc[0][col]), 1) if len(base_match) and col in base_match.columns else None
                sig_hits.append({
                    "category": cat_label, "month": col,
                    "this_segment_pct": round(this_pct, 1),
                    "rest_of_sample_pct": rest_pct,
                    "gap_points": round(this_pct - rest_pct, 1) if rest_pct is not None else None,
                    "direction": "higher" if m in ('▲', '△') else "lower",
                    "confidence": "95%" if m in ('▲', '▼') else "90% directional",
                })
    trend_map[title] = sorted_tbl


# Strict per-segment section/subsection structure, matching the live
# EXACT live-site order, verified from docs/investigation/full_scraped_data.json's
# dict insertion order (true DOM order on the live PHP page), not the
# requirements-doc's simplified per-segment table list — that doc describes
# what each segment NEEDS, the live site actually renders all three brand
# tables for every one of its four tabs (Overall/Acceptor/Rejector/
# Cancelled). Order for every segment, no exceptions:
#   Age, Education, Occupation, Household Income, Type of Buyer,
#   Additional+Replaced (CC, Brand), Brand Owned (CC, Brand),
#   Brand Considered (CC, Brand), Reasons.
st.markdown('<div id="sec-demographics"></div>', unsafe_allow_html=True)
st.markdown("### Demographics")
st.caption("Age, education, occupation, and household income profile of this segment — who are these respondents?")
section("Age", lambda d, s: _tbl_age(d, base_label=s, numeric=True, extra_groups=effective_extra_groups), chart_type="stacked_bar")
section("Education", lambda d, s: _tbl_education(d, base_label=s, numeric=True, extra_groups=effective_extra_groups), chart_type="stacked_bar")
section("Occupation", lambda d, s: _tbl_occupation(d, base_label=s, numeric=True, extra_groups=effective_extra_groups), chart_type="stacked_bar")
section("Household Income", lambda d, s: _tbl_income(d, base_label=s, numeric=True, extra_groups=effective_extra_groups), chart_type="stacked_bar")

_back_to_top()
st.markdown('<div id="sec-buyer-type"></div>', unsafe_allow_html=True)
st.markdown("### Type of Buyer")
st.caption("Was this purchase an additional bike, a replacement, or a first-time 2W purchase? This shapes the entire decision context.")
section("Type of Buyer", lambda d, s: _tbl_type_of_buyer(d, base_label=s, numeric=True, extra_groups=effective_extra_groups), chart_type="stacked_bar")

ROLLUP_LABELS = ["Royal Enfield"] + [m for m in engine.manufacturers() if m != "Royal Enfield"]

ADD_REPL_COLOR = "#2E3192"
BRAND_OWNED_COLOR = "#662D91"
BRAND_CONSIDERED_COLOR = "#1B8A8A"
REASONS_COLOR = "#D6742D"

# Per user request (2026-07-27): reverted to the original per-segment
# scoping (docs/PROJECT_LOG.md 2026-06-18) — Additional+Replaced is an
# Acceptor-specific question ("what did you replace/add to, to buy your
# RE"), Brand Owned is a Rejector/Cancelled-specific question ("what did
# you buy/already own instead"). A later change briefly showed both on
# every segment; Brand Owned/Brand Considered/Additional+Replaced/Type of
# Buyer are all validated now (see CLAUDE.md Resolved Blockers), so the
# earlier blanket hide is no longer warranted either.
# Additional+Replaced: Acceptor + Overall
if segment_value in ("Acceptor", "All"):
    _back_to_top()
    st.markdown('<div id="sec-addrepl"></div>', unsafe_allow_html=True)
    st.markdown("### Additional + Replaced")
    st.caption("What did these respondents own before this purchase? CC-wise and Brand-wise breakdown of the bike being added or replaced.")
    section("Additional + Replaced — CC Wise",
            lambda d, s: engine.additional_replaced_table(d, by="cc", base_label=s, numeric=True, extra_groups=effective_extra_groups),
            color=ADD_REPL_COLOR, chart_type="stacked_bar", show_chart=False)
    brand_wise_section("Additional + Replaced — Brand Wise",
                        lambda d, s: engine.additional_replaced_table(d, by="brand", base_label=s, numeric=True, extra_groups=effective_extra_groups),
                        color=ADD_REPL_COLOR, show_chart=False)

# Brand Owned: Rejector + Cancelled only (they own a competitor bike)
if segment_value in ("Rejector", "Cancelled"):
    _back_to_top()
    st.markdown('<div id="sec-brand-owned"></div>', unsafe_allow_html=True)
    st.markdown("### Brand Owned")
    st.caption("Current bike ownership — what brand and CC segment does this respondent already ride?")
    section("Brand Owned — CC Wise",
            lambda d, s: engine.brand_owned_table(d, by="cc", base_label=s, numeric=True, extra_groups=effective_extra_groups),
            color=BRAND_OWNED_COLOR, chart_type="stacked_bar", show_chart=False)
    brand_wise_section("Brand Owned — Brand Wise",
                        lambda d, s: engine.brand_owned_table(d, by="brand", base_label=s, numeric=True, extra_groups=effective_extra_groups),
                        color=BRAND_OWNED_COLOR, show_chart=False)

# Brand Considered: Acceptors only
if segment_value == "Acceptor":
    _back_to_top()
    st.markdown('<div id="sec-brand-considered"></div>', unsafe_allow_html=True)
    st.markdown("### Brand Considered")
    st.caption("Which other brands did this respondent evaluate before deciding? CC-wise and Brand-wise breakdown.")
    section("Brand Considered — CC Wise",
            lambda d, s: engine.brand_considered_table(d, by="cc", base_label=s, numeric=True, extra_groups=effective_extra_groups),
            color=BRAND_CONSIDERED_COLOR, chart_type="stacked_bar", show_chart=False)
    if not _overview_is_comparison:
        brand_wise_section("Brand Considered — Brand Wise",
                            lambda d, s: engine.brand_considered_table(d, by="brand", base_label=s, numeric=True, extra_groups=effective_extra_groups),
                            color=BRAND_CONSIDERED_COLOR, show_chart=False)


_back_to_top()
st.markdown('<div id="sec-reasons"></div>', unsafe_allow_html=True)
st.markdown("### Reasons & Motivations")
# Deterministic, exact reproduction (2026-07-27) via each respondent's own
# assigned netting codes -- see DataEngine.reasons_table() docstring for
# the validation against scraped live-site numbers. Per-row segment-aware
# (2026-07-28), so Overview/"All" gets a real combined table too, not the
# placeholder -- each respondent decodes through their OWN segment's
# netting sheet even when df spans all three.
if segment_value == "Acceptor":
    st.markdown('<div id="sec-reasons"></div>', unsafe_allow_html=True)
    st.markdown("### Key Buying Factors (Why Bought)")
    st.caption("Decoded from each respondent's own Infoleap-assigned netting code, matching the raw Masterfile workbook exactly (not an AI approximation).")
    _r_tree = engine.reasons_tree_data(df, base_label="Acceptor", broad_prefix="mq2a", extra_groups=effective_extra_groups)
    with st.container(border=True):
        render_collapsible_reasons_table(_r_tree, "Key Buying Factors (Why Bought)", color=REASONS_COLOR, key_suffix="acc_mq2a")
    _xl = open_end_tree_to_excel(_r_tree, "Key Buying Factors", show_sig=show_sig)
    if _xl:
        st.download_button("⬇ Download as Excel", _xl, "key_buying_factors.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_kbf_acc")
    _r_super_tbl = _trim_to_selected_months(
        engine.reasons_table(df, base_label="Acceptor", broad_prefix="mq2a", by="supernet", numeric=True, extra_groups=effective_extra_groups))
    trend_map["Key Buying Factors — Category Wise"] = _r_super_tbl

elif segment_value in ("Rejector", "Cancelled"):
    st.markdown('<div id="sec-reasons-considered"></div>', unsafe_allow_html=True)
    st.markdown("### Why They Considered RE First")
    st.caption("Positive considerations & factors liked about RE before rejecting/cancelling — decoded from Infoleap netting codes.")
    _r_tree_c = engine.reasons_tree_data(df, base_label=segment_value, broad_prefix="mq2c", extra_groups=effective_extra_groups)
    with st.container(border=True):
        render_collapsible_reasons_table(_r_tree_c, "Why They Considered RE First", color=BRAND_CONSIDERED_COLOR, key_suffix=f"{segment_value}_mq2c")
    _xl_c = open_end_tree_to_excel(_r_tree_c, "Why Considered RE First", show_sig=show_sig)
    if _xl_c:
        st.download_button("⬇ Download as Excel", _xl_c, "why_considered_re.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_considered_{segment_value}")
    _r_super_c = _trim_to_selected_months(
        engine.reasons_table(df, base_label=segment_value, broad_prefix="mq2c", by="supernet", numeric=True, extra_groups=effective_extra_groups))
    trend_map["Why Considered RE — Category Wise"] = _r_super_c

    _rej_label = "Reasons for Rejection" if segment_value == "Rejector" else "Reasons for Cancelling"
    st.markdown('<div id="sec-reasons"></div>', unsafe_allow_html=True)
    st.markdown(f"### {_rej_label}")
    st.caption(f"{_rej_label} — decoded from each respondent's own Infoleap-assigned netting code.")
    _r_tree_r = engine.reasons_tree_data(df, base_label=segment_value, broad_prefix="mq3a", extra_groups=effective_extra_groups)
    with st.container(border=True):
        render_collapsible_reasons_table(_r_tree_r, _rej_label, color=REASONS_COLOR, key_suffix=f"{segment_value}_mq3a")
    _xl_r = open_end_tree_to_excel(_r_tree_r, _rej_label[:31], show_sig=show_sig)
    if _xl_r:
        _rej_fname = "reasons_rejection.xlsx" if segment_value == "Rejector" else "reasons_cancelling.xlsx"
        st.download_button("⬇ Download as Excel", _xl_r, _rej_fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_rej_{segment_value}")
    _r_super_r = _trim_to_selected_months(
        engine.reasons_table(df, base_label=segment_value, broad_prefix="mq3a", by="supernet", numeric=True, extra_groups=effective_extra_groups))
    trend_map[f"{_rej_label} — Category Wise"] = _r_super_r

elif segment_value in ("Overview", "All"):
    st.markdown('<div id="sec-reasons"></div>', unsafe_allow_html=True)
    st.markdown("### Open-Ended Netting Taxonomy Breakdown")
    st.caption("Official Infoleap netting codebook breakdown across Acceptor (KBF), Rejector (Considered & Rejected), and Cancelled segments.")
    _acc_df = engine.filter_df("Acceptor")
    if len(_acc_df) > 0:
        st.markdown("#### Acceptors — Key Buying Factors")
        _r_tree_acc = engine.reasons_tree_data(_acc_df, base_label="Acceptor", broad_prefix="mq2a", extra_groups=effective_extra_groups)
        with st.container(border=True):
            render_collapsible_reasons_table(_r_tree_acc, "Acceptors — Key Buying Factors", color=REASONS_COLOR, key_suffix="ov_acc_mq2a")
        _xl_ov_acc = open_end_tree_to_excel(_r_tree_acc, "Acceptors KBF", show_sig=show_sig)
        if _xl_ov_acc:
            st.download_button("⬇ Download as Excel", _xl_ov_acc, "acceptors_kbf.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_ov_acc")
    _rej_df = engine.filter_df("Rejector")
    if len(_rej_df) > 0:
        st.markdown("#### Rejectors — Reasons for Rejection")
        _r_tree_rej = engine.reasons_tree_data(_rej_df, base_label="Rejector", broad_prefix="mq3a", extra_groups=effective_extra_groups)
        with st.container(border=True):
            render_collapsible_reasons_table(_r_tree_rej, "Rejectors — Reasons for Rejection", color=REASONS_COLOR, key_suffix="ov_rej_mq3a")
        _xl_ov_rej = open_end_tree_to_excel(_r_tree_rej, "Rejectors Reasons", show_sig=show_sig)
        if _xl_ov_rej:
            st.download_button("⬇ Download as Excel", _xl_ov_rej, "rejectors_reasons.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_ov_rej")
    _can_df = engine.filter_df("Cancelled")
    if len(_can_df) > 0:
        st.markdown("#### Booked & Cancelled — Reasons for Cancelling")
        _r_tree_can = engine.reasons_tree_data(_can_df, base_label="Cancelled", broad_prefix="mq3a", extra_groups=effective_extra_groups)
        with st.container(border=True):
            render_collapsible_reasons_table(_r_tree_can, "Booked & Cancelled — Reasons for Cancelling", color=REASONS_COLOR, key_suffix="ov_can_mq3a")
        _xl_ov_can = open_end_tree_to_excel(_r_tree_can, "Cancelled Reasons", show_sig=show_sig)
        if _xl_ov_can:
            st.download_button("⬇ Download as Excel", _xl_ov_can, "cancelled_reasons.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_ov_can")

