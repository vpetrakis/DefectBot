import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
import re
import networkx as nx
import traceback

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
.stApp { background-color: #020617 !important; background: radial-gradient(circle at 50% -20%, #0f172a 0%, #020617 100%) !important; color: #cbd5e1; font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-weight: 300 !important; letter-spacing: 2px; background: linear-gradient(90deg, #f8fafc 0%, #94a3b8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-transform: uppercase; }
.block-container { opacity: 1; animation: smoothEntry 0.8s forwards; }
@keyframes smoothEntry { 0% { transform: translateY(15px); opacity: 0.1; } 100% { transform: translateY(0); opacity: 1; } }
div[data-testid="metric-container"] { background: rgba(15, 23, 42, 0.4); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.05); border-top: 2px solid #0ea5e9; border-radius: 8px; padding: 24px; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5); }
div[data-testid="metric-container"]:nth-child(2) { border-top: 2px solid #ef4444; }
.stDataFrame { border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THE SHIP ONTOLOGY & NETWORKX LOGIC
# ==========================================
def build_vessel_topology():
    G = nx.DiGraph()
    G.add_nodes_from(["DG1", "DG2", "MAIN_SWITCHBOARD", "ME_COOLING", "MAIN_ENGINE", "PROPULSION", "STEERING", "ISOLATED"])
    G.add_edges_from([
        ("DG1", "MAIN_SWITCHBOARD"),
        ("DG2", "MAIN_SWITCHBOARD"),
        ("MAIN_SWITCHBOARD", "ME_COOLING"),
        ("MAIN_SWITCHBOARD", "STEERING"),
        ("ME_COOLING", "MAIN_ENGINE"),
        ("MAIN_ENGINE", "PROPULSION")
    ])
    return G

def assign_system_node(description):
    desc = str(description).upper()
    if any(kw in desc for kw in ['DG1', 'GEN 1', 'GENERATOR 1']): return "DG1"
    if any(kw in desc for kw in ['DG2', 'GEN 2', 'GENERATOR 2']): return "DG2"
    if any(kw in desc for kw in ['SWITCHBOARD', 'MSB', 'POWER']): return "MAIN_SWITCHBOARD"
    if any(kw in desc for kw in ['COOLING', 'JACKET WATER']): return "ME_COOLING"
    if any(kw in desc for kw in ['MAIN ENGINE', 'M/E']): return "MAIN_ENGINE"
    if any(kw in desc for kw in ['PROPULSION', 'SHAFT', 'PROPELLER']): return "PROPULSION"
    if any(kw in desc for kw in ['STEERING', 'RUDDER']): return "STEERING"
    return "ISOLATED"

def get_urgency_multiplier(description):
    """Replaces TextBlob with native, unbreakable Python keyword scanning."""
    desc = str(description).upper()
    urgent_words = ['URGENT', 'SEVERE', 'CRITICAL', 'IMMEDIATE', 'DANGER', 'FAILING', 'HEAVY LEAK']
    if any(word in desc for word in urgent_words): return 1.35
    return 1.0

# ==========================================
# 3. WEIBULL STOCHASTIC ENGINE
# ==========================================
def run_risk_simulation(df, G, simulations=2000):
    if df.empty: return pd.DataFrame()
    today = pd.Timestamp('today').normalize()
    results = []
    
    for _, row in df.iterrows():
        try:
            desc = str(row.get('Case Description', 'Unknown')).upper()
            base_loc = 0.35 if any(k in desc for k in ['ENGINE', 'PROPULSION', 'STEERING']) else 0.15
            base_cost = 150000 if base_loc == 0.35 else 30000
            
            # Safe Date Math
            try: days_open = max(0, (today - pd.to_datetime(row.get('Date of Initial Reporting', today))).days)
            except: days_open = 0
                
            time_multiplier = 1.0 + ((days_open / 15.0) * 0.05)
            urgency_multiplier = get_urgency_multiplier(desc)
            
            # Base Weibull Math
            weibull_array = np.clip(np.random.weibull(a=1.5, size=simulations) * base_loc, 0, 1)
            expected_loss = np.mean(weibull_array) * time_multiplier * urgency_multiplier * base_cost
            base_risk_score = (expected_loss / (base_cost * 0.6)) * 100
            
            # CASCADING LOGIC
            system_node = row.get('System Node', 'ISOLATED')
            cascading_threats = ""
            final_risk_score = base_risk_score
            
            if system_node in G.nodes and system_node != 'ISOLATED':
                victims = list(nx.descendants(G, system_node))
                if victims:
                    final_risk_score *= 1.45
                    cascading_threats = f"⚠️ THREATENS: {', '.join(victims)}"
            
            final_risk_score = min(100, int(final_risk_score))
            
            results.append({
                'Vessel': row.get('Vessel', 'Unknown'),
                'Case Ref': str(row.get('Case Reference', 'N/A')),
                'Description': str(row.get('Case Description', 'N/A')),
                'System Node': system_node,
                'Days Open': int(days_open),
                'Risk Score': final_risk_score,
                'Cascading Impact': cascading_threats,
                'Recommendation': 'CRITICAL THREAT' if final_risk_score > 75 else ('DISP REQUIRED' if final_risk_score > 50 else 'MONITOR')
            })
        except Exception as e:
            st.error(f"Error processing row: {e}")
            continue
            
    return pd.DataFrame(results).sort_values(by="Risk Score", ascending=False)

# ==========================================
# 4. DATA INGESTION (HUNTER-SEEKER)
# ==========================================
def process_uploaded_files(uploaded_files):
    df_list = []
    for file in uploaded_files:
        try:
            file_ext = os.path.splitext(file.name)[1].lower()
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
                init_date_col = next((c for c in temp_df.columns if 'INITIAL' in str(c).upper() and 'DATE' in str(c).upper()), None)
                if init_date_col: temp_df.rename(columns={init_date_col: 'Date of Initial Reporting'}, inplace=True)
                
                temp_df.dropna(subset=['Case Description'], inplace=True)
                temp_df['Vessel'] = vessel_name
                df_list.append(temp_df)
        except Exception as e:
            st.warning(f"Could not read file {file.name}. Ensure it is a valid Excel file.")
            continue
            
    if not df_list: return pd.DataFrame()
    
    master_df = pd.concat(df_list, ignore_index=True)
    master_df['System Node'] = master_df['Case Description'].apply(assign_system_node)
    return master_df

# ==========================================
# 5. SECURE OS UI & ROUTING
# ==========================================
st.sidebar.markdown("<h3>DEFECTBOT // OS</h3>", unsafe_allow_html=True)
st.sidebar.caption("SYS.STATUS: ARMORED MONOLITH")
uploaded_files = st.sidebar.file_uploader("UPLOAD TELEMETRY DATA", type=['xlsx', 'csv'], accept_multiple_files=True)

if not uploaded_files:
    st.markdown("<h1 style='text-align: center; margin-top: 15vh;'>AWAITING TELEMETRY</h1>", unsafe_allow_html=True)
    st.stop()

# --- ARMORED EXECUTION BLOCK ---
try:
    master_df = process_uploaded_files(uploaded_files)
    
    if master_df.empty: 
        st.error("FAULT: ZERO VALID METRICS DETECTED. Please check your Excel column headers.")
        st.stop()

    G = build_vessel_topology()
    risk_df = run_risk_simulation(master_df, G, simulations=2000)

    page = st.sidebar.radio("COMMAND MODULES", ["/// COMBINATORIAL OVERVIEW", "/// 3D SPATIAL MATRIX"])

    if page == "/// COMBINATORIAL OVERVIEW":
        st.markdown("<h2>FLEET THREAT OVERVIEW</h2>", unsafe_allow_html=True)
        total_open = len(risk_df)
        total_critical = len(risk_df[risk_df['Recommendation'] == 'CRITICAL THREAT'])
        total_cascading = len(risk_df[risk_df['Cascading Impact'] != ""])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("ACTIVE LOGS", total_open)
        col2.metric("CRITICAL ANOMALIES", total_critical, delta_color="inverse")
        col3.metric("SYNERGISTIC THREATS", total_cascading, help="Defects causing cascading network risk.", delta_color="inverse")
        
        st.markdown("<br><p style='color: #ef4444; font-size: 0.85rem; letter-spacing: 2px;'>🚨 SYNERGISTIC ACTION QUEUE</p>", unsafe_allow_html=True)
        st.dataframe(risk_df.head(15).style.set_properties(**{'background-color': 'rgba(15, 23, 42, 0.4)', 'color': '#cbd5e1'}), use_container_width=True, hide_index=True)

    elif page == "/// 3D SPATIAL MATRIX":
        st.markdown("<h2>WEIBULL STOCHASTIC ENGINE</h2>", unsafe_allow_html=True)
        
        if not risk_df.empty:
            risk_df['Plot Size'] = risk_df['Risk Score'].apply(lambda x: max(5, int(x/2)))
            fig_risk = px.scatter_3d(
                risk_df, x="Days Open", y="Risk Score", z="System Node", color="Recommendation",
                hover_data=['Vessel', 'Description', 'Cascading Impact'], size="Plot Size", size_max=25,
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

except Exception as e:
    # If the system breaks, it will now tell you EXACTLY why instead of crashing silently.
    st.error("🚨 CRITICAL SYSTEM FAILURE: An error occurred during data processing.")
    st.code(traceback.format_exc(), language='python')
