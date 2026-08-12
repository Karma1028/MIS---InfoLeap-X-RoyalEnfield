"""
Open-Ended Verbatim Taxonomy & Reasons Breakdown.
Fully follows Infoleap's official netting taxonomy from the raw Masterfile workbook
(Supernet -> Net hierarchy), showing the collapsible tree table matching the live website.
No AI/LLM analysis is used for open-ended questions.
"""
import re
import streamlit as st
from utils.visuals import render_collapsible_reasons_table

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
                pairs.append({"broad_reason": broad or "", "elaboration": specific or ""})
            if len(pairs) >= max_pairs:
                return pairs
    return pairs


def render_verbatim_intelligence_page(engine, platform=None, re_model=None):
    st.markdown("<h1>📋 Open-Ended Verbatim Taxonomy</h1>", unsafe_allow_html=True)
    st.caption(
        "Fully mapped to Infoleap's official netting codebook in the raw Masterfile workbook. "
        "Displays the hierarchical Supernet & Netting taxonomy in an interactive, collapsible tree format "
        "matching the live website — no AI approximation used."
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

    st.markdown("---")

    # 1. Collapsible Supernet -> Net Tree Table (Exact Raw File Mapping)
    try:
        tree_data = engine.reasons_tree_data(df, base_label=segment, broad_prefix=broad_prefix)
    except ValueError as _e:
        st.info(str(_e))
    else:
        with st.container(border=True):
            render_collapsible_reasons_table(
                tree_data,
                title=f"{broad_label} — Supernet & Netting Breakdown",
                color="#D6742D",
                key_suffix=f"vi_{segment}_{choice_idx}"
            )

    # 2. Raw Verbatim Inspector (for transparency, direct raw responses)
    pairs = collect_verbatim_pairs(df, broad_prefix, specific_prefix, max_pairs=40)
    with st.expander(f"💬 Raw Verbatim Responses ({len(pairs)} sampled pairs)", expanded=False):
        if not pairs:
            st.info("No text verbatims available for this selection.")
        else:
            for i, p in enumerate(pairs, 1):
                b_text = p['broad_reason']
                e_text = p['elaboration']
                st.markdown(
                    f"**{i}.** **Broad Reason:** _{b_text}_"
                    + (f" &nbsp;|&nbsp; **Elaboration:** _{e_text}_" if e_text else "")
                )
