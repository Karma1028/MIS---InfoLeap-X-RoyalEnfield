"""Pre-compute all dashboard metrics as a structured JSON snapshot.

Produces data/dashboard_data.json with shape:
{
  "meta": { "generated_at": ..., "months": [...], "segments": [...] },
  "segments": {
    "Acceptor": {
      "all_months": { <kpis + distributions> },
      "by_month": {
        "August'2025": { <same shape> },
        ...
      }
    },
    "Rejector": { ... },
    "Cancelled": { ... },
    "All": { ... }
  }
}

Each metrics block:
  base_n, avg_age, avg_age_source,
  age_dist, education_dist, income_dist, occupation_dist,
  ftb_pct, ftb_n,
  top_income_bracket, top_income_pct,
  top_edu_bracket, top_edu_pct
"""
import json
import math
from datetime import datetime

import pandas as pd


_AGE_MIDPOINTS = {1.0: 21.5, 2.0: 30.5, 3.0: 40.5, 4.0: 50.0}


def _mean_age(df):
    if 'age_numeric' in df.columns:
        vals = pd.to_numeric(df['age_numeric'], errors='coerce').dropna()
        if len(vals):
            return float(vals.mean()), 'dq7_raw'
    if 'age_grp' in df.columns:
        v = df['age_grp'].map(_AGE_MIDPOINTS).mean()
        if not math.isnan(v):
            return float(v), 'midpoint_estimate'
    return None, None


def _dist(df, col, value_map):
    """Return {label: pct} dict for a coded column."""
    s = pd.to_numeric(df[col], errors='coerce').dropna() if col in df.columns else pd.Series(dtype=float)
    if s.empty:
        return {}
    counts = s.map(value_map).value_counts()
    total = counts.sum()
    return {str(k): round(v / total * 100, 1) for k, v in counts.items() if k and str(k) != 'nan'}


def _ftb(df):
    if 'dq1a' not in df.columns:
        return None, None
    mask = pd.to_numeric(df['dq1a'], errors='coerce').isin([3.0, 4.0])
    n = int(mask.sum())
    base = int(df['dq1a'].notna().sum())
    pct = round(n / base * 100, 1) if base else None
    return pct, n


def _top_row(tbl, month_cols):
    """Highest-value non-Base row across all months combined ('All' column)."""
    data_rows = tbl[~tbl['Unnamed: 0'].astype(str).str.startswith('Base')]
    if data_rows.empty:
        return None, None
    try:
        idx = data_rows['All'].astype(float).idxmax()
        row = data_rows.loc[idx]
        return str(row['Unnamed: 0']), round(float(row['All']), 1)
    except Exception:
        return None, None


def _tbl_to_dist(tbl, month=None):
    """Convert a distribution table to {label: pct} for a given month or All."""
    col = month if (month and month in tbl.columns) else 'All'
    data_rows = tbl[~tbl['Unnamed: 0'].astype(str).str.startswith('Base')]
    out = {}
    for _, row in data_rows.iterrows():
        try:
            out[str(row['Unnamed: 0'])] = round(float(row[col]), 1)
        except Exception:
            pass
    return out


def _metrics_for(engine, df, month=None):
    """Compute full metrics block for a filtered df (already scoped to segment+month if needed)."""
    base_n = len(df)
    if base_n == 0:
        return {"base_n": 0}

    avg_age, age_src = _mean_age(df)

    # Age distribution from age_grp value_map
    age_vm = engine.value_maps.get('age_grp', _AGE_MIDPOINTS)
    age_dist = _dist(df, 'age_grp', age_vm)

    # Age bucket counts
    age_counts = {}
    if 'age_grp' in df.columns:
        for code, label in age_vm.items():
            n = int((pd.to_numeric(df['age_grp'], errors='coerce') == code).sum())
            if n:
                age_counts[str(label)] = n

    # Education, Income, Occupation via engine tables
    try:
        edu_tbl = engine.education_table(df, numeric=True)
        edu_dist = _tbl_to_dist(edu_tbl)
        top_edu, top_edu_pct = _top_row(edu_tbl, [])
    except Exception:
        edu_dist, top_edu, top_edu_pct = {}, None, None

    try:
        inc_tbl = engine.household_income_table(df, numeric=True)
        inc_dist = _tbl_to_dist(inc_tbl)
        top_inc, top_inc_pct = _top_row(inc_tbl, [])
    except Exception:
        inc_dist, top_inc, top_inc_pct = {}, None, None

    try:
        occ_tbl = engine.occupation_table(df, numeric=True)
        occ_dist = _tbl_to_dist(occ_tbl)
    except Exception:
        occ_dist = {}

    ftb_pct, ftb_n = _ftb(df)

    return {
        "base_n": base_n,
        "avg_age": avg_age,
        "avg_age_source": age_src,
        "age_distribution_pct": age_dist,
        "age_distribution_n": age_counts,
        "education_distribution_pct": edu_dist,
        "top_education_bracket": top_edu,
        "top_education_pct": top_edu_pct,
        "income_distribution_pct": inc_dist,
        "top_income_bracket": top_inc,
        "top_income_pct": top_inc_pct,
        "occupation_distribution_pct": occ_dist,
        "ftb_pct": ftb_pct,
        "ftb_n": ftb_n,
    }


def build_dashboard_json(engine, out_path="data/dashboard_data.json"):
    """Compute all metrics and write JSON snapshot. Returns the dict."""
    SEGMENTS = {
        "All": None,
        "Acceptor": "Acceptor",
        "Rejector": "Rejector",
        "Cancelled": "Cancelled",
    }
    months = list(engine.month_order)

    result = {
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "months": months,
            "segments": list(SEGMENTS.keys()),
            "age_source_note": (
                "avg_age uses dq7 (raw numeric age in years) when available; "
                "falls back to age_grp bracket midpoints otherwise."
            ),
        },
        "segments": {},
    }

    for seg_label, seg_value in SEGMENTS.items():
        df_all = engine.filter_df(segment=seg_value) if seg_value else engine.filter_df()

        seg_block = {
            "all_months": _metrics_for(engine, df_all),
            "by_month": {},
        }

        for m in months:
            df_m = df_all[df_all['month_label'] == m]
            if len(df_m) == 0:
                continue
            seg_block["by_month"][m] = _metrics_for(engine, df_m, month=m)

        result["segments"][seg_label] = seg_block

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
