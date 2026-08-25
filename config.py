"""Central config — all credentials and project-level constants live here."""
import os

# ── Google Drive ──────────────────────────────────────────────────────────────
# Only the FOLDER ID is fixed. File IDs are resolved dynamically by filename.
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "1SoD7nzHP8Lfnr8An2NT-SXO-IzJsKkJQ")
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "service_account.json")

# Filenames to search for inside the folder — update these if files are renamed
DRIVE_FILES = {
    "master": "RE_MIS_Master.xlsx",
}

# Google Sheet ID for master data — compared against xlsx modifiedTime at sync;
# whichever is newer wins and is downloaded as xlsx.
MASTER_SHEET_ID = os.environ.get("MASTER_SHEET_ID", "1j4TsEfRuG8A4wBAEaq72WWDC3LuoosuoMLIloHbrTQ4")

# ── Project metadata ──────────────────────────────────────────────────────────
PROJECT_NAME = "Royal Enfield MIS Dashboard"
CLIENT       = "Royal Enfield"
AGENCY       = "Infoleap"

# ── Local data paths (fallback / cache) ───────────────────────────────────────
MASTER_FILE  = "data/RE_MIS_Master.xlsx"
DQ2_CODEBOOK = "data/dq2_netting_codebook.json"
