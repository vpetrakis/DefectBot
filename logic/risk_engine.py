import numpy as np
import pandas as pd

def run_risk_simulation(df, simulations=5000, disp_cost=250):
    """Runs a Monte Carlo simulation on defects with no Due Date."""
    nodue_df = df[df['Due Date'].isna()].copy()
    if nodue_df.empty:
        return pd.DataFrame()
        
    results = []
    for _, row in nodue_df.iterrows():
        # Monte Carlo simulation array processing
        base_risk_array = np.random.normal(loc=0.18, scale=0.05, size=simulations)
        base_risk_array = np.clip(base_risk_array, 0, 1) 
        
        expected_loss = np.mean(base_risk_array) * 45000
        risk_score = min(100, int((expected_loss / 20000) * 100))
        
        results.append({
            'Vessel': row.get('Vessel', 'Unknown'),
            'Case Ref': row['Case Reference'],
            'Description': row['Case Description'],
            'Risk Score (0-100)': risk_score,
            'Expected Loss ($)': f"${int(expected_loss):,}",
            'Recommendation': '🔴 DISP REQUIRED' if risk_score > 60 else ('🟡 REVIEW' if risk_score > 30 else '🟢 NO ACTION')
        })
        
    return pd.DataFrame(results).sort_values(by="Risk Score (0-100)", ascending=False)
