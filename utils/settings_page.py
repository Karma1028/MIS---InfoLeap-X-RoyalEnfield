"""Settings page — Gemini API key management and user administration.
Groq/OpenRouter removed 2026-08-19 (Gemini-only AI layer)."""
import streamlit as st
from auth import list_users, add_user, set_user_active, load_audit_log


def render_settings_page():
    st.markdown("<h1>Settings</h1>", unsafe_allow_html=True)

    # ── Account info ─────────────────────────────────────────────────────
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

    is_admin = st.session_state.get("user_role", "user") == "admin"

    if is_admin:
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
                new_role = st.selectbox("Role", ["user", "admin"], index=0)
                if st.form_submit_button("Add User", use_container_width=True):
                    if not new_email.strip() or not new_pass.strip():
                        st.warning("Email and password required.")
                    else:
                        err = add_user(new_email, new_name, new_pass, role=new_role)
                        if err:
                            st.error(err)
                        else:
                            st.success(f"User {new_email.strip().lower()} added.")
                            st.rerun()

    with st.expander("📋 Login Audit Log (last 100 events)", expanded=False):
        audit_df = load_audit_log(100)
        if not audit_df.empty and not is_admin:
            audit_df = audit_df[audit_df["email"] == current_email]
        if audit_df.empty:
            st.caption("No events logged yet.")
        else:
            display_cols = [c for c in ["timestamp", "email"] if c in audit_df.columns]
            st.dataframe(audit_df[display_cols], use_container_width=True, hide_index=True)

