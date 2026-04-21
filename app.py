import streamlit as st
import pandas as pd
import plotly.express as px
from logic.fuzzy_engine import apply_fuzzy_logic
from logic.risk_engine import run_risk_simulation

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="DefectsBot OS | Fleet Intelligence", page_icon="🚢", layout="wide")

# --- LOAD CSS ---
try:
    with open("assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass # Failsafe if CSS is missing

# --- DATA INGESTION FUNCTION ---
@st.cache_data(show_spinner=False)
def process_uploaded_files(uploaded_files):
    df_list = []
    for file in uploaded_files:
        try:
            # Read CSV and skip the first 4 rows containing metadata
            temp_df = pd.read_csv(file, skiprows=4)
            
            # Extract Vessel name from the uploaded filename
            # Example: "TEC-003 Defect Status Log 2026.xlsx - FALCON.csv" -> "FALCON"
            filename = file.name
            vessel_name = filename.split(' - ')[-1].replace('.csv', '').strip()
            if not vessel_name or "TEC-003" in vessel_name:
                vessel_name = "UNKNOWN_VESSEL"
                
            temp_df['Vessel'] = vessel_name
            df_list.append(temp_df)
        except Exception as e:
            st.error(f"Error processing {file.name}: {e}")
            
    if not df_list:
        return pd.DataFrame()
        
    master_df = pd.concat(df_list, ignore_index=True)
    master_df.dropna(subset=['Case Reference', 'Case Description'], how='all', inplace=True)
    
    # Format dates
    master_df['Due Date'] = pd.to_datetime(master_df['Due Date'], errors='coerce')
    master_df['Date of Initial Reporting'] = pd.to_datetime(master_df['Date of Initial Reporting'], errors='coerce')
    
    # Apply logic engine
    master_df = apply_fuzzy_logic(master_df)
    return master_df

# --- SIDEBAR & UPLOADER ---
st.sidebar.title("DefectsBot OS 🚢")

# The Drag and Drop Zone
uploaded_files = st.sidebar.file_uploader(
    "Upload TEC-003 CSV Files", 
    type=['csv'], 
    accept_multiple_files=True,
    help="Drag and drop your vessel export CSVs here."
)

st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", ["Global Fleet Dashboard", "Vessel Deep-Dive", "Dispensation Risk Simulator"])
st.sidebar.markdown("---")

# --- INITIAL STATE CHECK ---
if not uploaded_files:
    st.title("Welcome to DefectsBot OS")
    st.info("👈 Please drag and drop your exported Vessel CSV files into the sidebar to initialize the dashboard.")
    st.stop()

# Process files if uploaded
with st.spinner("Aggregating fleet data..."):
    master_df = process_uploaded_files(uploaded_files)

if master_df.empty:
    st.error("Uploaded files contained no valid defect data. Please check the format.")
    st.stop()

# --- PAGE 1: GLOBAL DASHBOARD ---
if page == "Global Fleet Dashboard":
    st.title("🌐 Global Fleet Intelligence")
    
    # Top-Level Metrics
    total_open = len(master_df)
    total_critical = len(master_df[master_df['Tag'] == 'CRITICAL'])
    total_overdue = len(master_df[master_df['Condition'].str.contains('OVERDUE', na=False)])
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Open Defects", total_open)
    col2.metric("Critical Priority", total_critical, delta="Requires Attention", delta_color="inverse")
    col3.metric("Overdue Items", total_overdue, delta="Breach", delta_color="inverse")
    col4.metric("Active Vessels", master_df['Vessel'].nunique())
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Visualizations & Triage
    col_chart, col_data = st.columns([1.2, 1])
    
    with col_chart:
        st.subheader("Defect Volume by Vessel")
        fig = px.histogram(
            master_df, x="Vessel", color="Tag", 
            color_discrete_map={"CRITICAL": "#FF4B4B", "NON-CRITICAL": "#00A9FF"},
            template="plotly_dark", barmode="group"
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col_data:
        st.subheader("🚨 Critical Action Items")
        critical_df = master_df[master_df['Tag'] == 'CRITICAL'][['Vessel', 'Case Description', 'Condition']]
        st.dataframe(critical_df, use_container_width=True, hide_index=True)

# --- PAGE 2: VESSEL DEEP-DIVE ---
elif page == "Vessel Deep-Dive":
    st.title("⚓ Vessel Operations View")
    
    vessels = sorted(master_df['Vessel'].unique().tolist())
    selected_vessel = st.selectbox("Select Vessel", vessels)
    
    vessel_data = master_df[master_df['Vessel'] == selected_vessel]
    
    st.write(f"### Live Roster: {selected_vessel}")
    st.dataframe(
        vessel_data[['Case Reference', 'Case Description', 'Date of Initial Reporting', 'Condition', 'Tag']],
        use_container_width=True,
        hide_index=True
    )

# --- PAGE 3: RISK SIMULATOR ---
elif page == "Dispensation Risk Simulator":
    st.title("🎲 Stochastic Risk Engine")
    st.caption("Running algorithmic Monte Carlo simulations on defects missing due dates.")
    
    with st.expander("⚙️ Simulation Settings", expanded=False):
        sims = st.slider("Monte Carlo Iterations", min_value=1000, max_value=10000, value=5000, step=1000)
        disp_cost = st.number_input("Base Dispensation Cost ($)", value=250)
    
    with st.spinner('Computing matrix logic...'):
        risk_df = run_risk_simulation(master_df, simulations=sims, disp_cost=disp_cost)
    
    if not risk_df.empty:
        fig_risk = px.scatter(
            risk_df, x="Risk Score (0-100)", y="Expected Loss ($)", color="Recommendation",
            hover_data=['Vessel', 'Description'], size_max=20, size="Risk Score (0-100)",
            template="plotly_dark", 
            color_discrete_map={"🔴 DISP REQUIRED": "#FF4B4B", "🟡 REVIEW": "#FFA500", "🟢 NO ACTION": "#00CC96"}
        )
        fig_risk.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_risk, use_container_width=True)
        
        st.dataframe(risk_df, use_container_width=True, hide_index=True)
    else:
        st.success("✅ All logged defects currently have assigned due dates. System risk profile is minimal.")
