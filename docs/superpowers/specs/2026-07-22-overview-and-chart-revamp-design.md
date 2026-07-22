# Overview Rewrite + At-a-Glance Regroup + Chart Layout + Significance Filter — Design

Date: 2026-07-22
Status: drafted, pending user approval

## Source material

`redashboard (2).zip` (from `C:\Users\tuhin\Downloads\`) contains:
- `Final Story by brand_28_04_2026.pptx` — slides 1-4 used as Overview content source. RE logo extracted from slide 1 (`ppt/media/image16.png`).
- `Definitions of the different cohorts.xlsx` — per-attribute cohort definitions (Age/Education/Occupation/Income/Type of Buyer/Additional+Replacement/Brand Owned/Brand Considered), not used directly in this change (informational only, not requested for insertion anywhere yet).

## 1. Overview section rewrite

**Where:** replaces the current chart/hero-card content on the "Overview" nav page (`_overview_is_comparison` branch in `app.py`) — pie summary and comparison charts on that page go away; this narrative replaces them. (Per-segment pages Acceptors/Rejectors/Cancelled and the "Overall" deep-dive page are untouched.)

**Content, sourced from PPT slides 1-4:**

1. **Header** — RE logo (image16.png, copied into `assets/`) + "Understanding the RE Brands" + "Research Findings" + "April 2026".
2. **Research Objectives** (slide 2) — two numbered objective cards:
   - 01 Customer Journey & Brand Perception Analysis — "Understanding the areas which can be exploited and which elements to focus for improvement"; "Identifying specific reasons why customers choose: To Reject the RE brand through detailed drill-downs / To accept the RE brand through detailed drill-downs"
   - 02 Consumer Profile and Consideration Set — "Consumer profile"; "Understanding competitive sets of the different RE brands"
3. **Research Methodology** (slide 3):
   - CATI description paragraph (verbatim).
   - Target Audience: Gender (Male), Age bands, NCCS, Model Purchased (150cc+).
   - Segment definitions: Acceptors / Rejectors / Booked But Cancelled (verbatim, 3 short definitions).
4. **Sample Achieved** (slide 4, table content NOT reproduced as a grid per user decision):
   - 3 segment-level stat cards (Acceptors, Rejectors, Booked But Cancelled) each showing Achieved vs Target, computed by summing slide 4's table rows by segment (Acceptors 500/495, Rejectors 1373/1425, Booked But Cancelled 1385/1425 — Total 3258/3345).
   - Fieldwork context notes (from text beneath the table, not just the grid): "FW Dates: 11th Aug to 12th Apr", "Database used: June to February", "Each month's data is completed using the prior month database."
   - The reporting-lag reference table (Data Reported month → Database Used month, 9 rows) reproduced as a small table — this is reference info, not the big per-model grid, so it's kept intact.

All of this is static content (no chart/data-engine wiring needed) — a new block of markdown/HTML rendered where the old Overview hero+pie-summary+comparison charts currently render.

## 2. At a Glance — pie summary regrouping

Same pies as today, grouped under 4 subheadings instead of one flat 3-column grid:

- **Demographics**: Age, Education, Occupation, Household Income
- **Buyer Type**: Type of Buyer, Additional + Replaced — CC Wise
- **Edition Analysis**: Brand Owned — CC Wise, Test Ride Rate, Brand Resilience, Post-Cancellation Action
- **Brand-to-Brand Comparison**: Brand Considered — CC Wise, Competitor CC Segment, RE Model Considered

Each group renders as its own labeled subsection (3-column chart grid per group, same `donut_chart` calls as today — only the grouping/headings change, not the underlying tables/data). Groups with zero applicable pies for the current segment (e.g. Brand-to-Brand has nothing on the Overview page since Brand Considered etc. are gated `if not _overview_is_comparison`) are skipped entirely, same as today's "only show pies that resolved" behavior.

This section only exists on non-Overview pages now (Overview's chart area is replaced per #1 above), so it applies to Acceptors / Rejectors / Cancelled / Overall.

## 3. Cross-Segment Benchmark — removed

Delete the whole `Cross-Segment Benchmark` block (`app.py` ~line 1167-1229, guarded by `if not _overview_is_comparison and len(_seg_dfs) >= 2`). This is the only such block in the app (one code path, rendered on every segment page) — removing it removes it everywhere per the request.

## 4. Stacked column chart layout

Applies to `stacked_bar_chart()` in `utils/visuals.py`, used for demographics/buyer-type/etc. detail sections.

Current: legend renders horizontally below the chart, table renders below that.
New: legend renders as a vertical list on the **left side** of the chart (Plotly `legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="right", x=-0.02, ...)`), chart plot area shifts right to make room (`margin.l` increased). Chart still renders above its data table (unchanged — chart-then-table order already matches "chart just above the table"). Table's columns already align 1:1 with the chart's x-axis categories (both are driven by the same `cols` = time-period list) — no change needed there, just confirming today's table already satisfies this.

`distribution_bar()` (the plain horizontal bars, `showlegend=False`) and `donut_chart()` (already has its own always-visible legend, different chart type / not a "stacked column chart") are out of scope — only `stacked_bar_chart()` changes.

## 5. Significance High/Low filter

New sidebar control next to the existing `show_sig` toggle and `sig_level_label` radio:

```python
sig_direction = st.sidebar.radio("Show", ["Both", "High only", "Low only"], index=0, horizontal=True,
                                  help="Filter which significance markers are drawn: green (High/▲/△), red (Low/▼/▽), or both.")
```

Mechanism: every marker string (`▲ △ ▼ ▽`) produced by `compare_to_baseline_by_column()` / `calculate_significance()` call sites gets passed through a new small helper, e.g. `_filter_marker(marker, sig_direction)` in `utils/visuals.py`, before being handed to `distribution_bar`, `stacked_bar_chart`, `donut_chart`. When direction is "High only", any `▼`/`▽` marker is blanked to `''` (renders as plain/neutral — no red anywhere, per your answer). "Low only" blanks `▲`/`△` the same way. "Both" (default) passes markers through unchanged. This is applied once, centrally, right where `sig_markers`/`col_sig_markers` dicts are built in `app.py`, so all three chart types (and their paired data tables, which read the same marker values) stay in sync automatically — no per-chart-type duplication.

## Out of scope / unchanged
- `Definitions of the different cohorts.xlsx` content — not requested for placement anywhere in this change; flagging in case a future request wants it (e.g. as tooltips on cohort filters).
- Model Comparison page (`utils/compare.py`), Verbatim Intelligence, login gate — untouched.
- Significance methodology itself (unpooled two-proportion Z-test, base<30 exclusion) — untouched, only which markers are *displayed* changes.
