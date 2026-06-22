"""Encrypted local storage for user-supplied AI provider API keys (Groq,
Gemini, OpenRouter) — per user request: 'add one setting where user can
save their keys and it will be encrypted while saving to be used later for
these all ai generated analysis'.

Uses Fernet (symmetric AES) with a key file generated on first run and kept
OUTSIDE git (see .gitignore: data/.settings_key, data/api_keys.enc) — losing
that key file means the encrypted store can't be decrypted, which is fine
since keys are just re-entered in Settings. Falls back to .streamlit/secrets.toml
if nothing has been saved yet, so the existing GROQ_API_KEY keeps working
without anyone touching Settings.
"""
import json
import os
from cryptography.fernet import Fernet
import streamlit as st

KEY_FILE = "data/.settings_key"
STORE_FILE = "data/api_keys.enc"
PROVIDERS = ["groq", "gemini", "openrouter"]
_SECRET_NAMES = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}


def _get_fernet():
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    if not os.path.exists(KEY_FILE):
        with open(KEY_FILE, "wb") as f:
            f.write(Fernet.generate_key())
    with open(KEY_FILE, "rb") as f:
        return Fernet(f.read())


def _load_store():
    if not os.path.exists(STORE_FILE):
        return {}
    blob = open(STORE_FILE, "rb").read()
    if not blob:
        return {}
    try:
        return json.loads(_get_fernet().decrypt(blob).decode())
    except Exception:
        return {}


def _save_store(data):
    blob = _get_fernet().encrypt(json.dumps(data).encode())
    with open(STORE_FILE, "wb") as f:
        f.write(blob)


def save_api_key(provider, key):
    data = _load_store()
    data[provider] = key.strip()
    _save_store(data)


def clear_api_key(provider):
    data = _load_store()
    data.pop(provider, None)
    _save_store(data)


def get_api_key(provider):
    data = _load_store()
    if data.get(provider):
        return data[provider]
    return st.secrets.get(_SECRET_NAMES.get(provider, ""), "")


def has_api_key(provider):
    return bool(get_api_key(provider))
