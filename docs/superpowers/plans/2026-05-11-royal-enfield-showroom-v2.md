# Royal Enfield Digital Showroom V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform 50+ market research tables into a premium, "Midnight Chrome" digital showroom experience that traces the Passenger Journey through 4 distinct lifecycle stages, powered by an unbiased condition-based AI narrative.

**Architecture:** A multi-layered Streamlit application with a centralized **Condition Engine** for unbiased data analysis, a **Chameleon Theme** manager for dynamic variant styling, and a **Tri-Lens UI** for switching between simple charts, detailed tables, and advanced AI narratives.

**Tech Stack:** Python, Streamlit, Plotly, Groq API (Llama-3), Playwright (for scraping/verification).

---

### Task 1: Project Restructuring & Asset Recovery

**Files:**
- Create: `utils/assets.py`
- Modify: `app.py`
- Create: `utils/clean_assets.py`

- [ ] **Step 1: Write asset cleaner to remove "slop"**
Identify and delete HTML files incorrectly saved as .jpg in `assets/bikes/`.

```python
# utils/clean_assets.py
import os

def clean_assets(directory="assets/bikes"):
    for filename in os.listdir(directory):
        if filename.endswith(".jpg"):
            path = os.path.join(directory, filename)
            with open(path, "rb") as f:
                header = f.read(100).decode("utf-8", errors="ignore")
                if "<!DOCTYPE" in header or "<html" in header:
                    print(f"Deleting slop file: {path}")
                    os.remove(path)

if __name__ == "__main__":
    clean_assets()
```

- [ ] **Step 2: Run cleaner**
Run: `python utils/clean_assets.py`
Expected: Invalid files removed from `assets/bikes/`.

- [ ] **Step 3: Implement Multi-Source Asset Loader**
Create a robust loader that prioritizes: 1. Verified URLs, 2. Local valid files, 3. Live search fallback.

```python
# utils/assets.py
import os
import requests

VERIFIED_URLS = {
    "Classic 350": "https://www.royalenfield.com/content/dam/royal-enfield-revamp/header/shop/configure/classic-350.webp",
    "Himalayan 450": "https://www.royalenfield.com/content/dam/royal-enfield-revamp/header/shop/configure/himalayan-450.webp",
    # ... add other models from audit
}

def get_bike_image(model_name):
    # 1. Check Verified URLs
    if model_name in VERIFIED_URLS:
        return VERIFIED_URLS[model_name]
    
    # 2. Check Local Assets (if valid)
    local_path = f"assets/bikes/{model_name.replace(' ', '_')}.jpg"
    if os.path.exists(local_path) and os.path.getsize(local_path) > 10000:
        return local_path
        
    # 3. Fallback to generic RE Red texture or logo
    return "assets/re_logo.png"
```

- [ ] **Step 4: Commit**
```bash
git add utils/assets.py utils/clean_assets.py
git commit -m "restructure: asset recovery and cleaning"
```

---

### Task 2: The Condition Engine (Logic Layer)

**Files:**
- Create: `utils/logic_engine.py`
- Test: `tests/test_logic_engine.py`

- [ ] **Step 1: Define Condition Rules**
Implement a system that calculates unbiased "Flags" from the data.

```python
# utils/logic_engine.py
def evaluate_conditions(df, model, platform):
    results = {}
    # Rule 1: Tech Gap
    rejection_tech = df[(df['Table_Name'] == 'Reasons for rejection') & (df['Metric'].str.contains('Technology'))]['All_Avg'].mean()
    if rejection_tech > 15:
        results['TECH_GAP'] = True
    
    # Rule 2: Wait Time Pressure
    wait_time_rej = df[(df['Table_Name'] == 'Reasons for rejection') & (df['Metric'].str.contains('Waiting Period'))]['All_Avg'].mean()
    if wait_time_rej > 10:
        results['WAIT_TIME_CRITICAL'] = True
        
    return results
```

- [ ] **Step 2: Write tests for logic**
```python
# tests/test_logic_engine.py
from utils.logic_engine import evaluate_conditions
import pandas as pd

def test_tech_gap_rule():
    data = {'Table_Name': ['Reasons for rejection'], 'Metric': ['+[Technology]'], 'All_Avg': [20.0]}
    df = pd.DataFrame(data)
    flags = evaluate_conditions(df, "Classic 350", "All")
    assert flags['TECH_GAP'] is True
```

- [ ] **Step 3: Run tests**
Run: `pytest tests/test_logic_engine.py`
Expected: PASS.

- [ ] **Step 4: Commit**
```bash
git add utils/logic_engine.py tests/test_logic_engine.py
git commit -m "logic: unbiased condition engine"
```

---

### Task 3: Chameleon Theme Manager

**Files:**
- Create: `styles/showroom.css`
- Modify: `app.py`

- [ ] **Step 1: Define Theme Color Map**
Create a mapping of models to their signature colors.

```python
# In app.py
THEME_COLORS = {
    "Himalayan 450": "#2d5a27", # Pine Green
    "Classic 350": "#e31837",  # RE Red
    "Shotgun 650": "#2a52be",  # Plasma Blue
    # ...
}
```

- [ ] **Step 2: Create Dynamic CSS Injection**
Implement glassmorphism and dynamic accent colors.

```css
/* styles/showroom.css */
:root {
    --accent-color: #e31837;
}

[data-testid="stAppViewContainer"] {
    background-color: #050505;
    background-image: radial-gradient(circle at center, #111 0%, #050505 100%);
}

.glass-card {
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 1.5rem;
}
```

- [ ] **Step 3: Inject Style in app.py**
```python
# In app.py
def inject_theme(color):
    st.markdown(f"""
        <style>
        :root {{ --accent-color: {color}; }}
        /* ... existing showroom.css content ... */
        </style>
    """, unsafe_allow_html=True)
```

- [ ] **Step 4: Commit**
```bash
git add styles/showroom.css app.py
git commit -m "ui: chameleon theme and glassmorphism styling"
```

---

### Task 4: Tri-Lens UI Implementation

**Files:**
- Modify: `app.py`
- Modify: `utils/visuals.py`

- [ ] **Step 1: Implement Lens Navigation**
Add tabs for Simple, Table, and AI Brief.

```python
# In app.py
tabs = st.tabs(["📊 1. SIMPLE", "📑 2. TABLE", "🤖 3. AI BRIEF"])

with tabs[0]:
    render_simple_grid(df, model, platform, stage)
with tabs[1]:
    render_intel_table(df, model, platform, stage)
with tabs[2]:
    render_advanced_ai(df, model, platform, stage)
```

- [ ] **Step 2: Implement Dense Grid (Simple)**
Update `utils/visuals.py` to support 6-chart grid.

```python
# utils/visuals.py
def render_simple_grid(df, model, platform, stage):
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(create_age_dist(df, model, platform, stage))
        st.plotly_chart(create_income_dist(df, model, platform, stage))
    # ... more charts
```

- [ ] **Step 3: Implement Intel Table (Lens 2)**
Add heatmap-coded styling to the raw data.

```python
# In app.py
def render_intel_table(df, model, platform, stage):
    st.dataframe(
        df_filtered.style.background_gradient(subset=['MoM_Delta'], cmap='RdYlGn')
    )
```

- [ ] **Step 4: Commit**
```bash
git add app.py utils/visuals.py
git commit -m "ui: tri-lens implementation"
```

---

### Task 5: Advanced AI Briefing (Lens 3)

**Files:**
- Modify: `utils/intelligence.py`
- Modify: `app.py`

- [ ] **Step 1: Single-Prompt Bulk Generation**
Update the AI agent to take all chart data and condition flags in one prompt.

```python
# utils/intelligence.py
def generate_briefing(df, flags):
    prompt = f"Analyze this data for {model}. Conditions: {flags}. Table Summary: {df.to_json()}"
    # Call Groq API with unbiased instructions
    # ...
```

- [ ] **Step 2: Implement Advanced Visuals (Sankey/Radar)**
Add advanced chart functions to `utils/visuals.py`.

- [ ] **Step 3: Render AI Brief in app.py**
Include source tags and the logical synthesis story.

- [ ] **Step 4: Commit**
```bash
git add utils/intelligence.py app.py utils/visuals.py
git commit -m "ai: advanced briefing and narrative sync"
```

---

### Task 6: Final Verification & Polish

- [ ] **Step 1: UI Audit with Playwright**
Run headed browser test to verify theme switching and asset loading.
- [ ] **Step 2: Verify all 51 tables are reachable**
Walk through all stages and segments.
- [ ] **Step 3: Commit & Finish**
```bash
git commit -m "finish: royal enfield digital showroom v2 complete"
```
