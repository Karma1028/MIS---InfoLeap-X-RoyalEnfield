"""Classifies sampled respondent verbatim pairs against Infoleap's own
netting taxonomy (utils/netting_taxonomy.py) via LLM — structured
classification into a FIXED category list, not free clustering. Paired
with utils/verbatim_intel.py's existing free-form intent analysis (a
different, complementary lens on the same data)."""
import json
from utils.ai_providers import call_llm

BATCH_SIZE = 25  # respondents per LLM call — keeps prompt token count
# manageable alongside the taxonomy list, well within Groq's free-tier
# per-request token limits.


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
