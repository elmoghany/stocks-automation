"""Mine the live paper-day ledgers for REAL book observations.

Every row below is an inside bid/ask (and sometimes displayed depth)
that a live session actually read from the platform book and wrote to
data/paper_days/. These are the only ground truth we will ever have
for what the book looked like -- historical L2 does not exist and will
not be bought -- so they are the calibration targets for the bar-only
estimators in plan/liquidity_estimators.py.

CURATION, NOT PARSING. The ledgers are prose; a regex would silently
eat typos and mis-attribute symbols. Each observation was transcribed
by hand from the named ledger with its timestamp, then VALIDATED here:
whenever both bid and ask were logged, the canonical mid-denominated
spread is recomputed and compared against the ledger's own percent
(the ledgers mixed bid-, ask- and mid-denominators across days; the
validator tolerates that, and anything outside tolerance fails loudly
rather than entering the truth file).

Timebase notes:
  - time_et is the ET wall clock of the BOOK READ (act-time re-quote
    where one was taken, else the cycle window's midpoint --
    time_precision records which).
  - phase: premarket < 09:30 <= postopen (derived, not hand-coded).
  - requote=1 marks a re-read of a book already recorded within a few
    minutes (same fire / unchanged book): keep for the archive,
    exclude from correlation so serial duplicates do not inflate n.

Bars: rh_bars/{SYM}_{date}.csv (Robinhood, Days 8-13) else
massive/m1/{SYM}_{date}.csv (Massive SIP, Days 5-7). ALOY and NNNN
2026-08-10 have no bar file anywhere -- those rows carry
bars_source=null and are archived for a later Massive backfill.

Idempotent: `python plan/extract_liquidity_truth.py` rewrites
data/liquidity_truth.json from this table. To grow the sample, append
rows from new ledgers (or teach live sessions to log a
machine-readable book line -- see liquidity-estimation.md).
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(DATA, "liquidity_truth.json")

# (date, sym, time_et, bid, ask, logged_pct, depth_shares, depth_kind,
#  context, quality, requote, time_precision)
#   bid/ask None      -> ledger logged only a percent
#   logged_pct None   -> ledger logged only the raw book
#   depth_* None      -> no depth recorded at this read
E = "exact"    # explicit stamp in the ledger
C = "cycle"    # assigned from the cycle window (+/- ~3 min)

OBS = [
    # ---- Day 5, 2026-08-10 (ledger: 2026-08-10.md) ----
    ("2026-08-10", "ALOY", "07:43:00", 13.80, 14.00, 1.45, 212, "ask_to_cap", "veto SPREAD (B arming)", "ok", 0, E),
    ("2026-08-10", "SLN",  "07:43:00", 18.00, 18.30, 1.67, None, None, "veto SPREAD (rank2)", "ok", 0, E),
    ("2026-08-10", "ALOY", "07:47:00", 13.70, 14.00, 2.20, None, None, "veto holds", "ok", 0, E),
    ("2026-08-10", "ALOY", "07:52:00", 13.67, 13.90, 1.68, None, None, "veto holds", "ok", 0, E),
    ("2026-08-10", "SLN",  "07:52:00", 16.00, 16.38, 2.35, None, None, "watch", "ok", 0, E),
    ("2026-08-10", "STI",  "08:44:00",  7.89,  8.44, 6.70, None, None, "watch (near-untradeable)", "ok", 0, C),
    ("2026-08-10", "SLN",  "08:44:00", 15.06, 15.25, 1.26, None, None, "veto holds", "ok", 0, C),
    ("2026-08-10", "NNNN", "08:52:00", 10.06, 13.00, 29.0, None, None, "watch", "stale_tape", 0, C),
    ("2026-08-10", "SLN",  "08:52:00", 15.40, 15.67, 1.75, None, None, "veto holds", "ok", 0, C),
    ("2026-08-10", "SLN",  "08:57:00", 15.25, 15.90, 4.10, None, None, "veto holds (widened)", "ok", 0, C),
    ("2026-08-10", "ALOY", "08:57:00", 13.20, 13.35, 1.10, None, None, "ineligible, book read", "ok", 0, C),
    ("2026-08-10", "SLN",  "09:02:00", 15.80, 16.22, 2.60, None, None, "veto holds", "ok", 0, C),
    ("2026-08-10", "SLN",  "09:07:00", 15.90, 16.22, 2.00, None, None, "veto holds", "ok", 0, C),
    ("2026-08-10", "STI",  "09:07:00",  7.89,  8.44, 6.70, None, None, "veto (same book as 08:44)", "ok", 1, C),
    ("2026-08-10", "SLN",  "09:12:00", 16.00, 16.22, 1.40, None, None, "veto holds (tightening)", "ok", 0, C),
    ("2026-08-10", "SLN",  "09:20:00", 16.60, 16.88, 1.70, None, None, "veto holds", "ok", 0, C),
    ("2026-08-10", "SLN",  "09:22:00", 16.55, 16.68, 0.78, None, None, "compressing toward cap", "ok", 0, C),
    ("2026-08-10", "SLN",  "09:27:00", 16.73, 17.20, 2.80, None, None, "widened auction-adjacent", "auction_adjacent", 0, C),
    ("2026-08-10", "SLN",  "09:31:24", 16.43, 16.71, 1.70, None, None, "veto holds at open", "ok", 0, E),
    ("2026-08-10", "CLRO", "09:40:00", 11.74, 11.90, 1.36, 0, "ask_to_cap", "veto SPREAD+DEPTH (zero ask in band)", "ok", 0, C),
    ("2026-08-10", "NESR", "09:40:00", 33.41, 33.60, 0.57, 2295, "ask_to_cap", "one tick from clean", "ok", 0, C),
    ("2026-08-10", "NESR", "09:45:00", 33.36, 33.78, 1.26, 2582, "ask_to_cap", "veto SPREAD (B arming)", "ok", 0, C),
    ("2026-08-10", "PIII", "09:45:00", None, None,  4.70, None, None, "untrusted thin name", "ok", 0, C),
    ("2026-08-10", "LFST", "09:46:00", 11.99, 12.03, 0.33, 2858, "ask_to_cap", "first clean book of day; entered 09:47", "ok", 0, E),
    ("2026-08-10", "LFST", "14:53:02", 12.02, 12.03, None, 1242, "bid_swept_2lv", "exit ladder book", "ok", 0, E),

    # ---- Day 6, 2026-08-11 (ledger: 2026-08-11.md) ----
    ("2026-08-11", "KOPN", "07:24:00", 4.65, 4.80, 3.10, None, None, "veto SPREAD (B arming)", "ok", 0, C),
    ("2026-08-11", "KOPN", "07:28:00", 4.65, 4.80, 3.20, 503, "ask_to_cap", "veto stands", "ok", 1, C),
    ("2026-08-11", "FF",   "07:33:00", 6.32, 6.63, 4.80, None, None, "veto (also chase-blocked)", "ok", 0, C),
    ("2026-08-11", "KOPN", "07:33:00", 4.58, 4.70, 2.60, None, None, "veto stands", "ok", 0, C),
    ("2026-08-11", "FF",   "07:38:00", 6.27, 6.36, 1.40, 1528, "ask_to_cap", "veto SPREAD", "ok", 0, C),
    ("2026-08-11", "KOPN", "07:38:00", 4.59, 4.70, 2.40, None, None, "veto stands", "ok", 0, C),
    ("2026-08-11", "KOPN", "07:43:00", 4.58, 4.70, 2.59, 2903, "ask_to_cap", "veto SPREAD+DEPTH", "ok", 0, C),
    ("2026-08-11", "KOPN", "07:48:00", None, None, 2.37, 2912, "ask_to_cap", "veto stands", "ok", 0, C),
    ("2026-08-11", "FRMI", "07:48:00", 6.77, 6.79, 0.30, 8176, "ask_to_cap", "clean book, no trigger near", "ok", 0, C),
    ("2026-08-11", "FRMI", "07:53:00", 6.81, 6.90, 1.31, 8059, "ask_to_cap", "veto SPREAD (B arming)", "ok", 0, C),
    ("2026-08-11", "RIOT", "07:58:00", 22.40, 22.55, 0.67, None, None, "veto SPREAD (B arming)", "ok", 0, C),
    ("2026-08-11", "FRMI", "07:58:00", None, None, 0.15, 10400, "ask_to_cap", "clean book", "ok", 0, C),
    ("2026-08-11", "RIOT", "08:03:00", None, None, 1.90, None, None, "spread blew out", "ok", 0, C),
    ("2026-08-11", "FRMI", "08:04:00", 6.72, 6.73, 0.15, 10465, "ask_to_cap", "ARMED stop-buy 7.27", "ok", 0, E),
    ("2026-08-11", "FF",   "08:08:00", 6.42, 6.47, 0.77, None, None, "veto SPREAD (B arming)", "ok", 0, C),
    ("2026-08-11", "RIOT", "08:08:00", None, None, 0.41, None, None, "spread cleared", "ok", 0, C),
    ("2026-08-11", "FF",   "08:13:00", None, None, 0.31, 162, "ask_to_cap", "DEPTH SKIP (<25% floor)", "ok", 0, C),
    ("2026-08-11", "FF",   "08:18:00", 6.30, 6.45, 2.35, 199, "ask_to_cap", "book flapped wide again", "ok", 0, C),
    ("2026-08-11", "FRMI", "08:24:00", 6.90, 6.91, 0.14, 18000, "ask_to_cap", "RE-ARMED stop-buy 7.27", "ok", 0, E),
    ("2026-08-11", "FRMI", "08:28:00", 6.91, 6.93, 0.29, 14864, "ask_to_cap", "keep armed", "ok", 0, C),
    ("2026-08-11", "FRMI", "08:38:00", None, None, 1.00, 21600, "ask_to_cap", "keep armed", "ok", 0, C),
    ("2026-08-11", "FRMI", "08:43:00", 6.95, 6.97, 0.29, 15000, "ask_to_cap", "keep armed", "ok", 0, C),
    ("2026-08-11", "FRMI", "08:48:00", 7.17, 7.18, 0.14, 4072, "ask_to_cap", "walking into trigger", "ok", 0, C),
    ("2026-08-11", "FRMI", "08:51:34", 7.26, 7.27, None, None, None, "ask on the trigger", "ok", 0, E),

    # ---- Day 7, 2026-08-12 (ledger: 2026-08-12.md) ----
    ("2026-08-12", "SMWB", "07:20:00", 8.35, 8.50, 1.80, 1500, "ask_to_cap", "veto SPREAD (B arming)", "ok", 0, C),
    ("2026-08-12", "VELO", "07:20:00", 16.05, 16.24, 1.18, None, None, "rank2 book read", "ok", 0, C),
    ("2026-08-12", "SMWB", "07:26:00", 8.36, 8.50, 1.67, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "VELO", "07:26:00", 16.05, 16.29, 1.49, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "SMWB", "07:28:00", 7.58, 8.28, 9.20, 200, "bid_inside_2lv", "book deteriorated (100@7.58+100@7.54)", "ok", 0, C),
    ("2026-08-12", "VELO", "07:28:00", 16.05, 16.21, 1.00, 884, "ask_inside", "veto", "ok", 0, C),
    ("2026-08-12", "SMWB", "07:31:00", 7.52, 8.28, None, None, None, "book collapsed", "ok", 0, C),
    ("2026-08-12", "VELO", "07:31:54", 16.01, 16.21, 1.23, 6902, "ask_to_cap", "veto SPREAD (B arming)", "ok", 0, E),
    ("2026-08-12", "DFTX", "07:38:00", 49.01, 49.50, 1.00, 204, "ask_to_cap", "veto SPREAD (B arming)", "ok", 0, C),
    ("2026-08-12", "VELO", "07:38:00", 15.84, 16.10, 1.64, None, None, "rank2", "ok", 0, C),
    ("2026-08-12", "NTHI", "07:38:00", 4.45, 5.22, 14.75, None, None, "rank3 book read", "ok", 0, C),
    ("2026-08-12", "SMWB", "07:42:00", 7.52, 8.18, 8.41, None, None, "veto, nothing armable", "ok", 0, C),
    ("2026-08-12", "DFTX", "07:42:00", 48.75, 49.40, 1.32, 4208, "ask_to_cap", "veto", "ok", 0, C),
    ("2026-08-12", "DFTX", "07:46:00", 49.00, 49.50, 1.01, 3607, "ask_to_cap", "veto SPREAD (B arming)", "ok", 0, C),
    ("2026-08-12", "VELO", "07:46:00", None, None, 1.72, None, None, "rank2", "ok", 0, C),
    ("2026-08-12", "SMWB", "07:46:00", None, None, 7.73, None, None, "rank3", "ok", 0, C),
    ("2026-08-12", "DFTX", "07:51:00", 48.00, 48.40, 0.83, 12176, "ask_to_cap", "veto, converging on cap", "ok", 0, C),
    ("2026-08-12", "VELO", "07:51:00", None, None, 1.72, None, None, "rank2", "ok", 1, C),
    ("2026-08-12", "SMWB", "07:51:00", None, None, 9.94, None, None, "rank3", "ok", 0, C),
    ("2026-08-12", "NTHI", "07:51:00", None, None, 16.09, None, None, "rank4", "ok", 0, C),
    ("2026-08-12", "SMWB", "07:56:00", 7.52, 8.58, 12.35, 240, "bid_inside_2lv", "veto -- only 240 sh resting bid", "ok", 0, C),
    ("2026-08-12", "VELO", "07:56:00", 16.31, 16.50, 1.15, 76, "ask_to_cap", "veto", "ok", 0, C),
    ("2026-08-12", "DFTX", "07:56:00", 48.10, 48.20, 0.21, None, None, "first cap PASS of day (rank4)", "ok", 0, C),
    ("2026-08-12", "NTHI", "07:56:00", 4.75, 4.89, 2.86, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "SMWB", "08:01:00", 7.75, 8.68, 10.71, 0, "ask_to_cap", "veto, zero ask in cap band", "ok", 0, C),
    ("2026-08-12", "VELO", "08:01:00", 16.41, 16.50, 0.55, 504, "ask_to_cap", "a whisker above cap", "ok", 0, C),
    ("2026-08-12", "DFTX", "08:01:00", None, None, 0.35, None, None, "spread PASS, coil-blocked", "ok", 0, C),
    ("2026-08-12", "SMWB", "08:06:00", 7.77, 8.68, 11.07, 0, "ask_to_cap", "veto", "ok", 0, C),
    ("2026-08-12", "VELO", "08:06:00", None, None, 0.73, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "DFTX", "08:06:00", None, None, 0.77, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "DFTX", "08:11:00", 48.00, 48.85, 1.74, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "VELO", "08:11:00", None, None, 1.82, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "BRUN", "08:11:00", None, None, 0.89, None, None, "ineligible, book tightened", "ok", 0, C),
    ("2026-08-12", "SMWB", "08:16:00", 7.61, 8.48, 10.81, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "VELO", "08:16:00", None, None, 1.96, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "DFTX", "08:16:00", None, None, 0.10, None, None, "tightest of day", "ok", 0, C),
    ("2026-08-12", "SMWB", "08:21:00", 7.52, 8.48, 11.32, None, None, "veto", "ok", 1, C),
    ("2026-08-12", "VELO", "08:21:00", None, None, 1.76, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "DFTX", "08:21:00", None, None, 0.81, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "SMWB", "08:26:00", 8.22, 8.48, 3.07, None, None, "much improved, still veto", "ok", 0, C),
    ("2026-08-12", "VELO", "08:26:00", None, None, 2.44, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "SMWB", "08:31:00", 8.22, 8.48, 3.07, None, None, "veto (book unchanged)", "ok", 1, C),
    ("2026-08-12", "SMWB", "08:36:00", 8.22, 8.48, 3.11, None, None, "veto", "ok", 1, C),
    ("2026-08-12", "VELO", "08:36:00", 16.80, 16.91, 0.65, None, None, "tightest yet, still veto", "ok", 0, C),
    ("2026-08-12", "BRUN", "08:36:00", None, None, 1.45, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "SMWB", "08:41:00", 8.22, 8.48, 3.11, None, None, "veto (book unchanged)", "ok", 1, C),
    ("2026-08-12", "VELO", "08:41:00", None, None, 1.55, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "BRUN", "08:41:00", None, None, 1.78, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "DFTX", "08:41:00", None, None, 1.47, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "AXTI", "08:41:00", None, None, 0.30, None, None, "tightest of day, under +10% line", "ok", 0, C),
    ("2026-08-12", "SMWB", "08:46:00", 8.24, 8.48, 2.87, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "VELO", "08:46:00", None, None, 0.60, None, None, "nearly tradeable", "ok", 0, C),
    ("2026-08-12", "BRUN", "08:46:00", None, None, 1.30, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "AXTI", "08:46:00", None, None, 0.51, None, None, "under the line", "ok", 0, C),
    ("2026-08-12", "SMWB", "08:51:00", 8.24, 8.48, 2.83, None, None, "veto", "ok", 1, C),
    ("2026-08-12", "VELO", "08:51:00", None, None, 1.36, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "BRUN", "08:51:00", None, None, 1.29, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "AXTI", "08:51:00", None, None, 0.40, None, None, "under the line", "ok", 0, C),
    ("2026-08-12", "SMWB", "08:56:00", 8.28, 8.48, 2.36, None, None, "veto", "ok", 0, C),
    ("2026-08-12", "VELO", "08:56:00", None, None, 0.77, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "AXTI", "08:56:00", None, None, 0.34, None, None, "under the line", "ok", 0, C),
    ("2026-08-12", "SMWB", "09:01:00", 7.52, 8.48, 12.00, None, None, "blew back out", "ok", 0, C),
    ("2026-08-12", "VELO", "09:01:00", None, None, 1.18, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "BRUN", "09:01:00", None, None, 1.06, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "AXTI", "09:01:00", None, None, 0.34, None, None, "under the line", "ok", 1, C),
    ("2026-08-12", "SMWB", "09:06:00", 7.52, 8.48, 12.00, None, None, "veto (book unchanged)", "ok", 1, C),
    ("2026-08-12", "VELO", "09:06:00", None, None, 0.29, None, None, "would pass -- rank2", "ok", 0, C),
    ("2026-08-12", "DFTX", "09:06:00", None, None, 0.27, 39727, "ask_to_cap", "everything passes but coil", "ok", 0, C),
    ("2026-08-12", "SMWB", "09:11:00", None, None, 12.00, None, None, "veto (book unchanged)", "ok", 1, C),
    ("2026-08-12", "VELO", "09:11:00", None, None, 1.18, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "DFTX", "09:11:00", None, None, 0.48, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "AXTI", "09:11:00", None, None, 0.37, None, None, "bench", "ok", 0, C),
    ("2026-08-12", "BE",   "09:21:00", 233.68, 234.00, 0.137, 1172, "ask_to_cap", "ARMED stop-buy 235.34", "ok", 0, E),
    ("2026-08-12", "BE",   "09:24:24", 234.00, 235.00, 0.427, None, None, "re-armed 235.37 re-quote", "ok", 0, E),

    # ---- Day 8, 2026-08-13 (ledger: 2026-08-13.json veto_ledger) ----
    ("2026-08-13", "HLIT", "06:43:00", 14.80, 15.30, 3.32, 169, "ask_to_cap", "veto SPREAD (B arming)", "ok", 0, E),
    ("2026-08-13", "AZ",   "09:52:00", 7.61, 7.68, 0.92, None, None, "veto SPREAD (post-open)", "ok", 0, E),
    ("2026-08-13", "ANGX", "10:38:00", 4.17, 4.18, 0.24, None, None, "spread PASS; CHASE veto", "ok", 0, E),

    # ---- Day 9, 2026-08-14 (ledger: 2026-08-14.{json,md}) ----
    ("2026-08-14", "RDDT", "07:20:00", None, None, 0.327, 2062, "ask_to_cap", "ARMED stop-buy 178.90", "ok", 0, E),
    ("2026-08-14", "BRUN", "08:15:00", 25.50, 26.30, 3.14, None, None, "veto SPREAD (B arming)", "ok", 0, E),
    ("2026-08-14", "RDDT", "08:15:00", 175.22, 175.25, 0.017, None, None, "armed name quoting clean", "ok", 0, E),
    ("2026-08-14", "LPTH", "09:01:00", 14.37, 14.49, 0.835, None, None, "veto SPREAD (B arming)", "ok", 0, E),
    ("2026-08-14", "LPTH", "09:05:00", None, None, 0.485, 200, "ask_to_cap", "spread PASS; DEPTH veto (2.8% air pocket)", "ok", 0, E),
    ("2026-08-14", "RDDT", "09:32:43", 178.36, 178.90, 0.303, 308, "ask_to_cap", "PASS + FILLED", "ok", 0, E),

    # ---- Day 10, 2026-08-17 (ledger: 2026-08-17.{json,md}) ----
    ("2026-08-17", "NNNN", "07:04:00", 10.00, 11.00, 9.50, 100, "ask_inside", "CHASE veto; post-sweep book", "ok", 0, E),
    ("2026-08-17", "NNNN", "07:05:00", 10.00, 10.45, 4.40, 7, "ask_inside", "veto SPREAD (B arming); bid 20sh", "ok", 0, E),
    ("2026-08-17", "NNNN", "07:07:00", 10.00, 11.00, 9.50, 0, "ask_to_cap", "veto SPREAD (ratchet arming)", "ok", 1, E),
    ("2026-08-17", "NNNN", "07:34:00", 9.80, 11.00, 11.50, 0, "ask_to_cap", "veto SPREAD (ratchet arming)", "ok", 0, E),
    ("2026-08-17", "HIVE", "07:40:00", None, None, 0.34, 5461, "ask_to_cap", "ARMED stop-buy 2.98 (full ticket)", "ok", 0, E),
    ("2026-08-17", "HIVE", "07:41:00", 2.95, 2.97, 0.68, 1, "bid_inside", "veto SPREAD (Trigger C)", "ok", 0, E),
    ("2026-08-17", "HIVE", "07:44:00", 2.93, 2.95, 0.68, 65, "bid_inside", "veto SPREAD (Trigger C)", "ok", 0, E),
    ("2026-08-17", "HIVE", "07:47:00", None, None, 0.99, None, None, "veto SPREAD (Trigger C); requote 1.32", "ok", 0, E),

    # ---- Day 11, 2026-08-19 (ledger: 2026-08-19.{json,md}) ----
    ("2026-08-19", "BNTX", "08:08:00", 108.50, 109.20, 0.64, None, None, "context book (halal FAIL)", "ok", 0, E),
    ("2026-08-19", "MRVI", "08:08:00", 5.80, 7.08, 22.10, None, None, "context book, massively wide", "ok", 0, E),
    ("2026-08-19", "YXT",  "08:08:00", 2.96, 3.20, 7.80, None, None, "context book", "ok", 0, E),
    ("2026-08-19", "MRVI", "08:12:00", 5.80, 7.08, 22.10, None, None, "veto SPREAD (B arming, same book)", "ok", 1, E),
    ("2026-08-19", "MRVI", "08:15:00", None, None, 7.70, None, None, "watcher: compressing", "ok", 0, E),
    ("2026-08-19", "MRVI", "08:20:00", None, None, 3.50, None, None, "watcher: compressing", "ok", 0, E),
    ("2026-08-19", "MRVI", "08:21:54", 7.08, 7.24, 2.23, 1, "ask_inside", "veto SPREAD (Trigger C); bid 100sh", "ok", 0, E),
    ("2026-08-19", "MRVI", "08:25:00", 7.04, 7.10, 0.849, None, None, "compressing toward cap", "ok", 0, E),
    ("2026-08-19", "MRVI", "08:29:00", 7.04, 7.14, 1.41, 135, "ask_to_cap", "veto SPREAD (Trigger C)", "ok", 0, E),
    ("2026-08-19", "MRVI", "08:39:00", 7.19, 7.25, 0.83, None, None, "CHASE veto; marketable-limit spread fail", "ok", 0, E),
    ("2026-08-19", "MRVL", "08:40:00", 241.22, 241.84, 0.257, None, None, "first name inside cap today", "ok", 0, C),
    ("2026-08-19", "MRVI", "08:48:00", None, None, 1.25, None, None, "book widened back", "ok", 0, E),
    ("2026-08-19", "MRVL", "08:48:00", None, None, 0.08, None, None, "tightened", "ok", 0, E),
    ("2026-08-19", "MRVL", "08:50:00", 238.52, 239.00, 0.20, 4600, "ask_to_cap", "ARMED stop-buy 245.12", "ok", 0, E),
    ("2026-08-19", "MRVL", "08:54:02", 240.00, 240.63, 0.26, 2167, "ask_to_cap", "STALE-rule refusal; book itself fine", "ok", 0, E),
    ("2026-08-19", "MRVL", "15:01:00", 233.67, 233.77, None, None, None, "exit +60s quote", "ok", 0, E),

    # ---- Day 12, 2026-08-20 (ledger: 2026-08-20.{json,md}) ----
    ("2026-08-20", "RARE", "07:05:00", 28.19, 28.76, 2.02, 3216, "ask_inside", "veto SPREAD (B arming); bid 10sh", "ok", 0, E),
    ("2026-08-20", "RARE", "07:06:31", 28.50, 28.76, 0.91, 3216, "ask_inside", "veto SPREAD (Trigger C); bid 5sh", "ok", 0, E),
    ("2026-08-20", "RARE", "07:14:11", 28.47, 28.60, 0.457, 1345, "ask_inside", "PASS + ENTERED 524sh; bid 500sh", "ok", 0, E),
    ("2026-08-20", "TAOX", "09:49:00", 3.63, 3.79, 4.42, None, None, "veto SPREAD (post-open, B arming)", "ok", 0, E),
    ("2026-08-20", "TAOX", "10:37:00", 3.59, 3.74, 4.18, 200, "ask_to_cap", "veto SPREAD (post-open, Trigger C)", "ok", 0, E),
    ("2026-08-20", "MRVI", "11:04:00", 8.10, 8.11, 0.123, 12600, "ask_to_cap", "ARMED stop-buy 8.1789; bid 590/ask 1100", "ok", 0, E),
    ("2026-08-20", "MRVI", "11:13:27", 8.14, 8.15, 0.123, 701, "ask_to_cap", "PASS + ENTERED (depth-reduced 1833->701)", "ok", 0, E),

    # ---- Day 13, 2026-08-21 (ledger: 2026-08-21.{json,md}) ----
    ("2026-08-21", "ASST", "07:03:54", 17.72, 17.94, 1.23, 17, "ask_inside", "VETO #1 (B arming); bid 35sh; 39.5k to trig+0.5%", "ok", 0, E),
    ("2026-08-21", "ASST", "07:11:00", 17.70, 17.80, 0.56, 300, "ask_inside", "book trend read; bid 101sh", "ok", 0, E),
    ("2026-08-21", "ASST", "07:15:00", 17.70, 17.80, 0.56, 300, "ask_inside", "book read; bid 100sh", "ok", 1, E),
    ("2026-08-21", "ASST", "07:24:29", 17.50, 17.70, 1.13, 1000, "ask_inside", "VETO #2 (Trigger C); bid 100sh; 2000 to close+0.5%", "ok", 0, E),
    ("2026-08-21", "ASST", "07:29:12", 17.50, 17.77, 1.52, 1000, "ask_inside", "VETO #3 (Trigger C); bid 480sh", "ok", 0, E),
    ("2026-08-21", "ASST", "07:29:33", 17.50, 17.70, 1.13, None, None, "veto stands (re-quote, same fire)", "ok", 1, E),
    ("2026-08-21", "ASST", "07:40:10", 17.30, 17.58, 1.59, 10, "ask_inside", "VETO #4 (Trigger C); bid 500sh; 0 in cap", "ok", 0, E),
    ("2026-08-21", "ASST", "07:46:15", 17.38, 17.56, 1.03, 10, "ask_inside", "VETO #5 (Trigger C); bid 1sh", "ok", 0, E),
    ("2026-08-21", "ASST", "08:31:28", 17.31, 17.43, 0.69, 8, "ask_inside", "VETO #6 (Trigger C); bid 1000sh", "ok", 0, E),
    ("2026-08-21", "ASST", "08:37:38", 17.20, 17.43, 1.32, 6, "ask_inside", "VETO #7 (Trigger C); bid 5sh", "ok", 0, E),
    ("2026-08-21", "ASST", "08:41:32", 17.20, 17.56, 2.05, 1, "ask_inside", "VETO #8 (Trigger C); bid 5sh", "ok", 0, E),
    ("2026-08-21", "ASST", "08:45:31", 17.50, 17.68, 1.02, 350, "ask_inside", "VETO #9 (Trigger C); bid 100sh", "ok", 0, E),
    ("2026-08-21", "ASST", "08:57:24", 17.50, 17.55, 0.28, 460, "ask_inside", "PASS + ENTERED (depth-reduced 854->460)", "ok", 0, E),
]

LEDGER = {d: f"data/paper_days/{d}.md" for d in
          ["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13",
           "2026-08-14", "2026-08-17", "2026-08-19", "2026-08-20",
           "2026-08-21"]}


def canonical_spread(bid, ask):
    """Mid-denominated percent spread -- the single convention of the
    truth file (ledgers mixed bid/ask/mid denominators)."""
    if bid is None or ask is None or bid <= 0 or ask <= 0:
        return None
    mid = 0.5 * (bid + ask)
    return 100.0 * (ask - bid) / mid


def bars_source(sym, date):
    rh = os.path.join(DATA, "rh_bars", f"{sym}_{date}.csv")
    if os.path.exists(rh):
        return f"data/rh_bars/{sym}_{date}.csv"
    m1 = os.path.join(DATA, "massive", "m1", f"{sym}_{date}.csv")
    if os.path.exists(m1):
        return f"data/massive/m1/{sym}_{date}.csv"
    return None


def build():
    rows, problems = [], []
    for (date, sym, t, bid, ask, logged, dsh, dkind, ctx, q, rq,
         prec) in OBS:
        canon = canonical_spread(bid, ask)
        # VALIDATE transcription: canonical vs ledger percent. The
        # ledgers' own denominators differ (bid vs ask vs mid), so the
        # tolerance is 15% relative or 0.08pp absolute -- outside that
        # is a typo, and the build refuses to write it.
        if canon is not None and logged is not None:
            if abs(canon - logged) > max(0.15 * logged, 0.08):
                problems.append((date, sym, t, bid, ask, logged, canon))
        spread = canon if canon is not None else logged
        hh = int(t[:2])
        mm = int(t[3:5])
        phase = "premarket" if (hh, mm) < (9, 30) else "postopen"
        rows.append({
            "date": date, "symbol": sym, "time_et": t, "phase": phase,
            "bid": bid, "ask": ask,
            "spread_pct": None if spread is None else round(spread, 4),
            "spread_pct_logged": logged,
            "depth_shares": dsh, "depth_kind": dkind,
            "context": ctx, "quality": q, "requote": rq,
            "time_precision": prec,
            "bars_source": bars_source(sym, date),
            "source_ledger": LEDGER[date],
        })
    if problems:
        for p in problems:
            print("TRANSCRIPTION MISMATCH:", p)
        raise SystemExit(f"{len(problems)} rows failed validation -- "
                         f"fix the table, nothing written")
    return rows


def main():
    rows = build()
    n = len(rows)
    prim = [r for r in rows if not r["requote"]]
    with_bars = [r for r in prim if r["bars_source"]]
    spread_rows = [r for r in with_bars if r["spread_pct"] is not None]
    depth_rows = [r for r in prim if r["depth_shares"] is not None]
    days = sorted({r["date"] for r in rows})
    clusters = sorted({(r["date"], r["symbol"]) for r in rows})
    meta = {
        "generated_by": "plan/extract_liquidity_truth.py",
        "spread_convention":
            "spread_pct = 100*(ask-bid)/mid when bid/ask were logged; "
            "else the ledger's own percent (denominator varies by day "
            "-- treat as ordinal, which is all Spearman needs)",
        "phase_rule": "premarket < 09:30 ET <= postopen",
        "counts": {
            "observations_total": n,
            "requotes": n - len(prim),
            "primary": len(prim),
            "primary_with_bars": len(with_bars),
            "primary_spread_with_bars": len(spread_rows),
            "primary_with_depth": len(depth_rows),
            "days": len(days),
            "symbol_day_clusters": len(clusters),
            "by_phase_primary": {
                "premarket": sum(1 for r in prim
                                 if r["phase"] == "premarket"),
                "postopen": sum(1 for r in prim
                                if r["phase"] == "postopen"),
            },
        },
        "no_bars_note":
            "rows with bars_source=null (ALOY/NNNN 2026-08-10, "
            "percent-only rows are unaffected) await a Massive m1 "
            "backfill; they are archived, not calibratable yet",
    }
    out = {"meta": meta, "observations": rows}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {OUT}")
    print(json.dumps(meta["counts"], indent=1))


if __name__ == "__main__":
    main()
