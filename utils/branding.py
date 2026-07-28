"""Real Infoleap/Royal Enfield brand assets — replaces the earlier
CSS-mock logo (3 colored squares standing in for the real Infoleap
mark, per BUGS.md: "No logo image assets exist anywhere in the repo").
Sourced from the client's own PPT (Final Story by brand_28_04_2026.pptx,
2026-07-27) — assets/infoleap_logo.png, assets/re_logo.png (the latter
already existed, unused until now).

A swoosh watermark (assets/infoleap_swoosh.png, same PPT) was tried as
a background decoration on the login/landing pages and reverted
(2026-07-27) — the fixed-position ::before pseudo-element broke the
whole page render (content became invisible, only the swoosh painted).
Not worth re-attempting without a safer layering approach."""
import base64
import os
import streamlit as st

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
INFOLEAP_LOGO_PATH = os.path.join(_ASSETS_DIR, "infoleap_logo.png")
RE_LOGO_PATH = os.path.join(_ASSETS_DIR, "re_logo.png")
INFOLEAP_SWOOSH_PATH = os.path.join(_ASSETS_DIR, "infoleap_swoosh.png")


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


def sidebar_brand_html(logo_height_px=20, re_logo_height_px=22):
    """Compact, LEFT-aligned lockup for the narrow sidebar — NOT a scaled-
    down copy of brand_header_html() (that was tried via CSS transform:
    scale() and reported invisible, 2026-07-28: brand_header_html() is
    centered and sized for the wide login page, so at full size in a
    ~260px-wide sidebar the row overflows; centered flex content that
    overflows a container with hidden overflow clips symmetrically from
    BOTH edges, cutting off the logo — the first, left-most element —
    before the text. This version is sized and aligned for the sidebar
    from the start instead of shrinking something built for elsewhere."""
    infoleap_img = (
        f"<img src='data:image/png;base64,{_b64(INFOLEAP_LOGO_PATH)}' style='height:{logo_height_px}px;width:auto;flex-shrink:0;'/>"
        if os.path.exists(INFOLEAP_LOGO_PATH) else ""
    )
    re_img = (
        f"<img src='data:image/png;base64,{_b64(RE_LOGO_PATH)}' style='height:{re_logo_height_px}px;width:auto;flex-shrink:0;'/>"
        if os.path.exists(RE_LOGO_PATH) else ""
    )
    return f"""
    <div style="display:flex; align-items:center; justify-content:flex-start; gap:6px; margin-bottom:0.6rem; overflow:hidden;">
        {infoleap_img}
        <span style="font-weight:800; font-size:0.95rem; color:#1A1A1A; white-space:nowrap;">INFOLEAP</span>
        <span style="color:#662D91; font-size:0.85rem;">&times;</span>
        {re_img}
        <span style="font-weight:800; font-size:0.85rem; color:#C8102E; white-space:nowrap;">ROYAL ENFIELD</span>
    </div>
    """


def re_logo_img_html(height_px=34, extra_style=""):
    """Just the Royal Enfield logo <img> tag (or "" if the asset is
    missing) — used standalone on the main dashboard header, alongside
    the full brand_header_html() lockup on login/landing/sidebar."""
    if not os.path.exists(RE_LOGO_PATH):
        return ""
    return f"<img src='data:image/png;base64,{_b64(RE_LOGO_PATH)}' style='height:{height_px}px;width:auto;vertical-align:middle;{extra_style}'/>"


def swoosh_strip_html(height_px=90, opacity=0.85):
    """Decorative swoosh banner as a normal, bounded <img> — NOT a fixed
    full-page background (that broke the whole page render, reverted
    2026-07-27). Safe because it's a regular block element sized to its
    own height, can't cover or hide anything else on the page. Meant to
    sit in its own container above the sign-in card."""
    if not os.path.exists(INFOLEAP_SWOOSH_PATH):
        return ""
    return (
        f"<div style='width:100%;height:{height_px}px;overflow:hidden;border-radius:12px 12px 0 0;"
        f"background:#FAFAF8;display:flex;align-items:center;justify-content:center;'>"
        f"<img src='data:image/png;base64,{_b64(INFOLEAP_SWOOSH_PATH)}' "
        f"style='width:100%;height:100%;object-fit:cover;object-position:top right;opacity:{opacity};'/>"
        f"</div>"
    )


