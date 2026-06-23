"""
AI Verbatim Intent Intelligence — an explicit ADD-ON feature, outside the
original scope of replicating Infoleap's live dashboard. User request
(2026-06-18): go deeper than Infoleap's own KBF/Reasons treatment by joining
each respondent's broad reason with their follow-up elaboration across
multiple question pairs, and asking an LLM to dissect the underlying intent
(not just bucket keywords) — using only free Groq models, per instruction.

This does NOT attempt to reproduce the live dashboard's numbers. It is a
genuinely new capability layered on top of the raw verbatim text columns
that exist in the Masterfile (mq2a/mq2b for "why bought" + "what liked",
mq2c/mq2d for "why considered RE" [Rejector/Cancelled], mq3a/mq3b for
"why rejected/cancelled" + "what disliked").
"""
import json
import re
import streamlit as st
from utils.ai_providers import call_llm, get_active_provider

QUESTION_PAIRS = {
    "Acceptor": [
        ("Why bought (broad reason)", "What they specifically liked", "mq2a", "mq2b"),
    ],
    "Rejector": [
        ("Why they considered RE first", "What they liked about RE", "mq2c", "mq2d"),
        ("Why they didn't buy RE", "What exactly they disliked", "mq3a", "mq3b"),
    ],
    "Cancelled": [
        ("Why they considered RE first", "What they liked about RE", "mq2c", "mq2d"),
        ("Why they cancelled the booking", "What exactly they disliked", "mq3a", "mq3b"),
    ],
}

JUNK_VALUES = {"no", "na", "n/a", "none", "nil", "nothing", "ok", "okay", "-", "nan"}


def _clean(val):
    if val is None:
        return None
    text = str(val).strip()
    if not text or text.lower() in JUNK_VALUES:
        return None
    return re.sub(r"\s+", " ", text)


def collect_verbatim_pairs(df, broad_prefix, specific_prefix, max_pairs=60):
    """Joins each respondent's broad-reason verbatim with their follow-up
    elaboration across the 3 ranked-reason slots (_1/_2/_3), returns a list
    of (broad, specific) text pairs with junk/placeholder answers dropped."""
    pairs = []
    for rank in (1, 2, 3):
        broad_col = f"{broad_prefix}_{rank}_dis"
        specific_col = f"{specific_prefix}_{rank}"
        if broad_col not in df.columns or specific_col not in df.columns:
            continue
        sub = df[[broad_col, specific_col]].dropna(how="all")
        for _, row in sub.iterrows():
            broad = _clean(row[broad_col])
            specific = _clean(row[specific_col])
            if broad or specific:
                pairs.append({"broad_reason": broad, "elaboration": specific})
            if len(pairs) >= max_pairs:
                return pairs
    return pairs


@st.cache_data(show_spinner=False)
def analyze_intent(segment, pair_label, pairs_json, provider, model):
    """Calls the selected AI provider once per (segment, question-pair,
    sample, provider, model) combination — cached so re-rendering the page
    doesn't re-spend API quota."""
    pairs = json.loads(pairs_json)
    if not pairs:
        return {"themes": [], "error": "No usable verbatim text for this question pair (mostly blank or placeholder answers)."}

    prompt = f"""You are a qualitative consumer-research analyst studying Royal Enfield
motorcycle buyers in the "{segment}" segment, for the question pair: "{pair_label}".

Below are {len(pairs)} respondent answer-pairs. Each pair has a short broad
reason and (if given) a follow-up elaboration explaining it in more detail.
Many are in Hindi-English mixed colloquial text — interpret them in context.

Your job is NOT to just count keywords. Dissect the underlying INTENT behind
each cluster of similar answers — is it about status/identity, practical
function, emotional attachment, financial calculation, social influence, or
something else? Group into 4-6 distinct intent clusters.

Respond with ONLY valid JSON in this exact shape:
{{"themes": [
  {{"intent_label": "short name for the underlying intent (not just the surface topic)",
    "motivation_type": "one of: Functional, Emotional, Social/Status, Financial, Practical",
    "share_estimate_pct": "rough % of the sample showing this intent",
    "explanation": "1-2 sentences on WHY this is the underlying intent, referencing the broad+elaboration pattern",
    "example_quotes": ["1-2 representative quotes from the data, verbatim"]
  }}
]}}

Respondent answer-pairs:
{json.dumps(pairs, ensure_ascii=False)}
"""
    content = call_llm(
        provider, model,
        "You are a precise qualitative researcher. Output ONLY valid JSON, no markdown fences.",
        prompt, temperature=0.3, max_tokens=1500, json_mode=True,
    )
    try:
        return json.loads(content)
    except Exception as e:
        return {"themes": [], "error": f"{provider.title()} call failed or returned non-JSON: {e}. Raw: {content[:300]}"}


def render_verbatim_intelligence_page(engine):
    st.markdown("<h1>Verbatim Intelligence (AI)</h1>", unsafe_allow_html=True)
    provider = get_active_provider()
    model = st.session_state.get("or_model_choice") if provider == "openrouter" else None
    st.caption(
        "Beyond Infoleap's live dashboard scope — joins each respondent's broad reason with their "
        "follow-up elaboration and asks an LLM to dissect the underlying intent (status, emotional, "
        f"functional, financial, social), not just count keywords. Currently using **{provider.title()}** "
        "(change in Settings). Not a replication of the live site's numbers."
    )

    st.sidebar.markdown("### Verbatim Filters")
    segment = st.sidebar.selectbox("Segment", ["Acceptor", "Rejector", "Cancelled"], key="verbatim_segment")

    df = engine.filter_df(segment=segment)
    st.metric("Respondents in segment", f"{len(df):,}")

    pair_options = QUESTION_PAIRS[segment]
    pair_labels = [f"{b} → {s}" for b, s, _, _ in pair_options]
    choice_idx = st.selectbox("Question pair to analyze", range(len(pair_options)), format_func=lambda i: pair_labels[i])
    broad_label, specific_label, broad_prefix, specific_prefix = pair_options[choice_idx]

    pairs = collect_verbatim_pairs(df, broad_prefix, specific_prefix)
    st.caption(f"Sampled {len(pairs)} respondent answer-pairs for: **{broad_label} → {specific_label}**")

    if st.button("Run AI Intent Analysis", type="primary"):
        with st.spinner(f"Asking {provider.title()} to dissect respondent intent..."):
            result = analyze_intent(segment, pair_labels[choice_idx], json.dumps(pairs, ensure_ascii=False), provider, model)

        if result.get("error"):
            st.warning(result["error"])
        themes = result.get("themes", [])
        if not themes:
            st.info("No themes returned.")
        for theme in themes:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{theme.get('intent_label', 'Unlabeled')}**  \n_{theme.get('motivation_type', '')}_")
                c2.metric("Share", theme.get("share_estimate_pct", "?"))
                st.caption(theme.get("explanation", ""))
                for q in theme.get("example_quotes", []):
                    st.markdown(f"> {q}")

    with st.expander("Raw sampled verbatim pairs (for transparency)"):
        st.json(pairs[:20])
