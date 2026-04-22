import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
import re
import networkx as nx
import traceback

# ==========================================
# 1. SYSTEM CONFIGURATION & CLINICAL CSS
# ==========================================
st.set_page_config(page_title="DEFECTBOT // OS", layout="wide", initial_sidebar_state="expanded")

# Removed all emojis and 'cheap' visual elements. Applied strict, high-contrast, clinical styling.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap');
[data-testid="stHeader"] { background-color: transparent !important; }
footer { visibility: hidden; }
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #050505; }
::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
.stApp { background-color: #050505 !important; color: #a1a1aa; font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-weight: 400 !important; letter-spacing: 0.15em; color: #f4f4f5; text-transform: uppercase; border-bottom: 1px solid #27272a; padding-bottom: 8px;}
.block-container { padding-top: 2rem; }
div[data-testid="metric-container"] { background: #09090b; border: 1px solid #27272a; padding: 20px; border-radius: 4px; }
div[data-testid="metric-container"] label { color: #71717a !important; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; letter-spacing: 0.05em; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] { color: #f4f4f5; font-weight: 300; }
.stDataFrame { border: 1px solid #27272a; border-radius: 4px; }
.critical-text { color: #ef4444; font-family: 'JetBrains Mono', monospace; font-weight: 600; font-size: 0.85rem;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THE DEEP MARINE ONTOLOGY & NETWORKX
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
    """
    Autonomous Deep Marine Dictionary. 
    Maps specific sub-components to their parent network nodes.
    """
    desc = str(description).upper()
    
    # 1. Main Engine Ontology
    me_keywords = ['MAIN ENGINE', 'M/E', 'PISTON', 'LINER', 'EXHAUST VALVE', 'TURBOCHARGER', 'TURBO', 'JACKET WATER', 'CRANKCASE', 'CAMSHAFT', 'SCAVENGE', 'CROSSHEAD', 'FIP', 'INJECTOR']
    if any(kw in desc for kw in me_keywords): return "MAIN_ENGINE"
    
    # 2. Generator Ontology (Explicitly looking for 1 or 2 first)
    if any(kw in desc for kw in ['DG1', 'GEN 1', 'GENERATOR 1', 'AE 1']): return "DG1"
    if any(kw in desc for kw in ['DG2', 'GEN 2', 'GENERATOR 2', 'AE 2']): return "DG2"
    # Generic generator parts act as a proxy on DG1 to trigger switchboard risk
    dg_generic = ['AVR', 'GOVERNOR', 'STATOR', 'ALTERNATOR', 'ROTOR', 'EXCITER', 'DIESEL GEN']
    if any(kw in desc for kw in dg_generic): return "DG1" 
    
    # 3. Switchboard / Power Ontology
    msb_keywords = ['SWITCHBOARD', 'MSB', 'POWER', 'BREAKER', 'BUSBAR', 'RELAY', 'SYNCHRONIZER', 'MEGGER']
    if any(kw in desc for kw in msb_keywords): return "MAIN_SWITCHBOARD"
    
    # 4. Cooling Ontology
    cooling_keywords = ['COOLING', 'HEAT EXCHANGER', 'COOLER', 'SEA WATER PUMP', 'FRESH WATER PUMP', 'HT WATER', 'LT WATER']
    if any(kw in desc for kw in cooling_keywords): return "ME_COOLING"
    
    # 5. Propulsion Ontology
    prop_keywords = ['PROPULSION', 'SHAFT', 'PROPELLER', 'STERN TUBE', 'THRUST BEARING', 'PITCH']
    if any(kw in desc for kw in prop_keywords): return "PROPULSION"
    
    # 6. Steering Ontology
    steer_keywords = ['STEERING', 'RUDDER', 'TELEMOTOR', 'RAM', 'TILLER', 'HYDRAULIC PUMP']
    if any(kw in desc for kw in steer_keywords): return "STEERING"
    
    # Silent Fallback
    return "ISOLATED"

def get_urgency_multiplier(description):
    desc = str(description).upper()
    urgent_words = ['URGENT', 'SEVERE', 'CRITICAL', 'IMMEDIATE', 'DANGER', 'FAILING', 'HEAVY LEAK', 'VIBRATION', 'ALARM']
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
            base_loc = 0.35 if any(k in desc for k in ['ENGINE', 'PROPULSION', 'STEERING', 'GENERATOR']) else 0.15
            base_cost = 150000 if base_loc == 0.35 else 30000
            
            try: days_open = max(0, (today - pd.to_datetime(row.get('Date of Initial Reporting', today))).days)
            except: days_open = 0
                
            time_multiplier = 1.0 + ((days_open / 15.0) * 0.05)
            urgency_multiplier = get_urgency_multiplier(desc)
            
            weibull_array = np.clip(np.random.weibull(a=1.5, size=simulations) * base_loc, 0, 1)
            expected_loss = np.mean(weibull_array) * time_multiplier * urgency_multiplier * base_cost
            base_risk_score = (expected_loss / (base_cost * 0.6)) * 100
            
            system_node = row.get('System Node', 'ISOLATED')
            cascading_threats = ""
            final_risk_score = base_risk_score
            
            if system_node in G.nodes and system_node != 'ISOLATED':
                victims = list(nx.descendants(G, system_node))
                if victims:
                    final_risk_score *= 1.45
                    cascading_threats = f"NETWORK IMPACT: DEGRADES {', '.join(victims)}"
            
            final_risk_score = min(100, int(final_risk_score))
            
            results.append({
                'Vessel': row.get('Vessel', 'Unknown'),
                'Case Ref': str(row.get('Case Reference', 'N/A')),
                'Description': str(row.get('Case Description', 'N/A')),
                'System Node': system_node,
                'Days Open': int(days_open),
                'Risk Score': final_risk_score,
                'Cascading Impact': cascading_threats,
                'Status': 'CRITICAL' if final_risk_score > 75 else ('ELEVATED' if final_risk_score > 50 else 'NOMINAL')
            })
        except Exception: continue
            
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
        except Exception: continue
            
    if not df_list: return pd.DataFrame()
    
    master_df = pd.concat(df_list, ignore_index=True)
    master_df['System Node'] = master_df['Case Description'].apply(assign_system_node)
    return master_df

# ==========================================
# 5. SECURE OS UI & ROUTING
# ==========================================
st.sidebar.markdown("<h3 style='font-family: \"JetBrains Mono\", monospace; color: #fff;'>DEFECTBOT // OS</h3>", unsafe_allow_html=True)
st.sidebar.caption("SYS.VERSION: 4.0 // CLINICAL BUILD")
uploaded_files = st.sidebar.file_uploader("INGEST TELEMETRY", type=['xlsx', 'csv'], accept_multiple_files=True)

if not uploaded_files:
    st.markdown("<div style='text-align: center; margin-top: 20vh; font-family: \"JetBrains Mono\"; color: #52525b;'>AWAITING TELEMETRY UPLINK...</div>", unsafe_allow_html=True)
    st.stop()

# --- ARMORED EXECUTION BLOCK ---
try:
    master_df = process_uploaded_files(uploaded_files)
    
    if master_df.empty: 
        st.error("[SYS.HALT] ZERO VALID METRICS DETECTED. VERIFY COLUMN HEADERS.")
        st.stop()

    G = build_vessel_topology()
    risk_df = run_risk_simulation(master_df, G, simulations=2000)

    page = st.sidebar.radio("MODULES", ["THREAT MATRIX", "SPATIAL ENGINE"])

    if page == "THREAT MATRIX":
        st.markdown("<h2>COMBINATORIAL THREAT MATRIX</h2>", unsafe_allow_html=True)
        total_open = len(risk_df)
        total_critical = len(risk_df[risk_df['Status'] == 'CRITICAL'])
        total_cascading = len(risk_df[risk_df['Cascading Impact'] != ""])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("ACTIVE TELEMETRY", total_open)
        col2.metric("CRITICAL BREACHES", total_critical)
        col3.metric("SYNERGISTIC THREATS", total_cascading)
        
        st.markdown("<br><p class='critical-text'>PRIORITY ACTION QUEUE</p>", unsafe_allow_html=True)
        
        # Clinical styling for the dataframe
        st.dataframe(
            risk_df.head(20).style.applymap(
                lambda x: 'color: #ef4444; font-weight: bold;' if x == 'CRITICAL' else ('color: #a1a1aa;' if x == 'NOMINAL' else 'color: #f59e0b;'),
                subset=['Status']
            ),
            use_container_width=True, hide_index=True
        )

    elif page == "SPATIAL ENGINE":
        st.markdown("<h2>WEIBULL STOCHASTIC ENGINE</h2>", unsafe_allow_html=True)
        
        if not risk_df.empty:
            risk_df['Plot Size'] = risk_df['Risk Score'].apply(lambda x: max(5, int(x/2)))
            fig_risk = px.scatter_3d(
                risk_df, x="Days Open", y="Risk Score", z="System Node", color="Status",
                hover_data=['Vessel', 'Description', 'Cascading Impact'], size="Plot Size", size_max=25,
                template="plotly_dark", color_discrete_map={"CRITICAL": "#ef4444", "ELEVATED": "#f59e0b", "NOMINAL": "#3f3f46"}
            )
            fig_risk.update_layout(
                scene=dict(
                    xaxis=dict(showgrid=True, gridcolor="#27272a", backgroundcolor="#050505"),
                    yaxis=dict(showgrid=True, gridcolor="#27272a", backgroundcolor="#050505"),
                    zaxis=dict(showgrid=True, gridcolor="#27272a", backgroundcolor="#050505"),
                ),
                plot_bgcolor="#050505", paper_bgcolor="#050505", font=dict(family="Inter", color="#a1a1aa"), margin=dict(l=0, r=0, b=0, t=0)
            )
            st.plotly_chart(fig_risk, use_container_width=True, config={'displayModeBar': False})

except Exception as e:
    st.error("[SYS.HALT] EXECUTION FAILURE DETECTED.")
    st.code(traceback.format_exc(), language='python')
