import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
import re
from textblob import TextBlob

# ==========================================
# 1. SYSTEM CONFIGURATION & CINEMATIC CSS
# ==========================================
st.set_page_config(page_title="DEFECTBOT // OS", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
[data-testid="stHeader"] { background-color: transparent !important; }
footer { visibility: hidden; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #020617; }
::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #38bdf8; }
.stApp { background-color: #020617 !important; background: radial-gradient(circle at 50% -20%, #0f172a 0%, #020617 100%) !important; color: #cbd5e1; font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-weight: 300 !important; letter-spacing: 2px; background: linear-gradient(90deg, #f8fafc 0%, #94a3b8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-transform: uppercase; }
.block-container { opacity: 1; animation: smoothEntry 0.8s forwards; }
@keyframes smoothEntry { 0% { transform: translateY(15px); opacity: 0.1; } 100% { transform: translateY(0); opacity: 1; } }
@keyframes criticalPulse { 0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.4); } 70% { box-shadow: 0 0 25px 8px rgba(220, 38, 38, 0); } 100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); } }
div[data-testid="metric-container"] { background: rgba(15, 23, 42, 0.4); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.05); border-top: 2px solid #0ea5e9; border-radius: 8px; padding: 24px; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5); transition: all 0.3s ease; }
div[data-testid="metric-container"]:hover { transform: translateY(-4px); background: rgba(15, 23, 42, 0.6); }
div[data-testid="metric-container"]:nth-child(2) { border-top: 2px solid #ef4444; animation: criticalPulse 3s infinite; }
.stDataFrame { border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05); box-shadow: 0 10px 30px -10px rgba(0,0,0,0.6); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THE INTELLIGENCE ENGINES
# ==========================================
CRITICAL_KEYWORDS = [
    r'\bFIRE\b', r'\bBILGE\b', r'\bGMDSS\b', r'\bRESCUE\b', r'\bSTEERING\b', 
    r'\bCOMPRESSOR\b', r'\bPURIFIER\b', r'\bLEAKING\b', r'\bALARM\b', r'\bINGRESS\b', 
    r'\bMAIN ENGINE\b', r'\bGENERATOR\b', r'\bLIFEBOAT\b', r'\bOWS\b', r'\bBOILER\b'
]

def apply_fuzzy_logic(df):
    compiled_regexes = [re.compile(kw) for kw in CRITICAL_KEYWORDS]
    def evaluate_row(desc):
        if pd.isna(desc): return 'NON-CRITICAL'
        desc_upper = str(desc).upper()
        for regex in compiled_regexes:
            if regex.search(desc_upper): return 'CRITICAL'
        return 'NON-CRITICAL'
    df['Tag'] = df['Case Description'].apply(evaluate_row)
    return df

def get_equipment_risk_profile(description):
    desc = str(description).upper()
    if any(kw in desc for kw in ['ENGINE', 'PROPULSION', 'GENERATOR', 'STEERING', 'BOILER']): return 0.35, 150000 
    elif any(kw in desc for kw in ['FIRE', 'RESCUE', 'LIFEBOAT', 'GMDSS']): return 0.45, 95000   
    elif any(kw in desc for kw in ['PUMP', 'COMPRESSOR', 'PURIFIER', 'VALVE', 'OWS']): return 0.25, 45000   
    elif any(kw in desc for kw in ['GALLEY', 'CABIN', 'LAUNDRY', 'AC']): return 0.05, 5000    
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
        try: sentiment_multiplier = 1.35 if TextBlob(str(row['Case Description'])).sentiment.polarity < -0.3 else 1.0
        except: sentiment_multiplier = 1.0
        
        weibull_array = np.clip(np.random.weibull(a=1.5, size=simulations) * base_loc, 0, 1)
        expected_loss = np.mean(weibull_array) * time_multiplier * sentiment_multiplier * base_cost
        risk_score = min(100, int((expected_loss / (base_cost * 0.6)) * 100))
        
        results.append({
            'Vessel': row.get('Vessel', 'Unknown'),
            'Case Ref': row['Case Reference'],
            'Description': row['Case Description'],
            'Days Open': int(days_open),
            'Risk Score (0-100)': risk_score,
            'Expected Loss ($)': expected_loss,
            'Recommendation': 'CRITICAL THREAT' if risk_score > 75 else ('DISP REQUIRED' if risk_score > 50 else 'MONITOR')
        })
    return pd.DataFrame(results).sort_values(by="Risk Score (0-100)", ascending=False)

# ==========================================
# 3. DATA INGESTION (HUNTER-SEEKER)
# ==========================================
@st.cache_data(show_spinner=False)
def process_uploaded_files(uploaded_files):
    df_list, integrity_log = [], []
    for file in uploaded_files:
        try:
            file_ext = os.path.splitext(file.name)[1].lower()
            if file_ext in ['.xlsx', '.xls']:
                engine = 'openpyxl' if file_ext == '.xlsx' else 'xlrd'
                all_sheets = pd.read_excel(file, sheet_name=None, header=None, engine=engine)
                for sheet_name, raw_df in all_sheets.items():
                    vessel_name = str(sheet_name).strip().upper()
                    if raw_df.empty: continue
                    header_row = -1
                    for idx, row in raw_df.head(20).iterrows():
                        row_str = ' '.join([str(val).upper() for val in row.values])
                        if 'CASE REF' in row_str and 'DESC' in row_str:
                            header_row = idx; break
                    if header_row == -1: continue
                    temp_df = raw_df.iloc[header_row + 1:].copy()
                    temp_df.columns = [str(c).strip() for c in raw_df.iloc[header_row].values]
                    ref_col = next((c for c in temp_df.columns if 'CASE REF' in str(c).upper()), None)
                    desc_col = next((c for c in temp_df.columns if 'DESC' in str(c).upper()), None)
                    if not ref_col or not desc_col: continue
                    temp_df.rename(columns={ref_col: 'Case Reference', desc_col: 'Case Description'}, inplace=True)
                    date_col = next((c for c in temp_df.columns if 'DUE DATE' in str(c).upper()), None)
                    if date_col: temp_df.rename(columns={date_col: 'Due Date'}, inplace=True)
                    init_date_col = next((c for c in temp_df.columns if 'INITIAL' in str(c).upper() and 'DATE' in str(c).upper()), None)
                    if init_date_col: temp_df.rename(columns={init_date_col: 'Date of Initial Reporting'}, inplace=True)
                    temp_df.dropna(subset=['Case Description'], inplace=True)
                    if temp_df.empty: continue
                    temp_df['Vessel'] = vessel_name
                    df_list.append(temp_df)
                    integrity_log.append({"Vessel": vessel_name, "Status": "SUCCESS"})
        except Exception: pass
    if not df_list: return pd.DataFrame(), pd.DataFrame(integrity_log)
    master_df = pd.concat(df_list, ignore_index=True)
    today = pd.Timestamp('today').normalize()
    if 'Due Date' in master_df.columns:
        master_df['Due Date'] = pd.to_datetime(master_df['Due Date'], errors='coerce')
        master_df['True Condition'] = 'PENDING'
        master_df.loc[master_df['Due Date'] < today, 'True Condition'] = 'OVERDUE'
    else: master_df['True Condition'] = 'UNKNOWN'
    if 'Date of Initial Reporting' in master_df.columns:
        master_df['Date of Initial Reporting'] = pd.to_datetime(master_df['Date of Initial Reporting'], errors='coerce')
    master_df = apply_fuzzy_logic(master_df)
    return master_df, pd.DataFrame(integrity_log)

# ==========================================
# 4. SECURE OS UI & ROUTING
# ==========================================
st.sidebar.markdown("<h3>DEFECTBOT // OS</h3>", unsafe_allow_html=True)
st.sidebar.caption("SYS.STATUS: CLOUD-NATIVE NODE")
uploaded_files = st.sidebar.file_uploader("UPLOAD TELEMETRY DATA", type=['xlsx', 'csv'], accept_multiple_files=True)
page = st.sidebar.radio("COMMAND MODULES", ["/// OVERVIEW", "/// ASSET DEEP-DIVE", "/// 3D SPATIAL MATRIX", "/// INTEGRITY LEDGER"])

if not uploaded_files:
    st.markdown("<h1 style='text-align: center; margin-top: 15vh;'>AWAITING TELEMETRY</h1>", unsafe_allow_html=True)
    st.stop()
master_df, integrity_df = process_uploaded_files(uploaded_files)
if master_df.empty: st.error("FAULT: ZERO VALID METRICS DETECTED."); st.stop()

# --- MODULE: OVERVIEW ---
if page == "/// OVERVIEW":
    st.markdown("<h2>FLEET COMMAND OVERVIEW</h2>", unsafe_allow_html=True)
    total_open = len(master_df)
    total_critical = len(master_df[master_df['Tag'] == 'CRITICAL'])
    total_overdue = len(master_df[master_df['True Condition'] == 'OVERDUE'])
    health_index = max(0, round(100 - (((total_critical * 1.5) + total_overdue) / total_open * 100), 1)) if total_open > 0 else 100
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ACTIVE LOGS", total_open)
    col2.metric("CRITICAL ANOMALIES", total_critical, delta_color="inverse")
    col3.metric("TEMPORAL BREACHES", total_overdue, delta_color="inverse")
    col4.metric("HEALTH INDEX", f"{health_index}%", "OPTIMAL" if health_index > 80 else "DEGRADED", delta_color="normal" if health_index > 80 else "inverse")
    
    st.markdown("<br>", unsafe_allow_html=True)
    col_chart1, col_chart2 = st.columns([1, 1.5])
    
    with col_chart1:
        st.markdown("<p style='color: #94a3b8; font-size: 0.85rem; letter-spacing: 1px;'>THREAT DISTRIBUTION</p>", unsafe_allow_html=True)
        donut_data = master_df['Tag'].value_counts().reset_index()
        donut_data.columns = ['Tag', 'Count']
        fig_donut = px.pie(donut_data, names='Tag', values='Count', hole=0.75, color='Tag', color_discrete_map={"CRITICAL": "#ef4444", "NON-CRITICAL": "#0ea5e9"})
        fig_donut.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False, margin=dict(t=10, b=10, l=10, r=10),
                                annotations=[dict(text=f"{total_critical}", x=0.5, y=0.5, font_size=48, font_family="Inter", font_color="#ef4444", showarrow=False)])
        fig_donut.update_traces(textinfo='percent+label', textfont_color="#cbd5e1", marker=dict(line=dict(color='#020617', width=3)))
        st.plotly_chart(fig_donut, use_container_width=True, config={'displayModeBar': False})

    with col_chart2:
        st.markdown("<p style='color: #94a3b8; font-size: 0.85rem; letter-spacing: 1px;'>ASSET VULNERABILITY MATRIX</p>", unsafe_allow_html=True)
        fig_bar = px.histogram(master_df, x="Vessel", color="Tag", color_discrete_map={"CRITICAL": "#ef4444", "NON-CRITICAL": "#0ea5e9"}, template="plotly_dark", barmode="stack").update_xaxes(categoryorder="total descending")
        fig_bar.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", hovermode="x unified", font=dict(family="Inter", color="#94a3b8"), xaxis=dict(showgrid=False, zeroline=False, title=""), yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False, title="VOLUME"), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=""), margin=dict(t=10, b=10, l=0, r=0))
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

    st.markdown("<p style='color: #ef4444; font-size: 0.85rem; letter-spacing: 2px;'> PRIORITY ACTION QUEUE</p>", unsafe_allow_html=True)
    critical_df = master_df[master_df['Tag'] == 'CRITICAL'].head(10)[['Vessel', 'Case Reference', 'Case Description', 'True Condition', 'Due Date']] if not master_df[master_df['Tag'] == 'CRITICAL'].empty else pd.DataFrame()
    if not critical_df.empty:
        if 'Due Date' in critical_df.columns: critical_df['Due Date'] = critical_df['Due Date'].dt.strftime('%Y-%m-%d').fillna('NO DATE')
        st.dataframe(critical_df.style.set_properties(**{'background-color': 'rgba(239, 68, 68, 0.05)', 'color': '#fca5a5', 'border-bottom': '1px solid rgba(239, 68, 68, 0.1)'}), use_container_width=True, hide_index=True)

# --- MODULE: ASSET DEEP-DIVE ---
elif page == "/// ASSET DEEP-DIVE":
    st.markdown("<h2>ASSET OPERATIONS</h2>", unsafe_allow_html=True)
    vessels = sorted(master_df['Vessel'].unique().tolist())
    selected = st.selectbox("SELECT ASSET", vessels)
    vessel_data = master_df[master_df['Vessel'] == selected]
    cols_to_show = ['Case Reference', 'Case Description']
    if 'Date of Initial Reporting' in master_df.columns: cols_to_show.append('Date of Initial Reporting')
    if 'Due Date' in master_df.columns: cols_to_show.append('Due Date')
    cols_to_show.extend(['True Condition', 'Tag'])
    
    def row_style(row): return ['background-color: rgba(220, 38, 38, 0.12); color: #fca5a5; font-weight: 500'] * len(row) if str(row.get('Tag', '')) == 'CRITICAL' or str(row.get('True Condition', '')) == 'OVERDUE' else [''] * len(row)
    try: styled_df = vessel_data[cols_to_show].style.apply(row_style, axis=1)
    except: styled_df = vessel_data[cols_to_show].style.applymap(row_style, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=550)

# --- MODULE: 3D SPATIAL MATRIX ---
elif page == "/// 3D SPATIAL MATRIX":
    st.markdown("<h2>WEIBULL STOCHASTIC ENGINE</h2>", unsafe_allow_html=True)
    st.caption("Executing Temporal & Sentiment-Modified Monte Carlo Projections in 3D Space.")
    
    sims = st.slider("MONTE CARLO ITERATIONS", 1000, 10000, 5000, 1000)
    with st.spinner('COMPUTING WEIBULL PROBABILITY MATRICES...'):
        risk_df = run_risk_simulation(master_df, simulations=sims)
    
    if not risk_df.empty:
        risk_df['Plot Size'] = risk_df['Risk Score (0-100)'].apply(lambda x: max(1, int(x)))
        fig_risk = px.scatter_3d(
            risk_df, x="Days Open", y="Risk Score (0-100)", z="Expected Loss ($)", color="Recommendation",
            hover_data=['Vessel', 'Description'], size="Plot Size", size_max=25,
            template="plotly_dark", color_discrete_map={"CRITICAL THREAT": "#ef4444", "DISP REQUIRED": "#f59e0b", "MONITOR": "#10b981"}
        )
        fig_risk.update_layout(
            scene=dict(
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", backgroundcolor="rgba(0,0,0,0)"),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", backgroundcolor="rgba(0,0,0,0)"),
                zaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", backgroundcolor="rgba(0,0,0,0)"),
            ),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#94a3b8"), margin=dict(l=0, r=0, b=0, t=0)
        )
        st.plotly_chart(fig_risk, use_container_width=True, config={'displayModeBar': False})
        
        display_df = risk_df.drop(columns=['Plot Size']).copy()
        display_df['Expected Loss ($)'] = display_df['Expected Loss ($)'].apply(lambda x: f"${int(x):,}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else: st.success("100% TEMPORAL COMPLIANCE. NO UNBOUNDED RISKS DETECTED.")

# --- MODULE: INTEGRITY LEDGER ---
elif page == "/// INTEGRITY LEDGER":
    st.markdown("<h2>DATA INTEGRITY LEDGER</h2>", unsafe_allow_html=True)
    st.dataframe(integrity_df, use_container_width=True, hide_index=True)
