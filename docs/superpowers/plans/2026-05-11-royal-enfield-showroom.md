# Royal Enfield Digital Showroom Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the dashboard into a premium, auto-scrolling "Digital Showroom" with glassmorphism UI and instant AI intelligence.

**Architecture:** Streamlit host with custom CSS/JS injection for guided tour scrolling, persistent AI caching (Vault), and a multi-source asset loader to eliminate "slop".

**Tech Stack:** Streamlit, Python, JavaScript, Groq API, Plotly, Playwright.

---

## File Structure

- `app.py`: Updated layout and stage management.
- `styles/showroom.css`: Glassmorphism and Midnight Chrome styling.
- `utils/scroller.js`: JavaScript for smooth scrolling between stages.
- `utils/intelligence.py`: Bulk AI generation logic and `insights_vault.json` management.
- `utils/assets.py`: Multi-source image loader with headless fallback.
- `utils/visuals.py`: Enhanced custom-styled Plotly charts.

---

## Tasks

### Task 1: Showroom Layout & Glassmorphism Styling

**Files:**
- Create: `styles/showroom.css`
- Modify: `app.py`

- [ ] **Step 1: Create showroom.css**
Implement glassmorphism (`backdrop-filter: blur()`), "Midnight Chrome" variables, and Stage Layout classes.
```css
:root {
    --glass-bg: rgba(255, 255, 255, 0.05);
    --glass-border: rgba(255, 255, 255, 0.1);
}
.glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(10px);
    border: 1px solid var(--glass-border);
}
```

- [ ] **Step 2: Implement Page Stages in app.py**
Refactor the UI into 4 distinct `st.container` blocks (Stage 01-04).
```python
with st.container():
    st.markdown('<div id="stage-01" class="stage">...</div>', unsafe_allow_html=True)
```

- [ ] **Step 3: UI Verification**
Run: `python tests/verify_ui.py` (Update this to check for glassmorphism classes).
Expected: Dashboard background is pure dark, panels show blur effect.

- [ ] **Step 4: Commit**
```bash
git add styles/showroom.css app.py
git commit -m "feat: implement showroom layout and glassmorphism styling"
```

### Task 2: Auto-Scroll Engine (JS Injection)

**Files:**
- Create: `utils/scroller.js`
- Modify: `app.py`

- [ ] **Step 1: Create scroller.js**
Write a script to listen for stage changes and use `window.scrollTo` for smooth navigation.
```javascript
function scrollToStage(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
}
```

- [ ] **Step 2: Inject JS into app.py**
Use `streamlit.components.v1.html` or `st.markdown` to inject the scroll trigger when the selected model changes.

- [ ] **Step 3: Verification**
Run Playwright test in headed mode.
Expected: Selecting "Classic 350" causes the page to automatically scroll to the "Audience" stage.

- [ ] **Step 4: Commit**
```bash
git add utils/scroller.js app.py
git commit -m "feat: add auto-scroll engine for guided tour"
```

### Task 3: Intelligence Vault & Bulk AI Generation

**Files:**
- Create: `utils/intelligence.py`
- Create: `data/insights_vault.json`
- Modify: `app.py`

- [ ] **Step 1: Implement Intelligence Vault**
Create a class to handle reading/writing `insights_vault.json` with keys based on `(model, period)`.

- [ ] **Step 2: Bulk Generation Logic**
Write a function that sends all 4 chart contexts to Groq in ONE call and parses the response.
```python
def generate_showroom_briefing(model_data):
    # Prompt Groq for Storyteller, Strategist, Scientist perspectives
    # Return structured dict
```

- [ ] **Step 3: Integration**
Update `app.py` to check the vault first; if missing, trigger bulk generation and save.

- [ ] **Step 4: Commit**
```bash
git add utils/intelligence.py data/insights_vault.json app.py
git commit -m "feat: implement intelligence vault and bulk AI generation"
```

### Task 4: Multi-Source Asset Recovery

**Files:**
- Create: `utils/assets.py`
- Modify: `app.py`

- [ ] **Step 1: Implement VerifiedLoader**
Create a loader that iterates through Source 1 (Verified URLs), Source 2 (Local), Source 3 (Headless Search).

- [ ] **Step 2: Fix Image Search Logic**
Harden the search logic to simulate real user headers to bypass bot blocks.

- [ ] **Step 3: Verification**
Run: `pytest tests/test_assets.py`
Expected: Successfully returns a valid `.jpg` or `.png` binary/base64 for Classic 350.

- [ ] **Step 4: Commit**
```bash
git add utils/assets.py app.py
git commit -m "fix: implement robust multi-source asset loader"
```

### Task 5: Visual Sentiment & Final Polish

**Files:**
- Modify: `utils/visuals.py`
- Modify: `styles/showroom.css`
- Modify: `GEMINI.md`

- [ ] **Step 1: Sentiment Badges**
Update chart containers to include "Growth Glow" (CSS drop-shadow: green) or "Threat Pulse" (CSS animation: red) based on AI flags.

- [ ] **Step 2: Update Progress**
Update `GEMINI.md` to mark all tasks as complete.

- [ ] **Step 3: Final Audit**
Capture `dashboard_showroom_final.png` using Playwright.

- [ ] **Step 4: Commit**
```bash
git add utils/visuals.py styles/showroom.css GEMINI.md
git commit -m "polish: add sentiment badges and finalize showroom"
```
