"""
Product Feature Ratings page — Q3/Q4 rotary switch satisfaction.
Q3: Right Rotary (Self-Start). Q4: Left Rotary (Pass/Beam).
1–5 scale -> 0–100 (same as CSAT: (mean-1)/4*100).
IMPORTANT: Q3/Q4 are answered by ACCEPTORS ONLY (0 Rejector/Cancelled responses).
Applicable to 5 rotary-equipped RE models: Classic 350, Hunter 350, Bullet 350,
Meteor 350, Goan Classic 350.
Verbatim text in q3_1, q3_2, q4_1.
"""
import random
import streamlit as st
import pandas as pd
import altair as alt
from utils.ai_summary import render_chart_ai_blurb
from utils.stat_engine import calculate_significance

FEATURES = {
    'q3': {
        'label': 'Right Rotary Switch — Self-Start',
        'verbatim_cols': ['q3_1', 'q3_2'],
        'color': '#0984E3',
    },
    'q4': {
        'label': 'Left Rotary Switch — Pass/Beam',
        'verbatim_cols': ['q4_1'],
        'color': '#6C5CE7',
    },
}

# RE model codes that have the rotary switch feature (confirmed from G9-A data)
ROTARY_MODELS = {
    2:  'Classic 350',
    3:  'Hunter 350',
    1:  'Bullet 350',
    4:  'Meteor 350',
    5:  'Goan Classic 350',
}


def _score(series):
    """Returns (mean_0_100, n) or (None, 0) if insufficient data."""
    s = series.dropna()
    n = len(s)
    if n < 5:
        return None, 0
    return round((float(s.mean()) - 1) / 4 * 100, 1), n


def render_product_features_page(engine, seg_dfs, selected_months):
    st.title("🔧 Product Feature Ratings")

    st.info(
        "**Acceptors only** — Q3/Q4 are asked exclusively to respondents who purchased "
        "one of 5 Royal Enfield models equipped with the retro rotary switch: "
        "Classic 350, Hunter 350, Bullet 350, Meteor 350, Goan Classic 350. "
        "Rejectors and Cancelled respondents have 0 responses (not applicable)."
    )

    acc_df = seg_dfs.get("Acceptors", pd.DataFrame())

    for q_col, meta in FEATURES.items():
        label = meta['label']
        color = meta['color']
        vb_cols = meta['verbatim_cols']

        st.markdown(f"### {label}")

        # --- Overall Acceptor hero card ---
        overall_score, overall_n = _score(acc_df[q_col]) if q_col in acc_df.columns else (None, 0)
        col_hero, col_scale = st.columns([1, 2])
        with col_hero:
            if overall_score is not None:
                st.markdown(
                    f"<div style='border:2px solid {color};border-radius:8px;"
                    f"padding:18px 14px;text-align:center;'>"
                    f"<div style='font-weight:700;color:#555;font-size:0.82rem;"
                    f"text-transform:uppercase;letter-spacing:0.04em;'>Acceptors Overall</div>"
                    f"<div style='font-size:2.6rem;font-weight:900;color:{color};"
                    f"line-height:1.1;margin:6px 0;'>{overall_score:.0f}</div>"
                    f"<div style='font-size:0.82rem;color:#777;'>/100 &nbsp;·&nbsp; n={overall_n:,}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='border:1px solid #ddd;border-radius:8px;"
                    f"padding:18px 14px;text-align:center;color:#bbb;'>"
                    f"<div style='font-size:0.82rem;'>Acceptors Overall</div>"
                    f"<div style='font-size:1.8rem;'>—</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # --- Per-model breakdown (5 rotary models) ---
        with col_scale:
            if q_col in acc_df.columns and 'acc' in acc_df.columns:
                model_rows = []
                for code, mname in ROTARY_MODELS.items():
                    mdf = acc_df[acc_df['acc'] == float(code)]
                    s, n = _score(mdf[q_col])
                    model_rows.append({'Model': mname, 'Score': s if s else 0.0, 'n': n, 'Valid': s is not None})
                mdf_chart = pd.DataFrame(model_rows)
                valid = mdf_chart[mdf_chart['Valid']].sort_values('Score', ascending=False)
                if not valid.empty:
                    bar = (
                        alt.Chart(valid)
                        .mark_bar(color=color, opacity=0.85)
                        .encode(
                            x=alt.X('Score:Q', scale=alt.Scale(domain=[0, 100]), title='Score (0–100)'),
                            y=alt.Y('Model:N', sort='-x', title=''),
                            tooltip=[
                                alt.Tooltip('Model:N'),
                                alt.Tooltip('Score:Q', format='.1f', title='Score /100'),
                                alt.Tooltip('n:Q', title='n'),
                            ],
                        )
                        .properties(height=140, title='Score by Model')
                    )
                    st.altair_chart(bar, use_container_width=True)
                    render_chart_ai_blurb(
                        {
                            "chart": f"{label} — Score by Model", "overall_score": overall_score,
                            "overall_n": overall_n,
                            "by_model": {r["Model"]: {"score": r["Score"], "n": r["n"]} for r in model_rows if r["Valid"]},
                        },
                        key=f"feat_model_ai_{q_col}",
                    )

                    with st.expander(f"Is the gap between models real? — {label}", expanded=False):
                        st.caption("Unpooled two-proportion Z-test on the 0-100 score, n≥30 required each side.")
                        _valid_rows = valid.to_dict("records")
                        _pair_rows = []
                        for i, r1 in enumerate(_valid_rows):
                            for r2 in _valid_rows[i + 1:]:
                                if r1["n"] < 30 or r2["n"] < 30:
                                    verdict = "— too few respondents (n<30)"
                                else:
                                    res = calculate_significance(r1["Score"] / 100, r1["n"], r2["Score"] / 100, r2["n"])
                                    if res["tier"] == "95":
                                        winner = r1["Model"] if res["z_score"] > 0 else r2["Model"]
                                        verdict = f"✓ {winner} significantly higher (95%)"
                                    elif res["tier"] == "90":
                                        winner = r1["Model"] if res["z_score"] > 0 else r2["Model"]
                                        verdict = f"~ {winner} likely higher (90%)"
                                    else:
                                        verdict = "Similar — no significant gap"
                                _pair_rows.append({"Comparison": f"{r1['Model']} vs {r2['Model']}", "Verdict": verdict})
                        if _pair_rows:
                            st.dataframe(pd.DataFrame(_pair_rows), use_container_width=True, hide_index=True)

        # --- Monthly trend (Acceptors only) ---
        month_rows = []
        for m in selected_months:
            if q_col not in acc_df.columns:
                continue
            mdf = acc_df[acc_df['month_label'] == m]
            s, n = _score(mdf[q_col])
            if s is not None:
                month_rows.append({'Month': m, 'Score': s, 'n': n, 'Suppressed': n < 30})

        if month_rows:
            trend_df = pd.DataFrame(month_rows)
            solid = trend_df[~trend_df['Suppressed']]
            dashed = trend_df[trend_df['Suppressed']]
            enc = dict(
                x=alt.X('Month:N', sort=selected_months, title=''),
                y=alt.Y('Score:Q', scale=alt.Scale(domain=[0, 100]), title='Score (0–100)'),
                tooltip=[
                    alt.Tooltip('Month:N'),
                    alt.Tooltip('Score:Q', format='.1f'),
                    alt.Tooltip('n:Q', title='n'),
                ],
            )
            layers = []
            if not solid.empty:
                layers.append(alt.Chart(solid).mark_line(point=True, color=color, strokeWidth=2).encode(**enc))
            if not dashed.empty:
                layers.append(
                    alt.Chart(dashed).mark_line(point=True, color=color,
                                                strokeDash=[4, 3], strokeWidth=1.5, opacity=0.5).encode(**enc)
                )
            if layers:
                chart = alt.layer(*layers).properties(
                    height=180,
                    title=f"{label} — Monthly Trend (Acceptors · dashed=n<30)"
                )
                st.altair_chart(chart, use_container_width=True)
                render_chart_ai_blurb(
                    {"chart": f"{label} — Monthly Trend", "month_rows": month_rows},
                    key=f"feat_trend_ai_{q_col}",
                )

        # --- Cross-link: does this feature's rating track overall dealership CSAT? ---
        if q_col in acc_df.columns and 'q5' in acc_df.columns and 'q6a' in acc_df.columns:
            _visited = acc_df[acc_df['q5'] == 1.0]
            _low_feat = _visited[_visited[q_col] <= 2]['q6a'].dropna()
            _high_feat = _visited[_visited[q_col] >= 4]['q6a'].dropna()
            if len(_low_feat) >= 5 and len(_high_feat) >= 5:
                _low_csat = (_low_feat.mean() - 1) / 4 * 100
                _high_csat = (_high_feat.mean() - 1) / 4 * 100
                with st.expander(f"Does {label} rating track overall showroom CSAT?", expanded=False):
                    st.caption(
                        "Among visitors who rated their showroom experience (Q6a), compares those who rated THIS "
                        "feature poorly (1-2) vs. well (4-5) — tests whether a product gripe is really a dealer-"
                        "experience gripe in disguise, or genuinely separate."
                    )
                    _c1, _c2 = st.columns(2)
                    _c1.metric(f"CSAT when {label.split(' — ')[0]} rated Low (1-2)", f"{_low_csat:.0f}/100", f"n={len(_low_feat):,}")
                    _c2.metric(f"CSAT when {label.split(' — ')[0]} rated High (4-5)", f"{_high_csat:.0f}/100", f"n={len(_high_feat):,}")
                    if len(_low_feat) >= 30 and len(_high_feat) >= 30:
                        _res = calculate_significance(_low_csat / 100, len(_low_feat), _high_csat / 100, len(_high_feat))
                        if _res["tier"]:
                            st.caption(f"Gap is statistically significant ({_res['tier']}% confidence) — this feature genuinely moves overall showroom satisfaction.")
                        else:
                            st.caption("Gap is not statistically significant — feature rating doesn't clearly move overall CSAT.")
                    else:
                        st.caption("Too few respondents (n<30 on one side) to run significance testing — directional only.")

        # --- Verbatim samples ---
        pool = []
        _total_verbatim_n = 0
        for vc in vb_cols:
            if vc in acc_df.columns:
                texts = (
                    acc_df[vc].dropna().astype(str)
                    .pipe(lambda s: s[s.str.len() > 8])
                    .tolist()
                )
                _total_verbatim_n += len(texts)
                random.seed(42)
                pool.extend(random.sample(texts, min(8, len(texts))))

        if pool:
            with st.expander(f"💬 Verbatim Samples — {label} (Acceptors)", expanded=False):
                if _total_verbatim_n < 30:
                    st.warning(
                        f"Only {_total_verbatim_n} verbatim responses exist for this feature (n<30 rule — see "
                        "DATA_FIELD_MAPPING.md) — these quotes are illustrative only, not a statistically reliable "
                        "sample. Do not generalize to all Acceptors from these alone."
                    )
                for txt in pool[:15]:
                    st.markdown(
                        f"<div style='border-left:3px solid {color};padding:4px 12px;margin:5px 0;"
                        f"font-size:0.84rem;color:#333;'>\"<em>{txt}</em>\"</div>",
                        unsafe_allow_html=True,
                    )

        st.markdown("---")
