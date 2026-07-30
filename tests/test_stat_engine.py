import pandas as pd
from utils.stat_engine import compare_to_baseline_by_column, calculate_significance


def _table(all_val, month_val, base_all=200, base_month=100):
    return pd.DataFrame([
        {"Unnamed: 0": "Base", "All": base_all, "Aug'2025": base_month},
        {"Unnamed: 0": "Cat A", "All": all_val, "Aug'2025": month_val},
    ])


def test_confidence_90_flags_a_90_tier_difference():
    # Chosen so |Z| lands in the 90% band (>=1.64) but below 95% (<1.95).
    # calculate_significance(0.25, 100, 0.15, 100) -> z ~= 1.78.
    tbl = _table(all_val=25, month_val=25, base_month=100)
    baseline = _table(all_val=15, month_val=15, base_month=100)
    markers_95 = compare_to_baseline_by_column(tbl, baseline, ["Aug'2025"], confidence=0.95)
    markers_90 = compare_to_baseline_by_column(tbl, baseline, ["Aug'2025"], confidence=0.90)
    # At 95%, a 90%-tier-only difference shows the light marker (△), not the
    # deep one (▲). At 90%, the same difference must show as significant.
    assert markers_95["Aug'2025"][0] in ("△", "▽", "")
    # At 90% mode there's no lower tier to show — anything clearing 90%
    # reads as the deep (confirmed) marker.
    assert markers_90["Aug'2025"][0] in ("▲", "▼")


def test_confidence_defaults_to_95_backward_compatible():
    tbl = _table(all_val=70, month_val=70, base_month=200)
    baseline = _table(all_val=30, month_val=30, base_month=200)
    # No confidence kwarg passed — must not raise, must behave as before.
    # Per the direction-asymmetric rule reverse-engineered from the live
    # site (2026-07-29): a "higher than baseline" difference never reaches
    # the deep 95% tier, no matter how large the gap — only the 90% marker.
    markers = compare_to_baseline_by_column(tbl, baseline, ["Aug'2025"])
    assert markers["Aug'2025"][0] == "△"
