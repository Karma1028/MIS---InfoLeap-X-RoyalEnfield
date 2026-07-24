# Section Registry ("Pattern API") — Design Spec

Date: 2026-07-24
Status: drafted, pending user review — no code changed by this document

## Background

Per-page metric sections (Age, Education, Occupation, Household Income, Type
of Buyer, Additional + Replaced, Brand Owned, Brand Considered, ...) are
currently hand-wired in `app.py` as ~15 individual top-level statements
(`section(...)` / `brand_wise_section(...)` calls), each preceded by its own
`st.markdown("### ...")` heading, `st.caption(...)`, and — for
segment-specific sections (Competitor CC Preference, RE Model Consideration
Funnel, Brand Resilience, Post-Cancellation) — an `if segment_value ==
"Rejector":` / `"Cancelled"` guard written out by hand at each site. Visible
today at `app.py:1409-1546` (Demographics through Reasons & Motivations).

User request: "we have a pattern API calls and through that we will be
categorizing all the sections and if a new section comes up then also it
will be added" — i.e. adding a new section should mean appending one entry
to a list, not writing a new heading + caption + gate + call by hand.

## Existing precedent (already in the codebase)

`utils/compare.py`'s `DEMOGRAPHIC_BUILDERS` / `ACCEPTOR_BUILDERS` /
`REJECTOR_BUILDERS` dicts (metric name → `(table_fn, chart_type)`), merged by
`_metric_builders_for(segment)` and rendered in one loop
(`compare.py:228-372`). This is the closest existing shape — but scoped only
to the Model Comparison page, and it only carries 2 fields (no heading
grouping, no caption, no brand-filter, no cap_chart, no color). The segment
pages' `section()` function itself (`app.py:1079`) is the actual rendering
engine and stays unchanged — only the *call sites* get replaced by a
registry + loop.

## Proposed registry shape

```python
SEGMENT_SECTIONS = [
    {
        "id": "demographics",                 # group id — heading/caption/anchor render once per group
        "heading": "Demographics",
        "anchor": "sec-demographics",
        "caption": "Age, education, occupation, and household income profile of this segment — who are these respondents?",
        "items": [
            {"id": "age", "title": "Age", "table_fn": lambda d, s: _tbl_age(d, base_label=s, numeric=True, extra_groups=custom_group), "chart_type": "stacked_bar"},
            {"id": "education", "title": "Education", "table_fn": lambda d, s: _tbl_education(d, base_label=s, numeric=True, extra_groups=custom_group), "chart_type": "stacked_bar"},
            {"id": "occupation", "title": "Occupation", "table_fn": lambda d, s: _tbl_occupation(d, base_label=s, numeric=True, extra_groups=custom_group), "chart_type": "stacked_bar"},
            {"id": "income", "title": "Household Income", "table_fn": lambda d, s: _tbl_income(d, base_label=s, numeric=True, extra_groups=custom_group), "chart_type": "stacked_bar"},
        ],
    },
    {
        "id": "brand_owned",
        "heading": "Brand Owned",
        "anchor": "sec-brand-owned",
        "visible": False,   # replaces today's module-level SHOW_BRAND_OWNED_ONWARD flag — per-GROUP now, not one global switch
        "items": [
            {"id": "brand_owned_cc", "title": "Brand Owned — CC Wise", "table_fn": ..., "chart_type": "stacked_bar", "color": BRAND_OWNED_COLOR},
            {"id": "brand_owned_brand", "kind": "brand_wise", "title": "Brand Owned — Brand Wise", "table_fn": ..., "color": BRAND_OWNED_COLOR},
        ],
    },
    {
        "id": "competitor_cc",
        "heading": "Competitor CC Preference",
        "condition": lambda: segment_value == "Rejector",   # replaces the hand-written `if segment_value == "Rejector":` guard
        "items": [
            {"id": "competitor_cc", "title": "Competitor CC Segment — Rejectors", "table_fn": ..., "chart_type": "stacked_bar", "color": "#FDCB6E"},
        ],
    },
    # ... one entry per remaining group (Buyer Type, Additional+Replaced, Brand Considered,
    #     RE Model Consideration Funnel, Test Ride Intelligence, Brand Resilience,
    #     Post-Cancellation Trajectory, Reasons & Motivations)
]
```

Fields:
- `id` — stable key for widget/session-state namespacing (replaces using the
  human title as the cache key, which today means renaming a title silently
  invalidates cached tables).
- `heading` / `anchor` / `caption` — rendered once per group, before its
  `items` loop (today hand-written per group as separate `st.markdown` calls).
- `condition` — optional callable; group is skipped entirely if it returns
  False. Replaces today's scattered `if segment_value == "Rejector":` /
  `if segment_value == "Cancelled":` guards.
- `visible` — static kill-switch, defaults `True`. Directly replaces the
  existing single `SHOW_BRAND_OWNED_ONWARD = False` flag (`app.py:1546`) —
  but per-group instead of one flag covering 5 unrelated groups at once, so
  a future "hide just Post-Cancellation" ask doesn't require re-threading a
  new flag through the code.
- `items[].kind` — `"section"` (default, renders via `section()`) or
  `"brand_wise"` (renders via `brand_wise_section()`) — the two existing
  renderer functions stay as-is; the registry just picks which one to call.
- Every other `items[]` field (`table_fn`, `chart_type`, `color`,
  `cap_chart`, `brand_filter_labels`, `caption`) maps 1:1 to `section()`'s
  existing parameters — no renderer changes needed, just how it's *invoked*.

## Render loop (replaces ~140 lines of individual call sites)

```python
for group in SEGMENT_SECTIONS:
    if not group.get("visible", True):
        continue
    if "condition" in group and not group["condition"]():
        continue
    st.markdown(f'<div id="{group["anchor"]}"></div>', unsafe_allow_html=True) if group.get("anchor") else None
    st.markdown(f"### {group['heading']}")
    if group.get("caption"):
        st.caption(group["caption"])
    for item in group["items"]:
        if item.get("kind") == "brand_wise":
            brand_wise_section(item["title"], item["table_fn"], item.get("color", accent), caption=item.get("caption"))
        else:
            section(item["title"], item["table_fn"], caption=item.get("caption"),
                    chart_type=item.get("chart_type", "bar"), cap_chart=item.get("cap_chart"),
                    brand_filter_labels=item.get("brand_filter_labels"), color=item.get("color"))
```

**Adding a new section** going forward: append one `items[]` dict to the
relevant group (or a whole new group dict for a new heading) — no new
`st.markdown`/`st.caption`/`if` statements to hand-write, no risk of
forgetting the anchor-div or miscopying a caption from a neighboring section.

## What does NOT change

- `section()` and `brand_wise_section()` themselves — same signatures, same
  caching, same significance-testing, same Overview-vs-segment branching.
  This is purely how they get *called*, not what they do.
- The jump-nav pills (`_nav_pill(...)`) — still hand-written, but could read
  `group["heading"]`/`group["anchor"]` from the same registry in a later
  pass if wanted (not included in this first cut, to keep the change
  bounded).
- Pie summary / hero cards / Reasons & Motivations placeholder — out of
  scope for this registry (Reasons & Motivations has no `section()` call,
  it's a placeholder function; could be folded in later as a third `kind`).

## Risk / rollout plan

This touches `app.py:1409-1546` (all current section call sites) — a
meaningful diff, but mechanical (each existing call becomes one dict
entry; logic inside `section()`/`brand_wise_section()` is untouched). Two
options:

1. **One clean cutover** — replace all ~15 call sites with the registry +
   loop in a single change, verify every segment page (Acceptors/
   Rejectors/Cancelled/Overall) renders identically before/after via
   screenshot diff.
2. **Incremental** — introduce the registry alongside the existing calls for
   ONE group first (e.g. Demographics, the simplest, no conditions), verify,
   then migrate the rest group-by-group over follow-up turns.

Given the currently-hidden groups (Brand Owned onward, `visible: False`)
are dormant, migrating them carries near-zero visual regression risk (nothing
renders either way) — safe to include in the same pass as the live groups.

## Open question for user

Scope confirmation before implementation: migrate **all** groups (including
the currently-hidden Brand Owned/Brand Considered/etc., just re-flagged
`visible: False` in the new shape) in one pass, or start with only the
**live** groups (Demographics, Buyer Type, Additional + Replaced) and leave
the hidden ones as they are today (`SHOW_BRAND_OWNED_ONWARD` flag, untouched)
until they're actually re-enabled?
