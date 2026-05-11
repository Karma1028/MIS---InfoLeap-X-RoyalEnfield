import os
import json
import time
from unittest.mock import MagicMock, patch
from utils.intelligence import IntelligenceVault, generate_showroom_briefing
from groq import RateLimitError, APIStatusError, InternalServerError

def test_atomic_write():
    print("Testing atomic write...")
    vault_path = "data/test_vault.json"
    if os.path.exists(vault_path):
        os.remove(vault_path)
    
    vault = IntelligenceVault(vault_path=vault_path)
    
    # We want to verify that _save_vault uses os.replace
    # We can patch os.replace to see if it's called with the right arguments
    with patch("os.replace") as mock_replace:
        vault.save_insights("Classic 350", "Monthly", {"test": "data"})
        
        mock_replace.assert_called_once()
        args, _ = mock_replace.call_args
        assert args[0] == f"{vault_path}.tmp"
        assert args[1] == vault_path
        print("✅ Atomic write verified.")

def test_error_states():
    print("Testing structured error states...")
    model_data = {"dummy": "data"}
    model_name = "Classic 350"
    
    # 1. Test missing API key
    # Use patch.dict for os.environ and mock st.secrets
    mock_secrets = MagicMock()
    mock_secrets.get.return_value = None
    
    with patch("streamlit.secrets", mock_secrets), \
         patch.dict("os.environ", {"GROQ_API_KEY": ""}):
        result = generate_showroom_briefing(model_data, model_name)
        assert "Configuration Error" in result["storyteller"]
        assert "System offline" in result["strategist"]
        print("✅ Missing API key error verified.")

    # 2. Test RateLimitError (retriable)
    mock_secrets.get.return_value = "fake_key"
    with patch("streamlit.secrets", mock_secrets), \
         patch("utils.intelligence.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        
        # Raise RateLimitError 3 times
        mock_client.chat.completions.create.side_effect = RateLimitError(
            message="Rate limit reached",
            response=MagicMock(status_code=429),
            body={}
        )
        
        with patch("time.sleep"): # Skip sleep for speed
            result = generate_showroom_briefing(model_data, model_name)
            
        assert mock_client.chat.completions.create.call_count == 3
        assert "overloaded" in result["storyteller"]
        print("✅ RateLimitError handling verified.")

    # 4. Test APIStatusError 500 (retriable)
    mock_secrets.get.return_value = "fake_key"
    with patch("streamlit.secrets", mock_secrets), \
         patch("utils.intelligence.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        
        # Raise APIStatusError 500 3 times
        mock_client.chat.completions.create.side_effect = APIStatusError(
            message="Internal Server Error",
            response=MagicMock(status_code=500),
            body={}
        )
        
        with patch("time.sleep"): # Skip sleep for speed
            result = generate_showroom_briefing(model_data, model_name)
            
        assert mock_client.chat.completions.create.call_count == 3
        assert "Service interrupted" in result["storyteller"]
        print("✅ APIStatusError 500 handling verified.")

if __name__ == "__main__":
    try:
        test_atomic_write()
        test_error_states()
        print("\nALL VERIFICATIONS PASSED.")
    except Exception as e:
        print(f"\nVERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
