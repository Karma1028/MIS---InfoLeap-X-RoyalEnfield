"""Loads Infoleap's own manual coding taxonomy for open-ended verbatim
questions (Key Buying Factors / Reasons for Rejection / Reasons for
Cancelling) from the 3 hidden reference sheets in the Masterfile workbook.

These sheets (`Supernet | Net | Sub-net | Codelist | Codes`) are the real
market-research netting scheme Infoleap's human coders used — confirmed
exact match against the live dashboard's scraped Acceptor numbers (9/11
Supernet categories, 2026-07-27).

CORRECTION (2026-07-27): an earlier investigation (2026-07-24) concluded no
respondent-level linkage to these codes existed anywhere in the Masterfile —
that was WRONG. `data_updated` has 3 columns literally named
`MQ2a+MQ2b_KBF` / `MQ3a+MQ3b_Rejecter` / `MQ3a+MQ3b_Booked and cancelled`
holding each respondent's own assigned codes as a concatenated 3-digit
string (e.g. "001020117176180" = codes 001, 020, 117...). `load_code_map()`
below decodes those against this sheet's `Codes` column — used by
`utils.data_engine.DataEngine.reasons_table()` for an exact, deterministic
reproduction, and by `utils/verbatim_intel.py`'s "Reproduce Live Site
Categories" section (formerly an LLM approximation over sampled verbatim
text — superseded by this exact method once the linkage was found)."""
import openpyxl
from utils.data_engine import MASTERFILE_PATH

SEGMENT_SHEETS = {
    "Acceptor": "MQ2a+MQ2b_KBF",
    "Rejector": "MQ3a+MQ3b_Rejecter",
    "Cancelled": "MQ3a+MQ3b_Booked and cancelled",
}


def sheet_for(segment, broad_prefix):
    """Rejector/Cancelled each offer 2 question pairs: an mq2*-prefixed
    positive pair ("why considered/liked RE" — same framing as Acceptor's
    KBF questions) and an mq3*-prefixed negative pair ("why rejected/
    cancelled" — that segment's own Reasons sheet). SEGMENT_SHEETS alone
    only has one sheet per segment, which is right for Acceptor (only ever
    asked mq2*) but wrong for the mq2* pair under Rejector/Cancelled — this
    routes by the ACTUAL question framing, not just the segment."""
    if broad_prefix.startswith("mq2"):
        return SEGMENT_SHEETS["Acceptor"]
    return SEGMENT_SHEETS[segment]


def load_code_map(masterfile_path, sheet_name):
    """{code (3-digit zero-padded string): (Supernet, Net)} — decodes the
    numeric Codes column of the netting sheet into a lookup usable against
    the per-respondent code strings in data_updated's MQ2a+MQ2b_KBF/
    MQ3a+MQ3b_Rejecter/MQ3a+MQ3b_Booked and cancelled columns (each a
    concatenation of 3-digit codes, e.g. "001020117" = codes 001, 020,
    117). Codes are zero-padded to 3 digits since the sheet's own Codes
    column isn't always consistently formatted (sometimes "2", sometimes
    "002") but the respondent-level strings always use fixed 3-digit
    chunks."""
    wb = openpyxl.load_workbook(masterfile_path, read_only=True, data_only=True)
    if sheet_name not in wb.sheetnames:
        raise ValueError(
            f"Netting sheet {sheet_name!r} not found in {masterfile_path!r}. "
            f"Available sheets: {wb.sheetnames}. Check SEGMENT_SHEETS against "
            f"the current Masterfile — sheet names can drift across monthly drops."
        )
    ws = wb[sheet_name]
    code_map = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # header row: Supernet, Net, Sub-net, Codelist, Codes
        if len(row) < 5:
            continue
        supernet, net, code = row[0], row[1], row[4]
        if not supernet or not net or code is None:
            continue
        code_str = str(code).strip().zfill(3)
        code_map[code_str] = (supernet, net)
    return code_map
