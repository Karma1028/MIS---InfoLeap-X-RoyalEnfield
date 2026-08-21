"""Settings page — user administration, audit log, and model config management."""
import streamlit as st
from auth import list_users, add_user, set_user_active, load_audit_log

_SECTION_CSS = """
<style>
.settings-hero {
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border-radius: 12px;
    padding: 1.6rem 2rem 1.4rem;
    margin-bottom: 1.6rem;
    border-left: 4px solid #C8102E;
}
.settings-hero h2 {
    color: #F1F5F9; margin: 0 0 0.2rem; font-size: 1.5rem; font-weight: 700;
}
.settings-hero p {
    color: #94A3B8; margin: 0; font-size: 0.88rem;
}
.section-label {
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: #94A3B8; margin: 1.4rem 0 0.5rem;
}
.user-row {
    background: #F8FAFC; border: 1px solid #E2E8F0;
    border-radius: 8px; padding: 0.5rem 0.8rem; margin-bottom: 0.4rem;
}
.badge-active {
    background:#DCFCE7; color:#166534; border-radius:99px;
    padding:2px 10px; font-size:0.75rem; font-weight:600;
}
.badge-inactive {
    background:#FEE2E2; color:#991B1B; border-radius:99px;
    padding:2px 10px; font-size:0.75rem; font-weight:600;
}
.badge-admin {
    background:#EEF2FF; color:#3730A3; border-radius:99px;
    padding:2px 8px; font-size:0.72rem; font-weight:600; margin-left:4px;
}
.info-box {
    background:#F0F9FF; border:1px solid #BAE6FD; border-radius:8px;
    padding:0.7rem 1rem; font-size:0.83rem; color:#0C4A6E; margin-bottom:0.8rem;
}
.warn-box {
    background:#FFFBEB; border:1px solid #FDE68A; border-radius:8px;
    padding:0.7rem 1rem; font-size:0.83rem; color:#78350F; margin-bottom:0.8rem;
}
</style>
"""


def render_settings_page():
    st.markdown(_SECTION_CSS, unsafe_allow_html=True)

    is_admin = st.session_state.get("user_role", "user") == "admin"
    current_email = st.session_state.get("username", "")
    current_name  = st.session_state.get("user_name", current_email)

    # ── Hero ──────────────────────────────────────────────────────────────
    role_badge = '<span class="badge-admin">Admin</span>' if is_admin else ""
    st.markdown(f"""
    <div class="settings-hero">
        <h2>Settings {role_badge}</h2>
        <p>Signed in as <strong style="color:#E2E8F0">{current_name}</strong>
           &nbsp;·&nbsp; {current_email}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Session info cards ────────────────────────────────────────────────
    users = list_users()
    current = next((u for u in users if u["email"] == current_email), None)
    if current:
        c1, c2, c3 = st.columns(3)
        c1.metric("Name", current["name"] or "—")
        c2.metric("Role", "Administrator" if is_admin else "Viewer")
        c3.metric("Account status", "✅ Active" if current["active"] == "Yes" else "🔴 Inactive")

    # ═══════════════════════════════════════════════════════════════════════
    # ADMIN SECTIONS
    # ═══════════════════════════════════════════════════════════════════════
    if is_admin:

        # ── User Management ───────────────────────────────────────────────
        st.markdown('<div class="section-label">👥 User Management</div>', unsafe_allow_html=True)
        with st.expander("Manage portal users — grant, revoke, or add access", expanded=False):
            st.markdown(
                '<div class="info-box">🔐 <strong>Access control:</strong> '
                'Active users can sign in via Firebase. Revoking a user blocks login '
                'immediately — their Firebase account is unaffected so you can restore anytime. '
                'Admin users see this Settings panel and can add/revoke others.</div>',
                unsafe_allow_html=True,
            )

            # User list
            hc1, hc2, hc3, hc4, hc5 = st.columns([2.2, 3.2, 1.2, 1.0, 1.2])
            hc1.markdown("**Name**"); hc2.markdown("**Email**")
            hc3.markdown("**Status**"); hc4.markdown("**Role**"); hc5.markdown("**Action**")
            st.markdown("<hr style='margin:0.3rem 0 0.5rem;'>", unsafe_allow_html=True)

            # Reload with role info
            from auth import _load_users as _lu
            _users_full = _lu()

            for u in users:
                c1, c2, c3, c4, c5 = st.columns([2.2, 3.2, 1.2, 1.0, 1.2])
                c1.write(u["name"] or "—")
                c2.write(u["email"])
                badge = "badge-active" if u["active"] == "Yes" else "badge-inactive"
                label = "Active" if u["active"] == "Yes" else "Inactive"
                c3.markdown(f'<span class="{badge}">{label}</span>', unsafe_allow_html=True)
                role = _users_full.get(u["email"], {}).get("role", "user")
                role_html = '<span class="badge-admin">admin</span>' if role == "admin" else \
                            '<span style="color:#64748B;font-size:0.8rem">user</span>'
                c4.markdown(role_html, unsafe_allow_html=True)
                if u["email"] != current_email:
                    is_active = u["active"] == "Yes"
                    btn_label = "Revoke" if is_active else "Restore"
                    if c5.button(btn_label, key=f"toggle_{u['email']}", use_container_width=True):
                        err = set_user_active(u["email"], not is_active)
                        if err:
                            st.error(err)
                        else:
                            st.success(f"{u['email']} {'revoked' if is_active else 'restored'}.")
                            st.rerun()
                else:
                    c5.markdown('<span style="color:#94A3B8;font-size:0.8rem">— you —</span>', unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**Add New User**")
            st.markdown(
                '<div class="info-box">New users are added to this portal\'s user list. '
                'They still need a matching Firebase account (created via Firebase Console → '
                'Authentication → Add user) to be able to sign in.</div>',
                unsafe_allow_html=True,
            )
            with st.form("add_user_form"):
                nc1, nc2 = st.columns(2)
                new_email = nc1.text_input("Email address", placeholder="user@example.com")
                new_name  = nc2.text_input("Full name", placeholder="First Last")
                nc3, nc4  = st.columns(2)
                new_pass  = nc3.text_input("Temporary password", type="password",
                                           placeholder="Min 6 characters")
                new_role  = nc4.selectbox("Role", ["user", "admin"], index=0,
                                          help="Admin = full settings access. User = dashboard only.")
                if st.form_submit_button("➕ Add User", use_container_width=True, type="primary"):
                    if not new_email.strip() or not new_pass.strip():
                        st.warning("Email and password are required.")
                    else:
                        err = add_user(new_email, new_name, new_pass, role=new_role)
                        if err:
                            st.error(err)
                        else:
                            st.success(f"✅ {new_email.strip().lower()} added successfully.")
                            st.rerun()

        # ── Model Config Setup ────────────────────────────────────────────
        st.markdown('<div class="section-label">🗂️ Model Configuration</div>', unsafe_allow_html=True)
        with st.expander("Set up survey-code mapping columns in master Google Sheet", expanded=False):
            st.markdown(
                '<div class="info-box">'
                '<strong>What this does:</strong> Writes four columns into the '
                '<code>model_config</code> tab of the master Google Sheet — '
                '<code>in_survey</code>, <code>acceptor_code</code>, '
                '<code>rejector_code</code>, <code>cancelled_code</code>. '
                'These tell the app exactly which raw survey codes map to each RE model '
                'for each segment, replacing fragile block-math. '
                'Existing values are <strong>never overwritten</strong> — only blank cells are filled.'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="warn-box">'
                '⚠️ <strong>Adding a new model to the survey?</strong> '
                'Add a row to model_config with its model codes, set <code>in_survey = YES</code>, '
                'then click this button to apply colour coding. '
                'For <strong>future models</strong> (no survey data yet) set <code>in_survey = NO</code> '
                '— they appear in dropdowns but are excluded from segment counts.'
                '</div>',
                unsafe_allow_html=True,
            )
            col_btn, col_info = st.columns([1, 2])
            if col_btn.button("▶ Run setup", use_container_width=True, type="primary",
                              key="run_model_config_setup"):
                from utils.model_config_setup import setup_model_config_columns
                with st.spinner("Connecting to master sheet and writing columns…"):
                    ok, msg = setup_model_config_columns()
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
            col_info.caption(
                "Runs via the app's service account. "
                "Safe to re-run anytime — idempotent. "
                "After running, click **Reload Data** on the main dashboard to pick up changes."
            )

    # ── Audit Log (all users) ─────────────────────────────────────────────
    st.markdown('<div class="section-label">📋 Login Activity</div>', unsafe_allow_html=True)
    with st.expander(
        "Login audit log — last 100 events" if is_admin else "My recent login activity",
        expanded=False,
    ):
        if is_admin:
            st.markdown(
                '<div class="info-box">Full audit trail of all login events across all users. '
                'Includes successful logins, failures, lockouts, and user management actions. '
                'Stored in Google Sheets — persists across app restarts.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="info-box">Your personal login history on this portal. '
                'Contact an admin if you see unrecognised activity.</div>',
                unsafe_allow_html=True,
            )
        audit_df = load_audit_log(100)
        if not audit_df.empty and not is_admin:
            audit_df = audit_df[audit_df["email"] == current_email]
        if audit_df.empty:
            st.caption("No events logged yet.")
        else:
            display_cols = [c for c in ["timestamp", "email", "event"] if c in audit_df.columns]
            st.dataframe(
                audit_df[display_cols],
                use_container_width=True,
                hide_index=True,
            )
