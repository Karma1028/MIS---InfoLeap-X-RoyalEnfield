"""Dealership Intelligence page — Q5 (showroom visit) + Q6a (satisfaction 1-5)."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from styles.theme import render_theme_css
from utils.ai_summary import render_chart_ai_blurb
from utils.data_engine import RE_MODEL_LABELS
from utils.stat_engine import calculate_significance

_SEG_META = [
    ("Acceptors",  "#39B54A", "Acceptor"),
    ("Rejectors",  "#C8102E", "Rejector"),
    ("Cancelled",  "#F7941D", "Cancelled"),
]
_PLOTLY_CFG = {"displayModeBar": False}
_RATING_LABELS = {1: "1 — Very Poor", 2: "2 — Poor", 3: "3 — Average", 4: "4 — Good", 5: "5 — Excellent"}
_RATING_COLORS = ["#C8102E", "#E8773A", "#F5C542", "#7EC8A4", "#39B54A"]


def _csat_stats(df):
    """Returns (visit_rate_pct, mean_score, n_visitors, rating_dist_dict, total_n) or None if insufficient."""
    if df is None or len(df) == 0:
        return None
    if 'q5' not in df.columns or 'q6a' not in df.columns:
        return None
    total = len(df)
    visited = df[df['q5'] == 1.0]
    visit_rate = len(visited) / total * 100
    scores = visited['q6a'].dropna()
    if len(scores) < 5:
        return None
    mean_score = scores.mean()
    n_visitors = len(scores)
    dist = {r: int((scores == r).sum()) for r in range(1, 6)}
    dist_pct = {r: dist[r] / n_visitors * 100 for r in range(1, 6)}
    return visit_rate, mean_score, n_visitors, dist_pct, total


def _net_satisfaction(dist_pct):
    """Promoter(4-5)% minus Detractor(1-2)% — NPS-style net score from the existing 1-5 CSAT distribution."""
    promoters = dist_pct.get(4, 0) + dist_pct.get(5, 0)
    detractors = dist_pct.get(1, 0) + dist_pct.get(2, 0)
    return promoters - detractors, promoters, detractors


def _pairwise_sig_badge(p1, n1, p2, n2, label1, label2):
    """One-line pairwise Z-test verdict between two segments' proportions (0-100 scale in, converted internally)."""
    res = calculate_significance(p1 / 100, n1, p2 / 100, n2)
    if res["tier"] == "95":
        winner = label1 if res["z_score"] > 0 else label2
        return f"✓ {winner} significantly higher (95%)"
    if res["tier"] == "90":
        winner = label1 if res["z_score"] > 0 else label2
        return f"~ {winner} likely higher (90%)"
    if n1 < 30 or n2 < 30:
        return "— too few respondents (n<30)"
    return "Similar — no significant gap"


def render_dealership_page(engine, seg_dfs, selected_months):
    render_theme_css()
    st.markdown("## 🏬 Dealership Intelligence")
    st.caption(
        "Based on Q5 (Did you visit a showroom?) and Q6a (Rate your showroom experience 1–5). "
        "CSAT computed only for respondents who visited (Q5 = Yes). N < 30 suppressed."
    )

    # ── Compute per-segment stats ──────────────────────────────────────────
    stats = {}
    for lbl, color, seg_key in _SEG_META:
        df = seg_dfs.get(lbl)
        if df is not None and len(df) > 0:
            result = _csat_stats(df)
            if result:
                stats[lbl] = {"color": color, "seg_key": seg_key, "data": result}

    if not stats:
        st.warning("No dealership data available under current filters.")
        return

    # ── Hero metrics: Visit Rate + CSAT per segment ────────────────────────
    st.markdown("### Showroom Visit Rate & Satisfaction Score")
    hero_cols = st.columns(len(stats))
    for col, (lbl, meta) in zip(hero_cols, stats.items()):
        visit_rate, mean_score, n_vis, dist_pct, total_n = meta["data"]
        csat_100 = (mean_score - 1) / 4 * 100
        stars = "★" * round(mean_score) + "☆" * (5 - round(mean_score))
        net_sat, promoters, detractors = _net_satisfaction(dist_pct)
        net_color = "#1B8A3F" if net_sat >= 0 else "#C8102E"
        with col:
            st.markdown(
                f"<div style='background:#fff;border:2px solid {meta['color']};border-radius:12px;"
                f"padding:16px 18px;text-align:center;'>"
                f"<div style='font-size:0.7rem;font-weight:700;color:{meta['color']};letter-spacing:1px;'>{lbl.upper()}</div>"
                f"<div style='font-size:2.2rem;font-weight:900;color:#1A1A1A;margin-top:4px;'>{csat_100:.0f}<span style='font-size:1rem;color:#9A958D'>/100</span></div>"
                f"<div style='font-size:0.85rem;color:#555;margin-top:2px;'>{stars}</div>"
                f"<div style='font-size:0.72rem;color:#9A958D;margin-top:6px;'>"
                f"Visit rate: <strong style='color:#1A1A1A'>{visit_rate:.0f}%</strong> · n={n_vis:,} visitors</div>"
                f"<div style='font-size:0.7rem;font-weight:700;color:{net_color};margin-top:4px;'>"
                f"Net Satisfaction: {net_sat:+.0f} ({promoters:.0f}% promoters − {detractors:.0f}% detractors)</div>"
                f"</div>",
                unsafe_allow_html=True
            )
    st.caption(
        "Net Satisfaction = % rating 4-5 minus % rating 1-2 (promoters minus detractors), same logic as an NPS score — "
        "positive means happy visitors outnumber unhappy ones."
    )

    st.markdown("<div style='margin:1rem 0'></div>", unsafe_allow_html=True)

    # ── Pairwise significance: is the visit-rate / CSAT gap between segments real? ──
    with st.container(border=True):
        st.markdown("#### Is the Gap Between Segments Real?")
        st.caption("Unpooled two-proportion Z-test (n≥30 required each side) — same engine used everywhere else in this dashboard.")
        seg_labels = list(stats.keys())
        sig_rows = []
        for i, l1 in enumerate(seg_labels):
            for l2 in seg_labels[i + 1:]:
                vr1, ms1, nv1, _, tn1 = stats[l1]["data"]
                vr2, ms2, nv2, _, tn2 = stats[l2]["data"]
                sig_rows.append({
                    "Comparison": f"{l1} vs {l2}", "Metric": "Visit Rate",
                    "Verdict": _pairwise_sig_badge(vr1, tn1, vr2, tn2, l1, l2),
                })
                sig_rows.append({
                    "Comparison": f"{l1} vs {l2}", "Metric": "CSAT (/100)",
                    "Verdict": _pairwise_sig_badge((ms1 - 1) / 4 * 100, nv1, (ms2 - 1) / 4 * 100, nv2, l1, l2),
                })
        st.dataframe(pd.DataFrame(sig_rows), use_container_width=True, hide_index=True)

    st.markdown("<div style='margin:1rem 0'></div>", unsafe_allow_html=True)

    # ── Never-visited vs visited-but-still-lost — only meaningful for Rejector/Cancelled ──
    _lost_segs = {lbl: seg_dfs.get(lbl) for lbl in ("Rejectors", "Cancelled") if seg_dfs.get(lbl) is not None and len(seg_dfs.get(lbl)) > 0}
    if _lost_segs:
        with st.container(border=True):
            st.markdown("#### Never Visited vs. Visited-but-Lost")
            st.caption(
                "Splits Rejectors/Cancelled into two different problems: never gave a showroom the chance (awareness/"
                "consideration gap) vs. visited and still didn't convert (product/dealer-experience gap). "
                "Same Q5 field already used above, just cut the other way."
            )
            _lost_rows = []
            for lbl, df in _lost_segs.items():
                if 'q5' not in df.columns:
                    continue
                total = len(df)
                never = int((df['q5'] == 2.0).sum())
                visited = int((df['q5'] == 1.0).sum())
                _lost_rows.append({
                    "Segment": lbl, "Total N": total,
                    "Never Visited": f"{never/total*100:.0f}% (n={never:,})",
                    "Visited but Lost": f"{visited/total*100:.0f}% (n={visited:,})" + (" — n<30" if visited < 30 else ""),
                })
            if _lost_rows:
                st.dataframe(pd.DataFrame(_lost_rows), use_container_width=True, hide_index=True)

    st.markdown("<div style='margin:1rem 0'></div>", unsafe_allow_html=True)

    # ── CSAT Distribution — grouped bar (ratings 1-5 per segment) ─────────
    with st.container(border=True):
        st.markdown("#### Rating Distribution (% of Visitors)")
        st.caption("How visitors in each segment rated their showroom experience.")

        fig = go.Figure()
        rating_labels = [_RATING_LABELS[r] for r in range(1, 6)]
        for lbl, meta in stats.items():
            _, _, _, dist_pct, _ = meta["data"]
            fig.add_trace(go.Bar(
                name=lbl,
                x=rating_labels,
                y=[dist_pct.get(r, 0) for r in range(1, 6)],
                marker_color=meta["color"],
                text=[f"{dist_pct.get(r, 0):.1f}%" for r in range(1, 6)],
                textposition="outside",
                cliponaxis=False,
            ))
        fig.update_layout(
            barmode="group",
            height=340,
            margin=dict(l=10, r=10, t=10, b=20),
            yaxis=dict(ticksuffix="%", showgrid=True, gridcolor="#F0EDE8", title=None),
            xaxis=dict(title=None),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CFG, key="deal_dist")

        _dist_facts = {
            "chart": "Dealership CSAT Rating Distribution",
            "segments": {
                lbl: {
                    "visit_rate_pct": round(meta["data"][0], 1),
                    "mean_score_of_5": round(meta["data"][1], 2),
                    "csat_0_100": round((meta["data"][1] - 1) / 4 * 100, 1),
                    "n_visitors": meta["data"][2],
                }
                for lbl, meta in stats.items()
            },
        }
        render_chart_ai_blurb(_dist_facts, key="deal_dist_ai")

    # ── CSAT Summary table ─────────────────────────────────────────────────
    with st.expander("📊 Data Table — CSAT by Segment", expanded=False):
        rows = []
        for lbl, meta in stats.items():
            visit_rate, mean_score, n_vis, dist_pct, total_n = meta["data"]
            row = {"Segment": lbl, "Visit Rate %": f"{visit_rate:.1f}%",
                   "Mean Score (/5)": f"{mean_score:.2f}",
                   "CSAT (/100)": f"{(mean_score-1)/4*100:.1f}",
                   "N (Visitors)": f"{n_vis:,}"}
            for r in range(1, 6):
                row[f"Rating {r}%"] = f"{dist_pct.get(r, 0):.1f}%"
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Monthly CSAT trend ─────────────────────────────────────────────────
    if selected_months and len(selected_months) >= 2:
        with st.container(border=True):
            st.markdown("#### CSAT Trend — Month over Month")
            st.caption("Mean satisfaction score (1–5) per month for each segment. Months with < 30 visitors suppressed.")

            import altair as alt
            trend_rows = []
            for lbl, meta in stats.items():
                df = seg_dfs.get(lbl)
                if df is None or 'q5' not in df.columns or 'q6a' not in df.columns:
                    continue
                for m in selected_months:
                    mdf = df[(df['month_label'] == m) & (df['q5'] == 1.0)]
                    scores = mdf['q6a'].dropna()
                    if len(scores) < 30:
                        continue
                    short_m = m.split("'")[0][:3] + "'" + m.split("'")[1][2:] if "'" in m else m
                    trend_rows.append({"Segment": lbl, "Month": short_m,
                                       "CSAT": (scores.mean() - 1) / 4 * 100,
                                       "N": len(scores)})
            if trend_rows:
                _tdf = pd.DataFrame(trend_rows)
                _color_scale = alt.Scale(
                    domain=["Acceptors", "Rejectors", "Cancelled"],
                    range=["#39B54A", "#C8102E", "#F7941D"]
                )
                chart = (
                    alt.Chart(_tdf)
                    .mark_line(point=True, strokeWidth=2.5)
                    .encode(
                        x=alt.X("Month:N", sort=None, title=None),
                        y=alt.Y("CSAT:Q", title="CSAT Score (/100)", scale=alt.Scale(domain=[0, 100])),
                        color=alt.Color("Segment:N", scale=_color_scale, legend=alt.Legend(title=None)),
                        tooltip=["Segment:N", "Month:N",
                                 alt.Tooltip("CSAT:Q", format=".1f", title="CSAT/100"),
                                 alt.Tooltip("N:Q", title="Visitors")],
                    )
                    .properties(height=260)
                    .configure_view(strokeWidth=0)
                    .configure_axis(grid=True, gridColor="#F0EDE8")
                )
                st.altair_chart(chart, use_container_width=True)
                render_chart_ai_blurb(
                    {"chart": "Dealership CSAT Monthly Trend", "trend_rows": trend_rows},
                    key="deal_trend_ai",
                )
            else:
                st.caption("Insufficient monthly data (< 30 visitors per month per segment).")

    # ── CSAT by RE Model — Acceptors only (mirrors Product Feature Ratings pattern) ──
    _acc_df = seg_dfs.get("Acceptors")
    if _acc_df is not None and 'acc' in _acc_df.columns:
        with st.container(border=True):
            st.markdown("#### CSAT by RE Model (Acceptors)")
            st.caption(
                "Model cut only applies to Acceptors — Rejectors/Cancelled didn't buy an RE model, so there's no "
                "RE-model dimension to cut their showroom experience by."
            )
            _model_rows = []
            for code, mname in RE_MODEL_LABELS.items():
                mdf = _acc_df[_acc_df['acc'] == float(code)]
                r = _csat_stats(mdf)
                if r:
                    _, mean_score, n_vis, _, _ = r
                    _model_rows.append({"Model": mname, "CSAT": round((mean_score - 1) / 4 * 100, 1), "n": n_vis})
            if _model_rows:
                import altair as alt
                _mdf_chart = pd.DataFrame(_model_rows).sort_values("CSAT", ascending=False)
                _bar = (
                    alt.Chart(_mdf_chart)
                    .mark_bar(color="#39B54A", opacity=0.85)
                    .encode(
                        x=alt.X("CSAT:Q", scale=alt.Scale(domain=[0, 100]), title="CSAT (0-100)"),
                        y=alt.Y("Model:N", sort="-x", title=""),
                        tooltip=[alt.Tooltip("Model:N"), alt.Tooltip("CSAT:Q", format=".1f"), alt.Tooltip("n:Q")],
                    )
                    .properties(height=max(140, 28 * len(_mdf_chart)))
                )
                st.altair_chart(_bar, use_container_width=True)
                render_chart_ai_blurb(
                    {"chart": "CSAT by RE Model (Acceptors)", "by_model": _model_rows},
                    key="deal_model_ai",
                )
            else:
                st.caption("Insufficient per-model visitor data (n<5) under current filters.")
