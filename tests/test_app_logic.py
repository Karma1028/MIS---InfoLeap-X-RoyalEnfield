import pandas as pd
import os
import pytest

def load_data_logic(csv_path):
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    else:
        return pd.DataFrame(columns=["Platform", "Model", "Section", "Table_Name", "Metric", "All_Avg"])

def filter_data_logic(df, platform, model):
    if df.empty:
        return df
    return df[(df["Platform"] == platform) & (df["Model"] == model)]

def test_data_loading():
    csv_path = os.path.join("data", "processed_data.csv")
    df = load_data_logic(csv_path)
    assert not df.empty, "Dataframe should not be empty"
    assert "Platform" in df.columns
    assert "Model" in df.columns

def test_data_filtering():
    csv_path = os.path.join("data", "processed_data.csv")
    df = load_data_logic(csv_path)
    
    if not df.empty:
        platforms = df["Platform"].unique()
        assert len(platforms) > 0
        
        selected_platform = platforms[0]
        models = df[df["Platform"] == selected_platform]["Model"].unique()
        assert len(models) > 0
        
        selected_model = models[0]
        filtered_df = filter_data_logic(df, selected_platform, selected_model)
        
        assert not filtered_df.empty
        assert (filtered_df["Platform"] == selected_platform).all()
        assert (filtered_df["Model"] == selected_model).all()
