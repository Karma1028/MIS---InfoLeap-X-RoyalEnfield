import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

def create_brand_radar(df, platform, model):
    """Chart 1: Brand Comparison Radar (RE vs Competitors)"""
    if df.empty:
        return go.Figure().update_layout(
            title="No Data Available",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        )

    # Filter data
    filtered_df = df[(df["Platform"] == platform) & 
                     (df["Model"] == model) & 
                     (df["Table_Name"] == "Brand Owned - Brand Wise")]
    
    if filtered_df.empty:
        return go.Figure().update_layout(
            title="No Brand Data Available",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        )

    # Get top brands (excluding the model itself if it appears as a metric)
    brands = ["RE", "HONDA", "JAWA", "HARLEY DAVIDSON", "TVS", "BAJAJ", "SUZUKI", "YAMAHA", "TRIUMPH"]
    data = filtered_df[filtered_df["Metric"].isin(brands)]
    
    if data.empty:
        # Fallback to whatever is available
        data = filtered_df.head(5)

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=data["All_Avg"],
        theta=data["Metric"],
        fill='toself',
        line_color='#e31837'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, max(data["All_Avg"]) * 1.2 if not data.empty else 100]),
            bgcolor="rgba(0,0,0,0)"
        ),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=20, b=20),
        font=dict(color="white")
    )
    return fig

def create_monthly_trends(df, platform, model):
    """Chart 2: Monthly Trends (Age or Buyer Type)"""
    if df.empty:
        return go.Figure().update_layout(
            title="No Data Available",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        )

    # Let's use 'Age' for monthly trends
    filtered_df = df[(df["Platform"] == platform) & 
                     (df["Model"] == model) & 
                     (df["Table_Name"] == "Age") &
                     (df["Metric"] != "Total")]
    
    if filtered_df.empty:
        return go.Figure().update_layout(
            title="No Trend Data Available",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        )

    months = ["Aug_25", "Sep_25", "Oct_25", "Nov_25", "Dec_25", "Jan_26", "Feb_26", "Mar_26", "Apr_26"]
    
    fig = go.Figure()
    for _, row in filtered_df.iterrows():
        fig.add_trace(go.Scatter(
            x=months,
            y=[row[m] for m in months],
            mode='lines+markers',
            name=row["Metric"]
        ))

    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="Percentage (%)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=20, b=40),
        font=dict(color="white"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def create_buyer_segment_bar(df, platform, model):
    """Chart 3: Buyer Segment Bar Chart"""
    if df.empty:
        return go.Figure().update_layout(
            title="No Data Available",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        )

    filtered_df = df[(df["Platform"] == platform) & 
                     (df["Model"] == model) & 
                     (df["Table_Name"] == "Type of Buyer")].copy()
    
    if filtered_df.empty:
        return go.Figure().update_layout(
            title="No Buyer Data Available",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        )

    # Clean up metric names for display
    def clean_buyer_metric(m):
        if "Additional" in m: return "Additional"
        if "First Time" in m: return "First Time"
        if "Replaced" in m: return "Replacement"
        return m

    filtered_df["Clean_Metric"] = filtered_df["Metric"].apply(clean_buyer_metric)
    # Group by cleaned metric in case there are multiple "First Time" subcategories
    summary = filtered_df.groupby("Clean_Metric")["All_Avg"].mean().reset_index()

    fig = px.bar(
        summary, 
        x="Clean_Metric", 
        y="All_Avg",
        color_discrete_sequence=['#e31837']
    )

    fig.update_layout(
        xaxis_title="",
        yaxis_title="Percentage (%)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=20, b=40),
        font=dict(color="white")
    )
    return fig

def create_anomaly_chart(df, platform, model):
    """Chart 4: Anomaly/Significance Chart (Variance from Average)"""
    if df.empty:
        return go.Figure().update_layout(
            title="No Data Available",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        )

    # Focus on Education for this chart as an example of variety
    filtered_df = df[(df["Platform"] == platform) & 
                     (df["Model"] == model) & 
                     (df["Table_Name"] == "Education") &
                     (df["Metric"] != "Total")].copy()
    
    if filtered_df.empty:
        # Fallback to Age if Education not found
        filtered_df = df[(df["Platform"] == platform) & 
                         (df["Model"] == model) & 
                         (df["Table_Name"] == "Age") &
                         (df["Metric"] != "Total")].copy()

    if filtered_df.empty:
        return go.Figure().update_layout(
            title="No Data for Anomaly Detection",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        )

    months = ["Aug_25", "Sep_25", "Oct_25", "Nov_25", "Dec_25", "Jan_26", "Feb_26", "Mar_26", "Apr_26"]
    
    # Calculate MoM change for the most recent month (Apr_26) vs previous (Mar_26)
    filtered_df["MoM_Change"] = filtered_df["Apr_26"] - filtered_df["Mar_26"]
    
    fig = px.bar(
        filtered_df,
        x="Metric",
        y="MoM_Change",
        color="MoM_Change",
        color_continuous_scale='RdBu_r'
    )

    fig.update_layout(
        xaxis_title="",
        yaxis_title="MoM Change (pp)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=20, b=40),
        font=dict(color="white"),
        coloraxis_showscale=False
    )
    return fig
