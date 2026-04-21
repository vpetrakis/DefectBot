import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from logic.fuzzy_engine import apply_fuzzy_logic
from logic.risk_engine import run_risk_simulation

st.set_page_config(page_title="DEFECTBOT // OS", layout="wide", initial_sidebar_state="expanded")

# --- DIRECT CSS INJECTION (Bypasses Browser Caching) ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

[data-testid="stHeader"] { background-color: transparent !important; }
footer { visibility: hidden; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #020617; }
::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #38bdf8; }

.stApp {
    background: radial-gradient(circle at 50% -20%, #0f172a 0%, #020617 100%) !important;
    background-color: #020617 !important;
    color: #cbd5e1;
    font-family: 'Inter', sans-serif;
}

h1, h2, h3 {
    font-weight: 300 !important;
    letter-spacing: 2px;
    background: linear-gradient(90deg, #f8fafc 0%, #94a3b8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-transform: uppercase;
}

@keyframes smoothEntry {
    0% { transform: translateY(15px); opacity: 0.1; }
    100% { transform: translateY(0); opacity: 1; }
}

@keyframes criticalPulse {
    0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.4); }
    70% { box-shadow: 0 0 25px 8px rgba(220, 38, 38, 0); }
    100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }
}

.block-container {
    opacity: 1; 
    animation: smoothEntry 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

div[data-testid="metric-container"] {
    background: rgba(15, 23, 42, 0.4);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-top: 2px solid #0ea5e9;
    border-radius: 8px;
    padding: 24px;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

div[data-testid="metric-container"]:hover {
    transform: translateY(-4px);
    border-top: 2px solid #38bdf8;
    background: rgba(15, 23, 42, 0.6);
    box-shadow: 0 15px 40px -5px rgba(56, 189, 248, 0.2);
}

div[data-testid="metric-container"]:nth-child(2) {
    border-top: 2px solid #ef4444;
    animation: criticalPulse 2.5s infinite;
}
div[data-testid="metric-container"]:nth-child(2):hover {
    border-top: 2px solid #f87171;
    box-shadow: 0 15px 40px -5px rgba(239, 68, 68, 0.3);
}

[data-testid="stFileUploadDropzone"] {
    background: rgba(15, 23, 42, 0.4);
    border: 1px dashed rgba(56, 189, 248, 0.3);
    border-radius: 8px;
    transition: all 0.3s ease;
}
[data-testid="stFileUploadDropzone"]:hover {
    background: rgba(15, 23, 42, 0.8);
    border-color: #38bdf8;
    box-shadow: inset 0 0 30px rgba(56, 189, 248, 0.15);
}

.stDataFrame {
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    box-shadow: 0 10px 30px -10px rgba(0,0,0,0.6);
}
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
                    if raw_df.empty:
                        integrity_log.append({"Vessel": vessel_name, "Status": "SKIPPED: Blank Matrix", "Rows Extracted": 0})
                        continue
                        
                    header_row = -1
                    for idx, row in raw_df.head(20).iterrows():
                        row_str = ' '.join([str(val).upper() for val in row.values])
                        if 'CASE REF' in row_str and 'DESC' in row_str:
                            header_row = idx
                            break
                            
                    if header_row == -1:
                        integrity_log.append({"Vessel": vessel_name, "Status": "SKIPPED: Schema Unverified", "Rows Extracted": 0})
                        continue
                        
                    temp_df = raw_df.iloc[header_row + 1:].copy()
                    temp_df.columns = [str(c).strip() for c in raw_df.iloc[header_row].values]
                    
                    ref_col = next((c for c in temp_df.columns if 'CASE REF' in str(c).upper()), None)
                    desc_col = next((c for c in temp_df.columns if 'DESC' in str(c).upper()), None)
                    if not ref_col or not desc_col: continue
                        
                    temp_df.rename(columns={ref_col: 'Case Reference', desc_col: 'Case Description'}, inplace=True)
                    
                    date_col = next((c for c in temp_df.columns if 'DUE DATE' in str(c).upper()), None)
                    if date_col: temp_df.rename(columns={date_col: 'Due Date'}, inplace=True)
                    cond_col = next((c for c in temp_df.columns if 'COND' in str(c).upper()), None)
                    if cond_col: temp_df.rename(columns={cond_col: 'Condition'}, inplace=True)
                    init_date_col = next((c for c in temp_df.columns if 'INITIAL' in str(c).upper() and 'DATE' in str(c).upper()), None)
                    if init_date_col: temp_df.rename(columns={init_date_col: 'Date of Initial Reporting'}, inplace=True)
                    
                    temp_df.dropna(subset=['Case Description'], inplace=True)
                    if temp_df.empty: continue
                    
                    temp_df['Vessel'] = vessel_name
                    df_list.append(temp_df)
                    integrity_log.append({"Vessel": vessel_name, "Status": "SUCCESS: Telemetry Locked", "Rows Extracted": len(temp_df)})
                    
            elif file_ext == '.csv':
                temp_df = pd.read_csv(file, skiprows=4)
                temp_df.columns = [str(c).strip() for c in temp_df.columns]
                if 'Case Reference' in temp_df.columns and 'Case Description' in temp_df.columns:
                    temp_df.dropna(subset=['Case Description'], inplace=True)
                    vessel_name = file.name.split(' - ')[-1].replace('.csv', '').strip().upper()
                    if not vessel_name or "TEC-003" in vessel_name: vessel_name = "UNKNOWN"
                    temp_df['Vessel'] = vessel_name
                    df_list.append(temp_df)
                    integrity_log.append({"Vessel": vessel_name, "Status": "SUCCESS: Telemetry Locked (CSV)", "Rows Extracted": len(temp_df)})
        except Exception as e:
            st.error(f"CRITICAL FAULT: {e}")
            
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

st.sidebar.markdown("<h3 style='color: #38bdf8; letter-spacing: 2px;'>DEFECTBOT // OS</h3>", unsafe_allow_html=True)
st.sidebar.caption("SYS.STATUS: ONLINE // SECURE NODE")
uploaded_files = st.sidebar.file_uploader("UPLOAD TELEMETRY DATA", type=['xlsx', 'xls', 'csv'], accept_multiple_files=True)

st.sidebar.markdown("---")
page = st.sidebar.radio("COMMAND MODULES", ["/// SYSTEM OVERVIEW", "/// ASSET DEEP-DIVE", "/// SPATIAL RISK MATRIX", "/// INTEGRITY LEDGER"])
st.sidebar.markdown("---")

if not uploaded_files:
    st.markdown("<h1 style='text-align: center; margin-top: 15vh; font-weight: 300; color: #475569;'>AWAITING TELEMETRY</h1>", unsafe_allow_html=True)
    st.stop()

with st.spinner("EXECUTING HUNTER-SEEKER INGESTION..."):
    master_df, integrity_df = process_uploaded_files(uploaded_files)

if master_df.empty:
    st.error("FAULT: ZERO VALID METRICS DETECTED. CHECK INTEGRITY LEDGER.")
    st.stop()

if page == "/// SYSTEM OVERVIEW":
    st.markdown("<h2>FLEET COMMAND OVERVIEW</h2>", unsafe_allow_html=True)
    total_open = len(master_df)
    total_critical = len(master_df[master_df['Tag'] == 'CRITICAL'])
    total_overdue = len(master_df[master_df['True Condition'] == 'OVERDUE'])
    health_index = max(0, round(100 - (((total_critical * 1.5) + total_overdue) / total_open * 100), 1)) if total_open > 0 else 100
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ACTIVE LOGS", total_open)
    col2.metric("CRITICAL ANOMALIES", total_critical, "- Action Required", delta_color="inverse")
    col3.metric("TEMPORAL BREACHES", total_overdue, "- Protocol Violation", delta_color="inverse")
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
        fig_bar.update_traces(marker_line_width=0, opacity=0.9)
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

    st.markdown("<p style='color: #ef4444; font-size: 0.85rem; letter-spacing: 2px;'>🚨 PRIORITY ACTION QUEUE</p>", unsafe_allow_html=True)
    critical_df = master_df[master_df['Tag'] == 'CRITICAL'].head(10)[['Vessel', 'Case Reference', 'Case Description', 'True Condition', 'Due Date']] if not master_df[master_df['Tag'] == 'CRITICAL'].empty else pd.DataFrame()
    if not critical_df.empty:
        if 'Due Date' in critical_df.columns: critical_df['Due Date'] = critical_df['Due Date'].dt.strftime('%Y-%m-%d').fillna('NO DATE')
        st.dataframe(critical_df.style.set_properties(**{'background-color': 'rgba(239, 68, 68, 0.05)', 'color': '#fca5a5', 'border-bottom': '1px solid rgba(239, 68, 68, 0.1)'}), use_container_width=True, hide_index=True)
    else: st.success("SYSTEM CLEAR: No critical anomalies detected.")

elif page == "/// ASSET DEEP-DIVE":
    st.markdown("<h2>ASSET OPERATIONS</h2>", unsafe_allow_html=True)
    vessels = sorted(master_df['Vessel'].unique().tolist())
    selected_vessel = st.selectbox("SELECT TARGET ASSET", vessels)
    vessel_data = master_df[master_df['Vessel'] == selected_vessel]
    st.markdown(f"<p style='color: #38bdf8; font-family: JetBrains Mono;'>[ SYSTEM QUERY: {selected_vessel} ]</p>", unsafe_allow_html=True)
    cols_to_show = ['Case Reference', 'Case Description']
    if 'Date of Initial Reporting' in master_df.columns: cols_to_show.append('Date of Initial Reporting')
    if 'Due Date' in master_df.columns: cols_to_show.append('Due Date')
    cols_to_show.extend(['True Condition', 'Tag'])
    
    def cinematic_row_style(row):
        return ['background-color: rgba(220, 38, 38, 0.12); color: #fca5a5; font-weight: 500'] * len(row) if str(row.get('Tag', '')) == 'CRITICAL' or str(row.get('True Condition', '')) == 'OVERDUE' else [''] * len(row)
    try: styled_df = vessel_data[cols_to_show].style.apply(cinematic_row_style, axis=1)
    except: styled_df = vessel_data[cols_to_show].style.applymap(cinematic_row_style, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=550)

# --- THE 3D SPATIAL RISK UPGRADE (Now Crash-Proof) ---
elif page == "/// SPATIAL RISK MATRIX":
    st.markdown("<h2>WEIBULL STOCHASTIC ENGINE</h2>", unsafe_allow_html=True)
    st.caption("EXECUTING TEMPORAL & SENTIMENT-MODIFIED MONTE CARLO PROJECTIONS IN 3D SPACE.")
    
    col_ctrl, col_space = st.columns([1, 2])
    with col_ctrl: sims = st.slider("MONTE CARLO ITERATIONS", min_value=1000, max_value=10000, value=5000, step=1000)
    
    with st.spinner('COMPUTING WEIBULL PROBABILITY MATRICES...'):
        risk_df = run_risk_simulation(master_df, simulations=sims)
    
    if not risk_df.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- BULLETPROOF DATA SANITIZATION ---
        # Ensures that older risk_engine.py outputs (like strings) don't crash Plotly
        if risk_df['Expected Loss ($)'].dtype == object:
            risk_df['Expected Loss ($)'] = risk_df['Expected Loss ($)'].astype(str).str.replace('$', '').str.replace(',', '').astype(float)
        
        risk_df['Risk Score (0-100)'] = pd.to_numeric(risk_df['Risk Score (0-100)'], errors='coerce').fillna(1)
        # Plotly size cannot be 0 or negative. We force a minimum size of 1.
        risk_df['Plot Size'] = risk_df['Risk Score (0-100)'].apply(lambda x: max(1, int(x)))
        
        # Ensure Days Open exists
        if 'Days Open' not in risk_df.columns:
            risk_df['Days Open'] = 0

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
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#94a3b8"),
            margin=dict(l=0, r=0, b=0, t=0)
        )
        st.plotly_chart(fig_risk, use_container_width=True, config={'displayModeBar': False})
        
        # Re-format currency purely for the table display, keeping the raw data safe
        display_df = risk_df.drop(columns=['Plot Size'], errors='ignore').copy()
        display_df['Expected Loss ($)'] = display_df['Expected Loss ($)'].apply(lambda x: f"${int(x):,}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else: 
        st.success("100% TEMPORAL COMPLIANCE. NO UNBOUNDED RISKS DETECTED.")

elif page == "/// INTEGRITY LEDGER":
    st.markdown("<h2>DATA INTEGRITY LEDGER</h2>", unsafe_allow_html=True)
    st.metric("TOTAL VECTORS PROCESSED", integrity_df['Rows Extracted'].sum())
    def log_styler(row): return ['color: #10b981; font-family: JetBrains Mono'] * len(row) if 'SUCCESS' in str(row.get('Status', '')) else ['color: #ef4444; font-family: JetBrains Mono; font-weight: bold'] * len(row)
    try: styled_log = integrity_df.style.apply(log_styler, axis=1)
    except: styled_log = integrity_df
    st.dataframe(styled_log, use_container_width=True, hide_index=True, height=600)
