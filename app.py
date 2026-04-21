import streamlit as st
import pandas as pd
import plotly.express as px
import os
from logic.fuzzy_engine import apply_fuzzy_logic
from logic.risk_engine import run_risk_simulation
from spatial_matrix import spatial_risk_matrix

st.set_page_config(page_title="DEFECTBOT // OS", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
[data-testid="stHeader"] { background-color: transparent !important; }
footer { visibility: hidden; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #020617; }
::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
.stApp { background-color: #020617 !important; color: #cbd5e1; font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-weight: 300 !important; letter-spacing: 2px; background: linear-gradient(90deg, #f8fafc 0%, #94a3b8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-transform: uppercase; }
.block-container { opacity: 1; animation: smoothEntry 0.8s forwards; }
@keyframes smoothEntry { 0% { transform: translateY(15px); opacity: 0.1; } 100% { transform: translateY(0); opacity: 1; } }
div[data-testid="metric-container"] { background: rgba(15, 23, 42, 0.4); border-top: 2px solid #0ea5e9; border-radius: 8px; padding: 24px; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5); }
div[data-testid="metric-container"]:nth-child(2) { border-top: 2px solid #ef4444; }
.stDataFrame { border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05); }
</style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def process_uploaded_files(uploaded_files):
    df_list = []
    integrity_log = []
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
    master_df = apply_fuzzy_logic(master_df)
    return master_df, pd.DataFrame(integrity_log)

st.sidebar.markdown("<h3>DEFECTBOT // OS</h3>", unsafe_allow_html=True)
uploaded_files = st.sidebar.file_uploader("UPLOAD TELEMETRY DATA", type=['xlsx', 'csv'], accept_multiple_files=True)
page = st.sidebar.radio("COMMAND MODULES", ["/// OVERVIEW", "/// ASSET DEEP-DIVE", "/// REACT SPATIAL MATRIX"])

if not uploaded_files: st.stop()
master_df, _ = process_uploaded_files(uploaded_files)

if page == "/// OVERVIEW":
    st.markdown("<h2>FLEET COMMAND OVERVIEW</h2>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    col1.metric("ACTIVE LOGS", len(master_df))
    col2.metric("CRITICAL ANOMALIES", len(master_df[master_df['Tag'] == 'CRITICAL']), delta_color="inverse")
    st.dataframe(master_df[['Vessel', 'Case Reference', 'Case Description', 'Tag']], use_container_width=True)

elif page == "/// ASSET DEEP-DIVE":
    vessels = sorted(master_df['Vessel'].unique().tolist())
    selected = st.selectbox("SELECT ASSET", vessels)
    st.dataframe(master_df[master_df['Vessel'] == selected], use_container_width=True)

# --- THE REACT BRIDGE EXECUTION ---
elif page == "/// REACT SPATIAL MATRIX":
    st.markdown("<h2>60FPS SPATIAL FLUID MATRIX</h2>", unsafe_allow_html=True)
    st.caption("Custom React.js rendering engine bridging with Python backend.")
    
    risk_df = run_risk_simulation(master_df, simulations=2000)
    if not risk_df.empty:
        # Convert Pandas to JSON for React
        json_data = risk_df.to_dict(orient="records")
        
        # Fire the React Component
        user_action = spatial_risk_matrix(data_json=json_data, key="react_matrix")
        
        # Bi-Directional Response: Python reacting to React!
        if user_action and user_action.get('action') == 'inspect':
            st.warning(f" OS COMMAND INTERCEPTED: Superintendent requesting deep inspection of {user_action['vessel']} (Ref: {user_action['ref']}).")
