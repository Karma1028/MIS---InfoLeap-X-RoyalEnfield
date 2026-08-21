# Royal Enfield MIS Intelligence Portal — Handover Documentation
**Infoleap Market Research · Version 5.0 · August 2026**  
Author: Tuhin Bhattacharya (Karma) · PGDM Big Data Analytics, GIM Goa · MIS Project Lead, Infoleap Mumbai  
GitHub: `Karma1028/MIS---InfoLeap-X-RoyalEnfield` · Branch: `main`

---

## 1. What This System Is

Enterprise analytics dashboard for **Infoleap Market Research** and **Royal Enfield**. Replaces a legacy PHP system (`gdnindia.com/RoyalEnfield`) with real-time, transparent calculations from raw survey microdata.

**Core value:** every KPI, significance test, demographic cross-tab, and chart is computed live from 4,391 raw respondent records. No pre-aggregated tables. Fully auditable Python.

---

## 2. Production Architecture

```
Google Drive (xlsx)  ←→  Master Google Sheet
       ↓  (whichever is newer wins — Drive API comparison)
  Streamlit Cloud (app boot: service account downloads winner as xlsx)
       ↓
  data/RE_MIS_Master.xlsx  (local cache)
       ↓
  DataEngine (pandas) → Streamlit UI (all pages)
       ↓
  Firebase Auth  |  Users Google Sheet  |  Audit Google Sheet
```

**Hosting:** Streamlit Community Cloud, auto-deployed from GitHub main branch.  
**Runtime:** Python 3.10+, Streamlit 1.58.0, Pandas 3.0.3, Plotly 6.8.0, SciPy 1.17.1.

---

## 3. Key Files

| File | Role |
|------|------|
| `app.py` | Main entry point — sidebar, all page routing, `@st.cache_resource` engine |
| `utils/data_engine.py` | Core analytics: load, filter, segment, table computation, month/quarter logic |
| `utils/drive_loader.py` | Drive API download — `download_latest_master()` compares xlsx vs Sheet modifiedTime |
| `utils/sheets_client.py` | Google Sheets API v4 wrapper for users and audit log |
| `auth.py` | Firebase Auth + Google Sheets users/audit (no xlsx files for auth) |
| `config.py` | Drive folder ID, Sheet IDs, filenames |
| `utils/compare.py` | Model Comparison page |
| `utils/platform_compare.py` | Platform Comparison page |
| `utils/settings_page.py` | Admin settings, user management, model config setup |
| `utils/model_config_setup.py` | Admin utility: auto-fill acceptor/rejector/cancelled codes in model_config sheet |
| `utils/visuals.py` | All chart + HTML table rendering |
| `utils/stat_engine.py` | Pooled Z-test significance engine |

---

## 4. Authentication & Users

- **Login:** Firebase email/password only (Google OAuth removed in commit `fad1a67`)
- **Users store:** Google Sheets (not xlsx). Sheet ID in `st.secrets["USERS_SHEET_ID"]`
- **Audit log:** Google Sheets. Sheet ID in `st.secrets["AUDIT_SHEET_ID"]`
- **Service account:** `re-mis-reader@royal-enfield-dashboard.iam.gserviceaccount.com`
- **Admin role:** hardcoded check on email domain or specific emails in `auth.py`

---

## 5. Data Pipeline — How Data Gets In

### 5.1 Master File Sync (on every app boot / Reload Data)
`utils/data_engine.py → _sync_from_drive()` calls `download_latest_master()`:
1. Fetches `modifiedTime` for `RE_MIS_Master.xlsx` in Drive folder via Drive API
2. Fetches `modifiedTime` for master Google Sheet (`MASTER_SHEET_ID`)
3. Whichever timestamp is newer: exports that as xlsx into `data/RE_MIS_Master.xlsx`
4. Falls back to local cache if Drive API fails

### 5.2 Master Excel Structure (`RE_MIS_Master.xlsx`)
Key sheets:

| Sheet | Purpose |
|-------|---------|
| `raw_data` | 4,391 respondents × 588 columns. Header on row 1 (row 0 is a label row — auto-detected) |
| `model_config` | Model registry: codes, names, platform, active/in_survey flags, segment codes |
| `column_mapping` | Semantic key → internal column name mapping |
| `display_groups` | Code → display label groupings for age/education/occupation/income |
| `segment_config` | Segment derivation config |
| `netting_KBF` / `netting_Rejector` / `netting_Cancelled` | KBF netting taxonomy |
| `month_order` | Ordered list of survey waves |

### 5.3 model_config Sheet — Critical Columns

| Column | Meaning |
|--------|---------|
| `model_code` | Integer code (1–15). Matches `aq3_po` column for acceptors |
| `model_name` | Full display name |
| `platform_cc` | `350CC` / `450CC` / `650CC` / `EV` |
| `platform_label` | UI display label |
| `active` | `YES`/`NO` — shows in dashboard dropdowns |
| `in_survey` | `YES`/`NO` — model has current survey data (affects segment counts) |
| `acceptor_code` | Raw `aq3_po` value that identifies an Acceptor |
| `rejector_code` | Raw `seg` value that identifies a Rejector |
| `cancelled_code` | Raw `seg` value that identifies a Cancelled respondent |

**Table-driven mapping** (not block math). `_n = max(in_survey=YES codes)` = 14 currently.  
Current mapping: acceptor_code = model_code (1–14), rejector = model_code+14 (15–28), cancelled = model_code+28 (29–42).

**EV (code 15):** `in_survey=NO`. acceptor/rejector/cancelled codes manually set. Will become `YES` when field team adds EV to survey — admin runs "Model Config Setup" in Settings after updating in_survey.

---

## 6. Segment Logic

Three segments derived from raw data:
- **Acceptor:** `aq3_po` value matches `acceptor_code` for the model
- **Rejector:** `seg` value matches `rejector_code` for the model  
- **Cancelled:** `seg` value matches `cancelled_code` for the model

Global vars in `data_engine.py`:
```python
_ACC_CODE_MAP: dict[int, int]   # acceptor_code → model_code
_REJ_CODE_MAP: dict[int, int]   # rejector_code → model_code
_CAN_CODE_MAP: dict[int, int]   # cancelled_code → model_code
_ACCEPTOR_MAX_CODE: int          # max code among in_survey=YES models (14)
_MAX_MODEL_CODE: int             # max of ALL configured models (15 incl. EV)
_HAS_EXPLICIT_CODES: bool        # True — table-driven mapping active
```

**Critical:** these dicts are updated **in-place** (`.clear()` + `.update()`) so cross-module imports stay valid. Rebinding would break `compare.py`'s reference.

---

## 7. Quarter / Time Labels

- Quarter labels use **month initials**: `AMJ'25` (Apr-Jun), `JAS'25` (Jul-Sep), `OND'25` (Oct-Dec), `JFM'26` (Jan-Mar)
- Indian FY: Q1=AMJ(Apr–Jun), Q2=JAS(Jul–Sep), Q3=OND(Oct–Dec), Q4=JFM(Jan–Mar)
- `month_label_to_fy_quarter(m)` → returns initials format (e.g. `"JAS'25"`)
- `fy_quarter_order` built dynamically from months present in data — same format

---

## 8. Caching Architecture

```python
@st.cache_resource   # load_engine() — DataEngine instance, survives reruns
@st.cache_data       # _tbl_filter(segment, platform, model_code, months_tuple)
                     # _tbl_age / _tbl_education / _tbl_occupation / etc.
session_state[_ck]   # section() results — per filter combo, per rerun
```

**Key:** `_tbl_filter` is the base cached filter. All filter calls in `app.py` use it. Previously, 5–6 uncached `engine.filter_df()` calls ran on every rerun — now all go through cache.

---

## 9. Streamlit Secrets Required

```toml
# .streamlit/secrets.toml (Streamlit Cloud app settings)

DRIVE_FOLDER_ID = "1SoD7nzHP8Lfnr8An2NT-SXO-IzJsKkJQ"
MASTER_SHEET_ID = "1j4TsEfRuG8A4wBAEaq72WWDC3LuoosuoMLIloHbrTQ4"
USERS_SHEET_ID  = "114fQKtm1qpsfQ1Y0_iZjgnE0m7871ANgQcbnrieWcOk"
AUDIT_SHEET_ID  = "1kRFQB7HPt3LHve2QLydrlKdJxhkVNMZR1h5n6biB1xc"

[firebase]
# Firebase project config (web SDK values)
apiKey = "..."
authDomain = "..."
projectId = "..."

[gcp_service_account]
# Service account JSON key (re-mis-reader@royal-enfield-dashboard.iam.gserviceaccount.com)
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
# ... rest of SA key fields
```

---

## 10. Admin Operations

### Add a New Model (when field team adds to survey)
1. Open master Google Sheet → `model_config` tab
2. Add row: fill `model_code` (next integer), `model_name`, `platform_cc`, `platform_label`, `active=YES`, `in_survey=YES`
3. Leave `acceptor_code`/`rejector_code`/`cancelled_code` blank
4. Dashboard → Settings → "Model Configuration" → **Run Setup** (auto-fills codes)
5. Dashboard → **Reload Data**

### Add Future Model (not yet in survey data)
Same as above but set `in_survey=NO`. Codes won't be auto-filled until it goes `YES`.

### Monthly Data Update
1. Export new survey wave xlsx
2. Either: upload to Drive folder as `RE_MIS_Master.xlsx` (overwrites), OR update master Google Sheet
3. Dashboard → **Reload Data** (picks whichever source is newer)

### User Management
Dashboard → Settings → Admin panel. Add/deactivate users directly (writes to Google Sheet).

---

## 11. Known Issues & Constraints

| Issue | Status |
|-------|--------|
| EV phantom respondents (2 Acceptors) | Fixed — `_ACCEPTOR_MAX_CODE` excludes in_survey=NO models |
| Model comparison showed no RE models | Fixed — module-level dicts now updated in-place |
| Page load slow on every sidebar click | Fixed — filter calls cached via `_tbl_filter` |
| Quarter labels inconsistent (old Q2 FY25-26 format) | Fixed — now JAS'25 format throughout |
| Stale browser session: Reset Filters button clears quarters key | Workaround |
| Initial cold start slow (Drive download + xlsx parse 6.7MB) | Expected — 20–40s, cached after |

---

## 12. Security Rules (Never Break These)

- Never commit `service_account.json`, Firebase keys, or `.env` to git
- Users/audit data: Google Sheets only (no local files)
- Tier 3 data (finance/health/diary): local only — no API calls
- Admin setup script writes to Google Sheet via service account — no local file edits

---

## 13. Repo Structure

```
/
├── app.py                    # Main Streamlit entry
├── auth.py                   # Firebase + Sheets auth
├── config.py                 # Drive/Sheet IDs, filenames
├── requirements.txt
├── utils/
│   ├── data_engine.py        # Core analytics engine
│   ├── drive_loader.py       # Drive API sync
│   ├── sheets_client.py      # Sheets API for users/audit
│   ├── model_config_setup.py # Admin: auto-fill segment codes
│   ├── settings_page.py      # Settings UI
│   ├── compare.py            # Model Comparison page
│   ├── platform_compare.py   # Platform Comparison page
│   ├── visuals.py            # Charts + HTML tables
│   ├── stat_engine.py        # Z-test significance
│   ├── branding.py           # Logos, CSS
│   └── ...
├── data/
│   └── RE_MIS_Master.xlsx    # Local cache (gitignored)
└── model_images/             # RE model photos
```
