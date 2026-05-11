import pytest
from unittest.mock import MagicMock, patch
from utils.ai_agent import get_chart_insight

def test_get_chart_insight_persona_prompts():
    """Verify that different personas generate different prompt styles (mocked)"""
    data_context = {"chart_name": "Test Chart", "data": [10, 20, 30]}
    
    with patch("utils.ai_agent.client") as mock_client:
        mock_client.chat.completions.create.return_value.choices[0].message.content = "Mocked AI Response"
        
        # Test Storyteller
        get_chart_insight(data_context, "Storyteller")
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt = kwargs["messages"][0]["content"] # System prompt is now at index 0
        assert "narrative" in prompt.lower() or "journey" in prompt.lower() or "story" in prompt.lower()
        
        # Test Strategist
        get_chart_insight(data_context, "Strategist")
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt = kwargs["messages"][0]["content"]
        assert "strategy" in prompt.lower() or "growth" in prompt.lower() or "threat" in prompt.lower()
        
        # Test Data Scientist
        get_chart_insight(data_context, "Data Scientist")
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt = kwargs["messages"][0]["content"]
        assert "statistical" in prompt.lower() or "anomaly" in prompt.lower() or "data" in prompt.lower()

@patch("utils.ai_agent.st.cache_data")
def test_caching_mechanism(mock_cache):
    """Verify that caching decorator is applied (basic check)"""
    # This is more of a structural check since we can't easily test streamlit caching in pure pytest without extra setup
    from utils.ai_agent import get_chart_insight
    assert hasattr(get_chart_insight, "__wrapped__") or mock_cache.called
