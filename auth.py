"""Login gate for the Royal Enfield x Infoleap Digital Showroom.

Auth backend: Firebase Auth (Email/Password only).
Admin role: ADMIN_EMAILS in st.secrets (comma-separated string or list).
Audit log stored in Google Sheets (AUDIT_SHEET_ID).
"""
import os
import time
import uuid
from datetime import datetime
import pandas as pd
import streamlit as st
from utils.branding import brand_header_html, swoosh_strip_html

_AUDIT_COLS  = ["timestamp", "email", "event", "session_id"]


# ── Admin role ────────────────────────────────────────────────────────────────

def _is_admin(email: str) -> bool:
    """Return True if email is in ADMIN_EMAILS secret (comma-separated or list)."""
    try:
        raw = st.secrets.get("ADMIN_EMAILS", "")
        if isinstance(raw, str):
            admins = [e.strip().lower() for e in raw.split(",") if e.strip()]
        else:
            admins = [e.strip().lower() for e in raw]
        return email.strip().lower() in admins
    except Exception:
        return False


# ── Firebase helpers ──────────────────────────────────────────────────────────

def _firebase_api_key() -> str | None:
    try:
        if "FIREBASE_WEB_API_KEY" in st.secrets:
            return st.secrets["FIREBASE_WEB_API_KEY"]
    except Exception:
        pass
    return os.environ.get("FIREBASE_WEB_API_KEY")


def _firebase_send_reset(email: str) -> str | None:
    api_key = _firebase_api_key()
    if not api_key:
        return "Auth service not configured."
    import requests as _req
    try:
        resp = _req.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}",
            json={"requestType": "PASSWORD_RESET", "email": email},
            timeout=10,
        )
        if resp.status_code == 200:
            return None
        err = resp.json().get("error", {}).get("message", "UNKNOWN")
        return {"EMAIL_NOT_FOUND": "No account with that email."}.get(err, "Reset failed.")
    except Exception as e:
        return f"Auth service unavailable: {e}"


def _firebase_login(email: str, password: str) -> dict | None:
    api_key = _firebase_api_key()
    if not api_key:
        return None
    import requests as _req
    try:
        resp = _req.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=10
        )
        if resp.status_code == 200:
            d = resp.json()
            role = "admin" if _is_admin(d["email"]) else "user"
            return {"email": d["email"], "uid": d["localId"], "name": email.split("@")[0], "role": role}
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


# ── Sheets helpers ────────────────────────────────────────────────────────────

def _audit_sid() -> str | None:
    from utils.sheets_client import audit_sheet_id
    return audit_sheet_id()


def _sheet_to_df(rows: list[list], cols: list[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=cols)
    header = [str(c).strip() for c in rows[0]]
    data   = rows[1:]
    df = pd.DataFrame(data, columns=header)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]


# ── Audit log ─────────────────────────────────────────────────────────────────

def _log_event(email: str, event: str):
    sid = _audit_sid()
    if not sid:
        return
    try:
        from utils.sheets_client import ensure_header, append_row
        ensure_header(sid, _AUDIT_COLS)
        session_id = st.session_state.get("_session_id", "")
        row = [
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            email.lower(), event, session_id,
        ]
        append_row(sid, row)
    except Exception as e:
        print(f"[auth] audit log write error: {e}")


def load_audit_log(n: int = 100) -> pd.DataFrame:
    sid = _audit_sid()
    if not sid:
        return pd.DataFrame(columns=_AUDIT_COLS)
    try:
        from utils.sheets_client import read_sheet
        rows = read_sheet(sid)
        df = _sheet_to_df(rows, _AUDIT_COLS)
        return df.tail(n).iloc[::-1].reset_index(drop=True)
    except Exception as e:
        print(f"[auth] audit log read error: {e}")
        return pd.DataFrame(columns=_AUDIT_COLS)


# ── UI helpers ────────────────────────────────────────────────────────────────

def _render_brand_header():
    st.markdown(brand_header_html(), unsafe_allow_html=True)


_MAX_ATTEMPTS    = 5
_LOCKOUT_SECONDS = 60
_SESSION_TTL     = 8 * 3600
_INACTIVITY_TTL  = 37 * 60  # 37 mins (increased by 25 mins from 12 mins)


def _do_login(email: str, name: str, role: str, event: str):
    st.session_state["authenticated"]  = True
    st.session_state["auth_time"]      = time.time()
    st.session_state["username"]       = email.lower()
    st.session_state["user_role"]      = role
    st.session_state["user_name"]      = name
    st.session_state["_session_id"]    = str(uuid.uuid4())[:8]
    st.session_state.pop("login_fails", None)
    st.session_state.pop("login_locked_until", None)
    _log_event(email, event)
    st.rerun()


def _touch_activity():
    st.session_state["_last_activity"] = time.time()


def render_login() -> bool:
    if st.session_state.get("authenticated"):
        now = time.time()
        if now - st.session_state.get("auth_time", 0) < _SESSION_TTL:
            last_active = st.session_state.get("_last_activity", now)
            if now - last_active < _INACTIVITY_TTL:
                _touch_activity()
                return True
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

            with st.form("login_form"):
                email    = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                _fails        = st.session_state.get("login_fails", 0)
                _locked_until = st.session_state.get("login_locked_until", 0)
                if time.time() < _locked_until:
                    remaining = int(_locked_until - time.time())
                    st.error(f"Too many failed attempts. Try again in {remaining}s.")
                else:
                    key = email.strip().lower()
                    fb  = _firebase_login(key, password.strip())
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

            st.markdown("<hr style='margin:0.8rem 0 0.6rem;border:none;border-top:1px solid #E8E5DF;'>", unsafe_allow_html=True)
            _show_reset = st.toggle("Forgot password?", key="show_reset", value=False)
            if _show_reset:
                reset_email = st.text_input("Enter your email address", key="reset_email", label_visibility="collapsed", placeholder="your@email.com")
                if st.button("Send reset email", key="send_reset", use_container_width=True):
                    if not reset_email.strip():
                        st.error("Enter your email address.")
                    else:
                        err = _firebase_send_reset(reset_email.strip().lower())
                        if err:
                            st.error(err)
                        else:
                            st.success("Password reset email sent. Check your inbox.")

    return False


def render_landing() -> bool:
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
