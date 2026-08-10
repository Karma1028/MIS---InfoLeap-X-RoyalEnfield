# Royal Enfield Digital Showroom — Infoleap MIS Dashboard

Streamlit app that recomputes the live PHP MIS dashboard's segment analytics
(Acceptor / Rejector / Booked-but-Cancelled) directly from the research
Masterfile, with significance testing, brand-wise breakdowns, and
AI-assisted chart analysis.

## Required local data (not included in this repo)

This repo intentionally ships **code only** — no raw research data,
credentials, or internal docs. To run it, create a `data/` folder
(gitignored) containing:

- `Enroute_Fourth Wave_Masterfile_Base_4010_AUG-MAY.xlsx` — raw research data
- `MIS_datamap.xlsx` — value-label codebook
- `Enroute_AP_V2_netting.xlsx` — brand/model netting codebooks
- `dq2_netting_codebook.json` — generated brand codebook (176-code scheme)
- `users.xlsx` — login table with columns `email`, `password`, `name`, `active`

## Secrets

Create `.streamlit/secrets.toml` (gitignored) if you want to seed an AI
provider key without using the in-app Settings page:

```toml
GROQ_API_KEY = "..."
GEMINI_API_KEY = "..."
OPENROUTER_API_KEY = "..."
```

Keys can otherwise be added at runtime via the Settings page — they're
encrypted at rest (`data/.settings_key` + `data/api_keys.enc`, both
gitignored) and never written to this repo.

## Key System Features & Recent UI Updates

- **Table Center Alignment**: Enforced `text-align: center !important` across all data tables (headers and cell values) for consistent readability.
- **Selective Chart Focus**: Streamlined section layouts by removing heavy Plotly distribution charts from Additional & Replaced, Brand Owned, and Brand Considered sections, maintaining pure center-aligned data tables styled after the open-ended netting table card UI.
- **Top Executive KPI Cards**: Restructured header cards to strictly highlight **Age**, **Household Income**, **Type of Buyer**, and **Key Buying Factor (KBF)** for the last selected month.
- **Head-to-Head Model Comparison**: Dedicated 2-column side-by-side model comparison for 2 selected models across Core Demographics (Age, Education, Occupation, Household Income, Type of Buyer).
- **Open-Ended Netting Taxonomy**: 4-level collapsible tree renderer (Supernet ▶ Net ▶ Subnet ▶ Item) for verbatim reasons across Key Buying Factors, Reasons for Rejection, and Reasons for Cancelling.

## Running

```bash
pip install -r requirements.txt
streamlit run app.py
```
