import pandas as pd

def evaluate_conditions(df, model, platform):
    """
    Evaluates business conditions based on the processed dataframe.
    """
    df_filtered = df[(df['Model'] == model) & (df['Platform'] == platform)]
    
    flags = {
        'TECH_GAP': False,
        'WAIT_TIME_CRITICAL': False,
        'LOYALTY_LOCK_IN': False,
        'PRICE_SENSITIVITY': False,
        'LOW_CONFIDENCE': False
    }
    
    if df_filtered.empty:
        flags['LOW_CONFIDENCE'] = True
        return flags

    # Safeguard: LOW_CONFIDENCE if any Base size < 50
    # Look for metrics that indicate 'Base'
    base_rows = df_filtered[df_filtered['Metric'].str.contains('Base :', case=False, na=False)]
    if not base_rows.empty and any(base_rows['All_Avg'] < 50):
        flags['LOW_CONFIDENCE'] = True
    elif base_rows.empty:
        # If no base info found, we might want to flag it as well
        flags['LOW_CONFIDENCE'] = True

    # Rule 1: TECH_GAP (Reasons for rejection > 15% Technology)
    rejection_df = df_filtered[df_filtered['Table_Name'] == 'Reasons for rejection']
    tech_row = rejection_df[rejection_df['Metric'].str.contains('Technology', case=False, na=False)]
    if not tech_row.empty and tech_row['All_Avg'].iloc[0] > 15:
        flags['TECH_GAP'] = True

    # Rule 2: WAIT_TIME_CRITICAL (Reasons for rejection > 10% Waiting Period)
    wait_row = rejection_df[rejection_df['Metric'].str.contains('Waiting Period', case=False, na=False)]
    if not wait_row.empty and wait_row['All_Avg'].iloc[0] > 10:
        flags['WAIT_TIME_CRITICAL'] = True

    # Rule 3: LOYALTY_LOCK_IN (Brand Owned RE > 60%)
    brand_df = df_filtered[df_filtered['Table_Name'] == 'Brand Owned - Brand Wise']
    re_row = brand_df[brand_df['Metric'] == 'RE']
    if not re_row.empty and re_row['All_Avg'].iloc[0] > 60:
        flags['LOYALTY_LOCK_IN'] = True

    # Rule 4: PRICE_SENSITIVITY (Reasons for cancelling > 20% Overall price)
    cancelling_df = df_filtered[df_filtered['Table_Name'] == 'Reasons for cancelling']
    price_row = cancelling_df[cancelling_df['Metric'].str.contains('Overall price', case=False, na=False)]
    if not price_row.empty and price_row['All_Avg'].iloc[0] > 20:
        flags['PRICE_SENSITIVITY'] = True

    return flags

def get_logic_narrative(flags):
    """Converts logic flags into brief analytical bullet points."""
    narrative = []
    if flags["TECH_GAP"]:
        narrative.append("⚠️ **Tech Gap Alert**: Rejection data indicates significant feature-set parity risks (>15%).")
    if flags["WAIT_TIME_CRITICAL"]:
        narrative.append("🕒 **Supply Chain Friction**: Critical waiting period levels (>10%) are driving rejection.")
    if flags["LOYALTY_LOCK_IN"]:
        narrative.append("🔒 **Loyalty Lock-in**: Exceptionally high existing RE ownership (>60%) indicates a strong 'walled garden' effect.")
    if flags["PRICE_SENSITIVITY"]:
        narrative.append("💰 **Price Sensitivity**: Churn data shows pricing is a major barrier for cancellers (>20%).")
    
    if flags["LOW_CONFIDENCE"]:
        narrative.append("ℹ️ **Low Confidence**: Small sample size (Base < 50). Use these insights with caution.")
        
    if not narrative:
        narrative.append("✅ **Stable Baseline**: No critical logic violations detected in current data stream.")
        
    return narrative
