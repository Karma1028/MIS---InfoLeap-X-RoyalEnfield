"""Unified AI provider layer — Gemini only (Groq/OpenRouter removed 2026-08-19)."""
import re
import time
import requests
import streamlit as st
from utils.secure_settings import get_api_key


_PREAMBLE_PATTERNS = re.compile(
    r'^(the user wants|(i|we) (need to|will|must|should)|here is|let me|okay,|sure,|'
    r'sentence \d|based on the (data|instructions|prompt)|'
    r'alright|no bullet)',
    re.IGNORECASE,
)


def _strip_thinking(text: str) -> str:
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    lines = cleaned.split('\n')
    real_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and _PREAMBLE_PATTERNS.match(stripped):
            real_start = i + 1
        elif stripped:
            break
    cleaned = '\n'.join(lines[real_start:]).strip()
    first_block = re.split(r'\n\s*\n', cleaned, maxsplit=1)[0].strip()
    if len(first_block) > 1 and first_block[0] in '""' and first_block[-1] in '""':
        first_block = first_block[1:-1].strip()
    return first_block


RATE_LIMITS = {"gemini": 4.0}
DEFAULT_MODELS = {"gemini": "gemini-1.5-flash"}


def get_active_provider():
    return "gemini"


def _rate_limit_wait(provider):
    state_key = f"_ai_last_call_{provider}"
    now = time.time()
    last = st.session_state.get(state_key, 0.0)
    min_gap = RATE_LIMITS.get(provider, 4.0)
    remaining = min_gap - (now - last)
    if remaining > 0:
        time.sleep(remaining)
    st.session_state[state_key] = time.time()


def call_llm(provider, model, system_prompt, user_prompt, max_tokens=600, temperature=0.2, json_mode=False):
    _rate_limit_wait("gemini")
    api_key = get_api_key("gemini")
    if not api_key:
        return "No Gemini API key saved — add one under Settings."
    model = model or DEFAULT_MODELS["gemini"]
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
            json={
                "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _strip_thinking(raw)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Gemini call failed: %s", e)
        return "AI call failed — check your Gemini API key in Settings."
