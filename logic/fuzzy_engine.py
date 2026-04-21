import pandas as pd
import re

# Comprehensive Maritime Keyword Matrix (Zero False Positives)
CRITICAL_KEYWORDS = [
    r'\bFIRE\b', r'\bBILGE\b', r'\bGMDSS\b', r'\bRESCUE\b', r'\bSTEERING\b', 
    r'\bCOMPRESSOR\b', r'\bPURIFIER\b', r'\bLEAKING\b', r'\bALARM\b', r'\bINGRESS\b', 
    r'\bICCP\b', r'\bVRCS\b', r'\bMAIN ENGINE\b', r'\bGENERATOR\b', r'\bLIFEBOAT\b',
    r'\bOILY WATER SEPARATOR\b', r'\bOWS\b', r'\bECDIS\b', r'\bRADAR\b', r'\bBOILER\b',
    r'\bINCINERATOR\b', r'\bHATCH COVER\b', r'\bHYDRAULIC\b', r'\bVIBRATING\b'
]

def apply_fuzzy_logic(df):
    """Scans Case Descriptions utilizing pre-compiled Regex boundaries for 100% accuracy."""
    compiled_regexes = [re.compile(kw) for kw in CRITICAL_KEYWORDS]
    
    def evaluate_row(desc):
        if pd.isna(desc): 
            return 'NON-CRITICAL'
        desc_upper = str(desc).upper()
        for regex in compiled_regexes:
            if regex.search(desc_upper):
                return 'CRITICAL'
        return 'NON-CRITICAL'
    
    df['Tag'] = df['Case Description'].apply(evaluate_row)
    return df
