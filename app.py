import streamlit as st
import pandas as pd
import numpy as np
import re
import io
import math
import traceback
import base64
import warnings
import os
from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from xgboost import XGBRegressor
    from sklearn.covariance import LedoitWolf
    from sklearn.model_selection import KFold
    import shap
    HAS_ML = Trueimport streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
import re
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
::-webkit-scrollbar-thumb:hover { background: #38bdf8; }
.stApp { background-color: #020617 !important; background: radial-gradient(circle at 50% -20%, #0f172a 0%, #020617 100%) !important; color: #cbd5e1; font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-weight: 300 !important; letter-spacing: 2px; background: linear-gradient(90deg, #f8fafc 0%, #94a3b8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-transform: uppercase; }
.block-container { opacity: 1; animation: smoothEntry 0.8s forwards; }
@keyframes smoothEntry { 0% { transform: translateY(15px); opacity: 0.1; } 100% { transform: translateY(0); opacity: 1; } }
@keyframes criticalPulse { 0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.4); } 70% { box-shadow: 0 0 25px 8px rgba(220, 38, 38, 0); } 100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); } }
div[data-testid="metric-container"] { background: rgba(15, 23, 42, 0.4); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.05); border-top: 2px solid #0ea5e9; border-radius: 8px; padding: 24px; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5); transition: all 0.3s ease; }
div[data-testid="metric-container"]:hover { transform: translateY(-4px); background: rgba(15, 23, 42, 0.6); }
div[data-testid="metric-container"]:nth-child(2) { border-top: 2px solid #ef4444; animation: criticalPulse 3s infinite; }
.stDataFrame { border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.05); box-shadow: 0 10px 30px -10px rgba(0,0,0,0.6); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. THE INTELLIGENCE ENGINES
# ==========================================
CRITICAL_KEYWORDS = [
    r'\bFIRE\b', r'\bBILGE\b', r'\bGMDSS\b', r'\bRESCUE\b', r'\bSTEERING\b', 
    r'\bCOMPRESSOR\b', r'\bPURIFIER\b', r'\bLEAKING\b', r'\bALARM\b', r'\bINGRESS\b', 
    r'\bMAIN ENGINE\b', r'\bGENERATOR\b', r'\bLIFEBOAT\b', r'\bOWS\b', r'\bBOILER\b'
]

def apply_fuzzy_logic(df):
    compiled_regexes = [re.compile(kw) for kw in CRITICAL_KEYWORDS]
    def evaluate_row(desc):
        if pd.isna(desc): return 'NON-CRITICAL'
        desc_upper = str(desc).upper()
        for regex in compiled_regexes:
            if regex.search(desc_upper): return 'CRITICAL'
        return 'NON-CRITICAL'
    df['Tag'] = df['Case Description'].apply(evaluate_row)
    return df

def get_equipment_risk_profile(description):
    desc = str(description).upper()
    if any(kw in desc for kw in ['ENGINE', 'PROPULSION', 'GENERATOR', 'STEERING', 'BOILER']): return 0.35, 150000 
    elif any(kw in desc for kw in ['FIRE', 'RESCUE', 'LIFEBOAT', 'GMDSS']): return 0.45, 95000   
    elif any(kw in desc for kw in ['PUMP', 'COMPRESSOR', 'PURIFIER', 'VALVE', 'OWS']): return 0.25, 45000   
    elif any(kw in desc for kw in ['GALLEY', 'CABIN', 'LAUNDRY', 'AC']): return 0.05, 5000    
    else: return 0.15, 30000   

def run_risk_simulation(df, simulations=5000):
    if 'Due Date' not in df.columns or 'Date of Initial Reporting' not in df.columns: return pd.DataFrame()
    nodue_df = df[df['Due Date'].isna()].copy()
    if nodue_df.empty: return pd.DataFrame()
    today = pd.Timestamp('today').normalize()
    results = []
    
    for _, row in nodue_df.iterrows():
        base_loc, base_cost = get_equipment_risk_profile(row['Case Description'])
        try: days_open = max(0, (today - pd.to_datetime(row['Date of Initial Reporting'])).days)
        except: days_open = 0
            
        time_multiplier = 1.0 + ((days_open / 15.0) * 0.05)
        try: sentiment_multiplier = 1.35 if TextBlob(str(row['Case Description'])).sentiment.polarity < -0.3 else 1.0
        except: sentiment_multiplier = 1.0
        
        weibull_array = np.clip(np.random.weibull(a=1.5, size=simulations) * base_loc, 0, 1)
        expected_loss = np.mean(weibull_array) * time_multiplier * sentiment_multiplier * base_cost
        risk_score = min(100, int((expected_loss / (base_cost * 0.6)) * 100))
        
        results.append({
            'Vessel': row.get('Vessel', 'Unknown'),
            'Case Ref': row['Case Reference'],
            'Description': row['Case Description'],
            'Days Open': int(days_open),
            'Risk Score (0-100)': risk_score,
            'Expected Loss ($)': expected_loss,
            'Recommendation': 'CRITICAL THREAT' if risk_score > 75 else ('DISP REQUIRED' if risk_score > 50 else 'MONITOR')
        })
    return pd.DataFrame(results).sort_values(by="Risk Score (0-100)", ascending=False)

# ==========================================
# 3. DATA INGESTION (HUNTER-SEEKER)
# ==========================================
@st.cache_data(show_spinner=False)
def process_uploaded_files(uploaded_files):
    df_list, integrity_log = [], []
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
                    init_date_col = next((c for c in temp_df.columns if 'INITIAL' in str(c).upper() and 'DATE' in str(c).upper()), None)
                    if init_date_col: temp_df.rename(columns={init_date_col: 'Date of Initial Reporting'}, inplace=True)
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
    if 'Date of Initial Reporting' in master_df.columns:
        master_df['Date of Initial Reporting'] = pd.to_datetime(master_df['Date of Initial Reporting'], errors='coerce')
    master_df = apply_fuzzy_logic(master_df)
    return master_df, pd.DataFrame(integrity_log)

# ==========================================
# 4. SECURE OS UI & ROUTING
# ==========================================
st.sidebar.markdown("<h3>DEFECTBOT // OS</h3>", unsafe_allow_html=True)
st.sidebar.caption("SYS.STATUS: CLOUD-NATIVE NODE")
uploaded_files = st.sidebar.file_uploader("UPLOAD TELEMETRY DATA", type=['xlsx', 'csv'], accept_multiple_files=True)
page = st.sidebar.radio("COMMAND MODULES", ["/// OVERVIEW", "/// ASSET DEEP-DIVE", "/// 3D SPATIAL MATRIX", "/// INTEGRITY LEDGER"])

if not uploaded_files:
    st.markdown("<h1 style='text-align: center; margin-top: 15vh;'>AWAITING TELEMETRY</h1>", unsafe_allow_html=True)
    st.stop()
master_df, integrity_df = process_uploaded_files(uploaded_files)
if master_df.empty: st.error("FAULT: ZERO VALID METRICS DETECTED."); st.stop()

# --- MODULE: OVERVIEW ---
if page == "/// OVERVIEW":
    st.markdown("<h2>FLEET COMMAND OVERVIEW</h2>", unsafe_allow_html=True)
    total_open = len(master_df)
    total_critical = len(master_df[master_df['Tag'] == 'CRITICAL'])
    total_overdue = len(master_df[master_df['True Condition'] == 'OVERDUE'])
    health_index = max(0, round(100 - (((total_critical * 1.5) + total_overdue) / total_open * 100), 1)) if total_open > 0 else 100
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ACTIVE LOGS", total_open)
    col2.metric("CRITICAL ANOMALIES", total_critical, delta_color="inverse")
    col3.metric("TEMPORAL BREACHES", total_overdue, delta_color="inverse")
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
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

    st.markdown("<p style='color: #ef4444; font-size: 0.85rem; letter-spacing: 2px;'>  PRIORITY ACTION QUEUE</p>", unsafe_allow_html=True)
    critical_df = master_df[master_df['Tag'] == 'CRITICAL'].head(10)[['Vessel', 'Case Reference', 'Case Description', 'True Condition', 'Due Date']] if not master_df[master_df['Tag'] == 'CRITICAL'].empty else pd.DataFrame()
    if not critical_df.empty:
        if 'Due Date' in critical_df.columns: critical_df['Due Date'] = critical_df['Due Date'].dt.strftime('%Y-%m-%d').fillna('NO DATE')
        st.dataframe(critical_df.style.set_properties(**{'background-color': 'rgba(239, 68, 68, 0.05)', 'color': '#fca5a5', 'border-bottom': '1px solid rgba(239, 68, 68, 0.1)'}), use_container_width=True, hide_index=True)

# --- MODULE: ASSET DEEP-DIVE ---
elif page == "/// ASSET DEEP-DIVE":
    st.markdown("<h2>ASSET OPERATIONS</h2>", unsafe_allow_html=True)
    vessels = sorted(master_df['Vessel'].unique().tolist())
    selected = st.selectbox("SELECT ASSET", vessels)
    vessel_data = master_df[master_df['Vessel'] == selected]
    cols_to_show = ['Case Reference', 'Case Description']
    if 'Date of Initial Reporting' in master_df.columns: cols_to_show.append('Date of Initial Reporting')
    if 'Due Date' in master_df.columns: cols_to_show.append('Due Date')
    cols_to_show.extend(['True Condition', 'Tag'])
    
    def row_style(row): return ['background-color: rgba(220, 38, 38, 0.12); color: #fca5a5; font-weight: 500'] * len(row) if str(row.get('Tag', '')) == 'CRITICAL' or str(row.get('True Condition', '')) == 'OVERDUE' else [''] * len(row)
    try: styled_df = vessel_data[cols_to_show].style.apply(row_style, axis=1)
    except: styled_df = vessel_data[cols_to_show].style.applymap(row_style, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=550)

# --- MODULE: 3D SPATIAL MATRIX ---
elif page == "/// 3D SPATIAL MATRIX":
    st.markdown("<h2>WEIBULL STOCHASTIC ENGINE</h2>", unsafe_allow_html=True)
    st.caption("Executing Temporal & Sentiment-Modified Monte Carlo Projections in 3D Space.")
    
    sims = st.slider("MONTE CARLO ITERATIONS", 1000, 10000, 5000, 1000)
    with st.spinner('COMPUTING WEIBULL PROBABILITY MATRICES...'):
        risk_df = run_risk_simulation(master_df, simulations=sims)
    
    if not risk_df.empty:
        risk_df['Plot Size'] = risk_df['Risk Score (0-100)'].apply(lambda x: max(1, int(x)))
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
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#94a3b8"), margin=dict(l=0, r=0, b=0, t=0)
        )
        st.plotly_chart(fig_risk, use_container_width=True, config={'displayModeBar': False})
        
        display_df = risk_df.drop(columns=['Plot Size']).copy()
        display_df['Expected Loss ($)'] = display_df['Expected Loss ($)'].apply(lambda x: f"${int(x):,}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else: st.success("100% TEMPORAL COMPLIANCE. NO UNBOUNDED RISKS DETECTED.")

# --- MODULE: INTEGRITY LEDGER ---
elif page == "/// INTEGRITY LEDGER":
    st.markdown("<h2>DATA INTEGRITY LEDGER</h2>", unsafe_allow_html=True)
    st.dataframe(integrity_df, use_container_width=True, hide_index=True)
except ImportError:
    HAS_ML = False

warnings.filterwarnings("ignore")
st.set_page_config(
    page_title="POSEIDON TITAN",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════════════════════════════════════
# CSS LOADER — __file__-anchored, bulletproof on Streamlit Cloud
# ═══════════════════════════════════════════════════════════════════════════════
def load_local_css():
    css_path = Path(__file__).parent / "assets" / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"⚠️ CSS not found at: {css_path}")

load_local_css()

# ═══════════════════════════════════════════════════════════════════════════════
# CINEMATIC JS ENGINE — injected once, guarded against Streamlit re-renders
# ═══════════════════════════════════════════════════════════════════════════════
def inject_cinematic_engine():
    st.markdown("""
    <script>
    (function(){
      if(window.__POSEIDON_ENGINE) return;
      window.__POSEIDON_ENGINE = true;

      const RAF = requestAnimationFrame;

      /* ── 1. CUSTOM CURSOR ─────────────────────────────────────── */
      function initCursor(){
        if(document.querySelector('.p-cursor-dot')) return;
        const dot  = document.createElement('div');
        const ring = document.createElement('div');
        dot.className  = 'p-cursor-dot';
        ring.className = 'p-cursor-ring';
        document.body.append(dot, ring);

        let mx=-200, my=-200, rx=-200, ry=-200;

        document.addEventListener('mousemove', e=>{
          mx=e.clientX; my=e.clientY;
          dot.style.left=mx+'px'; dot.style.top=my+'px';
        });

        (function lerp(){
          rx+=(mx-rx)*0.1; ry+=(my-ry)*0.1;
          ring.style.left=rx+'px'; ring.style.top=ry+'px';
          RAF(lerp);
        })();

        document.addEventListener('mouseover', e=>{
          const hover = e.target.closest(
            'button,a,[data-baseweb="tab"],.hud-card,.vcard,.q-card,[data-testid="stSelectbox"]'
          );
          dot.classList.toggle('cursor-hover',  !!hover);
          ring.classList.toggle('cursor-hover', !!hover);
        });
      }

      /* ── 2. BOOT OVERLAY ──────────────────────────────────────── */
      function initBoot(){
        if(sessionStorage.getItem('__psdn_boot')) return;
        sessionStorage.setItem('__psdn_boot','1');

        const o = document.createElement('div');
        o.className = 'p-boot-overlay';

        const logoSVG = `<svg viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="bgl" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#c9a84c"/>
              <stop offset="50%" stop-color="#00e0b0"/>
              <stop offset="100%" stop-color="#fff"/>
            </linearGradient>
          </defs>
          <circle cx="40" cy="40" r="36" fill="none" stroke="url(#bgl)"
                  stroke-width="1" opacity=".45" class="p-boot-circle"/>
          <path d="M40 8L40 72" stroke="url(#bgl)" stroke-width="2.5"
                stroke-linecap="round" class="p-boot-line1"/>
          <path d="M18 40Q40 56 62 40" fill="none" stroke="url(#bgl)"
                stroke-width="2.5" stroke-linecap="round" class="p-boot-line2"/>
        </svg>`;

        o.innerHTML = `
          <div class="p-boot-inner">
            <div class="p-boot-logo">${logoSVG}</div>
            <div class="p-boot-title" id="pBT"></div>
            <div class="p-boot-sub">Forensic Engine Initializing</div>
            <div class="p-boot-progress-track">
              <div class="p-boot-progress-fill" id="pBP"></div>
            </div>
            <div class="p-boot-status" id="pBS">LOADING MODULES...</div>
          </div>
          <div class="p-boot-scan"></div>
        `;
        document.body.prepend(o);

        /* Animated letters */
        const T='POSEIDON TITAN';
        document.getElementById('pBT').innerHTML =
          T.split('').map((c,i)=>
            `<span style="animation-delay:${.22+i*.055}s">${c===' '?'&nbsp;':c}</span>`
          ).join('');

        /* Progress + status sequence */
        const msgs=['LOADING MODULES...','CALIBRATING PHYSICS ENGINE...','ARMING FORENSIC SUITE...','SYSTEM ONLINE.'];
        let si=0;
        const iv = setInterval(()=>{ si=Math.min(si+1,msgs.length-1); document.getElementById('pBS').textContent=msgs[si]; },580);

        const fp = document.getElementById('pBP');
        RAF(()=>RAF(()=>{ fp.style.transition='width 2.3s cubic-bezier(0.16,1,0.3,1)'; fp.style.width='100%'; }));

        setTimeout(()=>{ clearInterval(iv); o.classList.add('p-boot-out'); setTimeout(()=>o.remove(),950); }, 2700);
      }

      /* ── 3. HOLOGRAPHIC CARD TILT ─────────────────────────────── */
      function initHolographic(){
        document.querySelectorAll('.hud-card:not([data-holo])').forEach(card=>{
          card.dataset.holo='1';
          card.addEventListener('mousemove', e=>{
            const r=card.getBoundingClientRect();
            const x=((e.clientX-r.left)/r.width)*100;
            const y=((e.clientY-r.top)/r.height)*100;
            card.style.setProperty('--mouse-x',x+'%');
            card.style.setProperty('--mouse-y',y+'%');
            const tx=((e.clientY-r.top)/r.height-.5)*-7;
            const ty=((e.clientX-r.left)/r.width-.5)*7;
            card.style.transform=`translateY(-5px) perspective(500px) rotateX(${tx}deg) rotateY(${ty}deg) scale(1.015)`;
          });
          card.addEventListener('mouseleave',()=>{
            card.style.transform='';
            card.style.setProperty('--mouse-x','50%');
            card.style.setProperty('--mouse-y','50%');
          });
        });
      }

      /* ── 4. COUNT-UP NUMBERS ──────────────────────────────────── */
      function countUp(el,target,dec,pfx,sfx){
        if(el.dataset.counted) return;
        el.dataset.counted='1';
        const dur=1450, t0=performance.now();
        const fmt=n=>{
          const v = dec>0
            ? n.toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec})
            : Math.round(n).toLocaleString('en-US');
          return pfx+v+sfx;
        };
        (function tick(now){
          const p=Math.min((now-t0)/dur,1);
          const e=1-Math.pow(1-p,4);
          el.textContent=fmt(e*target);
          if(p<1) RAF(tick); else el.textContent=fmt(target);
        })(t0);
      }

      function initCountUp(){
        document.querySelectorAll('.hud-val[data-target]:not([data-counted])').forEach(el=>{
          const io=new IntersectionObserver(entries=>{
            entries.forEach(en=>{
              if(en.isIntersecting){
                const target=parseFloat(el.dataset.target||0);
                const dec=parseInt(el.dataset.dec||0);
                const pfx=el.dataset.pfx||'';
                const sfx=el.dataset.sfx||'';
                countUp(el,target,dec,pfx,sfx);
                io.disconnect();
              }
            });
          },{threshold:.4});
          io.observe(el);
        });
      }

      /* ── 5. GAUGE ARC ANIMATION ───────────────────────────────── */
      function initGauges(){
        document.querySelectorAll('.gauge-arc:not([data-animated])').forEach(arc=>{
          arc.dataset.animated='1';
          const offset=parseFloat(arc.dataset.offset||0);
          RAF(()=>RAF(()=>{ arc.style.strokeDashoffset=offset; }));
        });
      }

      /* ── 6. SONAR PULSE ON LOGO ───────────────────────────────── */
      function initSonar(){
        const wrap=document.querySelector('.hero-logo-wrap');
        if(!wrap||wrap.dataset.sonar) return;
        wrap.dataset.sonar='1';
        function pulse(){
          const r=document.createElement('div');
          r.className='p-sonar-ring';
          wrap.appendChild(r);
          setTimeout(()=>r.remove(),2000);
        }
        pulse();
        setInterval(pulse,3200);
      }

      /* ── 7. BUTTON RIPPLE ─────────────────────────────────────── */
      function initRipples(){
        if(document.body.dataset.ripples) return;
        document.body.dataset.ripples='1';
        document.addEventListener('click',e=>{
          const btn=e.target.closest('button');
          if(!btn) return;
          const r=btn.getBoundingClientRect();
          const rpl=document.createElement('span');
          rpl.className='p-ripple';
          const s=Math.max(r.width,r.height)*2.4;
          rpl.style.cssText=`width:${s}px;height:${s}px;left:${e.clientX-r.left-s/2}px;top:${e.clientY-r.top-s/2}px`;
          btn.style.position='relative';
          btn.style.overflow='hidden';
          btn.appendChild(rpl);
          setTimeout(()=>rpl.remove(),700);
        });
      }

      /* ── MUTATION OBSERVER — handle Streamlit re-renders ─────── */
      new MutationObserver(()=>{
        initHolographic();
        initCountUp();
        initGauges();
        initSonar();
      }).observe(document.body,{childList:true,subtree:true});

      /* ── INIT ─────────────────────────────────────────────────── */
      function init(){
        initCursor();
        initBoot();
        initHolographic();
        initCountUp();
        initGauges();
        initRipples();
        initSonar();
      }

      document.readyState==='loading'
        ? document.addEventListener('DOMContentLoaded',init)
        : init();

      setTimeout(init, 600); // Streamlit async fallback
    })();
    </script>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SVG ASSETS
# ═══════════════════════════════════════════════════════════════════════════════
def _u(s): return f"data:image/svg+xml;base64,{base64.b64encode(s.encode()).decode()}"

LOGO_SVG = base64.b64encode(
    b'<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">'
    b'<defs><linearGradient id="pg" x1="0" y1="0" x2="1" y2="1">'
    b'<stop offset="0%" stop-color="#c9a84c"/>'
    b'<stop offset="50%" stop-color="#00e0b0"/>'
    b'<stop offset="100%" stop-color="#fff"/>'
    b'</linearGradient></defs>'
    b'<circle cx="24" cy="24" r="22" fill="none" stroke="url(#pg)" stroke-width="0.8" opacity=".3"/>'
    b'<path d="M24 6L24 42" stroke="url(#pg)" stroke-width="1.5" stroke-linecap="round"/>'
    b'<path d="M12 24Q24 32 36 24" fill="none" stroke="url(#pg)" stroke-width="1.5" stroke-linecap="round"/>'
    b'</svg>'
).decode()

ICONS = {
    "VERIFIED":     _u('<svg viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><circle cx="14" cy="14" r="12" fill="none" stroke="#00e0b0" stroke-width="1" opacity=".2"/><circle cx="14" cy="14" r="7.5" fill="#061a14" stroke="#00e0b0" stroke-width="1.5"/><polyline points="10,14.5 12.8,17 18,10.5" fill="none" stroke="#00e0b0" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'),
    "GHOST BUNKER": _u('<svg viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><circle cx="14" cy="14" r="12" fill="none" stroke="#ff2a55" stroke-width="1" stroke-dasharray="4 3"/><circle cx="14" cy="14" r="7.5" fill="#1a0508" stroke="#ff2a55" stroke-width="1.5"/><g stroke="#ff2a55" stroke-width="2.5" stroke-linecap="round"><line x1="11" y1="11" x2="17" y2="17"/><line x1="17" y1="11" x2="11" y2="17"/></g></svg>'),
    "STAT OUTLIER": _u('<svg viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="4" width="20" height="20" rx="5" fill="none" stroke="#c9a84c" stroke-width="1.2"/><circle cx="14" cy="14" r="4.5" fill="#0e0a1e" stroke="#c9a84c" stroke-width="1.5"/><circle cx="14" cy="14" r="1.8" fill="#c9a84c"/></svg>')
}

STATUS_COLORS = {
    "VERIFIED":     "#00e0b0",
    "GHOST BUNKER": "#ff2a55",
    "STAT OUTLIER": "#c9a84c"
}

REQUIRED_RAW_COLS = [
    'FO_A','FO_L','MGO_A','MGO_L',
    'Bunk_FO','Bunk_MGO','Bunk_MELO','Bunk_HSCYLO','Bunk_LSCYLO','Bunk_GELO','Bunk_CYLO',
    'MELO_R','HSCYLO_R','LSCYLO_R','GELO_R','CYLO_R',
    'Speed','DistLeg','TotalDist','CargoQty','Voy','Port','AD','Date','Time'
]

# ═══════════════════════════════════════════════════════════════════════════════
# FLEET MASTER
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def load_fleet_master():
    db_path = Path(__file__).parent / 'fleet_master.csv'
    if db_path.exists():
        try: return pd.read_csv(db_path).set_index('Vessel_Name')
        except Exception: pass
    return pd.DataFrame(columns=['Min_Speed_kn','Ghost_Tol_Sea','Ghost_Tol_Port'])

fleet_db = load_fleet_master()

# ═══════════════════════════════════════════════════════════════════════════════
# FORENSIC UTILITIES  ← UNTOUCHED
# ═══════════════════════════════════════════════════════════════════════════════
def _sn(val):
    if pd.isna(val): return np.nan
    s = re.sub(r'[^\d.\-]','',str(val).strip())
    try: return float(s) if s and s not in ('.', '-', '-.') else np.nan
    except ValueError: return np.nan

def _sn0(val):
    v = _sn(val); return 0.0 if np.isnan(v) else v

def _parse_dt(d_val, t_val):
    try:
        if pd.isna(d_val): return pd.NaT
        ds = str(d_val).strip()
        ds = re.sub(r'20224','2024',ds); ds = re.sub(r'20023','2023',ds)
        ds = re.sub(r'(\d+)\s+([A-Za-z]+)\.?\s+(\d{4})',
                    lambda m:f"{m.group(3)}-{m.group(2)[:3]}-{m.group(1).zfill(2)}", ds)
        p = pd.to_datetime(ds, errors='coerce')
        if pd.isna(p): return pd.NaT
        d_str = p.strftime('%Y-%m-%d')
        t_str = '00:00'
        if not pd.isna(t_val):
            tr = re.sub(r'[HhLlTtUuCc\s]','',str(t_val).strip())
            m  = re.match(r'^(\d{1,2}):(\d{2})',tr)
            if m: t_str = f"{m.group(1).zfill(2)}:{m.group(2)}"
        return pd.to_datetime(f"{d_str} {t_str}", errors='coerce')
    except Exception: return pd.NaT

def compute_dqi(r1, r2, days, phys_burn, drift, ghost_tol):
    if days <= 0 or pd.isna(phys_burn): return 0
    scores = [100.0]
    if phys_burn >= ghost_tol: scores.append(100.0)
    else: scores.append(max(0.0, 100 - abs(phys_burn)*5))
    tol = max(30.0, 0.03*max(_sn0(r1.get('FO_A')), _sn0(r2.get('FO_A'))))
    if tol > 0: scores.append(math.exp(-0.5*((drift)/tol)**2)*100)
    else: scores.append(0.0)
    return int(sum(scores)/len(scores))

# ═══════════════════════════════════════════════════════════════════════════════
# SEMANTIC PARSE  ← UNTOUCHED
# ═══════════════════════════════════════════════════════════════════════════════
def semantic_parse(file_bytes, file_name):
    vn_raw = re.sub(r'\.[^.]+$','',file_name).strip()
    vname  = re.sub(r'[_\-]+',' ',vn_raw).upper()

    if file_name.lower().endswith('.xlsx'):
        df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, engine='openpyxl')
    else:
        df_raw = pd.read_csv(io.StringIO(file_bytes.decode('latin-1',errors='replace')),
                             header=None, on_bad_lines='skip')

    if df_raw.empty or len(df_raw) < 4: raise ValueError("File is empty or severely malformed.")

    header_idx, cols_found = 0, {}
    for i in range(min(60, len(df_raw))):
        vals = [str(x).upper() for x in df_raw.iloc[i].values if pd.notna(x)]
        if any(k in v for v in vals for k in ['DATE','DAY']) and \
           any(k in v for v in vals for k in ['PORT','LOC']):
            header_idx    = i
            top_header    = df_raw.iloc[i].ffill()
            bottom_header = df_raw.iloc[i+1] if i+1 < len(df_raw) \
                            else pd.Series([np.nan]*len(df_raw.columns))
            for j in range(len(df_raw.columns)):
                c1 = str(top_header.iloc[j]).upper().strip()    if pd.notna(top_header.iloc[j])    else ""
                c2 = str(bottom_header.iloc[j]).upper().strip() if pd.notna(bottom_header.iloc[j]) else ""
                c_comb = f"{c1} {c2}".strip()
                if   'VOY'   in c_comb:                            cols_found['Voy']       = j
                elif 'PORT'  in c_comb or 'LOC' in c_comb:        cols_found['Port']      = j
                elif 'A/D'   in c_comb or c_comb=='AD' or 'STATUS' in c_comb:
                                                                   cols_found['AD']        = j
                elif 'SPEED' in c_comb:                            cols_found['Speed']     = j
                elif 'CARGO' in c_comb or 'QTY' in c_comb:        cols_found['CargoQty']  = j
                elif 'DATE'  in c_comb or 'DAY' in c_comb:        cols_found['Date']      = j
                elif 'TIME'  in c_comb and 'TOTAL' not in c_comb: cols_found['Time']      = j
                elif 'DIST'  in c_comb and 'LEG'   in c_comb:     cols_found['DistLeg']   = j
                elif 'DIST'  in c_comb and 'TOTAL' in c_comb:     cols_found['TotalDist'] = j
                elif 'BUNKER' in c1 or 'RECEIV' in c1:
                    if   'FO'     in c2 and 'MGO' not in c2:      cols_found['Bunk_FO']     = j
                    elif 'MGO'    in c2:                           cols_found['Bunk_MGO']    = j
                    elif 'MELO'   in c2:                           cols_found['Bunk_MELO']   = j
                    elif 'HSCYLO' in c2 or 'HS CYL' in c2:        cols_found['Bunk_HSCYLO'] = j
                    elif 'LSCYLO' in c2 or 'LS CYL' in c2:        cols_found['Bunk_LSCYLO'] = j
                    elif 'CYLO'   in c2 or 'CYL OIL' in c2:       cols_found['Bunk_CYLO']   = j
                    elif 'GELO'   in c2:                           cols_found['Bunk_GELO']   = j
                elif 'ROB' in c1 or 'REMAIN' in c1:
                    if   'FO A'   in c2 or 'FO ACT' in c2:        cols_found['FO_A']      = j
                    elif 'FO L'   in c2 or 'FO LED' in c2:        cols_found['FO_L']      = j
                    elif 'MGO A'  in c2:                           cols_found['MGO_A']     = j
                    elif 'MGO L'  in c2:                           cols_found['MGO_L']     = j
                    elif 'MELO'   in c2:                           cols_found['MELO_R']    = j
                    elif 'HSCYLO' in c2 or 'HS CYL' in c2:        cols_found['HSCYLO_R']  = j
                    elif 'LSCYLO' in c2 or 'LS CYL' in c2:        cols_found['LSCYLO_R']  = j
                    elif 'CYLO'   in c2 or 'CYL OIL' in c2:       cols_found['CYLO_R']    = j
                    elif 'GELO'   in c2:                           cols_found['GELO_R']    = j
            break

    df = df_raw.iloc[header_idx+1:].copy().reset_index(drop=True)
    for std_name, exc_idx in cols_found.items():
        df[std_name] = df.iloc[:, exc_idx]

    missing = [col for col in REQUIRED_RAW_COLS if col not in df.columns]
    for req in missing:
        if req in ['FO_A','FO_L','MGO_A','MGO_L','MELO_R','HSCYLO_R','LSCYLO_R','GELO_R','CYLO_R']:
            df[req] = np.nan
        elif req in ['Voy','Port','AD','Date','Time']:
            df[req] = ''
        else:
            df[req] = 0.0

    df['Datetime'] = df.apply(lambda r: _parse_dt(r.get('Date'), r.get('Time')), axis=1)
    df = df.dropna(subset=['Datetime']).sort_values('Datetime').reset_index(drop=True)
    df['AD'] = df['AD'].apply(
        lambda v: 'D' if str(v).upper().strip() in ['D','DEP','SBE','FAOP']
        else ('A' if str(v).upper().strip().startswith('A') else v)
    )
    return df, vname

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MACHINE  ← UNTOUCHED
# ═══════════════════════════════════════════════════════════════════════════════
def build_state_machine(df, min_speed, ghost_sea, ghost_port):
    ad_events = df[df['AD'].isin(['A','D'])].copy()
    if len(ad_events) < 2: raise ValueError("Insufficient A/D events to construct a timeline.")

    ad_events['Prev_AD'] = ad_events['AD'].shift(1)
    ad_events = ad_events[ad_events['AD'] != ad_events['Prev_AD']].drop(columns=['Prev_AD']).copy()

    trips, cum_drift = [], []
    for i in range(len(ad_events)-1):
        r1, r2 = ad_events.iloc[i], ad_events.iloc[i+1]
        idx1, idx2 = r1.name, r2.name
        status, flags = 'VERIFIED', []
        phys_burn, log_burn, drift, daily_burn, days = np.nan, np.nan, np.nan, np.nan, 0.0

        phase = 'SEA' if r1['AD'] == 'D' else 'PORT'
        days  = (r2['Datetime']-r1['Datetime']).total_seconds()/86400.0
        if days <= 0: days = 0.02; flags.append("Time Delta Fallback Applied")

        start_rob, end_rob = _sn(r1.get('FO_A')), _sn(r2.get('FO_A'))
        if pd.isna(start_rob) or pd.isna(end_rob):
            status = 'QUARANTINE_ROB'; flags.append("Missing Physical Tank Sounding")

        if r1['AD'] == 'D' and not pd.isna(start_rob):
            fol = _sn(r1.get('FO_L'))
            cum_drift.append({'dt':r1['Datetime'],
                              'gap':start_rob-(fol if not pd.isna(fol) else start_rob),
                              'port':str(r1.get('Port',''))[:20]})

        window = df.loc[idx1+1:idx2]
        if phase == 'PORT':
            bfo      = _sn0(df.loc[idx1:idx2,'Bunk_FO'].sum())
            b_melo   = _sn0(df.loc[idx1:idx2,'Bunk_MELO'].sum())
            b_hscylo = _sn0(df.loc[idx1:idx2,'Bunk_HSCYLO'].sum())
            b_lscylo = _sn0(df.loc[idx1:idx2,'Bunk_LSCYLO'].sum())
            b_cylo   = _sn0(df.loc[idx1:idx2,'Bunk_CYLO'].sum())
            b_gelo   = _sn0(df.loc[idx1:idx2,'Bunk_GELO'].sum())
        else:
            bfo      = _sn0(window['Bunk_FO'].sum())
            b_melo   = _sn0(window['Bunk_MELO'].sum())
            b_hscylo = _sn0(window['Bunk_HSCYLO'].sum())
            b_lscylo = _sn0(window['Bunk_LSCYLO'].sum())
            b_cylo   = _sn0(window['Bunk_CYLO'].sum())
            b_gelo   = _sn0(window['Bunk_GELO'].sum())

        dist  = _sn0(window['DistLeg'].sum())
        if dist <= 0 and phase == 'SEA':
            dist = max(0, _sn0(r2.get('TotalDist'))-_sn0(r1.get('TotalDist')))

        speed = window['Speed'].replace(0,np.nan).mean() if not window['Speed'].empty else np.nan
        if pd.isna(speed): speed = dist/(days*24.0) if days > 0 else 0.0

        melo_c     = max(0, (_sn0(r1.get('MELO_R'))   -_sn0(r2.get('MELO_R')))   +b_melo)
        hscylo_c   = max(0, (_sn0(r1.get('HSCYLO_R')) -_sn0(r2.get('HSCYLO_R'))) +b_hscylo)
        lscylo_c   = max(0, (_sn0(r1.get('LSCYLO_R')) -_sn0(r2.get('LSCYLO_R'))) +b_lscylo)
        cylo_gen_c = max(0, (_sn0(r1.get('CYLO_R'))   -_sn0(r2.get('CYLO_R')))   +b_cylo)
        gelo_c     = max(0, (_sn0(r1.get('GELO_R'))   -_sn0(r2.get('GELO_R')))   +b_gelo)

        dqi = 0
        if status == 'VERIFIED':
            phys_burn  = (start_rob-end_rob)+bfo
            log_start  = _sn(r1.get('FO_L')) if not pd.isna(_sn(r1.get('FO_L'))) else start_rob
            log_end    = _sn(r2.get('FO_L')) if not pd.isna(_sn(r2.get('FO_L'))) else end_rob
            log_burn   = (log_start-log_end)+bfo
            drift      = phys_burn-log_burn
            daily_burn = phys_burn/days
            if phase == 'PORT' and phys_burn < ghost_port:
                status = 'GHOST BUNKER'; flags.append("Missing Port Bunker Receipt")
            elif phase == 'SEA' and phys_burn < ghost_sea:
                status = 'GHOST BUNKER'; flags.append("Negative Sea Burn Impossibility")
            dqi = compute_dqi(r1,r2,days,phys_burn,drift,
                              ghost_tol=(ghost_port if phase=='PORT' else ghost_sea))

        trips.append({
            'Indicator':     ICONS.get(status,ICONS['VERIFIED']) if 'QUARANTINE' not in status else '⛔',
            'Timeline':      f"{r1['Datetime'].strftime('%d %b %y')} → {r2['Datetime'].strftime('%d %b %y')}",
            'Date_Start_TS': r1['Datetime'],
            'Phase':         phase,
            'Condition':     'LADEN' if _sn0(r1.get('CargoQty',0))>100 else 'BALLAST',
            'Voy':           str(r1.get('Voy','')).strip(),
            'Route':         f"{str(r1.get('Port',''))[:15]} → {str(r2.get('Port',''))[:15]}"
                             if phase=='SEA' else f"Port Idle: {str(r1.get('Port',''))[:15]}",
            'Days':          round(days,2),
            'Dist_NM':       round(dist,0),
            'Speed_kn':      round(speed,1),
            'CargoQty':      _sn0(r1.get('CargoQty',0)),
            'FO_A_Start':    start_rob  if status=='VERIFIED' else np.nan,
            'Bunk_FO':       bfo,
            'FO_A_End':      end_rob    if status=='VERIFIED' else np.nan,
            'Phys_Burn':     round(phys_burn,1),
            'Log_Burn':      round(log_burn,1),
            'Drift_MT':      round(drift,1),
            'Daily_Burn':    round(daily_burn,1) if status=='VERIFIED' else np.nan,
            'MELO_L':        round(melo_c,0),
            'HSCYLO_L':      round(hscylo_c,0),
            'LSCYLO_L':      round(lscylo_c,0),
            'CYLO_GEN_L':    round(cylo_gen_c,0),
            'GELO_L':        round(gelo_c,0),
            'Total_CYLO':    round(hscylo_c+lscylo_c+cylo_gen_c,0),
            'DQI':           int(dqi),
            'Status':        status,
            'Flags':         ', '.join(flags) if flags else ''
        })

    trip_df = pd.DataFrame(trips)
    if len(trip_df) >= 4:
        for cond in ['LADEN','BALLAST']:
            ver = trip_df[(trip_df['Status']=='VERIFIED')&(trip_df['Phase']=='SEA')&
                          (trip_df['Phys_Burn']>0)&(trip_df['Condition']==cond)]
            if len(ver) >= 4:
                q1,q3 = ver['Daily_Burn'].quantile(0.25), ver['Daily_Burn'].quantile(0.75)
                iqr   = q3-q1
                if iqr > 0:
                    lo,hi = q1-2.0*iqr, q3+2.0*iqr
                    mask  = ((trip_df['Status']=='VERIFIED')&(trip_df['Phase']=='SEA')&
                             (trip_df['Condition']==cond)&
                             ((trip_df['Daily_Burn']<lo)|(trip_df['Daily_Burn']>hi)))
                    trip_df.loc[mask,'Status']    = 'STAT OUTLIER'
                    trip_df.loc[mask,'Indicator'] = ICONS['STAT OUTLIER']
    return trip_df, cum_drift

# ═══════════════════════════════════════════════════════════════════════════════
# AI PHYSICS ENGINE  ← UNTOUCHED
# ═══════════════════════════════════════════════════════════════════════════════
def execute_ai_physics(trip_df, min_speed):
    ai_status_msg = "Enterprise AI Optimized."
    if not HAS_ML: return trip_df, "AI Offline: Missing scikit-learn or xgboost."
    if trip_df.empty: return trip_df, "AI Offline: Empty ledger."

    for col in ['AI_Exp','HM_Base','Stoch_Var','SHAP_Base','SHAP_Propulsion','SHAP_Mass',
                'SHAP_Kinematics','SHAP_Season','SHAP_Degradation',
                'Exp_Lower','Exp_Upper','Mahalanobis','MD_Threshold','P_Value']:
        if col not in trip_df.columns: trip_df[col] = np.nan

    try:
        sea_mask = ((trip_df['Phase']=='SEA')&(trip_df['Status']=='VERIFIED')&
                    (trip_df['Speed_kn']>=min_speed))
        if sea_mask.sum() < 8:
            raise ValueError(f"Insufficient valid Sea Legs ({sea_mask.sum()}). Minimum 8 required.")

        ml = trip_df.loc[sea_mask].copy()
        ml['True_Mass']     = ml['CargoQty'].fillna(0)+ml['FO_A_Start'].fillna(0)
        ml['SOG']           = ml['Dist_NM']/np.maximum(ml['Days']*24,0.1)
        ml['Kin_Delta']     = (ml['Speed_kn']-ml['SOG']).clip(-3.0,3.0)
        ml['Accel_Penalty'] = ml['Speed_kn'].diff().fillna(0.0).clip(-2.0,2.0)
        ml['Speed_Cubed']   = ml['Speed_kn']**3
        ml['Season_Sin']    = np.sin(2*np.pi*ml['Date_Start_TS'].dt.month.fillna(6)/12.0)
        ml['Season_Cos']    = np.cos(2*np.pi*ml['Date_Start_TS'].dt.month.fillna(6)/12.0)
        epoch = trip_df['Date_Start_TS'].min()
        ml['Days_Since_Epoch'] = (ml['Date_Start_TS']-epoch).dt.total_seconds()/86400.0

        features      = ['Speed_kn','Speed_Cubed','True_Mass','Kin_Delta','Accel_Penalty',
                         'Season_Sin','Season_Cos','Days_Since_Epoch']
        maha_features = ['Speed_kn','True_Mass','Accel_Penalty','Season_Sin','Season_Cos','Days_Since_Epoch']
        ml[features]  = ml[features].fillna(0.0)

        k_array = ml['Daily_Burn']/((ml['True_Mass']**(2/3))*ml['Speed_Cubed']+1e-6)
        q25     = np.percentile(k_array,25)
        best_k  = np.median(k_array[k_array<=q25])
        ml['HM_Base'] = best_k*(ml['True_Mass']**(2/3))*ml['Speed_Cubed']
        trip_df.loc[sea_mask,'HM_Base'] = ml['HM_Base']

        y_delta = ml['Daily_Burn']-ml['HM_Base']
        X_train = ml[features]; weights = ml['Days'].clip(0.1,30.0)
        if y_delta.var() < 0.05: raise ValueError("Target variance too low.")

        kf = KFold(n_splits=min(5,len(X_train)), shuffle=True, random_state=42)
        oof_preds = np.zeros(len(X_train))
        for ti,vi in kf.split(X_train):
            m = XGBRegressor(n_estimators=100,max_depth=3,learning_rate=0.06,random_state=42)
            m.fit(X_train.iloc[ti],y_delta.iloc[ti],sample_weight=weights.iloc[ti])
            oof_preds[vi] = m.predict(X_train.iloc[vi])

        oof_residuals = np.abs(y_delta-oof_preds)
        model = XGBRegressor(n_estimators=100,max_depth=3,learning_rate=0.06,random_state=42)
        model.fit(X_train,y_delta,sample_weight=weights)
        preds = ml['HM_Base']+model.predict(X_train)

        var_model = XGBRegressor(n_estimators=40,max_depth=2,learning_rate=0.05,random_state=42)
        var_model.fit(X_train,oof_residuals,sample_weight=weights)
        var_preds_train  = np.maximum(var_model.predict(X_train),0.01)
        conformal_scores = oof_residuals/var_preds_train

        n     = len(conformal_scores)
        q_val = min(1.0,np.ceil((n+1)*0.90)/n) if n>0 else 0.90
        q90   = np.quantile(conformal_scores,q_val)
        stoch_margin = np.maximum(var_model.predict(X_train)*q90,0.5)

        p_vals = []
        for i,row_idx in enumerate(ml.index):
            cs  = np.abs(ml.loc[row_idx,'Daily_Burn']-preds.iloc[i])/var_preds_train[i]
            ple = np.sum(conformal_scores<=cs)/len(conformal_scores)
            p_vals.append((1.0-ple)*100)
        trip_df.loc[sea_mask,'P_Value'] = p_vals

        X_maha = ml[maha_features].values
        lw     = LedoitWolf().fit(X_maha)
        md     = np.sqrt(np.maximum(lw.mahalanobis(X_maha),0))
        trip_df.loc[sea_mask,'Mahalanobis']  = md
        trip_df.loc[sea_mask,'MD_Threshold'] = np.percentile(md,95)

        explainer = shap.TreeExplainer(model)
        sv        = explainer.shap_values(X_train)
        base_val  = explainer.expected_value[0] \
                    if isinstance(explainer.expected_value,np.ndarray) \
                    else explainer.expected_value

        trip_df.loc[sea_mask,'AI_Exp']           = preds.round(1)
        trip_df.loc[sea_mask,'Stoch_Var']        = stoch_margin.round(1)
        trip_df.loc[sea_mask,'SHAP_Base']        = base_val
        trip_df.loc[sea_mask,'SHAP_Propulsion']  = sv[:,0]+sv[:,1]
        trip_df.loc[sea_mask,'SHAP_Mass']        = sv[:,2]
        trip_df.loc[sea_mask,'SHAP_Kinematics']  = sv[:,3]+sv[:,4]
        trip_df.loc[sea_mask,'SHAP_Season']      = sv[:,5]+sv[:,6]
        trip_df.loc[sea_mask,'SHAP_Degradation'] = sv[:,7]
        trip_df.loc[sea_mask,'Exp_Lower']        = preds-stoch_margin
        trip_df.loc[sea_mask,'Exp_Upper']        = preds+stoch_margin

        outlier_mask = sea_mask&((trip_df['Daily_Burn']<trip_df['Exp_Lower'])|
                                 (trip_df['Daily_Burn']>trip_df['Exp_Upper']))
        trip_df.loc[outlier_mask,'Status'] = 'STAT OUTLIER'

    except ValueError as e: ai_status_msg = f"AI Offline: {str(e)}"
    except Exception as e:
        ai_status_msg = f"AI Critical Exception: {str(e)}"
        print(traceback.format_exc())
    return trip_df, ai_status_msg

# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE  ← UNTOUCHED
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def run_pipeline(file_bytes, filename, min_speed, ghost_sea, ghost_port):
    try:
        parsed_df, vname   = semantic_parse(file_bytes, filename)
        trip_df, cum_drift = build_state_machine(parsed_df, min_speed, ghost_sea, ghost_port)
        trip_df, ai_msg    = execute_ai_physics(trip_df, min_speed)

        quarantined = len(trip_df[trip_df['Status'].str.contains('QUARANTINE')])
        valid_sea   = trip_df[(trip_df['Phase']=='SEA')&(trip_df['Status']=='VERIFIED')]
        avg_sea     = valid_sea['Phys_Burn'].sum()/valid_sea['Days'].sum() \
                      if valid_sea['Days'].sum()>0 else 0.0
        trip_df['Total_CYLO'] = (
            trip_df.get('HSCYLO_L',  pd.Series([0],dtype=float))+
            trip_df.get('LSCYLO_L',  pd.Series([0],dtype=float))+
            trip_df.get('CYLO_GEN_L',pd.Series([0],dtype=float))
        )
        summary = {
            'vname':        vname,
            'integrity':    round((len(trip_df)-quarantined)/len(trip_df)*100,1)
                            if not trip_df.empty else 0,
            'avg_dqi':      round(trip_df['DQI'].mean(),0) if not trip_df.empty else 0,
            'total_fuel':   round(trip_df['Phys_Burn'].sum(skipna=True),1),
            'avg_sea_burn': round(avg_sea,1),
            'total_nm':     round(trip_df['Dist_NM'].sum(),0),
            'total_days':   round(trip_df['Days'].sum(),1),
            'total_melo':   round(trip_df.get('MELO_L',pd.Series([0])).sum(),0),
            'total_cylo':   round(trip_df['Total_CYLO'].sum(),0),
            'cycles':       len(trip_df),
            'quarantined':  quarantined,
            'anomalies':    len(trip_df[trip_df['Status'].isin(['GHOST BUNKER','STAT OUTLIER'])]),
            'ai_msg':       ai_msg
        }
        return trip_df, summary, cum_drift, None
    except ValueError as e: return pd.DataFrame(), None, None, f"Parsing Rejected: {str(e)}"
    except Exception as e:  return pd.DataFrame(), None, None, f"System Crash: {str(e)}"

# ═══════════════════════════════════════════════════════════════════════════════
# PLOTLY ENGINE  ← margin fix maintained; charts UNTOUCHED
# ═══════════════════════════════════════════════════════════════════════════════
_BL = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    hovermode='x unified',
    hoverlabel=dict(
        bgcolor="rgba(5,9,14,.97)",
        bordercolor="rgba(0,224,176,.55)",
        font=dict(family='Geist Mono',color='#f8fafc',size=13)
    ),
    font=dict(family='Hanken Grotesk',color='#f8fafc'),
    transition=dict(duration=800,easing='cubic-in-out')
)
_M  = dict(l=15,r=15,t=85,b=30)
_AX = dict(
    gridcolor='rgba(255,255,255,0.02)',
    zerolinecolor='rgba(255,255,255,0.05)',
    tickfont=dict(family='Geist Mono',size=11,color='#475569'),
    showspikes=True,
    spikecolor="rgba(0,224,176,0.6)",
    spikethickness=1,
    spikedash="solid"
)

def chart_fuel(df):
    sea  = df[(df['Phase']=='SEA') &(~df['Status'].str.contains('QUARANTINE'))]
    port = df[(df['Phase']=='PORT')&(~df['Status'].str.contains('QUARANTINE'))]
    fig  = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[0.7,0.3],vertical_spacing=0.08)
    if not sea.empty:
        fig.add_trace(go.Bar(x=sea['Timeline'],y=sea['Phys_Burn'],name='Sea Fuel',
            marker_color='rgba(0,224,176,.15)',marker_line_color='#00e0b0',marker_line_width=1.5),row=1,col=1)
    if not port.empty:
        fig.add_trace(go.Bar(x=port['Timeline'],y=port['Phys_Burn'],name='Port Fuel',
            marker_color='rgba(255,42,85,.15)',marker_line_color='#ff2a55',marker_line_width=1.5),row=1,col=1)
    if not sea.empty:
        fig.add_trace(go.Scatter(x=sea['Timeline'],y=sea['Daily_Burn'],name='Sea MT/day',
            mode='lines+markers',line=dict(color='#00e0b0',width=3,shape='spline'),
            fill='tozeroy',fillcolor='rgba(0,224,176,.05)',
            marker=dict(size=8,color='#051014',line=dict(color='#00e0b0',width=2))),row=1,col=1)
        fig.add_trace(go.Scatter(x=sea['Timeline'],y=sea['Speed_kn'],name='Sea Speed',
            mode='lines+markers',line=dict(color='#c9a84c',width=3,shape='spline'),
            fill='tozeroy',fillcolor='rgba(201,168,76,.05)',
            marker=dict(size=8,color='#051014',line=dict(color='#c9a84c',width=2))),row=2,col=1)
    fig.update_layout(**_BL,margin=_M,
        title=dict(text='Tri-State Fuel Consumption & Kinematics',
                   font=dict(size=24,family='Bricolage Grotesque',color='#fff')),
        barmode='group',showlegend=True,height=700,
        legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='right',x=1))
    fig.update_xaxes(tickangle=-45,automargin=True,**_AX)
    fig.update_yaxes(**_AX)
    return fig

def chart_lube(df):
    fig = go.Figure()
    if df.get('MELO_L',   pd.Series([0])).sum()>0:
        fig.add_trace(go.Bar(x=df['Timeline'],y=df['MELO_L'],name='MELO',
            marker_color='rgba(0,224,176,.15)',marker_line_color='#00e0b0',marker_line_width=1.5))
    if df.get('Total_CYLO',pd.Series([0])).sum()>0:
        fig.add_trace(go.Bar(x=df['Timeline'],y=df['Total_CYLO'],name='CYLO (All)',
            marker_color='rgba(255,42,85,.15)',marker_line_color='#ff2a55',marker_line_width=1.5))
    if df.get('GELO_L',   pd.Series([0])).sum()>0:
        fig.add_trace(go.Bar(x=df['Timeline'],y=df['GELO_L'],name='GELO',
            marker_color='rgba(201,168,76,.15)',marker_line_color='#c9a84c',marker_line_width=1.5))
    fig.update_layout(**_BL,margin=_M,
        title=dict(text='Lubricant Consumption (Liters)',
                   font=dict(size=24,family='Bricolage Grotesque',color='#fff')),
        barmode='group',showlegend=True,height=500,
        yaxis=dict(title='L',**_AX),xaxis=dict(automargin=True,**_AX))
    fig.update_xaxes(tickangle=-45)
    return fig

def chart_cum_drift(cum_drift):
    if not cum_drift: return None
    cdf = pd.DataFrame(cum_drift)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cdf['dt'],y=cdf['gap'],mode='lines+markers',name='A−L Gap',
        line=dict(color='#c9a84c',width=3),
        marker=dict(size=8,color='#051014',line=dict(color='#c9a84c',width=2)),
        fill='tozeroy',fillcolor='rgba(201,168,76,.08)'))
    fig.add_hline(y=0,line=dict(color='rgba(255,255,255,.15)',width=1))
    fig.update_layout(**_BL,margin=_M,
        title=dict(text='Physical vs Logged Mass Drift',
                   font=dict(size=24,family='Bricolage Grotesque',color='#fff')),
        height=500,yaxis=dict(title='FO_A − FO_L (MT)',**_AX),xaxis=dict(automargin=True,**_AX))
    fig.update_xaxes(tickangle=-45)
    return fig

# ═══════════════════════════════════════════════════════════════════════════════
# VESSEL CARD — animated circular integrity gauge
# ═══════════════════════════════════════════════════════════════════════════════
def render_vessel_card(sum_data):
    ic = STATUS_COLORS['VERIFIED']     if sum_data['integrity'] >= 80 else \
         STATUS_COLORS['STAT OUTLIER'] if sum_data['integrity'] >= 50 else \
         STATUS_COLORS['GHOST BUNKER']

    r_val   = 50
    circ    = 2 * math.pi * r_val          # ≈ 314.16
    offset  = circ * (1 - sum_data['integrity'] / 100)
    ri, gi, bi = int(ic[1:3],16), int(ic[3:5],16), int(ic[5:7],16)

    gauge = f"""
    <svg viewBox="0 0 120 120" class="integrity-gauge">
        <circle cx="60" cy="60" r="{r_val}" class="gauge-track"/>
        <circle cx="60" cy="60" r="{r_val}" class="gauge-arc"
            stroke="{ic}"
            stroke-dasharray="{circ:.2f}"
            stroke-dashoffset="{circ:.2f}"
            data-offset="{offset:.2f}"
            transform="rotate(-90 60 60)"
            style="filter:drop-shadow(0 0 10px rgba({ri},{gi},{bi},.65));
                   transition:stroke-dashoffset 1.9s cubic-bezier(0.16,1,0.3,1) .35s"/>
        <text x="60" y="58" text-anchor="middle" class="gauge-pct" style="fill:{ic}">{sum_data['integrity']:.0f}%</text>
        <text x="60" y="75" text-anchor="middle" class="gauge-label">INTEGRITY</text>
    </svg>"""

    return f"""
    <div class="vcard" style="
        background:var(--glass-bg);
        backdrop-filter:blur(48px) saturate(180%);
        -webkit-backdrop-filter:blur(48px) saturate(180%);
        border:1px solid var(--glass-border);
        border-radius:var(--r);
        padding:24px 32px;
        margin-bottom:24px;
        box-shadow:var(--glass-shadow);">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:24px">
            <div style="flex:1;min-width:0">
                <div class="vcard-name">{sum_data['vname']}</div>
                <div class="vcard-stats">
                    {sum_data['cycles']} LEGS&ensp;·&ensp;{sum_data['total_days']:.0f} DAYS&ensp;·&ensp;{int(sum_data['total_nm']):,} NM
                </div>
                <div class="vcard-ai">{sum_data['ai_msg']}</div>
            </div>
            <div class="integrity-gauge-wrapper">{gauge}</div>
        </div>
    </div>"""

# ═══════════════════════════════════════════════════════════════════════════════
# HUD RENDERER — data attributes enable JS count-up animation
# ═══════════════════════════════════════════════════════════════════════════════
def render_hud(sum_data):
    i_fuel  = '<svg viewBox="0 0 24 24"><path d="M12 2c-5.33 4.55-8 8.48-8 11.8 0 4.98 3.8 8.2 8 8.2s8-3.22 8-8.2c0-3.32-2.67-7.25-8-11.8zM12 20c-3.35 0-6-2.57-6-6.2 0-2.34 1.95-5.44 6-9.14 4.05 3.7 6 6.79 6 9.14 0 3.63-2.65 6.2-6 6.2z"/></svg>'
    i_speed = '<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/></svg>'
    i_lube  = '<svg viewBox="0 0 24 24"><path d="M19.36 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.36 8.04A5.994 5.994 0 0 0 4 20h14c3.31 0 6-2.69 6-6 0-3.15-2.44-5.74-5.64-5.96z"/></svg>'
    i_alert = '<svg viewBox="0 0 24 24"><path d="M12 2L1 21h22M12 6l7.53 13H4.47M11 10v4h2v-4m-2 6v2h2v-2"/></svg>'
    i_lock  = '<svg viewBox="0 0 24 24"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM9 6c0-1.66 1.34-3 3-3s3 1.34 3 3v2H9V6zm9 14H6V10h12v10zm-6-3c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z"/></svg>'

    w = " hud-warn" if sum_data['anomalies']   > 0 else ""
    q = " hud-warn" if sum_data['quarantined'] > 0 else ""

    ac = '#ff2a55' if sum_data['anomalies']   > 0 else '#fff'
    qc = '#ff2a55' if sum_data['quarantined'] > 0 else '#fff'

    def card(cls, title, icon, target, dec, val_str, sub):
        return f"""
        <div class="hud-card{cls}">
            <div class="hud-header">
                <div class="hud-title">{title}</div>
                <div class="hud-icon">{icon}</div>
            </div>
            <div class="hud-val" data-target="{target}" data-dec="{dec}">{val_str}</div>
            <div class="hud-sub">{sub}</div>
        </div>"""

    st.markdown(f"""
    <div class="hud-grid">
        {card('', 'Verified Fuel',  i_fuel,  sum_data['total_fuel'],   1, f"{sum_data['total_fuel']:,.1f}",  'Metric Tons')}
        {card('', 'Avg Sea Burn',   i_speed, sum_data['avg_sea_burn'], 1, f"{sum_data['avg_sea_burn']:.1f}", 'MT / Day')}
        {card('', 'Total MELO',     i_lube,  int(sum_data['total_melo']), 0, f"{int(sum_data['total_melo']):,}", 'Liters')}
        {card('', 'Total CYLO',     i_lube,  int(sum_data['total_cylo']), 0, f"{int(sum_data['total_cylo']):,}", 'Liters')}
        {card(w,  'Anomalies',      i_alert, sum_data['anomalies'],    0,
              f'<span style="color:{ac}">{sum_data["anomalies"]}</span>', 'Flagged Deviations')}
        {card(q,  'Quarantined',    i_lock,  sum_data['quarantined'],  0,
              f'<span style="color:{qc}">{sum_data["quarantined"]}</span>', 'Missing Data Legs')}
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FRONTEND
# ═══════════════════════════════════════════════════════════════════════════════

# Hero
st.markdown(f"""
<div class="hero">
    <div class="hero-left">
        <div class="hero-logo-wrap">
            <img src="data:image/svg+xml;base64,{LOGO_SVG}"
                 class="hero-logo" alt="" style="width:56px;height:56px"/>
        </div>
        <div class="hero-title-container">
            <div class="hero-title">POSEIDON TITAN</div>
            <div class="hero-sub">Enterprise Forensic Engine</div>
        </div>
    </div>
    <div class="hero-badge">
        <span style="color:#fff">KERNEL</span>&ensp;Ledoit-Wolf · Conformal PIML<br>
        <span style="color:#fff">RENDER</span>&ensp;Holographic VDOM · Count-up<br>
        <span style="color:var(--acc)">BUILD</span>&ensp;v11.0.0 · Maximum Cinematic
    </div>
</div>
""", unsafe_allow_html=True)

# Inject the JS engine immediately after hero
inject_cinematic_engine()

# File uploader
files = st.file_uploader(
    'Upload vessel telemetry',
    accept_multiple_files=True,
    type=['xlsx','csv'],
    label_visibility='collapsed'
)

if not files:
    st.info("Drop vessel noon-report files to execute the Multi-Dimensional Forensic Audit.")
    st.stop()

fleet_results = []
for f in files:
    with st.spinner(f'Auditing {f.name}…'):
        file_bytes = f.getvalue()
        try:
            _, vname = semantic_parse(file_bytes, f.name)
            if vname in fleet_db.index:
                v_props    = fleet_db.loc[vname]
                min_speed  = float(v_props.get('Min_Speed_kn',  4.0))
                ghost_sea  = float(v_props.get('Ghost_Tol_Sea', -3.0))
                ghost_port = float(v_props.get('Ghost_Tol_Port',-5.0))
            else:
                min_speed, ghost_sea, ghost_port = 4.0, -3.0, -5.0

            trip_df, sum_data, cum_drift, err = run_pipeline(
                file_bytes, f.name, min_speed, ghost_sea, ghost_port
            )
        except Exception as e:
            err = f"Initialization Error: {str(e)}"; trip_df = pd.DataFrame()

    if err:
        st.error(f"**Rejected {f.name}:** {err}"); continue
    if trip_df.empty:
        st.warning(f"No valid events extracted from {f.name}. Check template schema."); continue

    fleet_results.append({'name':sum_data['vname'],'summary':sum_data,'df':trip_df})

    # Vessel header card with animated gauge
    st.markdown(render_vessel_card(sum_data), unsafe_allow_html=True)

    # HUD metrics with count-up
    render_hud(sum_data)
    st.markdown("<br>", unsafe_allow_html=True)

    t1,t2,t3,t4,t5,t6 = st.tabs([
        'IMMUTABLE LEDGER','COMMERCIAL P&L',
        'LUBE & DRIFT','AI DIGITAL TWIN',
        'FORENSIC PROOF','QUARANTINE LOG'
    ])

    # ── Tab 1 ─────────────────────────────────────────────────────────────────
    with t1:
        st.markdown(
            '<div style="margin-bottom:14px">'
            '<span style="font-family:var(--fm);font-size:.72rem;color:var(--acc);'
            'background:rgba(0,224,176,.05);padding:6px 14px;border-radius:6px;'
            'border:1px solid rgba(0,224,176,.13);">'
            '[START ROB] + [BUNKERS] − [END ROB] = [PHYSICAL BURN]'
            '</span></div>', unsafe_allow_html=True)
        dcfg = {
            'Indicator':  st.column_config.ImageColumn(' '),
            'Timeline':   st.column_config.TextColumn('TIMELINE',  width='medium'),
            'Phase':      st.column_config.TextColumn('LEG'),
            'Days':       st.column_config.NumberColumn('DAYS',     format='%.2f'),
            'Speed_kn':   st.column_config.NumberColumn('SPD',      format='%.1f'),
            'FO_A_Start': st.column_config.NumberColumn('START ROB',format='%.1f'),
            'Bunk_FO':    st.column_config.NumberColumn('+ BUNKERS',format='%.1f'),
            'FO_A_End':   st.column_config.NumberColumn('− END ROB',format='%.1f'),
            'Phys_Burn':  st.column_config.NumberColumn('= BURN',   format='%.1f'),
            'Log_Burn':   st.column_config.NumberColumn('LOG BURN', format='%.1f'),
            'DQI':        st.column_config.ProgressColumn('DQI',format='%d',min_value=0,max_value=100),
            'Daily_Burn': st.column_config.NumberColumn('MT/DAY',   format='%.1f'),
            'Total_CYLO': st.column_config.NumberColumn('CYLO (ALL)',format='%d'),
            'Status':     st.column_config.TextColumn('STATUS',    width='medium'),
        }
        st.dataframe(
            trip_df[['Indicator','Timeline','Phase','Days','Speed_kn',
                     'FO_A_Start','Bunk_FO','FO_A_End','Phys_Burn',
                     'Log_Burn','Drift_MT','Daily_Burn',
                     'Total_CYLO','MELO_L','GELO_L','DQI','Status']],
            column_config=dcfg, hide_index=True, use_container_width=True, height=500
        )
        buf = io.BytesIO()
        exp = trip_df.drop(columns=['Indicator','Date_Start_TS'],errors='ignore')
        with pd.ExcelWriter(buf,engine='openpyxl') as w: exp.to_excel(w,index=False,sheet_name='Audit')
        buf.seek(0)
        st.download_button('Export Tri-State Ledger', data=buf,
            file_name=f"{sum_data['vname'].replace(' ','_')}_LEDGER.xlsx",
            key=f"dl_{sum_data['vname']}")

    # ── Tab 2 ─────────────────────────────────────────────────────────────────
    with t2:
        voy = (trip_df[~trip_df['Status'].str.contains('QUARANTINE')]
               .groupby('Voy',dropna=False)
               .agg(
                   Total_Fuel =('Phys_Burn','sum'),
                   Sea_Days   =('Days',   lambda x: x[trip_df.loc[x.index,'Phase']=='SEA'].sum()),
                   Port_Days  =('Days',   lambda x: x[trip_df.loc[x.index,'Phase']=='PORT'].sum()),
                   Sea_Fuel   =('Phys_Burn',lambda x: x[trip_df.loc[x.index,'Phase']=='SEA'].sum()),
                   Bunkers    =('Bunk_FO','sum'),
                   Dist       =('Dist_NM','sum'),
                   HSCYLO     =('HSCYLO_L','sum'),
                   LSCYLO     =('LSCYLO_L','sum'),
               ).reset_index())
        voy['Sea MT/Day'] = np.where(voy['Sea_Days']>0, voy['Sea_Fuel']/voy['Sea_Days'], 0.0)
        st.dataframe(voy, hide_index=True, use_container_width=True)

    # ── Tab 3 ─────────────────────────────────────────────────────────────────
    with t3:
        c1, c2 = st.columns(2)
        with c1:
            if trip_df.get('MELO_L',pd.Series([0])).sum()+trip_df.get('Total_CYLO',pd.Series([0])).sum()>0:
                st.plotly_chart(chart_lube(trip_df),use_container_width=True,config={'displayModeBar':False})
            else: st.info('No lubricant consumption data detected.')
        with c2:
            if cum_drift:
                st.plotly_chart(chart_cum_drift(cum_drift),use_container_width=True,config={'displayModeBar':False})

    # ── Tab 4 ─────────────────────────────────────────────────────────────────
    with t4:
        st.plotly_chart(chart_fuel(trip_df),use_container_width=True,config={'displayModeBar':False})
        sea_df = trip_df[(trip_df['Phase']=='SEA')&(trip_df['Status']=='VERIFIED')]
        if 'AI_Exp' in sea_df.columns and sea_df['AI_Exp'].abs().sum()>0:
            fig_c = go.Figure()
            fig_c.add_trace(go.Scatter(
                x=sea_df['Timeline'].tolist()+sea_df['Timeline'].tolist()[::-1],
                y=sea_df['Exp_Upper'].tolist()+sea_df['Exp_Lower'].tolist()[::-1],
                fill='toself',fillcolor='rgba(123,104,238,.14)',
                line=dict(color='rgba(255,255,255,0)'),hoverinfo='skip',name='90% Conformal Interval'))
            fig_c.add_trace(go.Scatter(x=sea_df['Timeline'],y=sea_df['AI_Exp'],name='Expected Mean',
                line=dict(color='#7b68ee',width=2,dash='dash')))
            fig_c.add_trace(go.Scatter(x=sea_df['Timeline'],y=sea_df['Daily_Burn'],
                name='Audited Burn',mode='lines+markers',
                line=dict(color='#00e0b0',width=3),
                marker=dict(size=8,color='#051014',line=dict(color='#00e0b0',width=2))))
            fig_c.update_layout(**_BL,margin=_M,
                title=dict(text='Conformal Propulsion Bounds (Verified Sea Legs)',
                           font=dict(size=22,family='Bricolage Grotesque',color='#fff')),
                height=700,yaxis=dict(title='MT/day',**_AX),xaxis=dict(tickangle=-45,automargin=True,**_AX))
            st.plotly_chart(fig_c,use_container_width=True,config={'displayModeBar':False})

    # ── Tab 5 ─────────────────────────────────────────────────────────────────
    with t5:
        sea = trip_df[(trip_df['Phase']=='SEA')&(trip_df['Status']=='VERIFIED')]
        if 'HM_Base' in sea.columns and sea['HM_Base'].abs().sum()>0:
            sel = st.selectbox('Select Verified Sea Passage',sea['Timeline'].tolist(),
                               key=f'shap_{sum_data["vname"]}')
            tr  = sea[sea['Timeline']==sel].iloc[0]
            eb  = tr['AI_Exp']

            fig_w = go.Figure(go.Waterfall(
                name="SHAP",orientation="v",
                measure=["absolute","relative","relative","relative","relative","relative","relative","total"],
                x=["Robust Baseline","Fleet Bias","Res. Speed","Mass","Kinematics","Season Spline","Degradation","AI Expected"],
                textposition="outside",
                text=[f"{tr['HM_Base']:.1f}",f"{tr['SHAP_Base']:+.1f}",f"{tr['SHAP_Propulsion']:+.1f}",
                      f"{tr['SHAP_Mass']:+.1f}",f"{tr['SHAP_Kinematics']:+.1f}",f"{tr['SHAP_Season']:+.1f}",
                      f"{tr['SHAP_Degradation']:+.1f}",f"{eb:.1f}"],
                y=[tr['HM_Base'],tr['SHAP_Base'],tr['SHAP_Propulsion'],tr['SHAP_Mass'],
                   tr['SHAP_Kinematics'],tr['SHAP_Season'],tr['SHAP_Degradation'],0],
                connector={"line":{"color":"rgba(255,255,255,.08)","width":2,"dash":"dot"}},
                decreasing={"marker":{"color":"#00e0b0"}},
                increasing={"marker":{"color":"#ff2a55"}},
                totals={"marker":{"color":"#7b68ee"}}))
            fig_w.update_layout(**_BL,height=500,
                title=dict(text=f"Mathematical Delta Breakdown: {tr['Route']} ({tr['Speed_kn']}kn)",
                           font=dict(size=20,family='Bricolage Grotesque',color='#fff')),
                yaxis=dict(**_AX),margin=dict(t=80,b=30,l=10,r=10))
            st.plotly_chart(fig_w,use_container_width=True,config={'displayModeBar':False})

            sigma  = max(tr['Stoch_Var']/1.645, 0.1)
            x_vals = np.linspace(eb-4*sigma, eb+4*sigma, 100)
            y_vals = np.exp(-0.5*((x_vals-eb)/sigma)**2)/(sigma*np.sqrt(2*np.pi))
            x_fill = np.linspace(tr['Exp_Lower'], tr['Exp_Upper'], 50)
            y_fill = np.exp(-0.5*((x_fill-eb)/sigma)**2)/(sigma*np.sqrt(2*np.pi))

            fig_s = go.Figure()
            fig_s.add_trace(go.Scatter(
                x=np.concatenate([x_fill,x_fill[::-1]]),
                y=np.concatenate([y_fill,np.zeros_like(y_fill)]),
                fill='toself',fillcolor='rgba(123,104,238,.18)',
                line=dict(color='rgba(255,255,255,0)'),hoverinfo='skip',showlegend=False))
            fig_s.add_trace(go.Scatter(x=x_vals,y=y_vals,mode='lines',
                line=dict(color='rgba(123,104,238,.9)',width=3),showlegend=False))
            fig_s.add_trace(go.Scatter(x=[eb,eb],y=[0,max(y_vals)],mode='lines',
                line=dict(color='#7b68ee',width=2,dash='dash'),showlegend=False))
            fig_s.add_trace(go.Scatter(x=[eb],y=[max(y_vals)*1.15],mode='text',
                text=['AI Mean'],textfont=dict(color='#7b68ee',family='Geist Mono',size=13),showlegend=False))
            ac2 = '#00e0b0' if (tr['Daily_Burn']>=tr['Exp_Lower'] and tr['Daily_Burn']<=tr['Exp_Upper']) else '#ff2a55'
            y_a = np.exp(-0.5*((tr['Daily_Burn']-eb)/sigma)**2)/(sigma*np.sqrt(2*np.pi))
            fig_s.add_trace(go.Scatter(x=[tr['Daily_Burn'],tr['Daily_Burn']],y=[0,y_a],mode='lines',
                line=dict(color=ac2,width=2),showlegend=False))
            fig_s.add_trace(go.Scatter(x=[tr['Daily_Burn']],y=[y_a+max(y_vals)*.15],
                mode='markers+text',marker=dict(color=ac2,size=14,symbol='diamond'),
                text=['Actual'],textfont=dict(color=ac2,family='Geist Mono',size=13),
                textposition='top center',showlegend=False))
            fig_s.update_layout(**_BL,
                title=dict(text='Empirical Probability Density (Cross-Conformal)',
                           font=dict(size=18,family='Bricolage Grotesque',color='#fff')),
                height=400,yaxis=dict(showticklabels=False,showgrid=False,zeroline=False),
                xaxis=dict(title='MT/day',**_AX),margin=dict(t=70,b=40,l=20,r=20))
            st.plotly_chart(fig_s,use_container_width=True,config={'displayModeBar':False})

            p_val = tr['P_Value']
            if p_val < 5.0:
                st.error(f"**Forensic Proof:** Audited Burn at absolute tail of Conformal distribution. "
                         f"Probability of natural occurrence: **{p_val:.2f}%**. High probability of mass extraction.")
            else:
                st.success(f"**Forensic Proof:** Audited Burn statistically nominal. "
                           f"Probability of natural occurrence: **{p_val:.2f}%**.")

            md_val = tr['Mahalanobis']; md_thresh = tr['MD_Threshold']
            md_col = '#00e0b0' if md_val <= md_thresh else '#ff2a55'
            fig_md = go.Figure(go.Indicator(
                mode="number+gauge",value=md_val,
                number={'font':{'color':md_col,'size':45,'family':'Bricolage Grotesque'}},
                domain={'x':[0,1],'y':[0,1]},
                title={'text':'Kinematic Plausibility Matrix','font':{'size':18,'color':'#f8fafc','family':'Bricolage Grotesque'}},
                gauge={
                    'axis':{'range':[None,max(md_val,md_thresh)*1.2],'tickwidth':2,'tickcolor':'rgba(255,255,255,.35)'},
                    'bar':{'color':md_col,'thickness':.3},
                    'bgcolor':'rgba(255,255,255,.04)','borderwidth':0,
                    'steps':[{'range':[0,md_thresh],'color':'rgba(0,224,176,.14)'},
                             {'range':[md_thresh,max(md_val,md_thresh)*1.2],'color':'rgba(255,42,85,.14)'}],
                    'threshold':{'line':{'color':'#fff','width':3},'thickness':.82,'value':md_thresh}
                }))
            fig_md.update_layout(**_BL,height=300,margin=dict(t=60,b=20,l=30,r=30))
            st.plotly_chart(fig_md,use_container_width=True,config={'displayModeBar':False})

            if md_val <= md_thresh:
                st.success(f"**Kinematic Audit: PASS.** Mahalanobis distance ({md_val:.1f}) within threshold ({md_thresh:.1f}).")
            else:
                st.error(f"⚠️ **Kinematic Audit: FAIL.** Distance ({md_val:.1f}) exceeds threshold ({md_thresh:.1f}). Inputs statistically inconsistent.")
        else:
            st.warning("AI Explainability Offline: Minimum 8 Sea Legs required.")

    # ── Tab 6 ─────────────────────────────────────────────────────────────────
    with t6:
        quar = trip_df[trip_df['Status'].str.contains('QUARANTINE|GHOST')]
        if quar.empty:
            st.success("Zero anomalies. All timelines and mass balances intact.")
        else:
            for _,r in quar.iterrows():
                c = STATUS_COLORS.get(r['Status'],'#ff2a55')
                st.markdown(
                    f'<div class="q-card">'
                    f'<span style="color:{c};font-weight:800;font-size:.78rem;letter-spacing:.1em">'
                    f'{r["Status"]}</span>'
                    f'<span style="color:var(--t2);margin-left:14px;font-size:.78rem;font-family:var(--fm)">'
                    f'{r["Timeline"]}</span>'
                    f'<div style="color:var(--t1);font-size:.82rem;margin-top:8px;font-weight:500">'
                    f'Exception: {r["Flags"]}</div></div>',
                    unsafe_allow_html=True)
    st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# FLEET MATRIX
# ═══════════════════════════════════════════════════════════════════════════════
if len(fleet_results) > 1:
    st.markdown(
        '<h2 style="color:#fff;font-family:var(--fd);margin-top:20px;font-size:2rem">'
        'Fleet Comparison Matrix</h2>', unsafe_allow_html=True)
    rows = [{'Vessel':r['name'],'Legs':r['summary']['cycles'],
             'Verified':f"{r['summary']['integrity']:.1f}%",
             'DQI':int(r['summary']['avg_dqi']),
             'Fuel MT':r['summary']['total_fuel'],
             'Sea Burn':r['summary']['avg_sea_burn'],
             'Anomalies':r['summary']['anomalies'],
             'NM':int(r['summary']['total_nm'])} for r in fleet_results]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=350)
