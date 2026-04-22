import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
import re
import networkx as nx
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
.stApp { background-color: #020617 !important; background: radial-gradient(circle at 50% -20%, #0f172a 0%, #020617 100%) !important; color: #cbd5e1; font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-weight: 300 !important; letter-spacing: 2px; background: linear-gradient(90deg, #f8fafc 0%, #94a3b8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-transform: uppercase; }
.block-container { opacity: 1; animation: smoothEntry 0.8s forwards; }
@keyframes smoothEntry { 0% { transform: translateY(15px); opacity: 0.1; } 100% { transform: translateY(0); opacity: 1; } }
@keyframes criticalPulse { 0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.4); } 70% { box-shadow: 0 0 25px 8px rgba(220, 38, 38, 0); } 100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); } }
div[data-testid="metric-container"] { background: rgba(15, 23, 42, 0.4); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.05); border-top: 2px solid #0ea5e9; border-radius: 8px; padding: 24px; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5); }
div[data-testid="metric-container"]:nth-child(2) { border-top: 2px solid #ef4444; animation: criticalPulse 3s infinite; }
.stDataFrame { border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THE SHIP ONTOLOGY & NETWORKX LOGIC
# ==========================================
@st.cache_resource
def build_vessel_topology():
    """Maps the combinatorial risk dependencies of the vessel."""
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
    """Contextual NLP Routing with Confidence Scoring."""
    desc = str(description).upper()
    if any(kw in desc for kw in ['DG1', 'GEN 1', 'GENERATOR 1']): return pd.Series(["DG1", "HIGH"])
    if any(kw in desc for kw in ['DG2', 'GEN 2', 'GENERATOR 2']): return pd.Series(["DG2", "HIGH"])
    if any(kw in desc for kw in ['SWITCHBOARD', 'MSB', 'POWER']): return pd.Series(["MAIN_SWITCHBOARD", "HIGH"])
    if any(kw in desc for kw in ['COOLING', 'JACKET WATER']): return pd.Series(["ME_COOLING", "HIGH"])
    if any(kw in desc for kw in ['MAIN ENGINE', 'M/E']): return pd.Series(["MAIN_ENGINE", "HIGH"])
    if any(kw in desc for kw in ['PROPULSION', 'SHAFT', 'PROPELLER']): return pd.Series(["PROPULSION", "HIGH"])
    if any(kw in desc for kw in ['STEERING', 'RUDDER']): return pd.Series(["STEERING", "HIGH"])
    if any(kw in desc for kw in ['CABIN', 'GALLEY', 'LAUNDRY']): return pd.Series(["ISOLATED", "HIGH"])
    return pd.Series(["UNKNOWN", "LOW"])

# ==========================================
# 3. WEIBULL STOCHASTIC ENGINE
# ==========================================
def run_risk_simulation(df, G, simulations=5000):
    if df.empty: return pd.DataFrame()
    today = pd.Timestamp('today').normalize()
    results = []
    
    for _, row in df.iterrows():
        desc = str(row['Case Description']).upper()
        base_loc = 0.35 if any(k in desc for k in ['ENGINE', 'PROPULSION', 'STEERING']) else 0.15
        base_cost = 150000 if base_loc == 0.35 else 30000
        
        try: days_open = max(0, (today - pd.to_datetime(row['Date of Initial Reporting'])).days)
        except: days_open = 0
            
        time_multiplier = 1.0 + ((days_open / 15.0) * 0.05)
        try: sentiment_multiplier = 1.35 if TextBlob(desc).sentiment.polarity < -0.3 else 1.0
        except: sentiment_multiplier = 1.0
        
        # Base Weibull Math
        weibull_array = np.clip(np.random.weibull(a=1.5, size=simulations) * base_loc, 0, 1)
        expected_loss = np.mean(weibull_array) * time_multiplier * sentiment_multiplier * base_cost
        base_risk_score = (expected_loss / (base_cost * 0.6)) * 100
        
        # NETWORKX CASCADING LOGIC
        system_node = row.get('System Node', 'ISOLATED')
        cascading_threats = ""
        final_risk_score = base_risk_score
        
        if system_node in G.nodes and system_node != 'ISOLATED':
            victims = list(nx.descendants(G, system_node))
            if victims:
                final_risk_score *= 1.45 # 45% Combinatorial Risk Spike
                cascading_threats = f"⚠️ THREATENS: {', '.join(victims)}"
        
        final_risk_score = min(100, int(final_risk_score))
        
        results.append({
            'Vessel': row.get('Vessel', 'Unknown'),
            'Case Ref': row['Case Reference'],
            'Description': row['Case Description'],
            'System Node': system_node,
            'Days Open': int(days_open),
            'Risk Score': final_risk_score,
            'Cascading Impact': cascading_threats,
            'Recommendation': 'CRITICAL THREAT' if final_risk_score > 75 else ('DISP REQUIRED' if final_risk_score > 50 else 'MONITOR')
        })
    return pd.DataFrame(results).sort_values(by="Risk Score", ascending=False)

# ==========================================
# 4. DATA INGESTION (HUNTER-SEEKER)
# ==========================================
@st.cache_data(show_spinner=False)
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
        except Exception: pass
    if not df_list: return pd.DataFrame()
    master_df = pd.concat(df_list, ignore_index=True)
    if 'Date of Initial Reporting' in master_df.columns:
        master_df['Date of Initial Reporting'] = pd.to_datetime(master_df['Date of Initial Reporting'], errors='coerce')
    
    # Apply NLP Routing
    master_df[['System Node', 'Confidence']] = master_df['Case Description'].apply(assign_system_node)
    return master_df

# ==========================================
# 5. SECURE OS UI & ROUTING
# ==========================================
st.sidebar.markdown("<h3>DEFECTBOT // OS</h3>", unsafe_allow_html=True)
st.sidebar.caption("SYS.STATUS: NETWORKX MONOLITH")
uploaded_files = st.sidebar.file_uploader("UPLOAD TELEMETRY DATA", type=['xlsx', 'csv'], accept_multiple_files=True)

if not uploaded_files:
    st.markdown("<h1 style='text-align: center; margin-top: 15vh;'>AWAITING TELEMETRY</h1>", unsafe_allow_html=True)
    st.stop()

master_df = process_uploaded_files(uploaded_files)
if master_df.empty: st.error("FAULT: ZERO VALID METRICS DETECTED."); st.stop()

# --- THE DETERMINISTIC GATE (TRIAGE UI) ---
low_confidence_mask = master_df['Confidence'] == 'LOW'
if low_confidence_mask.any():
    st.markdown("<h2>⚠️ ENTITY RESOLUTION REQUIRED</h2>", unsafe_allow_html=True)
    st.warning("The NLP engine detected ambiguous descriptions. To prevent NetworkX cascading errors, manual mapping is required.")
    
    edited_df = st.data_editor(
        master_df[low_confidence_mask][['Vessel', 'Case Reference', 'Case Description', 'System Node']],
        column_config={
            "System Node": st.column_config.SelectboxColumn("Map to System (REQUIRED)", options=["DG1", "DG2", "MAIN_SWITCHBOARD", "ME_COOLING", "MAIN_ENGINE", "PROPULSION", "STEERING", "ISOLATED"], required=True)
        },
        disabled=["Vessel", "Case Reference", "Case Description"],
        use_container_width=True, hide_index=True
    )
    
    if "UNKNOWN" in edited_df['System Node'].values:
        st.error("SYSTEM HALTED: You must resolve all 'UNKNOWN' tags before the Weibull engine can safely compute network risk.")
        st.stop()
        
    master_df.loc[low_confidence_mask, 'System Node'] = edited_df['System Node'].values
    master_df.loc[low_confidence_mask, 'Confidence'] = 'HIGH'
    st.success("Triage Complete. Network alignment verified.")
    st.divider()

# --- EXECUTE MATH NOW THAT DATA IS 100% CLEAN ---
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
