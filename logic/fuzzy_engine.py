import pandas as pd

CRITICAL_KEYWORDS = [
    'FIRE', 'BILGE', 'GMDSS', 'RESCUE', 'STEERING', 
    'COMPRESSOR', 'PURIFIER', 'LEAKING', 'ALARM', 'INGRESS', 'ICCP', 'VRCS'
]

def apply_fuzzy_logic(df):
    """Scans Case Descriptions and tags them based on critical keywords."""
    def evaluate_row(desc):
        if pd.isna(desc): 
            return 'NON-CRITICAL'
        
        desc_upper = str(desc).upper()
        for kw in CRITICAL_KEYWORDS:
            if kw in desc_upper:
                return 'CRITICAL'
        return 'NON-CRITICAL'
    
    df['Tag'] = df['Case Description'].apply(evaluate_row)
    return df
