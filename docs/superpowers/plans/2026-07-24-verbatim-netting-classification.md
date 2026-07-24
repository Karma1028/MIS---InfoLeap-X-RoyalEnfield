# Verbatim Netting Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify respondent verbatim text against Infoleap's own coding taxonomy (the 3 hidden netting sheets in the Masterfile) so the app can show Key Buying Factors / Reasons for Rejection / Reasons for Cancelling category breakdowns that are directly comparable to the live site — via LLM classification into the fixed taxonomy, since no respondent-level linkage exists in the data (confirmed in `docs/superpowers/specs/2026-07-24-verbatim-netting-reproduction-design.md`).

**Architecture:** A new taxonomy loader parses the 3 netting sheets into `{Supernet: [Net, Net, ...]}` maps per segment. A new batched classification function sends the SAME already-sampled verbatim pairs `collect_verbatim_pairs()` produces (capped at 60, same as the existing intent-analysis feature — deliberately NOT scaled up to the full ~4,000 respondents, to keep this affordable on Groq's free tier) to the LLM, asking it to pick the closest `Supernet > Net` for each pair from the fixed list (structured JSON, not free generation). Classification is deduplicated by exact verbatim text before batching, so repeated identical short answers only cost one classification. Results aggregate into the same `Unnamed: 0` / `All`-column DataFrame shape every other table in this app already uses, so it renders through the existing `treemap_chart()` unchanged.

**Tech Stack:** Python, openpyxl (sheet parsing), Streamlit (`st.cache_data`), existing `utils/ai_providers.call_llm`, existing `utils/visuals.treemap_chart`.

**Scope trim (stated explicitly, not silent):** v1 classifies to Supernet+Net level only, not the full ~220-entry leaf Codelist — this matches what the live site's top two display tiers (`+[Top Category]` / `[Mid Category]`) show, keeps the LLM prompt's taxonomy listing short (≈15 Supernets × ~3-5 Nets each, not 220 leaf phrases), and keeps classification scoped to the same ≤60 sampled pairs the rest of the page already uses. Leaf-level Codelist matching and scaling beyond 60 respondents are explicitly out of scope for this plan — flag to the user as a follow-up if they want deeper granularity later.

---

### Task 1: Taxonomy loader

**Files:**
- Create: `utils/netting_taxonomy.py`
- Test: `tests/test_netting_taxonomy.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_netting_taxonomy.py
import pandas as pd
from unittest.mock import patch, MagicMock
from utils.netting_taxonomy import load_netting_taxonomy, SEGMENT_SHEETS, flatten_supernet_net


def _fake_sheet_rows():
    return [
        ("Supernet", "Net", "Sub-net", "Codelist", "Codes"),
        ("Visual Appearance", "Body Design", "Front profile", "Liked the round shaped headlight design", "002"),
        ("Visual Appearance", "Design Language", "Design Language", "Aggressive looks", "011"),
        ("Overall price", "Value for money", "Value for money", "Priced reasonably", "045"),
    ]


def test_load_netting_taxonomy_groups_by_supernet_then_net():
    mock_ws = MagicMock()
    mock_ws.iter_rows.return_value = _fake_sheet_rows()
    mock_wb = MagicMock()
    mock_wb.__getitem__.return_value = mock_ws
    with patch("utils.netting_taxonomy.openpyxl.load_workbook", return_value=mock_wb):
        taxonomy = load_netting_taxonomy("fake_path.xlsx", "MQ2a+MQ2b_KBF")
    assert taxonomy == {
        "Visual Appearance": ["Body Design", "Design Language"],
        "Overall price": ["Value for money"],
    }


def test_load_netting_taxonomy_dedupes_repeated_net_within_supernet():
    rows = [
        ("Supernet", "Net", "Sub-net", "Codelist", "Codes"),
        ("Visual Appearance", "Body Design", "Front profile", "Liked headlight", "001"),
        ("Visual Appearance", "Body Design", "Rear profile", "Liked tail light", "002"),
    ]
    mock_ws = MagicMock()
    mock_ws.iter_rows.return_value = rows
    mock_wb = MagicMock()
    mock_wb.__getitem__.return_value = mock_ws
    with patch("utils.netting_taxonomy.openpyxl.load_workbook", return_value=mock_wb):
        taxonomy = load_netting_taxonomy("fake_path.xlsx", "MQ2a+MQ2b_KBF")
    assert taxonomy == {"Visual Appearance": ["Body Design"]}


def test_segment_sheets_maps_all_three_segments():
    assert set(SEGMENT_SHEETS.keys()) == {"Acceptor", "Rejector", "Cancelled"}
    assert SEGMENT_SHEETS["Acceptor"] == "MQ2a+MQ2b_KBF"
    assert SEGMENT_SHEETS["Rejector"] == "MQ3a+MQ3b_Rejecter"
    assert SEGMENT_SHEETS["Cancelled"] == "MQ3a+MQ3b_Booked and cancelled"


def test_flatten_supernet_net_produces_readable_list():
    taxonomy = {"Visual Appearance": ["Body Design", "Design Language"], "Overall price": ["Value for money"]}
    flat = flatten_supernet_net(taxonomy)
    assert flat == [
        "Visual Appearance > Body Design",
        "Visual Appearance > Design Language",
        "Overall price > Value for money",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_netting_taxonomy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'utils.netting_taxonomy'`

- [ ] **Step 3: Write the implementation**

```python
# utils/netting_taxonomy.py
"""Loads Infoleap's own manual coding taxonomy for open-ended verbatim
questions (Key Buying Factors / Reasons for Rejection / Reasons for
Cancelling) from the 3 hidden reference sheets in the Masterfile workbook.

These sheets (`Supernet | Net | Sub-net | Codelist | Codes`) are a real
market-research netting scheme — almost certainly how the live Infoleap
dashboard's Reasons sections were actually coded (confirmed via live-site
scrape structure analysis, 2026-07-24: same 3-level Top/Mid/leaf hierarchy).

No respondent-level linkage to these codes exists anywhere in the Masterfile
(checked directly, 2026-07-24 — see docs/superpowers/specs/2026-07-24-
verbatim-netting-reproduction-design.md) — these sheets are reference-only.
`utils/verbatim_intel.py` uses this taxonomy to classify sampled respondent
verbatim text via LLM, approximating (not exactly reproducing) the live
site's category breakdowns."""
import openpyxl
from utils.data_engine import MASTERFILE_PATH

SEGMENT_SHEETS = {
    "Acceptor": "MQ2a+MQ2b_KBF",
    "Rejector": "MQ3a+MQ3b_Rejecter",
    "Cancelled": "MQ3a+MQ3b_Booked and cancelled",
}


def load_netting_taxonomy(masterfile_path, sheet_name):
    """Returns {Supernet: [Net, Net, ...]} — Sub-net and Codelist/Codes
    columns are dropped (v1 classifies to Supernet+Net only, see plan's
    'Scope trim' note). Net names deduplicated within each Supernet,
    insertion order preserved."""
    wb = openpyxl.load_workbook(masterfile_path, read_only=True, data_only=True)
    ws = wb[sheet_name]
    taxonomy = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # header row: Supernet, Net, Sub-net, Codelist, Codes
        supernet, net = row[0], row[1]
        if not supernet or not net:
            continue
        nets = taxonomy.setdefault(supernet, [])
        if net not in nets:
            nets.append(net)
    return taxonomy


def flatten_supernet_net(taxonomy):
    """['Supernet > Net', ...] — the exact strings shown to the LLM as its
    fixed classification target list."""
    return [f"{supernet} > {net}" for supernet, nets in taxonomy.items() for net in nets]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_netting_taxonomy.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add utils/netting_taxonomy.py tests/test_netting_taxonomy.py
git commit -m "Add netting taxonomy loader for verbatim classification"
```

---

### Task 2: Batched LLM classification with text-level dedup caching

**Files:**
- Create: `utils/verbatim_classify.py`
- Test: `tests/test_verbatim_classify.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_verbatim_classify.py
import json
from unittest.mock import patch
from utils.verbatim_classify import dedupe_pairs, classify_verbatims_batch


def test_dedupe_pairs_collapses_identical_text_keeps_first_occurrence_order():
    pairs = [
        {"broad_reason": "Good looks", "elaboration": "Nice design"},
        {"broad_reason": "Price is high", "elaboration": None},
        {"broad_reason": "Good looks", "elaboration": "Nice design"},  # exact dup
    ]
    unique, index_map = dedupe_pairs(pairs)
    assert unique == [
        {"broad_reason": "Good looks", "elaboration": "Nice design"},
        {"broad_reason": "Price is high", "elaboration": None},
    ]
    # index_map maps each ORIGINAL pair index -> its position in `unique`
    assert index_map == [0, 1, 0]


def test_classify_verbatims_batch_maps_llm_json_back_to_all_original_pairs():
    pairs = [
        {"broad_reason": "Good looks", "elaboration": "Nice design"},
        {"broad_reason": "Price is high", "elaboration": None},
        {"broad_reason": "Good looks", "elaboration": "Nice design"},
    ]
    taxonomy_flat = ["Visual Appearance > Body Design", "Overall price > Value for money"]
    fake_llm_response = json.dumps({
        "classifications": [
            {"index": 0, "category": "Visual Appearance > Body Design"},
            {"index": 1, "category": "Overall price > Value for money"},
        ]
    })
    with patch("utils.verbatim_classify.call_llm", return_value=fake_llm_response) as mock_call:
        result = classify_verbatims_batch(pairs, taxonomy_flat, provider="groq", model=None)
    assert mock_call.call_count == 1  # only 2 unique pairs -> 1 batch call, not 3
    assert len(result) == 3  # one classification per ORIGINAL pair, dup included
    assert result[0]["category"] == "Visual Appearance > Body Design"
    assert result[2]["category"] == "Visual Appearance > Body Design"  # dup got same category
    assert result[1]["category"] == "Overall price > Value for money"


def test_classify_verbatims_batch_handles_no_match():
    pairs = [{"broad_reason": "asdkjaslkdj gibberish", "elaboration": None}]
    taxonomy_flat = ["Visual Appearance > Body Design"]
    fake_llm_response = json.dumps({"classifications": [{"index": 0, "category": "No match"}]})
    with patch("utils.verbatim_classify.call_llm", return_value=fake_llm_response):
        result = classify_verbatims_batch(pairs, taxonomy_flat, provider="groq", model=None)
    assert result[0]["category"] == "No match"


def test_classify_verbatims_batch_handles_malformed_llm_json_gracefully():
    pairs = [{"broad_reason": "Good looks", "elaboration": None}]
    taxonomy_flat = ["Visual Appearance > Body Design"]
    with patch("utils.verbatim_classify.call_llm", return_value="not valid json"):
        result = classify_verbatims_batch(pairs, taxonomy_flat, provider="groq", model=None)
    assert result[0]["category"] == "No match"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_verbatim_classify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'utils.verbatim_classify'`

- [ ] **Step 3: Write the implementation**

```python
# utils/verbatim_classify.py
"""Classifies sampled respondent verbatim pairs against Infoleap's own
netting taxonomy (utils/netting_taxonomy.py) via LLM — structured
classification into a FIXED category list, not free clustering. Paired
with utils/verbatim_intel.py's existing free-form intent analysis (a
different, complementary lens on the same data)."""
import json
from utils.ai_providers import call_llm

BATCH_SIZE = 25  # respondents per LLM call — keeps prompt token count
# manageable alongside the ~15-60 entry taxonomy list, well within Groq's
# free-tier per-request token limits.


def dedupe_pairs(pairs):
    """Collapses pairs with IDENTICAL (broad_reason, elaboration) text —
    many respondents give the same short answer verbatim (e.g. "Good
    looks", "Price is high") and only need classifying once. Returns
    (unique_pairs, index_map) where index_map[i] is unique_pairs' index
    for original pairs[i]."""
    seen = {}
    unique_pairs = []
    index_map = []
    for pair in pairs:
        key = (pair.get("broad_reason"), pair.get("elaboration"))
        if key not in seen:
            seen[key] = len(unique_pairs)
            unique_pairs.append(pair)
        index_map.append(seen[key])
    return unique_pairs, index_map


def _classify_one_batch(batch, taxonomy_flat, provider, model):
    taxonomy_list = "\n".join(f"- {c}" for c in taxonomy_flat)
    prompt = f"""You are classifying Royal Enfield survey respondent answers into a
FIXED market-research coding taxonomy. Do NOT invent new categories — pick
the single closest match from the list below for each answer, or "No match"
if genuinely nothing fits.

Taxonomy (Supernet > Net):
{taxonomy_list}

Respondent answers to classify (indexed):
{json.dumps([{"index": i, **p} for i, p in enumerate(batch)], ensure_ascii=False)}

Respond with ONLY valid JSON in this exact shape:
{{"classifications": [{{"index": 0, "category": "exact taxonomy string from the list above, or 'No match'"}}]}}
"""
    content = call_llm(
        provider, model,
        "You are a precise survey-response classifier. Output ONLY valid JSON, no markdown fences.",
        prompt, temperature=0.1, max_tokens=1500, json_mode=True,
    )
    try:
        parsed = json.loads(content)
        by_index = {c["index"]: c.get("category", "No match") for c in parsed.get("classifications", [])}
    except Exception:
        by_index = {}
    return [by_index.get(i, "No match") for i in range(len(batch))]


def classify_verbatims_batch(pairs, taxonomy_flat, provider, model):
    """Classifies `pairs` (list of {"broad_reason", "elaboration"}) against
    `taxonomy_flat` (list of "Supernet > Net" strings from
    flatten_supernet_net()). Dedupes identical text before calling the LLM
    — one classification per UNIQUE text, mapped back to every original
    pair. Returns a list (same length/order as `pairs`) of
    {**pair, "category": "Supernet > Net" | "No match"}."""
    unique_pairs, index_map = dedupe_pairs(pairs)
    categories_by_unique_index = []
    for start in range(0, len(unique_pairs), BATCH_SIZE):
        batch = unique_pairs[start:start + BATCH_SIZE]
        categories_by_unique_index.extend(_classify_one_batch(batch, taxonomy_flat, provider, model))
    return [
        {**pairs[i], "category": categories_by_unique_index[index_map[i]]}
        for i in range(len(pairs))
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_verbatim_classify.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add utils/verbatim_classify.py tests/test_verbatim_classify.py
git commit -m "Add batched LLM verbatim classification against netting taxonomy"
```

---

### Task 3: Aggregation into the app's standard table shape

**Files:**
- Modify: `utils/verbatim_classify.py`
- Test: `tests/test_verbatim_classify.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_verbatim_classify.py
from utils.verbatim_classify import aggregate_by_supernet


def test_aggregate_by_supernet_produces_base_plus_category_rows():
    classified = [
        {"broad_reason": "a", "elaboration": None, "category": "Visual Appearance > Body Design"},
        {"broad_reason": "b", "elaboration": None, "category": "Visual Appearance > Design Language"},
        {"broad_reason": "c", "elaboration": None, "category": "Overall price > Value for money"},
        {"broad_reason": "d", "elaboration": None, "category": "No match"},
    ]
    df = aggregate_by_supernet(classified, base_label="Acceptor")
    assert list(df.columns) == ["Unnamed: 0", "All"]
    base_row = df.iloc[0]
    assert base_row["Unnamed: 0"] == "Base : Total_Acceptor"
    assert base_row["All"] == 4  # all 4 classified pairs, including "No match", count toward base
    cat_rows = {row["Unnamed: 0"]: row["All"] for _, row in df.iloc[1:].iterrows()}
    # 2 of 4 pairs -> Visual Appearance = 50%, 1 of 4 -> Overall price = 25%
    assert cat_rows["Visual Appearance"] == 50.0
    assert cat_rows["Overall price"] == 25.0
    assert "No match" not in cat_rows  # unmatched pairs excluded from category rows, kept only in base


def test_aggregate_by_supernet_empty_input_returns_zero_base():
    df = aggregate_by_supernet([], base_label="Acceptor")
    assert df.iloc[0]["All"] == 0
    assert len(df) == 1  # base row only, no category rows
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_verbatim_classify.py -v -k aggregate`
Expected: FAIL with `ImportError: cannot import name 'aggregate_by_supernet'`

- [ ] **Step 3: Write the implementation**

```python
# append to utils/verbatim_classify.py
import pandas as pd


def aggregate_by_supernet(classified_pairs, base_label):
    """Counts classified pairs by their Supernet (top-level category,
    everything before ' > ' in the "category" field) into the SAME
    Base-row + category-rows DataFrame shape every other table in this app
    uses (Unnamed: 0 / All columns) — so it renders directly through
    utils.visuals.treemap_chart() with no adapter needed. "No match"
    pairs count toward the base (they were real respondents) but don't
    get their own category row."""
    base_n = len(classified_pairs)
    rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
    if base_n == 0:
        return pd.DataFrame(rows)
    supernet_counts = {}
    for item in classified_pairs:
        category = item.get("category", "No match")
        if category == "No match":
            continue
        supernet = category.split(" > ")[0]
        supernet_counts[supernet] = supernet_counts.get(supernet, 0) + 1
    for supernet, count in supernet_counts.items():
        rows.append({"Unnamed: 0": supernet, "All": round(count / base_n * 100, 1)})
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_verbatim_classify.py -v`
Expected: PASS (6 tests total in this file)

- [ ] **Step 5: Commit**

```bash
git add utils/verbatim_classify.py tests/test_verbatim_classify.py
git commit -m "Add Supernet-level aggregation for classified verbatims"
```

---

### Task 4: Wire into the Verbatim Intelligence page

**Files:**
- Modify: `utils/verbatim_intel.py`

- [ ] **Step 1: Read current end-of-function state to confirm insertion point**

Run: `grep -n "Raw sampled verbatim pairs" "utils/verbatim_intel.py"`
Expected: shows the `with st.expander("Raw sampled verbatim pairs...")` block near the end of `render_verbatim_intelligence_page()` — new section goes directly above it.

- [ ] **Step 2: Add the imports**

At the top of `utils/verbatim_intel.py`, alongside the existing imports:

```python
from utils.netting_taxonomy import SEGMENT_SHEETS, load_netting_taxonomy, flatten_supernet_net
from utils.verbatim_classify import classify_verbatims_batch, aggregate_by_supernet
from utils.visuals import treemap_chart, PLOTLY_CONFIG
from utils.data_engine import MASTERFILE_PATH
```

- [ ] **Step 3: Add a cached taxonomy loader wrapper**

Directly below the existing `analyze_intent()` function in `utils/verbatim_intel.py`:

```python
@st.cache_data(show_spinner=False)
def _cached_taxonomy(segment):
    sheet_name = SEGMENT_SHEETS[segment]
    return load_netting_taxonomy(MASTERFILE_PATH, sheet_name)


@st.cache_data(show_spinner=False)
def _cached_classification(segment, pairs_json, taxonomy_flat_json, provider, model):
    """Cached by exact (segment, pairs, taxonomy, provider, model) — same
    re-render-doesn't-re-spend-quota pattern as analyze_intent() above."""
    pairs = json.loads(pairs_json)
    taxonomy_flat = json.loads(taxonomy_flat_json)
    return classify_verbatims_batch(pairs, taxonomy_flat, provider, model)
```

- [ ] **Step 4: Add the new section to `render_verbatim_intelligence_page()`**

Insert directly above the existing `with st.expander("Raw sampled verbatim pairs (for transparency)"):` line:

```python
    st.markdown("#### Reproduce Live Site Categories")
    st.caption(
        "Classifies the same sampled answer-pairs above against Infoleap's own coding "
        "taxonomy (the hidden netting sheets behind the live dashboard's Key Buying "
        "Factors / Reasons sections) — an approximation via AI classification, not an "
        "exact reproduction, since no respondent-level linkage to that taxonomy exists "
        "in the raw data. Separate button from Intent Analysis above: different LLM "
        "call, different cost."
    )
    if st.button("Classify Against Live Site Taxonomy", type="secondary"):
        taxonomy = _cached_taxonomy(segment)
        taxonomy_flat = flatten_supernet_net(taxonomy)
        with st.spinner(f"Asking {provider.title()} to classify {len(pairs)} answers against {len(taxonomy_flat)} categories..."):
            classified = _cached_classification(
                segment, json.dumps(pairs, ensure_ascii=False),
                json.dumps(taxonomy_flat), provider, model,
            )
        agg_df = aggregate_by_supernet(classified, base_label=segment)
        if len(agg_df) <= 1:
            st.info("No classified categories to show (all answers were 'No match' or sample was empty).")
        else:
            fig = treemap_chart(agg_df, f"{broad_label} — Category Breakdown")
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG,
                             key=f"netting_treemap_{segment}_{choice_idx}")
            _no_match_n = sum(1 for c in classified if c.get("category") == "No match")
            if _no_match_n:
                st.caption(f"{_no_match_n} of {len(classified)} sampled answers didn't match any taxonomy category.")

```

- [ ] **Step 5: Syntax check**

Run: `python -m py_compile utils/verbatim_intel.py`
Expected: no output (clean compile)

- [ ] **Step 6: Manual verification in the running app**

Restart the app (`streamlit run app.py --server.port 8501`), log in, navigate to Verbatim Intelligence (AI), select a segment + question pair, click "Classify Against Live Site Taxonomy", confirm:
- A treemap renders (no exception box)
- A "No match" caption appears if applicable
- Re-clicking without changing filters doesn't re-trigger a spinner (cache hit)

- [ ] **Step 7: Commit**

```bash
git add utils/verbatim_intel.py
git commit -m "Wire netting-taxonomy classification into Verbatim Intelligence page"
```

---

### Task 5: Update stale scope-lock comments

**Files:**
- Modify: `utils/verbatim_intel.py:1-14` (module docstring)

- [ ] **Step 1: Update the module docstring**

The current docstring says "This does NOT attempt to reproduce the live dashboard's numbers" — no longer fully true now that the netting-classification section exists. Replace the docstring's second paragraph:

```python
"""
AI Verbatim Intent Intelligence — an explicit ADD-ON feature, outside the
original scope of replicating Infoleap's live dashboard. User request
(2026-06-18): go deeper than Infoleap's own KBF/Reasons treatment by joining
each respondent's broad reason with their follow-up elaboration across
multiple question pairs, and asking an LLM to dissect the underlying intent
(not just bucket keywords) — using only free Groq models, per instruction.

The free-form Intent Analysis (analyze_intent(), anchored to the 4 field-
methodology buckets since 2026-07-24) genuinely does NOT attempt to
reproduce the live dashboard's numbers. The separate "Reproduce Live Site
Categories" section (added 2026-07-24) DOES attempt an approximation — it
classifies sampled verbatims against Infoleap's own netting taxonomy (the
hidden reference sheets in the Masterfile, see utils/netting_taxonomy.py)
via LLM classification, since no respondent-level linkage to that taxonomy
survives in the raw data (confirmed via direct column check — see
docs/superpowers/specs/2026-07-24-verbatim-netting-reproduction-design.md).
This is an AI-driven approximation, not a deterministic replication — it
will not match the live site's exact percentages.

Layered on top of the raw verbatim text columns that exist in the
Masterfile (mq2a/mq2b for "why bought" + "what liked", mq2c/mq2d for "why
considered RE" [Rejector/Cancelled], mq3a/mq3b for "why rejected/cancelled"
+ "what disliked").
"""
```

- [ ] **Step 2: Syntax check**

Run: `python -m py_compile utils/verbatim_intel.py`
Expected: no output

- [ ] **Step 3: Commit**

```bash
git add utils/verbatim_intel.py
git commit -m "Update verbatim_intel.py docstring to reflect netting-classification addition"
```

---

## Explicitly out of scope for this plan (flag to user if wanted later)

- Leaf-level `Codelist` classification (v1 stops at Supernet+Net)
- Scaling classification beyond the existing ≤60-pair sample cap
- Net-level (Mid Category) drill-down chart — only Supernet-level (Top Category) treemap is built
- Persisting classification results across sessions (each run re-classifies; only within-session `st.cache_data` avoids re-spending quota on the exact same inputs)
