"""Real Infoleap/Royal Enfield brand assets — replaces the earlier
CSS-mock logo (3 colored squares standing in for the real Infoleap
mark, per BUGS.md: "No logo image assets exist anywhere in the repo").
Sourced from the client's own PPT (Final Story by brand_28_04_2026.pptx,
2026-07-27) — assets/infoleap_logo.png, assets/infoleap_swoosh.png,
assets/re_logo.png (the last already existed, unused until now)."""
import base64
import os
import streamlit as st

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
INFOLEAP_LOGO_PATH = os.path.join(_ASSETS_DIR, "infoleap_logo.png")
INFOLEAP_SWOOSH_PATH = os.path.join(_ASSETS_DIR, "infoleap_swoosh.png")
RE_LOGO_PATH = os.path.join(_ASSETS_DIR, "re_logo.png")


@st.cache_data(show_spinner=False)
def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def brand_header_html(logo_height_px=38, re_logo_height_px=42):
    """INFOLEAP x ROYAL ENFIELD lockup using the real logo images — used
    by the login page, landing page, and sidebar (auth.py / app.py)."""
    infoleap_img = (
        f"<img src='data:image/png;base64,{_b64(INFOLEAP_LOGO_PATH)}' style='height:{logo_height_px}px;width:auto;'/>"
        if os.path.exists(INFOLEAP_LOGO_PATH) else ""
    )
    re_img = (
        f"<img src='data:image/png;base64,{_b64(RE_LOGO_PATH)}' style='height:{re_logo_height_px}px;width:auto;'/>"
        if os.path.exists(RE_LOGO_PATH) else ""
    )
    return f"""
    <div style="display:flex; align-items:center; justify-content:center; gap:14px; margin-bottom:0.5rem;">
        {infoleap_img}
        <span style="font-size:1.9rem; font-weight:800; letter-spacing:0.02em; color:#1A1A1A; font-family:'Segoe UI',sans-serif; white-space:nowrap;">
            INFOLEAP
        </span>
        <span style="color:#662D91; font-size:1.4rem;">&times;</span>
        {re_img}
        <span style="font-size:1.7rem; font-weight:800; color:#C8102E; font-family:Georgia, serif; letter-spacing:0.03em; white-space:nowrap;">
            ROYAL ENFIELD
        </span>
    </div>
    """


def re_logo_img_html(height_px=34, extra_style=""):
    """Just the Royal Enfield logo <img> tag (or "" if the asset is
    missing) — used standalone on the main dashboard header, alongside
    the full brand_header_html() lockup on login/landing/sidebar."""
    if not os.path.exists(RE_LOGO_PATH):
        return ""
    return f"<img src='data:image/png;base64,{_b64(RE_LOGO_PATH)}' style='height:{height_px}px;width:auto;vertical-align:middle;{extra_style}'/>"


def swoosh_background_css(opacity=0.10):
    """Subtle full-bleed swoosh watermark behind the page content — used
    on the login/landing pages for visual texture without competing with
    the form/buttons. Layered via ::before (its own opacity, positioned
    behind everything) rather than .stApp's own background-image, since
    fading .stApp itself would fade the actual content too."""
    if not os.path.exists(INFOLEAP_SWOOSH_PATH):
        return ""
    return f"""
    <style>
        .stApp {{ position: relative; }}
        .stApp::before {{
            content: "";
            position: fixed;
            top: 0; right: 0;
            width: 55vw; height: 55vw;
            background-image: url('data:image/png;base64,{_b64(INFOLEAP_SWOOSH_PATH)}');
            background-repeat: no-repeat;
            background-position: top right;
            background-size: contain;
            opacity: {opacity};
            pointer-events: none;
            z-index: 0;
        }}
    </style>
    """
