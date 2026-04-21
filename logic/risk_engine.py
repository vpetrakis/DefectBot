import numpy as np
import pandas as pd
from textblob import TextBlob

def get_sentiment_multiplier(text):
    try:
        polarity = TextBlob(str(text)).sentiment.polarity
        if polarity < -0.3: return 1.35
        if polarity < 0.0: return 1.15
        return 1.0
    except:
        return 1.0

def get_equipment_risk_profile(description):
    desc = str(description).upper()
    if any(kw in desc for kw in ['ENGINE', 'PROPULSION', 'GENERATOR', 'STEERING', 'BOILER']): return 0.35, 150000 
    elif any(kw in desc for kw in ['FIRE', 'RESCUE', 'LIFEBOAT', 'GMDSS', 'ECDIS']): return 0.45, 95000   
    elif any(kw in desc for kw in ['PUMP', 'COMPRESSOR', 'PURIFIER', 'VALVE', 'OWS']): return 0.25, 45000   
    elif any(kw in desc for kw in ['GALLEY', 'CABIN', 'LAUNDRY', 'AC', 'LIGHTING']): return 0.05, 5000    
    else: return 0.15, 30000   

def run_risk_simulation(df, simulations=5000):
    if 'Due Date' not in df.columns or 'Date of Initial Reporting' not in df.columns: return pd.DataFrame()
    nodue_df = df[df['Due Date'].isna()].copy()
    if nodue_df.empty: return pd.DataFrame()
        
    today = pd.Timestamp('today').normalize()
    results = []
    
    for _, row in nodue_df.iterrows():
        base_loc, base_cost = get_equipment_risk_profile(row['Case Description'])
        try: days_open = max(0, (today - pd.to_datetime(row['Date of Initial Reporting'])).days)
        except: days_open = 0
            
        time_multiplier = 1.0 + ((days_open / 15.0) * 0.05)
        sentiment_multiplier = get_sentiment_multiplier(row['Case Description'])
        
        weibull_array = np.random.weibull(a=1.5, size=simulations) * base_loc
        weibull_array = np.clip(weibull_array, 0, 1)
        
        final_probability = np.mean(weibull_array) * time_multiplier * sentiment_multiplier
        expected_loss = final_probability * base_cost
        risk_score = min(100, int((expected_loss / (base_cost * 0.6)) * 100))
        
        results.append({
            'id': str(row['Case Reference']), # Required for React keys
            'Vessel': row.get('Vessel', 'Unknown'),
            'Case Ref': row['Case Reference'],
            'Description': row['Case Description'],
            'Days Open': int(days_open),
            'Risk Score': risk_score,
            'Expected Loss': int(expected_loss),
            'Recommendation': 'CRITICAL THREAT' if risk_score > 75 else ('DISP REQUIRED' if risk_score > 50 else 'MONITOR')
        })
        
    return pd.DataFrame(results).sort_values(by="Risk Score", ascending=False)
