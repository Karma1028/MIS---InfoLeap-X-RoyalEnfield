import json
from unittest.mock import patch
from utils.verbatim_classify import dedupe_pairs, classify_verbatims_batch, ERROR_CATEGORY


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
