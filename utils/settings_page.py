"""Settings page — user administration, audit log, and model config management."""
import streamlit as st
from auth import load_audit_log

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
    color: #F1F5F9 !important; margin: 0 0 0.2rem; font-size: 1.5rem; font-weight: 700;
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
    c1, c2 = st.columns(2)
    c1.metric("Name", current_name or "—")
    c2.metric("Role", "Administrator" if is_admin else "Viewer")

    # ═══════════════════════════════════════════════════════════════════════
    # ADMIN SECTIONS
    # ═══════════════════════════════════════════════════════════════════════
    if is_admin:

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

        st.markdown(
            '<div class="info-box">👥 <strong>User Management:</strong> '
            'Add or disable users directly in '
            '<a href="https://console.firebase.google.com" target="_blank">Firebase Console → Authentication</a>. '
            'To grant admin access, add the user\'s email to <code>ADMIN_EMAILS</code> in Streamlit secrets.</div>',
            unsafe_allow_html=True,
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
