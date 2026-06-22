"""Chart builders for the Digital Showroom. Plotly for the main distribution
bars; Altair for the compact month-over-month trend lines."""
import plotly.graph_objects as go
import altair as alt
import pandas as pd
import streamlit as st
from styles.theme import RE_RED, CHART_SEQUENCE, BORDER, MUTED

PLOTLY_CONFIG = {"displayModeBar": False, "staticPlot": False}


def _sig_border(marker):
    """Maps a compare_to_baseline() marker to a (line_color, line_width)
    border so significance is visible directly on the chart mark (bar
    border / donut wedge border), not just in the table cell — per user
    request to make 95%/90% significance 'visually understandable' beyond
    the table alone."""
    if marker in ('▲', '▼'):
        return (SIG_DEEP_GREEN if marker == '▲' else SIG_DEEP_RED), 3
    if marker in ('△', '▽'):
        return (SIG_LIGHT_GREEN if marker == '△' else SIG_LIGHT_RED), 2.5
    return "rgba(0,0,0,0)", 0


def distribution_bar(table_df, title, color=RE_RED, sig_markers=None):
    """Horizontal bar of the 'All' column for a distribution_table() result
    (numeric=True). Expects row 0 to be the Base row (n=), which is dropped
    from the plotted rows but always shown in the title — per
    MIS_Dashboard_Requirements.docx 5.5: 'Sample Size (n=) Display — Every
    chart and table must show the base size... non-negotiable.'

    sig_markers: optional list (one per category row) of significance
    markers from stat_engine.compare_to_baseline(), appended to the bar's
    data label (e.g. "47% ▲") AND drawn as a colored border on the bar
    itself (deep border = 95%, light border = 90%).
    """
    base_n = table_df.iloc[0]['All']
    rows = table_df.iloc[1:]
    values = rows['All'].astype(float)

    labels = []
    border_colors, border_widths = [], []
    for i, v in enumerate(values):
        marker = sig_markers[i] if sig_markers and i < len(sig_markers) else ''
        labels.append(f"{v:.0f}% {marker}".strip())
        bc, bw = _sig_border(marker)
        border_colors.append(bc)
        border_widths.append(bw)

    fig = go.Figure(go.Bar(
        x=values, y=rows['Unnamed: 0'], orientation='h',
        marker=dict(color=color, line=dict(color=border_colors, width=border_widths), cornerradius=4),
        text=labels, textposition='outside',
        textfont=dict(size=12, color="#1A1A1A", family="Inter, Segoe UI, sans-serif"),
        hovertemplate="<b>%{y}</b><br>%{x:.1f}% of base<extra></extra>",
        cliponaxis=False,
    ))
    fig.update_layout(
        title=dict(text=f"{title}  <span style='font-size:11px;color:{MUTED}'>(n={base_n:,.0f})</span>",
                    font=dict(size=15, color="#1A1A1A", family="Oswald, Inter, sans-serif")),
        height=max(230, 42 * len(rows)),
        margin=dict(l=10, r=70, t=44, b=10),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(title=None, showgrid=False, zeroline=False, showticklabels=True,
                   tickfont=dict(size=11, color=MUTED), ticksuffix="%",
                   range=[0, max(float(values.max()) * 1.32, 10)]),
        yaxis=dict(autorange='reversed', showgrid=False, tickfont=dict(size=12.5, color="#2B2B2B", family="Inter, Segoe UI, sans-serif")),
        font=dict(color="#2B2B2B", family="Inter, Segoe UI, sans-serif"),
        bargap=0.36,
        showlegend=False,
    )
    return fig


def donut_chart(table_df, title, color_seq=None, sig_markers=None):
    """Donut chart for compositional metrics (few mutually-exclusive
    buckets, e.g. Income brackets, Type of Buyer) — per user feedback
    ('too much bar chart'), a small number of MR-correct chart types for
    variety where a donut genuinely fits better than a ranked bar list
    (composition of a whole, not a ranked comparison).

    sig_markers: same vocabulary as distribution_bar — drawn as a colored
    wedge border (this was previously never wired in at all for donuts,
    so significance was invisible on every donut-rendered metric)."""
    base_n = table_df.iloc[0]['All']
    rows = table_df.iloc[1:]
    values = rows['All'].astype(float)
    colors = color_seq or CHART_SEQUENCE
    border_colors, border_widths = [], []
    for i in range(len(rows)):
        marker = sig_markers[i] if sig_markers and i < len(sig_markers) else ''
        bc, bw = _sig_border(marker)
        border_colors.append(bc if bw else 'white')
        border_widths.append(max(bw, 2))
    # Readability fix: inline "label+percent" text crammed inside small
    # wedges was unreadable. Percent stays on the wedge (only for slices
    # big enough to fit it), full category names move to a proper legend.
    fig = go.Figure(go.Pie(
        labels=rows['Unnamed: 0'], values=values, hole=0.55,
        marker=dict(colors=colors, line=dict(color=border_colors, width=border_widths)),
        textinfo='percent', textposition='inside',
        insidetextorientation='horizontal',
        textfont=dict(size=13, color="white", family="Inter, Segoe UI, sans-serif"),
        hovertemplate="<b>%{label}</b><br>%{value:.1f}% of base<extra></extra>",
        sort=False,
    ))
    fig.update_traces(texttemplate="%{percent:.0%}")
    fig.update_layout(
        title=dict(text=f"{title}  <span style='font-size:11px;color:{MUTED}'>(n={base_n:,.0f})</span>",
                    font=dict(size=15, color="#1A1A1A", family="Oswald, Inter, sans-serif")),
        height=360, margin=dict(l=10, r=10, t=44, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#2B2B2B"),
        showlegend=True,
        legend=dict(orientation='h', yanchor='top', y=-0.05, font=dict(size=11), itemwidth=30),
    )
    return fig


SIG_DEEP_GREEN = "#1A7A3C"   # 95% confidence, base >= 30
SIG_LIGHT_GREEN = "#B7E4C0"  # 90% directional, base >= 30
SIG_DEEP_RED = "#9E2A2A"     # 95% confidence, significantly LOWER
SIG_LIGHT_RED = "#F0C2C2"    # 90% directional, significantly lower


def render_sig_legend():
    """Single shared legend body — used inside the per-chart popover AND
    the one sidebar reference copy, so there's exactly one place this text
    is written (per user request to stop repeating the full legend on
    every chart down the page)."""
    st.markdown(
        f"<div style='font-size:12px;color:#3A3732;line-height:1.8;'>"
        f"<div><span style='display:inline-block;width:10px;height:10px;border-radius:2px;background:{SIG_DEEP_GREEN};margin-right:6px;'></span>95% significant, higher</div>"
        f"<div><span style='display:inline-block;width:10px;height:10px;border-radius:2px;background:{SIG_DEEP_RED};margin-right:6px;'></span>95% significant, lower</div>"
        f"<div><span style='display:inline-block;width:10px;height:10px;border-radius:2px;background:{SIG_LIGHT_GREEN};margin-right:6px;'></span>90% directional, higher</div>"
        f"<div><span style='display:inline-block;width:10px;height:10px;border-radius:2px;background:{SIG_LIGHT_RED};margin-right:6px;'></span>90% directional, lower</div>"
        f"<div style='margin-top:6px;color:#7A7670;'>Bar/wedge borders and table cells use these same colors. "
        f"Base &lt; 30 comparisons are never tested — checked per month too, not just overall.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


_FULL_MONTH_NAMES = {
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
}


def _month_header(m):
    """Abbreviates a real month column ("August'2025" -> "Aug'25"). Quarter-
    combined columns (e.g. "JAS'25") are already short — pass through
    unchanged rather than mangling them (year[2:] on a 2-digit year is empty,
    which would silently truncate the label)."""
    name, year = m.split("'")
    if name not in _FULL_MONTH_NAMES:
        return m
    return f"{name[:3]}'{year[2:]}"


def _render_html_table(table_df, sig_markers=None, accent=RE_RED, col_sig_markers=None, rollup_labels=None):
    """Renders a compact bordered HTML table matching the live dashboard's
    report-table look, with cells colour-highlighted for significance (deep
    green = 95% confidence, light green = 90% directional; red shades for
    significantly LOWER) instead of plain arrow text — per user request,
    base>=30 is already enforced upstream in stat_engine.calculate_significance
    (n<30 -> no marker at all).

    sig_markers: markers for the 'All' column only (backward compatible).
    col_sig_markers: optional {column_name: [markers]} from
    stat_engine.compare_to_baseline_by_column() — per user request
    ('significance testing should run month by month for a sample size
    equal or over 30 respondant'), applies the SAME highlighting to each
    month column independently, not just the aggregate 'All' column.

    The Base row (n=) is highlighted with the segment's accent color, since
    the live dashboard always keeps the base row visually prominent —
    'every chart and table must show the base size... non-negotiable.'

    rollup_labels: optional set of brand-rollup row labels (e.g. {"RE",
    "HERO", "BAJAJ"}) — per user request to match the live site's nested
    look, every OTHER non-Base row is indented and shown in a lighter
    weight as a "member" of whichever rollup precedes it."""
    cols = ["Unnamed: 0", "All"] + [c for c in table_df.columns if c not in ("Unnamed: 0", "All")]
    # Long brand-wise tables (rollup + many member rows) get a sticky header
    # + scrollable body instead of pushing the whole page down, plus zebra
    # striping on member rows and a subtle top-border between brand groups
    # — per user request to keep a long table 'aesthetically pleasing and
    # quite clean looking even when it is long', not just functionally
    # complete.
    is_long = len(table_df) > 12
    header_cells = "".join(
        f"<th style='padding:7px 10px;text-align:left;background:#F3F1ED;border-bottom:2px solid {BORDER};"
        f"white-space:nowrap;position:sticky;top:0;z-index:1;'>"
        f"{'Category' if c == 'Unnamed: 0' else ('All' if c == 'All' else _month_header(c))}</th>"
        for c in cols
    )
    body_rows = []
    member_n = 0
    for i, row in table_df.iterrows():
        is_base = (i == 0)
        is_rollup = (not is_base) and rollup_labels is not None and str(row['Unnamed: 0']) in rollup_labels
        is_member = (not is_base) and rollup_labels is not None and not is_rollup
        if is_member:
            member_n += 1
        elif is_rollup:
            member_n = 0
        cells = []
        for c in cols:
            val = row[c]
            if c == "Unnamed: 0":
                txt = str(val)
                if is_base:
                    style = f"padding:7px 10px;font-weight:800;white-space:nowrap;color:{accent};"
                elif is_member:
                    txt = f"&nbsp;&nbsp;&nbsp;&nbsp;↳ {txt}"
                    style = "padding:5px 10px;white-space:nowrap;color:#6A665F;font-size:12px;"
                elif rollup_labels is not None:
                    style = f"padding:7px 10px;white-space:nowrap;font-weight:700;border-top:2px solid {BORDER};"
                else:
                    style = "padding:6px 10px;white-space:nowrap;"
            else:
                try:
                    val = float(val)
                    # Per user request: a 0% cell reads as "no signal" at a
                    # glance, easy to mistake for missing/broken data — a
                    # dash makes "genuinely zero" visually distinct from a
                    # small-but-real percentage.
                    txt = f"{val:,.0f}" if is_base else ("-" if val == 0 else f"{val:.0f}%")
                except (ValueError, TypeError):
                    txt = str(val)
                if is_base:
                    style = f"padding:7px 10px;text-align:right;font-weight:800;color:{accent};"
                elif is_member:
                    style = "padding:5px 10px;text-align:right;font-size:12px;color:#6A665F;"
                elif rollup_labels is not None:
                    style = f"padding:7px 10px;text-align:right;font-weight:700;border-top:2px solid {BORDER};"
                else:
                    style = "padding:6px 10px;text-align:right;"
                if not is_base:
                    # Per user instruction: significance NEVER runs on the
                    # aggregate 'All' column, anywhere — only on individual
                    # month columns. col_sig_markers only ever carries month
                    # keys now (see compare_to_baseline_by_column call sites).
                    marker = None
                    if col_sig_markers and c in col_sig_markers and c != "All":
                        col_markers = col_sig_markers[c]
                        marker = col_markers[i - 1] if i - 1 < len(col_markers) else ''
                    if marker == '▲':
                        style += f"background:{SIG_DEEP_GREEN};color:white;font-weight:700;"
                    elif marker == '△':
                        style += f"background:{SIG_LIGHT_GREEN};color:#1A1A1A;font-weight:600;"
                    elif marker == '▼':
                        style += f"background:{SIG_DEEP_RED};color:white;font-weight:700;"
                    elif marker == '▽':
                        style += f"background:{SIG_LIGHT_RED};color:#1A1A1A;font-weight:600;"
            cells.append(f"<td style='{style}border-bottom:1px solid {BORDER};'>{txt}</td>")
        if is_base:
            bg = "background:#FAFAF8;"
        elif is_rollup:
            bg = "background:#FBF8F3;"
        elif is_member and member_n % 2 == 0:
            bg = "background:#FAFAF9;"
        else:
            bg = ""
        body_rows.append(f"<tr style='{bg}'>" + "".join(cells) + "</tr>")

    wrapper_style = (
        f"overflow-x:auto;overflow-y:auto;max-height:460px;border:1px solid {BORDER};border-radius:8px;margin-top:0.4rem;"
        if is_long else
        f"overflow-x:auto;border:1px solid {BORDER};border-radius:8px;margin-top:0.4rem;"
    )
    html = (
        f"<div style='{wrapper_style}'>"
        f"<table style='width:100%;border-collapse:collapse;font-size:13px;font-family:Segoe UI,Tahoma,sans-serif;'>"
        f"<thead><tr>{header_cells}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>"
    )
    if is_long:
        st.caption(f"{len(table_df) - 1} rows — scroll within the table to see all of them.")
    st.markdown(html, unsafe_allow_html=True)


def treemap_chart(table_df, title):
    """Treemap for many-category ranked lists (brand-wise Brand Considered/
    Brand Owned/Additional+Replaced, 8+ rows after cap_rows) — per repeated
    'too much bar chart' feedback. Treemap is the MR-correct alternative
    here: it's a share-of-mentions composition across many categories,
    where area naturally draws the eye to the largest contributors, which
    a long bar list does less effectively."""
    base_n = table_df.iloc[0]['All']
    rows = table_df.iloc[1:]
    values = rows['All'].astype(float)
    fig = go.Figure(go.Treemap(
        labels=rows['Unnamed: 0'], values=values, parents=[""] * len(rows),
        marker=dict(colors=values, colorscale=[[0, "#F6D9D9"], [1, RE_RED]], line=dict(width=1, color="white")),
        text=[f"{v:.0f}%" for v in values], textinfo="label+text",
        textfont=dict(size=13, family="Inter, Segoe UI, sans-serif"),
        hovertemplate="<b>%{label}</b><br>%{value:.1f}% of base<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=f"{title}  <span style='font-size:11px;color:{MUTED}'>(n={base_n:,.0f})</span>",
                    font=dict(size=15, color="#1A1A1A", family="Oswald, Inter, sans-serif")),
        height=380, margin=dict(l=4, r=4, t=44, b=4),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, Segoe UI, sans-serif"),
    )
    return fig


def brand_rollup_bar(rollup_table_df, title, color=RE_RED):
    """Simple bar comparing brand ROLLUPS only (RE/HERO/BAJAJ/...), no
    individual models — per user request: 'show the overall comparison in
    bar chart' above the detailed member-level table, separating the
    'which brand wins' read from the 'which model within that brand' read.
    Reuses distribution_bar's rendering (rollup_table_df is already just
    Base + rollup rows, sorted, 'Other' last)."""
    return distribution_bar(rollup_table_df, f"{title} — Brand Comparison", color=color)


def render_chart_with_table(table_df, title, color=RE_RED, sig_markers=None, key=None, chart_type="bar", col_sig_markers=None, table_df_html=None, rollup_labels=None):
    """Renders the chart, then the underlying data table right below it
    (per user requirement: tabular data must accompany every chart, not
    just the chart alone, and match the live site's table layout).
    chart_type='donut' for compositional metrics, 'treemap' for many-
    category ranked lists — per repeated 'too much bar chart' feedback,
    each chosen because it's the more correct MR visual for that data
    shape, not just for variety's sake.

    Per explicit user instruction ('significance running on the All column
    which should not happen... everywhere the all section is present') —
    significance NEVER applies to the aggregate 'All' column, anywhere, in
    any table. sig_markers is accepted for signature compatibility but is
    no longer used to color the chart/table — only col_sig_markers (month
    columns) drives any highlighting now.

    table_df_html: per user request ('brand wise data is not showing the
    full table') — when the CHART needs a capped/ranked subset (treemaps
    cap_rows() to ~8 rows + 'Other' so they stay readable), the data TABLE
    underneath should still show every row. Pass the full uncapped table
    here and table_df stays the (possibly capped) chart-only data; when
    omitted, both chart and table use table_df as before."""
    html_table = table_df_html if table_df_html is not None else table_df
    base_n = table_df.iloc[0]['All']
    all_zero = table_df.iloc[1:]['All'].astype(float).sum() == 0
    if base_n == 0 or all_zero:
        st.info(f"{title}: base n=0 for the current selection — this table doesn't apply here (e.g. Acceptors have no 'brand owned instead of RE'). Table shown below for completeness.")
        _render_html_table(html_table, accent=color, col_sig_markers=col_sig_markers, rollup_labels=rollup_labels)
        return
    # Per user request: significance legend lives ONLY in the sidebar now,
    # not repeated as a per-chart popover.
    if chart_type == "donut":
        fig = donut_chart(table_df, title)
    elif chart_type == "treemap":
        fig = treemap_chart(table_df, title)
    elif chart_type == "brand_rollup":
        # table_df here is the rollup-only table (Base + brand rollups,
        # sorted, 'Other' last); table_df_html carries the full sorted
        # member-level table separately, per user request to show 'the
        # overall comparison in bar chart and down to that the table'.
        fig = brand_rollup_bar(table_df, title, color=color)
    else:
        fig = distribution_bar(table_df, title, color=color)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=key)
    _render_html_table(html_table, accent=color, col_sig_markers=col_sig_markers, rollup_labels=rollup_labels)


def overlay_radar_chart(tables, title):
    """Spider/radar chart overlaying 2-4 models on ONE shared chart — each
    model is a separate colored trace on the SAME category axes (e.g. the
    same metric's age buckets, income brackets, etc.), with a shared
    legend, so shapes can be compared directly at a glance instead of
    flipping between separate per-model charts. tables: {model_name:
    table_df}. This is the legitimate MR use of radar — comparing one
    metric's profile shape across entities on a common axis set, not
    mixing unrelated category types (which would be the bad use)."""
    model_names = list(tables.keys())
    categories = tables[model_names[0]].iloc[1:]['Unnamed: 0'].tolist()
    fig = go.Figure()
    for i, name in enumerate(model_names):
        tbl = tables[name]
        cat_map = {row['Unnamed: 0']: float(row['All']) for _, row in tbl.iloc[1:].iterrows()}
        values = [cat_map.get(c, 0.0) for c in categories]
        color = CHART_SEQUENCE[i % len(CHART_SEQUENCE)]
        fig.add_trace(go.Scatterpolar(
            r=values + [values[0]], theta=categories + [categories[0]],
            name=name.replace("Royal Enfield ", ""), fill='toself',
            line=dict(color=color, width=2), opacity=0.75,
            hovertemplate=f"<b>{name}</b><br>%{{theta}}: %{{r:.0f}}%<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text=f"{title} — Model Profile Overlay", font=dict(size=15, color="#1A1A1A", family="Oswald, Inter, sans-serif")),
        polar=dict(radialaxis=dict(visible=True, ticksuffix="%", showline=False, gridcolor=BORDER),
                   angularaxis=dict(tickfont=dict(size=12, color="#2B2B2B"))),
        height=440, margin=dict(l=40, r=40, t=60, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, Segoe UI, sans-serif"),
        legend=dict(orientation='h', yanchor='bottom', y=-0.15, font=dict(size=12)),
    )
    return fig


def overlay_grouped_bar(tables, title):
    """Grouped bar overlay — same idea as the radar above (all models on
    one shared chart with a shared legend) but as bars, for users who
    prefer reading exact magnitudes over chart shape."""
    model_names = list(tables.keys())
    categories = tables[model_names[0]].iloc[1:]['Unnamed: 0'].tolist()
    fig = go.Figure()
    for i, name in enumerate(model_names):
        tbl = tables[name]
        cat_map = {row['Unnamed: 0']: float(row['All']) for _, row in tbl.iloc[1:].iterrows()}
        values = [cat_map.get(c, 0.0) for c in categories]
        color = CHART_SEQUENCE[i % len(CHART_SEQUENCE)]
        fig.add_trace(go.Bar(
            x=categories, y=values, name=name.replace("Royal Enfield ", ""),
            marker_color=color, text=[f"{v:.0f}%" for v in values], textposition='outside',
            hovertemplate=f"<b>{name}</b><br>%{{x}}: %{{y:.0f}}%<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text=f"{title} — Model Comparison", font=dict(size=15, color="#1A1A1A", family="Oswald, Inter, sans-serif")),
        barmode='group', height=400, margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, Segoe UI, sans-serif", size=12),
        yaxis=dict(showgrid=False, showticklabels=True, ticksuffix="%"),
        xaxis=dict(showgrid=False),
        legend=dict(orientation='h', yanchor='bottom', y=-0.25, font=dict(size=12)),
    )
    return fig


def overlay_trend_chart(tables, month_cols):
    """One Altair area/line chart with every selected model overlaid,
    colored by model — 'showing the overlapping at once... like area
    charts'. Trends each model's TOP category (the one with the highest
    'All' value) since overlaying every category for every model on one
    chart would be too busy to read."""
    long_rows = []
    for name, tbl in tables.items():
        rows = tbl.iloc[1:]
        top_cat = rows.loc[rows['All'].astype(float).idxmax(), 'Unnamed: 0']
        for m in month_cols:
            if m not in tbl.columns:
                continue
            val = float(rows[rows['Unnamed: 0'] == top_cat][m].iloc[0])
            long_rows.append({"Model": f"{name.replace('Royal Enfield ', '')} ({top_cat})",
                               "Month": m.split("'")[0][:3], "Value": val})
    long_df = pd.DataFrame(long_rows)
    chart = alt.Chart(long_df).mark_area(opacity=0.35, line=True, point=True).encode(
        x=alt.X('Month:N', sort=None, title=None),
        y=alt.Y('Value:Q', title='%'),
        color=alt.Color('Model:N', scale=alt.Scale(range=CHART_SEQUENCE), legend=alt.Legend(title=None, orient='bottom')),
        tooltip=['Model:N', 'Month:N', 'Value:Q'],
    ).properties(height=280).configure_view(strokeWidth=0).configure_axis(grid=True, gridColor=BORDER)
    return chart


def stacked_composition_bar(tbl, baseline_tbl, title, label_a="This Selection", label_b="Overview"):
    """100% stacked HORIZONTAL bar comparing the current filtered selection's
    category composition against the unfiltered Overview baseline — the
    standard MR 'compare profile shape across groups' visual. Horizontal
    (not vertical) so there's room for a legend AND in-bar labels without
    crushing them — readability fix: the old vertical version's segment
    text became illegible clutter once a category's slice dropped below
    ~6% of the bar (text overlapping its neighbours); those slices now show
    their value only on hover instead of cramming unreadable inline text."""
    cats = tbl.iloc[1:]['Unnamed: 0'].tolist()
    a_vals = tbl.iloc[1:]['All'].astype(float).tolist()
    b_map = {row['Unnamed: 0']: float(row['All']) for _, row in baseline_tbl.iloc[1:].iterrows()}
    b_vals = [b_map.get(c, 0.0) for c in cats]

    fig = go.Figure()
    for i, cat in enumerate(cats):
        vals = [a_vals[i], b_vals[i]]
        text = [f"{v:.0f}%" if v >= 6 else "" for v in vals]
        fig.add_trace(go.Bar(
            y=[label_a, label_b], x=vals, orientation='h',
            name=cat, marker_color=CHART_SEQUENCE[i % len(CHART_SEQUENCE)],
            text=text, textposition='inside', insidetextanchor='middle',
            textfont=dict(size=12, color="white"),
            hovertemplate=f"<b>{cat}</b><br>%{{y}}: %{{x:.0f}}%<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text=f"{title} — Composition vs Overview", font=dict(size=14, color="#1A1A1A", family="Oswald, Inter, sans-serif")),
        barmode='stack', height=max(220, 70 * 2 + 18 * len(cats)), margin=dict(l=90, r=10, t=44, b=10),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, Segoe UI, sans-serif", size=12.5, color="#2B2B2B"),
        legend=dict(orientation='h', yanchor='top', y=-0.12, font=dict(size=11)),
        xaxis=dict(showgrid=False, showticklabels=True, ticksuffix="%", range=[0, 105]),
        yaxis=dict(showgrid=False, tickfont=dict(size=13)),
    )
    return fig


def zone_heatmap(zone_matrix, title):
    """Category x Zone heatmap — % of base per category within each zone,
    ignoring the sidebar Zone filter so all 5 zones show side by side.
    Standard MR cross-tab visual for spotting regional skews at a glance.
    zone_matrix: {category: {zone: pct}}"""
    categories = list(zone_matrix.keys())
    zones = list(next(iter(zone_matrix.values())).keys()) if zone_matrix else []
    z = [[zone_matrix[cat][zone] for zone in zones] for cat in categories]

    # Readability fix: the old colorscale topped out at solid RE-red, which
    # made the fixed-dark text unreadable on the highest cells. Capped the
    # colorscale at a lighter rose tone so black text stays legible across
    # every cell, added a colorbar for scale context, and enlarged the grid.
    fig = go.Figure(go.Heatmap(
        z=z, x=zones, y=categories,
        colorscale=[[0, "#FCFBF9"], [0.5, "#F6D9D9"], [1, "#E8A0A8"]],
        zmin=0, zmax=max((max(row) for row in z), default=10),
        text=[[f"{v:.0f}%" for v in row] for row in z],
        texttemplate="%{text}", textfont=dict(size=13, color="#1A1A1A", family="Inter, Segoe UI, sans-serif"),
        hovertemplate="<b>%{y}</b> in <b>%{x}</b>: %{z:.0f}%<extra></extra>",
        showscale=True,
        colorbar=dict(title=dict(text="%", side="right"), thickness=12, len=0.8),
        xgap=3, ygap=3,
    ))
    fig.update_layout(
        title=dict(text=f"{title} — by Zone", font=dict(size=15, color="#1A1A1A", family="Oswald, Inter, sans-serif")),
        height=max(280, 48 * len(categories) + 90),
        margin=dict(l=140, r=20, t=60, b=10),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color="#2B2B2B"),
        xaxis=dict(side='top', tickfont=dict(size=13)),
        yaxis=dict(autorange='reversed', tickfont=dict(size=13), automargin=True),
    )
    return fig


def month_trend_chart(table_df, month_cols, category_filter=None):
    """Altair month-over-month line trend for selected categories. Expects
    row 0 to be the Base row, dropped here; numeric=True table."""
    rows = table_df.iloc[1:]
    if category_filter:
        rows = rows[rows['Unnamed: 0'].isin(category_filter)]

    long_rows = []
    for _, r in rows.iterrows():
        for m in month_cols:
            long_rows.append({"Category": r['Unnamed: 0'], "Month": m.split("'")[0][:3], "Value": float(r[m])})
    long_df = pd.DataFrame(long_rows)

    chart = alt.Chart(long_df).mark_line(point=True, strokeWidth=2.5).encode(
        x=alt.X('Month:N', sort=None, title=None),
        y=alt.Y('Value:Q', title='%'),
        color=alt.Color('Category:N', scale=alt.Scale(range=CHART_SEQUENCE), legend=alt.Legend(title=None)),
        tooltip=['Category:N', 'Month:N', 'Value:Q'],
    ).properties(height=260).configure_view(strokeWidth=0).configure_axis(grid=True, gridColor=BORDER)
    return chart
