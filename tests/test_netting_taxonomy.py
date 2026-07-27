import pytest
from unittest.mock import patch, MagicMock
from utils.netting_taxonomy import SEGMENT_SHEETS, sheet_for, load_code_map


def _fake_sheet_rows():
    return [
        ("Supernet", "Net", "Sub-net", "Codelist", "Codes"),
        ("Visual Appearance", "Body Design", "Front profile", "Liked the round shaped headlight design", "002"),
        ("Visual Appearance", "Design Language", "Design Language", "Aggressive looks", "011"),
        ("Overall price", "Value for money", "Value for money", "Priced reasonably", "045"),
    ]


def test_segment_sheets_maps_all_three_segments():
    assert set(SEGMENT_SHEETS.keys()) == {"Acceptor", "Rejector", "Cancelled"}
    assert SEGMENT_SHEETS["Acceptor"] == "MQ2a+MQ2b_KBF"
    assert SEGMENT_SHEETS["Rejector"] == "MQ3a+MQ3b_Rejecter"
    assert SEGMENT_SHEETS["Cancelled"] == "MQ3a+MQ3b_Booked and cancelled"


def test_sheet_for_acceptor_always_uses_kbf_sheet():
    assert sheet_for("Acceptor", "mq2a") == "MQ2a+MQ2b_KBF"


def test_sheet_for_rejector_mq2_pair_uses_kbf_sheet_not_rejecter_sheet():
    # Rejector's mq2c/mq2d pair asks "why they considered/liked RE" —
    # same positive framing as Acceptor's KBF questions, so it must be
    # classified against the KBF taxonomy, NOT the Rejecter (negative
    # framing) sheet, even though the segment is "Rejector".
    assert sheet_for("Rejector", "mq2c") == "MQ2a+MQ2b_KBF"


def test_sheet_for_rejector_mq3_pair_uses_rejecter_sheet():
    assert sheet_for("Rejector", "mq3a") == "MQ3a+MQ3b_Rejecter"


def test_sheet_for_cancelled_mq2_pair_uses_kbf_sheet():
    assert sheet_for("Cancelled", "mq2c") == "MQ2a+MQ2b_KBF"


def test_sheet_for_cancelled_mq3_pair_uses_cancelled_sheet():
    assert sheet_for("Cancelled", "mq3a") == "MQ3a+MQ3b_Booked and cancelled"


def test_load_code_map_keys_by_zero_padded_code():
    mock_ws = MagicMock()
    mock_ws.iter_rows.return_value = _fake_sheet_rows()
    mock_wb = MagicMock()
    mock_wb.sheetnames = ["MQ2a+MQ2b_KBF"]
    mock_wb.__getitem__.return_value = mock_ws
    with patch("utils.netting_taxonomy.openpyxl.load_workbook", return_value=mock_wb):
        code_map = load_code_map("fake_path.xlsx", "MQ2a+MQ2b_KBF")
    assert code_map == {
        "002": ("Visual Appearance", "Body Design"),
        "011": ("Visual Appearance", "Design Language"),
        "045": ("Overall price", "Value for money"),
    }


def test_load_code_map_zero_pads_short_codes():
    rows = [
        ("Supernet", "Net", "Sub-net", "Codelist", "Codes"),
        ("Visual Appearance", "Body Design", "Front profile", "Liked headlight", "2"),
    ]
    mock_ws = MagicMock()
    mock_ws.iter_rows.return_value = rows
    mock_wb = MagicMock()
    mock_wb.sheetnames = ["MQ2a+MQ2b_KBF"]
    mock_wb.__getitem__.return_value = mock_ws
    with patch("utils.netting_taxonomy.openpyxl.load_workbook", return_value=mock_wb):
        code_map = load_code_map("fake_path.xlsx", "MQ2a+MQ2b_KBF")
    assert code_map == {"002": ("Visual Appearance", "Body Design")}


def test_load_code_map_keeps_row_with_blank_net_falling_back_to_supernet():
    # Real data-quality gap found in the Rejecter sheet (2026-07-27): the
    # "Waiting Period" Supernet's row has a real Code but a blank Net cell
    # -- dropping the whole row (as the old code did) silently erased an
    # entire real category (21% of Rejectors, confirmed against the live
    # dashboard), not just a rounding difference.
    rows = [
        ("Supernet", "Net", "Sub-net", "Codelist", "Codes"),
        ("Waiting Period", None, None, "Very long waiting period", "183"),
    ]
    mock_ws = MagicMock()
    mock_ws.iter_rows.return_value = rows
    mock_wb = MagicMock()
    mock_wb.sheetnames = ["MQ3a+MQ3b_Rejecter"]
    mock_wb.__getitem__.return_value = mock_ws
    with patch("utils.netting_taxonomy.openpyxl.load_workbook", return_value=mock_wb):
        code_map = load_code_map("fake_path.xlsx", "MQ3a+MQ3b_Rejecter")
    assert code_map == {"183": ("Waiting Period", "Waiting Period")}


def test_load_code_map_raises_clear_error_for_missing_sheet():
    mock_wb = MagicMock()
    mock_wb.sheetnames = ["SomeOtherSheet"]
    with patch("utils.netting_taxonomy.openpyxl.load_workbook", return_value=mock_wb):
        with pytest.raises(ValueError, match="not found"):
            load_code_map("fake_path.xlsx", "MQ2a+MQ2b_KBF")
