# Royal Enfield Intelligent Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a professional, "Midnight Chrome" themed Streamlit dashboard with interactive Plotly charts and on-demand AI insights powered by Groq.

**Architecture:** A Streamlit SPA using a local processed CSV for speed, custom CSS for branding, and an agentic bridge to Groq for chart-level analysis.

**Tech Stack:** Python, Streamlit, Pandas, Plotly, Groq API, Playwright (for asset scraping).

---

## File Structure

- `app.py`: Main entry point and UI layout.
- `utils/data_engine.py`: Handles CSV processing from the raw JSON and runtime filtering.
- `utils/ai_agent.py`: Manages Groq API calls, prompting, and result caching.
- `utils/assets_manager.py`: Automated bike image scraping and logo management.
- `styles/main.css`: Custom CSS for the "Midnight Chrome" brand identity.
- `requirements.txt`: Project dependencies.

---

## Tasks

### Task 1: Project Initialization & Asset Scraping

**Files:**
- Create: `requirements.txt`
- Create: `utils/assets_manager.py`

- [ ] **Step 1: Create requirements.txt**
```text
streamlit
pandas
plotly
groq
playwright
beautifulsoup4
requests
```

- [ ] **Step 2: Install dependencies**
Run: `pip install -r requirements.txt && playwright install chromium`

- [ ] **Step 3: Implement Asset Scraper**
Write a script that takes the model names from `docs/investigation/dashboard_structure.json` and downloads 1 high-res image per bike into `assets/bikes/`.
```python
import os
import requests
from bs4 import BeautifulSoup

def download_bike_images(models):
    os.makedirs('assets/bikes', exist_ok=True)
    for model in models:
        # Search and download logic (mocked for plan)
        print(f"Downloading image for {model}...")
```

- [ ] **Step 4: Run Scraper**
Run: `python utils/assets_manager.py`
Expected: `assets/bikes/` contains images for all 18 models.

- [ ] **Step 5: Commit**
```bash
git add requirements.txt utils/assets_manager.py
git commit -m "chore: project init and asset scraping"
```

### Task 2: Data Transformation (JSON to CSV)

**Files:**
- Create: `utils/data_engine.py`
- Create: `data/processed_data.csv`

- [ ] **Step 1: Implement Data Transformer**
Create a function to flatten the 33MB JSON into a single CSV optimized for Streamlit.
```python
import json
import pandas as pd

def transform_json_to_csv(input_path, output_path):
    # Logic to iterate through platforms/models and flatten metrics
    pass
```

- [ ] **Step 2: Run Transformation**
Run: `python utils/data_engine.py`
Expected: `data/processed_data.csv` is created with columns [Platform, Model, Period, Category, Metric, Value].

- [ ] **Step 3: Commit**
```bash
git add utils/data_engine.py data/processed_data.csv
git commit -m "data: transform raw json to processed csv"
```

### Task 3: Streamlit UI & "Midnight Chrome" Styling

**Files:**
- Create: `app.py`
- Create: `styles/main.css`

- [ ] **Step 1: Create main.css**
```css
.stApp {
    background-color: #1a1a1a;
    color: #ffffff;
}
.metric-card {
    border: 1px solid #333;
    background: #222;
    padding: 1rem;
    border-radius: 8px;
}
```

- [ ] **Step 2: Implement App Skeleton**
Set up the sidebar filters and hero section in `app.py`.
```python
import streamlit as st

st.set_page_config(layout="wide")
with open('styles/main.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

st.sidebar.title("Royal Enfield MIS")
# Filter logic here
```

- [ ] **Step 3: Run and Verify UI**
Run: `streamlit run app.py`
Expected: A dark-themed app with filters visible in the sidebar.

- [ ] **Step 4: Commit**
```bash
git add app.py styles/main.css
git commit -m "ui: setup midnight chrome theme and app skeleton"
```

### Task 4: Interactive Plotly Charts

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Implement Chart Generation Functions**
Create functions for the Radar and Trend charts.
```python
import plotly.graph_objects as go

def create_radar_chart(data):
    # Plotly radar logic
    pass
```

- [ ] **Step 2: Integrate Charts into app.py**
Add the 2x2 grid layout to `app.py` and connect it to the filtered data.

- [ ] **Step 3: Verify Interactivity**
Run: `streamlit run app.py`
Expected: Selecting a different model in the sidebar updates the charts instantly.

- [ ] **Step 4: Commit**
```bash
git add app.py
git commit -m "feat: add interactive plotly charts"
```

### Task 5: Groq AI Integration (On-Demand Analysis)

**Files:**
- Create: `utils/ai_agent.py`
- Modify: `app.py`

- [ ] **Step 1: Implement AI Agent**
Connect to Groq and implement the `get_chart_insight` function with caching.
```python
from groq import Groq
import streamlit as st

@st.cache_data
def get_chart_insight(data_context):
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    # Prompt and call logic
```

- [ ] **Step 2: Add "Analyze this Chart" Buttons**
Add the expander and button logic under each chart in `app.py`.

- [ ] **Step 3: Test AI Integration**
Run: `streamlit run app.py`
Expected: Clicking the button triggers a spinner and then displays a Storyteller/Strategist/Scientist summary.

- [ ] **Step 4: Commit**
```bash
git add utils/ai_agent.py app.py
git commit -m "feat: integrate groq ai for chart-level insights"
```

### Task 6: Final Polish & Visual Indicators

**Files:**
- Modify: `app.py`
- Modify: `styles/main.css`

- [ ] **Step 1: Add KPI Deltas**
Implement the 🔼/🔽 indicators for the top KPI row.

- [ ] **Step 2: Add Bike Hero Image**
Ensure the correct image from `assets/bikes/` displays when a model is selected.

- [ ] **Step 3: Final Verification**
Conduct a full walkthrough of all filters and AI analysis buttons.

- [ ] **Step 4: Commit**
```bash
git add app.py styles/main.css
git commit -m "polish: final ui refinements and visual indicators"
```
