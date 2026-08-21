"""One-time admin utility: writes in_survey / acceptor_code / rejector_code /
cancelled_code columns to the model_config sheet in the master Google Sheet,
then applies green/red conditional formatting on the in_survey column.
Called from the Settings page admin panel — runs via the app's service account.
"""
from __future__ import annotations


def _get_sheets_service():
    import os
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            creds = service_account.Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]),
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            return build("sheets", "v4", credentials=creds)
    except Exception:
        pass
    sa_file = os.environ.get("SERVICE_ACCOUNT_FILE", "service_account.json")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def _master_sheet_id() -> str:
    try:
        import streamlit as st
        if "MASTER_SHEET_ID" in st.secrets:
            return st.secrets["MASTER_SHEET_ID"]
    except Exception:
        pass
    from config import MASTER_SHEET_ID
    return MASTER_SHEET_ID


def _get_tab_grid_id(svc, spreadsheet_id: str, tab_name: str) -> int | None:
    """Return the gridId (sheetId) for a named tab."""
    meta = svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for s in meta.get("sheets", []):
        if s["properties"]["title"] == tab_name:
            return s["properties"]["sheetId"]
    return None


def setup_model_config_columns() -> tuple[bool, str]:
    """Read model_config tab, add/fill new columns, apply conditional formatting.
    Returns (success: bool, message: str)."""
    try:
        svc = _get_sheets_service()
        sid = _master_sheet_id()
        TAB = "model_config"

        # ── Read current data ─────────────────────────────────────────────
        result = svc.spreadsheets().values().get(
            spreadsheetId=sid, range=f"{TAB}"
        ).execute()
        rows = result.get("values", [])
        if not rows:
            return False, "model_config tab is empty."

        header = [str(c).strip() for c in rows[0]]
        data   = rows[1:]

        # ── Resolve existing column indices ───────────────────────────────
        def col_idx(name: str) -> int | None:
            try:
                return header.index(name)
            except ValueError:
                return None

        mc_idx  = col_idx("model_code")
        if mc_idx is None:
            return False, "model_code column not found in model_config."

        NEW_COLS = ["in_survey", "acceptor_code", "rejector_code", "cancelled_code"]
        # Add missing columns to header
        for c in NEW_COLS:
            if c not in header:
                header.append(c)

        is_idx  = header.index("in_survey")
        acc_idx = header.index("acceptor_code")
        rej_idx = header.index("rejector_code")
        can_idx = header.index("cancelled_code")

        # ── Build updated rows ────────────────────────────────────────────
        # Determine _n from max in-survey model code (fall back to 14)
        existing_in_survey_col = col_idx("in_survey")
        existing_codes_in_survey: list[int] = []
        for r in data:
            try:
                code = int(float(r[mc_idx]))
                in_s = str(r[existing_in_survey_col]).strip().upper() if (
                    existing_in_survey_col is not None and
                    existing_in_survey_col < len(r)
                ) else "YES"
                if in_s != "NO":
                    existing_codes_in_survey.append(code)
            except (ValueError, TypeError, IndexError):
                continue
        _n = max(existing_codes_in_survey) if existing_codes_in_survey else 14

        new_data: list[list] = []
        for r in data:
            row = list(r)
            # Pad to full header width
            while len(row) < len(header):
                row.append("")
            try:
                code = int(float(row[mc_idx]))
            except (ValueError, TypeError):
                new_data.append(row)
                continue

            # in_survey: keep existing value if set, else YES
            cur_is = str(row[is_idx]).strip().upper() if row[is_idx] else ""
            in_survey = cur_is if cur_is in ("YES", "NO") else "YES"
            row[is_idx] = in_survey

            # Only set code columns when in_survey=YES and not already filled
            if in_survey == "YES":
                if not str(row[acc_idx]).strip():
                    row[acc_idx] = code
                if not str(row[rej_idx]).strip():
                    row[rej_idx] = code + _n
                if not str(row[can_idx]).strip():
                    row[can_idx] = code + 2 * _n
            else:
                # in_survey=NO — leave code columns blank (future model)
                pass

            new_data.append(row)

        # ── Write header + data back ──────────────────────────────────────
        write_range = f"{TAB}!A1"
        body = {"values": [header] + new_data}
        svc.spreadsheets().values().update(
            spreadsheetId=sid,
            range=write_range,
            valueInputOption="RAW",
            body=body,
        ).execute()

        # ── Conditional formatting: in_survey column ──────────────────────
        grid_id = _get_tab_grid_id(svc, sid, TAB)
        if grid_id is not None:
            col_letter_idx = is_idx  # 0-based column index
            n_rows = len(new_data) + 1  # +1 for header
            requests = [
                # Clear existing conditional formatting rules on the sheet
                # (we re-add fresh ones)
            ]
            # Green for YES
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": grid_id,
                            "startRowIndex": 1,   # skip header
                            "endRowIndex": n_rows,
                            "startColumnIndex": col_letter_idx,
                            "endColumnIndex": col_letter_idx + 1,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": "YES"}],
                            },
                            "format": {
                                "backgroundColor": {"red": 0.714, "green": 0.843, "blue": 0.659},
                                "textFormat": {"bold": True},
                            },
                        },
                    },
                    "index": 0,
                }
            })
            # Red for NO
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": grid_id,
                            "startRowIndex": 1,
                            "endRowIndex": n_rows,
                            "startColumnIndex": col_letter_idx,
                            "endColumnIndex": col_letter_idx + 1,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": "NO"}],
                            },
                            "format": {
                                "backgroundColor": {"red": 0.918, "green": 0.600, "blue": 0.600},
                                "textFormat": {"bold": True},
                            },
                        },
                    },
                    "index": 1,
                }
            })
            svc.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={"requests": requests},
            ).execute()

        return True, f"model_config updated — {len(new_data)} models, in_survey column color-coded."
    except Exception as e:
        return False, f"Error: {e}"
