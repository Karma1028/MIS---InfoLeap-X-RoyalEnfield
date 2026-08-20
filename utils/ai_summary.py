"""AI-generated KPI narrative — feeds the KPI cards with Gemini-powered
analysis grounded in pre-computed dashboard_data.json facts.
Only provider: Gemini (Groq/OpenRouter removed per 2026-08-19 cleanup).
"""
import json
import streamlit as st
from utils.ai_providers import call_llm, get_active_provider
from utils.secure_settings import get_api_key


def _looks_like_leaked_reasoning(text):
    t = (text or "").strip()
    return len(t) < 60 or t.endswith((":", "...", "…"))


STUDY_CONTEXT = """Royal Enfield Digital Showroom MIS study by Infoleap.
Segments: Acceptor (bought RE), Rejector (bought another brand), Cancelled (booked RE, cancelled).
Goal: understand WHY each group behaved as they did — demographics, models, CC class — for
product positioning, dealer focus, marketing decisions."""

SYSTEM_PROMPT = (
    "You write precise, unbiased KPI summaries for the Royal Enfield MIS study. "
    "Use ONLY the numbers given. Never invent figures. "
    "Output ONLY the final paragraph — no preamble, no reasoning, no bullet points. "
    "Start directly with the first word of the summary."
)

_NARRATIVE_V = 5


@st.cache_data(show_spinner=False)
def generate_kpi_narrative(facts_json, provider, model, _v=_NARRATIVE_V):
    """Generate 3-4 sentence KPI summary from pre-computed facts dict."""
    facts = json.loads(facts_json)
    prompt = (
        f"Write a 3-4 sentence executive summary of these Royal Enfield KPI metrics. "
        f"Cover: avg age, income profile, first-time buyer rate, education. "
        f"Use ONLY the numbers given. No preamble. Start with the finding.\n\n"
        f"Context: {STUDY_CONTEXT}\n\nData:\n{json.dumps(facts, ensure_ascii=False, indent=2)}"
    )
    return call_llm(provider, model, SYSTEM_PROMPT, prompt, max_tokens=600, temperature=0.2)


def render_kpi_ai_narrative(facts: dict, key: str):
    """Auto-render AI KPI narrative below KPI cards — no button, cached."""
    provider = get_active_provider()
    if not get_api_key(provider):
        st.caption(
            "💡 AI KPI insight not configured — add a Gemini API key in **Settings → API Keys** to enable."
        )
        return
    facts_json = json.dumps(facts, ensure_ascii=False, sort_keys=True)
    with st.spinner("Generating KPI insight…"):
        text = generate_kpi_narrative(facts_json, provider, None)
    if _looks_like_leaked_reasoning(text):
        return  # bad response — show nothing rather than garbage
    st.markdown(
        f"<div style='background:#FAFAFA;border:1px solid #ECE9E4;"
        f"border-left:4px solid #2E3192;border-radius:8px;padding:12px 16px;"
        f"margin-top:0.5rem;margin-bottom:0.75rem;font-size:0.88rem;line-height:1.65;color:#2D3748;'>"
        f"<span style='font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;"
        f"color:#94A3B8;font-weight:700;'>AI KPI Insight · Gemini</span>"
        f"<br><br>{text}</div>",
        unsafe_allow_html=True,
    )
