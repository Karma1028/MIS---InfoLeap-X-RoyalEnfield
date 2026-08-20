"""Login gate for the Royal Enfield x Infoleap Digital Showroom.

Auth backend: Firebase Auth (Email/Password + Google OAuth).
Session-state gated: render_login() returns True once authenticated.
"""
import csv
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
import bcrypt
from utils.branding import brand_header_html, swoosh_strip_html


def _firebase_api_key() -> str | None:
    """Return Firebase Web API Key from st.secrets or env, or None."""
    try:
        import streamlit as st
        if "FIREBASE_WEB_API_KEY" in st.secrets:
            return st.secrets["FIREBASE_WEB_API_KEY"]
    except Exception:
        pass
    return os.environ.get("FIREBASE_WEB_API_KEY")


def _firebase_login(email: str, password: str) -> dict | None:
    """Try Firebase login. Returns {email, uid} on success, {error: msg} on failure, None if not configured."""
    api_key = _firebase_api_key()
    if not api_key:
        return None  # Firebase not configured — fall through to xlsx
    import requests as _req
    try:
        resp = _req.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=10
        )
        if resp.status_code == 200:
            d = resp.json()
            return {"email": d["email"], "uid": d["localId"], "name": email.split("@")[0], "role": "user"}
        error = resp.json().get("error", {}).get("message", "UNKNOWN")
        _FIREBASE_ERRORS = {
            "EMAIL_NOT_FOUND": "Email not registered.",
            "INVALID_PASSWORD": "Incorrect password.",
            "USER_DISABLED": "Account disabled. Contact admin.",
            "INVALID_LOGIN_CREDENTIALS": "Invalid email or password.",
        }
        return {"error": _FIREBASE_ERRORS.get(error, "Login failed.")}
    except Exception as e:
        return {"error": f"Auth service unavailable: {e}"}


# ── Google OAuth helpers ──────────────────────────────────────────────────────

def _google_client_id() -> str | None:
    try:
        if "GOOGLE_CLIENT_ID" in st.secrets:
            return st.secrets["GOOGLE_CLIENT_ID"]
    except Exception:
        pass
    return os.environ.get("GOOGLE_CLIENT_ID")


def _google_client_secret() -> str | None:
    try:
        if "GOOGLE_CLIENT_SECRET" in st.secrets:
            return st.secrets["GOOGLE_CLIENT_SECRET"]
    except Exception:
        pass
    return os.environ.get("GOOGLE_CLIENT_SECRET")


def _google_redirect_uri() -> str:
    try:
        if "GOOGLE_REDIRECT_URI" in st.secrets:
            return st.secrets["GOOGLE_REDIRECT_URI"]
    except Exception:
        pass
    return os.environ.get("GOOGLE_REDIRECT_URI", "https://mis---infoleap-x-royalenfield-kbrtsyxq6xjcjvwwtjis4r.streamlit.app/")


def _google_auth_url() -> str | None:
    client_id = _google_client_id()
    if not client_id:
        return None
    redirect_uri = _google_redirect_uri()
    import urllib.parse
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def _exchange_google_code(code: str) -> dict | None:
    """Exchange OAuth code → Google ID token → Firebase sign-in. Returns auth dict or None."""
    import requests as _req
    client_id = _google_client_id()
    client_secret = _google_client_secret()
    redirect_uri = _google_redirect_uri()
    api_key = _firebase_api_key()
    if not all([client_id, client_secret, api_key]):
        return None
    # Step 1: exchange code for tokens
    token_resp = _req.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=10)
    if token_resp.status_code != 200:
        return {"error": "Google token exchange failed."}
    id_token = token_resp.json().get("id_token")
    if not id_token:
        return {"error": "No ID token from Google."}
    # Step 2: sign in to Firebase with Google ID token
    fb_resp = _req.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={api_key}",
        json={
            "postBody": f"id_token={id_token}&providerId=google.com",
            "requestUri": redirect_uri,
            "returnSecureToken": True,
            "returnIdpCredential": True,
        },
        timeout=10,
    )
    if fb_resp.status_code == 200:
        d = fb_resp.json()
        email = d.get("email", "")
        name = d.get("displayName", email.split("@")[0])
        return {"email": email, "uid": d.get("localId", ""), "name": name, "role": "user"}
    err = fb_resp.json().get("error", {}).get("message", "Google login failed.")
    return {"error": err}


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


def _hash_password(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()


def _verify_password(pwd: str, stored: str) -> bool:
    try:
        # bcrypt hash starts with $2b$ or $2a$
        if stored.startswith("$2"):
            return bcrypt.checkpw(pwd.encode(), stored.encode())
        # Legacy plaintext — accept and upgrade on next save
        return pwd == stored
    except Exception:
        return False


def _sync_users_from_drive():
    """Download users.xlsx from Drive folder via service account (always fresh)."""
    try:
        from utils.drive_loader import download_file
        Path(USERS_PATH).parent.mkdir(parents=True, exist_ok=True)
        download_file("users.xlsx", USERS_PATH)
        print("[users-sync] users.xlsx downloaded via service account.")
    except Exception as e:
        print(f"[users-sync] WARNING: failed to download users.xlsx: {e}")


def _ensure_users_file():
    """Ensure data/users.xlsx exists. Downloads from Drive if USERS_FILE_ID set."""
    _sync_users_from_drive()
    p = Path(USERS_PATH)
    if not p.exists():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=["email", "password", "name", "active", "role"]).to_excel(USERS_PATH, index=False)
        except Exception:
            pass


def _save_users(df: pd.DataFrame):
    """Write users DataFrame back to users.xlsx. Caller responsible for column correctness."""
    p = Path(USERS_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(USERS_PATH, index=False)


def add_user(email: str, name: str, password: str, role: str = "user") -> str:
    """Add new user row. Returns error string or empty string on success."""
    _ensure_users_file()
    try:
        df = pd.read_excel(USERS_PATH)
    except Exception:
        df = pd.DataFrame(columns=["email", "password", "name", "active", "role"])
    key = email.strip().lower()
    if key in df["email"].str.strip().str.lower().values:
        return f"User {key} already exists."
    new_row = pd.DataFrame([{"email": key, "password": _hash_password(password), "name": name.strip(), "active": "Y", "role": role.strip().lower()}])
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
        df = pd.DataFrame(columns=["email", "password", "name", "active"])
    mask = df["email"].str.strip().str.lower() == email.strip().lower()
    if not mask.any():
        return f"User {email} not found."
    df.loc[mask, "active"] = "Y" if active else "N"
    _save_users(df)
    evt = "USER_ACTIVATED" if active else "USER_REVOKED"
    _log_event(email, evt)
    return ""


def _load_users():
    """Load credentials from data/users.xlsx only — no hardcoded defaults."""
    users = {}
    _ensure_users_file()
    try:
        df = pd.read_excel(USERS_PATH)
        for _, r in df.iterrows():
            email = str(r['email']).strip().lower()
            if email and email != 'nan':
                pwd = str(r['password']) if pd.notna(r['password']) else ""
                active = str(r.get('active', 'Y')).strip().upper() != "N"
                role = str(r.get('role', 'user')).strip().lower() if 'role' in r.index else 'user'
                users[email] = {"password": pwd, "active": active, "name": str(r.get('name', '')), "role": role}
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
_SESSION_TTL = 8 * 3600
_INACTIVITY_TTL = 12 * 60


def _do_login(email: str, name: str, role: str, event: str):
    """Set session state for authenticated user and rerun."""
    st.session_state["authenticated"] = True
    st.session_state["auth_time"] = time.time()
    st.session_state["username"] = email.lower()
    st.session_state["user_role"] = role
    st.session_state["user_name"] = name
    st.session_state["_session_id"] = str(uuid.uuid4())[:8]
    st.session_state.pop("login_fails", None)
    st.session_state.pop("login_locked_until", None)
    st.session_state.pop("_google_code_used", None)
    _log_event(email, event)
    st.rerun()


def _touch_activity():
    """Call on every authenticated page load to reset the inactivity clock."""
    st.session_state["_last_activity"] = time.time()


def render_login() -> bool:
    # Session expiry — re-authenticate after 8 hours absolute, or 12 min inactivity
    if st.session_state.get("authenticated"):
        now = time.time()
        if now - st.session_state.get("auth_time", 0) < _SESSION_TTL:
            # Inactivity check
            last_active = st.session_state.get("_last_activity", now)
            if now - last_active < _INACTIVITY_TTL:
                _touch_activity()
                return True
            # Inactive too long
            st.session_state.pop("authenticated", None)
            st.session_state.pop("auth_time", None)
            st.session_state.pop("_last_activity", None)
            st.warning("Session expired due to inactivity. Please sign in again.")
        else:
            st.session_state.pop("authenticated", None)
            st.session_state.pop("auth_time", None)
            st.session_state.pop("_last_activity", None)
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
                "<div class='login-tagline'>Intelligence Portal &mdash; built by Infoleap for Royal Enfield</div>"
                "</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("##### Sign in")

            # ── Handle Google OAuth callback (code in URL) ────────────────
            params = st.query_params
            google_code = params.get("code")
            if google_code and not st.session_state.get("_google_code_used"):
                st.session_state["_google_code_used"] = True
                with st.spinner("Signing in with Google..."):
                    result = _exchange_google_code(google_code)
                st.query_params.clear()
                if result and "error" not in result:
                    _do_login(result["email"], result.get("name", ""), result.get("role", "user"), "GOOGLE_LOGIN")
                else:
                    st.error(result.get("error", "Google login failed.") if result else "Google login failed.")

            # ── Google Sign-In button ─────────────────────────────────────
            google_url = _google_auth_url()
            if google_url:
                st.link_button("🔵  Sign in with Google", google_url, use_container_width=True)
                st.markdown("<div style='text-align:center;color:#aaa;font-size:0.8rem;margin:0.4rem 0'>or</div>", unsafe_allow_html=True)

            # ── Email / Password form ─────────────────────────────────────
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
                    key = email.strip().lower()
                    fb = _firebase_login(key, password.strip())
                    if fb is None:
                        st.error("Auth service not configured.")
                    elif "error" in fb:
                        _fails += 1
                        st.session_state["login_fails"] = _fails
                        if _fails >= _MAX_ATTEMPTS:
                            st.session_state["login_locked_until"] = time.time() + _LOCKOUT_SECONDS
                            st.session_state["login_fails"] = 0
                            _log_event(key, "ACCOUNT_LOCKED")
                            st.error(f"Too many failed attempts. Locked for {_LOCKOUT_SECONDS}s.")
                        else:
                            _log_event(key, "LOGIN_FAILED")
                            st.error(f"{fb['error']} ({_MAX_ATTEMPTS - _fails} attempts remaining)")
                    else:
                        _do_login(fb["email"], fb.get("name", key.split("@")[0]), fb.get("role", "user"), "LOGIN_SUCCESS")

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
                "<div class='landing-tagline'>Intelligence Portal</div>"
                "<div class='landing-sub'>Live segment analytics for Acceptors, Rejectors &amp; Booked-but-Cancelled — "
                "recomputed directly from the research Masterfile, built by Infoleap for Royal Enfield.</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Enter Dashboard  →", use_container_width=True, type="primary"):
                st.session_state["entered_dashboard"] = True
                st.rerun()

    return False
