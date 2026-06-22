"""AI-generated narrative summary of the CURRENT filtered numeric view —
per user request: 'can we generate simple ai generated summary based on
the data... unbiased narrative'. This is deterministic data fed to the
LLM (every number is one we already computed), the LLM's only job is to
phrase an objective summary — not to invent or estimate anything itself.
Routes through utils/ai_providers.py so it works with whichever provider
(Groq/Gemini/OpenRouter) is selected in Settings.
"""
import json
import streamlit as st
from utils.ai_providers import call_llm

# Per explicit instruction ("do not make the analysis of charts a generic
# one, see the content, understand the scope they are working and data is
# being analysed") — grounds every AI call in what this study actually IS,
# not a generic "data analyst" framing. Keeps the model from drifting into
# boilerplate market-research phrasing disconnected from the real study.
STUDY_CONTEXT = """This is the Royal Enfield Digital Showroom MIS study, run by
Infoleap for Royal Enfield. Respondents are split into three groups based on
what actually happened with their Royal Enfield purchase journey:
- Acceptor: ended up buying a Royal Enfield model.
- Rejector: looked at Royal Enfield but bought a different brand instead.
- Booked but Cancelled: booked a Royal Enfield but cancelled before delivery.
The dashboard's purpose is to help Royal Enfield and Infoleap understand WHY
people in each group behaved the way they did — demographics, what else they
own/considered/bought, by model and CC class — to inform product positioning,
dealer focus, and marketing targeting decisions. Every chart is one specific
cut of this data (a segment, sometimes further filtered by model/platform/
month). Write as someone who understands THIS study's stakes, not a generic
analyst describing arbitrary numbers."""

SYSTEM_PROMPT = (
    "You write precise, unbiased, numbers-only data summaries for a specific "
    "market-research study (context given below every time). Never invent "
    "figures, and never write generic analyst boilerplate that could apply "
    "to any dataset — ground every sentence in what this specific group "
    "(Acceptor/Rejector/Cancelled) and this specific chart actually represent."
)


@st.cache_data(show_spinner=False)
def generate_narrative(facts_json, provider, model):
    facts = json.loads(facts_json)
    prompt = f"""You are a market-research analyst writing an objective, unbiased
summary paragraph for a Royal Enfield stakeholder dashboard. You are given
ONLY pre-computed numbers below — do not invent, estimate, or round
differently than given. Do not editorialize or add opinions beyond what
the numbers show. Mention any statistically significant findings explicitly
(marked sig_95 or sig_90 in the data) since those are the most decision-
relevant facts. Keep it to 3-4 sentences, plain language, no bullet points.

Data:
{json.dumps(facts, ensure_ascii=False, indent=2)}
"""
    return call_llm(provider, model, SYSTEM_PROMPT, prompt, max_tokens=300, temperature=0.2)


def render_ai_summary_button(facts: dict, key):
    provider = st.session_state.get("active_ai_provider", "groq")
    model = st.session_state.get("or_model_choice") if provider == "openrouter" else None
    if st.button("Generate AI Summary of this view", key=f"ai_summary_btn_{key}"):
        with st.spinner(f"Asking {provider.title()} for an unbiased summary of the current filtered data..."):
            text = generate_narrative(json.dumps(facts, ensure_ascii=False, sort_keys=True), provider, model)
        st.markdown(
            f"<div style='background:#FFFFFF;border:1px solid #ECE9E4;border-left:4px solid #2E3192;"
            f"border-radius:8px;padding:14px 18px;margin-top:0.6rem;font-size:0.92rem;line-height:1.6;'>"
            f"🤖 <b>AI Summary</b> ({provider.title()}, generated only from the numbers already shown above — not a separate data source)<br><br>{text}</div>",
            unsafe_allow_html=True,
        )


@st.cache_data(show_spinner=False)
def generate_chart_summary(facts_json, provider, model):
    """Rich per-chart analysis — distinct from generate_narrative (which
    covers the whole page). Per user request: 'ai generated summary... for
    each chart shortly describing the chart details and comparison on the
    specific data of the chart', later switched to on-demand (click to
    generate) after the auto-generate design burned through Groq's free
    daily token cap (100k TPD) in one session — and the user asked for a
    richer analysis now that it's user-triggered instead of a short caption.
    Same deterministic-data contract: every number is pre-computed, the LLM
    only analyses/phrases it, never invents one."""
    facts = json.loads(facts_json)
    prompt = f"""You are a market-research analyst producing a rich, decision-
useful analysis of ONE specific chart on a Royal Enfield dashboard, using
ONLY the numbers given below — never invent, estimate, or round differently
than given.

Cover, in order, as a short flowing paragraph (not bullet points):
1. Context: name the active filters (platform/model/zone) from "filters"
   and the exact month range from "months_included"/"time_period" if they
   are not "All" (e.g. "Among Bullet 350 buyers in the North zone, Aug'25-
   Oct'25..."). Omit any filter that is "All" rather than naming it.
2. The standout category from "top_category" with its exact %, and what
   that concentration suggests about this group in plain business terms.
3. EVERY entry in "significant_vs_rest_of_sample" (if non-empty), reported
   with real numbers: "<category> is <this_segment_pct>% here vs
   <rest_of_sample_pct>% in the rest of the sample (a <gap_points>-point
   gap, significant at <confidence>)" — and one sentence on why this gap
   might matter for Royal Enfield/Infoleap's decisions (e.g. targeting,
   model positioning). If the list is empty, say plainly "No category here
   is statistically different from the rest of the sample" — never invent
   a finding or use vague filler like "is the same across the segment".
4. Base size context: mention "base_n" so the reader knows how much weight
   to give this read.

4-6 sentences total. Every sentence must reference a specific number from
the data below — no generic filler, no preamble like "Here is...".

Data:
{json.dumps(facts, ensure_ascii=False, indent=2)}
"""
    return call_llm(provider, model, SYSTEM_PROMPT, prompt, max_tokens=320, temperature=0.15)


def render_chart_ai_blurb(facts: dict, key):
    """On-demand (button-gated) per-chart analysis — switched back from
    auto-generate-on-load after that design exhausted Groq's free daily
    token cap (100k TPD) in a single session. Cached by the exact facts
    payload, so re-clicking on an unchanged view doesn't re-spend quota."""
    provider = st.session_state.get("active_ai_provider", "groq")
    model = st.session_state.get("or_model_choice") if provider == "openrouter" else None
    if st.button("🤖 Analyse this chart", key=f"chart_ai_btn_{key}"):
        with st.spinner(f"Asking {provider.title()} for a rich analysis of this chart..."):
            text = generate_chart_summary(json.dumps(facts, ensure_ascii=False, sort_keys=True), provider, model)
        st.markdown(
            f"<div style='background:#FAFAF8;border-left:3px solid #9A958D;border-radius:6px;"
            f"padding:10px 14px;margin:6px 0 2px 0;font-size:0.88rem;color:#3A3732;line-height:1.6;'>"
            f"🤖 {text}</div>",
            unsafe_allow_html=True,
        )
