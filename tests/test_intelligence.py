import pytest
import os
import json
from unittest.mock import MagicMock, patch
from utils.intelligence import IntelligenceVault, parse_briefing_response

# --- IntelligenceVault Tests ---

@pytest.fixture
def temp_vault_file(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    f = d / "insights_vault.json"
    return str(f)

def test_vault_get_miss(temp_vault_file):
    vault = IntelligenceVault(temp_vault_file)
    assert vault.get_insights("Classic 350", "Monthly") is None

def test_vault_save_and_get_hit(temp_vault_file):
    vault = IntelligenceVault(temp_vault_file)
    insights = {
        "storyteller": "The story of Classic 350...",
        "strategist": "The strategy for Classic 350...",
        "scientist": "The data for Classic 350..."
    }
    vault.save_insights("Classic 350", "Monthly", insights)
    
    # Reload vault to simulate persistence
    vault2 = IntelligenceVault(temp_vault_file)
    retrieved = vault2.get_insights("Classic 350", "Monthly")
    assert retrieved == insights

def test_vault_different_keys(temp_vault_file):
    vault = IntelligenceVault(temp_vault_file)
    vault.save_insights("Classic 350", "Monthly", {"text": "Classic Monthly"})
    vault.save_insights("Classic 350", "Quarterly", {"text": "Classic Quarterly"})
    vault.save_insights("Bullet 350", "Monthly", {"text": "Bullet Monthly"})
    
    assert vault.get_insights("Classic 350", "Monthly") == {"text": "Classic Monthly"}
    assert vault.get_insights("Classic 350", "Quarterly") == {"text": "Classic Quarterly"}
    assert vault.get_insights("Bullet 350", "Monthly") == {"text": "Bullet Monthly"}

# --- Parsing Tests ---

def test_parse_briefing_response_json():
    response = """
    ```json
    {
        "storyteller": "Human story content",
        "strategist": "Business strategy content",
        "scientist": "Data science content"
    }
    ```
    """
    parsed = parse_briefing_response(response)
    assert parsed["storyteller"] == "Human story content"
    assert parsed["strategist"] == "Business strategy content"
    assert parsed["scientist"] == "Data science content"

def test_parse_briefing_response_tags():
    response = """
    <storyteller>Human story content</storyteller>
    <strategist>Business strategy content</strategist>
    <scientist>Data science content</scientist>
    """
    parsed = parse_briefing_response(response)
    assert parsed["storyteller"] == "Human story content"
    assert parsed["strategist"] == "Business strategy content"
    assert parsed["scientist"] == "Data science content"

def test_parse_briefing_response_fallback():
    response = "This is a raw response without tags or JSON."
    parsed = parse_briefing_response(response)
    # If no tags/json found, it might put everything into one or return empty
    # Let's decide it returns at least storyteller as fallback or splits it
    assert "storyteller" in parsed
    assert response in parsed["storyteller"]

# --- Sentiment Tests ---

def test_get_sentiment_flag():
    from utils.intelligence import get_sentiment_flag
    
    assert get_sentiment_flag("We are seeing massive growth and opportunity.") == "Positive"
    assert get_sentiment_flag("There is a significant threat and decline in the market.") == "Warning"
    assert get_sentiment_flag("The data remains stable with no major changes.") == "Neutral"
    assert get_sentiment_flag("Growth is offset by threats.") == "Neutral" # 1 pos, 1 neg -> Neutral
