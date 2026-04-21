import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
from logic.fuzzy_engine import apply_fuzzy_logic
from logic.risk_engine import run_risk_simulation

# --- SYSTEM CONFIGURATION ---
st.set_page_config(page_title="DEFECTBOT // OS", layout="wide", initial_sidebar_state="expanded")

# --- LOAD CINEMATIC CSS ---
try:
    with open("assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass 

# --- ZERO-BUG INGESTION ENGINE ---
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
                        integrity_log.append({"Vessel": vessel_name, "Status": "SKIPPED: Blank Sheet", "Rows Extracted": 0})
                        continue
                        
                    header_row = -1
                    for idx, row in raw_df.head(20).iterrows():
                        row_str = ' '.join([str(val).upper() for val in row.values])
                        if 'CASE REF' in row_str and 'DESC' in row_str:
                            header_row = idx
                            break
                            
                    if header_row == -1:
                        integrity_log.append({"Vessel": vessel_name, "Status": "SKIPPED: No Data Table Detected", "Rows Extracted": 0})
                        continue
                        
                    temp_df = raw_df.iloc[header_row + 1:].copy()
                    temp_df.columns = [str(c).strip() for c in raw_df.iloc[header_row].values]
                    
                    ref_col = next((c for c in temp_df.columns if 'CASE REF' in str(c).upper()), None)
                    desc_col = next((c for c in temp_df.columns if 'DESC' in str(c).upper()), None)
                    
                    if not ref_col or not desc_col:
                        integrity_log.append({"Vessel": vessel_name, "Status": "SKIPPED: Corrupted Schema", "Rows Extracted": 0})
                        continue
                        
                    temp_df.rename(columns={ref_col: 'Case Reference', desc_col: 'Case Description'}, inplace=True)
                    
                    date_col = next((c for c in temp_df.columns if 'DUE DATE' in str(c).upper()), None)
                    if date_col: temp_df.rename(columns={date_col: 'Due Date'}, inplace=True)
                    
                    cond_col = next((c for c in temp_df.columns if 'COND' in str(c).upper()), None)
                    if cond_col: temp_df.rename(columns={cond_col: 'Condition'}, inplace=True)
                    
                    init_date_col = next((c for c in temp_df.columns if 'INITIAL' in str(c).upper() and 'DATE' in str(c).upper()), None)
                    if init_date_col: temp_df.rename(columns={init_date_col: 'Date of Initial Reporting'}, inplace=True)
                    
                    temp_df.dropna(subset=['Case Description'], inplace=True)
                    if temp_df.empty:
                        integrity_log.append({"Vessel": vessel_name, "Status": "SKIPPED: Empty Descriptions", "Rows Extracted": 0})
                        continue
                    
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
            st.error(f"CRITICAL FAULT parsing {file.name}: {e}")
            
    if not df_list:
        return pd.DataFrame(), pd.DataFrame(integrity_log)
        
    master_df = pd.concat(df_list, ignore_index=True)
    
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

# --- SECURE SIDEBAR INTERFACE ---
st.sidebar.markdown("<h3 style='color: #38bdf8; letter-spacing: 2px;'>DEFECTBOT // OS</h3>", unsafe_allow_html=True)
st.sidebar.caption("SYS.STATUS: ONLINE // SECURE NODE")

uploaded_files = st.sidebar.file_uploader(
    "UPLOAD TELEMETRY DATA", 
    type=['xlsx', 'xls', 'csv'], 
    accept_multiple_files=True
)

st.sidebar.markdown("---")
page = st.sidebar.radio("COMMAND MODULES", [
    "/// SYSTEM OVERVIEW", 
    "/// ASSET DEEP-DIVE", 
    "/// STOCHASTIC RISK", 
    "/// INTEGRITY LEDGER"
])
st.sidebar.markdown("---")

if not uploaded_files:
    st.markdown("<h1 style='text-align: center; margin-top: 15vh; font-weight: 300; color: #475569;'>AWAITING TELEMETRY</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b;'>Establish secure connection by uploading fleet matrix.</p>", unsafe_allow_html=True)
    st.stop()

with st.spinner("EXECUTING HUNTER-SEEKER INGESTION..."):
    master_df, integrity_df = process_uploaded_files(uploaded_files)

if master_df.empty:
    st.error("FAULT: ZERO VALID METRICS DETECTED. CHECK INTEGRITY LEDGER.")
    st.stop()

# ==========================================
# MODULE 1: SYSTEM OVERVIEW
# ==========================================
if page == "/// SYSTEM OVERVIEW":
    st.markdown("<h2>FLEET COMMAND OVERVIEW</h2>", unsafe_allow_html=True)
    
    total_open = len(master_df)
    total_critical = len(master_df[master_df['Tag'] == 'CRITICAL'])
    total_overdue = len(master_df[master_df['True Condition'] == 'OVERDUE'])
    
    if total_open > 0:
        health_index = max(0, round(100 - (((total_critical * 1.5) + total_overdue) / total_open * 100), 1))
    else:
        health_index = 100
        
    health_color = "normal" if health_index > 80 else "inverse"
    health_status = "OPTIMAL" if health_index > 80 else "DEGRADED"
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ACTIVE LOGS", total_open)
    col2.metric("CRITICAL ANOMALIES", total_critical, "- Action Required", delta_color="inverse")
    col3.metric("TEMPORAL BREACHES", total_overdue, "- Protocol Violation", delta_color="inverse")
    col4.metric("HEALTH INDEX", f"{health_index}%", f"Status: {health_status}", delta_color=health_color)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_chart1, col_chart2 = st.columns([1, 1.5])
    
    with col_chart1:
        st.markdown("<p style='color: #94a3b8; font-size: 0.85rem; letter-spacing: 1px;'>THREAT DISTRIBUTION</p>", unsafe_allow_html=True)
        donut_data = master_df['Tag'].value_counts().reset_index()
        donut_data.columns = ['Tag', 'Count']
        
        fig_donut = px.pie(
            donut_data, names='Tag', values='Count', hole=0.75,
            color='Tag', color_discrete_map={"CRITICAL": "#ef4444", "NON-CRITICAL": "#0ea5e9"}
        )
        fig_donut.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False, margin=dict(t=10, b=10, l=10, r=10),
            annotations=[dict(text=f"{total_critical}", x=0.5, y=0.5, font_size=48, font_family="Inter", font_color="#ef4444", showarrow=False)]
        )
        fig_donut.update_traces(textinfo='percent+label', textfont_color="#cbd5e1", marker=dict(line=dict(color='#020617', width=3)))
        st.plotly_chart(fig_donut, use_container_width=True, config={'displayModeBar': False})

    with col_chart2:
        st.markdown("<p style='color: #94a3b8; font-size: 0.85rem; letter-spacing: 1px;'>ASSET VULNERABILITY MATRIX</p>", unsafe_allow_html=True)
        fig_bar = px.histogram(
            master_df, x="Vessel", color="Tag",
            color_discrete_map={"CRITICAL": "#ef4444", "NON-CRITICAL": "#0ea5e9"},
            template="plotly_dark", barmode="stack"
        ).update_xaxes(categoryorder="total descending")
        
        fig_bar.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified", font=dict(family="Inter", color="#94a3b8"),
            xaxis=dict(showgrid=False, zeroline=False, title=""),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False, title="VOLUME"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=""),
            margin=dict(t=10, b=10, l=0, r=0)
        )
        fig_bar.update_traces(marker_line_width=0, opacity=0.9)
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<p style='color: #ef4444; font-size: 0.85rem; letter-spacing: 2px;'>🚨 PRIORITY ACTION QUEUE (TOP 10 CRITICAL)</p>", unsafe_allow_html=True)
    
    critical_df = master_df[master_df['Tag'] == 'CRITICAL'].copy()
    if not critical_df.empty:
        critical_df = critical_df.head(10)[['Vessel', 'Case Reference', 'Case Description', 'True Condition', 'Due Date']]
        if 'Due Date' in critical_df.columns:
            critical_df['Due Date'] = critical_df['Due Date'].dt.strftime('%Y-%m-%d').fillna('NO DATE')
            
        st.dataframe(
            critical_df.style.set_properties(**{
                'background-color': 'rgba(239, 68, 68, 0.05)', 'color': '#fca5a5', 'border-bottom': '1px solid rgba(239, 68, 68, 0.1)'
            }),
            use_container_width=True, hide_index=True
        )
    else:
        st.success("SYSTEM CLEAR: No critical anomalies detected across the fleet.")

# ==========================================
# MODULE 2: ASSET DEEP-DIVE
# ==========================================
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
            return ['background-color: rgba(220, 38, 38, 0.12); color: #fca5a5; font-weight: 500'] * len(row)
        return [''] * len(row)

    styler = vessel_data[cols_to_show].style
    try:
        styled_df = styler.apply(cinematic_row_style, axis=1)
    except AttributeError:
        styled_df = styler.applymap(cinematic_row_style, axis=1)

    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=550)

# ==========================================
# MODULE 3: STOCHASTIC RISK
# ==========================================
elif page == "/// STOCHASTIC RISK":
    st.markdown("<h2>STOCHASTIC RISK ENGINE</h2>", unsafe_allow_html=True)
    st.caption("EXECUTING DYNAMIC MONTE CARLO PROJECTIONS ON UNBOUNDED DEFECTS.")
    
    col_ctrl, col_space = st.columns([1, 2])
    with col_ctrl:
        sims = st.slider("MONTE CARLO ITERATIONS", min_value=1000, max_value=10000, value=5000, step=1000)
    
    with st.spinner('COMPUTING PROBABILITY MATRICES...'):
        risk_df = run_risk_simulation(master_df, simulations=sims)
    
    if not risk_df.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        fig_risk = px.scatter(
            risk_df, x="Risk Score (0-100)", y="Expected Loss ($)", color="Recommendation",
            hover_data=['Vessel', 'Description'], size_max=25, size="Risk Score (0-100)",
            template="plotly_dark", 
            color_discrete_map={"DISP REQUIRED": "#ef4444", "REVIEW": "#f59e0b", "NO ACTION": "#10b981"}
        )
        fig_risk.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#94a3b8"),
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"), yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
        )
        fig_risk.update_traces(marker=dict(line=dict(width=0), opacity=0.85))
        st.plotly_chart(fig_risk, use_container_width=True, config={'displayModeBar': False})
        
        st.dataframe(risk_df, use_container_width=True, hide_index=True)
    else:
        st.success("100% TEMPORAL COMPLIANCE. NO UNBOUNDED RISKS DETECTED.")

# ==========================================
# MODULE 4: INTEGRITY LEDGER
# ==========================================
elif page == "/// INTEGRITY LEDGER":
    st.markdown("<h2>DATA INTEGRITY LEDGER</h2>", unsafe_allow_html=True)
    st.caption("MATHEMATICAL PROOF OF ALGORITHMIC INGESTION PER NODE.")
    
    st.metric("TOTAL VECTORS PROCESSED", integrity_df['Rows Extracted'].sum())
    
    def log_styler(row):
        if 'SUCCESS' in str(row.get('Status', '')):
            return ['color: #10b981; font-family: JetBrains Mono'] * len(row)
        return ['color: #ef4444; font-family: JetBrains Mono; font-weight: bold'] * len(row)

    try:
        styled_log = integrity_df.style.apply(log_styler, axis=1)
    except Exception:
        styled_log = integrity_df
        
    st.dataframe(styled_log, use_container_width=True, hide_index=True, height=600)
