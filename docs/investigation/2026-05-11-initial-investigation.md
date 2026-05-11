# Royal Enfield MIS Dashboard Investigation

**Date**: 2026-05-11
**Project**: Royal Enfield MIS Study Infoleap Dashboard
**Source**: gdnindia.com/RoyalEnfield/

## 1. System Overview
The dashboard is a web-based MIS (Management Information System) reporting tool for Royal Enfield, likely used for market research and consumer study. It features static tables with deep longitudinal data.

## 2. Data Hierarchy & Segmentation

### A. Dimensions (Dropdowns)
- **Platforms**: J Platform (350CC), K Platform (450CC), P Platform (650CC).
- **Models**: Specific Royal Enfield models (Classic 350, Himalayan 450, Hunter 350, etc.).
- **Timeline**: 
    - **Monthly**: August 2025 to April 2026.
    - **Quarterly**: JAS'25 (July-Aug-Sept), OND'25 (Oct-Nov-Dec), JFM'26 (Jan-Feb-Mar).

### B. Core Pages (Tabs)
1. **Overall**: High-level summaries across all respondent types.
2. **Acceptor**: Analysis of customers who accepted the brand/product.
3. **Rejector**: Analysis of customers who rejected the product.
4. **Booked but Cancelled**: Critical segment analyzing churn/cancellation reasons.

## 3. Data Categories & Metrics

### Demographics
- **Age**: 18-25, 26-35, 36-45, 46+.
- **Education**: Professional, Graduate, Diploma, etc.
- **Occupation**: Full-time, Business, Student, Agriculture.
- **Household Income**: Brackets from <15k to >1 Lac.

### Consumer Behavior
- **Type of Buyer**: First-time vs Additional vs Replaced.
- **Previous Ownership**: Brand and CC (Engine Capacity) previously owned.
- **Consideration Set**: Other brands/models considered alongside Royal Enfield.

### Product Metrics
- **Engine Capacity (CC)**: 125cc, 150-199cc, 200-249cc, 250-350cc, 351cc+.
- **Brands Tracked**: Royal Enfield, Hero, Bajaj, Honda, TVS, Yamaha, KTM, Suzuki, Jawa, Harley Davidson, Triumph.

## 4. Analytical Features
- **Base (N)**: Each table starts with a "Base" row (Total sample size for that segment).
- **Significance Testing**: 
    - Green/Blue highlights indicate statistical significance at 95% or 90% confidence intervals.
    - Z-scores are embedded in the tooltips (e.g., `z = 2.752`).
- **Reporting Period Toggle**: Allows switching between Monthly and Quarterly views.
- **Sig Test Comparison**: Sig tests are performed against the "ALL" column.

## 5. Requirements for New Dashboard
- **Consolidation**: Turn 50+ individual tables into cohesive interactive charts.
- **Trend Analysis**: Visualize monthly/quarterly shifts in demographics and preferences.
- **Competitive Comparison**: Radar charts or bar comparisons for RE vs Competitors.
- **AI Insights**: Automated narratives summarizing significant shifts in data.
- **Filtering**: Retain the ability to drill down by Platform and Model.
