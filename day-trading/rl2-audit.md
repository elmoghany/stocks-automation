# RL-SERIES v2 (2026-09-16) — RL without the +10% gapper rule: a causal wide
# intraday universe, four discovery methods, and what they found

**Status: IN PROGRESS — this file is written as the runs land.**

Read `day-trading/rl-audit.md` first. v1 asked whether RL could beat the
baselines *inside the +10% gapper pool* and the answer was no, with a harness
proven honest by a 64/64 poison test and a foresight positive control. v2
throws the pool away, because pool membership is conditioned on the day's own
regular-session high (`NOTES-DAYTRADING.md`, "MX-SERIES RETRACTION #2"), and
asks the question again on a universe built only from information that is
complete before the day opens.

---

## Part 1 — The universe

### 1.1 The membership rule

On each trading date **D** a symbol is eligible iff

| # | condition | source, and why it is causal |
|---|---|---|
| a | **halal-PASS point-in-time at D** | `plan/penny_ax11b_massive.halal_pt(sym, D, prev_close)` under `HALAL_STRICT=1 PT_FILED=1`, network removed. Shares outstanding are read as-of a date **<= D**; quarterly statements are selected by FILED date **<= D**. |
| b | **median dollar volume >= \$2,000,000 and median close >= \$3.00 over the prior 60 TRADING days** | `data/massive/gd/*.json.gz`, rows with date **< D** only. At least 40 of the 60 sessions must have printed. |
| c | **printed at least one 1-minute bar on D** | `data/massive/m1w/{SYM}_{D}.csv`. |

`prev_close` is the grouped-daily close of the previous **trading** day.
Nothing about D's own outcome — not its gain, not its high, not its volume —
enters membership anywhere.

### 1.2 The confound v1 flagged, and the fix

v1's stated caveat was that `data/pt_shares` had been populated by earlier
campaigns whose rankers were later shown to be future-conditioned. Under
`shares_asof`'s nearest-earlier semantics that has a sharp consequence: a
symbol becomes **halal-evaluable at D only if some campaign had already queried
it on or before D** — and those campaigns queried the names that had just
printed a +10% gap. Left alone, the "wide halal universe" would quietly
collapse back onto *recent big movers*, i.e. the gapper pool wearing a hat.

`plan/rl2/backfill_shares.py` removes it. Shares outstanding are fetched on a
**fixed monthly anchor grid** (first calendar day of each month, 2024-08 →
2026-09) for **every symbol that survives the causal liquidity screen and
carries a sector/industry label** — 1,127 symbols x 26 anchors = **29,302
lookups, 27,759 answers, 1,483 nulls, 0 failures**, into a private cache
(`plan/rl2/cache/shares/`) so no concurrently-running halal job is disturbed.
`plan/rl2/halal2.py` reads that cache and `data/pt_shares` together and takes
the most recent as-of date strictly <= D.

Measured effect: on 2025-01-15 the number of screened, label-clean names with
a point-in-time share count went from **261 to 543**, and after the full gate
the universe on that date went from **20 names to 44**. Across the study the
shares cache now answers **652,020 of 652,078 lookups** (58 misses), 83% of
them from the new de-campaigned cache; **`shares` is no longer a binding
constraint anywhere** (screened-and-labelled = 728/day, with-shares = 728/day).

### 1.3 A second bug found on the way

`data/massive/gd/` holds a file for every **weekday**, including market
holidays, whose `results` list is empty. Using them as trading days made "the
previous trading day" empty for the 20 post-holiday sessions, so `prev_close`
was missing for every symbol and the universe came out **empty on those
dates**. `plan/rl2/universe.py::gd_dates()` now returns real trading days only,
and the 60-day lookback is 60 real sessions.

### 1.4 Coverage funnel (mean per trading day, 448 dates, 2024-10-22 → 2026-08-06)

| stage | names/day | what it cuts |
|---|---|---|
| all grouped-daily symbols | ~11,500 | — |
| **liquidity screen** (b) | **4,575** (4,020 … 5,059) | price/turnover |
| carries a sector/industry label **and** passes the haram-word + SIC-6000-6999 screens | **728** (595 … 856) | `industry_clean` + `sector_clean` |
| has a cached quarterly-statement file | 642 (534 … 751) | `data/pt_halal` coverage |
| has a point-in-time share count | **728** (595 … 856) | *no longer binding* |
| **halal-PASS (10/10/20 + TTM interest < 5%)** | **61** (30 … 91) | the ratio tests |

**27,209 symbol-days over 448 trading dates, 191 distinct symbols**, every one
of which had bars on its date (`no_bars = 0`). Membership churn is ~9 names in
and ~7 out per month.

The universe **grows** over the sample — 44 names/day in 2024-10 to 87 in
2026-07 — because `data/pt_halal` statement coverage grew as campaigns ran and
because more names cleared the ratio tests. That drift is a property of the
gate's cache, not of the market, and it is the largest remaining caveat: see
Part 5.

### 1.5 The bar cache

`data/massive/m1w/` — 1-minute bars 04:00-20:00 ET for every (symbol, date) in
the universe, written by `plan/rl2/backfill_m1w.py` in the resumable,
atomic-write, EMPTY-sentinel format of `plan/backfill_m1_full.py`, so the two
caches cannot drift.

| | |
|---|---|
| symbol-days | **27,209** |
| bytes | **0.557 GB** |
| fetched from Polygon | 25,987 |
| hard-linked from the existing `data/massive/m1` gapper cache | **1,222 (4.5%)** |
| permanent failures | **0** |
| EMPTY (no print all day) | 0 after pruning to the final universe |

**Only 4.5% of the wide universe's symbol-days already existed in the gapper
cache.** That number is the point of the exercise: the causal universe and the
+10% pool are almost disjoint.

Coverage and the membership rule are also written to
`data/massive/MANIFEST_m1w.json`.

---

## Part 2 — Methodology

*(filled in below as runs land)*
