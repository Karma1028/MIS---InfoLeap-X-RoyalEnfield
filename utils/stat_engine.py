import numpy as np
import pandas as pd
from scipy.stats import norm

# Source of truth: data/95% CI_sig test.xls ("prop (3)" sheet).
# Reference cells: P1=62, P2=56, N1=390, N2=390 -> Sdiff=3.515533, Zvalue=1.706711.
# This is an UNPOOLED two-proportion Z-test on the 0-100 percentage scale
# (not the textbook pooled-proportion test). Reproduced exactly below:
#   Sdiff = sqrt( p1*(100-p1)/n1 + p2*(100-p2)/n2 )      [p1,p2 in 0-100]
#   Z     = (p1 - p2) / Sdiff
# Their reference sheet also lists a two-tier critical-Z band:
#   0.95 confidence -> Z >= 1.95   (rounded 1.96)
#   0.90 confidence -> Z in [1.64, 1.94]  (directional/lower-tier flag)

Z_95 = 1.95
Z_90_LOW = 1.64
Z_90_HIGH = 1.94


def calculate_significance(p1, n1, p2, n2, confidence=0.95):
    """
    Calculates if the difference between two proportions (0-1 scale) is
    statistically significant, using the agency's unpooled-SE formula.
    p1, p2 are proportions (0-1); internally converted to percentage scale
    to match the reference Excel formula exactly.
    """
    # Strict rule: never run significance testing on a base under 30 — too
    # unstable to report a meaningful difference.
    if n1 < 30 or n2 < 30:
        return {"is_significant": False, "z_score": 0.0, "tier": None}

    pct1, pct2 = p1 * 100, p2 * 100
    sdiff = np.sqrt((pct1 * (100 - pct1)) / n1 + (pct2 * (100 - pct2)) / n2)

    if sdiff == 0:
        return {"is_significant": False, "z_score": 0.0, "tier": None}

    z_score = (pct1 - pct2) / sdiff
    abs_z = abs(z_score)

    if confidence >= 0.95:
        tier = "95" if abs_z >= Z_95 else ("90" if Z_90_LOW <= abs_z <= Z_90_HIGH else None)
        is_significant = abs_z >= Z_95
    else:
        tier = "90" if abs_z >= Z_90_LOW else None
        is_significant = abs_z >= Z_90_LOW

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
        if len(match) == 0 or base_n == baseline_n:
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


def compare_to_baseline_by_column(table_df, baseline_df, columns):
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
    Returns {column: [markers...]} — one marker per category row (row 0/
    Base excluded), same '▲▼△▽'/'' vocabulary as compare_to_baseline().
    """
    same_population = table_df.equals(baseline_df)
    result = {}
    for col in columns:
        if col not in table_df.columns or col not in baseline_df.columns:
            continue
        n1 = float(table_df.iloc[0][col])
        n2 = float(baseline_df.iloc[0][col])
        markers = []
        for i in range(1, len(table_df)):
            label = table_df.iloc[i]['Unnamed: 0']
            match = baseline_df[baseline_df['Unnamed: 0'] == label]
            if same_population or len(match) == 0:
                markers.append('')
                continue
            p1 = float(table_df.iloc[i][col]) / 100
            p2 = float(match.iloc[0][col]) / 100
            res = calculate_significance(p1, n1, p2, n2)
            if res['tier'] == '95':
                markers.append('▲' if res['z_score'] > 0 else '▼')
            elif res['tier'] == '90':
                markers.append('△' if res['z_score'] > 0 else '▽')
            else:
                markers.append('')
        result[col] = markers
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

