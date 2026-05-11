import streamlit as st
import pandas as pd
import os
import base64
from PIL import Image

from utils.visuals import (
    create_brand_radar, 
    create_monthly_trends, 
    create_buyer_segment_bar, 
    create_anomaly_chart
)
from utils.ai_agent import analyze_chart_ui
from utils.intelligence import IntelligenceVault, generate_showroom_briefing, get_sentiment_flag
from utils.assets import BikeAssetLoader

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Royal Enfield | Midnight Chrome Dashboard",
    page_icon="🏍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- INITIALIZE VAULT & ASSETS ---
vault = IntelligenceVault()
asset_loader = BikeAssetLoader()

# --- UTILS ---
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def inject_scroller():
    # Only inject once to avoid redundant DOM operations
    if st.session_state.get("scroller_injected"):
        return

    scroller_path = os.path.join("utils", "scroller.js")
    if os.path.exists(scroller_path):
        with open(scroller_path, 'r') as f:
            js_code = f.read()
            st.markdown(f"<script>{js_code}</script>", unsafe_allow_html=True)
            st.session_state.scroller_injected = True

def trigger_scroll(stage_id, key=None):
    if stage_id == "INTRODUCE":
        type_msg = "INTRODUCE_BIKE"
        payload = f"type: '{type_msg}'"
    else:
        type_msg = "SCROLL_TO_STAGE"
        payload = f"type: '{type_msg}', stageId: '{stage_id}'"
        
    js_code = f"""
    <script>
        window.parent.postMessage({{
            {payload}
        }}, '*');
    </script>
    """
    st.components.v1.html(js_code, height=0)

# --- LOAD CSS ---
def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Create styles directory if it doesn't exist (safety)
if not os.path.exists("styles"):
    os.makedirs("styles")

local_css(os.path.join("styles", "main.css"))
local_css(os.path.join("styles", "showroom.css"))

# --- DATA LOADING ---
@st.cache_data
def load_data():
    csv_path = os.path.join("data", "processed_data.csv")
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    else:
        # Fallback empty dataframe with expected columns
        return pd.DataFrame(columns=["Platform", "Model", "Section", "Table_Name", "Metric", "All_Avg"])

df = load_data()

def get_kpi_metrics(df, platform, model):
    if df.empty:
        return None
        
    # Get last two months
    cols = [c for c in df.columns if '_' in c and any(year in c for year in ['25', '26'])]
    # Filter only monthly columns (3 letters month _ 2 digits year)
    monthly_cols = [c for c in cols if len(c.split('_')[0]) == 3]
    # They are already in order in the CSV: Aug_25 to Apr_26
    current_month = monthly_cols[-1]
    prev_month = monthly_cols[-2]
    
    # 1. Total Sample Size (Base)
    base_mask = (df["Platform"] == platform) & (df["Model"] == model) & (df["Table_Name"] == "Age") & (df["Metric"].str.startswith("Base"))
    base_row = df[base_mask]
    if not base_row.empty:
        curr_base = base_row[current_month].values[0]
        prev_base = base_row[prev_month].values[0]
        delta_base = ((curr_base - prev_base) / prev_base * 100) if prev_base != 0 else 0
    else:
        curr_base, delta_base = 0, 0

    # 2. Brand Awareness (Ownership RE)
    awareness_mask = (df["Platform"] == platform) & (df["Model"] == model) & (df["Table_Name"] == "Brand Owned - Brand Wise") & (df["Metric"] == "RE")
    awareness_row = df[awareness_mask]
    if not awareness_row.empty:
        curr_awareness = awareness_row[current_month].values[0]
        prev_awareness = awareness_row[prev_month].values[0]
        delta_awareness = curr_awareness - prev_awareness
    else:
        curr_awareness, delta_awareness = 0, 0

    # 3. Purchase Intent (Consideration RE)
    intent_mask = (df["Platform"] == platform) & (df["Model"] == model) & (df["Table_Name"] == "Brand Considered - Brand wise") & (df["Metric"] == "RE")
    intent_row = df[intent_mask]
    if not intent_row.empty:
        curr_intent = intent_row[current_month].values[0]
        prev_intent = intent_row[prev_month].values[0]
        delta_intent = curr_intent - prev_intent
    else:
        curr_intent, delta_intent = 0, 0

    # 4. Satisfaction (Proxy: Overall Riding in Key Buying Factors)
    sat_mask = (df["Platform"] == platform) & (df["Model"] == model) & (df["Table_Name"] == "Key Buying Factors") & (df["Metric"] == "+[Overall Riding]")
    sat_row = df[sat_mask]
    if not sat_row.empty:
        curr_sat = sat_row[current_month].values[0]
        prev_sat = sat_row[prev_month].values[0]
        delta_sat = curr_sat - prev_sat
    else:
        curr_sat, delta_sat = 0, 0

    return {
        "sample_size": (curr_base, delta_base),
        "awareness": (curr_awareness, delta_awareness),
        "intent": (curr_intent, delta_intent),
        "satisfaction": (curr_sat, delta_sat)
    }

# --- SIDEBAR FILTERS ---
# RE Logo Placeholder (using text for now as no asset found)
st.sidebar.markdown("""
    <div style="text-align: center; padding: 10px; border: 2px solid #e31837; border-radius: 5px; margin-bottom: 20px;">
        <h1 style="color: #e31837; font-family: 'Syncopate', sans-serif; margin: 0; font-size: 1.5rem;">RE</h1>
        <p style="color: white; font-family: 'Syncopate', sans-serif; margin: 0; font-size: 0.6rem; letter-spacing: 2px;">ROYAL ENFIELD</p>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### INSIGHTS ENGINE")

if not df.empty:
    platforms = sorted(df["Platform"].unique().tolist())
    selected_platform = st.sidebar.selectbox("PLATFORM", platforms)

    models = sorted(df[df["Platform"] == selected_platform]["Model"].unique().tolist())
    selected_model = st.sidebar.selectbox("MODEL", models)

    period_type = st.sidebar.radio("ANALYSIS PERIOD", ["Monthly", "Quarterly"])
    
    # --- AUTO-SCROLL LOGIC ---
    if "last_selection" not in st.session_state:
        st.session_state.last_selection = (selected_platform, selected_model)
        st.session_state.scroll_trigger = None

    if st.session_state.last_selection != (selected_platform, selected_model):
        st.session_state.last_selection = (selected_platform, selected_model)
        st.session_state.scroll_trigger = "INTRODUCE"
        # We'll use a delayed trigger for stage-02 in the next rerun or handle it in JS
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### DATA STAGES")
    st.sidebar.markdown(f"""
        <div class="step-container">
            <div class="step-indicator" data-stage="stage-01">01 Hero & KPIs</div>
            <div class="step-indicator" data-stage="stage-02">02 Performance</div>
            <div class="step-indicator" data-stage="stage-03">03 Competitive</div>
            <div class="step-indicator" data-stage="stage-04">04 AI Insights</div>
        </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.warning("Data source not found.")
    selected_model = "Classic 350" # Default
    period_type = "Monthly"

st.sidebar.markdown("---")
st.sidebar.markdown("v1.0.0 | Midnight Chrome Edition")

# --- MAIN BODY ---
inject_scroller()

if st.session_state.get("scroll_trigger"):
    trigger_scroll(st.session_state.scroll_trigger)
    st.session_state.scroll_trigger = None

# Stage 01: Hero & KPIs
with st.container():
    st.markdown('<div id="stage-01" class="glass-card">', unsafe_allow_html=True)
    
    # Hero Section
    hero_img_url = asset_loader.get_asset_url(selected_model)

    st.markdown(f"""
        <div class="hero-container" style="background-image: linear-gradient(rgba(0,0,0,0.1), rgba(0,0,0,0.6)), url('{hero_img_url}');">
            <div class="hero-overlay">
                <p style="color: #e31837; font-family: 'Syncopate', sans-serif; font-weight: 700; margin-bottom: 0; letter-spacing: 3px;">PREMIUM MOTORCYCLING</p>
                <h1 class="hero-title">{selected_model}</h1>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # KPI Row
    kpis = get_kpi_metrics(df, selected_platform, selected_model)
    m1, m2, m3, m4 = st.columns(4)
    if kpis:
        with m1:
            val, delta = kpis["sample_size"]
            st.metric("Total Sample Size", f"{val:,.0f}", f"{delta:+.1f}%")
        with m2:
            val, delta = kpis["awareness"]
            st.metric("Brand Awareness", f"{val:.1f}%", f"{delta:+.1f}%")
        with m3:
            val, delta = kpis["intent"]
            st.metric("Purchase Intent", f"{val:.1f}%", f"{delta:+.1f}%")
        with m4:
            val, delta = kpis["satisfaction"]
            rating = val / 20.0
            prev_rating = (val - delta) / 20.0
            delta_rating = rating - prev_rating
            st.metric("Customer Satisfaction", f"{rating:.1f}/5", f"{delta_rating:+.1f}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Stage 02: Core Performance Trends
with st.container():
    st.markdown('<div id="stage-02" class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 01 | CORE PERFORMANCE")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Monthly Age Trends")
        fig_trends = create_monthly_trends(df, selected_platform, selected_model)
        st.plotly_chart(fig_trends, use_container_width=True)
    with c2:
        st.subheader("Buyer Segment Breakdown")
        fig_buyer = create_buyer_segment_bar(df, selected_platform, selected_model)
        st.plotly_chart(fig_buyer, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Stage 03: Competitive Analysis
with st.container():
    st.markdown('<div id="stage-03" class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 02 | COMPETITIVE INTELLIGENCE")
    c3, c4 = st.columns(2)
    with c3:
        st.subheader("MoM Significance (Education)")
        fig_anomaly = create_anomaly_chart(df, selected_platform, selected_model)
        st.plotly_chart(fig_anomaly, use_container_width=True)
    with c4:
        st.subheader("Competitive Radar")
        fig_radar = create_brand_radar(df, selected_platform, selected_model)
        st.plotly_chart(fig_radar, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Stage 04: AI Insights Terminal
with st.container():
    st.markdown('<div id="stage-04" class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 03 | AI INSIGHTS TERMINAL")
    
    # Check for existing insights
    cached_insights = vault.get_insights(selected_model, period_type)
    
    if cached_insights:
        st.info("💡 Strategic Intelligence Loaded from Vault")
        
        # Determine sentiments
        story_sent = get_sentiment_flag(cached_insights.get('storyteller', ''))
        strat_sent = get_sentiment_flag(cached_insights.get('strategist', ''))
        sci_sent = get_sentiment_flag(cached_insights.get('scientist', ''))
        
        sent_colors = {"Positive": "#27ae60", "Warning": "#f39c12", "Neutral": "#95a5a6"}
        
        t1, t2, t3 = st.tabs(["📖 Storyteller", "🎯 Strategist", "🧪 Data Scientist"])
        
        with t1:
            st.markdown(f"""
                <div style="background-color: #1e1e1e; padding: 20px; border-left: 5px solid #3498db; border-radius: 5px; color: white;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h4 style="margin:0;">The Human Journey</h4>
                        <span style="background-color: {sent_colors[story_sent]}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: bold;">{story_sent.upper()}</span>
                    </div>
                    {cached_insights.get('storyteller', 'No storyteller insights available.')}
                </div>
            """, unsafe_allow_html=True)
            
        with t2:
            st.markdown(f"""
                <div style="background-color: #1e1e1e; padding: 20px; border-left: 5px solid #e67e22; border-radius: 5px; color: white;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h4 style="margin:0;">Growth & Strategy</h4>
                        <span style="background-color: {sent_colors[strat_sent]}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: bold;">{strat_sent.upper()}</span>
                    </div>
                    {cached_insights.get('strategist', 'No strategist insights available.')}
                </div>
            """, unsafe_allow_html=True)
            
        with t3:
            st.markdown(f"""
                <div style="background-color: #1e1e1e; padding: 20px; border-left: 5px solid #e31837; border-radius: 5px; color: white;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h4 style="margin:0;">Statistical Anomalies</h4>
                        <span style="background-color: {sent_colors[sci_sent]}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: bold;">{sci_sent.upper()}</span>
                    </div>
                    {cached_insights.get('scientist', 'No scientist insights available.')}
                </div>
            """, unsafe_allow_html=True)
        
        if st.button("RE-GENERATE BRIEF"):
            cached_insights = None
            st.rerun()
            
    if not cached_insights:
        st.warning("No insights found for this model/period.")
        if st.button("GENERATE STRATEGIC BRIEF"):
            with st.spinner("Synthesizing market intelligence from multiple streams..."):
                # Prepare summary data for bulk generation
                summary_data = {
                    "KPIs": kpis,
                    "Age_Trends": df[(df["Platform"] == selected_platform) & (df["Model"] == selected_model) & (df["Table_Name"] == "Age")].to_dict(orient='records')[:10],
                    "Buyer_Segments": df[(df["Platform"] == selected_platform) & (df["Model"] == selected_model) & (df["Table_Name"] == "Type of Buyer")].to_dict(orient='records'),
                    "Competitive": df[(df["Platform"] == selected_platform) & (df["Model"] == selected_model) & (df["Table_Name"] == "Brand Owned - Brand Wise")].to_dict(orient='records')[:5]
                }
                
                new_insights = generate_showroom_briefing(summary_data, selected_model, period_type)
                vault.save_insights(selected_model, period_type, new_insights)
                st.success("Briefing generated and saved to vault!")
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# --- FOOTER ---
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.8rem; margin-top: 5rem;">
    CONFIDENTIAL | INTERNAL USE ONLY | ROYAL ENFIELD MOTORCYCLES
</div>
""", unsafe_allow_html=True)
