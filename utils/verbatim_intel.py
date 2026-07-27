"""
AI Verbatim Intent Intelligence — an explicit ADD-ON feature, outside the
original scope of replicating Infoleap's live dashboard. User request
(2026-06-18): go deeper than Infoleap's own KBF/Reasons treatment by joining
each respondent's broad reason with their follow-up elaboration across
multiple question pairs, and asking an LLM to dissect the underlying intent
(not just bucket keywords) — using only free Groq models, per instruction.

The free-form Intent Analysis section (bucketed into the fieldwork's own
Product/Price/Dealership/Personal framing) does NOT attempt to reproduce
the live dashboard's numbers — it is a genuinely new capability layered on
top of the raw verbatim text columns that exist in the Masterfile
(mq2a/mq2b for "why bought" + "what liked", mq2c/mq2d for "why considered
RE" [Rejector/Cancelled], mq3a/mq3b for "why rejected/cancelled" + "what
disliked").

A second, separate section ("Reproduce Live Site Categories") shows the
live dashboard's REAL Key Buying Factors / Reasons numbers — a
deterministic, exact reproduction via each respondent's own Infoleap-
assigned netting code (DataEngine.reasons_table(), see that method's
docstring for the validation against scraped live-site numbers). This
used to be an LLM classification over sampled verbatim TEXT, believed
necessary because "no respondent-level linkage exists" — that was wrong
(corrected 2026-07-27, see utils/netting_taxonomy.py's docstring) — the
LLM approximation (utils/verbatim_classify.py) is no longer used here.
"""
import json
import re
import streamlit as st
from utils.ai_providers import call_llm, get_active_provider
from utils.visuals import render_chart_with_table

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

# Per 2026-07-24 research: these questions were fielded with 4 interviewer-
# provided prompt buckets already baked into the field methodology (per
# data/MIS Questionnaire_31072025_Updated.docx — interviewers read these
# prompts when a respondent gave <3 reasons or a vague answer). The AI
# clustering below previously ignored this and invented its own 4-6
# categories from scratch each time, which meant Acceptor "why bought"
# themes and Rejector "why not bought" themes weren't on a comparable
# axis. Anchoring both to the SAME 4 buckets (positive framing for mq2*
# "why considered/liked" pairs, negative framing for mq3* "why
# rejected/disliked" pairs) makes segment-to-segment comparison meaningful
# and grounds the AI's output in how the fieldwork was actually designed,
# instead of free association.
POSITIVE_BUCKETS = [
    "Product (design, features, performance, build quality)",
    "Price (value for money, affordability, financing ease)",
    "Dealership (staff, test ride, booking experience)",
    "Personal (funds ready, loan approved, family/social encouragement)",
]
NEGATIVE_BUCKETS = [
    "Product (design, features, performance, or quality concerns)",
    "Price (too expensive, poor perceived value, financing difficulty)",
    "Dealership (waiting period, test-ride issues, booking issues, model unavailable)",
    "Personal (financial constraints, loan rejected/delayed, family/social pressure against)",
]


def _bucket_frame_for(broad_prefix):
    """mq2* pairs ask why a respondent considered/liked RE (positive
    framing); mq3* pairs ask why they rejected/disliked it (negative
    framing) — same 4 underlying axes (Product/Price/Dealership/Personal),
    opposite valence."""
    return NEGATIVE_BUCKETS if broad_prefix.startswith("mq3") else POSITIVE_BUCKETS


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
def analyze_intent(segment, pair_label, pairs_json, provider, model, bucket_frame_json):
    """Calls the selected AI provider once per (segment, question-pair,
    sample, provider, model, bucket_frame) combination — cached so
    re-rendering the page doesn't re-spend API quota.

    bucket_frame_json: JSON-encoded list of the 4 field-methodology
    buckets (POSITIVE_BUCKETS or NEGATIVE_BUCKETS) this question pair was
    actually fielded against — see module docstring note above those
    constants for why this replaces free-form clustering."""
    pairs = json.loads(pairs_json)
    buckets = json.loads(bucket_frame_json)
    if not pairs:
        return {"themes": [], "error": "No usable verbatim text for this question pair (mostly blank or placeholder answers)."}

    bucket_list = "\n".join(f"- {b}" for b in buckets)
    prompt = f"""You are a qualitative consumer-research analyst studying Royal Enfield
motorcycle buyers in the "{segment}" segment, for the question pair: "{pair_label}".

Below are {len(pairs)} respondent answer-pairs. Each pair has a short broad
reason and (if given) a follow-up elaboration explaining it in more detail.
Many are in Hindi-English mixed colloquial text — interpret them in context.

This question was fielded against 4 pre-defined prompt buckets (the actual
field methodology interviewers used to help respondents articulate reasons):
{bucket_list}

Classify each theme you find into EXACTLY ONE of these 4 buckets — do not
invent new top-level categories. Within a bucket, dissect the underlying
INTENT behind each cluster of similar answers (status/identity, practical
function, emotional attachment, financial calculation, social influence,
etc.) rather than just restating the bucket name. Produce 1-3 themes PER
bucket that has enough data to support them (skip a bucket entirely if
there's no real signal for it — don't force themes that aren't there).

Respond with ONLY valid JSON in this exact shape:
{{"themes": [
  {{"bucket": "which of the 4 buckets above this theme belongs to (exact bucket name)",
    "intent_label": "short name for the underlying intent (not just the surface topic)",
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


def render_verbatim_intelligence_page(engine, platform=None, re_model=None):
    st.markdown("<h1>Verbatim Intelligence (AI)</h1>", unsafe_allow_html=True)
    provider = get_active_provider()
    # NOTE: this `model` is the LLM model choice (OpenRouter), NOT the RE
    # motorcycle model filter — kept as a separate name (`re_model` param
    # above) after a bug where this line silently overwrote the RE-model
    # filter parameter, making platform/model filtering on this page a
    # silent no-op (never crashed, just never actually filtered anything).
    model = st.session_state.get("or_model_choice") if provider == "openrouter" else None
    st.caption(
        "Beyond Infoleap's live dashboard scope — joins each respondent's broad reason with their "
        "follow-up elaboration and asks an LLM to dissect the underlying intent within the same "
        "Product / Price / Dealership / Personal buckets the fieldwork itself was designed around "
        "(status, emotional, financial, social read within each), not just count keywords. Currently using "
        f"**{provider.title()}** (change in Settings). Not a replication of the live site's numbers."
    )

    st.sidebar.markdown("### Verbatim Filters")
    segment = st.sidebar.selectbox("Segment", ["Acceptor", "Rejector", "Cancelled"], key="verbatim_segment")

    # Resolve RE model name → code for filter_df
    _model_code = None
    if re_model and re_model != "All":
        from utils.data_engine import RE_MODEL_LABELS
        _code_map = {v: k for k, v in RE_MODEL_LABELS.items()}
        _model_code = _code_map.get(re_model)
    _plat = platform if platform and platform != "All" else None
    df = engine.filter_df(segment=segment, platform=_plat, model_code=_model_code)
    _filter_note = ""
    if _plat or _model_code:
        _parts = []
        if _plat: _parts.append(f"Platform: {_plat}")
        if re_model and re_model != "All": _parts.append(f"Model: {re_model}")
        _filter_note = f" — filtered to {', '.join(_parts)}"
    st.metric("Respondents in segment" + _filter_note, f"{len(df):,}")

    pair_options = QUESTION_PAIRS[segment]
    pair_labels = [f"{b} → {s}" for b, s, _, _ in pair_options]
    choice_idx = st.selectbox("Question pair to analyze", range(len(pair_options)), format_func=lambda i: pair_labels[i])
    broad_label, specific_label, broad_prefix, specific_prefix = pair_options[choice_idx]

    pairs = collect_verbatim_pairs(df, broad_prefix, specific_prefix)
    st.caption(f"Sampled {len(pairs)} respondent answer-pairs for: **{broad_label} → {specific_label}**")

    bucket_frame = _bucket_frame_for(broad_prefix)

    def _render_theme_card(theme):
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{theme.get('intent_label', 'Unlabeled')}**  \n_{theme.get('motivation_type', '')}_")
            c2.metric("Share", theme.get("share_estimate_pct", "?"))
            st.caption(theme.get("explanation", ""))
            for q in theme.get("example_quotes", []):
                st.markdown(f"> {q}")

    if st.button("Run AI Intent Analysis", type="primary"):
        with st.spinner(f"Asking {provider.title()} to dissect respondent intent..."):
            result = analyze_intent(segment, pair_labels[choice_idx], json.dumps(pairs, ensure_ascii=False),
                                     provider, model, json.dumps(bucket_frame))

        if result.get("error"):
            st.warning(result["error"])
        themes = result.get("themes", [])
        if not themes:
            st.info("No themes returned.")
        # Grouped by the 4 field-methodology buckets (Product/Price/
        # Dealership/Personal) instead of a flat list — per 2026-07-24
        # request to anchor AI output to how the fieldwork was actually
        # designed, so Acceptor and Rejector themes read on the same axis.
        for bucket in bucket_frame:
            bucket_themes = [t for t in themes if t.get("bucket") == bucket]
            if not bucket_themes:
                continue
            st.markdown(f"#### {bucket}")
            for theme in bucket_themes:
                _render_theme_card(theme)
        # Any theme the LLM mis-tagged outside the 4 buckets still shows,
        # rather than silently disappearing.
        _stray = [t for t in themes if t.get("bucket") not in bucket_frame]
        if _stray:
            st.markdown("#### Other")
            for theme in _stray:
                _render_theme_card(theme)

    st.markdown("#### Reproduce Live Site Categories")
    st.caption(
        "The live dashboard's REAL Key Buying Factors / Reasons numbers — decoded from "
        "each respondent's own Infoleap-assigned netting code (exact match, not an AI "
        "guess). Uses the full segment base (not just the sampled pairs above), filtered "
        "the same way as the rest of this page."
    )
    try:
        _reasons_tbl = engine.reasons_table(df, base_label=segment, by="supernet", numeric=True, broad_prefix=broad_prefix)
    except ValueError as _e:
        st.info(str(_e))
    else:
        if len(_reasons_tbl) <= 1:
            st.info("No respondents in this segment/filter selection have an assigned netting code for this question.")
        else:
            render_chart_with_table(_reasons_tbl, f"{broad_label} — Category Breakdown",
                                     chart_type="stacked_bar", key=f"reasons_chart_{segment}_{choice_idx}")

    with st.expander("Raw sampled verbatim pairs (for transparency)"):
        st.json(pairs[:20])
