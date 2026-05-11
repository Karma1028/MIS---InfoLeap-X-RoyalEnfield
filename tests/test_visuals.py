import pytest
import pandas as pd
import plotly.graph_objects as go
from utils.visuals import create_brand_radar, create_monthly_trends, create_buyer_segment_bar, create_anomaly_chart

@pytest.fixture
def sample_df():
    data = {
        "Platform": ["All"] * 20,
        "Model": ["Classic 350"] * 20,
        "Section": ["General"] * 20,
        "Table_Name": ["Brand Owned - Brand Wise"] * 5 + ["Age"] * 5 + ["Type of Buyer"] * 5 + ["Education"] * 5,
        "Metric": ["RE", "HONDA", "JAWA", "TVS", "BAJAJ", "18-25", "26-35", "36-45", "46+", "Total", "FTB", "Additional", "Replacement", "Upgrade", "Total", "Grad", "PG", "Diploma", "School", "Total"],
        "All_Avg": [70, 10, 5, 5, 10, 20, 50, 20, 10, 100, 40, 40, 20, 0, 100, 60, 20, 10, 10, 100],
        "Aug_25": [70, 10, 5, 5, 10, 20, 50, 20, 10, 100, 40, 40, 20, 0, 100, 60, 20, 10, 10, 100],
        "Sep_25": [72, 8, 6, 4, 10, 22, 48, 20, 10, 100, 42, 38, 20, 0, 100, 62, 18, 10, 10, 100],
        "Oct_25": [70, 10, 5, 5, 10, 20, 50, 20, 10, 100, 40, 40, 20, 0, 100, 60, 20, 10, 10, 100],
        "Nov_25": [70, 10, 5, 5, 10, 20, 50, 20, 10, 100, 40, 40, 20, 0, 100, 60, 20, 10, 10, 100],
        "Dec_25": [70, 10, 5, 5, 10, 20, 50, 20, 10, 100, 40, 40, 20, 0, 100, 60, 20, 10, 10, 100],
        "Jan_26": [70, 10, 5, 5, 10, 20, 50, 20, 10, 100, 40, 40, 20, 0, 100, 60, 20, 10, 10, 100],
        "Feb_26": [70, 10, 5, 5, 10, 20, 50, 20, 10, 100, 40, 40, 20, 0, 100, 60, 20, 10, 10, 100],
        "Mar_26": [70, 10, 5, 5, 10, 20, 50, 20, 10, 100, 40, 40, 20, 0, 100, 60, 20, 10, 10, 100],
        "Apr_26": [70, 10, 5, 5, 10, 20, 50, 20, 10, 100, 40, 40, 20, 0, 100, 60, 20, 10, 10, 100]
    }
    return pd.DataFrame(data)

def test_create_brand_radar(sample_df):
    fig = create_brand_radar(sample_df, "All", "Classic 350")
    assert isinstance(fig, go.Figure)

def test_create_monthly_trends(sample_df):
    fig = create_monthly_trends(sample_df, "All", "Classic 350")
    assert isinstance(fig, go.Figure)

def test_create_buyer_segment_bar(sample_df):
    fig = create_buyer_segment_bar(sample_df, "All", "Classic 350")
    assert isinstance(fig, go.Figure)

def test_create_anomaly_chart(sample_df):
    fig = create_anomaly_chart(sample_df, "All", "Classic 350")
    assert isinstance(fig, go.Figure)

def test_styling_consistency(sample_df):
    """Verify that all charts use the Midnight Chrome theme styling."""
    charts = [
        create_brand_radar(sample_df, "All", "Classic 350"),
        create_monthly_trends(sample_df, "All", "Classic 350"),
        create_buyer_segment_bar(sample_df, "All", "Classic 350"),
        create_anomaly_chart(sample_df, "All", "Classic 350")
    ]
    
    for fig in charts:
        # Check for transparent background
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
        # Check for white font
        assert fig.layout.font.color == "white"

def test_radar_color(sample_df):
    fig = create_brand_radar(sample_df, "All", "Classic 350")
    # Radar should use RE Red
    assert fig.data[0].line.color == "#e31837"

def test_buyer_bar_color(sample_df):
    fig = create_buyer_segment_bar(sample_df, "All", "Classic 350")
    # Bar should use RE Red
    assert fig.data[0].marker.color == "#e31837"

def test_empty_df_handling():
    empty_df = pd.DataFrame()
    functions = [create_brand_radar, create_monthly_trends, create_buyer_segment_bar, create_anomaly_chart]
    for func in functions:
        fig = func(empty_df, "All", "Classic 350")
        assert isinstance(fig, go.Figure)

def test_no_matches_handling(sample_df):
    # Test when filters return no rows
    fig = create_brand_radar(sample_df, "NonExistent", "NonExistent")
    assert "No Brand Data Available" in fig.layout.title.text

def test_empty_df_styling():
    """Verify that empty/fallback figures still use Midnight Chrome styling."""
    empty_df = pd.DataFrame()
    charts = [
        create_brand_radar(empty_df, "All", "Classic 350"),
        create_monthly_trends(empty_df, "All", "Classic 350"),
        create_buyer_segment_bar(empty_df, "All", "Classic 350"),
        create_anomaly_chart(empty_df, "All", "Classic 350")
    ]
    
    for fig in charts:
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.font.color == "white"
