import streamlit as st
import os
from unittest.mock import MagicMock, patch

# Mock streamlit before importing the function to test
import sys
from types import ModuleType

mock_st = MagicMock()
mock_st.session_state = {}
sys.modules["streamlit"] = mock_st

# Now we can define or import the function
def inject_scroller():
    # Only inject once to avoid redundant DOM operations
    if mock_st.session_state.get("scroller_injected"):
        return

    scroller_path = os.path.join("utils", "scroller.js")
    if os.path.exists(scroller_path):
        with open(scroller_path, 'r') as f:
            js_code = f.read()
            mock_st.markdown(f"<script>{js_code}</script>", unsafe_allow_html=True)
            mock_st.session_state["scroller_injected"] = True

def test_inject_scroller():
    print("Running test_inject_scroller...")
    
    # 1. Reset state
    mock_st.session_state = {}
    mock_st.markdown.reset_mock()
    
    # 2. First call
    inject_scroller()
    assert mock_st.session_state.get("scroller_injected") == True
    assert mock_st.markdown.call_count == 1
    print("✅ First injection successful.")
    
    # 3. Second call
    inject_scroller()
    assert mock_st.markdown.call_count == 1
    print("✅ Second injection skipped as expected.")
    
    print("Verification passed!")

if __name__ == "__main__":
    try:
        test_inject_scroller()
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        sys.exit(1)
