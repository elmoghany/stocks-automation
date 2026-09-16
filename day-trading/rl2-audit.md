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

### 2.1 The environment, shared by every approach and every control

`plan/rl2/sim.py` is the only simulator in this study. A policy is just a
score matrix `sc[T, S]` (higher = more want to buy, `-inf` = never); the
bandit, the rule search, the RL agents, the random controls and the foresight
control all produce one and all run through the same `run_day`. The only thing
that differs between a reported row and its control is the score.

| | |
|---|---|
| episode | one trading day, no overnight carry |
| decision grid | every **5 minutes** on the 04:00–19:55 ET grid — **192 steps/day** (v1 could not act before 09:30 because the gapper onset gate forbade it; here premarket is legal) |
| fills | a decision at minute *m* fills at the **OPEN of minute m+1**. If m+1 did not print, the order does not happen — and that fact is not knowable at decision time, so availability is read off bar *m* (`printed`), never m+1 |
| costs | **10 bps per side**, **+50 bps** on any fill outside 09:30–16:00 |
| size cap | a fill may not exceed **20% of the symbol's volume over the trailing 5 minutes**; a capped order is sized down and dropped below \$500 notional (and then does not consume a ticket) |
| tickets | flat **\$15,000** x 6 then **\$10,000** — <= 7 concurrent, <= \$100,000/day, one open ticket per symbol, **long only**, no options/margin/shorting |
| forced flatten | every open ticket closes at the day's **last printed bar** for that symbol, at that bar's close, paying the cost ladder |
| reward (RL) | change in mark-to-market equity in \$1,000s, so cost is in the learner's signal at **every** step |

### 2.2 Features (26) and targets — `plan/rl2/features.py`

Every feature at step *t* (minute *m*) is a function of bars with grid index
**<= m** and grouped-daily rows with date **< D**:

`gap_vs_prevclose, ret_since_open, dist_vwap_day, dist_vwap30, ret5, ret15,
ret30, ret60, rvol_profile, log_dv5, dv_burst, rvol30, bar_range5,
print_density30, print_density5, amihud30, tod, min_to_1600, is_ext,
log_price, prev_day_ret, log_mdv20, dist_hi, dist_lo, xs_breadth,
xs_rank_ret30`

`amihud30` and the print-density pair are the vectorized forms of
`plan/liquidity_estimators.amihud` and `no_trade_share` (the module is
pandas-per-call and is used as the formula reference, not in the inner loop).
`rvol_profile` compares the day's cumulative volume to the name's own prior-20
grouped-daily median volume scaled by an **intraday volume profile fitted on
train dates only** (< 2025-08-01, 8,756 symbol-days) and frozen — a test day's
own shape never informs its own feature.

**Target** `tgt[t, s, h]` is the net return per \$1 of *buy at the open of
minute m+1, sell at the open of the first printed minute at or after m+1+H, or
at the forced-flatten price if that would fall past the day's last print*, both
legs paying the cost ladder. Horizons: 15, 30, 60, 120 minutes and hold-to-flatten.
It is **exactly the trade the simulator executes** for a fixed-horizon exit, so
the model's label and the simulator's P&L cannot disagree. It is written to a
separate array and never enters the feature block.

### 2.3 Splits

| use | dates | days |
|---|---|---|
| bandit / rule search training | everything **strictly before** the fold | grows 193 → 448 |
| **walk-forward test (approaches 1, 4-wf)** | 2025-08-01 → 2026-08-06, one month at a time, train = all dates < that month | **255** |
| **held-out final year (approach 4)** | search sees 2024-10-22 → 2025-07-31 (193 days) only; the single best rule is run **once** over 2025-08-01 → 2026-08-06 | 255 |
| RL train / val / test (approaches 2, 3) | < 2025-06-01 / 2025-06-01…2025-07-31 / 2025-08-01…2026-08-06 | 152 / 41 / 255 |

### 2.4 The adversarial battery — `plan/rl2/honesty.py`

| check | what it does | result |
|---|---|---|
| **poison** | replace every bar strictly after minute *m* with garbage and recompute the whole feature block; `F`, `mark`, `printed` and `volcap` at every decision step <= *m* must be bit-identical. 16 days x 4 cut points | **64 checks, 0 mismatches** |
| **hold-is-zero** | a never-buy score matrix returns exactly \$0 and 0 tickets | **passes** |
| **cost monotonicity** | one fixed policy at 0x / 1x / 10x cost | **-514 > -52,175 > -517,121** |
| **shuffled target** | the label permuted across (name, t) rows **within each day**, so per-row sums are *not* preserved. v1's control permuted the price path, which pins the day's terminal price and makes the panel a Brownian bridge worth hundreds of dollars a ticket; this one destroys only the association between a row's features and its own outcome | see 3.2 |
| **foresight** | score = the trade's own realized net return | **+\$153/ticket, Sharpe 21** |
| **random x30** | uniform scores, same eligibility / fills / costs / exit rule, at several entry rates | **-\$128/ticket** at 7 tkt/day |

**One control was mis-specified and the failure is recorded, not hidden.**
Run without a buy threshold, the foresight policy spends all seven tickets in
the first premarket minute — where the best available 30-minute net return is
still negative after a 120 bps extended round trip — and **loses \$85/ticket
with perfect foresight**. That measures the policy *shape*, not the harness.
Under the same shape approach 1 uses (buy only where the predicted net return
is positive, at most 2 per decision) the identical code earns **+\$153/ticket
at Sharpe 21**. Both rows are in `plan/rl2/out/honesty.json`.

That failure has a second consequence, and it is the most important
methodological point in this document. **The v1-style "RANDOM" baseline is a
straw man on this universe.** A random policy that fills its tickets greedily
spends them at 04:00, pays 120 bps, and loses \$114/ticket — it is beaten by
*any* policy that has learned what a clock is. `plan/rl2/baselines.py`
therefore reports four random controls, 30 seeds each, on the full 255-day test
window, and every approach below is judged against the last one:

| baseline (30 seeds) | \$/ticket | sd | range | total \$ | tkt/day |
|---|---|---|---|---|---|
| HOLD | **0.00** | – | – | **0** | 0.00 |
| RANDOM-ANY (greedy, whole grid — v1's "random") | -113.94 | 2.15 | -118.35 … -108.84 | -203,374 | 7.00 |
| RANDOM-SPREAD (whole grid, spread over the day) | -46.50 | 6.91 | -64.09 … -33.52 | -82,961 | 7.00 |
| RANDOM-RTH (09:30–16:00 only, spread) | -28.85 | 6.95 | -46.64 … -16.55 | -51,497 | 7.00 |
| **RANDOM-RTH-greedy** (7 random names at 09:30, hold 30 min) | **-24.44** | 7.42 | -38.60 … -8.57 | **-43,620** | 7.00 |

Anything that does not beat **-\$24.44/ticket** has learned nothing that a
coin flip plus "trade in the regular session" does not already know.

---

## Part 3 — Results

All dollars are on a \$100k/day ticket budget. The walk-forward test window is
**255 trading days, 2025-08-01 → 2026-08-06**, and the held-out year for the
rule search is the same 255 days, touched once.

### 3.1 The universe with no policy at all (`plan/rl2/profile_universe.py`)

One ticket at every tradeable (name, decision minute), held H minutes, same
costs and size cap. \$ per \$15,000 ticket, shown as all / RTH / EXT:

| hold | train | val | test |
|---|---|---|---|
| 15 min | -45.01 / **-33.53** / -174.49 | -43.84 / -33.13 / -169.56 | -44.90 / **-33.22** / -172.63 |
| 30 min | -47.84 / -36.71 / -173.40 | -45.64 / -35.77 / -161.61 | -47.10 / -36.01 / -168.30 |
| 60 min | -52.47 / -42.11 / -169.25 | -49.06 / -40.75 / -146.60 | -50.97 / -40.92 / -160.84 |
| 120 min | -61.53 / -52.53 / -163.04 | -56.58 / -51.10 / -120.96 | -57.02 / -48.32 / -152.13 |
| to flatten | -108.45 / -98.58 / -219.85 | -93.45 / -89.71 / -137.38 | -82.40 / -75.97 / -152.80 |

n = 379,300 / 120,531 / 1,066,702 entries. Two things to take from this table,
and they point in opposite directions:

1. **A 20 bps round trip on \$15,000 is \$30, and the regular-session
   15-minute figure is -\$33.22.** So on this universe the *market* part of the
   unconditional expectancy is about **-\$3 per ticket** — essentially flat.
   That is a materially healthier starting point than v1's gapper pool, where
   the same measurement was -\$38.56 at 5 minutes and got steadily worse with
   the horizon because the names were fading after their onset. Here there is
   almost no adverse drift to fight; there is only the toll.
2. **The toll is the whole problem.** Extended-hours entries lose \$150–\$175
   per ticket at every horizon, five times the regular-session figure, because
   60 bps a side twice is 120 bps of a \$15,000 ticket = \$180. Any policy that
   is allowed to trade premarket and after-hours will spend most of its
   learning capacity discovering that it should not.

A long-only policy on this universe needs roughly **+\$33/ticket of selection
alpha** to break even, and about **+\$24/ticket** to beat a coin flip that
knows the session times.

### 3.2 Approach 1 — contextual bandit (LightGBM), walk-forward monthly

`plan/rl2/bandit.py`. Train on every row before the test month, predict the
month, never look at it again. 13 folds, 255 test days, 1.93M rows.

| variant | \$/ticket | total \$ | tkt/day | Sharpe | max DD |
|---|---|---|---|---|---|
| **foresight** (label = the trade's own realized net return) | **+150.70** | **+268,994** | 7.00 | 16.84 | -1,700 |
| real, h=15 | -28.66 | -51,135 | 7.00 | -2.17 | -55,275 |
| **real, h=30, 5 seeds** | **-26.28 … -46.35** (mean **-36.04**) | -46,884 … -82,687 | 7.00 | -1.64 … -2.87 | up to -82,697 |
| real, h=60 | -60.10 | -107,275 | 7.00 | -3.22 | -109,465 |
| real, h=120 | -84.40 | -150,651 | 7.00 | -4.56 | -155,163 |
| real, hold to flatten | -52.18 | -93,143 | 7.00 | -1.69 | -114,413 |
| real, h=30, buy only if predicted > 50 bps | -11.80 | -14,405 | 4.79 | -0.60 | -31,704 |
| real, h=30, buy only if predicted > 100 bps | **-1.90** | -942 | 1.95 | -0.06 | -15,082 |
| real, h=30, threshold = train-quantile 0.99 | -18.29 | -28,912 | 6.20 | -1.09 | -41,139 |
| real, h=30, threshold = train-quantile 0.995 | -12.15 | -13,928 | 4.49 | -0.58 | -30,335 |
| real, h=30, threshold = train-quantile 0.999, 3 seeds | -32.53 / -41.12 / -76.14 | -7,353 / -8,595 / -15,379 | ~0.8 | -0.64 … -1.21 | -13,736 |
| **shuffled target, h=30, 3 seeds** | **-41.61 / -80.35 / -93.13** | -18,310 / -42,425 / -39,209 | 1.65 … 2.07 | -1.79 … -5.22 | -43,902 |

**The decisive comparison.** The mean real h=30 row is **-\$36.04/ticket**
against **-\$24.44/ticket** for RANDOM-RTH-greedy: the bandit is **1.56
standard deviations BELOW** the random control, and its best seed (-\$26.28) is
still below the random mean. It beats RANDOM-ANY by \$78/ticket, but so does
the one-line rule "do not trade before 09:30".

The two threshold rows that look near-breakeven (-\$1.90 at a 100 bps
predicted-return floor, -\$12.15 at the 0.995 train quantile) are **five
thresholds tried on the same 255 test days**; the -\$1.90 row is the best of
them and it is not reproducible — the same threshold family at the 0.999
quantile gives -\$32.53 / -\$41.12 / -\$76.14 across three seeds. They are
recorded, not believed.

**What the model actually learned.** Top features by gain in the last fold:
`is_ext` (51.7), `tod` (38.0), `min_to_1600` (20.3), `prev_day_ret` (17.4),
`rvol_profile` (13.7), `xs_breadth` (13.7), `log_mdv20` (13.6), `log_price`
(13.4). The three largest are all **clock** features. The model's dominant
discovery is *avoid the 50 bps extended haircut* — cost avoidance, not alpha.
That is the same finding as v1, reached on a completely different universe.

**The shuffled-target control behaves.** Trained on labels permuted across
(name, t) rows within each day, the policy makes 1.65–2.07 tickets/day and
loses \$41.61–\$93.13 per ticket — far worse than the real model, and worse
than every random control except RANDOM-ANY. No leakage signal.

**Per test month (real, h=30, seed 0):**

| month | tickets | total \$ | \$/tkt | Sharpe |
|---|---|---|---|---|
| 2025-08 | 147 | -1,510 | -10.27 | -0.75 |
| 2025-09 | 147 | -6,810 | -46.33 | -3.57 |
| 2025-10 | 161 | -2,061 | -12.80 | -0.65 |
| 2025-11 | 133 | -6,577 | -49.45 | -2.91 |
| 2025-12 | 150 | -10,062 | -67.08 | -5.23 |
| 2026-01 | 140 | -13,340 | -95.29 | -10.45 |
| 2026-02 | 133 | -1,154 | -8.68 | -0.51 |
| 2026-03 | 154 | **+4,992** | **+32.42** | 1.97 |
| 2026-04 | 147 | -10,203 | -69.41 | -4.16 |
| 2026-05 | 140 | -1,652 | -11.80 | -0.48 |
| 2026-06 | 147 | -2,992 | -20.35 | -1.18 |
| 2026-07 | 154 | -11,703 | -76.00 | -3.67 |
| 2026-08 (4 days) | 28 | **+5,104** | +182.27 | 10.46 |

2 of 13 months positive, one of which is a 4-day stub.

### 3.3 Approach 4 — rule discovery by search

`plan/rl2/rules.py`. Random + elitist-mutation search over
`entry conjunction (1–3 feature thresholds) x entry window x exit rule`, 900
candidates x 3 generations, thresholds drawn from **train-row quantiles**,
screened on 90 train days with the top 40 re-scored on all 193. The single
best-on-train rule is then run **once** on the held-out year. Five independent
seeds:

| seed | best-on-train \$/tkt | **held-out \$/tkt** | held-out total | tkt/day | Sharpe | percentile in the unsearched null |
|---|---|---|---|---|---|---|
| **0** | +39.38 | **+14.11** | **+4,305** | 1.20 | 0.39 | **99.93** |
| 1 | +29.18 | -12.19 | -9,352 | 3.01 | -0.63 | 97.83 |
| 2 | +12.47 | -12.71 | -10,552 | 3.25 | -0.86 | 97.45 |
| 3 | +13.58 | -7.34 | -7,747 | 4.14 | -1.14 | 99.03 |
| 4 | +17.36 | -46.28 | -27,813 | 2.36 | -2.26 | 52.28 |
| | | **mean -12.88** | | | | |

Seed 0's rule, in full:

> **buy** when `dist_vwap_day < -0.00006` (price below the session VWAP)
> **and** `xs_breadth < -0.0238` (the day's own universe is down on average)
> **and** `log_price < 2.7537` (price below about \$15.70),
> **entries 09:30–16:00 only**, **exit** on a +5% take-profit, a 3% trailing
> stop, or 240 minutes, whichever comes first.

That is a **mean-reversion entry with TA exits** — the same shape the project's
own research line had already nominated as the next thing to try
(`MEMORY.md`, "honest baseline + research line", 2026-09-02).

**The null distribution (`plan/rl2/rules_null.py`).** 1,500 rules drawn from
the same generator with the same train quantiles, **not searched**, evaluated
directly on the held-out year (1,335 cleared the 60-ticket floor):

| | \$/ticket |
|---|---|
| mean | **-59.12** |
| sd | 36.68 |
| median | -48.67 |
| p90 / p95 / p99 | -21.31 / -15.83 / -7.98 |
| max of 1,335 | **+22.71** |
| fraction positive | **0.37%** |

Two readings, and both belong in the record:

* **The search transfers something real.** The five searched rules average
  -\$12.88/ticket out of sample against -\$59.12 for an unsearched rule of the
  same shape, and four of the five sit above the 97th percentile of the null.
  Selecting on train is worth roughly **+\$46/ticket** out of sample. That is
  the only place in this study where training selection demonstrably survives
  the walk to a held-out year.
* **It is not worth enough.** +\$46/ticket of transfer applied to a -\$59
  starting point lands at -\$13, still below HOLD and below RANDOM-RTH-greedy.
  One seed of five crossed zero.

**Matched-random control.** Random entries at the searched rules' ticket
*rate* (`--mode matched`, 30 seeds, 180-minute holds) give -\$40.51/ticket at
0.13 tkt/day and -\$78.32/ticket at 0.54 tkt/day. Seed 0's rule is far above
those, which is why it is recorded as the closest miss rather than dismissed.
