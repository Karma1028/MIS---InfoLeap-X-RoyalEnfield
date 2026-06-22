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

        html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', Tahoma, sans-serif; }}

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

        h1, h2, h3 {{
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

        /* Cards */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
            transition: box-shadow 0.15s ease;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
            box-shadow: 0 4px 14px rgba(0,0,0,0.08);
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

        /* Buttons */
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

        /* Brand block accent (infoleap-style 4-color stack), used via .io-blocks */
        .io-blocks {{ display: inline-flex; flex-direction: column; gap: 2px; margin-right: 8px; }}
        .io-blocks span {{ width: 14px; height: 14px; display: block; border-radius: 2px; }}
    </style>
    """, unsafe_allow_html=True)
