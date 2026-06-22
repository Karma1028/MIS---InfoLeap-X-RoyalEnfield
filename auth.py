"""Login gate for the Royal Enfield x Infoleap Digital Showroom.

Session-state gated: render_login() returns True once authenticated, and the
caller (app.py) should st.stop() if it returns False.
"""
import pandas as pd
import streamlit as st
from styles.theme import RE_RED, INFOLEAP_ORANGE, INFOLEAP_GREEN, INFOLEAP_BLUE, INFOLEAP_PURPLE

USERS_PATH = "data/users.xlsx"


def _load_users():
    """Credentials live in data/users.xlsx (columns: email, password, name,
    active) per user request — add a row there to grant someone access, no
    code change needed. Set active=N to revoke access without deleting the
    row (audit trail of who has ever had access). Login is by email,
    case-insensitive. NOTE: plaintext in an Excel file is adequate for this
    small internal MIS tool with a handful of known users, but is not a
    hardened auth store — do not reuse this pattern for anything
    public-facing or higher-stakes without adding hashing + access control."""
    df = pd.read_excel(USERS_PATH)
    users = {}
    for _, r in df.iterrows():
        email = str(r['email']).strip().lower()
        active = str(r.get('active', 'Y')).strip().upper() != "N"
        users[email] = {"password": str(r['password']), "active": active, "name": str(r.get('name', ''))}
    return users


def list_users():
    """Account-info view for the Settings page — email/name/active only,
    NEVER the password column, even though the source file itself stores
    it in plaintext (documented limitation, not something to compound by
    also surfacing it in the UI)."""
    users = _load_users()
    return [
        {"email": email, "name": info["name"], "active": "Yes" if info["active"] else "No"}
        for email, info in users.items()
    ]


def _render_brand_header():
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:center; gap:14px; margin-bottom:0.5rem;">
        <div style="display:flex; flex-direction:column; gap:3px;">
            <span style="width:18px;height:18px;border-radius:3px;background:{INFOLEAP_ORANGE};display:block;"></span>
            <span style="width:18px;height:18px;border-radius:3px;background:{INFOLEAP_GREEN};display:block;"></span>
            <span style="width:18px;height:18px;border-radius:3px;background:{INFOLEAP_BLUE};display:block;"></span>
        </div>
        <span style="font-size:1.9rem; font-weight:800; letter-spacing:0.02em; color:#1A1A1A; font-family:'Segoe UI',sans-serif;">
            INFO-LEAP
        </span>
        <span style="color:{INFOLEAP_PURPLE}; font-size:1.4rem;">&times;</span>
        <span style="font-size:1.7rem; font-weight:800; color:{RE_RED}; font-family:Georgia, serif; letter-spacing:0.03em;">
            ROYAL ENFIELD
        </span>
    </div>
    """, unsafe_allow_html=True)


def render_login() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.markdown(f"""
    <style>
        .stApp {{ background: #FAFAF8; }}
        .login-tagline {{
            text-align:center; color:#7A7670; font-size:0.95rem; margin-top:0.2rem; margin-bottom:1.8rem;
        }}
    </style>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)
        _render_brand_header()
        st.markdown(
            "<div class='login-tagline'>Digital Showroom Intelligence Portal &mdash; built by Infoleap for Royal Enfield</div>",
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown("##### Sign in")
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Submit", use_container_width=True)

            if submitted:
                users = _load_users()
                key = email.strip().lower()
                user = users.get(key)
                if user and user["active"] and password == user["password"]:
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = key
                    st.rerun()
                elif user and not user["active"]:
                    st.error("This account has been deactivated. Contact your admin.")
                else:
                    st.error("Invalid email or password.")

    return False


def render_landing() -> bool:
    """Branded interstitial shown once per session, between login and the
    dashboard itself — per user request: 'place a landing page where the
    infoleap x royalenfiled branding will mentioned, clicking there to
    next will open the whole page'. Gated the same way as render_login()."""
    if st.session_state.get("entered_dashboard"):
        return True

    st.markdown("""
    <style>
        .stApp { background: #FAFAF8; }
        .landing-tagline { text-align:center; color:#7A7670; font-size:1.05rem; margin-top:0.4rem; margin-bottom:0.4rem; }
        .landing-sub { text-align:center; color:#9A958D; font-size:0.85rem; margin-bottom:2.2rem; }
    </style>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<div style='height:12vh'></div>", unsafe_allow_html=True)
        _render_brand_header()
        st.markdown(
            "<div class='landing-tagline'>Digital Showroom Intelligence Portal</div>"
            "<div class='landing-sub'>Live segment analytics for Acceptors, Rejectors &amp; Booked-but-Cancelled — "
            "recomputed directly from the research Masterfile, built by Infoleap for Royal Enfield.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Enter Dashboard  →", use_container_width=True, type="primary"):
            st.session_state["entered_dashboard"] = True
            st.rerun()

    return False
