import streamlit as st
from auth import render_login, render_landing
from styles.theme import render_theme_css, SEGMENT_COLORS
from utils.data_engine import DataEngine, RE_MODEL_PLATFORM, RE_MODEL_LABELS, month_label_to_fy_quarter
from utils.visuals import render_chart_with_table, month_trend_chart, stacked_composition_bar, render_sig_legend
from utils.stat_engine import compare_to_baseline_by_column
from utils.compare import render_comparison_page
from utils.verbatim_intel import render_verbatim_intelligence_page
from utils.ai_summary import render_ai_summary_button, render_chart_ai_blurb
from utils.settings_page import render_settings_page

st.set_page_config(page_title="RE Digital Showroom | Infoleap", layout="wide")

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

# ----------------------------------------------------------------------
# Sidebar — segment + filters (identical filter set on every segment page)
# ----------------------------------------------------------------------
SEGMENT_LABELS = {"Overview": "All", "Acceptors": "Acceptor", "Rejectors": "Rejector", "Booked but Cancelled": "Cancelled"}
SEGMENT_ICONS = {"Overview": "🏠", "Acceptors": "✅", "Rejectors": "❌", "Booked but Cancelled": "🚫"}

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
    elif "Settings" in nav_choice:
        render_settings_page()
    else:
        render_verbatim_intelligence_page(engine)
    if st.sidebar.button("Log out"):
        st.session_state["authenticated"] = False
        st.session_state["entered_dashboard"] = False
        st.rerun()
    st.stop()

segment_value = SEGMENT_LABELS[segment_nav]
accent = SEGMENT_COLORS.get(segment_value, SEGMENT_COLORS["All"])
render_theme_css(accent=accent)

st.markdown(
    "<div style='height:4px;border-radius:2px;margin-bottom:0.6rem;"
    "background:linear-gradient(90deg,#C8102E 0%,#C8102E 25%,#F7941D 25%,#F7941D 50%,"
    "#39B54A 50%,#39B54A 75%,#2E3192 75%,#2E3192 100%);'></div>"
    "<h1>Royal Enfield Digital Showroom</h1>",
    unsafe_allow_html=True,
)
st.caption("Intelligence Portal &mdash; built by Infoleap for Royal Enfield", unsafe_allow_html=True)

st.sidebar.markdown("### Report Filters")
# Live site names these "J Platform (350CC)" / "K Platform (450CC)" /
# "P Platform (650CC)" (confirmed via the scraped tab keys) — display labels
# match that, while the underlying filter value stays the plain "350CC" etc.
# that RE_MODEL_PLATFORM/filter_df already key off of.
PLATFORM_DISPLAY = {
    "All": "All", "350CC": "J Platform (350CC)",
    "450CC": "K Platform (450CC)", "650CC": "P Platform (650CC)",
}
platform = st.sidebar.selectbox("Platform (CC)", ["All", "350CC", "450CC", "650CC"],
                                  format_func=lambda p: PLATFORM_DISPLAY[p])

model_options = ["All"]
if platform != "All":
    model_options += sorted(RE_MODEL_LABELS[code] for code, plat in RE_MODEL_PLATFORM.items() if plat == platform)
model = st.sidebar.selectbox("Model", model_options)

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
st.sidebar.markdown("### Custom Combined Column")
_available_years = sorted({m.split("'")[1] for m in MONTH_ORDER})
_available_month_names = list(dict.fromkeys(m.split("'")[0] for m in MONTH_ORDER))
custom_years = st.sidebar.multiselect("Years", _available_years, default=[], key="custom_years")
custom_month_names = st.sidebar.multiselect("Months", _available_month_names, default=[], key="custom_months")
custom_col_name = None
custom_group = {}
if custom_years and custom_month_names:
    custom_months = [m for m in MONTH_ORDER if m.split("'")[0] in custom_month_names and m.split("'")[1] in custom_years]
    if custom_months:
        custom_label_input = st.sidebar.text_input("Combined column name", value="Custom Combined", key="custom_col_label").strip()
        custom_col_name = custom_label_input or "Custom Combined"
        custom_group = {custom_col_name: custom_months}
        custom_months_short = [m.split("'")[0][:3] + "'" + m.split("'")[1][2:] for m in custom_months]
        st.sidebar.caption(f"Combines: {', '.join(custom_months_short)}")

show_sig = st.sidebar.toggle("Significance vs Rest of Sample (95%/90%)", value=True,
                              help="Marks each category as significantly higher/lower than the OTHER segments combined (e.g. Acceptor vs Rejector+Cancelled) — a true 'this group vs the rest' test, not diluted by including the group in its own baseline.")
with st.sidebar.popover("ℹ️ What do the colors mean?", use_container_width=True):
    render_sig_legend()
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

st.sidebar.markdown("---")
if st.sidebar.button("Log out"):
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


def kpi_chip(icon, label, value, sub=None):
    sub_html = f"<div style='font-size:11px;color:#9A958D;margin-top:2px;'>{sub}</div>" if sub else ""
    return (
        f"<div style='flex:1;min-width:150px;background:linear-gradient(165deg,#FFFFFF,#FCFBF9);"
        f"border:1px solid #ECE9E4;border-radius:10px;padding:12px 14px;"
        f"box-shadow:0 2px 8px rgba(0,0,0,0.04);position:relative;overflow:hidden;'>"
        f"<div style='position:absolute;top:0;left:0;width:100%;height:3px;background:{accent};'></div>"
        f"<div style='font-size:18px;margin-bottom:2px;'>{icon}</div>"
        f"<div style='font-size:10px;text-transform:uppercase;letter-spacing:0.05em;color:#9A958D;font-weight:600;'>{label}</div>"
        f"<div style='font-size:1.45rem;font-weight:800;color:#1A1A1A;line-height:1.2;'>{value}</div>{sub_html}</div>"
    )


chips = [
    kpi_chip("📋", "Segment", segment_nav),
    kpi_chip("👥", "Base (N)", f"{base_n:,}", f"{base_n / total_n * 100:.0f}% of total {total_n:,}"),
    kpi_chip("🎯", "Top Age Group", top_age_row['Unnamed: 0'], f"{float(top_age_row['All']):.0f}% of base"),
    kpi_chip("🔍", "Active Filters", f"{platform} / {model}"),
]
st.markdown(f"<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:1rem;'>{''.join(chips)}</div>", unsafe_allow_html=True)

# Headline insight strip — gives the page a narrative entry point instead
# of dropping straight into a grid of charts (per "still not good
# representation wise" feedback: lack of visual hierarchy was the real gap,
# not just chart-type variety).
income_quick = engine.household_income_table(df, base_label=segment_value, numeric=True)
top_income_row = income_quick.iloc[1:].loc[income_quick.iloc[1:]['All'].astype(float).idxmax()]
tob_quick = engine.type_of_buyer_table(df, base_label=segment_value, numeric=True)
top_tob_row = tob_quick.iloc[1:].loc[tob_quick.iloc[1:]['All'].astype(float).idxmax()]

st.markdown(
    f"<div style='background:linear-gradient(135deg,{accent}10,#FFFFFF);border-left:4px solid {accent};"
    f"border-radius:8px;padding:14px 18px;margin-bottom:1.2rem;font-size:0.95rem;color:#2B2B2B;line-height:1.6;'>"
    f"💡 Among <b>{segment_nav}</b> ({base_n:,} respondents), the typical profile is a "
    f"<b>{top_age_row['Unnamed: 0']}</b>-old ({float(top_age_row['All']):.0f}%) earning "
    f"<b>{top_income_row['Unnamed: 0']}</b> ({float(top_income_row['All']):.0f}%), most commonly as "
    f"<b>{top_tob_row['Unnamed: 0'].lower()}</b> ({float(top_tob_row['All']):.0f}%)."
    f"</div>",
    unsafe_allow_html=True,
)

ai_facts = {
    "segment": segment_nav, "base_n": int(base_n), "total_n": int(total_n),
    "filters": {"platform": platform, "model": model, "time_period": time_mode},
    "top_age_group": {"label": top_age_row['Unnamed: 0'], "pct": round(float(top_age_row['All']), 1)},
    "top_income_bracket": {"label": top_income_row['Unnamed: 0'], "pct": round(float(top_income_row['All']), 1)},
    "top_buyer_type": {"label": top_tob_row['Unnamed: 0'], "pct": round(float(top_tob_row['All']), 1)},
}
render_ai_summary_button(ai_facts, key=f"{segment_value}_{platform}_{model}_{time_mode}")

# Per-chart AI blurbs (separate from the page-level summary above) auto-
# generate as each chart renders — per user's chosen design: auto-generate
# on load, with a single button per page that regenerates ALL of them at
# once by bumping a page-scoped nonce included in every chart's cache key.
regen_key = f"regen_nonce_{segment_value}"
st.session_state.setdefault(regen_key, 0)
if st.button("🔄 Regenerate all AI insights on this page", key=f"regen_btn_{segment_value}"):
    st.session_state[regen_key] += 1
    st.rerun()

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


def _extra_views(title, table_fn):
    """Lazy + isolated: st.expander's body runs on EVERY script execution
    regardless of collapsed/expanded state (it only hides the result
    visually). Gating behind a checkbox inside @st.fragment means it only
    computes when actually requested, and toggling it only reruns this
    fragment, not the whole page. Zone Heatmap removed per explicit
    instruction to remove the zonal filter — only Composition vs Overview
    remains here now."""
    @st.fragment
    def _frag():
        show = st.checkbox("Show Composition vs Overview", key=f"extra_{title}")
        if not show:
            return
        full_tbl = table_fn(df, segment_value)
        full_baseline = table_fn(baseline_df, "All")
        st.plotly_chart(stacked_composition_bar(full_tbl, full_baseline, title),
                         use_container_width=True, config={"displayModeBar": False}, key=f"stack_{title}")
    _frag()


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
    unfiltered Overview baseline, plus a lazily-computed Composition-vs-
    Overview stacked bar — an MR-standard supplementary view, available for
    every metric on every page without slowing down the
    default view (see _extra_views).
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
    tbl = _trim_to_selected_months(table_fn(df, segment_value))
    baseline_tbl = _trim_to_selected_months(table_fn(baseline_df, "All"))
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
    col_markers = compare_to_baseline_by_column(tbl, baseline_tbl, sig_cols) if show_sig else None
    chart_tbl = engine.cap_rows(tbl, **cap_chart) if cap_chart else tbl
    with st.container(border=True):
        if caption:
            st.caption(caption)
        render_chart_with_table(chart_tbl, title, color=(color or accent), key=f"chart_{title}", chart_type=chart_type, col_sig_markers=col_markers, table_df_html=tbl, rollup_labels=rollup_set, highlight_col=custom_col_name)
        cat_rows = tbl.iloc[1:]
        top_row = cat_rows.loc[cat_rows['All'].astype(float).idxmax()]
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
        render_chart_ai_blurb(chart_facts, key=f"aiblurb_{title}_{segment_value}_{platform}_{model}_{time_mode}")
        _extra_views(title, table_fn)
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
    tbl = _trim_to_selected_months(table_fn(df, segment_value))
    baseline_tbl = _trim_to_selected_months(table_fn(baseline_df, "All"))
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
    col_markers = compare_to_baseline_by_column(tbl, baseline_tbl, sig_cols) if show_sig else None

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
        render_chart_with_table(rollup_tbl, title, color=color, key=f"chart_{title}",
                                 chart_type="brand_rollup", col_sig_markers=sorted_col_markers,
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
        render_chart_ai_blurb(chart_facts, key=f"aiblurb_{title}_{segment_value}_{platform}_{model}_{time_mode}")
        _extra_views(title, table_fn)
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
st.markdown("### Demographics")
# One subsection at a time (not a 2-column grid) per user feedback —
# the stacked-bar charts are wide (right-side legend) and cramped
# side-by-side; full-width, one-below-the-other reduces clutter.
section("Age", lambda d, s: engine.age_table(d, base_label=s, numeric=True, extra_groups=custom_group), chart_type="stacked_bar")
section("Education", lambda d, s: engine.education_table(d, base_label=s, numeric=True, extra_groups=custom_group), chart_type="stacked_bar")
section("Occupation", lambda d, s: engine.occupation_table(d, base_label=s, numeric=True, extra_groups=custom_group), chart_type="stacked_bar")
section("Household Income", lambda d, s: engine.household_income_table(d, base_label=s, numeric=True, extra_groups=custom_group), chart_type="stacked_bar")

st.markdown("### Type of Buyer")
section("Type of Buyer", lambda d, s: engine.type_of_buyer_table(d, base_label=s, numeric=True, extra_groups=custom_group), chart_type="donut")

# Treemaps rank+cap by 'All' value, so brand ROLLUP rows ("RE", "HERO",
# "BAJAJ"...) must be excluded before capping — otherwise a rollup sits
# next to its own member rows and (being the largest by construction)
# drowns out everything else. Computed dynamically from the manufacturers
# actually present, not hardcoded, since brand_owned/considered/additional
# now emit a rollup for every manufacturer, not just RE.
ROLLUP_LABELS = ["RE"] + [m for m in engine.manufacturers() if m != "Royal Enfield"]

# Each of the three brand-wise sections gets its own distinct color (not the
# segment's shared accent, not each other) — per user request to visually
# tell them apart at a glance.
ADD_REPL_COLOR = "#2E3192"      # Infoleap blue
BRAND_OWNED_COLOR = "#662D91"   # Infoleap purple
BRAND_CONSIDERED_COLOR = "#1B8A8A"  # teal, distinct from both

st.markdown("### Additional + Replaced")
section("Additional + Replaced — CC Wise",
        lambda d, s: engine.additional_replaced_table(d, by="cc", base_label=s, numeric=True, extra_groups=custom_group),
        color=ADD_REPL_COLOR)
brand_wise_section("Additional + Replaced — Brand Wise",
                    lambda d, s: engine.additional_replaced_table(d, by="brand", base_label=s, numeric=True, extra_groups=custom_group),
                    color=ADD_REPL_COLOR)

st.markdown("### Brand Owned")
section("Brand Owned — CC Wise",
        lambda d, s: engine.brand_owned_table(d, by="cc", base_label=s, numeric=True, extra_groups=custom_group),
        color=BRAND_OWNED_COLOR)
brand_wise_section("Brand Owned — Brand Wise",
                    lambda d, s: engine.brand_owned_table(d, by="brand", base_label=s, numeric=True, extra_groups=custom_group),
                    color=BRAND_OWNED_COLOR)

st.markdown("### Brand Considered")
section("Brand Considered — CC Wise",
        lambda d, s: engine.brand_considered_table(d, by="cc", base_label=s, numeric=True, extra_groups=custom_group),
        caption="Approximate — see docs/DATA_FIELD_MAPPING.md Addendum 8/9.",
        color=BRAND_CONSIDERED_COLOR)
brand_wise_section("Brand Considered — Brand Wise",
                    lambda d, s: engine.brand_considered_table(d, by="brand", base_label=s, numeric=True, extra_groups=custom_group),
                    color=BRAND_CONSIDERED_COLOR,
                    caption="Approximate — see docs/DATA_FIELD_MAPPING.md Addendum 8/9.")

st.markdown("### Reasons")
if segment_value == "Cancelled":
    reasons_placeholder("Reasons for Cancelling", "Cancelled")
elif segment_value == "Rejector":
    reasons_placeholder("Reasons for Rejection", "Rejectors")
elif segment_value == "Acceptor":
    reasons_placeholder("Key Buying Factors", "Acceptors")
else:
    reasons_placeholder("Key Buying Factors / Reasons for Rejection / Reasons for Cancelling", "this segment")

st.markdown("### Month-over-Month Trend")


@st.fragment
def _trend_section():
    trend_table_choice = st.selectbox("Trend for", list(trend_map.keys()))
    st.altair_chart(month_trend_chart(trend_map[trend_table_choice], selected_months), use_container_width=True)


_trend_section()
