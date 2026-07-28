"""Settings page — save API keys (encrypted at rest, see secure_settings.py)
for the AI-driven features (AI Summary, Verbatim Intelligence) and pick which
provider/model those features should use. Per user request: 'add one setting
where user can save their keys and it will be encrypted... gemini api,
openrouter apis... groq keys too... openrouter it will show available
models too with specifically refreshing the free module'."""
import streamlit as st
import pandas as pd
from utils.secure_settings import save_api_key, clear_api_key, get_api_key
from utils.ai_providers import list_openrouter_free_models, RATE_LIMITS, DEFAULT_MODELS, get_active_provider
from auth import list_users, add_user, set_user_active, load_audit_log


def _key_row(provider, label):
    saved = get_api_key(provider)
    status = "🟢 saved (encrypted)" if saved else "⚪ not set"
    st.markdown(f"**{label}** &nbsp; <span style='font-size:0.85rem;color:#7A7670;'>{status}</span>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([4, 1, 1])
    with c1:
        new_key = st.text_input(f"{label} API Key", value="", type="password", key=f"set_{provider}_input", label_visibility="collapsed")
    with c2:
        if st.button("Save", key=f"save_{provider}"):
            if new_key.strip():
                save_api_key(provider, new_key)
                st.success(f"{label} key saved (encrypted).")
                st.rerun()
            else:
                st.warning("Paste a key first.")
    with c3:
        if saved and st.button("Clear", key=f"clear_{provider}"):
            clear_api_key(provider)
            st.rerun()


def render_settings_page():
    st.markdown("<h1>Settings</h1>", unsafe_allow_html=True)

    st.markdown("### Account")
    users = list_users()
    current_email = st.session_state.get("username", "")
    current = next((u for u in users if u["email"] == current_email), None)
    if current:
        c1, c2, c3 = st.columns(3)
        c1.metric("Logged in as", current["name"] or current_email)
        c2.metric("Email", current["email"])
        c3.metric("Status", "Active" if current["active"] == "Yes" else "Inactive")
    else:
        st.caption(f"Logged in as: {current_email}")

    with st.expander("👥 User Management", expanded=False):
        st.markdown("**All Users**")
        for u in users:
            col_name, col_email, col_status, col_action = st.columns([2, 3, 1, 1])
            col_name.write(u["name"] or "—")
            col_email.write(u["email"])
            col_status.write("🟢" if u["active"] == "Yes" else "🔴")
            if u["email"] != current_email:
                is_active = u["active"] == "Yes"
                btn_label = "Revoke" if is_active else "Restore"
                if col_action.button(btn_label, key=f"toggle_{u['email']}"):
                    err = set_user_active(u["email"], not is_active)
                    if err:
                        st.error(err)
                    else:
                        st.success(f"{u['email']} {'revoked' if is_active else 'restored'}.")
                        st.rerun()
            else:
                col_action.caption("(you)")

        st.markdown("---")
        st.markdown("**Add New User**")
        with st.form("add_user_form"):
            new_email = st.text_input("Email")
            new_name = st.text_input("Name")
            new_pass = st.text_input("Password", type="password")
            if st.form_submit_button("Add User", use_container_width=True):
                if not new_email.strip() or not new_pass.strip():
                    st.warning("Email and password required.")
                else:
                    err = add_user(new_email, new_name, new_pass)
                    if err:
                        st.error(err)
                    else:
                        st.success(f"User {new_email.strip().lower()} added.")
                        st.rerun()

    with st.expander("📋 Login Audit Log (last 100 events)", expanded=False):
        audit_df = load_audit_log(100)
        if audit_df.empty:
            st.caption("No events logged yet.")
        else:
            st.dataframe(audit_df, use_container_width=True, hide_index=True)
            st.caption("Events: LOGIN_SUCCESS · LOGIN_FAILED · ACCOUNT_LOCKED · ACCOUNT_INACTIVE · USER_ADDED · USER_REVOKED · USER_ACTIVATED")

    st.markdown("---")
    st.caption(
        "API keys are encrypted with Fernet (AES) before being written to disk — the decryption key lives "
        "in a local file outside the repo (data/.settings_key, gitignored). Used only for the AI Summary / "
        "Verbatim Intelligence features below."
    )

    st.markdown("### Groq")
    _key_row("groq", "Groq")
    st.caption(f"Free tier — guarded to 1 request every {RATE_LIMITS['groq']:.0f}s from this dashboard.")

    st.markdown("---")
    st.markdown("### Google Gemini")
    _key_row("gemini", "Gemini")
    st.caption(f"Free tier — guarded to 1 request every {RATE_LIMITS['gemini']:.0f}s from this dashboard.")

    st.markdown("---")
    st.markdown("### OpenRouter")
    _key_row("openrouter", "OpenRouter")
    or_key = get_api_key("openrouter")
    if or_key:
        col_a, col_b = st.columns([3, 1])
        with col_b:
            if st.button("🔄 Refresh free models"):
                list_openrouter_free_models.clear()
                st.rerun()
        free_models = list_openrouter_free_models(or_key)
        with col_a:
            if free_models:
                preferred = DEFAULT_MODELS.get("openrouter")
                default_idx = free_models.index(preferred) if preferred in free_models else 0
                st.selectbox(
                    "Free OpenRouter model to use",
                    free_models,
                    index=default_idx,
                    key="or_model_choice",
                    help="Only models with $0 prompt AND $0 completion pricing are listed — true free tier, no surprise billing. Defaults to the largest free model available (best analysis quality).",
                )
            else:
                st.info("No free models found yet — save a valid OpenRouter key, then click Refresh.")
    st.caption(f"Free models — guarded to 1 request every {RATE_LIMITS['openrouter']:.0f}s from this dashboard (actual per-model limits vary; this is a conservative floor).")

    st.markdown("---")
    st.markdown("### Active provider for AI features")
    providers = ["groq", "gemini", "openrouter"]
    default_provider = get_active_provider()
    st.selectbox(
        "AI Summary / Verbatim Intelligence will use this provider",
        providers,
        index=providers.index(default_provider),
        format_func=lambda p: {"groq": "Groq", "gemini": "Gemini", "openrouter": "OpenRouter"}[p],
        key="active_ai_provider",
    )
    st.caption("Switch any time — no restart needed. If the selected provider has no key saved, the AI buttons will say so instead of failing silently.")
