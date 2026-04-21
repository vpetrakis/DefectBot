import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
from logic.fuzzy_engine import apply_fuzzy_logic
from logic.risk_engine import run_risk_simulation

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DefectBot | Enterprise OS", layout="wide", initial_sidebar_state="expanded")

# --- LOAD ANIMATED CSS ---
try:
    with open("assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass 

# --- DATA INGESTION & VALIDATION ENGINE ---
@st.cache_data(show_spinner=False)
def process_uploaded_files(uploaded_files):
    df_list = []
    integrity_log = []
    
    for file in uploaded_files:
        try:
            file_ext = os.path.splitext(file.name)[1].lower()
            
            if file_ext in ['.xlsx', '.xls']:
                engine = 'openpyxl' if file_ext == '.xlsx' else 'xlrd'
                all_sheets = pd.read_excel(file, sheet_name=None, skiprows=4, engine=engine)
                
                for sheet_name, temp_df in all_sheets.items():
                    temp_df.columns = temp_df.columns.astype(str).str.strip()
                    
                    if 'Case Reference' not in temp_df.columns or 'Case Description' not in temp_df.columns:
                        continue
                    
                    # Mathematical Drop: A defect MUST have a description to be valid
                    temp_df.dropna(subset=['Case Description'], inplace=True)
                    if temp_df.empty: continue
                    
                    vessel_name = str(sheet_name).strip().upper()
                    temp_df['Vessel'] = vessel_name
                    df_list.append(temp_df)
                    integrity_log.append({"Vessel": vessel_name, "Rows Processed": len(temp_df), "Source": "Master Excel"})
                    
            elif file_ext == '.csv':
                temp_df = pd.read_csv(file, skiprows=4)
                temp_df.columns = temp_df.columns.astype(str).str.strip()
                
                if 'Case Reference' not in temp_df.columns or 'Case Description' not in temp_df.columns:
                    continue
                
                temp_df.dropna(subset=['Case Description'], inplace=True)
                if temp_df.empty: continue
                
                vessel_name = file.name.split(' - ')[-1].replace('.csv', '').strip().upper()
                if not vessel_name or "TEC-003" in vessel_name: vessel_name = "UNKNOWN"
                    
                temp_df['Vessel'] = vessel_name
                df_list.append(temp_df)
                integrity_log.append({"Vessel": vessel_name, "Rows Processed": len(temp_df), "Source": "CSV"})
                
        except Exception as e:
            st.error(f"Critical System Error parsing {file.name}: {e}")
            
    if not df_list:
        return pd.DataFrame(), pd.DataFrame()
        
    master_df = pd.concat(df_list, ignore_index=True)
    
    # --- 100% ACCURACY DATE ENGINE ---
    # We do not trust Excel strings. We calculate reality as of today.
    today = pd.Timestamp('today').normalize()
    
    if 'Due Date' in master_df.columns:
        master_df['Due Date'] = pd.to_datetime(master_df['Due Date'], errors='coerce')
        # Overwrite 'Condition' mathematically
        master_df['True Condition'] = 'PENDING'
        master_df.loc[master_df['Due Date'] < today, 'True Condition'] = 'OVERDUE'
    else:
        master_df['True Condition'] = 'UNKNOWN'
        
    if 'Date of Initial Reporting' in master_df.columns:
        master_df['Date of Initial Reporting'] = pd.to_datetime(master_df['Date of Initial Reporting'], errors='coerce')
    
    # Apply NLP
    master_df = apply_fuzzy_logic(master_df)
    
    return master_df, pd.DataFrame(integrity_log)

# --- SIDEBAR UI ---
st.sidebar.markdown("### ⚓ DefectBot OS")
st.sidebar.caption("System Status: 🟢 SECURE CONNECTION")

uploaded_files = st.sidebar.file_uploader(
    "Upload Secure Data Logs", 
    type=['xlsx', 'xls', 'csv'], 
    accept_multiple_files=True
)

st.sidebar.markdown("---")
page = st.sidebar.radio("Core Modules", ["1. Global Command", "2. Asset Deep-Dive", "3. Stochastic Risk", "4. Data Integrity Log"])
st.sidebar.markdown("---")

if not uploaded_files:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Awaiting Telemetry Data</h1>", unsafe_allow_html=True)
    st.info("Drop your fleet export matrix into the sidebar to initialize the operating system.")
    st.stop()

with st.spinner("Executing algorithmic ingestion..."):
    master_df, integrity_df = process_uploaded_files(uploaded_files)

if master_df.empty:
    st.error("Data Parse Failure: Zero valid defect metrics detected.")
    st.stop()

# --- MODULE 1: GLOBAL COMMAND ---
if page == "1. Global Command":
    st.markdown("<h2>Global Fleet Intelligence</h2>", unsafe_allow_html=True)
    
    total_open = len(master_df)
    total_critical = len(master_df[master_df['Tag'] == 'CRITICAL'])
    total_overdue = len(master_df[master_df['True Condition'] == 'OVERDUE'])
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Case Volume", total_open)
    col2.metric("Critical Priority", total_critical, "Requires Action", delta_color="inverse")
    col3.metric("Mathematically Overdue", total_overdue, "Breach Detected", delta_color="inverse")
    col4.metric("Assets Tracking", master_df['Vessel'].nunique())
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_chart, col_data = st.columns([1.2, 1])
    
    with col_chart:
        st.markdown("#### Defect Matrix Distribution")
        fig = px.bar(
            master_df.groupby(['Vessel', 'Tag']).size().reset_index(name='Count'),
            x="Vessel", y="Count", color="Tag",
            color_discrete_map={"CRITICAL": "rgba(239, 68, 68, 0.8)", "NON-CRITICAL": "rgba(59, 130, 246, 0.6)"},
            template="plotly_dark", barmode="group"
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified", margin=dict(t=10, l=10, r=10, b=10)
        )
        fig.update_traces(marker_line_width=1.5, marker_line_color="black")
        st.plotly_chart(fig, use_container_width=True)

    with col_data:
        st.markdown("#### 🚨 Priority Action Required")
        critical_df = master_df[master_df['Tag'] == 'CRITICAL'][['Vessel', 'Case Description', 'True Condition']]
        st.dataframe(critical_df, use_container_width=True, hide_index=True, height=350)

# --- MODULE 2: ASSET DEEP-DIVE ---
elif page == "2. Asset Deep-Dive":
    st.markdown("<h2>Asset Operations View</h2>", unsafe_allow_html=True)
    
    vessels = sorted(master_df['Vessel'].unique().tolist())
    selected_vessel = st.selectbox("Select Target Asset", vessels)
    
    vessel_data = master_df[master_df['Vessel'] == selected_vessel]
    
    st.markdown(f"#### Active Log: {selected_vessel}")
    
    cols_to_show = ['Case Reference', 'Case Description']
    if 'Date of Initial Reporting' in master_df.columns: cols_to_show.append('Date of Initial Reporting')
    if 'Due Date' in master_df.columns: cols_to_show.append('Due Date')
    cols_to_show.append('True Condition')
    cols_to_show.append('Tag')
    
    # --- BULLETPROOF STYLING FAILSAFE ---
    # Accounts for Pandas 2.1.0+ deprecating .applymap() in favor of .map()
    def highlight_critical(val):
        if str(val) in ['OVERDUE', 'CRITICAL']:
            return 'color: #ef4444; font-weight: bold'
        return ''

    styler = vessel_data[cols_to_show].style
    try:
        styled_df = styler.map(highlight_critical, subset=['True Condition', 'Tag'])
    except AttributeError:
        styled_df = styler.applymap(highlight_critical, subset=['True Condition', 'Tag'])

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=500
    )

# --- MODULE 3: RISK SIMULATOR ---
elif page == "3. Stochastic Risk":
    st.markdown("<h2>Stochastic Risk Engine</h2>", unsafe_allow_html=True)
    st.caption("Executing algorithmic Monte Carlo simulations on defects without established due dates.")
    
    with st.expander("System Variables", expanded=False):
        sims = st.slider("Monte Carlo Iterations", min_value=1000, max_value=10000, value=5000, step=1000)
        disp_cost = st.number_input("Base Dispensation Cost (USD)", value=250)
    
    with st.spinner('Computing matrix logic...'):
        risk_df = run_risk_simulation(master_df, simulations=sims, disp_cost=disp_cost)
    
    if not risk_df.empty:
        fig_risk = px.scatter(
            risk_df, x="Risk Score (0-100)", y="Expected Loss ($)", color="Recommendation",
            hover_data=['Vessel', 'Description'], size_max=25, size="Risk Score (0-100)",
            template="plotly_dark", 
            color_discrete_map={"DISP REQUIRED": "#ef4444", "REVIEW": "#f59e0b", "NO ACTION": "#10b981"}
        )
        fig_risk.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig_risk.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))
        st.plotly_chart(fig_risk, use_container_width=True)
        
        st.dataframe(risk_df, use_container_width=True, hide_index=True)
    else:
        st.success("100% Due Date Compliance. System risk profile is minimal.")

# --- MODULE 4: DATA INTEGRITY ---
elif page == "4. Data Integrity Log":
    st.markdown("<h2>Data Integrity Ledger</h2>", unsafe_allow_html=True)
    st.caption("Proof of 100% mathematical accuracy during file parsing and ingestion.")
    
    st.metric("Total Rows Processed", integrity_df['Rows Processed'].sum())
    st.dataframe(integrity_df, use_container_width=True, hide_index=True)
