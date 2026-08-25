"""Dynamic Google Drive loader — resolves files by name, never hardcoded ID.
Works locally (service_account.json) and on Streamlit Cloud (st.secrets).
"""
import io
import os
import tempfile
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

from config import DRIVE_FOLDER_ID, DRIVE_FILES, MASTER_SHEET_ID

SCOPES = [
    'https://www.googleapis.com/auth/drive',  # full access — needed to update shared files
]

_service = None


def _get_credentials():
    """Return credentials — from st.secrets on Cloud, from JSON file locally."""
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            from google.oauth2 import service_account
            return service_account.Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=SCOPES
            )
    except Exception:
        pass
    # Local fallback — JSON file
    sa_file = os.environ.get("SERVICE_ACCOUNT_FILE", "service_account.json")
    from google.oauth2 import service_account
    return service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)


def _get_service():
    global _service
    if _service is None:
        _service = build('drive', 'v3', credentials=_get_credentials())
    return _service


def find_file_id(filename: str, folder_id: str = DRIVE_FOLDER_ID) -> str | None:
    """Search folder for filename — returns file ID or None."""
    service = _get_service()
    safe_name = filename.replace("'", "\\'")
    q = f"'{folder_id}' in parents and name = '{safe_name}' and trashed = false"
    results = service.files().list(
        q=q, fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc", pageSize=5
    ).execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None


def download_file(filename: str, dest_path: str, folder_id: str = DRIVE_FOLDER_ID) -> str:
    """Download file by name to dest_path. Returns dest_path."""
    service = _get_service()
    file_id = find_file_id(filename, folder_id)
    if not file_id:
        raise FileNotFoundError(f"'{filename}' not found in Drive folder {folder_id}")
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    with io.FileIO(dest_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return dest_path


def load_excel(key: str, sheet_name=0) -> pd.DataFrame:
    """Download DRIVE_FILES[key] to temp file, return as DataFrame."""
    filename = DRIVE_FILES[key]
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name
    download_file(filename, tmp_path)
    df = pd.read_excel(tmp_path, sheet_name=sheet_name)
    os.unlink(tmp_path)
    return df


def load_csv(key: str) -> pd.DataFrame:
    """Download DRIVE_FILES[key] (csv) to temp file, return as DataFrame."""
    filename = DRIVE_FILES[key]
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name
    download_file(filename, tmp_path)
    df = pd.read_csv(tmp_path)
    os.unlink(tmp_path)
    return df


def upload_file(local_path: str, filename: str, folder_id: str = DRIVE_FOLDER_ID) -> str:
    """Upload local_path to Drive folder, replacing existing file of same name.
    Returns file ID. Requires Editor access on the file."""
    import mimetypes
    service = _get_service()
    mime_type = mimetypes.guess_type(local_path)[0] or 'application/octet-stream'
    media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)

    existing_id = find_file_id(filename, folder_id)
    if existing_id:
        # Update existing file content
        updated = service.files().update(
            fileId=existing_id,
            media_body=media,
        ).execute()
        return updated['id']
    else:
        # Create new file in folder
        metadata = {'name': filename, 'parents': [folder_id]}
        created = service.files().create(
            body=metadata,
            media_body=media,
            fields='id'
        ).execute()
        return created['id']


def _file_modified_time(file_id: str) -> str | None:
    """Return RFC 3339 modifiedTime string for any Drive/Sheet file ID, or None."""
    try:
        meta = _get_service().files().get(
            fileId=file_id, fields="modifiedTime"
        ).execute()
        return meta.get("modifiedTime")
    except Exception:
        return None


def _find_master_in_folder() -> tuple[str | None, str | None]:
    """Return (file_id, mime_type) for the best RE_MIS_Master file in the folder.
    Prefers an uploaded .xlsx over the Google Sheet of the same name."""
    service = _get_service()
    results = service.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and name contains 'RE_MIS_Master' and trashed = false",
        fields="files(id,name,mimeType,modifiedTime)",
        orderBy="modifiedTime desc",
    ).execute()
    files = results.get("files", [])
    xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    sheet_mime = "application/vnd.google-apps.spreadsheet"
    # Prefer xlsx upload over Google Sheet
    for f in files:
        if f["mimeType"] == xlsx_mime:
            print(f"[drive] found xlsx: {f['name']} (id={f['id']})")
            return f["id"], xlsx_mime
    for f in files:
        if f["mimeType"] == sheet_mime:
            print(f"[drive] found Google Sheet: {f['name']} (id={f['id']}) — will export as xlsx")
            return f["id"], sheet_mime
    return None, None


def download_latest_master(dest_path: str) -> str:
    """Download RE_MIS_Master from Google Drive folder.
    Prefers an uploaded .xlsx; falls back to exporting the Google Sheet.
    Returns dest_path."""
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    file_id, mime = _find_master_in_folder()

    if not file_id:
        raise FileNotFoundError(
            "RE_MIS_Master not found in Drive folder. "
            "Upload RE_MIS_Master.xlsx to the Drive folder and reload."
        )

    xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if mime == xlsx_mime:
        # Direct binary download
        service = _get_service()
        request = service.files().get_media(fileId=file_id)
        with io.FileIO(dest_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        print("[drive] xlsx download complete")
    else:
        # Export Google Sheet → xlsx
        import requests as _req
        from google.auth.transport.requests import Request as AuthRequest
        creds = _get_credentials()
        if not creds.valid:
            creds.refresh(AuthRequest())
        resp = _req.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
            params={"mimeType": xlsx_mime},
            headers={"Authorization": f"Bearer {creds.token}"},
            stream=True,
            timeout=120,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Sheet export failed ({resp.status_code}): {resp.text[:200]}")
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        print("[drive] Sheet export complete")

    return dest_path


def list_folder(folder_id: str = DRIVE_FOLDER_ID) -> list[dict]:
    """List all files in folder."""
    service = _get_service()
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id, name, mimeType, modifiedTime)",
        orderBy="name"
    ).execute()
    return results.get('files', [])
