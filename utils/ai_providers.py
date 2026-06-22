"""Unified AI-provider call layer for the dashboard's AI Summary and
Verbatim Intelligence features — supports Groq, Gemini, and OpenRouter (per
user request: 'they can use gemini api, openrouter apis... groq keys too').

Includes a conservative per-provider cooldown so repeated clicks on
'Generate' can't blow through a free-tier rate limit ('keeping in mind the
rate limit to generate output based on the data') — this is a courtesy
guard, not a substitute for the provider's own quota enforcement.
"""
import time
import requests
import streamlit as st
from groq import Groq
from utils.secure_settings import get_api_key

# Conservative minimum seconds between calls per provider, tuned to each
# free tier's published rate limit (Groq ~30 req/min, Gemini free tier
# ~15 req/min, OpenRouter free ":free" models are pooled across ALL
# OpenRouter free users, not just this app, and commonly cap lower than
# Groq/Gemini's own free tiers — 5s is a deliberately wider margin there)
# — deliberately under the real limit so a burst of dashboard clicks
# doesn't trip it. Calls are on-demand (button per chart), not automatic,
# so this only ever paces a human clicking through charts quickly.
RATE_LIMITS = {"groq": 2.0, "gemini": 4.0, "openrouter": 5.0}

DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-1.5-flash",
    # Largest genuinely-free ($0/$0) model available as of the 2026-06-22
    # catalog pull — best analysis quality among the free tier. Settings'
    # model picker can still override this per-session.
    "openrouter": "nvidia/nemotron-3-ultra-550b-a55b:free",
}


def _rate_limit_wait(provider):
    """Blocks (sleeps) until this provider's cooldown has elapsed, rather
    than bailing out with a 'try again' message — per-chart AI blurbs are
    triggered automatically in a fixed sequence on page load (not by a user
    mashing a button), so the right behavior is to pace the calls and let
    every chart get real content, not to surface the rate-limit mechanics
    to the user as visible failures."""
    state_key = f"_ai_last_call_{provider}"
    now = time.time()
    last = st.session_state.get(state_key, 0.0)
    min_gap = RATE_LIMITS.get(provider, 2.0)
    remaining = min_gap - (now - last)
    if remaining > 0:
        time.sleep(remaining)
    st.session_state[state_key] = time.time()


@st.cache_data(show_spinner=False, ttl=3600)
def list_openrouter_free_models(api_key):
    """OpenRouter's full model catalog, filtered to models that are
    genuinely free (prompt AND completion pricing both 0) — cached for an
    hour so 'refresh' means a deliberate re-fetch, not one API hit per
    Streamlit rerun."""
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        models = resp.json().get("data", [])
        free = [
            m["id"] for m in models
            if float(m.get("pricing", {}).get("prompt", 1) or 0) == 0
            and float(m.get("pricing", {}).get("completion", 1) or 0) == 0
        ]
        return sorted(free)
    except Exception:
        return []


def call_llm(provider, model, system_prompt, user_prompt, max_tokens=300, temperature=0.2, json_mode=False):
    """Routes a system+user prompt to the chosen provider/model. Returns
    plain text (callers needing JSON should request it in the prompt and
    parse the result themselves, same as before). json_mode only forces a
    structured-output mode on providers that support it (Groq); for others
    the prompt's own "respond with ONLY valid JSON" instruction is relied on."""
    _rate_limit_wait(provider)

    api_key = get_api_key(provider)
    if not api_key:
        return f"No {provider.title()} API key saved — add one under Settings."

    model = model or DEFAULT_MODELS.get(provider)
    if provider == "openrouter" and not model:
        return "Pick a free OpenRouter model in Settings first."

    try:
        if provider == "groq":
            client = Groq(api_key=api_key)
            kwargs = {}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return resp.choices[0].message.content

        if provider == "openrouter":
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        if provider == "gemini":
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                json={
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

        return f"Unknown provider: {provider}"
    except Exception as e:
        return f"AI call failed ({provider}/{model}): {e}"
