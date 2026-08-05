"""Static Overview-page narrative — replaces the old chart/hero content on
the Overview (comparison hub) nav page per 2026-07-22 client request.
Sourced verbatim from slides 1-4 of `Final Story by brand_28_04_2026.pptx`
(see docs/superpowers/specs/2026-07-22-overview-and-chart-revamp-design.md).
The big per-model Sample Achieved grid on slide 4, and later (per 2026-07-22
follow-up) the segment-level Sample Achieved cards too, are intentionally
NOT reproduced — only the fieldwork/database-lag notes beneath them are
kept, rendered as a reporting-cadence timeline."""
import base64
import streamlit as st

RE_LOGO_PATH = "assets/re_logo.png"


@st.cache_data(show_spinner=False)
def _logo_b64():
    """Base64-encoded logo, inlined as a data: URI in the hero banner —
    needed because the banner is one hand-built flex <div> (for vertical
    centering against the title text, which st.image/st.columns can't do
    on their own), so the image has to be embedded directly in that HTML
    rather than rendered via st.image."""
    with open(RE_LOGO_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

# Reporting-lag reference table (slide 4, "Table 7") — a small legitimate
# reference table, kept intact (unlike the per-model grid).
DATA_LAG_TABLE = [
    ("July", "June"), ("August", "July"), ("September", "August"),
    ("October", "September"), ("November", "October"), ("December", "November"),
    ("January", "December"), ("February", "January"), ("March", "February"),
    ("April", "March"), ("May", "April"),
]

SEGMENT_DEFINITIONS = [
    ("Acceptors", "Individuals who have successfully purchased a motorcycle."),
    ("Rejectors", "Individuals who did not buy the inquired RE motorcycle."),
    ("Booked But Cancelled", "Individuals who booked but canceled a RE model and may or may not have bought any other model."),
]


def _card(inner, accent="#C8102E", extra=""):
    return (
        f"<div style='flex:1;min-width:280px;max-width:calc(50% - 7px);background:#fff;border:1px solid #ECE9E4;"
        f"border-top:3px solid {accent};border-radius:12px;padding:20px 22px;box-sizing:border-box;{extra}'>{inner}</div>"
    )


def render_overview_intro():
    """Renders the full static Overview narrative (slides 1-4). No chart
    data, no engine/df dependency — pure content."""

    # ── Slide 1: title + logo ────────────────────────────────────────────
    # Rendered as one flex block (not st.columns) so the logo and title
    # text vertically center against each other — st.columns has no
    # cross-axis alignment control, which is why the logo previously sat
    # top-aligned against a much taller text block. A soft circular
    # backing behind the logo also stops it floating bare against the
    # off-white page background.
    st.markdown(
        f"""
        <div style='display:flex;align-items:center;gap:22px;
                     background:linear-gradient(135deg,#C8102E08 0%,#FAFAF8 60%);
                     border:1px solid #ECE9E4;border-radius:16px;
                     padding:22px 28px;margin-bottom:1.6rem;'>
          <div style='flex-shrink:0;width:104px;height:104px;border-radius:50%;
                       background:#fff;border:1px solid #ECE9E4;
                       box-shadow:0 2px 10px rgba(0,0,0,0.06);
                       display:flex;align-items:center;justify-content:center;'>
            <img src='data:image/png;base64,{_logo_b64()}' style='width:72px;height:72px;object-fit:contain;'/>
          </div>
          <div>
            <div style='font-family:Oswald,sans-serif;font-size:1.9rem;font-weight:800;
                        color:#1A1A1A;line-height:1.15;'>Understanding the RE Brands</div>
            <div style='font-size:1.05rem;color:#C8102E;font-weight:700;margin-top:3px;'>Research Findings</div>
            <div style='font-size:0.85rem;color:#7A7670;margin-top:2px;'>April 2026</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Slide 2: Research Objectives ─────────────────────────────────────
    st.markdown("<h3>Research Objectives</h3>", unsafe_allow_html=True)
    _obj_cards = (
        _card(
            "<div style='font-size:1.6rem;font-weight:900;color:#C8102E;'>01</div>"
            "<div style='font-size:1rem;font-weight:700;color:#1A1A1A;margin-top:4px;'>"
            "Customer Journey & Brand Perception Analysis</div>"
            "<div style='font-size:0.85rem;color:#4A4644;margin-top:8px;line-height:1.55;'>"
            "Understanding the areas which can be exploited and which elements to focus for improvement."
            "<br><br>Identifying specific reasons why customers choose:"
            "<ul style='margin:4px 0 0 1.1rem;padding:0;'>"
            "<li>To reject the RE brand through detailed drill-downs</li>"
            "<li>To accept the RE brand through detailed drill-downs</li>"
            "</ul></div>"
        )
        + _card(
            "<div style='font-size:1.6rem;font-weight:900;color:#C8102E;'>02</div>"
            "<div style='font-size:1rem;font-weight:700;color:#1A1A1A;margin-top:4px;'>"
            "Consumer Profile and Consideration Set</div>"
            "<div style='font-size:0.85rem;color:#4A4644;margin-top:8px;line-height:1.55;'>"
            "Consumer profile.<br><br>"
            "Understanding competitive sets of the different RE brands."
            "</div>"
        )
    )
    # align-items:flex-start (not the flex default of stretch) — the two
    # cards have genuinely different amounts of source content, so forcing
    # equal height just left card 02 with a large dead patch of empty
    # space at the bottom. Letting each card size to its own content
    # reads cleaner than an artificially stretched, half-empty box.
    st.markdown(f"<div style='display:flex;align-items:flex-start;gap:14px;flex-wrap:wrap;margin-bottom:1.4rem;'>{_obj_cards}</div>",
                unsafe_allow_html=True)

    # ── Slide 3: Research Methodology ────────────────────────────────────
    st.markdown(
        "<h3>Research Methodology</h3>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:0.88rem;color:#4A4644;line-height:1.6;margin-bottom:1rem;'>"
        "CATI (Computer-Assisted Telephonic Interview) enables structured phone interviews across "
        "multiple languages, ensuring regional representation and accurate responses via trained "
        "multilingual interviewers.</div>",
        unsafe_allow_html=True,
    )

    _target_card = _card(
        "<div style='font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;"
        "color:#C8102E;font-weight:700;margin-bottom:8px;'>Target Audience</div>"
        "<div style='font-size:0.85rem;color:#1A1A1A;line-height:1.9;'>"
        "<b>Gender:</b> Male<br>"
        "<b>Age:</b> 18-25 Years, 26-35 Years, 36-45 Years, 41 or more<br>"
        "<b>NCCS:</b> A/B, Key Decision Maker, Main user<br>"
        "<b>Model Purchased:</b> 150cc and above"
        "</div>"
    )
    _seg_def_rows = "".join(
        f"<div style='padding:7px 0;border-bottom:1px solid #F0EDE8;'>"
        f"<b style='color:#1A1A1A;'>{name}:</b> "
        f"<span style='color:#4A4644;'>{desc}</span></div>"
        for name, desc in SEGMENT_DEFINITIONS
    )
    _segments_card = _card(
        "<div style='font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;"
        "color:#C8102E;font-weight:700;margin-bottom:8px;'>Segments</div>"
        f"<div style='font-size:0.85rem;'>{_seg_def_rows}</div>"
    )
    st.markdown(
        f"<div style='display:flex;gap:14px;flex-wrap:wrap;margin-bottom:1.4rem;align-items:stretch;'>"
        f"{_target_card}{_segments_card}</div>",
        unsafe_allow_html=True,
    )

    # ── Slide 4: Reporting cadence (Sample Achieved cards removed per
    # 2026-07-22 follow-up request; the fieldwork/database-lag notes are
    # kept and shown as a "live" reporting pipeline instead of a plain
    # table). ─────────────────────────────────────────────────────────
    st.markdown(
        "<h3>Reporting Cadence</h3>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:0.82rem;color:#4A4644;line-height:1.8;margin-bottom:0.9rem;'>"
        "<b>FW Dates:</b> 11th Aug to 12th Apr &nbsp;&middot;&nbsp; "
        "<b>Database used:</b> June to February<br>"
        "Each month's data is completed using the prior month database."
        "</div>",
        unsafe_allow_html=True,
    )

    _latest_reported, _latest_used = DATA_LAG_TABLE[-1]
    _chip_css = (
        "flex-shrink:0;background:#fff;border:1px solid #ECE9E4;border-radius:10px;"
        "padding:8px 14px;text-align:center;min-width:76px;"
    )
    _chips = []
    for _reported, _used in DATA_LAG_TABLE:
        _is_latest = (_reported, _used) == (_latest_reported, _latest_used)
        if _is_latest:
            _chips.append(
                f"<div style='{_chip_css}border-color:#C8102E;border-width:2px;position:relative;"
                f"box-shadow:0 2px 8px rgba(200,16,46,0.15);'>"
                f"<span class='live-pulse-dot'></span>"
                f"<div style='font-size:0.7rem;font-weight:800;color:#C8102E;letter-spacing:0.04em;'>LIVE</div>"
                f"<div style='font-size:0.92rem;font-weight:800;color:#1A1A1A;margin-top:2px;'>{_reported}</div>"
                f"<div style='font-size:0.65rem;color:#9A958D;margin-top:1px;'>uses {_used}</div>"
                f"</div>"
            )
        else:
            _chips.append(
                f"<div style='{_chip_css}'>"
                f"<div style='font-size:0.88rem;font-weight:700;color:#1A1A1A;'>{_reported}</div>"
                f"<div style='font-size:0.65rem;color:#9A958D;margin-top:1px;'>uses {_used}</div>"
                f"</div>"
            )
    _arrow = (
        "<span style='flex-shrink:0;color:#D8D3CC;font-size:1.1rem;align-self:center;'>&#8594;</span>"
    )
    _timeline_html = _arrow.join(_chips)
    st.markdown(
        "<style>"
        "@keyframes live-pulse {"
        "  0% { box-shadow: 0 0 0 0 rgba(200,16,46,0.55); }"
        "  70% { box-shadow: 0 0 0 7px rgba(200,16,46,0); }"
        "  100% { box-shadow: 0 0 0 0 rgba(200,16,46,0); }"
        "}"
        ".live-pulse-dot {"
        "  position:absolute; top:7px; right:7px; width:7px; height:7px;"
        "  border-radius:50%; background:#C8102E;"
        "  animation: live-pulse 1.6s ease-out infinite;"
        "}"
        "</style>"
        "<div style='font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;"
        "color:#9A958D;font-weight:700;margin-bottom:8px;'>Data Reported &#8594; Database Used</div>"
        f"<div style='display:flex;align-items:center;gap:8px;overflow-x:auto;padding:4px 4px 10px;'>"
        f"{_timeline_html}</div>",
        unsafe_allow_html=True,
    )
