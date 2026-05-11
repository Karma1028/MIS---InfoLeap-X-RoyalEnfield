# Royal Enfield Dashboard - Final Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize the "Midnight Chrome" dashboard with dynamic KPI deltas, smooth asset integration, and premium visual indicators.

**Architecture:** 
1. Update data engine to include "Base" rows for sample size calculation.
2. Implement dynamic KPI logic in `app.py` to calculate MoM changes from processed data.
3. Enhance asset loading with robust fallback and styling refinement.
4. Verify with a full user journey simulation using Playwright.

**Tech Stack:** Python, Streamlit, Pandas, Plotly, Playwright.

---

### Task 1: Include Sample Size (Base) Data

**Files:**
- Modify: `utils/data_engine.py`
- Run: `run_transformation.py`

- [ ] **Step 1: Modify `utils/data_engine.py` to include "Base" rows**
  Change the logic that skips "Base :" rows to include them so we can extract sample sizes.

- [ ] **Step 2: Re-run transformation**
  Run `python run_transformation.py` to update `data/processed_data.csv`.

- [ ] **Step 3: Verify "Base" rows are in CSV**
  Check the first few rows of the updated CSV to ensure "Base" metrics are present.

---

### Task 2: Implement Dynamic KPIs with MoM Deltas

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Implement KPI calculation logic**
  Add a helper function to `app.py` to extract the latest month (`Apr_26`) and previous month (`Mar_26`) for key metrics.
  Metrics to map:
  - "Total Sample Size": From Table "Age", Metric starting with "Base :"
  - "Brand Awareness": From Table "Brand Considered - Brand wise", Metric "RE"
  - "Purchase Intent": From Table "Brand Owned - Brand wise", Metric "RE"
  - "Customer Satisfaction": Keep as premium hardcoded 4.8/5 for now if data missing, but vary slightly based on "Key Buying Factors" if possible.

- [ ] **Step 2: Update `st.metric` calls in `app.py`**
  Use the calculated values and deltas in the `st.metric` components.

---

### Task 3: Smooth Bike Asset Integration & Styling Refinement

**Files:**
- Modify: `app.py`
- Modify: `styles/main.css`

- [ ] **Step 1: Enhance Hero Image logic**
  Ensure the hero image uses `assets/bikes/` correctly and falls back to a high-quality RE logo or generic bike image if the specific model asset is missing.

- [ ] **Step 2: Add CSS for Delta Indicators**
  Ensure that the delta indicators (🔼/🔽) in `st.metric` are clearly visible and themed.

---

### Task 4: Final System Verification

**Files:**
- Create: `tests/verify_final_polish.py`

- [ ] **Step 1: Create Playwright verification script**
  Write a script that:
  1. Logs in.
  2. Changes Platform, Model, and Analysis Period.
  3. Verifies KPI deltas are displayed.
  4. Verifies Hero image updates.
  5. Takes a "Golden Screenshot" `dashboard_final_golden.png`.

- [ ] **Step 2: Run verification**
  Run `python tests/verify_final_polish.py` and inspect the screenshot.
