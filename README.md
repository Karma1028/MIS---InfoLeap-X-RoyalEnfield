# Royal Enfield MIS Portal — Infoleap

A Streamlit-based Market Intelligence System (MIS) portal built by **Infoleap** for **Royal Enfield**. Provides live segment analytics (Acceptors, Rejectors, Booked-but-Cancelled) recomputed directly from the research Masterfile, with statistical significance testing, model comparisons, and AI-assisted analysis.

---

## Features

- **Segment Analytics** — Acceptor, Rejector, BBC breakdowns across demographics
- **Statistical Significance** — Z-test engine with ▲/▼ arrows (95% confidence)
- **Model Comparison** — Head-to-head comparison across any two RE models
- **Platform Comparison** — 350cc vs 650cc platform deep-dives
- **Verbatim Intelligence** — 4-level netting tree (Supernet → Net → Subnet → Item)
- **Low-Base Handling** — Months with n<50 show highlighted base count, suppress data rows
- **Firebase Auth** — Email/password login with session management and audit log
- **Admin Panel** — Model config setup, login audit trail

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Data files (not in repo — gitignored)

Place in `data/`:
- `RE_MIS_Master.xlsx` — survey Masterfile (pulled from Google Drive on boot)

### 3. Streamlit secrets

Create `.streamlit/secrets.toml`:

```toml
# Google Drive — Masterfile source
DRIVE_FILE_ID = "..."

# Google Sheets service account (for audit log)
AUDIT_SHEET_ID = "..."
[gcp_service_account]
type = "service_account"
project_id = "royal-enfield-dashboard"
# ... rest of service account JSON fields

# Firebase Auth
FIREBASE_WEB_API_KEY = "..."

# Admin users (comma-separated emails)
ADMIN_EMAILS = "admin@infoleap.in, ..."

# AI keys (optional — can also be set in-app Settings)
GROQ_API_KEY = "..."
GEMINI_API_KEY = "..."
```

### 4. Run locally

```bash
streamlit run app.py
```

---

## Deployment (Streamlit Cloud)

1. Connect this repo (`Info-Leap/royal-enfield-mis-portal`) at [share.streamlit.io](https://share.streamlit.io)
2. Set **Main file**: `app.py`, **Branch**: `main`
3. Paste secrets in **Advanced settings → Secrets**
4. Deploy

---

## Project Structure

```
app.py                  # Main Streamlit app
auth.py                 # Firebase auth + session management
config.py               # App-wide constants
requirements.txt
assets/                 # Logos, model images
utils/
  data_engine.py        # Core data processing engine
  visuals.py            # Table + chart rendering
  stat_engine.py        # Z-test significance engine
  netting_taxonomy.py   # Verbatim netting tree
  model_images.py       # Model image path lookup
  settings_page.py      # Admin settings UI
  sheets_client.py      # Google Sheets API client (audit log)
  drive_loader.py       # Google Drive file sync
  overview_intro.py     # Overview page hero section
  compare.py            # Model comparison logic
  platform_compare.py   # Platform comparison logic
  branding.py           # RE + Infoleap brand assets
scripts/
  build_master.py       # Masterfile rebuild utility
  clean_master_sheets.py
tests/                  # Unit tests
```

---

*Built by Infoleap · Confidential — Royal Enfield Internal Use Only*
