"""Classifies sampled respondent verbatim pairs against Infoleap's own
netting taxonomy (utils/netting_taxonomy.py) via LLM — structured
classification into a FIXED category list, not free clustering. Paired
with utils/verbatim_intel.py's existing free-form intent analysis (a
different, complementary lens on the same data)."""
import json
import pandas as pd
from utils.ai_providers import call_llm

BATCH_SIZE = 25  # respondents per LLM call — keeps prompt token count
# manageable alongside the taxonomy list, well within Groq's free-tier
# per-request token limits.

# Distinct from "No match" (a genuine LLM classification decision) —
# marks a batch where the LLM call itself failed (bad/missing API key,
# rate limit, provider outage) so callers/UI can surface it as an error
# instead of silently presenting it as confident "nothing fit" data.
ERROR_CATEGORY = "⚠ Classification unavailable"


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
    if not batch:
        return []
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
        valid_categories = set(taxonomy_flat)
        results = []
        for i in range(len(batch)):
            category = by_index.get(i)
            if category is None:
                # Missing from the response — a truncated batch (e.g.
                # max_tokens cut the JSON array short) is a failed
                # classification, not a "nothing fit" decision. Flagging
                # it ERROR_CATEGORY keeps it distinct from a genuine
                # "No match" the same way a total parse failure already is.
                results.append(ERROR_CATEGORY)
            elif category == "No match" or category in valid_categories:
                results.append(category)
            else:
                # LLM returned a string that isn't in the fixed taxonomy
                # and isn't "No match" — a hallucinated/paraphrased
                # category. Flagging it rather than trusting it verbatim
                # keeps aggregate_by_supernet from minting a fake Supernet
                # bucket that doesn't exist in Infoleap's taxonomy.
                results.append(ERROR_CATEGORY)
        return results
    except Exception:
        # call_llm() never raises on failure (missing key, rate limit,
        # provider down) — it returns a plain error string instead (see
        # utils/ai_providers.py), which fails json.loads and lands here.
        # Without this distinct marker, a failed API call and a genuine
        # "nothing in the taxonomy fits" classification were both
        # indistinguishable "No match" results — silently presenting an
        # outage as confident classification data. See code review,
        # 2026-07-24.
        return [ERROR_CATEGORY] * len(batch)


def classify_verbatims_batch(pairs, taxonomy_flat, provider, model):
    """Classifies `pairs` (list of {"broad_reason", "elaboration"}) against
    `taxonomy_flat` (list of "Supernet > Net" strings from
    flatten_supernet_net()). Dedupes identical text before calling the LLM
    — one classification per UNIQUE text, mapped back to every original
    pair. Returns a list (same length/order as `pairs`) of
    {**pair, "category": "Supernet > Net" | "No match" | ERROR_CATEGORY}
    (ERROR_CATEGORY marks a batch whose LLM call itself failed, distinct
    from a genuine "no taxonomy entry fits" decision)."""
    if not pairs:
        return []
    unique_pairs, index_map = dedupe_pairs(pairs)
    categories_by_unique_index = []
    for start in range(0, len(unique_pairs), BATCH_SIZE):
        batch = unique_pairs[start:start + BATCH_SIZE]
        categories_by_unique_index.extend(_classify_one_batch(batch, taxonomy_flat, provider, model))
    return [
        {**pairs[i], "category": categories_by_unique_index[index_map[i]]}
        for i in range(len(pairs))
    ]


def aggregate_by_supernet(classified_pairs, base_label):
    """Counts classified pairs by their Supernet (top-level category,
    everything before ' > ' in the "category" field) into the SAME
    Base-row + category-rows DataFrame shape every other table in this app
    uses (Unnamed: 0 / All columns) — so it renders directly through
    utils.visuals.treemap_chart() with no adapter needed. Both "No match"
    (a genuine LLM decision that nothing fit) and ERROR_CATEGORY (the LLM
    call itself failed) count toward the base — they're real classification
    attempts — but neither gets its own category row, since neither is a
    real taxonomy match."""
    base_n = len(classified_pairs)
    rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
    if base_n == 0:
        return pd.DataFrame(rows)
    supernet_counts = {}
    for item in classified_pairs:
        category = item.get("category", "No match")
        if category in ("No match", ERROR_CATEGORY):
            continue
        supernet = category.split(" > ")[0]
        supernet_counts[supernet] = supernet_counts.get(supernet, 0) + 1
    for supernet, count in supernet_counts.items():
        rows.append({"Unnamed: 0": supernet, "All": round(count / base_n * 100, 1)})
    return pd.DataFrame(rows)
