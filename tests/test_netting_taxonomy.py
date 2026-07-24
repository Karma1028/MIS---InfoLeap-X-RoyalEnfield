import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from utils.netting_taxonomy import load_netting_taxonomy, SEGMENT_SHEETS, flatten_supernet_net


def _fake_sheet_rows():
    return [
        ("Supernet", "Net", "Sub-net", "Codelist", "Codes"),
        ("Visual Appearance", "Body Design", "Front profile", "Liked the round shaped headlight design", "002"),
        ("Visual Appearance", "Design Language", "Design Language", "Aggressive looks", "011"),
        ("Overall price", "Value for money", "Value for money", "Priced reasonably", "045"),
    ]


def test_load_netting_taxonomy_groups_by_supernet_then_net():
    mock_ws = MagicMock()
    mock_ws.iter_rows.return_value = _fake_sheet_rows()
    mock_wb = MagicMock()
    mock_wb.sheetnames = ["MQ2a+MQ2b_KBF"]
    mock_wb.__getitem__.return_value = mock_ws
    with patch("utils.netting_taxonomy.openpyxl.load_workbook", return_value=mock_wb):
        taxonomy = load_netting_taxonomy("fake_path.xlsx", "MQ2a+MQ2b_KBF")
    assert taxonomy == {
        "Visual Appearance": ["Body Design", "Design Language"],
        "Overall price": ["Value for money"],
    }


def test_load_netting_taxonomy_dedupes_repeated_net_within_supernet():
    rows = [
        ("Supernet", "Net", "Sub-net", "Codelist", "Codes"),
        ("Visual Appearance", "Body Design", "Front profile", "Liked headlight", "001"),
        ("Visual Appearance", "Body Design", "Rear profile", "Liked tail light", "002"),
    ]
    mock_ws = MagicMock()
    mock_ws.iter_rows.return_value = rows
    mock_wb = MagicMock()
    mock_wb.sheetnames = ["MQ2a+MQ2b_KBF"]
    mock_wb.__getitem__.return_value = mock_ws
    with patch("utils.netting_taxonomy.openpyxl.load_workbook", return_value=mock_wb):
        taxonomy = load_netting_taxonomy("fake_path.xlsx", "MQ2a+MQ2b_KBF")
    assert taxonomy == {"Visual Appearance": ["Body Design"]}


def test_load_netting_taxonomy_raises_clear_error_for_missing_sheet():
    mock_wb = MagicMock()
    mock_wb.sheetnames = ["SomeOtherSheet"]
    with patch("utils.netting_taxonomy.openpyxl.load_workbook", return_value=mock_wb):
        with pytest.raises(ValueError, match="not found"):
            load_netting_taxonomy("fake_path.xlsx", "MQ2a+MQ2b_KBF")


def test_segment_sheets_maps_all_three_segments():
    assert set(SEGMENT_SHEETS.keys()) == {"Acceptor", "Rejector", "Cancelled"}
    assert SEGMENT_SHEETS["Acceptor"] == "MQ2a+MQ2b_KBF"
    assert SEGMENT_SHEETS["Rejector"] == "MQ3a+MQ3b_Rejecter"
    assert SEGMENT_SHEETS["Cancelled"] == "MQ3a+MQ3b_Booked and cancelled"


def test_flatten_supernet_net_produces_readable_list():
    taxonomy = {"Visual Appearance": ["Body Design", "Design Language"], "Overall price": ["Value for money"]}
    flat = flatten_supernet_net(taxonomy)
    assert flat == [
        "Visual Appearance > Body Design",
        "Visual Appearance > Design Language",
        "Overall price > Value for money",
    ]
