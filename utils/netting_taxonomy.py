"""Loads Infoleap's own manual coding taxonomy for open-ended verbatim
questions (Key Buying Factors / Reasons for Rejection / Reasons for
Cancelling) from the 3 hidden reference sheets in the Masterfile workbook.

These sheets (`Supernet | Net | Sub-net | Codelist | Codes`) are a real
market-research netting scheme — almost certainly how the live Infoleap
dashboard's Reasons sections were actually coded (confirmed via live-site
scrape structure analysis, 2026-07-24: same 3-level Top/Mid/leaf hierarchy).

No respondent-level linkage to these codes exists anywhere in the Masterfile
(checked directly, 2026-07-24 — see docs/superpowers/specs/2026-07-24-
verbatim-netting-reproduction-design.md) — these sheets are reference-only.
`utils/verbatim_intel.py` uses this taxonomy to classify sampled respondent
verbatim text via LLM, approximating (not exactly reproducing) the live
site's category breakdowns."""
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


def load_netting_taxonomy(masterfile_path, sheet_name):
    """Returns {Supernet: [Net, Net, ...]} — Sub-net and Codelist/Codes
    columns are dropped (v1 classifies to Supernet+Net only). Net names
    deduplicated within each Supernet, insertion order preserved."""
    wb = openpyxl.load_workbook(masterfile_path, read_only=True, data_only=True)
    if sheet_name not in wb.sheetnames:
        raise ValueError(
            f"Netting sheet {sheet_name!r} not found in {masterfile_path!r}. "
            f"Available sheets: {wb.sheetnames}. Check SEGMENT_SHEETS against "
            f"the current Masterfile — sheet names can drift across monthly drops."
        )
    ws = wb[sheet_name]
    taxonomy = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # header row: Supernet, Net, Sub-net, Codelist, Codes
        if len(row) < 2:
            continue
        supernet, net = row[0], row[1]
        if not supernet or not net:
            continue
        nets = taxonomy.setdefault(supernet, [])
        if net not in nets:
            nets.append(net)
    return taxonomy


def flatten_supernet_net(taxonomy):
    """['Supernet > Net', ...] — the exact strings shown to the LLM as its
    fixed classification target list."""
    return [f"{supernet} > {net}" for supernet, nets in taxonomy.items() for net in nets]
