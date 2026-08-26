"""Light theme: Royal Enfield + Infoleap brand colors. Minimalist, no dark mode."""
import streamlit as st

# Brand palette
RE_RED = "#C8102E"        # Royal Enfield primary red
RE_BLACK = "#1A1A1A"       # RE wordmark black
INFOLEAP_ORANGE = "#F7941D"
INFOLEAP_GREEN = "#39B54A"
INFOLEAP_BLUE = "#2E3192"
INFOLEAP_PURPLE = "#662D91"
BG = "#FAFAF8"             # warm off-white
CARD = "#FFFFFF"
BORDER = "#ECE9E4"
TEXT = "#2B2B2B"
MUTED = "#7A7670"

CHART_SEQUENCE = [RE_RED, INFOLEAP_BLUE, INFOLEAP_ORANGE, INFOLEAP_GREEN, INFOLEAP_PURPLE, "#8C8C8C"]

# Per MIS_Dashboard_Requirements.docx 5.1: "Charts, graphs, and tables should
# use consistent colour coding aligned to segment types (e.g., green for
# Acceptors, red for Rejectors, orange for Cancelled)."
SEGMENT_COLORS = {
    "All": RE_RED,
    "Acceptor": INFOLEAP_GREEN,
    "Rejector": RE_RED,
    "Cancelled": INFOLEAP_ORANGE,
}


def render_theme_css(accent=RE_RED):
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Oswald:wght@500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', 'Segoe UI', Tahoma, sans-serif;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            text-rendering: optimizeLegibility;
        }}

        :root {{
            --bg: {BG}; --card: {CARD}; --border: {BORDER};
            --text: {TEXT}; --muted: {MUTED};
            --re-red: {RE_RED}; --re-black: {RE_BLACK};
            --io-orange: {INFOLEAP_ORANGE}; --io-green: {INFOLEAP_GREEN};
            --io-blue: {INFOLEAP_BLUE}; --io-purple: {INFOLEAP_PURPLE};
            --accent: {accent};
        }}

        .stApp {{
            background-color: var(--bg);
            color: var(--text);
        }}

        .main .block-container {{
            max-width: 100%;
            padding: 1.2rem 1.5rem;
        }}

        h1, h2, h3, h4 {{
            color: var(--re-black) !important;
            font-family: 'Oswald', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            letter-spacing: 0.01em;
            font-weight: 700;
        }}

        /* KPI numbers + sidebar nav also carry the branded display font, so
        the showroom/automotive feel is consistent everywhere a number or
        section title appears, not just <h1-3>. */
        [data-testid="stMetricValue"], .kpi-value {{
            font-family: 'Oswald', 'Segoe UI', sans-serif !important;
        }}
        [data-testid="stSidebar"] [role="radiogroup"] label {{
            font-family: 'Oswald', 'Segoe UI', sans-serif;
            font-weight: 500;
        }}

        h1 {{ border-bottom: 3px solid var(--accent); padding-bottom: 0.4rem; display: inline-block; }}

        /* Cards — transparent, no borders */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            border-radius: 0 !important;
        }}

        /* Sidebar */
        [data-testid="stSidebar"] {{
            background-color: var(--card);
            border-right: 1px solid var(--border);
        }}
        [data-testid="stSidebar"] h3 {{
            color: var(--re-red) !important;
            text-transform: uppercase;
            font-size: 0.85rem;
            letter-spacing: 0.05em;
        }}

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{
            background-color: var(--card);
            border-bottom: 2px solid var(--border);
            gap: 0.5rem;
        }}
        .stTabs [data-baseweb="tab"] {{
            color: var(--muted);
            font-weight: 600;
        }}
        .stTabs [aria-selected="true"] {{
            color: var(--re-black) !important;
            border-bottom-color: var(--re-red) !important;
            border-bottom-width: 3px !important;
        }}

        /* Buttons — primary (default): RE red CTA */
        .stButton button, .stFormSubmitButton button {{
            background-color: var(--re-red);
            color: white;
            border: none;
            border-radius: 6px;
            font-weight: 600;
        }}
        .stButton button:hover, .stFormSubmitButton button:hover {{
            background-color: #a30d24;
        }}
        /* Secondary buttons (Log out, minor actions) — subtle, no fill */
        .stButton button[kind="secondary"] {{
            background-color: transparent !important;
            color: var(--muted) !important;
            border: 1px solid var(--border) !important;
            font-weight: 500 !important;
            font-size: 0.85rem !important;
            padding: 0.3rem 0.8rem !important;
        }}
        .stButton button[kind="secondary"]:hover {{
            background-color: var(--border) !important;
            color: var(--text) !important;
            border-color: #ccc !important;
        }}

        /* Significance superscripts */
        .sig-letter {{ color: var(--io-green); font-weight: 700; font-size: 0.75em; vertical-align: super; }}

        /* KPI metric cards */
        [data-testid="stMetric"] {{
            background-color: var(--card);
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            padding: 0.8rem 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        }}

        /* Section headers (h3) get a small accent tick — !important needed
        because Streamlit's own h3 rules otherwise win the padding fight,
        which previously made the tick overlap the first letter. */
        h3 {{
            position: relative !important;
            padding-left: 14px !important;
            margin-top: 1.6rem !important;
            margin-bottom: 0.6rem !important;
        }}
        h3::before {{
            content: "";
            position: absolute; left: 0; top: 50%;
            transform: translateY(-50%);
            height: 70%; width: 4px; border-radius: 2px;
            background: var(--accent);
        }}
        [data-testid="stSidebar"] h3 {{
            padding-left: 14px !important;
        }}

        /* h4 (subsection headers, e.g. the At a Glance pie-group labels —
        Demographics/Buyer Type/Edition Analysis/Brand-to-Brand Comparison)
        get the same accent-tick treatment as h3, just a touch smaller and
        lighter, so they read as a clear tier below h3 instead of plain
        unstyled bold text that broke the page's visual consistency. */
        h4 {{
            position: relative !important;
            padding-left: 12px !important;
            margin-top: 1.1rem !important;
            margin-bottom: 0.5rem !important;
            font-size: 1.05rem !important;
        }}
        h4::before {{
            content: "";
            position: absolute; left: 0; top: 50%;
            transform: translateY(-50%);
            height: 60%; width: 3px; border-radius: 2px;
            background: var(--accent);
            opacity: 0.65;
        }}

        /* Brand block accent (infoleap-style 4-color stack), used via .io-blocks */
        .io-blocks {{ display: inline-flex; flex-direction: column; gap: 2px; margin-right: 8px; }}

        /* Table Center Alignment */
        .stDataFrame th, .stDataFrame td, table th, table td, div[data-testid="stTable"] th, div[data-testid="stTable"] td {{
            text-align: center !important;
        }}

        /* Shared card component — use via class="re-card" in st.markdown HTML */
        .re-card {{
            background: var(--card);
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            padding: 1.25rem;
            margin-bottom: 1rem;
        }}

        /* Section divider chips — segment label pills above each section */
        .re-section-chip {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 20px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
            background: var(--accent);
            color: white;
            opacity: 0.85;
        }}

        /* Metric section sub-header with left accent bar */
        .re-metric-header {{
            border-left: 4px solid var(--accent);
            padding-left: 12px;
            margin: 1.2rem 0 0.5rem 0;
            font-family: 'Oswald', 'Segoe UI', sans-serif;
            font-size: 1.05rem;
            font-weight: 700;
            color: #1e293b;
            letter-spacing: 0.01em;
        }}

        /* Data table card wrapper — consistent shadow/border on all tables */
        .re-table-wrap {{
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 10px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
            overflow: hidden;
            margin-bottom: 1rem;
        }}
        .re-table-wrap table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .re-table-wrap th {{
            background: #1e293b !important;
            color: #f8fafc !important;
            font-weight: 600;
            letter-spacing: 0.02em;
            padding: 10px 14px !important;
            text-align: center !important;
            border-bottom: none !important;
        }}
        .re-table-wrap td {{
            padding: 8px 14px !important;
            border-bottom: 1px solid #f1f5f9 !important;
            text-align: center !important;
        }}
        .re-table-wrap tr:nth-child(even) td {{
            background: #f8fafc;
        }}
    </style>
    """, unsafe_allow_html=True)
