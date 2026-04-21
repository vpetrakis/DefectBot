import streamlit as st
import pandas as pd
import plotly.express as px
import os
from logic.fuzzy_engine import apply_fuzzy_logic
from logic.risk_engine import run_risk_simulation

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DefectBot | Fleet Intelligence", layout="wide")

# --- LOAD CSS ---
try:
    with open("assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass 

# --- DATA INGESTION FUNCTION ---
@st.cache_data(show_spinner=False)
def process_uploaded_files(uploaded_files):
    df_list = []
    for file in uploaded_files:
        try:
            file_ext = os.path.splitext(file.name)[1].lower()
            
            # Dynamically handle Excel vs CSV with explicit engines
            if file_ext == '.xlsx':
                temp_df = pd.read_excel(file, skiprows=4, engine='openpyxl')
            elif file_ext == '.xls':
                temp_df = pd.read_excel(file, skiprows=4, engine='xlrd')
            elif file_ext == '.csv':
                temp_df = pd.read_csv(file, skiprows=4)
            else:
                continue
            
            filename = file.name
            vessel_name = filename.split(' - ')[-1].replace('.csv', '').replace('.xlsx', '').replace('.xls', '').strip()
            if not vessel_name or "TEC-003" in vessel_name:
                vessel_name = "UNKNOWN_VESSEL"
                
            temp_df['Vessel'] = vessel_name
            df_list.append(temp_df)
        except Exception as e:
            st.error(f"System Error parsing {file.name}: {e}")
            
    if not df_list:
        return pd.DataFrame()
        
    master_df = pd.concat(df_list, ignore_index=True)
    
    # --- THE BULLETPROOF FIX ---
    # Strip all leading/trailing whitespace from column headers
    master_df.columns = master_df.columns.str.strip()
    
    master_df.dropna(subset=['Case Reference', 'Case Description'], how='all', inplace=True)
    
    # Safely convert dates if columns exist
    if 'Due Date' in master_df.columns:
        master_df['Due Date'] = pd.to_datetime(master_df['Due Date'], errors='coerce')
    if 'Date of Initial Reporting' in master_df.columns:
        master_df['Date of Initial Reporting'] = pd.to_datetime(master_df['Date of Initial Reporting'], errors='coerce')
    
    master_df = apply_fuzzy_logic(master_df)
    return master_df

# --- SIDEBAR & UPLOADER ---
st.sidebar.title("DefectBot")

uploaded_files = st.sidebar.file_uploader(
    "Upload Status Logs", 
    type=['xlsx', 'xls', 'csv'], 
    accept_multiple_files=True,
    help="Drag and drop your Excel or CSV vessel export files here."
)

st.sidebar.markdown("---")
page = st.sidebar.radio("Module Navigation", ["Global Fleet Dashboard", "Vessel Deep-Dive", "Dispensation Risk Simulator"])
st.sidebar.markdown("---")

# --- INITIAL STATE CHECK ---
if not uploaded_files:
    st.title("DefectBot Intelligence")
    st.info("Awaiting Data: Please upload fleet export files via the sidebar to initialize the dashboard.")
    st.stop()

with st.spinner("Compiling fleet data arrays..."):
    master_df = process_uploaded_files(uploaded_files)

if master_df.empty:
    st.error("Data Parse Failure: Uploaded files contained no valid defect metrics.")
    st.stop()

# --- PAGE 1: GLOBAL DASHBOARD ---
if page == "Global Fleet Dashboard":
    st.title("Global Fleet Intelligence")
    
    total_open = len(master_df)
    total_critical = len(master_df[master_df['Tag'] == 'CRITICAL'])
    
    # Safely check condition column
    total_overdue = 0
    if 'Condition' in master_df.columns:
        total_overdue = len(master_df[master_df['Condition'].str.contains('OVERDUE', na=False)])
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Open Defects", total_open)
    col2.metric("Critical Priority", total_critical)
    col3.metric("Overdue Items", total_overdue)
    col4.metric("Active Vessels", master_df['Vessel'].nunique())
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_chart, col_data = st.columns([1.2, 1])
    
    with col_chart:
        st.subheader("Defect Volume Distribution")
        fig = px.histogram(
            master_df, x="Vessel", color="Tag", 
            color_discrete_map={"CRITICAL": "#D32F2F", "NON-CRITICAL": "#1976D2"},
            template="plotly_dark", barmode="group"
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col_data:
        st.subheader("Critical Action Required")
        cols_to_show = ['Vessel', 'Case Description']
        if 'Condition' in master_df.columns:
            cols_to_show.append('Condition')
            
        critical_df = master_df[master_df['Tag'] == 'CRITICAL'][cols_to_show]
        st.dataframe(critical_df, use_container_width=True, hide_index=True)

# --- PAGE 2: VESSEL DEEP-DIVE ---
elif page == "Vessel Deep-Dive":
    st.title("Vessel Operations View")
    
    vessels = sorted(master_df['Vessel'].unique().tolist())
    selected_vessel = st.selectbox("Select Asset", vessels)
    
    vessel_data = master_df[master_df['Vessel'] == selected_vessel]
    
    st.write(f"### Active Case Log: {selected_vessel}")
    
    cols_to_show = ['Case Reference', 'Case Description']
    if 'Date of Initial Reporting' in master_df.columns: cols_to_show.append('Date of Initial Reporting')
    if 'Condition' in master_df.columns: cols_to_show.append('Condition')
    cols_to_show.append('Tag')
    
    st.dataframe(
        vessel_data[cols_to_show],
        use_container_width=True,
        hide_index=True
    )

# --- PAGE 3: RISK SIMULATOR ---
elif page == "Dispensation Risk Simulator":
    st.title("Stochastic Risk Engine")
    st.caption("Executing algorithmic Monte Carlo simulations on defects without established due dates.")
    
    with st.expander("Simulation Parameters", expanded=False):
        sims = st.slider("Monte Carlo Iterations", min_value=1000, max_value=10000, value=5000, step=1000)
        disp_cost = st.number_input("Base Dispensation Cost (USD)", value=250)
    
    with st.spinner('Computing matrix logic...'):
        risk_df = run_risk_simulation(master_df, simulations=sims, disp_cost=disp_cost)
    
    if not risk_df.empty:
        fig_risk = px.scatter(
            risk_df, x="Risk Score (0-100)", y="Expected Loss ($)", color="Recommendation",
            hover_data=['Vessel', 'Description'], size_max=20, size="Risk Score (0-100)",
            template="plotly_dark", 
            color_discrete_map={"DISP REQUIRED": "#D32F2F", "REVIEW": "#F57C00", "NO ACTION": "#388E3C"}
        )
        fig_risk.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_risk, use_container_width=True)
        
        st.dataframe(risk_df, use_container_width=True, hide_index=True)
    else:
        st.success("All logged defects currently possess assigned due dates. System risk profile is minimal.")
