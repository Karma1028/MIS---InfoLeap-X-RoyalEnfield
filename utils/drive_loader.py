"""Dynamic Google Drive loader — resolves files by name, never hardcoded ID.
Works locally (service_account.json) and on Streamlit Cloud (st.secrets).
"""
import io
import os
import tempfile
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

from config import DRIVE_FOLDER_ID, DRIVE_FILES

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


def list_folder(folder_id: str = DRIVE_FOLDER_ID) -> list[dict]:
    """List all files in folder."""
    service = _get_service()
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id, name, mimeType, modifiedTime)",
        orderBy="name"
    ).execute()
    return results.get('files', [])
