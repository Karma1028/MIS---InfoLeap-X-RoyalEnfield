import streamlit as st
import streamlit.components.v1 as _components
from auth import render_login, render_landing
from styles.theme import render_theme_css, SEGMENT_COLORS
from utils.data_engine import DataEngine, RE_MODEL_PLATFORM, RE_MODEL_LABELS, month_label_to_fy_quarter
from utils.visuals import render_chart_with_table, month_trend_chart, segment_trend_chart, render_sig_legend, segment_comparison_bar, PLOTLY_CONFIG, filter_sig_markers
from utils.stat_engine import compare_to_baseline_by_column, calculate_significance
from utils.compare import render_comparison_page
from utils.verbatim_intel import render_verbatim_intelligence_page
from utils.dealership import render_dealership_page
from utils.product_features import render_product_features_page
from utils.ai_summary import render_ai_summary_button, render_chart_ai_blurb
from utils.settings_page import render_settings_page
from utils.overview_intro import render_overview_intro

st.set_page_config(page_title="RE Digital Showroom | Infoleap", layout="wide", initial_sidebar_state="expanded")

if not render_login():
    st.stop()
if not render_landing():
    st.stop()


@st.cache_resource
def load_engine():
    engine = DataEngine()
    engine.load_data()
    return engine


engine = load_engine()

# Cached wrappers for the most expensive per-rerun operations.
# @st.cache_data persists across reruns — same filter = cache hit, not a full
# recompute. Calling engine methods directly (uncached) costs ~15-30ms each;
# the hash check on a cached hit costs ~2-5ms. On Overview, section() loops
# over 3 segments × 5 demographic sections = 15 table calls; Block D does
# 14 models × 3 segments = 42 filter_df calls. Without cache: ~600-900ms per
# rerun. With cache after first run for a given filter: ~50-100ms.
@st.cache_data(show_spinner=False, max_entries=600)
def _tbl_filter(segment, platform, model_code, months_tuple):
    _df = engine.filter_df(segment=segment, platform=platform, model_code=model_code)
    return _df[_df['month_label'].isin(set(months_tuple))].copy()

@st.cache_data(show_spinner=False, max_entries=600)
def _tbl_age(df, base_label="All", numeric=False, extra_groups=None):
    return engine.age_table(df, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

@st.cache_data(show_spinner=False, max_entries=600)
def _tbl_education(df, base_label="All", numeric=False, extra_groups=None):
    return engine.education_table(df, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

@st.cache_data(show_spinner=False, max_entries=600)
def _tbl_occupation(df, base_label="All", numeric=False, extra_groups=None):
    return engine.occupation_table(df, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

@st.cache_data(show_spinner=False, max_entries=600)
def _tbl_income(df, base_label="All", numeric=False, extra_groups=None):
    return engine.household_income_table(df, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

@st.cache_data(show_spinner=False, max_entries=600)
def _tbl_type_of_buyer(df, base_label="All", numeric=False, extra_groups=None):
    return engine.type_of_buyer_table(df, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

@st.cache_data(show_spinner=False, max_entries=200)
def _tbl_brand_owned(df, by="brand", base_label="All", numeric=False, extra_groups=None):
    return engine.brand_owned_table(df, by=by, base_label=base_label, numeric=numeric, extra_groups=extra_groups)

# ----------------------------------------------------------------------
# Sidebar — segment + filters (identical filter set on every segment page)
# ----------------------------------------------------------------------
SEGMENT_LABELS = {"Overview": "All", "Overall": "All", "Acceptors": "Acceptor", "Rejectors": "Rejector", "Booked but Cancelled": "Cancelled"}
SEGMENT_ICONS = {"Overview": "🏠", "Overall": "👥", "Acceptors": "✅", "Rejectors": "❌", "Booked but Cancelled": "🚫"}

st.sidebar.markdown(
    "<div style='display:flex;align-items:center;gap:8px;margin-bottom:0.6rem;'>"
    "<div style='display:flex;flex-direction:column;gap:2px;'>"
    "<span style='width:10px;height:10px;border-radius:2px;background:#F7941D;display:block;'></span>"
    "<span style='width:10px;height:10px;border-radius:2px;background:#39B54A;display:block;'></span>"
    "<span style='width:10px;height:10px;border-radius:2px;background:#2E3192;display:block;'></span>"
    "</div>"
    "<span style='font-weight:800;font-size:0.95rem;color:#1A1A1A;'>INFOLEAP</span>"
    "<span style='color:#C8102E;font-weight:800;font-size:0.95rem;'>&times; ROYAL ENFIELD</span>"
    "</div>",
    unsafe_allow_html=True,
)

st.sidebar.markdown("### Segment")
EXTRA_PAGES = ["📊 Model Comparison", "🧠 Verbatim Intelligence (AI)", "⚙️ Settings"]
nav_options = [f"{SEGMENT_ICONS[k]} {k}" for k in SEGMENT_LABELS] + EXTRA_PAGES
nav_choice = st.sidebar.radio("Page", nav_options, label_visibility="collapsed")
segment_nav = nav_choice.split(" ", 1)[1] if nav_choice not in EXTRA_PAGES else nav_choice

if nav_choice in EXTRA_PAGES:
    render_theme_css()
    if "Model Comparison" in nav_choice:
        render_comparison_page(engine)
    elif "Dealership Intelligence" in nav_choice:
        # Inline sidebar filters — these variables don't exist yet (defined after st.stop())
        st.sidebar.markdown("### Report Filters")
        _dl_plat_map = {"All": "All", "350CC": "J Platform (350CC)", "450CC": "K Platform (450CC)", "650CC": "P Platform (650CC)"}
        _dl_platform = st.sidebar.selectbox("Platform (CC)", list(_dl_plat_map.keys()),
                                            format_func=lambda p: _dl_plat_map[p], key="dl_platform")
        _dl_time = st.sidebar.radio("Time", ["All Months", "Month Range"], label_visibility="collapsed", key="dl_time")
        _dl_mo = engine.month_order
        _dl_short = [m.split("'")[0][:3] + "'" + m.split("'")[1][2:] for m in _dl_mo]
        if _dl_time == "Month Range":
            _dl_lo, _dl_hi = st.sidebar.select_slider("Month range", options=_dl_short,
                                                       value=(_dl_short[0], _dl_short[-1]), key="dl_month_range")
            _dl_months = _dl_mo[_dl_short.index(_dl_lo):_dl_short.index(_dl_hi) + 1]
        else:
            _dl_months = _dl_mo
        _dl_seg_dfs = {}
        for _dl_lbl, _dl_seg in [("Acceptors", "Acceptor"), ("Rejectors", "Rejector"), ("Cancelled", "Cancelled")]:
            _dl_df = engine.filter_df(segment=_dl_seg,
                                      platform=_dl_platform if _dl_platform != "All" else None)
            _dl_df = _dl_df[_dl_df['month_label'].isin(set(_dl_months))]
            _dl_seg_dfs[_dl_lbl] = _dl_df
        render_dealership_page(engine, _dl_seg_dfs, list(_dl_months))
    elif "Product Feature Ratings" in nav_choice:
        st.sidebar.markdown("### Report Filters")
        _pf_time = st.sidebar.radio("Time", ["All Months", "Month Range"],
                                    label_visibility="collapsed", key="pf_time")
        _pf_mo = engine.month_order
        _pf_short = [m.split("'")[0][:3] + "'" + m.split("'")[1][2:] for m in _pf_mo]
        if _pf_time == "Month Range":
            _pf_lo, _pf_hi = st.sidebar.select_slider(
                "Month range", options=_pf_short,
                value=(_pf_short[0], _pf_short[-1]), key="pf_month_range"
            )
            _pf_months = _pf_mo[_pf_short.index(_pf_lo):_pf_short.index(_pf_hi) + 1]
        else:
            _pf_months = _pf_mo
        _pf_seg_dfs = {}
        for _pf_lbl, _pf_seg in [("Acceptors", "Acceptor"), ("Rejectors", "Rejector"), ("Cancelled", "Cancelled")]:
            _pf_df = engine.filter_df(segment=_pf_seg)
            _pf_df = _pf_df[_pf_df['month_label'].isin(set(_pf_months))]
            _pf_seg_dfs[_pf_lbl] = _pf_df
        render_product_features_page(engine, _pf_seg_dfs, list(_pf_months))
    elif "Settings" in nav_choice:
        render_settings_page()
    else:
        # Bug fix: `platform`/`model` (the main sidebar filters) aren't
        # defined until after this EXTRA_PAGES block's st.stop() below —
        # referencing them here always raised NameError the moment anyone
        # opened this page. Verbatim Intelligence gets its own small
        # inline Platform/Model selectors instead (same pattern already
        # used above for Dealership Intelligence / Product Feature
        # Ratings), rather than depending on state that doesn't exist yet.
        st.sidebar.markdown("### Report Filters")
        _vi_plat_map = {"All": "All", "350CC": "J Platform (350CC)", "450CC": "K Platform (450CC)", "650CC": "P Platform (650CC)"}
        _vi_platform = st.sidebar.selectbox("Platform (CC)", list(_vi_plat_map.keys()),
                                             format_func=lambda p: _vi_plat_map[p], key="vi_platform")
        _vi_model_options = ["All"]
        if _vi_platform != "All":
            _vi_model_options += sorted(RE_MODEL_LABELS[code] for code, plat in RE_MODEL_PLATFORM.items() if plat == _vi_platform)
        _vi_model = st.sidebar.selectbox("Model", _vi_model_options, key="vi_model")
        render_verbatim_intelligence_page(engine, platform=_vi_platform, re_model=_vi_model)
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
st.markdown(
    f"<div style='height:3px;border-radius:0 2px 2px 0;margin-bottom:0.75rem;"
    f"background:linear-gradient(90deg,{_stripe_color} 0%,{_stripe_color} 55%,rgba(200,16,46,0.10) 100%);'></div>"
    f"<h1 style='margin-top:0;'>Royal Enfield Digital Showroom{_seg_badge}</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:0.3rem;'>"
    f"<span style='color:#7A7670;font-size:0.85rem;'>Intelligence Portal &mdash; built by Infoleap for Royal Enfield</span>"
    f"<span style='color:#9A958D;font-size:0.78rem;'>{_freshness}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

_reset_col, _reset_lbl = st.sidebar.columns([1, 2])
_reset_lbl.markdown("### Report Filters")
if _reset_col.button("↺ Reset", key="reset_filters", help="Clear all filters to defaults"):
    for _k in ["platform_filter", "model_filter", "time_mode", "month_range", "quarters",
               "custom_years", "custom_months", "custom_col_label"]:
        st.session_state.pop(_k, None)
    # Clear table cache so next render recomputes with fresh filters
    for _k in list(st.session_state.keys()):
        if _k.startswith("_tbl_"):
            del st.session_state[_k]
    st.rerun()

# Live site names these "J Platform (350CC)" / "K Platform (450CC)" /
# "P Platform (650CC)" (confirmed via the scraped tab keys) — display labels
# match that, while the underlying filter value stays the plain "350CC" etc.
# that RE_MODEL_PLATFORM/filter_df already key off of.
PLATFORM_DISPLAY = {
    "All": "All", "350CC": "J Platform (350CC)",
    "450CC": "K Platform (450CC)", "650CC": "P Platform (650CC)",
}
platform = st.sidebar.selectbox("Platform (CC)", ["All", "350CC", "450CC", "650CC"],
                                  format_func=lambda p: PLATFORM_DISPLAY[p],
                                  key="platform_filter")

model_options = ["All"]
if platform != "All":
    model_options += sorted(RE_MODEL_LABELS[code] for code, plat in RE_MODEL_PLATFORM.items() if plat == platform)
model = st.sidebar.selectbox("Model", model_options, key="model_filter")

st.sidebar.markdown("### Time Period")
time_mode = st.sidebar.radio("View by", ["All Months", "Month Range", "Quarter (Financial Calendar)"], label_visibility="collapsed", key="time_mode")

MONTH_ORDER = engine.month_order
FY_QUARTER_ORDER = engine.fy_quarter_order
month_short = [m.split("'")[0][:3] + "'" + m.split("'")[1][2:] for m in MONTH_ORDER]
selected_months = MONTH_ORDER
if time_mode == "Month Range":
    lo, hi = st.sidebar.select_slider("Month range", options=month_short, value=(month_short[0], month_short[-1]), key="month_range")
    lo_i, hi_i = month_short.index(lo), month_short.index(hi)
    selected_months = MONTH_ORDER[lo_i:hi_i + 1]
elif time_mode == "Quarter (Financial Calendar)":
    quarters = st.sidebar.multiselect("Quarter (Apr-Mar FY)", FY_QUARTER_ORDER, default=FY_QUARTER_ORDER, key="quarters")
    selected_months = [m for m in MONTH_ORDER if month_label_to_fy_quarter(m) in quarters]

# Removed per explicit user request ("remove the quarter combined column
# it was not something that i asked for") — the table builders still know
# how to compute these (quarter_combined_groups()), but this flag being
# False means _trim_to_selected_months() always strips them out, same as
# the toggle being off.
show_quarter_cols = False

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

show_sig = st.sidebar.toggle("Significance vs Rest of Sample (95%/90%)", value=True,
                              help="Marks each category as significantly higher than the OTHER segments combined (e.g. Acceptor vs Rejector+Cancelled) — a true 'this group vs the rest' test, not diluted by including the group in its own baseline.")
# Per user request: no user-facing 95%/90% or Both/High/Low controls —
# always show both confidence tiers together, and always positive-only
# (significantly HIGHER only, never lower). filter_sig_markers() already
# handles "High only" by dropping the ▼/▽ markers at the single choke
# point every chart/table call site routes through — no other code needed.
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
    model_code = next(c for c, n in RE_MODEL_LABELS.items() if n == model)

df = engine.filter_df(segment=segment_value, platform=platform, model_code=model_code)
df = df[df['month_label'].isin(selected_months)]

# BUG FIX: baseline used to be the full unfiltered population, which
# INCLUDES the current segment inside itself — comparing Acceptor against
# "everyone, including all Acceptors" dilutes the true difference and is
# not a clean, unbiased comparison. Per user feedback ("significance test
# engine is still not running correctly... unbiased narrative"), the
# baseline for a specific segment is now the OTHER segments combined
# (e.g. Acceptor vs Rejector+Cancelled) — a real "this group vs the rest"
# test.
#
# REAL BUG FOUND (2026-06-19, "overall page not highlighting significant
# values"): on Overview, this used to re-apply the SAME platform/model
# filters to the baseline as the main view — meaning baseline_df was
# IDENTICAL to df whenever segment_value=="All", so nothing could ever be
# significant there even with a Model filter active (e.g. "Bullet 350
# buyers" had no "everyone" to compare against). Fixed: Overview's baseline
# is now the genuinely unfiltered FULL population (no platform/model
# filters at all), so picking a Model on Overview can show how that
# slice differs from everyone. With no filters active at all, baseline
# trivially still equals df (whole population) — correctly shows nothing
# significant, since there's truly nothing to compare against, not a bug.
if segment_value == "All":
    baseline_df = engine.filter_df()
else:
    other_segments = [s for s in ("Acceptor", "Rejector", "Cancelled") if s != segment_value]
    everyone = engine.filter_df(platform=platform, model_code=model_code)
    baseline_df = everyone[everyone['segment'].isin(other_segments)]
baseline_df = baseline_df[baseline_df['month_label'].isin(selected_months)]
base_n = len(df)

# Pre-compute one filtered df per segment for the cross-segment comparison
# bar — same platform/model filter, ALL months (not just selected window)
# so the "All periods" comparison is unaffected by time-period picker.
_seg_label_map = {"All": "Overview", "Acceptor": "Acceptors", "Rejector": "Rejectors", "Cancelled": "Cancelled"}
_seg_dfs = {}
for _seg in ("All", "Acceptor", "Rejector", "Cancelled"):
    _sdf = engine.filter_df(segment=_seg, platform=platform, model_code=model_code)
    _sdf = _sdf[_sdf['month_label'].isin(selected_months)]
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
if base_n == 0:
    st.warning(
        f"No respondents match this combination: Segment={segment_nav}, Platform={platform}, "
        f"Model={model}, Time={time_mode}. Try widening one of the filters in the sidebar "
        "— most commonly the Model filter holds a selection from a different segment that doesn't exist here."
    )
    st.stop()

total_n = len(engine.df)
age_quick = engine.age_table(df, base_label=segment_value, numeric=True)
top_age_row = age_quick.iloc[1:].loc[age_quick.iloc[1:]['All'].astype(float).idxmax()]
income_quick = engine.household_income_table(df, base_label=segment_value, numeric=True)
top_income_row = income_quick.iloc[1:].loc[income_quick.iloc[1:]['All'].astype(float).idxmax()]
tob_quick = engine.type_of_buyer_table(df, base_label=segment_value, numeric=True)
top_tob_row = tob_quick.iloc[1:].loc[tob_quick.iloc[1:]['All'].astype(float).idxmax()]
_TOB_SHORT = {
    "This is my Additional 2W": "Additional 2W",
    "This is my Replaced 2W": "Replaced 2W",
    "First Time Buyer of 2W(No one owns a 2W)": "First-Time Buyer",
    "First Time Buyer of 2W(Family owns a 2W and not a primary user)": "First-Time Buyer",
    "First Time Buyer of 2W (No one owns a 2W)": "First-Time Buyer",
    "First Time Buyer of 2W (Family owns a 2W and not a primary user)": "First-Time Buyer",
}
tob_display = _TOB_SHORT.get(top_tob_row['Unnamed: 0'], top_tob_row['Unnamed: 0'])
seg_pct = base_n / total_n * 100

# Delta vs total (overall) for each stat chip — shown as "+Xpp" or "-Xpp"
_chip_deltas = {}
_overall_df_chip = _seg_dfs.get("Overview")
if _overall_df_chip is not None and segment_value not in ("All",):
    try:
        _ov_age = engine.age_table(_overall_df_chip, base_label="All", numeric=True)
        _ov_age_row = _ov_age[_ov_age['Unnamed: 0'] == top_age_row['Unnamed: 0']]
        if len(_ov_age_row):
            _chip_deltas['age'] = float(top_age_row['All']) - float(_ov_age_row.iloc[0]['All'])
    except Exception:
        pass
    try:
        _ov_inc = engine.household_income_table(_overall_df_chip, base_label="All", numeric=True)
        _ov_inc_row = _ov_inc[_ov_inc['Unnamed: 0'] == top_income_row['Unnamed: 0']]
        if len(_ov_inc_row):
            _chip_deltas['income'] = float(top_income_row['All']) - float(_ov_inc_row.iloc[0]['All'])
    except Exception:
        pass
    try:
        _ov_tob = engine.type_of_buyer_table(_overall_df_chip, base_label="All", numeric=True)
        _ov_tob_row = _ov_tob[_ov_tob['Unnamed: 0'] == top_tob_row['Unnamed: 0']]
        if len(_ov_tob_row):
            _chip_deltas['tob'] = float(top_tob_row['All']) - float(_ov_tob_row.iloc[0]['All'])
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
    # Overview page: replaced entirely with the static PPT-sourced narrative
    # (objectives + methodology + sample achieved) per 2026-07-22 client
    # request — the old hero cards / pie summary / comparison charts /
    # insight blocks below are all Overview-only and never reached because
    # of the st.stop() here.
    render_overview_intro()
    st.stop()

else:
    # P3 + P6: Segment identity hero — colored anchor card + 3 profile stat cards + 1 segment-specific card
    _card4_html = ""
    try:
        if segment_value == "Acceptor" and 're_model_code' in df.columns:
            _acc_codes = df['re_model_code'].dropna()
            if not _acc_codes.empty:
                from utils.data_engine import RE_MODEL_LABELS
                _top_code = _acc_codes.mode().iloc[0]
                _t_m_name = RE_MODEL_LABELS.get(_top_code, f"Model {int(_top_code)}").replace("Royal Enfield ", "")
                _t_m_pct = (_acc_codes == _top_code).sum() / len(_acc_codes) * 100
                _card4_html = (
                    f"<div style='flex:1;min-width:120px;background:#fff;border:1px solid #ECE9E4;border-radius:12px;padding:14px 16px;'>"
                    f"<div style='font-size:10px;text-transform:uppercase;letter-spacing:0.06em;color:#9A958D;font-weight:600;'>Top RE Model</div>"
                    f"<div style='font-size:0.88rem;font-weight:700;color:#1A1A1A;margin-top:5px;line-height:1.3;'>{_t_m_name}</div>"
                    f"<div style='display:flex;align-items:baseline;margin-top:4px;'>"
                    f"<span style='font-size:1.6rem;font-weight:800;color:{accent};line-height:1;'>{_t_m_pct:.0f}%</span></div>"
                    f"{_mini_bar(_t_m_pct, accent)}"
                    f"<div style='font-size:0.7rem;color:#9A958D;margin-top:5px;'>of segment</div></div>"
                )
        elif segment_value == "Rejector" and 'owned_manufacturer' in df.columns:
            _mfr_counts = df['owned_manufacturer'].dropna().value_counts()
            _non_re = _mfr_counts[~_mfr_counts.index.str.contains("Royal Enfield", case=False, na=False)]
            if not _non_re.empty:
                _t_comp = _non_re.index[0]
                _t_comp_pct = _non_re.iloc[0] / len(df) * 100
                _card4_html = (
                    f"<div style='flex:1;min-width:120px;background:#fff;border:1px solid #ECE9E4;border-radius:12px;padding:14px 16px;'>"
                    f"<div style='font-size:10px;text-transform:uppercase;letter-spacing:0.06em;color:#9A958D;font-weight:600;'>Top Competitor</div>"
                    f"<div style='font-size:0.88rem;font-weight:700;color:#1A1A1A;margin-top:5px;line-height:1.3;'>{_t_comp}</div>"
                    f"<div style='display:flex;align-items:baseline;margin-top:4px;'>"
                    f"<span style='font-size:1.6rem;font-weight:800;color:{accent};line-height:1;'>{_t_comp_pct:.0f}%</span></div>"
                    f"{_mini_bar(_t_comp_pct, accent)}"
                    f"<div style='font-size:0.7rem;color:#9A958D;margin-top:5px;'>of segment</div></div>"
                )
        elif segment_value == "Cancelled" and 'aq1b' in df.columns:
            _still_n = (df['aq1b'] == 3.0).sum()
            _still_base = df['aq1b'].dropna().shape[0]
            if _still_base > 0:
                _still_pct = _still_n / _still_base * 100
                _card4_html = (
                    f"<div style='flex:1;min-width:120px;background:#fff;border:1px solid #ECE9E4;border-radius:12px;padding:14px 16px;'>"
                    f"<div style='font-size:10px;text-transform:uppercase;letter-spacing:0.06em;color:#9A958D;font-weight:600;'>Still Searching</div>"
                    f"<div style='font-size:0.88rem;font-weight:700;color:#1A1A1A;margin-top:5px;line-height:1.3;'>Win-Back Opportunity</div>"
                    f"<div style='display:flex;align-items:baseline;margin-top:4px;'>"
                    f"<span style='font-size:1.6rem;font-weight:800;color:{accent};line-height:1;'>{_still_pct:.0f}%</span></div>"
                    f"{_mini_bar(_still_pct, accent)}"
                    f"<div style='font-size:0.7rem;color:#9A958D;margin-top:5px;'>of cancelled bookers</div></div>"
                )
    except Exception:
        _card4_html = ""

    st.markdown(
        f"<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:1rem;align-items:stretch;'>"
        f"<div style='flex:1.8;min-width:200px;background:{accent}0D;"
        f"border:1.5px solid {accent}40;border-left:5px solid {accent};"
        f"border-radius:12px;padding:16px 20px;'>"
        f"<div style='font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:{accent};font-weight:700;margin-bottom:6px;'>Active Segment</div>"
        f"<div style='font-size:2.2rem;font-weight:800;color:{accent};font-family:Oswald,sans-serif;line-height:1;'>{segment_nav.upper()}</div>"
        f"<div style='font-size:0.95rem;font-weight:700;color:#1A1A1A;margin-top:6px;'>"
        f"{base_n:,} respondents &nbsp;·&nbsp; <span style='color:#7A7670;font-weight:500;'>{seg_pct:.0f}% of {total_n:,} total</span>"
        f"</div>"
        f"<div style='font-size:0.82rem;color:#4A4644;margin-top:8px;line-height:1.5;'>{_frame_text}</div>"
        f"</div>"
        f"<div style='flex:1;min-width:120px;background:#fff;border:1px solid #ECE9E4;border-radius:12px;padding:14px 16px;'>"
        f"<div style='font-size:10px;text-transform:uppercase;letter-spacing:0.06em;color:#9A958D;font-weight:600;'>Top Age</div>"
        f"<div style='font-size:0.88rem;font-weight:700;color:#1A1A1A;margin-top:5px;line-height:1.3;'>{top_age_row['Unnamed: 0']}</div>"
        f"<div style='display:flex;align-items:baseline;margin-top:4px;'>"
        f"<span style='font-size:1.6rem;font-weight:800;color:{accent};line-height:1;'>{float(top_age_row['All']):.0f}%</span>"
        f"{_delta_badge(_chip_deltas.get('age'))}</div>"
        f"{_mini_bar(float(top_age_row['All']), accent)}"
        f"<div style='font-size:0.7rem;color:#9A958D;margin-top:5px;'>of segment &nbsp;·&nbsp; n≈{round(base_n*float(top_age_row['All'])/100):,}</div>"
        f"</div>"
        f"<div style='flex:1;min-width:120px;background:#fff;border:1px solid #ECE9E4;border-radius:12px;padding:14px 16px;'>"
        f"<div style='font-size:10px;text-transform:uppercase;letter-spacing:0.06em;color:#9A958D;font-weight:600;'>Top Income</div>"
        f"<div style='font-size:0.88rem;font-weight:700;color:#1A1A1A;margin-top:5px;line-height:1.3;'>{top_income_row['Unnamed: 0']}</div>"
        f"<div style='display:flex;align-items:baseline;margin-top:4px;'>"
        f"<span style='font-size:1.6rem;font-weight:800;color:{accent};line-height:1;'>{float(top_income_row['All']):.0f}%</span>"
        f"{_delta_badge(_chip_deltas.get('income'))}</div>"
        f"{_mini_bar(float(top_income_row['All']), accent)}"
        f"<div style='font-size:0.7rem;color:#9A958D;margin-top:5px;'>of segment &nbsp;·&nbsp; n≈{round(base_n*float(top_income_row['All'])/100):,}</div>"
        f"</div>"
        f"<div style='flex:1;min-width:120px;background:#fff;border:1px solid #ECE9E4;border-radius:12px;padding:14px 16px;'>"
        f"<div style='font-size:10px;text-transform:uppercase;letter-spacing:0.06em;color:#9A958D;font-weight:600;'>Buyer Type</div>"
        f"<div style='font-size:0.88rem;font-weight:700;color:#1A1A1A;margin-top:5px;line-height:1.3;'>{tob_display}</div>"
        f"<div style='display:flex;align-items:baseline;margin-top:4px;'>"
        f"<span style='font-size:1.6rem;font-weight:800;color:{accent};line-height:1;'>{float(top_tob_row['All']):.0f}%</span>"
        f"{_delta_badge(_chip_deltas.get('tob'))}</div>"
        f"{_mini_bar(float(top_tob_row['All']), accent)}"
        f"<div style='font-size:0.7rem;color:#9A958D;margin-top:5px;'>of segment &nbsp;·&nbsp; n≈{round(base_n*float(top_tob_row['All'])/100):,}</div>"
        f"</div>"
        f"{_card4_html}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Each chip = the single largest category in this segment for that question, out of the full filtered "
        "base above. The colored badge (+Xpp/-Xpp) compares that category's % here vs. the same category in the "
        "**overall sample** (same platform/model filters, no segment restriction) — green ≥+2pp, red ≤-2pp, "
        "grey = within 2 points (not a meaningful gap). Higher isn't automatically 'good': read it against what "
        "this segment is (e.g. a high First-Time-Buyer share is good context for Acceptors, a warning sign for Rejectors)."
    )

ai_facts = {
    "segment": segment_nav, "base_n": int(base_n), "total_n": int(total_n),
    "filters": {"platform": platform, "model": model, "time_period": time_mode},
    "top_age_group": {"label": top_age_row['Unnamed: 0'], "pct": round(float(top_age_row['All']), 1)},
    "top_income_bracket": {"label": top_income_row['Unnamed: 0'], "pct": round(float(top_income_row['All']), 1)},
    "top_buyer_type": {"label": top_tob_row['Unnamed: 0'], "pct": round(float(top_tob_row['All']), 1)},
}

regen_key = f"regen_nonce_{segment_nav}"
st.session_state.setdefault(regen_key, 0)
_ai_col, _regen_col = st.columns([5, 1])
with _ai_col:
    render_ai_summary_button(ai_facts, key=f"{segment_nav}_{platform}_{model}_{time_mode}")
with _regen_col:
    st.markdown("<div style='margin-top:0.35rem'></div>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", key=f"regen_btn_{segment_nav}", help="Regenerate all AI chart insights on this page", type="secondary"):
        st.session_state[regen_key] += 1
        st.rerun()

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
if _overview_is_comparison:
    st.markdown(
        f"<div id='jump-nav-bar' style='display:flex;gap:8px;flex-wrap:wrap;margin:0.6rem 0 1.4rem;"
        f"position:sticky;top:3.2rem;z-index:90;background:rgba(250,250,248,0.96);"
        f"backdrop-filter:blur(6px);padding:6px 0 8px;margin-left:-0.5rem;padding-left:0.5rem;'>"
        + _nav_pill("Demographics", "sec-demographics")
        + _nav_pill("Buyer Type", "sec-buyer-type")
        + _nav_pill("Additional & Replaced", "sec-addrepl")
        + "</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"<div id='jump-nav-bar' style='display:flex;gap:8px;flex-wrap:wrap;margin:0.6rem 0 1.4rem;"
        f"position:sticky;top:3.2rem;z-index:90;background:rgba(250,250,248,0.96);"
        f"backdrop-filter:blur(6px);padding:6px 0 8px;margin-left:-0.5rem;padding-left:0.5rem;'>"
        + _nav_pill("Demographics", "sec-demographics")
        + _nav_pill("Buyer Type", "sec-buyer-type")
        + _nav_pill("Additional & Replaced", "sec-addrepl")
        # Brand Owned / Brand Considered pills dropped — their sections are
        # hidden (SHOW_BRAND_OWNED_ONWARD = False above); pills would dead-link.
        + _nav_pill("Month Trend", "sec-trend")
        + "</div>",
        unsafe_allow_html=True,
    )

# Active-pill scroll observer (same-origin iframe → parent DOM)
_components.html(
    f"""<script>
(function(){{
  var ac='{accent}';
  var secs=['sec-demographics','sec-buyer-type','sec-addrepl','sec-trend'];
  function activate(id){{
    var pdoc=window.parent.document;
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
    var pdoc=window.parent.document;
    var obs=new IntersectionObserver(function(entries){{
      entries.forEach(function(e){{if(e.isIntersecting)activate(e.target.id);}});
    }},{{threshold:0.1,rootMargin:'-60px 0px -60% 0px'}});
    secs.forEach(function(id){{var el=pdoc.getElementById(id);if(el)obs.observe(el);}});
  }}
  setTimeout(init,1200);
}})();
</script>""",
    height=0,
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

    # Block E — Segment Monthly Trend (Issue O2 — was completely absent)
    _trend_months = [m for m in engine.month_order if m in selected_months]
    if len(_trend_months) >= 2 and len(_seg_dfs) >= 2:
        _trend_fig = segment_trend_chart(_seg_dfs, _trend_months)
        if _trend_fig:
            with st.container(border=True):
                st.markdown("#### Monthly Trend — Respondents per Segment")
                st.caption("How each segment's monthly respondent count has moved across the study period. Accepts = respondents who bought RE; Rejectors = chose competitor; Cancelled = booked then cancelled.")
                st.altair_chart(_trend_fig, use_container_width=True)

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
                            text=[f"{v:.1f}%" for v in _bom_data['_pct']],
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
            _PLAT_LABELS = {"350CC": "J Platform (350CC)", "450CC": "K Platform (450CC)", "650CC": "P Platform (650CC)"}
            for _mc, _ml in RE_MODEL_LABELS.items():
                _ma = _tbl_filter("Acceptor", _mar_plat, _mc, _months_t)
                _mr = _tbl_filter("Rejector", _mar_plat, _mc, _months_t)
                _mca = _tbl_filter("Cancelled", _mar_plat, _mc, _months_t)
                _mall = _pd.concat([_ma, _mr, _mca]).drop_duplicates()
                _mt_unique = max(len(_mall), 1)
                if _mt_unique >= 30:
                    _mar_rows.append({
                        "model": _ml.replace("Royal Enfield ", ""),
                        "platform": _PLAT_LABELS.get(RE_MODEL_PLATFORM.get(_mc, "350CC"), "Other"),
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
    if time_mode == "All Months":
        if show_quarter_cols:
            cols = list(tbl.columns)
        else:
            quarter_cols = set(engine.quarter_combined_groups().keys())
            cols = [c for c in tbl.columns if c not in quarter_cols]
    else:
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


def section(title, table_fn, caption=None, chart_type="bar", cap_chart=None, brand_filter_labels=None, color=None):
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
    _ck = f"_tbl_{title}_{segment_value}_{platform}_{model}_{time_mode}_{','.join(sorted(selected_months))}"
    if _ck not in st.session_state:
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
    sig_cols = selected_months + (list(engine.quarter_combined_groups().keys()) if show_quarter_cols else []) + ([custom_col_name] if custom_col_name else [])
    col_markers = compare_to_baseline_by_column(tbl, baseline_tbl, sig_cols, confidence=sig_confidence) if show_sig else None
    col_markers = filter_sig_markers(col_markers, sig_direction)
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
            # Monthly trend: hidden on Overview (comparison IS the view), shown as expander on segment pages.
            if segment_value != "All":
                with st.expander("📈 Monthly Trend", expanded=False):
                    render_chart_with_table(chart_tbl, title, color=(color or accent), key=f"chart_{title}", chart_type=chart_type, col_sig_markers=col_markers, table_df_html=tbl, rollup_labels=rollup_set, highlight_col=custom_col_name)
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
            render_chart_with_table(chart_tbl, title, color=(color or accent), key=f"chart_{title}", chart_type=chart_type, col_sig_markers=col_markers, table_df_html=tbl, rollup_labels=rollup_set, highlight_col=custom_col_name)
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
        chart_facts = {
            "chart": title, "segment": segment_nav, "base_n": int(tbl.iloc[0]['All']),
            "filters": {"platform": platform, "model": model},
            "time_period": time_mode, "months_included": selected_months,
            "top_category": {"label": top_row['Unnamed: 0'], "pct": round(float(top_row['All']), 1)},
            "significant_vs_rest_of_sample": sig_hits,
            "_regen": st.session_state.get(regen_key, 0),
        }
        if not _overview_is_comparison:
            render_chart_ai_blurb(chart_facts, key=f"aiblurb_{title}_{segment_value}_{platform}_{model}_{time_mode}")
    trend_map[title] = tbl


def brand_wise_section(title, table_fn, color, caption=None):
    """Bespoke renderer for the three brand-wise tables (Additional+Replaced/
    Brand Owned/Brand Considered) — per user request: CC-wise chart goes
    ABOVE this section (caller's responsibility, see layout below), and
    THIS section shows a brand-ROLLUP-only comparison bar on top, then the
    full member-level table below it sorted descending with the 'Other'
    catch-all pinned to the very end — replacing the earlier capped
    treemap approach. Each of the three sections gets its own distinct
    color (passed in), not the segment's shared accent."""
    _ck = f"_tbl_{title}_{segment_value}_{platform}_{model}_{time_mode}_{','.join(sorted(selected_months))}"
    if _ck not in st.session_state:
        st.session_state[_ck] = _trim_to_selected_months(table_fn(df, segment_value))
        st.session_state[_ck + "_b"] = _trim_to_selected_months(table_fn(baseline_df, "All"))
    tbl = st.session_state[_ck]
    baseline_tbl = st.session_state[_ck + "_b"]
    rollup_set = set(ROLLUP_LABELS)
    selected = st.multiselect(f"Brands shown in '{title}'", ROLLUP_LABELS, default=ROLLUP_LABELS, key=f"brandfilter_{title}")
    tbl = _filter_brand_table(tbl, selected, rollup_set)
    baseline_tbl = _filter_brand_table(baseline_tbl, selected, rollup_set)

    if len(tbl) <= 1:
        st.info(f"{title}: no brands selected.")
        return

    # Per explicit user instruction: significance NEVER runs on the
    # aggregate 'All' column, anywhere — only on individual month columns
    # (and the quarter-combined columns, same rule, same n>=30 gate —
    # their base is always well over 30 so they're virtually always
    # eligible when shown).
    sig_cols = selected_months + (list(engine.quarter_combined_groups().keys()) if show_quarter_cols else []) + ([custom_col_name] if custom_col_name else [])
    col_markers = compare_to_baseline_by_column(tbl, baseline_tbl, sig_cols, confidence=sig_confidence) if show_sig else None
    col_markers = filter_sig_markers(col_markers, sig_direction)

    sorted_tbl = engine.sort_brand_table(tbl, rollup_set)
    rollup_tbl = engine.rollup_only_table(tbl, rollup_set)

    # col_markers is positional against tbl's ORIGINAL row order;
    # sort_brand_table reorders rows by value, so realign by label before
    # rendering the sorted table — a position-only permutation would attach
    # the wrong marker to the wrong row.
    orig_labels = tbl.iloc[1:]['Unnamed: 0'].tolist()
    label_order = sorted_tbl.iloc[1:]['Unnamed: 0'].tolist()
    sorted_col_markers = None
    if col_markers:
        sorted_col_markers = {}
        for col, mk in col_markers.items():
            m_by_label = dict(zip(orig_labels, mk))
            sorted_col_markers[col] = [m_by_label.get(l, '') for l in label_order]

    with st.container(border=True):
        if caption:
            st.caption(caption)
        # Per user request: one consistent chart shape AND layout across
        # every section — stacked bar with its table directly below (not
        # tucked into a collapsed expander like this used to do, unlike
        # every plain section() call elsewhere on the page).
        render_chart_with_table(rollup_tbl, title, color=color, key=f"chart_{title}",
                                 chart_type="stacked_bar", col_sig_markers=sorted_col_markers,
                                 table_df_html=sorted_tbl, rollup_labels=rollup_set, highlight_col=custom_col_name)
        cat_rows = sorted_tbl.iloc[1:]
        top_row = cat_rows.loc[cat_rows['All'].astype(float).idxmax()]
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
        chart_facts = {
            "chart": title, "segment": segment_nav, "base_n": int(tbl.iloc[0]['All']),
            "filters": {"platform": platform, "model": model},
            "time_period": time_mode, "months_included": selected_months,
            "top_category": {"label": top_row['Unnamed: 0'], "pct": round(float(top_row['All']), 1)},
            "significant_vs_rest_of_sample": sig_hits,
            "_regen": st.session_state.get(regen_key, 0),
        }
        if not _overview_is_comparison:
            render_chart_ai_blurb(chart_facts, key=f"aiblurb_{title}_{segment_value}_{platform}_{model}_{time_mode}")
    trend_map[title] = sorted_tbl


def reasons_placeholder(label, segment_hint):
    with st.container(border=True):
        st.markdown(f"**{label}**")
        st.info(
            f"No coded source exists for {label} in the data provided — the live site's categories here are "
            "AI-clustered output over open-ended verbatim text (confirmed against the raw `mq2`/`mq3` columns and "
            "Infoleap's own spec note 'will provide codelist and Data later'). See **Verbatim Intelligence (AI)** "
            f"in the sidebar for an AI-driven intent analysis of {segment_hint}'s verbatims instead — a different "
            "but genuinely useful treatment of the same open-ended data. Full investigation in docs/DATA_FIELD_MAPPING.md."
        )


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
section("Age", lambda d, s: _tbl_age(d, base_label=s, numeric=True, extra_groups=custom_group), chart_type="stacked_bar")
section("Education", lambda d, s: _tbl_education(d, base_label=s, numeric=True, extra_groups=custom_group), chart_type="stacked_bar")
section("Occupation", lambda d, s: _tbl_occupation(d, base_label=s, numeric=True, extra_groups=custom_group), chart_type="stacked_bar")
section("Household Income", lambda d, s: _tbl_income(d, base_label=s, numeric=True, extra_groups=custom_group), chart_type="stacked_bar")

st.markdown('<div id="sec-buyer-type"></div>', unsafe_allow_html=True)
st.markdown("### Type of Buyer")
st.caption("Was this purchase an additional bike, a replacement, or a first-time 2W purchase? This shapes the entire decision context.")
section("Type of Buyer", lambda d, s: _tbl_type_of_buyer(d, base_label=s, numeric=True, extra_groups=custom_group), chart_type="stacked_bar")

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
if segment_value == "Acceptor":
    st.markdown('<div id="sec-addrepl"></div>', unsafe_allow_html=True)
    st.markdown("### Additional + Replaced")
    st.caption("What did these respondents own before this purchase? CC-wise breakdown of the bike being added or replaced.")
    section("Additional + Replaced — CC Wise",
            lambda d, s: engine.additional_replaced_table(d, by="cc", base_label=s, numeric=True, extra_groups=custom_group),
            color=ADD_REPL_COLOR, chart_type="stacked_bar")
    if not _overview_is_comparison:
        brand_wise_section("Additional + Replaced — Brand Wise",
                            lambda d, s: engine.additional_replaced_table(d, by="brand", base_label=s, numeric=True, extra_groups=custom_group),
                            color=ADD_REPL_COLOR)

if segment_value in ("Rejector", "Cancelled"):
    st.markdown('<div id="sec-brand-owned"></div>', unsafe_allow_html=True)
    st.markdown("### Brand Owned")
    # Acceptors trivially own RE (they just bought one) — use baseline_df (all owners:
    # Rej∪BBC-confirmed∪Acc) so competitor bikes appear, matching the live site (base ~2938).
    _bo_df = baseline_df if segment_value == "Acceptor" else df
    _bo_label = "All Owners" if segment_value == "Acceptor" else segment_value
    _bo_caption = ("Bike ownership across all respondents — Acceptors' new RE purchase aside, "
                   "what bikes do people in the study already ride?" if segment_value == "Acceptor"
                   else "Current bike ownership — what brand and CC segment does this respondent already ride?")
    st.caption(_bo_caption)
    section("Brand Owned — CC Wise",
            lambda d, s, _df=_bo_df, _lbl=_bo_label: engine.brand_owned_table(_df, by="cc", base_label=_lbl, numeric=True, extra_groups=custom_group),
            color=BRAND_OWNED_COLOR, chart_type="stacked_bar")
    if not _overview_is_comparison:
        brand_wise_section("Brand Owned — Brand Wise",
                            lambda d, s, _df=_bo_df, _lbl=_bo_label: engine.brand_owned_table(_df, by="brand", base_label=_lbl, numeric=True, extra_groups=custom_group),
                            color=BRAND_OWNED_COLOR)

# Per user request: brand-wise data (Additional+Replaced/Brand Owned/
# Brand Considered) belongs only to Acceptor/Rejector/Cancelled — never
# on the Overview/"All" page, same scoping as Additional+Replaced and
# Brand Owned above.
if segment_value in ("Acceptor", "Rejector", "Cancelled"):
    st.markdown('<div id="sec-brand-considered"></div>', unsafe_allow_html=True)
    st.markdown("### Brand Considered")
    st.caption("Which other brands did this respondent evaluate before deciding? The competitive set — high overlap with a competitor here means RE is losing comparison battles in that CC segment.")
    section("Brand Considered — CC Wise",
            lambda d, s: engine.brand_considered_table(d, by="cc", base_label=s, numeric=True, extra_groups=custom_group),
            caption="Approximate — see docs/DATA_FIELD_MAPPING.md Addendum 8/9.",
            color=BRAND_CONSIDERED_COLOR, chart_type="stacked_bar")
    brand_wise_section("Brand Considered — Brand Wise",
                        lambda d, s: engine.brand_considered_table(d, by="brand", base_label=s, numeric=True, extra_groups=custom_group),
                        color=BRAND_CONSIDERED_COLOR,
                        caption="Approximate — see docs/DATA_FIELD_MAPPING.md Addendum 8/9.")

# AQ2A — Competitor CC Preference (Rejectors only — most relevant; 84.8% chose 351CC+)
if segment_value == "Rejector":
    st.markdown("### Competitor CC Preference")
    st.caption(
        "AQ2A: CC range of the competitor bike ultimately purchased. "
        "Base = Rejectors who answered (n=1,789). "
        "Shows whether Rejectors traded up, traded sideways, or downgraded vs RE's 350CC core."
    )
    section("Competitor CC Segment — Rejectors",
            lambda d, s: engine.competitor_cc_table(d, base_label=s, numeric=True, extra_groups=custom_group),
            color="#FDCB6E", chart_type="stacked_bar")

# AQ5b — RE Model Consideration Funnel (Rejectors only)
if segment_value == "Rejector":
    st.markdown("### RE Model Consideration Funnel")
    st.caption(
        "AQ5b: 'Which Royal Enfield model did you consider most seriously before choosing a competitor?' "
        "Base = all Rejectors (n=1,789). % = share of total Rejectors who considered each RE model. "
        "Top models sorted by consideration rate."
    )
    section("RE Model Considered — Rejectors",
            lambda d, s: engine.aq5b_table(d, base_label=s, numeric=True, extra_groups=custom_group),
            color="#C8102E", chart_type="stacked_bar")

# Test Ride Intelligence — AQ6: which RE models did respondents test ride?
# Per user report: this was showing on Overall/"All" too, where the live
# site never has it — gated to the 3 real segments only, same pattern as
# Additional+Replaced/Brand Owned/Brand Considered above.
if segment_value in ("Acceptor", "Rejector", "Cancelled"):
    st.markdown("### Test Ride Intelligence")
    st.caption(
        "AQ6: Which Royal Enfield models did you test ride? Multi-select across all 14 RE models. "
        "% = share of segment who test-rode each model. Base = total segment respondents."
    )
    section("Test Ride Rate — RE Models",
            lambda d, s: engine.test_ride_table(d, base_label=s, numeric=True, extra_groups=custom_group),
            color="#0984E3", chart_type="stacked_bar")

# Brand Resilience — AQ5c: "If your preferred brand were unavailable, what would you buy?"
# Only asked to Acceptors (n=140) and Rejectors (n=251) — Cancelled have 0 responses.
if segment_value in ("Acceptor", "Rejector"):
    st.markdown("### Brand Resilience")
    st.caption(
        "AQ5c: 'If your preferred brand/model were unavailable, what would you have bought?' "
        "Measures brand equity lock-in. Base = respondents who answered (not total segment). "
        "Not on live dashboard — additional insight layer."
    )
    section("Brand Resilience — Substitute Choice",
            lambda d, s: engine.brand_resilience_table(d, base_label=s, numeric=True, extra_groups=custom_group),
            color="#6C5CE7", chart_type="stacked_bar")

# Post-Cancellation Trajectory — AQ1B (Cancelled only, n=1,527)
if segment_value == "Cancelled":
    st.markdown("### Post-Cancellation Trajectory")
    st.caption(
        "AQ1B: After cancelling the RE booking, what did you do? "
        "Base = all Cancelled respondents. Not on live dashboard — additional insight layer."
    )
    section("Post-Cancellation Action",
            lambda d, s: engine.post_cancellation_table(d, base_label=s, numeric=True, extra_groups=custom_group),
            color="#E17055", chart_type="stacked_bar")

st.markdown('<div id="sec-reasons"></div>', unsafe_allow_html=True)
st.markdown("### Reasons & Motivations")
# Deterministic, exact reproduction (2026-07-27) via each respondent's own
# assigned netting codes -- see DataEngine.reasons_table() docstring for
# the validation against scraped live-site numbers. Only real for the 3
# single-segment pages; Overview/"All" keeps the placeholder (no reliable
# ground truth for what an all-segments Reasons table should look like).
_REASONS_LABELS = {
    "Cancelled": "Reasons for Cancelling",
    "Rejector": "Reasons for Rejection",
    "Acceptor": "Key Buying Factors",
}
if segment_value in _REASONS_LABELS:
    _reasons_label = _REASONS_LABELS[segment_value]
    st.caption(f"{_reasons_label} — decoded from each respondent's own Infoleap-assigned netting code, matching the live dashboard exactly (not an AI approximation).")
    # Can't use the shared section() helper here -- it always computes a
    # significance-vs-baseline table too, and that baseline (the OTHER
    # segments combined) can span multiple segments at once (e.g.
    # Rejector+Cancelled together). reasons_table() correctly rejects a
    # mixed-segment df -- each segment's Reasons codes come from a
    # DIFFERENT netting sheet/question, so "vs the other segments combined"
    # isn't a coherent comparison for this table the way it is for Age/
    # Education. Render this segment's own table only, no baseline compare.
    for _r_title, _r_by in ((f"{_reasons_label} — Category Wise", "supernet"),
                             (f"{_reasons_label} — Detailed", "net")):
        _r_tbl = _trim_to_selected_months(
            engine.reasons_table(df, base_label=segment_value, by=_r_by, numeric=True, extra_groups=custom_group))
        with st.container(border=True):
            render_chart_with_table(_r_tbl, _r_title, color=REASONS_COLOR, key=f"chart_{_r_title}", chart_type="stacked_bar")
        trend_map[_r_title] = _r_tbl
else:
    reasons_placeholder("Key Buying Factors / Reasons for Rejection / Reasons for Cancelling", "this segment")

if not _overview_is_comparison:
    st.markdown('<div id="sec-trend"></div>', unsafe_allow_html=True)
    st.markdown("### Month-over-Month Trend")
    st.caption("Pick any metric above to see how its category split evolved across the survey period — useful for spotting seasonal shifts or data-collection timing effects.")

    @st.fragment
    def _trend_section():
        trend_table_choice = st.selectbox("Trend for", list(trend_map.keys()))
        st.altair_chart(month_trend_chart(trend_map[trend_table_choice], selected_months), use_container_width=True)

    _trend_section()
