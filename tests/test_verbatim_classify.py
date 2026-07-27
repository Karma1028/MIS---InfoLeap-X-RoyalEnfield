import json
from unittest.mock import patch
from utils.verbatim_classify import dedupe_pairs, classify_verbatims_batch, ERROR_CATEGORY, aggregate_by_supernet


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


def test_classify_verbatims_batch_flags_malformed_llm_json_as_error_not_no_match():
    # Distinct from "No match" (a genuine LLM decision) — unparseable
    # output means the classification itself never happened, so it must
    # be visibly distinguishable, not silently folded into "No match".
    pairs = [{"broad_reason": "Good looks", "elaboration": None}]
    taxonomy_flat = ["Visual Appearance > Body Design"]
    with patch("utils.verbatim_classify.call_llm", return_value="not valid json"):
        result = classify_verbatims_batch(pairs, taxonomy_flat, provider="groq", model=None)
    assert result[0]["category"] == ERROR_CATEGORY


def test_classify_verbatims_batch_flags_call_llm_failure_string_as_error():
    # call_llm() never raises on failure (missing key, provider down) —
    # it returns a plain error string instead (see utils/ai_providers.py).
    # That string fails json.loads just like malformed JSON does, and
    # must be flagged the same way, not silently reported as "No match".
    pairs = [{"broad_reason": "Good looks", "elaboration": None}]
    taxonomy_flat = ["Visual Appearance > Body Design"]
    with patch("utils.verbatim_classify.call_llm", return_value="No Groq API key saved — add one under Settings."):
        result = classify_verbatims_batch(pairs, taxonomy_flat, provider="groq", model=None)
    assert result[0]["category"] == ERROR_CATEGORY


def test_classify_verbatims_batch_flags_missing_index_as_error_not_no_match():
    # LLM response parses fine but is missing an index (e.g. max_tokens
    # truncated the JSON array mid-batch) -- a failed classification for
    # that item, not a genuine "nothing fit" decision.
    pairs = [
        {"broad_reason": "Good looks", "elaboration": None},
        {"broad_reason": "Too expensive", "elaboration": None},
    ]
    taxonomy_flat = ["Visual Appearance > Body Design", "Overall price > Value for money"]
    fake_llm_response = json.dumps({
        "classifications": [{"index": 0, "category": "Visual Appearance > Body Design"}]
    })
    with patch("utils.verbatim_classify.call_llm", return_value=fake_llm_response):
        result = classify_verbatims_batch(pairs, taxonomy_flat, provider="groq", model=None)
    assert result[0]["category"] == "Visual Appearance > Body Design"
    assert result[1]["category"] == ERROR_CATEGORY


def test_classify_verbatims_batch_flags_hallucinated_category_as_error():
    # LLM returns a category string that isn't "No match" and isn't in
    # the fixed taxonomy list it was given -- must not be trusted verbatim,
    # since aggregate_by_supernet would mint a fake Supernet bucket from it.
    pairs = [{"broad_reason": "Good looks", "elaboration": None}]
    taxonomy_flat = ["Visual Appearance > Body Design"]
    fake_llm_response = json.dumps({
        "classifications": [{"index": 0, "category": "Made Up Category > Not Real"}]
    })
    with patch("utils.verbatim_classify.call_llm", return_value=fake_llm_response):
        result = classify_verbatims_batch(pairs, taxonomy_flat, provider="groq", model=None)
    assert result[0]["category"] == ERROR_CATEGORY


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


def test_aggregate_by_supernet_excludes_error_category_from_category_rows():
    from utils.verbatim_classify import ERROR_CATEGORY
    classified = [
        {"broad_reason": "a", "elaboration": None, "category": "Visual Appearance > Body Design"},
        {"broad_reason": "b", "elaboration": None, "category": ERROR_CATEGORY},
    ]
    df = aggregate_by_supernet(classified, base_label="Acceptor")
    base_row = df.iloc[0]
    assert base_row["All"] == 2  # ERROR_CATEGORY items still count toward base
    cat_rows = {row["Unnamed: 0"]: row["All"] for _, row in df.iloc[1:].iterrows()}
    assert ERROR_CATEGORY not in cat_rows  # errors excluded from category rows, same as "No match"
    assert cat_rows["Visual Appearance"] == 50.0


def test_aggregate_by_supernet_empty_input_returns_zero_base():
    df = aggregate_by_supernet([], base_label="Acceptor")
    assert df.iloc[0]["All"] == 0
    assert len(df) == 1  # base row only, no category rows
