# Royal Enfield Intelligent Dashboard - Project GEMINI

> **Main Instructions Reference**: [D:/antigravity project/karma - zeroclaw/.gemini/GEMINI.md](../../karma - zeroclaw/.gemini/GEMINI.md)

## 🎯 Project Vision
Transforming 50+ static market research tables into a premium, brand-oriented "Digital Showroom" dashboard with integrated autonomous AI analysis for Royal Enfield.

## 🛠️ Tech Stack
- **Frontend**: Streamlit (Midnight Chrome Theme)
- **Data**: Processed CSV (Long Format) / SQLite
- **AI**: Groq (Llama-3/Mixtral) - Autonomous Agentic Loop
- **Charts**: Plotly / D3.js

## 📝 Ongoing Progress
- [x] **Task 1: Project Initialization & Asset Scraping**
  - Created `requirements.txt`, `utils/assets_manager.py`.
  - Scraped 18 bike images.
- [x] **Task 2: Data Transformation (JSON to CSV)**
  - Created `utils/data_engine.py`.
  - Flattened 33MB JSON into `data/processed_data.csv`.
- [ ] **Task 3: Streamlit UI & "Midnight Chrome" Styling**
  - [ ] Create `styles/main.css`.
  - [ ] Implement `app.py` with sidebar and filters.
- [x] **Task 4: Interactive Plotly Charts**
  - Created `utils/visuals.py` with 4 charts.
- [x] **Task 5: Groq AI Integration (On-Demand Analysis)**
  - Created `utils/ai_agent.py` with 3 personas.
  - Implemented `.streamlit/secrets.toml`.
- [x] **Task 6: Final Polish & Visual Indicators**
  - Added MoM deltas and bike hero assets.
- [ ] **Task 7: Showroom Expansion (Comprehensive Data)**
  - [ ] Map all 51 tables to specific stages (Demographics, Behavioral, Segment Deep-Dive).
  - [ ] Implement multi-chart layouts for "Overall", "Acceptor", "Rejector", and "Cancelled".
  - [ ] Add interactive "Segment Switcher" to view data by buyer journey stage.


## 🧪 Testing Strategy (Standard: Karpathy/LENS)
- **UI Verification**: Use `webapp-testing` with Playwright in **headed mode** for visual audit.
- **Logic Verification**: TDD for all data processing and AI agentic reasoning.
- **Agent Audit**: Continuous debug loop for tool-use and context injection accuracy.

## 📂 Directory Map
- `data/`: Processed datasets.
- `assets/`: Bike images and brand logos.
- `utils/`: Core logic (Data Engine, AI Agent, Assets).
- `docs/`: Investigation notes and specs.
- `styles/`: Custom CSS for RE branding.
