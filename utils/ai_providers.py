"""Unified AI-provider call layer for the dashboard's AI Summary and
Verbatim Intelligence features — supports Groq, Gemini, and OpenRouter (per
user request: 'they can use gemini api, openrouter apis... groq keys too').

Includes a conservative per-provider cooldown so repeated clicks on
'Generate' can't blow through a free-tier rate limit ('keeping in mind the
rate limit to generate output based on the data') — this is a courtesy
guard, not a substitute for the provider's own quota enforcement.
"""
import re
import time
import requests
import streamlit as st
from groq import Groq
from utils.secure_settings import get_api_key


_PREAMBLE_PATTERNS = re.compile(
    r'^(the user wants|i need to|i will|here is|let me|okay,|sure,|'
    r'sentence \d|based on the (data|instructions|prompt)|'
    r'alright|no bullet|i must|i should)',
    re.IGNORECASE,
)


def _strip_thinking(text: str) -> str:
    """Remove chain-of-thought preamble from model output.
    Handles: <think>...</think> tagged blocks (DeepSeek-R1/QwQ) AND
    untagged self-narrating reasoning lines (some instruction models)."""
    # 1. Strip XML-tagged thinking blocks
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    # 2. Strip untagged reasoning lines at the start — drop any leading
    #    paragraph that reads like "I need to write 3-4 sentences..."
    lines = cleaned.split('\n')
    real_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and _PREAMBLE_PATTERNS.match(stripped):
            real_start = i + 1
        elif stripped:
            break
    cleaned = '\n'.join(lines[real_start:]).strip()
    return cleaned

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
    # Stale-snapshot fallback ONLY — OpenRouter's free catalog changes
    # over time (models get pulled or repriced), so this string is never
    # trusted as-is. call_llm() always re-checks it (and any
    # session-picked model) against the LIVE free-models list before
    # using it, per user instruction ('should be free at this moment
    # always for openrouter').
    # meta-llama/llama-3.1-8b-instruct:free chosen because it reliably
    # follows instructions without emitting chain-of-thought preamble.
    "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
}


def get_active_provider():
    """Single source of truth for 'which AI provider should this feature
    use right now' — every AI feature (AI Summary, Verbatim Intelligence)
    used to independently default to st.session_state.get("active_ai_provider",
    "groq"), which is WRONG whenever the user has only configured a
    DIFFERENT provider's key and hasn't happened to visit Settings yet
    this session (Settings is the only place that ever sets
    active_ai_provider in session_state) — every feature would still try
    Groq, fail with 'No Groq API key saved', even with a perfectly valid
    OpenRouter key sitting in Cloud Secrets. Falls back to whichever
    provider actually HAS a key configured (OpenRouter > Groq > Gemini),
    only landing on the Groq default if truly nothing is set anywhere."""
    if "active_ai_provider" in st.session_state:
        return st.session_state["active_ai_provider"]
    for provider in ("openrouter", "groq", "gemini"):
        if get_api_key(provider):
            return provider
    return "groq"


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
    if provider == "openrouter":
        free_models = list_openrouter_free_models(api_key)
        if not free_models:
            return "No free OpenRouter models available right now — check your key or try again shortly."
        # Preferred free models, empirically verified to actually return
        # content (2026-07-27) — OpenRouter's free catalog drifts over
        # time (models get pulled/renamed), and the PREVIOUS list here had
        # gone entirely stale: none of its 4 entries existed in the live
        # catalog anymore, so every call silently fell through to
        # free_models[0] (alphabetically first), which landed on
        # cohere/north-mini-code:free — a reasoning-heavy model that burns
        # its whole max_tokens budget on hidden chain-of-thought and
        # returns truncated/empty content. This list WILL go stale again;
        # the empty-content retry below is the real safety net, not this
        # list.
        _PREFERRED = [
            "nvidia/nemotron-3-nano-30b-a3b:free",
            "openai/gpt-oss-20b:free",
            "inclusionai/ling-3.0-flash:free",
            "nvidia/nemotron-nano-9b-v2:free",
        ]
        available_preferred = [m for m in _PREFERRED if m in free_models]
        if not model or model not in free_models:
            model = available_preferred[0] if available_preferred else free_models[0]
        # Today's free-tier models commonly reason-by-default even with
        # include_reasoning:false (that flag only suppresses the separate
        # reasoning_details field, not the hidden reasoning tokens actually
        # consumed) — a small max_tokens budget (e.g. 300 for a chart
        # blurb) can be entirely eaten by reasoning before any visible
        # content is emitted, same failure mode as the stale-model bug
        # above. Give OpenRouter calls more headroom regardless of what
        # the caller asked for.
        max_tokens = max(max_tokens, 500)

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
            # Try up to 3 models — preferred first, then fall back on 429/404
            _models_to_try = [model]
            if available_preferred:
                _models_to_try += [m for m in available_preferred if m != model]
            last_err = None
            for _m in _models_to_try[:3]:
                try:
                    resp = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": _m,
                            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            "include_reasoning": False,
                        },
                        timeout=30,
                    )
                    if resp.status_code in (429, 503):
                        last_err = f"{resp.status_code} on {_m}"
                        continue
                    resp.raise_for_status()
                    msg = resp.json()["choices"][0]["message"]
                    content = _strip_thinking(msg.get("content") or "")
                    if not content:
                        # Truncated by max_tokens before real content came
                        # out (e.g. spent on hidden reasoning) or genuinely
                        # empty — not a success, try the next candidate.
                        last_err = f"empty content from {_m}"
                        continue
                    return content
                except Exception as e:
                    last_err = str(e)
                    continue
            return f"All OpenRouter models busy (rate limited). Try again in a moment. Last error: {last_err}"

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
        import logging
        logging.getLogger(__name__).error("AI call failed (%s/%s): %s", provider, model, e)
        return "AI call failed — check Settings or try again."
