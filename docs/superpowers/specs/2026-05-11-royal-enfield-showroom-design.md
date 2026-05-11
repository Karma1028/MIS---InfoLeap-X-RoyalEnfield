# Royal Enfield Digital Showroom Dashboard Spec

## 1. Objective
Transform the static Royal Enfield MIS data into a premium, "Digital Showroom" experience. The dashboard will move away from generic templates to a custom-designed, agency-grade interface that uses auto-scrolling storytelling and high-fidelity AI intelligence.

## 2. Visual & Interaction Design (The "Showroom" Identity)
- **Theme**: "Midnight Chrome" (Urban Dark). 
    - Background: `#0a0a0a` (Pure dark).
    - Accents: Royal Enfield Red (`#e31837`).
    - Panels: Glassmorphism (semi-transparent with background blur).
- **Typography**: 
    - Headers: 'Syncopate' (Premium, wide-set sans-serif).
    - Body: 'Inter' (Modern, highly readable).
- **Interaction Model**: **Guided Tour (Auto-Scroll)**.
    - Selecting a model triggers a smooth scroll to the "Data Journey" stages.
    - Stage Indicators (01-04) tracking the story on the right-hand side.
- **Hero Section**: 
    - Large, edge-to-edge studio shots of bikes.
    - Floating "Frosted Glass" metric cards.

## 3. Data Intelligence Architecture (The "Instant Briefing")
- **AI Engine**: Groq API (Llama-3/Mixtral).
- **All-at-Once Generation**:
    - On page load or model selection, a single multi-persona request analyzes the entire data cut (Trends, Segments, Threats).
    - Output is parsed into distinct Storyteller (Narrative), Strategist (Action), and Scientist (Anomalies) blocks.
- **Persistent Caching (The Vault)**:
    - AI insights are saved to a local `insights_vault.json`.
    - Subsequent visits load these insights **instantly** (0ms) without API calls.
- **Visual Sentiment Badges**:
    - Charts are dynamically tagged with "Growth Glow" (Green) or "Threat Pulse" (Red) based on the AI's pre-flight analysis.

## 4. Asset Management (The "No-Slop" Fix)
- **Multi-Source Loader**:
    - Priority 1: Verified high-res studio shot URL.
    - Priority 2: Local `assets/bikes/` fallback.
    - Priority 3: Dynamic Search & Load (using Headless browser logic to bypass bot detection).
- **Competitor Assets**: Inclusion of high-quality brand logos for the radar chart comparison.

## 5. Technical Stack
- **Frontend**: Streamlit (with heavy Custom CSS and JavaScript injection for scrolling).
- **Visualizations**: Custom-styled Plotly charts (Transparent backgrounds, RE Red color palettes).
- **Logic**: Python-based data engine (Processed CSV from Task 2).
- **Verification**: Playwright in Headed Mode for "Karpathy-standard" UI audits.

## 6. Implementation Stages
1. **Showroom UI Overhaul**: CSS-heavy styling for glassmorphism and the hero container.
2. **Auto-Scroll Engine**: Implementation of the JS-in-Streamlit scrolling logic.
3. **Intelligence Vault**: Persistent AI caching layer.
4. **Asset Recovery**: Replacing broken images with verified high-res studio shots.
5. **Final Audit**: Full headed Playwright walkthrough and "Golden Screenshot" capture.
