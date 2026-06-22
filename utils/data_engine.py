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

MASTERFILE_PATH = "data/Enroute_Fourth Wave_Masterfile_Base_4010_AUG-MAY.xlsx"
DATAMAP_PATH = "data/MIS_datamap.xlsx"
DQ2_CODEBOOK_PATH = "data/dq2_netting_codebook.json"

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
    else:  # Jan-Mar belongs to the FY that started the previous April
        q, fy_start = 4, cal_year - 1
    return f"Q{q} FY{str(fy_start)[2:]}-{str(fy_start + 1)[2:]}"


MONTHLY_DROPS_DIR = "data/monthly_drops"  # poor-man's sync target: drop a
# new month's extract .xlsx here (same schema as the Masterfile) and it
# gets merged in automatically on next load. True SharePoint auto-sync
# needs an Azure AD app registration + Graph API credentials from
# Royal Enfield/Infoleap IT — wire that in once those exist; this folder
# is the interim mechanism so the system itself isn't hardcoded to one file.

# acc/rej/can/aq3_po/seg-derived RE model codes 1-14, and their CC platform.
RE_MODEL_LABELS = {
    1: "Royal Enfield Bullet 350", 2: "Royal Enfield Classic 350",
    3: "Royal Enfield Hunter 350", 4: "Royal Enfield Meteor 350",
    5: "Royal Enfield Goan Classic 350", 6: "Royal Enfield Scram 440",
    7: "Royal Enfield Himalayan 450", 8: "Royal Enfield Guerrilla 450",
    9: "Royal Enfield Continental GT 650", 10: "Royal Enfield Interceptor 650",
    11: "Royal Enfield Super Meteor 650", 12: "Royal Enfield Bear 650",
    13: "Royal Enfield Shotgun 650", 14: "Royal Enfield Classic 650",
}
RE_MODEL_PLATFORM = {
    1: "350CC", 2: "350CC", 3: "350CC", 4: "350CC", 5: "350CC",
    6: "450CC", 7: "450CC", 8: "450CC",
    9: "650CC", 10: "650CC", 11: "650CC", 12: "650CC", 13: "650CC", 14: "650CC",
}

# Display-bucket groupings matching the live dashboard's collapsed categories
# (docs/DATA_FIELD_MAPPING.md Addendum 3 — raw per-code %s are correct, but the
# live site shows fewer, merged rows). None = drop from the chart (negligible).
EDUCATION_DISPLAY_GROUPS = {
    1.0: None, 2.0: None, 3.0: None,  # Illiterate / School<=4 / School5-9 (~1% combined)
    4.0: "SSC / HSC",
    5.0: "College but non-grad (Diploma)",
    6.0: "General Graduate/PG",
    7.0: "Professional Graduate/PG",
}
OCCUPATION_DISPLAY_GROUPS = {
    1.0: "Full time worker", 2.0: "Full time worker",
    3.0: "Other", 4.0: "Other",
    5.0: "Businessman", 6.0: "Businessman", 7.0: "Businessman", 8.0: "Businessman",
    9.0: "Other", 10.0: "Other",
    11.0: "Agriculture",
    12.0: "Student",
    13.0: "Other", 14.0: "Other", 15.0: "Other",
}


class DataEngine:
    def __init__(self, masterfile_path=MASTERFILE_PATH, datamap_path=DATAMAP_PATH):
        self.masterfile_path = masterfile_path
        self.datamap_path = datamap_path
        self.df = None
        self.labels = {}
        self.value_maps = {}
        # Instance-level copies, not just the mutated module globals below —
        # Streamlit's file-watcher can re-import utils.data_engine on a code
        # change while @st.cache_resource keeps the OLD engine instance
        # alive, leaving the module's MONTH_ORDER list reset to empty while
        # this engine's data is still fully loaded. Reading from the
        # instance (engine.month_order) instead of the module global avoids
        # that desync — see BUGS.md.
        self.month_order = []
        self.fy_quarter_order = []

    # ------------------------------------------------------------------
    # Load + decode
    # ------------------------------------------------------------------
    def load_data(self):
        # header=1: row 0 of the Masterfile is a merged group-header row
        # (e.g. "Segment", "Acceptor / Brand Owned"), real column codes are row 1.
        self.df = pd.read_excel(self.masterfile_path, header=1)
        self._ingest_monthly_drops()

        dm = pd.read_excel(self.datamap_path, skiprows=2)
        self.labels = dict(zip(dm['Variable'], dm['Label']))

        dm2 = pd.read_excel(self.datamap_path, sheet_name='Sheet2')
        self._parse_value_labels(dm2)

        # age_grp has no Sheet2 value-map block (derived/recoded variable,
        # not documented in the datamap) — bucket order confirmed against
        # scraped % in docs/DATA_FIELD_MAPPING.md (26%/53%/18%/3%).
        if not self.value_maps.get('age_grp'):
            self.value_maps['age_grp'] = {
                1.0: "18 to 25 Years", 2.0: "26 to 35 Years",
                3.0: "36 to 45 Years", 4.0: "46 or more",
            }

        self._derive_segment()
        self._derive_month()

        # Drop incomplete/blank submissions (no grida, no SubmissionDate —
        # genuinely empty quota rows, not real respondents). Unrelated to
        # the month-window question below; this is just data hygiene.
        self.df = self.df[self.df['month_label'].notna()].copy()

        # Dynamic month list (see BUGS.md Bug #1 for the historical finding
        # this replaces): derive every month actually present in the data,
        # in true chronological order, instead of a hardcoded literal list.
        # This is what lets new monthly drops show up automatically.
        present_months = self.df['month_label'].dropna().unique().tolist()
        present_months.sort(key=lambda m: pd.to_datetime(m.replace("'", " "), format="%B %Y"))
        fy_quarters = sorted(set(month_label_to_fy_quarter(m) for m in present_months),
                              key=lambda q: present_months.index(
                                  next(m for m in present_months if month_label_to_fy_quarter(m) == q)))
        self.month_order = present_months
        self.fy_quarter_order = fy_quarters
        MONTH_ORDER[:] = present_months          # kept for backward compat / direct module use
        FY_QUARTER_ORDER[:] = fy_quarters
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

    def _parse_value_labels(self, dm2):
        current_var = None
        for _, row in dm2.iterrows():
            var_name = row['Unnamed: 0']
            if pd.notna(var_name) and var_name not in ('Variable Values', 'Value'):
                current_var = var_name
                self.value_maps[current_var] = {}
            val, label = row['Unnamed: 1'], row['Unnamed: 2']
            if pd.notna(val) and pd.notna(label) and current_var:
                try:
                    self.value_maps[current_var][float(val)] = str(label)
                except ValueError:
                    self.value_maps[current_var][val] = str(label)

    def _manufacturer_for_code(self, code):
        """Manufacturer name for any owned_brand_code (1-124 scheme). Shared
        by _derive_segment (global fallback columns) and filter_df (per-
        segment rescoping) so there's one definition, not two copies that
        could drift."""
        if pd.isna(code):
            return None
        if 1 <= code <= 14:
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
        df = self.df
        acceptor_mask = df['aq3_po'].between(1, 14)
        df['segment'] = None
        df.loc[acceptor_mask, 'segment'] = 'Acceptor'
        df.loc[(df['grida'] == 2) & ~acceptor_mask, 'segment'] = 'Rejector'
        df.loc[(df['grida'] == 3) & ~acceptor_mask, 'segment'] = 'Cancelled'

        acc_or_aq3po = df['acc'].fillna(df['aq3_po'])
        df['re_model_code'] = np.select(
            [df['segment'] == 'Acceptor', df['segment'] == 'Rejector', df['segment'] == 'Cancelled'],
            [acc_or_aq3po, df['rej'], df['can']],
            default=np.nan,
        )
        df['re_model_name'] = df['re_model_code'].map(RE_MODEL_LABELS)
        df['re_platform'] = df['re_model_code'].map(RE_MODEL_PLATFORM)

        # Unified "what model does this respondent actually own" across
        # RE AND every competitor brand (1-124 scheme), per user request to
        # filter/segregate by brand+model beyond just RE's 14 models.
        # Acceptors: acc (their RE purchase). Rejector/Cancelled: aq3 (what
        # they actually bought instead — RE codes 1-14 here would mean a
        # Rejector/Cancelled who still ended up owning an RE model; codes
        # 15-123 are competitor purchases; NaN = no resolvable purchase,
        # e.g. a Cancelled respondent who never confirmed buying anything).
        df['owned_brand_code'] = acc_or_aq3po.where(df['segment'] == 'Acceptor', df['aq3'])
        acc_map = self.value_maps.get('acc', {})
        df['owned_brand_name'] = df['owned_brand_code'].map(acc_map)

        df['owned_manufacturer'] = df['owned_brand_code'].apply(self._manufacturer_for_code)

    def _derive_month(self):
        # The raw `month`/`year` text columns are dirty (typos, garbage years).
        # SubmissionDate is a clean datetime — derive month labels from it.
        dt = pd.to_datetime(self.df['SubmissionDate'], errors='coerce')
        self.df['month_label'] = dt.dt.strftime("%B'%Y")

    def quarter_combined_groups(self):
        """{display_label: [month_labels]} for the live site's always-shown
        quarter-combined columns (e.g. 'JAS\\'25') — see QUARTER_INITIALS.
        The trailing (most recent, still-filling) quarter is excluded, same
        as live: confirmed it shows JAS'25/OND'25/JFM'26 but NOT the current
        Apr-Jun quarter even though Apr/May already have rows."""
        groups = {}
        for m in self.month_order:
            q = month_label_to_fy_quarter(m)
            groups.setdefault(q, []).append(m)
        quarters_to_show = self.fy_quarter_order[:-1] if len(self.fy_quarter_order) > 1 else []
        out = {}
        for q in quarters_to_show:
            months = groups.get(q)
            if not months:
                continue
            qnum = int(q.split()[0][1:])
            year_suffix = months[0].split("'")[1][2:]
            out[f"{QUARTER_INITIALS[qnum]}'{year_suffix}"] = months
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
        'All' (no segment) keeps the global mutually-exclusive columns from
        _derive_segment, for Overview and "rest of sample" baselines."""
        if segment == "Acceptor":
            df = self.df[self.df['aq3_po'].between(1, 14)].copy()
            df['segment'] = 'Acceptor'
            df['re_model_code'] = df['acc'].fillna(df['aq3_po'])
            df['owned_brand_code'] = df['re_model_code']
        elif segment == "Rejector":
            df = self.df[self.df['grida'] == 2].copy()
            df['segment'] = 'Rejector'
            df['re_model_code'] = df['rej']
            df['owned_brand_code'] = df['aq3']
        elif segment == "Cancelled":
            df = self.df[self.df['grida'] == 3].copy()
            df['segment'] = 'Cancelled'
            df['re_model_code'] = df['can']
            df['owned_brand_code'] = df['aq3']
        else:
            df = self.df
        if segment in ("Acceptor", "Rejector", "Cancelled"):
            df['re_platform'] = df['re_model_code'].map(RE_MODEL_PLATFORM)
            df['owned_manufacturer'] = df['owned_brand_code'].apply(self._manufacturer_for_code)
        if platform and platform != "All":
            df = df[df['re_platform'] == platform]
        if model_code:
            df = df[df['re_model_code'] == model_code]
        if owned_brand_code:
            df = df[df['owned_brand_code'] == owned_brand_code]
        return df

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
    def distribution_table(self, df, code_col, base_label, display_groups=None, numeric=False):
        """
        display_groups: optional {code: display_label or None}. Codes mapping
        to the same label are summed together; None drops that code from the
        chart (used to match the live dashboard's collapsed category display).
        numeric: return raw floats instead of "NN%" strings (for chart use).
        """
        value_map = self.value_maps.get(code_col, {})
        base_n = df[code_col].notna().sum()
        quarter_groups = self.quarter_combined_groups()
        extra_cols = list(quarter_groups.keys())

        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in MONTH_ORDER + extra_cols:
            idx = self._col_index(df, col, quarter_groups)
            rows[0][col] = df.loc[idx, code_col].notna().sum()

        if display_groups:
            labels_in_order = []
            for code in sorted(value_map):
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
            for col in MONTH_ORDER + extra_cols:
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
        sorts the blocks by the rollup's own 'All' value, and always puts
        the 'Other' block last."""
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
            ordered_rows.append(pd.DataFrame(block_rows))
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

    def age_table(self, df, base_label="All", numeric=False):
        return self.distribution_table(df, 'age_grp', base_label, numeric=numeric)

    def education_table(self, df, base_label="All", numeric=False):
        return self.distribution_table(df, 'dq3', base_label, display_groups=EDUCATION_DISPLAY_GROUPS, numeric=numeric)

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

    def occupation_table(self, df, base_label="All", numeric=False):
        tbl = self.distribution_table(df, 'dq4', base_label, display_groups=OCCUPATION_DISPLAY_GROUPS, numeric=numeric)
        return self.sort_by_value(tbl) if numeric else tbl

    def household_income_table(self, df, base_label="All", numeric=False):
        return self.distribution_table(df, 'dq6', base_label, numeric=numeric)

    # ------------------------------------------------------------------
    # Type of Buyer — dq1a (prior 2W usage) x dq1b (additional vs replaced).
    # dq1a==3/4 match the scrape almost exactly as standalone buckets. The
    # Additional/Replaced split is trickier: dq1b was only answered by 878 of
    # the 2137 respondents with dq1a in {1,2} (skip-logic gap in the raw
    # data). We extrapolate dq1b's answered ratio across the full {1,2}
    # group rather than reporting only the 878 who answered — validated
    # against scrape: 47.6%/5.7% computed vs 49%/5% scraped (close, within
    # the same ~10% overall base gap documented elsewhere in this file).
    # See docs/DATA_FIELD_MAPPING.md Addendum 5.
    # ------------------------------------------------------------------
    def type_of_buyer_table(self, df, base_label="All", numeric=False):
        base_n = df['dq1a'].notna().sum()
        quarter_groups = self.quarter_combined_groups()
        extra_cols = list(quarter_groups.keys())
        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in MONTH_ORDER + extra_cols:
            idx = self._col_index(df, col, quarter_groups)
            rows[0][col] = df.loc[idx, 'dq1a'].notna().sum()

        prior_user_mask = df['dq1a'].isin([1, 2])
        answered_mask = prior_user_mask & df['dq1b'].notna()
        additional_ratio = (df.loc[answered_mask, 'dq1b'] == 1).sum() / answered_mask.sum() if answered_mask.sum() else 0
        replaced_ratio = 1 - additional_ratio

        def pct_row(label, mask_fn):
            row = {"Unnamed: 0": label}
            for col in ["All"] + MONTH_ORDER + extra_cols:
                sub = df.loc[self._col_index(df, col, quarter_groups)]
                sub_base = len(sub)
                val = mask_fn(sub) / sub_base * 100 if sub_base else 0
                row[col] = val if numeric else f"{val:.0f}%"
            return row

        rows.append(pct_row("This is my Additional 2W", lambda d: d['dq1a'].isin([1, 2]).sum() * additional_ratio))
        rows.append(pct_row("First Time Buyer of 2W (No one owns a 2W)", lambda d: (d['dq1a'] == 4).sum()))
        rows.append(pct_row("First Time Buyer of 2W (Family owns a 2W and not a primary user)", lambda d: (d['dq1a'] == 3).sum()))
        rows.append(pct_row("This is my Replaced 2W", lambda d: d['dq1a'].isin([1, 2]).sum() * replaced_ratio))
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
    def brand_owned_table(self, df, by="brand", base_label="All", numeric=False):
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
            owners_mask = (df['grida'] == 2) | ((df['grida'] == 3) & (df['aq1b'] == 1))
            sub = df[owners_mask]
        base_n = len(sub)
        acc_map = self.value_maps.get('acc', {})
        model_col = 'owned_brand_code'
        quarter_groups = self.quarter_combined_groups()
        extra_cols = list(quarter_groups.keys())

        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in MONTH_ORDER + extra_cols:
            rows[0][col] = len(self._col_index(sub, col, quarter_groups))

        def pct_row(label, mask):
            row = {"Unnamed: 0": label}
            for col in ["All"] + MONTH_ORDER + extra_cols:
                idx = self._col_index(sub, col, quarter_groups)
                sub_base = len(idx)
                val = mask.loc[idx].sum() / sub_base * 100 if sub_base else 0
                row[col] = val if numeric else f"{val:.0f}%"
            return row

        re_union = sub[model_col].between(1, 14)
        rows.append(pct_row("RE", re_union))

        if by == "brand":
            for code in range(1, 15):
                rows.append(pct_row(acc_map.get(float(code), f"Model {code}"), sub[model_col] == code))
            # FIX (2026-06-19): this loop used to stop at RE's 14 codes —
            # but 'Brand Owned (Purchased Instead of RE)' is fundamentally
            # about what COMPETITORS they bought, which was entirely
            # missing. Mirrors live's pattern of brand rollup + member
            # models, grouped by manufacturer derived the same way
            # owned_manufacturer is (acc_map label's "BRAND - Model - cc"
            # prefix), for codes 15-123 (124 = catch-all 'Other').
            for manufacturer in self.manufacturers():
                if manufacturer == "Royal Enfield":
                    continue
                codes = sub.loc[sub[model_col].notna() & (sub['owned_manufacturer'] == manufacturer), model_col].unique()
                if len(codes) == 0:
                    continue
                rows.append(pct_row(manufacturer, sub[model_col].isin(codes)))
                for code in sorted(codes):
                    rows.append(pct_row(acc_map.get(float(code), f"Model {int(code)}"), sub[model_col] == code))
        else:  # CC-wise — real netting-sheet bucket scheme (same source as
            # Brand Considered's CC-wise), confirmed against the scraped
            # '150-199CC/200-249CC/250-350CC/351-500CC/501-650CC' labels —
            # the old RE_MODEL_PLATFORM + 'Competitor (CC unmapped)' version
            # never resolved any competitor model to a real CC bucket.
            cc_netting = self._aq5a_cc_netting()
            for bucket in sorted(set(cc_netting.values())):
                codes = [c for c, v in cc_netting.items() if v == bucket]
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
    def additional_replaced_table(self, df, by="brand", base_label="All", numeric=False):
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
        with open(DQ2_CODEBOOK_PATH, encoding='utf-8') as f:
            codebook = {int(k): v for k, v in json.load(f).items()}

        sub = df[df['dq1b'].notna()]
        base_n = len(sub)
        quarter_groups = self.quarter_combined_groups()
        extra_cols = list(quarter_groups.keys())
        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in MONTH_ORDER + extra_cols:
            rows[0][col] = len(self._col_index(sub, col, quarter_groups))

        def pct_row(label, mask):
            row = {"Unnamed: 0": label}
            for col in ["All"] + MONTH_ORDER + extra_cols:
                idx = self._col_index(sub, col, quarter_groups)
                sub_base = len(idx)
                val = mask.loc[idx].sum() / sub_base * 100 if sub_base else 0
                row[col] = val if numeric else f"{val:.0f}%"
            return row

        def model_mask(code):
            col = f"dq2a_{code}"
            return (sub[col] == 1) if col in sub.columns else pd.Series(False, index=sub.index)

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
                rows.append(pct_row(brand, brand_mask))
                for code in brand_codes:
                    mask = model_mask(code)
                    if mask.any():
                        rows.append(pct_row(codebook[code]['model'].title(), mask))
        else:  # CC-wise — cc_netting is the live site's own display bucketing
            cc_buckets = sorted({v['cc_netting'] for v in codebook.values() if v.get('cc_netting')})
            for bucket in cc_buckets:
                codes = [c for c, v in codebook.items() if v.get('cc_netting') == bucket]
                cols = [f"dq2a_{c}" for c in codes if f"dq2a_{c}" in sub.columns]
                mask = sub[cols].eq(1).any(axis=1) if cols else pd.Series(False, index=sub.index)
                label = f"{bucket} CC" if bucket[0].isdigit() else bucket
                rows.append(pct_row(label, mask))
        return pd.DataFrame(rows)

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
    def brand_considered_table(self, df, by="brand", base_label="All", numeric=False):
        base_n = len(df)
        acc_map = self.value_maps.get('acc', {})
        quarter_groups = self.quarter_combined_groups()
        extra_cols = list(quarter_groups.keys())

        rows = [{"Unnamed: 0": f"Base : Total_{base_label}", "All": base_n}]
        for col in MONTH_ORDER + extra_cols:
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
            for col in ["All"] + MONTH_ORDER + extra_cols:
                idx = self._col_index(df, col, quarter_groups)
                sub_base = len(idx)
                val = mask.loc[idx].sum() / sub_base * 100 if sub_base else 0
                row[col] = val if numeric else f"{val:.0f}%"
            return row

        rows.append(pct_row("RE", considered_mask(range(1, 15))))

        if by == "brand":
            for code in range(1, 15):
                rows.append(pct_row(acc_map.get(float(code), f"Model {code}"), considered_mask([code])))
            # FIX (2026-06-19): same gap as Brand Owned — only RE's 14 codes
            # were ever listed, no competitor brand rollups/models, even
            # though aq5a covers all 124 codes and live shows HONDA/TVS/
            # TRIUMPH/etc. rollups right after RE's.
            manufacturer_codes = {}
            for code in range(15, 124):
                label = acc_map.get(float(code), "")
                manufacturer = label.split(" - ")[0].strip() if " - " in label else label
                if manufacturer:
                    manufacturer_codes.setdefault(manufacturer, []).append(code)
            for manufacturer, codes in manufacturer_codes.items():
                rows.append(pct_row(manufacturer, considered_mask(codes)))
                for code in sorted(codes):
                    rows.append(pct_row(acc_map.get(float(code), f"Model {code}"), considered_mask([code])))
        else:  # CC-wise, using the real netting-sheet CC buckets
            cc_netting = self._aq5a_cc_netting()
            for bucket in sorted(set(cc_netting.values())):
                codes = [c for c, v in cc_netting.items() if v == bucket]
                rows.append(pct_row(f"{bucket}CC" if bucket[0].isdigit() else bucket, considered_mask(codes)))
        return pd.DataFrame(rows)

    def _aq5a_cc_netting(self):
        """Loads the real CC-bucket scheme for aq5a's 1-124 codes from the
        'Neeting for AQ3a_AQ5' sheet (no numeric code column there — codes
        are inferred from row order, confirmed to match acc/rej/can)."""
        net = pd.read_excel("data/Enroute_AP_V2_netting.xlsx", sheet_name="Neeting for AQ3a_AQ5", header=None)
        net = net.iloc[3:127].reset_index(drop=True)
        return {i + 1: str(net.iloc[i, 5]).strip() for i in range(len(net))}


if __name__ == "__main__":
    engine = DataEngine()
    engine.load_data()
    print("Segments:", engine.df['segment'].value_counts(dropna=False).to_dict())
    print(engine.age_table(engine.filter_df()).to_string())
