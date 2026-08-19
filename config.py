"""Central config — all credentials and project-level constants live here.
Set DRIVE_FILE_ID via environment variable or Streamlit Cloud secrets;
this file provides the fallback default only."""
import os

# Google Drive file ID for RE_MIS_Master.xlsx
# Set via .env (local) or Streamlit Cloud → Settings → Secrets
DRIVE_FILE_ID = os.environ.get("DRIVE_FILE_ID", "")

# Project metadata
PROJECT_NAME = "Royal Enfield MIS Dashboard"
CLIENT = "Royal Enfield"
AGENCY = "Infoleap"

# Data file paths
MASTER_FILE = "data/RE_MIS_Master.xlsx"
DQ2_CODEBOOK = "data/dq2_netting_codebook.json"
