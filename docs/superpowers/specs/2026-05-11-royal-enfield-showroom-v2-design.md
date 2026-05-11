# Design Spec: Royal Enfield Digital Showroom V2 (The Passenger Journey)

**Topic**: Advanced Market Research Dashboard  
**Date**: 2026-05-11  
**Status**: Approved (Drafting Plan)

## 1. Vision
Transform 50+ market research tables into a premium, "Midnight Chrome" digital showroom experience that traces the **Passenger Journey** through 4 distinct lifecycle stages, powered by an unbiased condition-based AI narrative.

## 2. Architecture: The 4-Stage Journey
The dashboard is structured into 4 logical "Nodes" based on data segmentation:
- **01. The Prospect (Base)**: Demographics, Income, Occupation, and overall interest.
- **02. The Acceptor (_1)**: Key buying factors, brand loyalty, and CC upgrade patterns.
- **03. The Rejector (_2)**: Reasons for rejection, competitive consideration (Honda, Jawa, etc.).
- **04. The Canceller (_3)**: Churn analysis (waiting periods, finance, dealership experience).

## 3. UI/UX: The Tri-Lens System
For every node, the user can toggle between three specialized "Lenses":

### Lens 1: Simple Dashboard (Dense Grid)
- **Visuals**: High-density grid of 5-6 standard charts (Bar, Line, Donut, Area).
- **Purpose**: Rapid aesthetic overview of the segment's core metrics.
- **Advanced Feature**: Dynamic layout that stays synced with the active lifecycle stage.

### Lens 2: Intel Table (The Stream)
- **Visuals**: A high-intensity "Terminal" table view.
- **Interaction**: Heatmap-coded rows (Neon Green for ↑, Royal Red for ↓ trends).
- **Features**: MoM Delta percentages and "Source ID" mapping to the raw 51 tables.

### Lens 3: Advanced AI Brief (Narrative Suite)
- **Visuals**: 2-3 Advanced charts (Sankey Flow, Radar Spider, Treemap Cluster).
- **Intelligence**: Unbiased, condition-based AI Storyteller.
- **Grounding**: "Visual Source Tags" (e.g., `[Ref: Chart A]`) that link story sentences to specific data points.

## 4. Branding: Chameleon Theme
The entire dashboard's DNA transforms based on the selected bike variant:
- **Himalayan 450**: Pine Green accents, rugged texture, adventure-themed icons.
- **Classic 350**: Chrome Red accents, heritage texture, classic aesthetic.
- **Shotgun 650**: Plasma Blue accents, neon-dark industrial texture.
- **Assets**: High-res bike shots scraped directly from the official RE homepage.

## 5. Technical Logic: The Condition Engine
AI narrative is strictly governed by a "Logic HUD":
- **Unbiased Rules**: Hard-coded thresholds (e.g., `IF Rejection > 20% THEN flag 'Critical Tech Gap'`).
- **Sync**: All 3 lenses share a unified state to ensure the table, the charts, and the story never contradict each other.

## 6. Success Criteria
- **Zero Hallucination**: Every AI claim must be traceable to a specific table row.
- **Zero Slop**: No HTML error pages masquerading as images.
- **High Density**: All 51 tables accessible and categorized.
- **Performance**: Instant load times via the "Insights Vault" caching system.
