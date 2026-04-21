import numpy as np
import pandas as pd

def get_equipment_risk_profile(description):
    """Dynamically assigns failure probabilities and baseline costs based on NLP context."""
    desc = str(description).upper()
    
    if any(kw in desc for kw in ['ENGINE', 'PROPULSION', 'GENERATOR', 'STEERING', 'BOILER']):
        return 0.35, 120000  # High exposure, catastrophic cost
    elif any(kw in desc for kw in ['FIRE', 'RESCUE', 'LIFEBOAT', 'GMDSS', 'ECDIS']):
        return 0.40, 80000   # Critical safety, severe port state risk
    elif any(kw in desc for kw in ['PUMP', 'COMPRESSOR', 'PURIFIER', 'VALVE', 'OWS']):
        return 0.20, 35000   # Standard operational machinery
    elif any(kw in desc for kw in ['GALLEY', 'CABIN', 'LAUNDRY', 'AC', 'LIGHTING']):
        return 0.05, 5000    # Low impact hotel services
    else:
        return 0.15, 25000   # Fleet standard baseline

def run_risk_simulation(df, simulations=5000, disp_cost=250):
    """Vectorized Stochastic Monte Carlo Engine."""
    if 'Due Date' not in df.columns:
        return pd.DataFrame()
        
    nodue_df = df[df['Due Date'].isna()].copy()
    if nodue_df.empty:
        return pd.DataFrame()
        
    results = []
    for _, row in nodue_df.iterrows():
        # Fetch dynamic parameters instead of hardcoded numbers
        base_loc, base_cost = get_equipment_risk_profile(row['Case Description'])
        
        # Execute Monte Carlo Matrix
        base_risk_array = np.random.normal(loc=base_loc, scale=0.05, size=simulations)
        base_risk_array = np.clip(base_risk_array, 0, 1) 
        
        expected_loss = np.mean(base_risk_array) * base_cost
        
        # Normalize score
        risk_score = min(100, int((expected_loss / (base_cost * 0.5)) * 100))
        
        results.append({
            'Vessel': row.get('Vessel', 'Unknown'),
            'Case Ref': row['Case Reference'],
            'Description': row['Case Description'],
            'Risk Score (0-100)': risk_score,
            'Expected Loss ($)': f"${int(expected_loss):,}",
            'Recommendation': 'DISP REQUIRED' if risk_score > 60 else ('REVIEW' if risk_score > 30 else 'NO ACTION')
        })
        
    return pd.DataFrame(results).sort_values(by="Risk Score (0-100)", ascending=False)
