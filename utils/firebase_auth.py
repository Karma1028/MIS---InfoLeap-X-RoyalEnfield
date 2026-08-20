"""Firebase Authentication — login, token verify, user info."""
import os
import requests
import firebase_admin
from firebase_admin import credentials, auth

_initialized = False

def _init():
    global _initialized
    if not _initialized:
        sa_file = os.environ.get("FIREBASE_SERVICE_ACCOUNT_FILE", "firebase_service_account.json")
        cred = credentials.Certificate(sa_file)
        firebase_admin.initialize_app(cred)
        _initialized = True


def login(email: str, password: str) -> dict | None:
    """Verify email+password via Firebase REST API.
    Returns user dict {email, uid, idToken} or None on failure."""
    api_key = os.environ.get("FIREBASE_WEB_API_KEY")
    if not api_key:
        raise ValueError("FIREBASE_WEB_API_KEY not set in environment")

    resp = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=10
    )
    if resp.status_code == 200:
        data = resp.json()
        return {
            "email": data["email"],
            "uid": data["localId"],
            "id_token": data["idToken"],
        }
    error = resp.json().get("error", {}).get("message", "UNKNOWN")
    # Map Firebase error codes to human messages
    messages = {
        "EMAIL_NOT_FOUND": "Email not registered.",
        "INVALID_PASSWORD": "Incorrect password.",
        "USER_DISABLED": "Account disabled. Contact admin.",
        "INVALID_LOGIN_CREDENTIALS": "Invalid email or password.",
    }
    return {"error": messages.get(error, "Login failed. Try again.")}


def get_user(uid: str) -> dict | None:
    """Get Firebase user record by UID (admin SDK)."""
    _init()
    try:
        user = auth.get_user(uid)
        return {"email": user.email, "uid": user.uid, "disabled": user.disabled}
    except auth.UserNotFoundError:
        return None


def list_users() -> list[dict]:
    """List all Firebase Auth users (admin SDK)."""
    _init()
    users = []
    for user in auth.list_users().iterate_all():
        users.append({"email": user.email, "uid": user.uid, "disabled": user.disabled})
    return users
