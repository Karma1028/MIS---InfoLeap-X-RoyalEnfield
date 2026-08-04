"""Login gate for the Royal Enfield x Infoleap Digital Showroom.

Session-state gated: render_login() returns True once authenticated, and the
caller (app.py) should st.stop() if it returns False.
"""
import csv
import time
import uuid
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from utils.branding import brand_header_html, swoosh_strip_html

USERS_PATH = "data/users.xlsx"
AUDIT_LOG_PATH = "data/login_audit.csv"
_AUDIT_COLS = ["timestamp", "email", "event", "session_id"]


def _log_event(email: str, event: str):
    """Append one auth event row to login_audit.csv (creates file + header on first write)."""
    log_path = Path(AUDIT_LOG_PATH)
    write_header = not log_path.exists() or log_path.stat().st_size == 0
    session_id = st.session_state.get("_session_id", "")
    row = [datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), email.lower(), event, session_id]
    with log_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(_AUDIT_COLS)
        w.writerow(row)


def load_audit_log(n: int = 100) -> pd.DataFrame:
    """Return last n rows of login_audit.csv for display in Settings."""
    p = Path(AUDIT_LOG_PATH)
    if not p.exists():
        return pd.DataFrame(columns=_AUDIT_COLS)
    df = pd.read_csv(p)
    return df.tail(n).iloc[::-1].reset_index(drop=True)


DEFAULT_USERS_DATA = [
    {"email": "misdashboard@infoleap", "password": "MIS_INFOLEAP@1234", "name": "Infoleap MIS Team", "active": "Y"},
    {"email": "misdashboard@infoleap.com", "password": "MIS_INFOLEAP@1234", "name": "Infoleap MIS Team", "active": "Y"},
    {"email": "misdashboard", "password": "MIS_INFOLEAP@1234", "name": "Infoleap MIS Team", "active": "Y"},
    {"email": "test@test", "password": "test@123", "name": "Test Account", "active": "Y"},
]


def _ensure_users_file():
    """Ensure data/users.xlsx exists with default accounts on fresh deployments."""
    p = Path(USERS_PATH)
    if not p.exists():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            df = pd.DataFrame(DEFAULT_USERS_DATA)
            df.to_excel(USERS_PATH, index=False)
        except Exception:
            pass


def _save_users(df: pd.DataFrame):
    """Write users DataFrame back to users.xlsx. Caller responsible for column correctness."""
    p = Path(USERS_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(USERS_PATH, index=False)


def add_user(email: str, name: str, password: str) -> str:
    """Add new user row. Returns error string or empty string on success."""
    _ensure_users_file()
    try:
        df = pd.read_excel(USERS_PATH)
    except Exception:
        df = pd.DataFrame(DEFAULT_USERS_DATA)
    key = email.strip().lower()
    if key in df["email"].str.strip().str.lower().values:
        return f"User {key} already exists."
    new_row = pd.DataFrame([{"email": key, "password": password, "name": name.strip(), "active": "Y"}])
    df = pd.concat([df, new_row], ignore_index=True)
    _save_users(df)
    _log_event(key, "USER_ADDED")
    return ""


def set_user_active(email: str, active: bool) -> str:
    """Toggle active flag for a user. Returns error string or empty string on success."""
    _ensure_users_file()
    try:
        df = pd.read_excel(USERS_PATH)
    except Exception:
        df = pd.DataFrame(DEFAULT_USERS_DATA)
    mask = df["email"].str.strip().str.lower() == email.strip().lower()
    if not mask.any():
        return f"User {email} not found."
    df.loc[mask, "active"] = "Y" if active else "N"
    _save_users(df)
    evt = "USER_ACTIVATED" if active else "USER_REVOKED"
    _log_event(email, evt)
    return ""


def _load_users():
    """Credentials live in data/users.xlsx (columns: email, password, name, active).
    Always pre-populated with DEFAULT_USERS_DATA so login is bulletproof even on cloud deployments."""
    users = {}
    for r in DEFAULT_USERS_DATA:
        email = r['email'].strip().lower()
        users[email] = {"password": str(r['password']), "active": r['active'] != "N", "name": r['name']}

    p = Path(USERS_PATH)
    if p.exists():
        try:
            df = pd.read_excel(USERS_PATH)
            for _, r in df.iterrows():
                email = str(r['email']).strip().lower()
                if email and email != 'nan':
                    pwd = str(r['password']) if pd.notna(r['password']) else ""
                    active = str(r.get('active', 'Y')).strip().upper() != "N"
                    users[email] = {"password": pwd, "active": active, "name": str(r.get('name', ''))}
        except Exception:
            pass
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
    # Real Infoleap + Royal Enfield logo images (utils/branding.py) —
    # replaces the earlier CSS-mock (3 colored squares standing in for
    # the real Infoleap mark, per BUGS.md) now that both logos exist as
    # actual assets, sourced from the client's own PPT (2026-07-27).
    st.markdown(brand_header_html(), unsafe_allow_html=True)


_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60
_SESSION_TTL = 8 * 3600  # 8 hours


def render_login() -> bool:
    # Session expiry — re-authenticate after 8 hours
    if st.session_state.get("authenticated"):
        if time.time() - st.session_state.get("auth_time", 0) < _SESSION_TTL:
            return True
        st.session_state.pop("authenticated", None)
        st.session_state.pop("auth_time", None)
        st.warning("Session expired. Please sign in again.")

    st.markdown("""
    <style>
        .stApp { background: #FAFAF8; }
        .login-tagline {
            text-align:center; color:#7A7670; font-size:0.95rem; margin-top:0.2rem; margin-bottom:1.8rem;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            box-shadow: 0 4px 24px rgba(26,26,26,0.06);
        }
    </style>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.markdown("<div style='height:9vh'></div>", unsafe_allow_html=True)
        st.markdown(swoosh_strip_html(), unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<div style='padding:0.8rem 0.5rem 0 0.5rem;'>", unsafe_allow_html=True)
            _render_brand_header()
            st.markdown(
                "<div class='login-tagline'>Digital Showroom Intelligence Portal &mdash; built by Infoleap for Royal Enfield</div>"
                "</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("##### Sign in")
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                _fails = st.session_state.get("login_fails", 0)
                _locked_until = st.session_state.get("login_locked_until", 0)
                if time.time() < _locked_until:
                    remaining = int(_locked_until - time.time())
                    st.error(f"Too many failed attempts. Try again in {remaining}s.")
                else:
                    users = _load_users()
                    key = email.strip().lower()
                    user = users.get(key)
                    if user and user["active"] and password.strip() == str(user["password"]).strip():
                        st.session_state["authenticated"] = True
                        st.session_state["auth_time"] = time.time()
                        st.session_state["username"] = key
                        st.session_state["_session_id"] = str(uuid.uuid4())[:8]
                        st.session_state.pop("login_fails", None)
                        st.session_state.pop("login_locked_until", None)
                        _log_event(key, "LOGIN_SUCCESS")
                        st.rerun()
                    elif user and not user["active"]:
                        _log_event(key, "ACCOUNT_INACTIVE")
                        st.error("This account has been deactivated. Contact your admin.")
                    else:
                        _fails += 1
                        st.session_state["login_fails"] = _fails
                        if _fails >= _MAX_ATTEMPTS:
                            st.session_state["login_locked_until"] = time.time() + _LOCKOUT_SECONDS
                            st.session_state["login_fails"] = 0
                            _log_event(key, "ACCOUNT_LOCKED")
                            st.error(f"Too many failed attempts. Account locked for {_LOCKOUT_SECONDS}s.")
                        else:
                            _log_event(key, "LOGIN_FAILED")
                            st.error(f"Invalid email or password. ({_MAX_ATTEMPTS - _fails} attempts remaining)")

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
        .landing-sub { text-align:center; color:#9A958D; font-size:0.85rem; margin-bottom:1.4rem; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            box-shadow: 0 4px 24px rgba(26,26,26,0.06);
        }
    </style>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
        st.markdown(swoosh_strip_html(), unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<div style='padding:0.8rem 0.5rem 1.6rem 0.5rem;'>", unsafe_allow_html=True)
            _render_brand_header()
            st.markdown(
                "<div class='landing-tagline'>Digital Showroom Intelligence Portal</div>"
                "<div class='landing-sub'>Live segment analytics for Acceptors, Rejectors &amp; Booked-but-Cancelled — "
                "recomputed directly from the research Masterfile, built by Infoleap for Royal Enfield.</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Enter Dashboard  →", use_container_width=True, type="primary"):
                st.session_state["entered_dashboard"] = True
                st.rerun()

    return False
