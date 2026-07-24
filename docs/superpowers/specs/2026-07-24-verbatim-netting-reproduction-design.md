# Verbatim Netting Reproduction — Design Spec (Step 2 of 2)

Date: 2026-07-24
Status: drafted, pending user review — no code changed by this document

## Background

Step 1 (done, shipped): `utils/verbatim_intel.py`'s AI clustering now
anchors to the 4 field-methodology buckets (Product/Price/Dealership/
Personal) instead of inventing categories freely.

Step 2 (this doc): reproduce the live site's actual **Key Buying Factors /
Reasons for Rejection / Reasons for Cancelling** numbers — previously ruled
out of scope (CLAUDE.md, 2026-06-18) for lack of a coded source column. That
source now exists: 3 hidden reference sheets in the Masterfile workbook.

## The ground-truth taxonomy (confirmed directly, 2026-07-24)

`data/Enroute_Fourth Wave_Masterfile_Base_4010_AUG-MAY.xlsx` contains 3
extra sheets, each a flat 5-column netting table:

| Sheet | Rows | Feeds |
|---|---|---|
| `MQ2a+MQ2b_KBF` | 228 | Key Buying Factors (Acceptors) |
| `MQ3a+MQ3b_Rejecter` | 211 | Reasons for Rejection (Rejectors) |
| `MQ3a+MQ3b_Booked and cancelled` | 224 | Reasons for Cancelling (Cancelled) |

Columns: `Supernet | Net | Sub-net | Codelist | Codes`. Example row:
`Visual Appearance | Body Design | Front profile | "Liked the round shaped
headlight design" | 002`. This is a 3-level hierarchy (Supernet → Net →
Sub-net) with ~220 leaf `Codelist` phrases, each carrying a numeric `Codes`
value — i.e. a real manual coding frame, matching exactly what the live
site's `+[Top Category]` → `[Mid Category]` → leaf-phrase structure showed
in the scrape analysis.

## Confirmed: no respondent-level linkage (Path B applies)

Checked directly (2026-07-24): `data_updated`'s full column list has
exactly the 30 mq2/mq3 columns already known (`mq2a_1..3` + `_dis`,
`mq2b_1..3`, `mq2c_1..3` + `_dis`, `mq2d_1..3`, `mq3a_1..3` + `_dis`,
`mq3b_1..3`) — no additional column holds a `Codes`-range integer (1-230)
per verbatim slot. The `_dis` columns that do exist are decoded labels for
OTHER coded/multi-select fields, not a pre-assigned netting code for these
open-text answers. `mq2b`, `mq2d`, `mq3b` (the actual elaboration text) have
**no coded sibling at all**.

**Conclusion: the netting sheets are reference-only.** Coding against them
happened in a separate process/tool Infoleap used to build the live
dashboard — there's no row-level trace of it in our Masterfile. Reproducing
the live site's numbers means classifying each respondent's free text
against the ~220-entry Codelist ourselves.

## Build plan (Path B)

1. **Taxonomy loader** — new `utils/netting_taxonomy.py` (or a method on
   `DataEngine`): parses the 3 sheets into `{Supernet: {Net: {Sub-net:
   [Codelist phrases]}}}` per segment, cached at engine-load time (same
   pattern as `dq2_netting_codebook.json`'s load).
2. **LLM classification (not clustering)** — new function alongside
   `analyze_intent()`: for each respondent's verbatim (broad + elaboration),
   force the model to pick the single closest `Supernet > Net > Sub-net >
   Codelist` entry from the fixed list (or "no match" if genuinely nothing
   fits) — structured JSON output, not free generation. Batch 20-30
   respondents per call to control Groq free-tier rate/token limits (~220
   category names is a lot of prompt context per call — needs testing
   against actual token budgets).
3. **Aggregation table** — count classified respondents per Supernet (and
   per Net, drill-down style) → percentages, matching the live site's
   `+[Top Category]` / `[Mid Category]` display format from the scrape.
4. **New UI section** — "Key Buying Factors" / "Reasons for Rejection" /
   "Reasons for Cancelling", rendered like any other segment-page section
   (stacked bar or treemap, given ~15 Supernet categories — treemap likely
   reads better, matches the "too many bars" precedent from other treemap
   sections), sourced from data now genuinely comparable to the live
   dashboard.

## Cost/complexity flag

This is a real new capability, not a tuning pass — classifying ~4,000
respondents × up to 3 ranked slots × 2 verbatim fields against a large
category list is meaningfully more LLM calls than anything currently in
the app. Needs a caching strategy (cache per unique verbatim TEXT, not per
respondent — many respondents give near-identical short answers) to keep
this affordable on Groq's free tier. Worth a caching-cost estimate pass
before implementation starts.

## Open question for user

Proceed with this Path B build (taxonomy loader → batched LLM classifier →
aggregation table → new UI section), or is the cost/complexity enough to
park this and keep the current step-1 (4-bucket AI clustering) as the
verbatim feature's ceiling for now?
