import pandas as pd
import pytest
from utils.logic_engine import evaluate_conditions

@pytest.fixture
def mock_df():
    data = [
        ['All', 'Classic 350', 'General', 'Reasons for rejection', 'Base : All_Classic 350', 100.0],
        ['All', 'Classic 350', 'General', 'Reasons for rejection', '+[Technology]', 20.0],
        ['All', 'Classic 350', 'General', 'Reasons for rejection', '+[Waiting Period]', 15.0],
        ['All', 'Classic 350', 'General', 'Brand Owned - Brand Wise', 'Base : All_Classic 350', 100.0],
        ['All', 'Classic 350', 'General', 'Brand Owned - Brand Wise', 'RE', 70.0],
        ['All', 'Classic 350', 'General', 'Reasons for cancelling', 'Base : All_Classic 350', 100.0],
        ['All', 'Classic 350', 'General', 'Reasons for cancelling', '+[Overall price]', 25.0],
        ['All', 'Bullet 350', 'General', 'Reasons for rejection', 'Base : All_Bullet 350', 30.0],
        ['All', 'Bullet 350', 'General', 'Reasons for rejection', '+[Technology]', 5.0],
    ]
    columns = ['Platform', 'Model', 'Section', 'Table_Name', 'Metric', 'All_Avg']
    return pd.DataFrame(data, columns=columns)

def test_evaluate_conditions_triggers_all(mock_df):
    flags = evaluate_conditions(mock_df, 'Classic 350', 'All')
    assert flags['TECH_GAP'] is True
    assert flags['WAIT_TIME_CRITICAL'] is True
    assert flags['LOYALTY_LOCK_IN'] is True
    assert flags['PRICE_SENSITIVITY'] is True
    assert flags['LOW_CONFIDENCE'] is False

def test_evaluate_conditions_low_confidence(mock_df):
    flags = evaluate_conditions(mock_df, 'Bullet 350', 'All')
    assert flags['LOW_CONFIDENCE'] is True
    assert flags['TECH_GAP'] is False

def test_evaluate_conditions_no_data(mock_df):
    flags = evaluate_conditions(mock_df, 'Non Existent', 'All')
    # Should probably return all False and LOW_CONFIDENCE True or just all False
    assert flags['LOW_CONFIDENCE'] is True
