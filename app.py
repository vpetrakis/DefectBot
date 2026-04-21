import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime
from logic.fuzzy_engine import apply_fuzzy_logic
from logic.risk_engine import run_risk_simulation

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DEFECTBOT // OS", layout="wide", initial_sidebar_state="expanded")

# --- LOAD ANIMATED CSS ---
try:
    with open("assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass 

# --- DYNAMIC INGESTION & VALIDATION ENGINE ---
@st.cache_data(show_spinner=False)
def process_uploaded_files(uploaded_files):
    df_list = []
    integrity_log = []
    
    for file in uploaded_files:
        try:
            file_ext = os.path.splitext(file.name)[1].lower()
            
            if file_ext in ['.xlsx', '.xls']:
                engine = 'openpyxl' if file_ext == '.xlsx' else 'xlrd'
                
                # Load raw without skipping rows to dynamically hunt for headers
                all_sheets = pd.read_excel(file, sheet_name=None, header=None, engine=engine)
                
                for sheet_name, raw_df in all_sheets.items():
                    vessel_name = str(sheet_name).strip().upper()
                    
                    if raw_df.empty:
                        integrity_log.append({"Vessel": vessel_name, "Status": "SKIPPED: Blank Sheet", "Rows Extracted": 0})
                        continue
                        
                    # --- HUNTER-SEEKER ALGORITHM ---
                    # Scan the first 20 rows to find the actual table header
                    header_row = -1
                    for idx, row in raw_df.head(20).iterrows():
                        row_str = ' '.join(row.astype(str).str.upper())
                        if 'CASE REF' in row_str and 'DESC' in row_str:
                            header_row = idx
                            break
                            
                    if header_row == -1:
                        integrity_log.append({"Vessel": vessel_name, "Status": "SKIPPED: No Defect Table Found", "Rows Extracted": 0})
                        continue
                        
                    # Reconstruct DataFrame precisely from the located header
                    temp_df = raw_df.iloc[header_row + 1:].copy()
                    temp_df.columns = raw_df.iloc[header_row].astype(str).str.strip()
                    
                    # Fuzzy Column Mapping (Immune to slight misspellings or spaces)
                    ref_col = next((c for c in temp_df.columns if 'CASE REF' in c.upper()), None)
                    desc_col = next((c for c in temp_df.columns if 'DESC' in c.upper()), None)
                    
                    if not ref_col or not desc_col:
                        integrity_log.append({"Vessel": vessel_name, "Status": "SKIPPED: Corrupted Columns", "Rows Extracted": 0})
                        continue
                        
                    # Standardize names for the master system
                    temp_df.rename(columns={ref_col: 'Case Reference', desc_col: 'Case Description'}, inplace=True)
                    
                    date_col = next((c for c in temp_df.columns if 'DUE DATE' in c.upper()), None)
                    if date_col: temp_df.rename(columns={date_col: 'Due Date'}, inplace=True)
                    
                    cond_col = next((c for c in temp_df.columns if 'COND' in c.upper()), None)
                    if cond_col: temp_df.rename(columns={cond_col: 'Condition'}, inplace=True)
                    
                    init_date_col = next((c for c in temp_df.columns if 'INITIAL' in c.upper() and 'DATE' in c.upper()), None)
                    if init_date_col: temp_df.rename(columns={init_date_col: 'Date of Initial Reporting'}, inplace=True)
                    
                    # Drop rows that don't actually contain a description
                    temp_df.dropna(subset=['Case Description'], inplace=True)
                    if temp_df.empty:
                        integrity_log.append({"Vessel": vessel_name, "Status": "SKIPPED: Table empty of descriptions", "Rows Extracted": 0})
                        continue
                    
                    temp_df['Vessel'] = vessel_name
                    df_list.append(temp_df)
                    integrity_log.append({"Vessel": vessel_name, "Status": "SUCCESS: Active Data", "Rows Extracted": len(temp_df)})
                    
            elif file_ext == '.csv':
                # Similar dynamic hunting logic can be applied, but CSVs are usually flat.
                # Kept standard for CSV fallback.
                temp_df = pd.read_csv(file, skiprows=4)
                temp_df.columns = temp_df.columns.astype(str).str.strip()
                if 'Case Reference' in temp_df.columns and 'Case Description' in temp_df.columns:
                    temp_df.dropna(subset=['Case Description'], inplace=True)
                    vessel_name = file.name.split(' - ')[-1].replace('.csv', '').strip().upper()
                    if not vessel_name or "TEC-003" in vessel_name: vessel_name = "UNKNOWN"
                    temp_df['Vessel'] = vessel_name
                    df_list.append(temp_df)
                    integrity_log.append({"Vessel": vessel_name, "Status": "SUCCESS: Active Data (CSV)", "Rows Extracted": len(temp_df)})
                
        except Exception as e:
            st.error(f"CRITICAL FAULT parsing {file.name}: {e}")
            
    if not df_list:
        return pd.DataFrame(), pd.DataFrame(integrity_log)
        
    master_df = pd.concat(df_list, ignore_index=True)
    
    # Mathematical Date Engine
    today = pd.Timestamp('today').normalize()
    if 'Due Date' in master_df.columns:
        master_df['Due Date'] = pd.to_datetime(master_df['Due Date'], errors='coerce')
        master_df['True Condition'] = 'PENDING'
        master_df.loc[master_df['Due Date'] < today, 'True Condition'] = 'OVERDUE'
    else:
        master_df['True Condition'] = 'UNKNOWN'
        
    if 'Date of Initial Reporting' in master_df.columns:
        master_df['Date of Initial Reporting'] = pd.to_datetime(master_df['Date of Initial Reporting'], errors='coerce')
    
    master_df = apply_fuzzy_logic(master_df)
    return master_df, pd.DataFrame(integrity_log)

# --- SIDEBAR UI ---
st.sidebar.markdown("<h3 style='color: #38bdf8; letter-spacing: 2px;'>DEFECTBOT // OS</h3>", unsafe_allow_html=True)
st.sidebar.caption("SYS.STATUS: ONLINE // SECURE")

uploaded_files = st.sidebar.file_uploader(
    "UPLOAD TELEMETRY DATA", 
    type=['xlsx', 'xls', 'csv'], 
    accept_multiple_files=True
)

st.sidebar.markdown("---")
page = st.sidebar.radio("COMMAND MODULES", [
    "/// GLOBAL COMMAND", 
    "/// ASSET DEEP-DIVE", 
    "/// STOCHASTIC RISK", 
    "/// INTEGRITY LOG"
])
st.sidebar.markdown("---")

if not uploaded_files:
    st.markdown("<h1 style='text-align: center; margin-top: 15vh; font-weight: 300; color: #475569;'>AWAITING TELEMETRY</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b;'>Establish connection by uploading fleet matrix to the secure node.</p>", unsafe_allow_html=True)
    st.stop()

with st.spinner("EXECUTING HUNTER-SEEKER INGESTION..."):
    master_df, integrity_df = process_uploaded_files(uploaded_files)

if master_df.empty:
    st.error("FAULT: ZERO VALID METRICS DETECTED. CHECK INTEGRITY LOG.")
    if not integrity_df.empty:
        st.dataframe(integrity_df, use_container_width=True)
    st.stop()

# --- MODULE 1: GLOBAL COMMAND ---
if page == "/// GLOBAL COMMAND":
    st.markdown("<h2>GLOBAL FLEET OVERVIEW</h2>", unsafe_allow_html=True)
    
    total_open = len(master_df)
    total_critical = len(master_df[master_df['Tag'] == 'CRITICAL'])
    total_overdue = len(master_df[master_df['True Condition'] == 'OVERDUE'])
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ACTIVE LOGS", total_open)
    col2.metric("CRITICAL PRIORITY", total_critical, "IMMEDIATE ACTION", delta_color="inverse")
    col3.metric("MATHEMATICALLY OVERDUE", total_overdue, "PROTOCOL BREACH", delta_color="inverse")
    col4.metric("ASSETS ONLINE", master_df['Vessel'].nunique())
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_chart, col_data = st.columns([1.4, 1])
    
    with col_chart:
        st.markdown("<p style='color: #94a3b8; font-size: 0.9rem; letter-spacing: 1px;'>DISTRIBUTION MATRIX</p>", unsafe_allow_html=True)
        fig = px.bar(
            master_df.groupby(['Vessel', 'Tag']).size().reset_index(name='Count'),
            x="Vessel", y="Count", color="Tag",
            color_discrete_map={"CRITICAL": "#ef4444", "NON-CRITICAL": "#0ea5e9"},
            template="plotly_dark", barmode="group"
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified", font=dict(family="Inter", color="#94a3b8"),
            xaxis=dict(showgrid=False, zeroline=False, title=""),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False, title="VOLUME")
        )
        fig.update_traces(marker_line_width=0, opacity=0.9)
        st.plotly_chart(fig, use_container_width=True)

    with col_data:
        st.markdown("<p style='color: #ef4444; font-size: 0.9rem; letter-spacing: 1px;'>PRIORITY ACTION QUEUE</p>", unsafe_allow_html=True)
        critical_df = master_df[master_df['Tag'] == 'CRITICAL'][['Vessel', 'Case Description', 'True Condition']]
        st.dataframe(critical_df, use_container_width=True, hide_index=True, height=380)

# --- MODULE 2: ASSET DEEP-DIVE ---
elif page == "/// ASSET DEEP-DIVE":
    st.markdown("<h2>ASSET OPERATIONS</h2>", unsafe_allow_html=True)
    
    vessels = sorted(master_df['Vessel'].unique().tolist())
    selected_vessel = st.selectbox("SELECT TARGET ASSET", vessels)
    
    vessel_data = master_df[master_df['Vessel'] == selected_vessel]
    st.markdown(f"<p style='color: #38bdf8; font-family: JetBrains Mono;'>[ SYSTEM QUERY: {selected_vessel} ]</p>", unsafe_allow_html=True)
    
    cols_to_show = ['Case Reference', 'Case Description']
    if 'Date of Initial Reporting' in master_df.columns: cols_to_show.append('Date of Initial Reporting')
    if 'Due Date' in master_df.columns: cols_to_show.append('Due Date')
    cols_to_show.append('True Condition')
    cols_to_show.append('Tag')
    
    def cinematic_row_style(row):
        is_critical = str(row.get('Tag', '')) == 'CRITICAL'
        is_overdue = str(row.get('True Condition', '')) == 'OVERDUE'
        if is_critical or is_overdue:
            return ['background-color: rgba(220, 38, 38, 0.15); color: #fca5a5; font-weight: 500'] * len(row)
        return [''] * len(row)

    styler = vessel_data[cols_to_show].style
    try:
        styled_df = styler.apply(cinematic_row_style, axis=1)
    except AttributeError:
        styled_df = styler.applymap(cinematic_row_style, axis=1)

    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=550)

# --- MODULE 3: RISK SIMULATOR ---
elif page == "/// STOCHASTIC RISK":
    st.markdown("<h2>STOCHASTIC RISK ENGINE</h2>", unsafe_allow_html=True)
    st.caption("EXECUTING MONTE CARLO PROJECTIONS ON UNBOUNDED DEFECTS.")
    
    col_ctrl, col_space = st.columns([1, 2])
    with col_ctrl:
        sims = st.slider("MONTE CARLO ITERATIONS", min_value=1000, max_value=10000, value=5000, step=1000)
        disp_cost = st.number_input("BASE DISPENSATION COST (USD)", value=250)
    
    with st.spinner('COMPUTING PROBABILITY MATRICES...'):
        risk_df = run_risk_simulation(master_df, simulations=sims, disp_cost=disp_cost)
    
    if not risk_df.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        fig_risk = px.scatter(
            risk_df, x="Risk Score (0-100)", y="Expected Loss ($)", color="Recommendation",
            hover_data=['Vessel', 'Description'], size_max=25, size="Risk Score (0-100)",
            template="plotly_dark", 
            color_discrete_map={"DISP REQUIRED": "#ef4444", "REVIEW": "#f59e0b", "NO ACTION": "#10b981"}
        )
        fig_risk.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#94a3b8"),
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
        )
        fig_risk.update_traces(marker=dict(line=dict(width=0), opacity=0.85))
        st.plotly_chart(fig_risk, use_container_width=True)
        
        st.dataframe(risk_df, use_container_width=True, hide_index=True)
    else:
        st.success("100% TEMPORAL COMPLIANCE. NO UNBOUNDED RISKS DETECTED.")

# --- MODULE 4: DATA INTEGRITY ---
elif page == "/// INTEGRITY LOG":
    st.markdown("<h2>DATA INTEGRITY LEDGER</h2>", unsafe_allow_html=True)
    st.caption("MATHEMATICAL PROOF OF ALGORITHMIC INGESTION PER NODE.")
    
    st.metric("TOTAL VECTORS PROCESSED", integrity_df['Rows Extracted'].sum())
    
    # Conditional formatting to show SUCCESS vs SKIPPED
    def log_styler(row):
        if 'SUCCESS' in str(row.get('Status', '')):
            return ['color: #10b981; font-family: JetBrains Mono'] * len(row)
        return ['color: #ef4444; font-family: JetBrains Mono; font-weight: bold'] * len(row)

    try:
        styled_log = integrity_df.style.apply(log_styler, axis=1)
    except Exception:
        styled_log = integrity_df
        
    st.dataframe(styled_log, use_container_width=True, hide_index=True, height=600)
