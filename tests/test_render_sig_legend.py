import pytest
pytest.importorskip("plotly")
pytest.importorskip("altair")
from unittest.mock import patch
from utils.visuals import render_sig_legend


def test_legend_states_95_by_default():
    with patch("utils.visuals.st.markdown") as mock_md:
        render_sig_legend()
        html = mock_md.call_args[0][0]
        assert "95%" in html


def test_legend_states_90_when_active():
    with patch("utils.visuals.st.markdown") as mock_md:
        render_sig_legend(active_confidence=0.90)
        html = mock_md.call_args[0][0]
        assert "90%" in html
        assert "Currently" in html or "currently" in html
