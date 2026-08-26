"""
Recomputes the Royal Enfield live-dashboard tables directly from the raw
Masterfile, instead of trusting the precomputed scrape. See
docs/DATA_FIELD_MAPPING.md for the full source-column research behind every
choice below — do not change a mapping here without updating that doc too.

Per user instruction (2026-06-18): only closed-ended questions are in scope.
Key Buying Factors / Reasons for Cancelling / Reasons for Rejection are
AI-clustered verbatim output on the live site (no coded source column exists
anywhere in the datamap) and are explicitly OUT OF SCOPE.
"""
import os
import re
import json
import pandas as pd
import numpy as np
from pathlib import Path

MASTERFILE_PATH = "data/RE_MIS_Master.xlsx"
RAW_DATA_SHEET = "raw_data"
DATAMAP_PATH = "data/RE_MIS_Master.xlsx"  # datamap sheets now embedded in master file
DQ2_CODEBOOK_PATH = "data/dq2_netting_codebook.json"
DATA_DIR = Path("data")
MASTER_CONFIG_PATH = DATA_DIR / "RE_MIS_Master.xlsx"

_DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "1SoD7nzHP8Lfnr8An2NT-SXO-IzJsKkJQ")
_DRIVE_FILES = {
    "RE_MIS_Master.xlsx": "master",
    "users.xlsx":         "users",
    "login_audit.csv":    "login_audit",
}

def _sync_from_drive(force: bool = False):
    """Download data files from Drive using service account. No gdown, no public links."""
    file_missing = not Path(MASTERFILE_PATH).exists()
    try:
        from utils.drive_loader import download_latest_master
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        download_latest_master(str(DATA_DIR / "RE_MIS_Master.xlsx"))
        print("[drive-sync] Downloaded: RE_MIS_Master.xlsx (latest source)")
    except Exception as e:
        if file_missing:
            raise RuntimeError(
                f"RE_MIS_Master.xlsx not found and Drive sync failed: {e}"
            ) from e
        print(f"[drive-sync] WARNING: Drive sync failed, using local files. Error: {e}")
        try:
            import streamlit as st
            st.session_state["_drive_sync_warning"] = (
                f"⚠️ Data could not be refreshed from Drive — showing last cached version. ({type(e).__name__})"
            )
        except Exception:
            pass


def load_display_groups(xl_or_df=None):
    """Read display_groups sheet → {variable: {code_float: label_or_None}}.
    label_or_None: str = display label (same label on multiple codes = merged);
    None = drop that code from chart (blank cell in sheet).
    Falls back to empty dict (raw datamap labels used as-is) if sheet absent."""
    if not MASTER_CONFIG_PATH.exists() and xl_or_df is None:
        return {}
    try:
        if isinstance(xl_or_df, pd.DataFrame):
            df = xl_or_df
        elif isinstance(xl_or_df, pd.ExcelFile):
            df = xl_or_df.parse("display_groups")
        else:
            df = pd.read_excel(MASTER_CONFIG_PATH, sheet_name="display_groups")
        # Skip note rows: variable must be a short word (no spaces, not the header note)
        df = df[df["variable"].astype(str).str.match(r'^\w+$', na=False)]
        result = {}
        for _, row in df.iterrows():
            var  = str(row["variable"]).strip()
            try:
                code = float(row["code"])
            except (ValueError, TypeError):
                continue
            raw_lbl = row.get("display_label", "")
            lbl = str(raw_lbl).strip() if pd.notna(raw_lbl) else ""
            # Blank or explicit drop marker → None (drop from chart)
            if not lbl or lbl.startswith("(dropped"):
                lbl = None
            result.setdefault(var, {})[code] = lbl
        return result
    except Exception:
        return {}


def load_column_mapping(xl_or_df=None):
    """Reads column_mapping sheet from RE_MIS_Master.xlsx.
    Returns {raw_column: internal_name}. Falls back to empty dict
    (identity mapping — raw names used as-is) if master config missing."""
    if not MASTER_CONFIG_PATH.exists() and xl_or_df is None:
        return {}
    try:
        if isinstance(xl_or_df, pd.DataFrame):
            df = xl_or_df
        elif isinstance(xl_or_df, pd.ExcelFile):
            df = xl_or_df.parse("column_mapping")
        else:
            df = pd.read_excel(MASTER_CONFIG_PATH, sheet_name="column_mapping")
        # Skip note rows: real column names never contain spaces
        df = df[df["raw_column"].astype(str).str.strip().str.contains(r'^\S+$', na=False)]
        # New 5-col structure: raw_column → raw_column (no internal rename needed)
        # Special case: age_raw (dq7) maps to 'age_numeric' for legacy compat
        _SK_COL = "semantic_key" if "semantic_key" in df.columns else None
        rename = {}
        for _, row in df.iterrows():
            raw = str(row.get("raw_column", "")).strip()
            sk  = str(row.get(_SK_COL, "") if _SK_COL else "").strip()
            # Only rename dq7→age_numeric; everything else keeps raw name
            if sk == "age_raw" and raw and raw != "age_numeric":
                rename[raw] = "age_numeric"
        return rename
    except Exception:
        return {}


def load_field_registry(xl_or_df=None):
    """Read column_mapping → {semantic_key: raw_column}.
    Python uses self.F['education'] to get the actual df column name.
    Returns empty dict if sheet absent."""
    if not MASTER_CONFIG_PATH.exists() and xl_or_df is None:
        return {}
    try:
        if isinstance(xl_or_df, pd.DataFrame):
            df = xl_or_df
        elif isinstance(xl_or_df, pd.ExcelFile):
            df = xl_or_df.parse("column_mapping")
        else:
            df = pd.read_excel(MASTER_CONFIG_PATH, sheet_name="column_mapping")
        df = df[df["raw_column"].astype(str).str.strip().str.contains(r'^\S+$', na=False)]
        if "semantic_key" not in df.columns:
            return {}
        result = {}
        for _, row in df.iterrows():
            sk  = str(row.get("semantic_key", "")).strip()
            raw = str(row.get("raw_column", "")).strip()
            if sk and raw and sk != "nan" and raw != "nan":
                if sk not in result:  # first match wins — ignore duplicate semantic keys
                    result[sk] = "age_numeric" if sk == "age_raw" else raw
        return result
    except Exception:
        return {}


def get_required_columns(xl_or_df=None):
    """All mapped raw_column names are required — no required column in sheet anymore."""
    if not MASTER_CONFIG_PATH.exists() and xl_or_df is None:
        return set()
    try:
        if isinstance(xl_or_df, pd.DataFrame):
            df = xl_or_df
        elif isinstance(xl_or_df, pd.ExcelFile):
            df = xl_or_df.parse("column_mapping")
        else:
            df = pd.read_excel(MASTER_CONFIG_PATH, sheet_name="column_mapping")
        df = df[df["raw_column"].astype(str).str.strip().str.contains(r'^\S+$', na=False)]
        # Exclude wildcard prefix rows (multi-select) from hard validation
        return {str(r).strip() for r in df["raw_column"] if "*" not in str(r)}
    except Exception:
        return set()

# MONTH_ORDER is intentionally NOT a hardcoded literal list. Per user
# instruction (2026-06-18): "do not hard code anything... month by month
# data will come so make the nature dynamic". DataEngine.load_data()
# populates this in place (MONTH_ORDER[:] = ...) from whatever months are
# actually present in the loaded data, in true chronological order — so
# dropping a new month's extract into data/monthly_drops/ and restarting
# picks it up automatically, no code change needed. Historical note: an
# earlier version of this file hardcoded a fixed 9-month window to match
# one frozen validation snapshot (docs/investigation/full_scraped_data.json,
# scraped before May 2026 data existed) — see BUGS.md Bug #1 for that
# validation finding, and PROJECT_LOG.md for why production now shows all
# available months instead of re-hiding new real data going forward.
MONTH_ORDER = []

# Indian FY quarter -> calendar-month initials, for the live site's always-
# shown quarter-combined columns confirmed via a fresh scrape (2026-06-22):
# "JAS'25" (Jul-Aug-Sep 2025), "OND'25" (Oct-Nov-Dec 2025), "JFM'26" (Jan-
# Feb-Mar 2026) appear after the monthly columns on every table — even
# JAS'25 keeps its full 3-letter name though July has zero rows (it's named
# for the calendar quarter, not just whichever months happen to have data).
QUARTER_INITIALS = {1: "AMJ", 2: "JAS", 3: "OND", 4: "JFM"}

FY_QUARTER_ORDER = []  # populated alongside MONTH_ORDER, in FY chronological order


def month_label_to_fy_quarter(month_label):
    """Indian Financial Year quarter (Apr-Mar) for any 'MonthName'Year'
    label, computed from the actual calendar month/year — not a lookup
    table — so it generalizes to any future month automatically. Per
    MIS_Dashboard_Requirements.docx 2: 'Quarter Wise — view data
    aggregated by quarter (Q1, Q2, Q3, Q4)'. Q1=Apr-Jun, Q2=Jul-Sep,
    Q3=Oct-Dec, Q4=Jan-Mar."""
    name, year = month_label.split("'")
    dt = pd.to_datetime(f"{name} 1, {year}")
    month_num, cal_year = dt.month, dt.year
    if month_num in (4, 5, 6):
        q, fy_start = 1, cal_year
    elif month_num in (7, 8, 9):
        q, fy_start = 2, cal_year
    elif month_num in (10, 11, 12):
        q, fy_start = 3, cal_year
    else:
        q, fy_start = 4, cal_year - 1
    year_suffix = str(cal_year)[2:]
    return f"{QUARTER_INITIALS[q]}'{year_suffix}"


MONTHLY_DROPS_DIR = "data/monthly_drops"  # poor-man's sync target: drop a
# new month's extract .xlsx here (same schema as the Masterfile) and it
# gets merged in automatically on next load. True SharePoint auto-sync
# needs an Azure AD app registration + Graph API credentials from
# Royal Enfield/Infoleap IT — wire that in once those exist; this folder
# is the interim mechanism so the system itself isn't hardcoded to one file.

def load_model_config(xl_or_df=None):
    """Read model_config sheet → (labels, platform, platform_labels).
    labels:          {code: model_name}   — all active models
    platform:        {code: platform_cc}  — e.g. {1:'350CC', 6:'450CC'}
    platform_labels: {platform_cc: display_label} — e.g. {'350CC':'J Platform (350CC)'}
    Fully dynamic: add rows/platforms to model_config sheet, no code change needed.
    Called after _sync_from_drive() so file is guaranteed to exist."""
    if not MASTER_CONFIG_PATH.exists() and xl_or_df is None:
        raise RuntimeError(
            f"RE_MIS_Master.xlsx not found at {MASTER_CONFIG_PATH}. "
            "Set DRIVE_FILE_ID in Streamlit Cloud secrets."
        )
    if isinstance(xl_or_df, pd.DataFrame):
        df = xl_or_df
    elif isinstance(xl_or_df, pd.ExcelFile):
        df = xl_or_df.parse("model_config")
    else:
        df = pd.read_excel(MASTER_CONFIG_PATH, sheet_name="model_config")
    df = df[pd.to_numeric(df["model_code"], errors="coerce").notna()]
    labels, platform, plat_labels = {}, {}, {}
    in_survey_codes: set[int] = set()
    # Explicit segment-code lookup tables (table-driven, no block math)
    # Keys = raw survey code values; values = model_code
    acc_code_map:  dict[int, int] = {}   # acceptor_code  → model_code
    rej_code_map:  dict[int, int] = {}   # rejector_code  → model_code
    can_code_map:  dict[int, int] = {}   # cancelled_code → model_code
    dq2b_code_map: dict[int, int] = {}   # model_code → dq2b_code (survey DQ2 response code)
    has_explicit_codes = any(c in df.columns for c in ("acceptor_code", "rejector_code", "cancelled_code"))

    for _, row in df.iterrows():
        try:
            code      = int(float(row["model_code"]))
            name      = str(row["model_name"]).strip()
            plat      = str(row["platform_cc"]).strip()
            active    = str(row.get("active", "YES")).strip().upper()
            in_survey = str(row.get("in_survey", "YES")).strip().upper()
            if not name or name == "nan":
                continue
            # platform mapping includes ALL codes so deactivated models still
            # get correct re_platform for segment filtering
            platform[code] = plat
            raw_lbl = row.get("platform_label", plat)
            lbl = str(raw_lbl).strip() if raw_lbl and str(raw_lbl).strip() not in ("", "nan") else plat
            plat_labels[plat] = lbl
            if active == "YES":
                labels[code] = name
            # dq2b_code: which dq2a_N column + dq2b value maps to this RE model
            def _int_col(col, default):
                v = row.get(col, default)
                try:
                    return int(float(v)) if str(v).strip() not in ("", "nan") else default
                except (ValueError, TypeError):
                    return default
            dq2b_c = _int_col("dq2b_code", None)
            if dq2b_c is not None:
                dq2b_code_map[code] = dq2b_c
            if in_survey != "NO":
                in_survey_codes.add(code)
                acc_c = _int_col("acceptor_code",  code)
                rej_c = _int_col("rejector_code",  None)
                can_c = _int_col("cancelled_code", None)
                acc_code_map[acc_c] = code
                if rej_c is not None:
                    rej_code_map[rej_c] = code
                if can_c is not None:
                    can_code_map[can_c] = code
        except (ValueError, TypeError, KeyError):
            continue
    if not labels:
        raise RuntimeError(
            "model_config sheet found but no active models. "
            "Check model_code is numeric and active=YES for at least one row."
        )
    return labels, platform, plat_labels, in_survey_codes, acc_code_map, rej_code_map, can_code_map, has_explicit_codes, dq2b_code_map


# Populated after _sync_from_drive() in load_data() so cloud boot succeeds
RE_MODEL_LABELS: dict = {}
RE_MODEL_PLATFORM: dict = {}
RE_PLATFORM_LABELS: dict = {}  # {platform_cc: display_label} — dynamic from model_config
_ACCEPTOR_MAX_CODE: int = 0   # max code present in survey data (in_survey=YES); overwritten in load_data()
_MAX_MODEL_CODE: int = 0      # max of ALL configured codes including future models
# Explicit segment-code lookup tables — populated from model_config columns
# acceptor_code / rejector_code / cancelled_code (table-driven, no block math)
_ACC_CODE_MAP: dict[int, int] = {}   # acceptor_code  → model_code
_REJ_CODE_MAP: dict[int, int] = {}   # rejector_code  → model_code
_CAN_CODE_MAP: dict[int, int] = {}   # cancelled_code → model_code
_DQ2B_CODE_MAP: dict[int, int] = {}  # model_code → dq2b_code (DQ2 survey response code)
_HAS_EXPLICIT_CODES: bool = False     # True when model_config has explicit code columns

# Field registry — semantic_key → internal_name, loaded from column_mapping sheet.
# Python code uses self.F['education'] instead of 'dq3'. Adding/renaming columns
# in the Excel sheet auto-updates what the app reads — no code change needed.
_FIELD_REGISTRY = load_field_registry()

# Fallback registry for when display_groups sheet is absent (keeps app running)
_FIELD_FALLBACK = {
    "segment_gate":          "grida",
    "re_model_acc":          "acc",
    "joint_seg_model":       "seg",
    "re_model_fallback":     "aq3_po",
    "brand_model_purchased": "aq3",
    "fieldwork_month":       "Month",
    "fieldwork_year":        "Year",
    "submission_date":       "SubmissionDate",
    "buyer_type":            "dq1a",
    "replaced_vehicle":      "dq2b",
    "education":             "dq3",
    "occupation":            "dq4",
    "household_income":      "dq6",
    "age_band":              "age_grp",
    "age_raw":               "age_numeric",
    "post_cancel_action":    "aq1b",
    "competitor_cc":         "aq2a",
    "re_model_considered":   "aq5b",
    "brand_resilience":      "aq5c",
    "additional_vehicles":   "dq2a_*",
    "brands_considered":     "aq5a_*",
    "test_ride":             "aq6_*",
    "kbf_codes":             "kbf_codes",
    "rejection_codes":       "rejecter_codes",
    "cancellation_codes":    "cancelled_codes",
}
# Merge: Excel values override fallback
_FIELD_REGISTRY = {**_FIELD_FALLBACK, **_FIELD_REGISTRY}

# Standard 6-category occupation mapping — insertion order = display order
_DEFAULT_OCCUPATION_DISPLAY = {
    1.0: "Full-time Worker", 2.0: "Full-time Worker",        # salaried first
    5.0: "Businessman",      6.0: "Businessman", 7.0: "Businessman",
    8.0: "Self-employed",
    11.0: "Agriculture",
    12.0: "Students",
    3.0: "Others", 4.0: "Others", 9.0: "Others", 10.0: "Others",
    13.0: "Others", 14.0: "Others", 15.0: "Others",
}

# Display groups loaded from display_groups sheet in RE_MIS_Master.xlsx.
# Edit that sheet to rename categories, merge codes, or drop codes — no code change needed.
_DISPLAY_GROUPS = load_display_groups()
EDUCATION_DISPLAY_GROUPS  = _DISPLAY_GROUPS.get("dq3",     {}) or None
OCCUPATION_DISPLAY_GROUPS = _DISPLAY_GROUPS.get("dq4") or _DEFAULT_OCCUPATION_DISPLAY
_AGE_GRP_DISPLAY          = _DISPLAY_GROUPS.get("age_grp", {}) or None


class DataEngine:
    def __init__(self, masterfile_path=MASTERFILE_PATH, datamap_path=DATAMAP_PATH):
        self.masterfile_path = masterfile_path
        self.datamap_path = datamap_path
        self.df = None
        self.labels = {}
        self.value_maps = {}
        self.education_display_groups = EDUCATION_DISPLAY_GROUPS
        self.occupation_display_groups = OCCUPATION_DISPLAY_GROUPS
        self.age_grp_display = _AGE_GRP_DISPLAY
        # Field registry: semantic_key → actual column name in self.df
        # Populated at load_data() after column rename is applied.
        # Use self.col('education') anywhere you'd otherwise write 'dq3'.
        self.F: dict = dict(_FIELD_REGISTRY)
        # Instance-level copies, not just the mutated module globals below —
        # Streamlit's file-watcher can re-import utils.data_engine on a code
        # change while @st.cache_resource keeps the OLD engine instance
        # alive, leaving the module's MONTH_ORDER list reset to empty while
        # this engine's data is still fully loaded. Reading from the
        # instance (engine.month_order) instead of the module global avoids
        # that desync — see BUGS.md.
        self.month_order = []
        self.fy_quarter_order = []
        self.model_labels: dict = {}    # code → display name, instance-level copy
        self.model_platform: dict = {}  # code → platform cc, instance-level copy
        self.platform_labels: dict = {} # platform_cc → display label, instance-level copy

    def col(self, semantic_key: str) -> str:
        """Return actual df column name for a semantic key.
        Raises KeyError with helpful message if key not in registry."""
        if semantic_key not in self.F:
            raise KeyError(
                f"Unknown semantic field '{semantic_key}'. "
                f"Add it to column_mapping sheet (semantic_key column) in RE_MIS_Master.xlsx."
            )
        return self.F[semantic_key]

    # ------------------------------------------------------------------
    # Load + decode
    # ------------------------------------------------------------------
    def load_data(self):
        import datetime
        import pickle
        global _MAX_MODEL_CODE, _ACCEPTOR_MAX_CODE, _HAS_EXPLICIT_CODES

        cache_path = DATA_DIR / ".cache_data_engine.pkl"
        master_mtime = os.path.getmtime(self.masterfile_path) if os.path.exists(self.masterfile_path) else 0

        # Try ultra-fast binary cache first
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    cached_data = pickle.load(f)
                if cached_data.get("mtime") == master_mtime:
                    self.df = cached_data["df"]
                    self.labels = cached_data["labels"]
                    self.value_maps = cached_data["value_maps"]
                    self.education_display_groups = cached_data["education_display_groups"]
                    self.occupation_display_groups = cached_data["occupation_display_groups"]
                    self.age_grp_display = cached_data["age_grp_display"]
                    self.load_timestamp = cached_data["load_timestamp"]
                    self.month_order = cached_data.get("month_order", [])
                    self.fy_quarter_order = cached_data.get("fy_quarter_order", [])

                    # Update module globals and instance attrs
                    MONTH_ORDER[:] = self.month_order
                    FY_QUARTER_ORDER[:] = self.fy_quarter_order
                    RE_MODEL_LABELS.clear(); RE_MODEL_LABELS.update(cached_data["model_labels"])
                    RE_MODEL_PLATFORM.clear(); RE_MODEL_PLATFORM.update(cached_data["model_platform"])
                    self.model_labels.clear(); self.model_labels.update(cached_data["model_labels"])
                    self.model_platform.clear(); self.model_platform.update(cached_data["model_platform"])
                    self.platform_labels.clear(); self.platform_labels.update(cached_data.get("plat_labels", {}))
                    RE_PLATFORM_LABELS.clear(); RE_PLATFORM_LABELS.update(cached_data["plat_labels"])
                    _ACC_CODE_MAP.clear(); _ACC_CODE_MAP.update(cached_data["acc_map"])
                    _REJ_CODE_MAP.clear(); _REJ_CODE_MAP.update(cached_data["rej_map"])
                    _CAN_CODE_MAP.clear(); _CAN_CODE_MAP.update(cached_data["can_map"])
                    _ACCEPTOR_MAX_CODE = cached_data["acc_max_code"]
                    _MAX_MODEL_CODE = cached_data["max_model_code"]
                    _HAS_EXPLICIT_CODES = cached_data["has_explicit_codes"]
                    return
            except Exception:
                pass

        # If masterfile does not exist locally (e.g. fresh Streamlit Cloud container boot), sync from Drive
        if not Path(self.masterfile_path).exists():
            _sync_from_drive()

        # Load all sheets in a single pass using pd.ExcelFile
        try:
            xl = pd.ExcelFile(self.masterfile_path)
        except Exception as _xl_err:
            # File on disk is corrupt — delete and re-sync from Drive
            print(f"[data_engine] Masterfile corrupt ({_xl_err}), deleting and re-syncing from Drive")
            Path(self.masterfile_path).unlink(missing_ok=True)
            _sync_from_drive()
            try:
                xl = pd.ExcelFile(self.masterfile_path)
            except Exception as _xl_err2:
                raise RuntimeError(
                    f"RE_MIS_Master.xlsx still unreadable after re-sync: {_xl_err2}. "
                    "Check Drive folder has a valid .xlsx file."
                ) from _xl_err2

        # 1. model_config
        (_labels, _platform, _plat_labels,
         _in_survey, _acc_map, _rej_map, _can_map, _HAS_EXPLICIT_CODES, _dq2b_map) = load_model_config(xl)
        RE_MODEL_LABELS.clear();   RE_MODEL_LABELS.update(_labels)
        RE_MODEL_PLATFORM.clear(); RE_MODEL_PLATFORM.update(_platform)
        self.model_labels.clear();    self.model_labels.update(_labels)
        self.model_platform.clear();  self.model_platform.update(_platform)
        self.platform_labels.clear(); self.platform_labels.update(_plat_labels)
        RE_PLATFORM_LABELS.clear(); RE_PLATFORM_LABELS.update(_plat_labels)
        _ACC_CODE_MAP.clear(); _ACC_CODE_MAP.update(_acc_map)
        _REJ_CODE_MAP.clear(); _REJ_CODE_MAP.update(_rej_map)
        _CAN_CODE_MAP.clear(); _CAN_CODE_MAP.update(_can_map)
        _DQ2B_CODE_MAP.clear(); _DQ2B_CODE_MAP.update(_dq2b_map)
        _ACCEPTOR_MAX_CODE = max(_in_survey) if _in_survey else (max(RE_MODEL_PLATFORM.keys()) if RE_MODEL_PLATFORM else 14)
        _MAX_MODEL_CODE = max(RE_MODEL_PLATFORM.keys()) if RE_MODEL_PLATFORM else 14

        # 2. display_groups
        _dg = load_display_groups(xl)
        self.education_display_groups = _dg.get("dq3", {}) or None
        self.occupation_display_groups = _dg.get("dq4") or _DEFAULT_OCCUPATION_DISPLAY
        self.age_grp_display = _dg.get("age_grp", {}) or None
        self.load_timestamp = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")

        # 3. raw_data
        _probe = xl.parse(RAW_DATA_SHEET, nrows=0, header=0)
        _header_row = 1 if all(str(c).startswith("Unnamed") for c in _probe.columns[:5]) else 0
        self.df = xl.parse(RAW_DATA_SHEET, header=_header_row)

        col_map = load_column_mapping(xl)
        rename_map = {k: v for k, v in col_map.items() if k in self.df.columns and k != v and "*" not in k}
        if rename_map:
            self.df = self.df.rename(columns=rename_map)

        self._merge_reasons_codes()
        self._ingest_monthly_drops()

        # 4. datamap_labels & value_labels
        dm = xl.parse('datamap_labels')
        if 'variable' in dm.columns:
            self.labels = dict(zip(dm['variable'], dm['label']))
        else:
            dm2_leg = xl.parse('datamap_labels', header=None, skiprows=2, names=['Variable', 'Label', 'col3', 'col4'])
            self.labels = dict(zip(dm2_leg['Variable'], dm2_leg['Label']))

        dm2 = xl.parse('datamap_value_labels')
        self._parse_value_labels(dm2)

        if not self.value_maps.get('age_grp'):
            self.value_maps['age_grp'] = self.age_grp_display or {
                1.0: "18 to 25 Years", 2.0: "26 to 35 Years",
                3.0: "36 to 45 Years", 4.0: "46 or more",
            }

        # Auto-discover RE model codes from acc/aq3_po column using aq3 value map.
        # Any code present in the data but missing from model_config is auto-added —
        # so a new survey model appears immediately without a model_config sheet edit.
        _aq3_vm = self.value_maps.get("aq3", {})

        # Load CC-bucket map from netting_aq3a_aq5 to assign correct platform_cc
        # for auto-discovered models. Maps raw CC bucket string → platform_cc label.
        _cc_bucket_map: dict[int, str] = {}
        def _bucket_to_platform(bucket: str) -> str:
            """'501-650CC' → '650CC', '250-350CC' → '350CC', '351-500CC' → '450CC', etc."""
            b = str(bucket).strip()
            if "650" in b: return "650CC"
            if "450" in b or "440" in b or "351" in b or "400" in b or "500" in b: return "450CC"
            if "350" in b or "250" in b: return "350CC"
            return "Unknown"
        try:
            _net = xl.parse("netting_aq3a_aq5", header=None)
            _net_rows = _net.iloc[3:127].reset_index(drop=True)
            for _i in range(len(_net_rows)):
                _bucket = str(_net_rows.iloc[_i, 5]).strip()
                if _bucket and _bucket != "nan":
                    _cc_bucket_map[_i + 1] = _bucket_to_platform(_bucket)
        except Exception:
            pass

        # Build set of raw acceptor/rejector codes already claimed by model_config
        _known_raw_codes: set[int] = set(_ACC_CODE_MAP.keys()) | set(_REJ_CODE_MAP.keys()) | set(_CAN_CODE_MAP.keys())

        for _acc_col in ("acc", "aq3_po", self.F.get("re_model_acc", "acc")):
            if _acc_col in self.df.columns:
                for _raw in self.df[_acc_col].dropna().unique():
                    try:
                        _c = int(float(_raw))
                    except (ValueError, TypeError):
                        continue
                    if _c in RE_MODEL_LABELS:
                        continue  # already configured as model_code
                    if _c in _known_raw_codes:
                        continue  # raw code already claimed by a model_config entry (e.g. acceptor_code=125 → model 15)
                    _name = _aq3_vm.get(float(_c))
                    if not _name:
                        continue
                    RE_MODEL_LABELS[_c] = _name
                    self.model_labels[_c] = _name
                    if _c not in RE_MODEL_PLATFORM:
                        _plat = _cc_bucket_map.get(_c, "Unknown")
                        RE_MODEL_PLATFORM[_c] = _plat
                        self.model_platform[_c] = _plat
                    _ACC_CODE_MAP.setdefault(_c, _c)
                    _REJ_CODE_MAP.setdefault(_c, _c)
                    _CAN_CODE_MAP.setdefault(_c, _c)
                break  # found the column, stop searching

        self._derive_segment()
        self._derive_month()

        # Drop incomplete/blank submissions (no grida, no SubmissionDate —
        # genuinely empty quota rows, not real respondents). Unrelated to
        # the month-window question below; this is just data hygiene.
        self.df = self.df[self.df['month_label'].notna()].copy()

        # Dynamic month list
        present_months = self.df['month_label'].dropna().unique().tolist()
        present_months.sort(key=lambda m: pd.to_datetime(m.replace("'", " "), format="%B %Y"))
        fy_quarters = sorted(set(month_label_to_fy_quarter(m) for m in present_months),
                              key=lambda q: present_months.index(
                                  next(m for m in present_months if month_label_to_fy_quarter(m) == q)))
        self.month_order = present_months
        self.fy_quarter_order = fy_quarters
        MONTH_ORDER[:] = present_months          # kept for backward compat / direct module use
        FY_QUARTER_ORDER[:] = fy_quarters

        # Save binary cache for subsequent instant loads (< 0.05s)
        try:
            cache_obj = {
                "mtime": master_mtime,
                "df": self.df,
                "labels": self.labels,
                "value_maps": self.value_maps,
                "education_display_groups": self.education_display_groups,
                "occupation_display_groups": self.occupation_display_groups,
                "age_grp_display": self.age_grp_display,
                "load_timestamp": self.load_timestamp,
                "month_order": self.month_order,
                "fy_quarter_order": self.fy_quarter_order,
                "model_labels": dict(RE_MODEL_LABELS),
                "model_platform": dict(RE_MODEL_PLATFORM),
                "plat_labels": dict(RE_PLATFORM_LABELS),
                "acc_map": dict(_ACC_CODE_MAP),
                "rej_map": dict(_REJ_CODE_MAP),
                "can_map": dict(_CAN_CODE_MAP),
                "acc_max_code": _ACCEPTOR_MAX_CODE,
                "max_model_code": _MAX_MODEL_CODE,
                "has_explicit_codes": _HAS_EXPLICIT_CODES,
            }
            with open(cache_path, "wb") as f:
                pickle.dump(cache_obj, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass

        return self.df

    def _ingest_monthly_drops(self):
        """Merges any additional monthly extract files dropped into
        MONTHLY_DROPS_DIR (same schema as the Masterfile: header on row 1)
        into self.df, deduplicated on SubmissionDate+deviceid+username so
        re-running on the same drop twice doesn't double-count anyone.
        This is the interim 'no hardcoded single file' mechanism — see the
        MONTHLY_DROPS_DIR comment for the real SharePoint-sync path."""
        import glob
        if not os.path.isdir(MONTHLY_DROPS_DIR):
            return
        for path in sorted(glob.glob(os.path.join(MONTHLY_DROPS_DIR, "*.xlsx"))):
            try:
                extra = pd.read_excel(path, header=1)
            except Exception:
                continue
            self.df = pd.concat([self.df, extra], ignore_index=True)
        dedup_cols = [c for c in ('SubmissionDate', 'deviceid', 'username') if c in self.df.columns]
        if dedup_cols:
            self.df = self.df.drop_duplicates(subset=dedup_cols, keep='last').reset_index(drop=True)

    # Names of the 3 respondent-level netting-code columns in data_updated
    # -- same names as the 3 reference netting sheets, but holding each
    # respondent's OWN assigned codes (concatenated 3-digit chunks, e.g.
    # "001020117" = codes 001, 020, 117), not the taxonomy itself. See
    # DataEngine.reasons_table() and utils/netting_taxonomy.load_code_map().
    REASONS_CODE_COLUMNS = {
        "kbf_codes": "MQ2a+MQ2b_KBF",
        "rejecter_codes": "MQ3a+MQ3b_Rejecter",
        "cancelled_codes": "MQ3a+MQ3b_Booked and cancelled",
    }

    def _merge_reasons_codes(self):
        """Pulls the 3 respondent-level netting-code columns onto self.df.
        Must be read with dtype=str: Excel/pandas silently mangles the long
        concatenated digit strings into float/scientific-notation otherwise
        (e.g. "022031038042079166172173175176198210211216217" -> a garbage
        float), losing the exact codes. Joined on SubmissionDate rather than
        concatenated positionally -- validated (2026-07-27) to produce
        exactly len(self.df) rows with no duplication, even though
        SubmissionDate isn't globally unique in the raw file (the
        duplicates only exist among rows load_data() drops as incomplete)."""
        src_cols = list(self.REASONS_CODE_COLUMNS.values())
        try:
            _probe2 = pd.read_excel(self.masterfile_path, sheet_name=RAW_DATA_SHEET, nrows=0, header=0)
            _hrow2 = 1 if all(str(c).startswith("Unnamed") for c in _probe2.columns[:5]) else 0
            raw = pd.read_excel(self.masterfile_path, sheet_name=RAW_DATA_SHEET, header=_hrow2,
                                 usecols=['SubmissionDate'] + src_cols,
                                 dtype={c: str for c in src_cols})
        except Exception:
            # Sheet name drift across monthly Masterfile drops -- degrade to
            # "no Reasons data" rather than breaking the whole app load.
            for dest_col in self.REASONS_CODE_COLUMNS:
                self.df[dest_col] = ""
            return
        raw = raw.rename(columns={v: k for k, v in self.REASONS_CODE_COLUMNS.items()})
        # Drop any existing dest_col columns (load_data column_mapping may have
        # already renamed them) to avoid _x/_y suffix collision on merge.
        drop_existing = [c for c in self.REASONS_CODE_COLUMNS if c in self.df.columns]
        if drop_existing:
            self.df = self.df.drop(columns=drop_existing)
        self.df = self.df.merge(raw, on='SubmissionDate', how='left')
        for dest_col in self.REASONS_CODE_COLUMNS:
            self.df[dest_col] = self.df[dest_col].fillna("")

    def _parse_value_labels(self, dm2):
        # Support both old format (Unnamed: 0/1/2) and new cleaned format (variable/code/label)
        cols = list(dm2.columns)
        if 'variable' in cols:
            col_var, col_code, col_label = 'variable', 'code', 'label'
        else:
            col_var, col_code, col_label = cols[0], cols[1], cols[2]

        # New flat format: every row has variable filled (no merged cells)
        if 'variable' in cols:
            for _, row in dm2.iterrows():
                var_name = row[col_var]
                if pd.isna(var_name) or str(var_name).strip() in ('', 'nan'):
                    continue
                var_name = str(var_name).strip()
                if var_name not in self.value_maps:
                    self.value_maps[var_name] = {}
                val, lbl = row[col_code], row[col_label]
                if pd.notna(val):
                    try:
                        self.value_maps[var_name][float(val)] = str(lbl) if pd.notna(lbl) else ''
                    except (ValueError, TypeError):
                        self.value_maps[var_name][val] = str(lbl) if pd.notna(lbl) else ''
        else:
            # Legacy merged-cell format
            current_var = None
            for _, row in dm2.iterrows():
                var_name = row[col_var]
                if pd.notna(var_name) and var_name not in ('Variable Values', 'Value'):
                    current_var = str(var_name).strip()
                    self.value_maps[current_var] = {}
                val, lbl = row[col_code], row[col_label]
                if pd.notna(val) and pd.notna(lbl) and current_var:
                    try:
                        self.value_maps[current_var][float(val)] = str(lbl)
                    except (ValueError, TypeError):
                        self.value_maps[current_var][val] = str(lbl)

    def _manufacturer_for_code(self, code):
        """Manufacturer name for any owned_brand_code (1-124 scheme). Shared
        by _derive_segment (global fallback columns) and filter_df (per-
        segment rescoping) so there's one definition, not two copies that
        could drift."""
        if pd.isna(code):
            return None
        if 1 <= code <= 14:
            return "Royal Enfield"
        # RE models with model_code > 14 (e.g. Flying Flea = 16) must also
        # resolve to "Royal Enfield", not a competitor brand from the acc codebook.
        if int(code) in RE_MODEL_LABELS:
            return "Royal Enfield"
        if code == 124:
            return "Other"
        acc_map = self.value_maps.get('acc', {})
        label = acc_map.get(code, "")
        name = label.split(" - ")[0].strip() if " - " in label else label
        # Source-data typo (acc_map code 84): "RIUMPH - T SCRAMBLER - 400 XC"
        # is missing its leading 'T' — every other TRIUMPH model (85-105) is
        # spelled correctly. Without this fix it split into its own bogus
        # one-model "RIUMPH" brand rollup instead of joining TRIUMPH.
        return {"RIUMPH": "TRIUMPH"}.get(name, name)

    def _derive_segment(self):
        """
        Global fallback segment/model columns on self.df — used for Overview
        (no segment filter) and for "rest of sample" significance baselines.
        Mutually exclusive by construction: Acceptor = `aq3_po` between 1-14
        (priority), Rejector/Cancelled = `grida` (2/3) MINUS whichever of
        those rows already qualify as Acceptor — so these three sum cleanly
        to 4,010 for Overview-level aggregation.

        IMPORTANT (2026-06-19, confirmed by re-scraping the live site): the
        live dashboard's Acceptor/Rejector/Cancelled TABS are NOT mutually
        exclusive — each tab applies its own independent rule and they
        overlap (Acceptor tab=1997 via aq3_po; Rejector tab=1789 via grida==2
        FULL, unfiltered; Cancelled tab=1527 via grida==3 FULL). filter_df()
        below re-scopes df independently per explicit segment request to
        match that — this method's mutually-exclusive columns are ONLY the
        Overview/baseline fallback, not what a segment page's tab shows.
        Per explicit instruction, that overlap is now accepted and those
        rows move into Acceptor; Rejector/Cancelled counts shrink by the
        same amount they used to be 1,789/1,527, now ~889/~1,124.

        `re_model_code` (1-14, which specific RE model) comes from `acc` for
        originally-Acceptor rows, `aq3_po` for the newly-reclassified ones
        (their `acc` is null since they were never asked that question),
        `rej`/`can` for Rejector/Cancelled as before.
        """
        df = self.df.copy()
        _aq3po = self.F.get('re_model_fallback', 'aq3_po')
        _grida = self.F.get('segment_gate', 'grida')
        _acc   = self.F.get('re_model_acc', 'acc')
        _seg   = self.F.get('joint_seg_model', 'seg')
        _aq3   = self.F.get('brand_model_purchased', 'aq3')
        _n = _ACCEPTOR_MAX_CODE or 14  # seg block size = codes present in survey
        if _HAS_EXPLICIT_CODES and _ACC_CODE_MAP:
            # Table-driven: use explicit acceptor_code/rejector_code/cancelled_code columns
            acceptor_mask = df[_aq3po].isin(_ACC_CODE_MAP.keys())
        else:
            acceptor_mask = df[_aq3po].between(1, _n)
        df['segment'] = None
        df.loc[acceptor_mask, 'segment'] = 'Acceptor'
        df.loc[(df[_grida] == 2) & ~acceptor_mask, 'segment'] = 'Rejector'
        df.loc[(df[_grida] == 3) & ~acceptor_mask, 'segment'] = 'Cancelled'

        acc_or_aq3po = df[_acc].fillna(df[_aq3po])
        if _HAS_EXPLICIT_CODES and _REJ_CODE_MAP and _CAN_CODE_MAP:
            # Map raw seg value → model_code via explicit lookup tables
            rej_model = df[_seg].map(_REJ_CODE_MAP)
            can_model = df[_seg].map(_CAN_CODE_MAP)
            df['re_model_code'] = np.select(
                [df['segment'] == 'Acceptor', df['segment'] == 'Rejector', df['segment'] == 'Cancelled'],
                [acc_or_aq3po.map(_ACC_CODE_MAP).fillna(acc_or_aq3po), rej_model, can_model],
                default=np.nan,
            )
        else:
            df['re_model_code'] = np.select(
                [df['segment'] == 'Acceptor', df['segment'] == 'Rejector', df['segment'] == 'Cancelled'],
                [acc_or_aq3po, df[_seg] - _n, df[_seg] - 2*_n],
                default=np.nan,
            )
        df['re_model_name'] = df['re_model_code'].map(RE_MODEL_LABELS)
        df['re_platform'] = df['re_model_code'].map(RE_MODEL_PLATFORM)

        df['owned_brand_code'] = acc_or_aq3po.where(df['segment'] == 'Acceptor', df[_aq3])
        acc_map = self.value_maps.get(_acc, {})
        df['owned_brand_name'] = df['owned_brand_code'].map(acc_map)
        df['owned_manufacturer'] = df['owned_brand_code'].apply(self._manufacturer_for_code)
        self.df = df.copy()

    def _derive_month(self):
        # The raw lowercase `month`/`year` text columns are dirty (typos,
        # garbage years) -- unusable. SubmissionDate looked like a clean
        # fallback but drifts near month-end (a respondent surveyed in the
        # last days of March can submit in April), which silently moved a
        # handful of rows into the wrong month bucket -- e.g. our old
        # SubmissionDate-derived counts were Mar=316/Apr=369 vs the live
        # site's Mar=324/Apr=361 (2026-07-29 finding). The capitalized
        # `Month`/`Year` numeric columns are the actual clean fielding-period
        # tags: grouping by them reproduces the live site's base counts for
        # every one of the 10 months exactly (366/678/413/468/238/375/396/
        # 324/361/391), so they're the source of truth, not SubmissionDate.
        _month = self.F.get('fieldwork_month', 'Month')
        _year  = self.F.get('fieldwork_year', 'Year')
        month_num = pd.to_numeric(self.df[_month], errors='coerce')
        year_num = pd.to_numeric(self.df[_year], errors='coerce')
        dt = pd.to_datetime(
            dict(year=year_num, month=month_num, day=1), errors='coerce'
        )
        self.df['month_label'] = dt.dt.strftime("%B'%Y")
        self.df = self.df.copy()

    def quarter_combined_groups(self, extra_groups=None, include_quarters=False):
        """{display_label: [month_labels]} for quarter-combined columns.
        include_quarters defaults to False so tables remain clean with monthly columns
        and do not append trailing JAS'25 / OND'25 / JFM'26 columns across sections.
        """
        groups = {}
        out = {}
        if include_quarters:
            for m in self.month_order:
                q = month_label_to_fy_quarter(m)
                groups.setdefault(q, []).append(m)
            quarters_to_show = self.fy_quarter_order[:-1] if len(self.fy_quarter_order) > 1 else []
            for q in quarters_to_show:
                months = groups.get(q)
                if not months:
                    continue
                out[q] = months  # q already in initials format e.g. "JAS'25"
        if extra_groups:
            out.update(extra_groups)
        return out

    @staticmethod
    def _col_index(df, col, quarter_groups):
        """Row index for any table column — a real month, 'All', or one of
        the quarter-combined labels (union of that quarter's month rows)."""
        if col == "All":
            return df.index
        if col in quarter_groups:
            return df[df['month_label'].isin(quarter_groups[col])].index
        return df[df['month_label'] == col].index

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------
    def _segment_slice(self, segment):
        """One segment's full (unfiltered) tab rows with segment/re_model_code/
        owned_brand_code/re_platform/owned_manufacturer set — see filter_df
        docstring for why each segment is scoped independently."""
        _aq3po = self.F.get('re_model_fallback', 'aq3_po')
        _grida = self.F.get('segment_gate', 'grida')
        _acc   = self.F.get('re_model_acc', 'acc')
        _seg   = self.F.get('joint_seg_model', 'seg')
        _aq3   = self.F.get('brand_model_purchased', 'aq3')
        _n = _ACCEPTOR_MAX_CODE or 14
        if segment == "Acceptor":
            if _HAS_EXPLICIT_CODES and _ACC_CODE_MAP:
                df = self.df[self.df[_aq3po].isin(_ACC_CODE_MAP.keys())].copy()
            else:
                df = self.df[self.df[_aq3po].between(1, _n)].copy()
            df['segment'] = 'Acceptor'
            _raw_acc = df[_acc].fillna(df[_aq3po])
            if _HAS_EXPLICIT_CODES and _ACC_CODE_MAP:
                df['re_model_code'] = _raw_acc.map(_ACC_CODE_MAP).fillna(_raw_acc)
                # Normalize owned_brand_code to model_code so RE detection in
                # brand_owned_table works dynamically (e.g. Bullet 650 raw=125 → 15)
                df['owned_brand_code'] = df['re_model_code']
            else:
                df['re_model_code'] = _raw_acc
                df['owned_brand_code'] = _raw_acc
        elif segment == "Rejector":
            df = self.df[self.df[_grida] == 2].copy()
            df['segment'] = 'Rejector'
            if _HAS_EXPLICIT_CODES and _REJ_CODE_MAP:
                df['re_model_code'] = df[_seg].map(_REJ_CODE_MAP)
            else:
                df['re_model_code'] = df[_seg] - _n
            df['owned_brand_code'] = df[_aq3]
        elif segment == "Cancelled":
            df = self.df[self.df[_grida] == 3].copy()
            df['segment'] = 'Cancelled'
            if _HAS_EXPLICIT_CODES and _CAN_CODE_MAP:
                df['re_model_code'] = df[_seg].map(_CAN_CODE_MAP)
            else:
                df['re_model_code'] = df[_seg] - 2*_n
            df['owned_brand_code'] = df[_aq3]
        else:
            raise ValueError(segment)
        df['re_platform'] = df['re_model_code'].map(RE_MODEL_PLATFORM)
        df['owned_manufacturer'] = df['owned_brand_code'].apply(self._manufacturer_for_code)
        return df

    def filter_df(self, segment=None, platform=None, model_code=None, owned_brand_code=None):
        """Segment pages re-scope `df` independently per the live site's own
        (non-exclusive) tab rules — confirmed 2026-06-19 by re-scraping the
        live dashboard fresh: Acceptor tab=1997 (aq3_po 1-14), Rejector
        tab=1789 (grida==2, FULL — no Acceptor carve-out), Cancelled
        tab=1527 (grida==3, FULL). A respondent can legitimately appear on
        both the Acceptor tab AND the Rejector/Cancelled tab — that's the
        live site's actual behavior, not a bug to "fix" into exclusivity.
        Each branch recomputes re_model_code/owned_brand_code/segment for
        the returned slice, since the same respondent's "relevant model"
        differs by which tab is asking (e.g. one of the ~1,303 overlap rows
        shows their REJECTED model on the Rejector tab, but their BOUGHT
        model on the Acceptor tab).

        'All' (no segment) with NO platform/model/owned_brand filter keeps
        the global mutually-exclusive columns from _derive_segment (matches
        live Overview base 4010 exactly — confirmed unfiltered).

        'All' WITH a platform/model/owned_brand filter instead unions the
        three segments' independently-filtered rows (live Overview's base
        is the union of what the 3 tabs each show for that filter, NOT the
        mutually-exclusive count — confirmed 2026-06-25 by re-scraping
        Bullet 350: live Overview=562, union of filtered tabs=565 (within
        residual noise), old mutually-exclusive count=480, way off)."""
        def _apply_filters(d):
            if platform and platform != "All":
                d = d[d['re_platform'] == platform]
            if model_code is not None:
                d = d[pd.to_numeric(d['re_model_code'], errors='coerce') == float(model_code)]
            if owned_brand_code is not None:
                d = d[pd.to_numeric(d['owned_brand_code'], errors='coerce') == float(owned_brand_code)]
            return d

        if segment in ("Acceptor", "Rejector", "Cancelled"):
            return _apply_filters(self._segment_slice(segment))
        if (platform and platform != "All") or model_code or owned_brand_code:
            # Filter each segment's tab independently first, THEN union the
            # matching rows — filtering the deduped union instead would lose
            # a respondent's match in segment B if segment A's row (picked
            # by the dedup) doesn't also match the filter.
            filtered = [
                _apply_filters(self._segment_slice(s))
                for s in ("Acceptor", "Rejector", "Cancelled")
            ]
            df = pd.concat(filtered)
            return df[~df.index.duplicated(keep='first')]
        return self.df

    def manufacturers(self):
        """Sorted list of every manufacturer present in owned_brand_name
        (Royal Enfield first), for the Brand filter dropdown."""
        names = sorted(self.df['owned_manufacturer'].dropna().unique().tolist())
        if "Royal Enfield" in names:
            names.remove("Royal Enfield")
            names = ["Royal Enfield"] + names
        return names

    def models_for_manufacturer(self, manufacturer):
        """{model_name: code} for every model under a given manufacturer,
        sourced from the same acc/rej/can/aq3 1-124 scheme — covers all
        124 brand/model codes, not just RE's 14."""
        sub = self.df[self.df['owned_manufacturer'] == manufacturer]
        pairs = sub[['owned_brand_code', 'owned_brand_name']].dropna().drop_duplicates()
        return dict(sorted(zip(pairs['owned_brand_name'], pairs['owned_brand_code']), key=lambda x: x[0]))

    # ------------------------------------------------------------------
    # Generic single-code distribution table (Age / Education / Occupation /
    # Household Income share this shape: one categorical column, decode via
    # datamap value_maps, base row + category rows, columns = All + months).
    # ------------------------------------------------------------------
    def distribution_table(self, df, code_col, base_label, display_groups=None, numeric=False, extra_groups=None):
        """
        display_groups: optional {code: display_label or None}. Codes mapping
        to the same label are summed together; None drops that code from the
        chart (used to match the live dashboard's collapsed category display).
        numeric: return raw floats instead of "NN%" strings (for chart use).
        extra_groups: see quarter_combined_groups() docstring.
        """
        value_map = self.value_maps.get(code_col, {})
        base_n = df[code_col].notna().sum()  # denominator for % calculations
        display_base_n = len(df)             # display base = total segment rows
        quarter_groups = self.quarter_combined_groups(extra_groups)
        extra_cols = list(quarter_groups.keys())

        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": display_base_n}]
        for col in self.month_order + extra_cols:
            idx = self._col_index(df, col, quarter_groups)
            rows[0][col] = len(idx)

        if display_groups:
            labels_in_order = []
            for code in display_groups.keys():  # preserve insertion/sheet-row order
                lbl = display_groups.get(code)
                if lbl and lbl not in labels_in_order:
                    labels_in_order.append(lbl)
            code_groups = {lbl: [c for c, l in display_groups.items() if l == lbl] for lbl in labels_in_order}
        else:
            code_groups = {label: [code] for code, label in sorted(value_map.items())}

        for label, codes in code_groups.items():
            mask_all = df[code_col].isin(codes)
            pct_all = mask_all.sum() / base_n * 100 if base_n else 0
            row = {"Unnamed: 0": label, "All": pct_all if numeric else f"{pct_all:.0f}%"}
            for col in self.month_order + extra_cols:
                idx = self._col_index(df, col, quarter_groups)
                col_base = len(idx)
                pct = (df.loc[idx, code_col].isin(codes)).sum() / col_base * 100 if col_base else 0
                row[col] = pct if numeric else f"{pct:.0f}%"
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def cap_rows(table_df, max_rows=8, exclude_labels=None):
        """Keeps the Base row + the top `max_rows` categories by 'All' value,
        rolling everything else into a single 'Other' row (summed, since
        these are mutually-exclusive single-select buckets in every table
        this is applied to). Per user feedback: brand-wise tables with 14+
        rows were 'too long and overcomplicated' as charts.

        exclude_labels: rows to drop entirely before ranking — for tables
        that mix a rollup/type row (e.g. 'RE' union, 'Additional Vehicle')
        with the individual brand/model breakdown underneath it. Treemap-
        ping a rollup next to its own children double-counts and visually
        drowns out every other category (the rollup is always #1 by
        construction)."""
        if exclude_labels:
            table_df = pd.concat([table_df.iloc[[0]], table_df.iloc[1:][~table_df.iloc[1:]['Unnamed: 0'].isin(exclude_labels)]], ignore_index=True)
        base_row = table_df.iloc[[0]]
        rest = table_df.iloc[1:].copy()
        rest['All'] = rest['All'].astype(float)
        rest = rest.sort_values('All', ascending=False)
        if len(rest) <= max_rows:
            return table_df
        top = rest.iloc[:max_rows]
        tail = rest.iloc[max_rows:]
        other_row = {"Unnamed: 0": "Other"}
        for col in table_df.columns:
            if col == "Unnamed: 0":
                continue
            other_row[col] = tail[col].astype(float).sum()
        return pd.concat([base_row, top, pd.DataFrame([other_row])], ignore_index=True)

    @staticmethod
    def sort_brand_table(table_df, rollup_labels):
        """Per user request: brand-wise tables (Additional+Replaced/Brand
        Owned/Brand Considered) should show in descending order, with the
        catch-all 'Other' manufacturer block pinned to the very end
        regardless of its value — matching the live site's own ordering.
        Groups each rollup row with its member rows that follow (the table
        builders already emit rollup-then-members blocks in that shape),
        sorts the BLOCKS by the rollup's own 'All' value (descending,
        'Other' always last), and ALSO sorts each block's member rows by
        their own 'All' value descending — per follow-up request ('the
        models should also be in descending order of value to see within
        the brands which are leading and which are not')."""
        base_row = table_df.iloc[[0]]
        rest = table_df.iloc[1:]
        blocks = []
        current_label, current_rows = None, []
        for _, row in rest.iterrows():
            label = row['Unnamed: 0']
            if label in rollup_labels:
                if current_rows:
                    blocks.append((current_label, current_rows))
                current_label, current_rows = label, [row]
            else:
                current_rows.append(row)
        if current_rows:
            blocks.append((current_label, current_rows))
        other_blocks = [b for b in blocks if b[0] == "Other"]
        normal_blocks = [b for b in blocks if b[0] != "Other"]
        normal_blocks.sort(key=lambda b: float(b[1][0]['All']), reverse=True)
        ordered_rows = [base_row]
        for _, block_rows in normal_blocks + other_blocks:
            rollup_row, member_rows = block_rows[0], block_rows[1:]
            member_rows.sort(key=lambda r: float(r['All']), reverse=True)
            ordered_rows.append(pd.DataFrame([rollup_row] + member_rows))
        return pd.concat(ordered_rows, ignore_index=True)

    @staticmethod
    def rollup_only_table(table_df, rollup_labels):
        """Base row + only the brand-ROLLUP rows (RE/HERO/BAJAJ/...), sorted
        descending with 'Other' pinned last — feeds the brand-level overlay
        bar chart sitting above the full member-level table, per user
        request to show 'the overall comparison in bar chart' separately
        from the detailed table underneath it."""
        base_row = table_df.iloc[[0]]
        rollups = table_df[table_df['Unnamed: 0'].isin(rollup_labels)].copy()
        rollups['All'] = rollups['All'].astype(float)
        other = rollups[rollups['Unnamed: 0'] == "Other"]
        normal = rollups[rollups['Unnamed: 0'] != "Other"].sort_values('All', ascending=False)
        return pd.concat([base_row, normal, other], ignore_index=True)

    def age_table(self, df, base_label="All", numeric=False, extra_groups=None):
        return self.distribution_table(df, self.F.get('age_band', 'age_grp'), base_label, numeric=numeric, extra_groups=extra_groups)

    def education_table(self, df, base_label="All", numeric=False, extra_groups=None):
        return self.distribution_table(df, self.F.get('education', 'dq3'), base_label, display_groups=self.education_display_groups, numeric=numeric, extra_groups=extra_groups)

    @staticmethod
    def sort_by_value(table_df):
        """Sorts category rows by 'All' descending, keeping the Base row
        first — for NOMINAL categories (no inherent order, e.g. Occupation
        types, Buyer types) so the biggest factor is immediately visible at
        a glance, unlike ORDINAL scales (Age, Education, Income) where the
        natural low-to-high order matters more than the ranking."""
        base_row = table_df.iloc[[0]]
        rest = table_df.iloc[1:].copy()
        rest['_sort'] = rest['All'].astype(float)
        rest = rest.sort_values('_sort', ascending=False).drop(columns=['_sort'])
        return pd.concat([base_row, rest], ignore_index=True)

    def occupation_table(self, df, base_label="All", numeric=False, extra_groups=None):
        return self.distribution_table(df, self.F.get('occupation', 'dq4'), base_label, display_groups=self.occupation_display_groups, numeric=numeric, extra_groups=extra_groups)

    def household_income_table(self, df, base_label="All", numeric=False, extra_groups=None):
        return self.distribution_table(df, self.F.get('household_income', 'dq6'), base_label, numeric=numeric, extra_groups=extra_groups)

    # ------------------------------------------------------------------
    # Type of Buyer — dq1a (prior 2W usage) x Additional/Replaced split.
    # dq1a==3/4 match the scrape almost exactly as standalone buckets.
    # Additional/Replaced FIXED (2026-08-06) per questionnaire skip logic:
    # dq1b is only a routing flag (asked once, gates DQ2a vs DQ2b) and goes
    # fully blank Nov'25 onward (skip-logic gap) — do NOT use it to compute
    # the split. Per questionnaire, DQ2a (multi-select, "other 2W owned") is
    # asked only if coded 1 in dq1a AND dq1b, DQ2b (single-select, "2W
    # replaced") only if coded 2 in both — same gating columns already used
    # by the Additional+Replaced brand-wise section below. So a respondent's
    # actual answer lives in whichever of dq2a_*/dq2b they answered; use
    # that directly instead of re-deriving from dq1b. This also keeps both
    # sections (Type of Buyer here, and the brand-wise table) internally
    # consistent on the same source columns.
    # ------------------------------------------------------------------
    def type_of_buyer_table(self, df, base_label="All", numeric=False, extra_groups=None):
        _dq1a = self.F.get('buyer_type', 'dq1a')
        base_n = df[_dq1a].notna().sum()
        quarter_groups = self.quarter_combined_groups(extra_groups)
        extra_cols = list(quarter_groups.keys())
        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in self.month_order + extra_cols:
            idx = self._col_index(df, col, quarter_groups)
            rows[0][col] = df.loc[idx, _dq1a].notna().sum()

        def pct_row(label, mask_fn):
            row = {"Unnamed: 0": label}
            for col in ["All"] + self.month_order + extra_cols:
                sub = df.loc[self._col_index(df, col, quarter_groups)]
                sub_base = len(sub)
                val = mask_fn(sub) / sub_base * 100 if sub_base else 0
                row[col] = val if numeric else f"{val:.0f}%"
            return row

        rows.append(pct_row("This is my Additional 2W", lambda d: (d[_dq1a] == 1).sum()))
        rows.append(pct_row("First Time Buyer of 2W (No one owns a 2W)", lambda d: (d[_dq1a] == 4).sum()))
        rows.append(pct_row("First Time Buyer of 2W (Family owns a 2W and not a primary user)", lambda d: (d[_dq1a] == 3).sum()))
        rows.append(pct_row("This is my Replaced 2W", lambda d: (d[_dq1a] == 2).sum()))
        tbl = pd.DataFrame(rows)
        return self.sort_by_value(tbl) if numeric else tbl

    # ------------------------------------------------------------------
    # Brand Owned — FIXED, shippable. Source: `aq3` ("Make & model
    # purchased"), NOT dq2a (that was the wrong column entirely — dq2a is
    # "other 2W also currently owned", a different question). Per
    # data/Enroute_AP_V2_netting.xlsx Sheet1 row "AQ3": base = "All Owners" =
    # "All coded 1 or 2 in Grid A or coded 3 in Grid A and coded 1 in AQ1b"
    # i.e. Rejector ∪ (Cancelled AND confirmed-purchase via aq1b==1).
    # aq3 uses the same 1-124 acc/rej/can code scheme (confirmed: aq3 has a
    # full Sheet2 value-map block). Validated against scrape: Bullet 350
    # 9.6% vs 10%, Classic 350 14.5% vs 13%, Hunter 350 8.2% vs 9%, Meteor
    # 350 7.7% vs 8% — all within ~1.5pts. Base still slightly under
    # (computed 2244 vs scraped 2547, same general ~10-12% gap pattern seen
    # elsewhere in this file) but the per-row shape is now right, unlike the
    # old dq2a-based version. See docs/DATA_FIELD_MAPPING.md Addendum 7.
    # MIS_Dashboard_Requirements.docx scopes this table to the Rejectors
    # page specifically ("the brand/CC ultimately purchased [instead of
    # RE]") — callers should filter to segment="Rejector" before calling
    # this, though the "All Owners" base technically also includes
    # purchase-confirmed Cancelled respondents per the spec.
    # ------------------------------------------------------------------
    def brand_owned_table(self, df, by="brand", base_label="All", numeric=False, extra_groups=None):
        """FIX (2026-06-19): base/model-column must be segment-aware. The
        live site's Acceptor tab DOES show a 'Brand Owned' table too (base
        ~segment size, RE=100% trivially, broken into which RE model) —
        confirmed via docs/investigation/full_scraped_data.json's
        'Brand Owned - Brand Wise_1' (Acceptor tab: base 1737, RE 100%).
        Previously this always used the Rejector∪Cancelled-confirmed mask
        regardless of which segment's df was passed in, so an Acceptor-only
        df always produced base_n=0 (every row's `segment` is 'Acceptor',
        which never matches that mask) — the table looked broken/absent on
        the Acceptors page when it should show their own purchase, just
        with trivial 100% RE content. Uses the unified `owned_brand_code`
        field (acc for Acceptor rows, aq3 otherwise) so one model-column
        works for both cases instead of hardcoding aq3.

        SIMPLIFIED BACK (2026-06-19): now that filter_df() itself re-scopes
        the Rejector/Cancelled tabs to their live-confirmed FULL grida
        populations (1789/1527, overlapping with Acceptor's aq3_po-based
        1997 by design — see filter_df's docstring), this no longer needs
        to reconstruct anything from self.df. Using `grida`/`aq1b` directly
        (not the `segment` label) means this works correctly whether df is
        a single segment's tab (pure grida==2 or grida==3), Overview's
        unscoped df (grida spans all three, union naturally gives the
        original 'All Owners'=2244), or another segment's baseline slice."""
        is_acceptor_only = set(df['segment'].dropna().unique()) == {'Acceptor'}
        if is_acceptor_only:
            sub = df
        else:
            # FIX (2026-06-23): live's fresh Overview scrape shows "Brand
            # Owned" All base = 2938, not 2244 — confirmed = 694 (grida==1,
            # Acceptors trivially own their RE model) + 1789 (grida==2,
            # full Rejector) + 455 (grida==3 & aq1b==1, Cancelled-confirmed-
            # owners). The old mask omitted grida==1 entirely, which is
            # invisible on single-segment Rejector/Cancelled tabs (no
            # grida==1 rows there) but silently undercounted Overview.
            owners_mask = (df['grida'] == 1) | (df['grida'] == 2) | ((df['grida'] == 3) & (df['aq1b'] == 1))
            sub = df[owners_mask]
        base_n = len(sub)
        acc_map = self.value_maps.get('acc', {})
        model_col = 'owned_brand_code'
        quarter_groups = self.quarter_combined_groups(extra_groups)
        extra_cols = list(quarter_groups.keys())

        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in self.month_order + extra_cols:
            rows[0][col] = len(self._col_index(sub, col, quarter_groups))

        def pct_row(label, mask):
            row = {"Unnamed: 0": label}
            for col in ["All"] + self.month_order + extra_cols:
                idx = self._col_index(sub, col, quarter_groups)
                sub_base = len(idx)
                val = mask.loc[idx].sum() / sub_base * 100 if sub_base else 0
                row[col] = val if numeric else f"{val:.0f}%"
            return row

        if by == "brand":
            # Dynamic: use all configured RE model_codes (not hardcoded 1-14)
            re_model_codes = set(RE_MODEL_LABELS.keys())
            re_union = sub[model_col].isin(re_model_codes)
            rows.append(pct_row("Royal Enfield", re_union))
            for code in sorted(re_model_codes):
                rows.append(pct_row(RE_MODEL_LABELS.get(code, f"Model {code}"), sub[model_col] == code))
            for manufacturer in self.manufacturers():
                if manufacturer == "Royal Enfield":
                    continue
                codes = sub.loc[sub[model_col].notna() & (sub['owned_manufacturer'] == manufacturer), model_col].unique()
                if len(codes) == 0:
                    continue
                rows.append(pct_row(manufacturer, sub[model_col].isin(codes)))
                for code in sorted(codes):
                    rows.append(pct_row(acc_map.get(float(code), f"Model {int(code)}"), sub[model_col] == code))
        else:  # CC-wise — RE models use RE_MODEL_PLATFORM; competitors use netting sheet
            cc_map = self._re_aware_cc_map()
            for bucket in sorted(set(cc_map.values())):
                codes = [c for c, v in cc_map.items() if v == bucket]
                label = f"{bucket}CC" if bucket[0].isdigit() else bucket
                rows.append(pct_row(label, sub[model_col].isin(codes)))
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Additional + Replaced — FIXED per spec. Source: dq2a (multi-select,
    # "other vehicles owned") for Additional, dq2b (single-select, "vehicle
    # replaced") for Replaced — decoded via the real Infoleap netting
    # codebook (data/dq2_netting_codebook.json, from
    # "Netting for DQ2a+b" sheet in Enroute_AP_V2_netting.xlsx — this has a
    # DIFFERENT code order than acc/rej/can, e.g. code 14 = Hunter 350 here,
    # not code 3). Base per spec Sheet1 row "DQ2a+b": "Answered Base" /
    # "Filtered base" — i.e. only respondents who actually answered dq1b
    # (878 of them), NOT an extrapolation across the full prior-user group
    # like the earlier Type of Buyer approximation used. See
    # docs/DATA_FIELD_MAPPING.md Addendum 7.
    # ------------------------------------------------------------------
    def additional_replaced_table(self, df, by="brand", base_label="All", numeric=False, extra_groups=None):
        """FIXED (2026-06-19): two real bugs found against
        docs/investigation/full_scraped_data.json's 'All | All' section.
        (1) 'Additional Vehicle'/'Replaced Vehicle' rows were being mixed
        into this table — the live site's Additional+Replaced CC Wise AND
        Brand Wise tables show ONLY vehicle buckets (no Type-of-question
        rollup rows at all); that belongs to a different table entirely
        and has been removed here.
        (2) Brand-wise was missing manufacturer rollup rows AND every
        competitor model (only individual RE-adjacent dq2a model rows were
        emitted, no 'RE'/'HERO'/'BAJAJ' rollups) — live shows brand rollup
        then its member models, brand by brand. CC-wise used cc_revised
        (the codebook's OWN granular buckets, e.g. '200-349') instead of
        cc_netting, which is the exact bucket scheme the live site
        displays ('200-249 CC', '250-350 CC', etc. — confirmed by
        comparing live's 7-row CC Wise table label-for-label)."""
        codebook = self._load_dq2_codebook()

        # Base FIXED (2026-06-23): dq1b.notna() gave 878 vs live's fresh
        # scrape "All" base of 2137 — dq1a.isin([1,2]) (1="Added another
        # vehicle", 2="Replaced existing vehicle") matches live exactly.
        # dq1b is a narrower follow-up field, not the segmentation gate.
        _dq1a_col = self.F.get('buyer_type', 'dq1a')
        if _dq1a_col not in df.columns:
            _dq1a_col = 'dq1a' if 'dq1a' in df.columns else None
        sub = df[df[_dq1a_col].isin([1, 2])] if _dq1a_col else df.iloc[0:0]
        base_n = len(sub)
        quarter_groups = self.quarter_combined_groups(extra_groups)
        extra_cols = list(quarter_groups.keys())
        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in self.month_order + extra_cols:
            rows[0][col] = len(self._col_index(sub, col, quarter_groups))

        def pct_row(label, mask):
            row = {"Unnamed: 0": label}
            for col in ["All"] + self.month_order + extra_cols:
                idx = self._col_index(sub, col, quarter_groups)
                sub_base = len(idx)
                val = mask.loc[idx].sum() / sub_base * 100 if sub_base else 0
                row[col] = val if numeric else f"{val:.0f}%"
            return row

        def model_mask(code):
            # BUG FIX (2026-07-29): this table is titled "Additional +
            # Replaced" but only ever checked dq2a (the multi-select
            # "Additional" answer) -- dq2b (single-select "Replaced"
            # answer) was silently dropped, undercounting every model.
            # Confirmed against live: Classic 350 was 10.8% (dq2a only) vs
            # live's 14%; adding dq2b == code lands at 14.1%, matching.
            col = f"dq2a_{code}"
            add_mask = (sub[col] == 1) if col in sub.columns else pd.Series(False, index=sub.index)
            return add_mask | (sub['dq2b'] == code)

        if by == "brand":
            brands_in_order = []
            for code in sorted(codebook):
                b = codebook[code].get('brand')
                if b and b not in brands_in_order:
                    brands_in_order.append(b)
            for brand in brands_in_order:
                brand_codes = [c for c in codebook if codebook[c].get('brand') == brand
                                and codebook[c]['model'] and codebook[c]['model'] != 'Others']
                if not brand_codes:
                    continue
                brand_mask = pd.concat([model_mask(c) for c in brand_codes], axis=1).any(axis=1)
                # The dq2 netting codebook stores Royal Enfield's brand
                # field as the literal "RE" — relabel for display only
                # (the `brand` variable itself stays "RE" for the
                # codebook equality check above, so matching is unaffected).
                rows.append(pct_row("Royal Enfield" if brand == "RE" else brand, brand_mask))
                for code in brand_codes:
                    mask = model_mask(code)
                    if mask.any():
                        rows.append(pct_row(codebook[code]['model'].title(), mask))
        else:  # CC-wise — cc_netting is the live site's own display bucketing
            cc_buckets = sorted({v['cc_netting'] for v in codebook.values() if v.get('cc_netting')})
            for bucket in cc_buckets:
                codes = [c for c, v in codebook.items() if v.get('cc_netting') == bucket]
                cols = [f"dq2a_{c}" for c in codes if f"dq2a_{c}" in sub.columns]
                add_mask = sub[cols].eq(1).any(axis=1) if cols else pd.Series(False, index=sub.index)
                mask = add_mask | sub['dq2b'].isin(codes)
                label = f"{bucket} CC" if bucket[0].isdigit() else bucket
                rows.append(pct_row(label, mask))
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Reasons & Motivations (Key Buying Factors / Reasons for Rejection /
    # Reasons for Cancelling) — deterministic, exact reproduction via each
    # respondent's OWN assigned netting codes (see _merge_reasons_codes),
    # decoded against the matching netting sheet's Supernet/Net taxonomy.
    # Validated exact match against scraped Acceptor numbers on 9/11
    # Supernet categories (2026-07-27) — see docs/PROJECT_LOG.md. Earlier
    # (2026-07-24) this was believed impossible: "no respondent-level
    # linkage exists" — that investigation missed these 3 columns.
    # ------------------------------------------------------------------
    # Infoleap's own sheets use inconsistent Supernet spelling in a few
    # places -- confirmed against the live dashboard (2026-07-27) that
    # these are meant to be ONE category, not two: exact-string grouping
    # was silently splitting live's single number into two smaller ones.
    # Sheet-specific because the split isn't consistent across sheets --
    # e.g. Rejecter's sheet only has "Dealership Experience" (matches
    # live's own label there, 25%), so it must NOT be remapped to
    # "Overall Dealership experience" the way Cancelled's sheet needs.
    # Adding a new sheet later: add its own entry here if it has the same
    # kind of spelling drift -- everything else in reasons_table() is
    # already generic per-sheet.
    REASONS_SUPERNET_ALIASES = {
        "MQ2a+MQ2b_KBF": {"Visual Appreance": "Visual Appearance"},
        "MQ3a+MQ3b_Rejecter": {"Visual Appreance": "Visual Appearance"},
        "MQ3a+MQ3b_Booked and cancelled": {"Dealership Experience": "Overall Dealership experience"},
    }

    def reasons_table(self, df, base_label="All", by="supernet", numeric=False, extra_groups=None, broad_prefix=None):
        """Segment-aware PER ROW (not per-df) -- df can span multiple
        segments (e.g. Overview/"All") since each respondent is decoded
        using THEIR OWN segment's code column + netting sheet, not one
        picked for the whole df. Raises ValueError only if a segment
        outside Acceptor/Rejector/Cancelled shows up (nothing else has a
        code column to decode).

        broad_prefix: which question pair (e.g. "mq2a", "mq3a") — routed
        through netting_taxonomy.sheet_for(), the SAME mq2*-is-always-KBF /
        mq3*-is-the-segment's-own-sheet rule used for Rejector/Cancelled's
        2 selectable question pairs on the Verbatim Intelligence page (see
        that module for why). Defaults to each segment's live-dashboard
        framing when omitted: "mq2a" for Acceptor (only ever asked KBF),
        "mq3a" for Rejector/Cancelled (matches app.py's Reasons for
        Rejection/Cancelling sections — the negative framing, not the
        positive mq2c/mq2d pair). Applied per-segment (Acceptor rows
        always use "mq2a" regardless of what a mixed-segment call passes,
        since Acceptor has no mq3* pair) unless a single segment is
        present, in which case the override applies to it directly.

        by="supernet" (default) gives the top-level rollup (Visual
        Appearance/Overall Riding/...); by="net" gives the finer Net-level
        breakdown ("Supernet > Net", same string format as
        netting_taxonomy.flatten_supernet_net()) — mirrors the CC-wise/
        Brand-wise dual-view pattern used elsewhere in this file."""
        from utils.netting_taxonomy import load_code_map, sheet_for

        segments_present = set(df['segment'].dropna().unique())
        _VALID = ("Acceptor", "Rejector", "Cancelled")
        if not segments_present or not segments_present <= set(_VALID):
            raise ValueError(
                f"reasons_table() needs df['segment'] to be Acceptor/Rejector/"
                f"Cancelled only — got {segments_present or 'empty'}. No other "
                f"segment has a netting code column to decode."
            )

        # Per-segment decode config, built once -- each segment gets its
        # OWN code column + netting sheet + code map + alias table, so a
        # mixed-segment df (e.g. the full "All" population) decodes every
        # respondent correctly instead of forcing one sheet on everyone.
        _seg_conf = {}
        for seg in segments_present:
            _prefix = broad_prefix or ("mq2a" if seg == "Acceptor" else "mq3a")
            sheet_name = sheet_for(seg, _prefix)
            code_col = {v: k for k, v in self.REASONS_CODE_COLUMNS.items()}[sheet_name]
            _seg_conf[seg] = (
                code_col,
                load_code_map(self.masterfile_path, sheet_name),
                self.REASONS_SUPERNET_ALIASES.get(sheet_name, {}),
            )

        def decode(row):
            code_col, code_map, aliases = _seg_conf[row['segment']]
            code_str = row[code_col]
            code_str = code_str if isinstance(code_str, str) else ""
            if not code_str:
                return frozenset()
            chunks = [code_str[i:i + 3] for i in range(0, len(code_str), 3)]
            cats = set()
            for c in chunks:
                hit = code_map.get(c)
                if hit:
                    supernet, net = hit[0], hit[1]
                    supernet = aliases.get(supernet, supernet)
                    cats.add(supernet if by == "supernet" else f"{supernet} > {net}")
            return frozenset(cats)

        decoded = df.apply(decode, axis=1)

        base_n = len(df)
        quarter_groups = self.quarter_combined_groups(extra_groups)
        extra_cols = list(quarter_groups.keys())
        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in self.month_order + extra_cols:
            rows[0][col] = len(self._col_index(df, col, quarter_groups))

        def pct_row(label, mask):
            row = {"Unnamed: 0": label}
            for col in ["All"] + self.month_order + extra_cols:
                idx = self._col_index(df, col, quarter_groups)
                sub_base = len(idx)
                val = mask.loc[idx].sum() / sub_base * 100 if sub_base else 0
                row[col] = val if numeric else f"{val:.0f}%"
            return row

        all_cats = set().union(*decoded) if len(decoded) else set()
        cat_counts = {cat: sum(1 for cats in decoded if cat in cats) for cat in all_cats}
        for cat in sorted(all_cats, key=lambda c: cat_counts[c], reverse=True):
            mask = decoded.apply(lambda cats, _c=cat: _c in cats)
            rows.append(pct_row(cat, mask))
        return pd.DataFrame(rows)

    def reasons_tree_data(self, df, base_label="All", numeric=False, extra_groups=None, broad_prefix=None):
        """Computes a hierarchical Supernet -> Net structure for open-ended netting taxonomy responses.
        Returns a dictionary with columns, base counts, and sorted supernets with child nets.
        """
        from utils.netting_taxonomy import load_code_map, sheet_for

        if len(df) == 0:
            return {"columns": ["All"], "col_bases": {"All": 0}, "supernets": []}

        segments_present = set(df['segment'].dropna().unique())
        _VALID = ("Acceptor", "Rejector", "Cancelled")
        if not segments_present or not segments_present <= set(_VALID):
            return {"columns": ["All"], "col_bases": {"All": 0}, "supernets": []}

        from utils.stat_engine import calculate_significance

        _seg_conf = {}
        for seg in segments_present:
            _prefix = broad_prefix or ("mq2a" if seg == "Acceptor" else "mq3a")
            sheet_name = sheet_for(seg, _prefix)
            code_col = {v: k for k, v in self.REASONS_CODE_COLUMNS.items()}[sheet_name]
            _seg_conf[seg] = (
                code_col,
                load_code_map(self.masterfile_path, sheet_name),
                self.REASONS_SUPERNET_ALIASES.get(sheet_name, {}),
            )

        def decode_hierarchical(row):
            code_col, code_map, aliases = _seg_conf[row['segment']]
            code_str = row[code_col]
            code_str = code_str if isinstance(code_str, str) else ""
            if not code_str:
                return (frozenset(), frozenset(), frozenset(), frozenset())
            chunks = [code_str[i:i + 3] for i in range(0, len(code_str), 3)]
            supernets = set()
            supernet_nets = set()
            supernet_net_subnets = set()
            supernet_net_subnet_items = set()
            for c in chunks:
                hit = code_map.get(c)
                if hit:
                    if len(hit) >= 4:
                        supernet, net, subnet, item = hit[0], hit[1], hit[2], hit[3]
                    elif len(hit) == 3:
                        supernet, net, subnet = hit[0], hit[1], hit[2]
                        item = subnet
                    elif len(hit) == 2:
                        supernet, net = hit[0], hit[1]
                        subnet = net
                        item = net
                    else:
                        supernet = hit[0]
                        net = supernet
                        subnet = supernet
                        item = supernet

                    supernet = aliases.get(supernet, supernet)
                    supernets.add(supernet)
                    supernet_nets.add((supernet, net))
                    supernet_net_subnets.add((supernet, net, subnet))
                    supernet_net_subnet_items.add((supernet, net, subnet, item))
            return (frozenset(supernets), frozenset(supernet_nets), frozenset(supernet_net_subnets), frozenset(supernet_net_subnet_items))

        decoded = df.apply(decode_hierarchical, axis=1)

        # Per user request: exclude combined quarter months (JAS'25, OND'25, JFM'26) from open-ended netting table
        present = set(df['month_label'].dropna().unique())
        all_time_cols = ["All"] + [c for c in self.month_order if c in present]

        quarter_groups = self.quarter_combined_groups(extra_groups)
        col_indices = {}
        col_bases = {}
        for col in all_time_cols:
            if col == "All":
                idx = df.index
            else:
                idx = self._col_index(df, col, quarter_groups)
            col_indices[col] = idx
            col_bases[col] = len(idx)

        # Filter out time columns with 0 base size unless it's All
        all_time_cols = [c for c in all_time_cols if c == "All" or col_bases[c] > 0]

        all_supernets = set()
        all_nets_map = {}
        all_subnets_map = {}
        all_items_map = {}
        for tup in decoded:
            super_set = tup[0] if len(tup) >= 1 else set()
            net_set = tup[1] if len(tup) >= 2 else set()
            subnet_set = tup[2] if len(tup) >= 3 else set()
            item_set = tup[3] if len(tup) >= 4 else set()

            for s in super_set:
                all_supernets.add(s)
                if s not in all_nets_map:
                    all_nets_map[s] = set()
            for s, n in net_set:
                all_supernets.add(s)
                if s not in all_nets_map:
                    all_nets_map[s] = set()
                all_nets_map[s].add(n)
                if (s, n) not in all_subnets_map:
                    all_subnets_map[(s, n)] = set()
            for s, n, sub in subnet_set:
                all_supernets.add(s)
                if s not in all_nets_map:
                    all_nets_map[s] = set()
                all_nets_map[s].add(n)
                if (s, n) not in all_subnets_map:
                    all_subnets_map[(s, n)] = set()
                all_subnets_map[(s, n)].add(sub)
                if (s, n, sub) not in all_items_map:
                    all_items_map[(s, n, sub)] = set()
            for s, n, sub, itm in item_set:
                all_supernets.add(s)
                if s not in all_nets_map:
                    all_nets_map[s] = set()
                all_nets_map[s].add(n)
                if (s, n) not in all_subnets_map:
                    all_subnets_map[(s, n)] = set()
                all_subnets_map[(s, n)].add(sub)
                if (s, n, sub) not in all_items_map:
                    all_items_map[(s, n, sub)] = set()
                all_items_map[(s, n, sub)].add(itm)

        def _calc_pcts_and_sig(mask):
            num_pcts = {}
            str_pcts = {}
            sig_markers = {}

            all_n = col_bases.get("All", 0)
            all_mask = mask & (df.index.isin(col_indices["All"]))
            all_k = all_mask.sum()
            all_pct = (all_k / all_n * 100.0) if all_n > 0 else 0.0
            p2 = all_pct / 100.0
            all_b = all_n

            for col in all_time_cols:
                idx = col_indices[col]
                b = col_bases[col]
                if b == 0:
                    str_pcts[col] = "-"
                    num_pcts[col] = 0.0
                    sig_markers[col] = ""
                    continue

                col_m = mask & (df.index.isin(idx))
                k = col_m.sum()
                val = (k / b * 100.0) if b > 0 else 0.0
                num_pcts[col] = val
                p1 = val / 100.0

                marker = ""
                if col != "All" and b > 0 and all_b > 0:
                    res = calculate_significance(p1, b, p2, all_b)
                    if res["z_score"] > 0:
                        if res["tier"] == "95":
                            marker = "▲"
                        elif res["tier"] == "90":
                            marker = "△"

                sig_markers[col] = marker
                if not numeric:
                    rounded = round(val)
                    str_val = "-" if rounded == 0 else f"{rounded}%"
                    str_pcts[col] = f"{str_val} {marker}".strip() if (marker and str_val != "-") else str_val
                else:
                    str_pcts[col] = val

            return str_pcts, num_pcts, sig_markers

        supernet_list = []
        for s in all_supernets:
            s_mask = decoded.apply(lambda tup, _s=s: _s in tup[0])
            s_str_pcts, s_num_pcts, s_sig = _calc_pcts_and_sig(s_mask)

            nets_list = []
            for n in all_nets_map.get(s, []):
                sn_mask = decoded.apply(lambda tup, _s=s, _n=n: (_s, _n) in tup[1])
                n_str_pcts, n_num_pcts, n_sig = _calc_pcts_and_sig(sn_mask)

                subnets_list = []
                for sub in all_subnets_map.get((s, n), []):
                    sns_mask = decoded.apply(lambda tup, _s=s, _n=n, _sub=sub: len(tup) >= 3 and (_s, _n, _sub) in tup[2])
                    sub_str_pcts, sub_num_pcts, sub_sig = _calc_pcts_and_sig(sns_mask)

                    items_list = []
                    for itm in all_items_map.get((s, n, sub), []):
                        if itm and str(itm).strip() and str(itm).strip() != str(sub).strip():
                            itms_mask = decoded.apply(lambda tup, _s=s, _n=n, _sub=sub, _itm=itm: len(tup) >= 4 and (_s, _n, _sub, _itm) in tup[3])
                            itm_str_pcts, itm_num_pcts, itm_sig = _calc_pcts_and_sig(itms_mask)
                            items_list.append({
                                'name': itm,
                                'pcts': itm_str_pcts,
                                'numeric_pcts': itm_num_pcts,
                                'sig_markers': itm_sig,
                                'all_pct': itm_num_pcts['All']
                            })

                    items_list.sort(key=lambda x: x['all_pct'], reverse=True)

                    subnets_list.append({
                        'name': sub,
                        'pcts': sub_str_pcts,
                        'numeric_pcts': sub_num_pcts,
                        'sig_markers': sub_sig,
                        'all_pct': sub_num_pcts['All'],
                        'items': items_list
                    })

                subnets_list.sort(key=lambda x: x['all_pct'], reverse=True)

                nets_list.append({
                    'name': n,
                    'pcts': n_str_pcts,
                    'numeric_pcts': n_num_pcts,
                    'sig_markers': n_sig,
                    'all_pct': n_num_pcts['All'],
                    'subnets': subnets_list
                })

            nets_list.sort(key=lambda x: x['all_pct'], reverse=True)

            supernet_list.append({
                'name': s,
                'pcts': s_str_pcts,
                'numeric_pcts': s_num_pcts,
                'sig_markers': s_sig,
                'all_pct': s_num_pcts['All'],
                'nets': nets_list
            })

        supernet_list.sort(key=lambda x: x['all_pct'], reverse=True)

        return {
            'columns': all_time_cols,
            'col_bases': col_bases,
            'base_label': f"Base : Total_{base_label}",
            'supernets': supernet_list,
        }
    # ------------------------------------------------------------------
    # Brand Considered — multi-select aq5a_1..aq5a_124 (1=selected), same
    # code order as acc/rej/can (confirmed via Enroute_AP_V2_netting.xlsx
    # "Neeting for AQ3a_AQ5" sheet). Base = whole sample ("All respondents"
    # per Enroute_AP_V2_netting.xlsx Sheet1 row AQ5a_ALL).
    #
    # KEY FIX: every respondent's own associated RE model is trivially
    # flagged 1 in aq5a (confirmed: 694/694 Acceptors). For Acceptors this
    # inflates the numbers — AQ5a asks "what OTHER models did you
    # consider", and the model they bought isn't "other". For
    # Rejector/Cancelled, their own associated RE model genuinely IS
    # something they considered before buying/cancelling elsewhere, so it's
    # kept. Excluding ONLY the Acceptor self-match: RE union dropped from a
    # wrongly-inflated 98% to 87.5% (scraped 81%) and individual top RE
    # models from ~2x the scraped value to ~1.4-1.8x. Real improvement, but
    # NOT an exact match — ship with this caveat clearly visible, do not
    # claim exact replication for this table. See
    # docs/DATA_FIELD_MAPPING.md Addendum 8.
    #
    # CC-wise uses the real CC bucketing from the same netting sheet
    # ("New_netting" column) rather than RE_MODEL_PLATFORM, since that's
    # what the live table's row labels ("150-199CC" etc.) actually are.
    # Non-RE-dominant buckets (150-199, 200-249) match almost exactly with
    # no fix needed (7.6% vs 7%, 4.0% vs 3%), confirming the bug is
    # RE-self-match specific, not a base/denominator problem.
    # ------------------------------------------------------------------
    def brand_considered_table(self, df, by="brand", base_label="All", numeric=False, extra_groups=None):
        base_n = len(df)
        acc_map = self.value_maps.get('acc', {})
        quarter_groups = self.quarter_combined_groups(extra_groups)
        extra_cols = list(quarter_groups.keys())

        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in self.month_order + extra_cols:
            rows[0][col] = len(self._col_index(df, col, quarter_groups))

        def considered_mask(codes):
            mask = pd.Series(False, index=df.index)
            for c in codes:
                col = f"aq5a_{c}"
                if col not in df.columns:
                    continue
                # BUG FIX (2026-06-19): since segment redefinition, ~1,303
                # rows reclassified into Acceptor have a null `acc` (their
                # RE model lives in `aq3_po` instead, that question was
                # never asked of them as an original Acceptor) — self_match
                # silently never fired for them, inflating their RE-
                # considered tally. Check both columns, whichever is populated.
                self_match = (df['segment'] == 'Acceptor') & ((df['acc'] == c) | (df['aq3_po'] == c))
                mask |= (df[col] == 1) & (~self_match)
            return mask

        def pct_row(label, mask):
            row = {"Unnamed: 0": label}
            for col in ["All"] + self.month_order + extra_cols:
                idx = self._col_index(df, col, quarter_groups)
                sub_base = len(idx)
                val = mask.loc[idx].sum() / sub_base * 100 if sub_base else 0
                row[col] = val if numeric else f"{val:.0f}%"
            return row

        if by == "brand":
            # Dynamic RE model codes: use raw acceptor_codes from _ACC_CODE_MAP
            # (aq5a columns use raw survey codes, e.g. aq5a_125 for Bullet 650)
            re_raw_codes = sorted(_ACC_CODE_MAP.keys()) if _HAS_EXPLICIT_CODES and _ACC_CODE_MAP else list(range(1, _MAX_MODEL_CODE + 1))
            rows.append(pct_row("Royal Enfield", considered_mask(re_raw_codes)))
            # Sub-rows: one per RE model, label from RE_MODEL_LABELS
            for raw_code in re_raw_codes:
                model_code = _ACC_CODE_MAP.get(raw_code, raw_code) if _HAS_EXPLICIT_CODES else raw_code
                label = RE_MODEL_LABELS.get(model_code) or acc_map.get(float(raw_code), f"Model {raw_code}")
                rows.append(pct_row(label, considered_mask([raw_code])))
            # Competitor brands — all aq5a codes not claimed by RE model_config
            known_re_raw = set(re_raw_codes)
            manufacturer_codes = {}
            for code in range(1, 125):
                if code in known_re_raw:
                    continue
                label = acc_map.get(float(code), "")
                manufacturer = label.split(" - ")[0].strip() if " - " in label else label
                manufacturer = {"RIUMPH": "TRIUMPH"}.get(manufacturer, manufacturer)
                if manufacturer:
                    manufacturer_codes.setdefault(manufacturer, []).append(code)
            for manufacturer, codes in manufacturer_codes.items():
                rows.append(pct_row(manufacturer, considered_mask(codes)))
                for code in sorted(codes):
                    rows.append(pct_row(acc_map.get(float(code), f"Model {code}"), considered_mask([code])))
        else:  # CC-wise — RE models use RE_MODEL_PLATFORM; competitors use netting sheet
            cc_map = self._re_aware_cc_map(use_acc_codes=True)
            for bucket in sorted(set(cc_map.values())):
                codes = [c for c, v in cc_map.items() if v == bucket]
                rows.append(pct_row(f"{bucket}CC" if bucket[0].isdigit() else bucket, considered_mask(codes)))
        return pd.DataFrame(rows)

    def brand_resilience_table(self, df, base_label="All", numeric=False, extra_groups=None):
        """AQ5c: 'If your preferred brand/model were unavailable, what would you have bought?'
        Groups: Royal Enfield (codes 1-14), top competitor brands, Would not buy (code 124).
        Only asked to Acceptors and Rejectors — Cancelled have 0 responses.
        Base = non-null aq5c count (not total segment n).
        """
        _aq5c = self.F.get('brand_resilience', 'aq5c')
        if _aq5c not in df.columns:
            return pd.DataFrame()
        sub = df[df[_aq5c].notna()].copy()
        base_n = len(sub)
        if base_n == 0:
            return pd.DataFrame()

        acc_map = self.value_maps.get('acc', {})
        quarter_groups = self.quarter_combined_groups(extra_groups)
        extra_cols = list(quarter_groups.keys())

        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in self.month_order + extra_cols:
            rows[0][col] = len(self._col_index(sub, col, quarter_groups))

        def pct_row(label, mask):
            row = {"Unnamed: 0": label}
            for col in ["All"] + self.month_order + extra_cols:
                idx = self._col_index(sub, col, quarter_groups)
                n_col = len(idx)
                if n_col == 0:
                    row[col] = 0.0
                    continue
                cnt = mask.loc[idx].sum() if not idx.empty else 0
                row[col] = round(cnt / n_col * 100) if numeric else f"{cnt / n_col * 100:.0f}%"
            return row

        re_codes = set(RE_MODEL_LABELS.keys())
        re_mask = sub['aq5c'].isin(re_codes)
        rows.append(pct_row("Royal Enfield (retain brand)", re_mask))

        no_buy_mask = sub['aq5c'] == 124.0
        rows.append(pct_row("Would not buy any alternative", no_buy_mask))

        # Top competitor brands (exclude RE + code 124)
        comp_sub = sub[~sub['aq5c'].isin(re_codes | {124.0})]
        if len(comp_sub):
            brand_counts = {}
            for code, grp in comp_sub.groupby('aq5c'):
                label = acc_map.get(float(code), f"Code {int(code)}")
                brand = label.split(" - ")[0].strip() if " - " in label else label
                brand_counts[brand] = brand_counts.get(brand, 0) + len(grp)
            for brand, _ in sorted(brand_counts.items(), key=lambda x: -x[1])[:5]:
                brand_mask = comp_sub['aq5c'].map(
                    lambda c: (acc_map.get(float(c), "").split(" - ")[0].strip()
                               if " - " in acc_map.get(float(c), "") else acc_map.get(float(c), "")) == brand
                ).reindex(sub.index, fill_value=False)
                rows.append(pct_row(brand, brand_mask))

        return pd.DataFrame(rows)

    def aq5b_table(self, df, base_label="All", numeric=False, extra_groups=None):
        """AQ5b: 'Which RE model did you consider most seriously before choosing a competitor?'
        Only meaningful for Rejectors (n≈957 non-null out of 1,789).
        Shows % of total segment (not % of aq5b-answerers) so base = full segment n.
        Top RE models sorted by All% descending.
        """
        if 'aq5b' not in df.columns:
            return pd.DataFrame()
        base_n = len(df)
        if base_n == 0:
            return pd.DataFrame()

        quarter_groups = self.quarter_combined_groups(extra_groups)
        extra_cols = list(quarter_groups.keys())

        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in self.month_order + extra_cols:
            rows[0][col] = len(self._col_index(df, col, quarter_groups))

        def pct_row(label, code):
            row = {"Unnamed: 0": label}
            for col in ["All"] + self.month_order + extra_cols:
                idx = self._col_index(df, col, quarter_groups)
                n_col = len(idx)
                if n_col == 0:
                    row[col] = 0.0 if numeric else "0%"
                    continue
                cnt = (df.loc[idx, 'aq5b'] == float(code)).sum()
                row[col] = round(cnt / n_col * 100) if numeric else f"{cnt / n_col * 100:.0f}%"
            return row

        data_rows = []
        for code, name in RE_MODEL_LABELS.items():
            short = name.replace("Royal Enfield ", "")
            _aq5b = self.F.get('re_model_considered', 'aq5b')
            cnt = (df[_aq5b] == float(code)).sum()
            if cnt > 0:
                data_rows.append((cnt, code, short))

        for _, code, label in sorted(data_rows, reverse=True):
            rows.append(pct_row(label, code))

        return pd.DataFrame(rows)

    def test_ride_table(self, df, base_label="All", numeric=False, extra_groups=None):
        """AQ6: multi-select binary columns aq6_1..aq6_124 — which models did respondent test ride?
        Returns % of base who test-rode each RE model (codes 1-14 only).
        Base = total segment n (all respondents, not just those who test-rode any model).
        Sorted by All% descending.
        """
        base_n = len(df)
        if base_n == 0:
            return pd.DataFrame()

        quarter_groups = self.quarter_combined_groups(extra_groups)
        extra_cols = list(quarter_groups.keys())

        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in self.month_order + extra_cols:
            rows[0][col] = len(self._col_index(df, col, quarter_groups))

        def pct_row(label, code):
            col_name = f"aq6_{int(code)}"
            if col_name not in df.columns:
                return None
            row = {"Unnamed: 0": label}
            for col in ["All"] + self.month_order + extra_cols:
                idx = self._col_index(df, col, quarter_groups)
                n_col = len(idx)
                if n_col == 0:
                    row[col] = 0.0 if numeric else "0%"
                    continue
                cnt = (df.loc[idx, col_name] == 1).sum()
                row[col] = round(cnt / n_col * 100) if numeric else f"{cnt / n_col * 100:.0f}%"
            return row

        data_rows = []
        for code, name in RE_MODEL_LABELS.items():
            col_name = f"aq6_{int(code)}"
            if col_name not in df.columns:
                continue
            cnt = (df[col_name] == 1).sum()
            if cnt > 0:
                short = name.replace("Royal Enfield ", "")
                data_rows.append((cnt, code, short))

        for _, code, label in sorted(data_rows, reverse=True):
            row = pct_row(label, code)
            if row:
                rows.append(row)

        return pd.DataFrame(rows)

    # AQ2A display labels — loaded from display_groups sheet (variable=aq2a)
    @property
    def _AQ2A_DISPLAY(self):
        return _DISPLAY_GROUPS.get("aq2a") or {2.0: "150-249 CC", 3.0: "250-350 CC", 4.0: "351 CC and above"}

    def competitor_cc_table(self, df, base_label="All", numeric=False, extra_groups=None):
        """AQ2A: CC range of competitor bike considered / purchased.
        All 3 segments answer (Rej=1789, Acc=1303, Can=455). Base = aq2a non-null count.
        Sorted by All% descending.
        """
        tbl = self.distribution_table(
            df, self.F.get('competitor_cc', 'aq2a'), base_label,
            display_groups=self._AQ2A_DISPLAY,
            numeric=numeric,
            extra_groups=extra_groups,
        )
        return self.sort_by_value(tbl) if numeric else tbl

    # AQ1B display labels — loaded from display_groups sheet (variable=aq1b)
    @property
    def _AQ1B_DISPLAY(self):
        return _DISPLAY_GROUPS.get("aq1b") or {1.0: "Bought another 2W", 2.0: "Bought a car", 3.0: "Still searching", 4.0: "Dropped the idea"}

    def post_cancellation_table(self, df, base_label="All", numeric=False, extra_groups=None):
        """AQ1B: What did Booked-but-Cancelled respondents do after cancelling?
        Strictly Cancelled-segment question (n=1,527). Base = aq1b non-null count.
        """
        tbl = self.distribution_table(
            df, self.F.get('post_cancel_action', 'aq1b'), base_label,
            display_groups=self._AQ1B_DISPLAY,
            numeric=numeric,
            extra_groups=extra_groups,
        )
        return self.sort_by_value(tbl) if numeric else tbl

    def _load_dq2_codebook(self) -> dict:
        """Load DQ2a/DQ2b codebook.

        Returns dict: {dq2b_code(int): {'brand': str, 'cc_netting': str, 'model': str}}

        Source priority:
        1. RE models: auto-generated from model_config (dq2b_code + platform_cc columns).
           Adding new RE model to model_config auto-populates this — no netting_dq2 change needed.
        2. Competitor models: read from netting_dq2 Excel sheet (competitor rows only).
           Adding new competitor: add row to netting_dq2.
        3. Fallback: JSON codebook (legacy, used if Excel missing).

        Platform → DQ2 CC bucket:
          350CC/450CC → '351 and above'  (all RE premium models ≥350CC)
          650CC       → '501-650'
        """
        if hasattr(self, '_dq2_codebook_cache'):
            return self._dq2_codebook_cache

        codebook: dict = {}
        _PLATFORM_TO_DQ2_BUCKET = {'350CC': '351 and above', '450CC': '351 and above', '650CC': '501-650'}

        # Step 1: RE models from model_config (via _DQ2B_CODE_MAP populated at load_data)
        for model_code, dq2b_code in _DQ2B_CODE_MAP.items():
            name = RE_MODEL_LABELS.get(model_code, '')
            plat = RE_MODEL_PLATFORM.get(model_code, '')
            cc_bucket = _PLATFORM_TO_DQ2_BUCKET.get(plat, '351 and above')
            codebook[dq2b_code] = {
                'brand':      'RE',
                'cc_netting': cc_bucket,
                'model':      name.upper(),
            }

        # Step 2: Competitor models from netting_dq2 sheet
        try:
            xl = pd.ExcelFile(self.masterfile_path)
            if 'netting_dq2' in xl.sheet_names:
                sheet = xl.parse('netting_dq2', header=0, skiprows=[1])
                for _, row in sheet.iterrows():
                    try:
                        code = int(float(row.get('code', 0) or 0))
                        if code <= 0:
                            continue
                        brand = str(row.get('brand', '') or '').strip()
                        if brand.upper() == 'RE':
                            continue  # RE entries come from model_config above
                        model_name_col = next((c for c in sheet.columns if 'model_name' in str(c).lower()), None)
                        model_name = str(row.get(model_name_col, '') or '').replace('[AUTO from model_config]', '').strip()
                        codebook[code] = {
                            'brand':      brand or None,
                            'cc_netting': str(row.get('cc_netting', '') or '').strip() or None,
                            'model':      model_name,
                        }
                    except (ValueError, TypeError):
                        continue
        except Exception:
            pass

        # Step 3: JSON fallback (only if Excel gave nothing at all)
        if not codebook:
            try:
                with open(DQ2_CODEBOOK_PATH, encoding='utf-8') as f:
                    raw = json.load(f)
                codebook = {int(k): v for k, v in raw.items()}
            except (FileNotFoundError, json.JSONDecodeError):
                codebook = {}

        self._dq2_codebook_cache = codebook
        return codebook

    def _re_aware_cc_map(self, use_acc_codes: bool = False) -> dict:
        """Unified CC-bucket map for all codes.

        For brand_owned_table (use_acc_codes=False): owned_brand_code is
        normalized to model_code (1-N) for RE models, so RE_MODEL_PLATFORM
        is the authoritative source. Competitors use the netting sheet.

        For brand_considered_table (use_acc_codes=True): aq5a columns use raw
        acceptor_codes (e.g. 125 for Bullet 650), not model_codes. RE raw codes
        come from _ACC_CODE_MAP.keys(); CC bucket from RE_MODEL_PLATFORM via
        the model_code mapping. Competitors use the netting sheet for all codes
        not claimed by model_config.

        Platform → netting-style bucket string (matches live dashboard labels).
        """
        platform_to_bucket = {"350CC": "250-350", "450CC": "351-500", "650CC": "501-650"}
        competitor_netting = self._aq5a_cc_netting()

        if use_acc_codes:
            # aq5a codes: RE = raw acceptor codes; competitors = everything else
            known_re_raw = set(_ACC_CODE_MAP.keys()) if _HAS_EXPLICIT_CODES and _ACC_CODE_MAP else set(range(1, _MAX_MODEL_CODE + 1))
            result = {code: bucket for code, bucket in competitor_netting.items() if code not in known_re_raw}
            for raw_code in known_re_raw:
                model_code = _ACC_CODE_MAP.get(raw_code, raw_code) if _HAS_EXPLICIT_CODES else raw_code
                plat = RE_MODEL_PLATFORM.get(model_code)
                bucket = platform_to_bucket.get(plat)
                if bucket:
                    result[raw_code] = bucket
        else:
            # owned_brand_code normalized to model_code for RE; raw for competitors
            re_model_codes = set(RE_MODEL_PLATFORM.keys())
            result = {code: bucket for code, bucket in competitor_netting.items() if code not in re_model_codes}
            for model_code, plat in RE_MODEL_PLATFORM.items():
                bucket = platform_to_bucket.get(plat)
                if bucket:
                    result[model_code] = bucket

        return result

    def _aq5a_cc_netting(self):
        """Loads CC-bucket scheme for aq5a/aq5c survey codes from netting_aq3a_aq5 sheet.

        Sheet structure (post-restructure):
          Col 0 = survey_code (explicit integer — replaces position-based reading)
          Col 1 = model_name, Col 2 = brand, Col 3 = cc, Col 4 = revised, Col 5 = new_netting
          Row 3 = header row, rows 4+ = data.

        RE models are included in the sheet for reference but their CC bucket comes
        from model_config.platform_cc via _re_aware_cc_map() — no duplication needed.
        Cached on instance after first read."""
        if hasattr(self, '_aq5a_cc_netting_cache'):
            return self._aq5a_cc_netting_cache
        if not MASTER_CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"RE_MIS_Master.xlsx not found at {MASTER_CONFIG_PATH}. "
                "Set DRIVE_FILE_ID in Streamlit Cloud secrets and reload."
            )
        net = pd.read_excel(MASTER_CONFIG_PATH, sheet_name="netting_aq3a_aq5", header=None)
        # Row 0=blank, row 1=title, row 2=header, rows 3+ = data.
        # Col 0 = survey_code (explicit after restructure), Col 5 = new_netting bucket.
        data = net.iloc[3:].reset_index(drop=True)
        result = {}
        for i in range(len(data)):
            raw_code = data.iloc[i, 0]
            bucket   = str(data.iloc[i, 5]).strip()
            if bucket in ('', 'nan', 'New_netting'):
                continue
            try:
                code = int(float(raw_code))
                result[code] = bucket
            except (ValueError, TypeError):
                # Legacy: no survey_code column yet — fall back to position
                if not result:
                    result[i + 1] = bucket
        self._aq5a_cc_netting_cache = result
        return self._aq5a_cc_netting_cache


if __name__ == "__main__":
    engine = DataEngine()
    engine.load_data()
    print("Segments:", engine.df['segment'].value_counts(dropna=False).to_dict())
    print(engine.age_table(engine.filter_df()).to_string())
