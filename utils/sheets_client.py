"""Google Sheets read/write client using the service account credentials.
Replaces users.xlsx and login_audit.csv with persistent Google Sheets.
Sheet IDs come from st.secrets or environment variables.
"""
import os

_sheets_service = None


def _get_service():
    global _sheets_service
    if _sheets_service is not None:
        return _sheets_service
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            creds = service_account.Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]),
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            _sheets_service = build("sheets", "v4", credentials=creds)
            return _sheets_service
    except Exception:
        pass
    sa_file = os.environ.get("SERVICE_ACCOUNT_FILE", "service_account.json")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    _sheets_service = build("sheets", "v4", credentials=creds)
    return _sheets_service


def _sheet_id(secret_key: str, env_key: str) -> str | None:
    try:
        import streamlit as st
        if secret_key in st.secrets:
            return st.secrets[secret_key]
    except Exception:
        pass
    return os.environ.get(env_key)


def read_sheet(sheet_id: str, range_: str = "Sheet1") -> list[list]:
    """Return all rows as list-of-lists. First row = headers."""
    svc = _get_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=range_
    ).execute()
    return result.get("values", [])


def append_row(sheet_id: str, row: list, range_: str = "Sheet1") -> None:
    """Append one row to the sheet."""
    svc = _get_service()
    svc.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=range_,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


def update_row(sheet_id: str, row_index: int, row: list, range_prefix: str = "Sheet1") -> None:
    """Overwrite a specific row (1-based, including header)."""
    svc = _get_service()
    range_ = f"{range_prefix}!A{row_index}:{chr(64 + len(row))}{row_index}"
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_,
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()


def ensure_header(sheet_id: str, headers: list, range_: str = "Sheet1") -> None:
    """Write header row if sheet is empty."""
    rows = read_sheet(sheet_id, range_)
    if not rows:
        append_row(sheet_id, headers, range_)


# ── Sheet ID helpers ──────────────────────────────────────────────────────────

def audit_sheet_id() -> str | None:
    return _sheet_id("AUDIT_SHEET_ID", "AUDIT_SHEET_ID")
