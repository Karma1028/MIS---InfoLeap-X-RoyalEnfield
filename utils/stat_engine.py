import numpy as np
import pandas as pd
from scipy.stats import norm

# Source of truth: data/95% CI_sig test.xls ("prop (3)" sheet).
# Reference cells: P1=62, P2=56, N1=390, N2=390 -> Sdiff=3.515533, Zvalue=1.706711
# (that reference used an UNPOOLED formula and landed in the 90% band).
#
# FORMULA SWITCHED TO POOLED (2026-07-29): reverse-engineered against 16 real
# highlight cells scraped from the live MIS site (Overview/Age table,
# n>=30 only, values + colors pulled directly from the page DOM, not
# guessed). Score per candidate formula, live-cell-color agreement:
#   unpooled, exact %              10/16
#   unpooled, rounded %            11/16
#   pooled,   exact %              14/16   <- this one
#   pooled,   rounded %            11/16
# The pooled formula also reproduces the one confirmed ground-truth
# reference case (P1=62,P2=56,N1=390,N2=390) into the same tier (90%,
# Z=1.7035 vs the documented 1.706711 -- same classification, formula
# gives a slightly different Z but the SAME confidence band), so nothing
# in the original reference is broken by this change.
#   pooled p = (p1*n1/100 + p2*n2/100) / (n1+n2)          [0-100 scale]
#   Sdiff    = sqrt( pooled_p*(100-pooled_p) * (1/n1+1/n2) )
#   Z        = (p1 - p2) / Sdiff
# 2 of 16 sampled cells still don't match under any tested formula variant
# (unpooled or pooled, rounded or exact) -- see project memory for the
# investigation trail; likely stale/pre-baked highlighting on their side
# rather than a formula we haven't found, since their site loads from
# separately-exported per-model static files, not a live query.
#
# Confidence tiers:
#   0.95 confidence -> Z >= 1.95   (rounded 1.96)
#   0.90 confidence -> Z in [1.64, 1.94]  (directional/lower-tier flag)
#
# DIRECTION ASYMMETRY:
# The live MIS site shows light green for ALL higher values (no dark tier for
# rises), and dark green for drops at z<=-1.95 only. Our app intentionally
# departs from that: per user requirement (2026-08-04) both tiers apply to
# HIGHER values too, so the full mapping is:
#   - value HIGHER than baseline:
#       z >= 1.95 → dark green (95%, ▲)
#       z in [1.64, 1.95) → light green (90%, △)
#   - value LOWER than baseline:
#       z <= -1.95 → dark green (95%, ▼)
#       z in (-1.95, -1.64] → nothing (no light tier for drops)
# Net: dark green = strongly significant in either direction; light green =
# directionally higher at 90% only.

Z_95 = 1.95
Z_90_LOW = 1.64
Z_90_HIGH = 1.94
# CORRECTED (2026-07-30): originally set to 1.2816 (one-tailed 90%) from a
# ~28-cell sample that never actually tested the 1.28-1.64 gap -- largest
# confirmed unflagged sample was Z=0.42, smallest confirmed flagged sample
# was Z=2.44, leaving that whole band unverified. Re-derived against exact
# (non-rounded) underlying proportions for Royal Enfield Classic 350's
# Education table: two cells sit inside that gap and are FALSELY flagged
# at 1.2816 but are plain/unhighlighted on the live site --
#   SSC/HSC Aug'25 (18% vs ALL 12.19%, n=60): Z=1.371
#   ProfGrad/PG Jan'26 (21% vs ALL 14.95%, n=66): Z=1.343
# All previously-confirmed true positives clear 1.64 with room to spare
# (Sept'25 ProfGrad Z=2.44, Feb'26 SSC/HSC Z=2.61, Apr'26 College-non-grad
# Z=2.49) -- so the light tier is two-tailed 90% (Z_90_LOW), same value
# already used for the old symmetric tiering, not a separate one-tailed cut.
Z_HIGHER_LIGHT = Z_90_LOW


def calculate_significance(p1, n1, p2, n2, confidence=0.95):
    """
    Calculates if the difference between two proportions (0-1 scale) is
    statistically significant, using a pooled-proportion two-sample Z-test
    (see module docstring above for why pooled, not unpooled).
    p1, p2 are proportions (0-1); internally converted to percentage scale
    to match the reference Excel formula's scale.
    """
    # Strict rule: never run significance testing on a base under 30 — too
    # unstable to report a meaningful difference.
    if n1 < 30 or n2 < 30:
        return {"is_significant": False, "z_score": 0.0, "tier": None}

pct1, pct2 = p1 * 100, p2 * 100
    pooled_pct = (pct1 * n1 + pct2 * n2) / (n1 + n2)
    sdiff = np.sqrt(pooled_pct * (100 - pooled_pct) * (1 / n1 + 1 / n2))

    if sdiff == 0:
        return {"is_significant": False, "z_score": 0.0, "tier": None}

    z_score = (pct1 - pct2) / sdiff

    # Asymmetric by direction -- see module docstring above.
    # Higher direction: dark (95%) at z>=1.95, light (90%) at z in [1.64, 1.95).
    # Lower direction: dark (95%) only at z<=-1.95, no light tier for drops.
    if z_score >= Z_95:
        tier = "95"
    elif z_score >= Z_HIGHER_LIGHT:
        tier = "90"
    elif z_score <= -Z_95:
        tier = "95"
    else:
        tier = None
    is_significant = tier is not None

    return {
        "is_significant": is_significant,
        "z_score": z_score,
        "tier": tier,
    }

def compare_to_baseline(table_df, baseline_df):
    """
    Per-category significance markers comparing the current filtered view
    (e.g. a segment + model + zone selection) against the unfiltered "All
    respondents" baseline — the "All vs Model" comparison required by
    MIS_Dashboard_Requirements.docx 5.3 ("Significance testing must be
    applied at all levels of selection... All vs. Model").
    Returns a list of marker strings (one per category row, excluding the
    Base row): '▲'/'▼' for 95% significant higher/lower, '△'/'▽' for the
    90% directional tier, '' otherwise.
    """
    base_n = table_df.iloc[0]['All']
    baseline_n = baseline_df.iloc[0]['All']
    markers = []
    for i in range(1, len(table_df)):
        label = table_df.iloc[i]['Unnamed: 0']
        p1 = float(table_df.iloc[i]['All']) / 100
        match = baseline_df[baseline_df['Unnamed: 0'] == label]
        if len(match) == 0 or table_df is baseline_df:
            markers.append('')
            continue
        p2 = float(match.iloc[0]['All']) / 100
        res = calculate_significance(p1, base_n, p2, baseline_n)
        if res['tier'] == '95':
            markers.append('▲' if res['z_score'] > 0 else '▼')
        elif res['tier'] == '90':
            markers.append('△' if res['z_score'] > 0 else '▽')
        else:
            markers.append('')
    return markers


def compare_to_baseline_by_column(table_df, baseline_df, columns, confidence=0.95, vs_own_all=False):
    """Per user request: 'significance testing should run month by month
    for a sample size equal or over 30 respondant' — testing only the
    aggregate 'All' column hides cases where a category is significant
    overall but not in a given month (or vice versa) because that month's
    sub-sample swings differently. Runs the same unpooled Z-test per
    category row, separately for EACH column in `columns` (typically
    ['All'] + the selected month labels), using THAT column's own base N
    (row 0 already carries a per-month n for every distribution_table()
    output) — so a month with n<30 on either side is skipped for that
    month only, not for the whole row.

    confidence: 0.95 (default) shows both the 95% tier (▲▼) and the 90%
    directional tier (△▽) together, exactly as before. 0.90 collapses to
    a single pass/fail at the 90% threshold — every category that clears
    90% (whether or not it also clears 95%) shows as the deep marker
    (▲▼), so switching the sidebar control to "90%" reads as "show me
    everything at or above 90%", not "show me only the 90-94% band".

    vs_own_all: per user request (2026-07-29, "select their methodology
    but only for sample >=30") — matches the live MIS site's own
    methodology, which tests each month column against that SAME table's
    'All' (aggregate) column, not against a separate baseline_df (e.g.
    other segments). When True, baseline_df is ignored for the p2/n2
    lookup; instead each row's own 'All' value/base is used as the
    comparison point. We keep our existing n>=30 gate (calculate_significance
    already enforces it) -- the live site has no such gate and will flag
    single-digit-base months as "significant", which we deliberately do
    not replicate.

    Returns {column: [markers...]} — one marker per category row (row 0/
    Base excluded), same '▲▼△▽'/'' vocabulary as compare_to_baseline().
    """
    same_population = (not vs_own_all) and table_df.equals(baseline_df)
    result = {}
    for col in columns:
        if col == 'All' and vs_own_all:
            # A column can't be tested against itself.
            continue
        if col not in table_df.columns or (not vs_own_all and col not in baseline_df.columns):
            continue
        n1 = float(table_df.iloc[0][col])
        n2 = float(table_df.iloc[0]['All']) if vs_own_all else float(baseline_df.iloc[0][col])
        markers = []
        for i in range(1, len(table_df)):
            label = table_df.iloc[i]['Unnamed: 0']
            src_df = table_df if vs_own_all else baseline_df
            match = src_df[src_df['Unnamed: 0'] == label]
            if same_population or len(match) == 0:
                markers.append('')
                continue
            p1 = float(table_df.iloc[i][col]) / 100
            p2 = float(match.iloc[0]['All' if vs_own_all else col]) / 100
            res = calculate_significance(p1, n1, p2, n2, confidence=confidence)
            if confidence >= 0.95:
                if res['tier'] == '95':
                    markers.append('▲' if res['z_score'] > 0 else '▼')
                elif res['tier'] == '90':
                    markers.append('△' if res['z_score'] > 0 else '▽')
                else:
                    markers.append('')
            else:
                # 90% mode: anything clearing the 90% bar reads as the
                # deep (confirmed) marker — there is no lower tier to show.
                if res['is_significant']:
                    markers.append('▲' if res['z_score'] > 0 else '▼')
                else:
                    markers.append('')
        result[col] = markers
    return result


def gaps_by_column(table_df, baseline_df, columns, vs_own_all=False):
    """Companion to compare_to_baseline_by_column() — per user request
    ("if one section is significant how much significant it is it should
    be shown"), a bare ▲/△ marker only said THAT a category was
    significantly higher, not BY HOW MUCH. Returns {column: [gap_pp,
    ...]} — gap_pp = this_value% - baseline_value% (percentage points),
    one per category row (row 0/Base excluded), same row-index alignment
    and label-matching as compare_to_baseline_by_column() so the two can
    be zipped together by the caller. None where no baseline match
    exists (same population, or the category doesn't appear in the
    baseline) — callers should only display the gap where a marker is
    also present, since a gap on a non-significant category is noise.

    vs_own_all: must match whatever was passed to the paired
    compare_to_baseline_by_column() call, or the gap values won't line up
    with what the markers actually tested against."""
    same_population = (not vs_own_all) and table_df.equals(baseline_df)
    result = {}
    for col in columns:
        if col == 'All' and vs_own_all:
            continue
        if col not in table_df.columns or (not vs_own_all and col not in baseline_df.columns):
            continue
        gaps = []
        for i in range(1, len(table_df)):
            label = table_df.iloc[i]['Unnamed: 0']
            src_df = table_df if vs_own_all else baseline_df
            match = src_df[src_df['Unnamed: 0'] == label]
            if same_population or len(match) == 0:
                gaps.append(None)
                continue
            p1 = float(table_df.iloc[i][col])
            p2 = float(match.iloc[0]['All' if vs_own_all else col])
            gaps.append(p1 - p2)
        result[col] = gaps
    return result


def apply_pairwise_significance(df, metric_col, base_col, col_id_map):
    """
    Applies A/B/C column-wise significance testing.
    df: DataFrame where rows are categories (e.g. Brands) and columns are dimensions (e.g. Zones)
    col_id_map: Dict mapping dimension names to letters e.g. {'North': 'A', 'South': 'B'}
    """
    # This is a complex operation that modifies the formatted strings
    # For MVP of the PBI dashboard, we'll return the formatted strings
    
    result_df = pd.DataFrame(index=df.index)
    columns = list(col_id_map.keys())
    
    for row_idx in df.index:
        for col_main in columns:
            if col_main not in df.columns or f"{col_main}_{base_col}" not in df.columns:
                continue
                
            p_main = df.loc[row_idx, col_main]
            n_main = df.loc[row_idx, f"{col_main}_{base_col}"]
            
            sig_letters = []
            
            for col_compare in columns:
                if col_main == col_compare: continue
                if col_compare not in df.columns or f"{col_compare}_{base_col}" not in df.columns:
                    continue
                    
                p_comp = df.loc[row_idx, col_compare]
                n_comp = df.loc[row_idx, f"{col_compare}_{base_col}"]
                
                res = calculate_significance(p_main, n_main, p_comp, n_comp)
                
                # If main is significantly HIGHER than compare, append compare's letter
                if res['is_significant'] and res['z_score'] > 0:
                    sig_letters.append(col_id_map[col_compare])
            
            # Format output: "45% A B"
            val_str = f"{p_main*100:.1f}%"
            if sig_letters:
                letters = "".join(sorted(sig_letters))
                val_str += f" <span class='sig-a'>{letters}</span>"
            
            result_df.loc[row_idx, col_main] = val_str
            
    return result_df

