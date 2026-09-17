# RL-SERIES v2 (2026-09-16) — RL without the +10% gapper rule: a causal wide intraday universe, four discovery methods, and what they found

**Status: COMPLETE. VERDICT: nothing reaches the $7,500/month bar. Nothing
beats HOLD. Nothing beats a coin flip that knows the market hours.**

> Walk-forward test, $ per month NET of costs on a $100k/day ticket budget:
> **FORESIGHT +22,152** (positive control, handed the future) |
> rule-search seed 0 **+355** (1 of 5 seeds; the other four −638 … −2,290) |
> **HOLD 0** | bandit2 feat2 RTH −1,434 | RANDOM-RTH-greedy −3,592 |
> bandit −4,774 | offline CQL −8,705 | PPO −9,078 | MaskablePPO −16,230 |
> RANDOM-ANY −16,748.
> The bar is **34% of what perfect 30-minute foresight earns here**.

Sources: `plan/rl2/results/*.json`, `plan/rl2/out/honesty.json`,
`plan/rl2/out/profile_universe.json`, `plan/rl2/out/bar_table.md`,
`plan/rl2/out/report.md`, `data/massive/MANIFEST_m1w.json`.

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

### 3.4 Approach 3 — online RL (PPO / MaskablePPO): reported as UNINFORMATIVE

`plan/rl2/rlenv.py`, `plan/rl2/train.py`. Same ticket rules, same cost ladder,
same fills; 20 liquidity-ranked slots, `Discrete(28)`, 192 steps/day,
250,000 steps per seed, train 152 days / val 41 / test 255.

| policy | seeds | test \$/ticket | test total | \$/month | tkt/day | invalid actions |
|---|---|---|---|---|---|---|
| MaskablePPO, real | 5 | -66.14 … -110.41 (mean **-90.12**) | -118,058 … -197,077 | -9,722 … -16,230 | 7.00 | 0 |
| PPO, real | 3 | -61.76 / -61.82 / -75.89 | -110,236 … -135,468 | -9,078 … -11,156 | 7.00 | ~43,600 |
| **MaskablePPO, leak30 (30-min foresight IN THE OBSERVATION), 250k** | 1 | **-88.40** | -157,795 | -12,995 | 7.00 | 0 |
| **MaskablePPO, leak30, 800k steps (3.2x)** | 1 | **-85.73** | -153,034 | -12,603 | 7.00 | 0 |

**The positive control fails, so the null from this arm means nothing.** In
v1 the same control returned +\$187/ticket at Sharpe 7 and licensed the null;
here, with 30 minutes of foresight handed to the agent in its observation, it
still loses \$86–88 per ticket at 250k **and** at 800k steps. The
approach-1 foresight control on the same data and the same simulator returns
**+\$150.70/ticket**, so the *harness* is fine — it is this *agent* that
cannot use the information.

The mechanism is visible in the 800k row: with foresight its regular-session
leg turns **positive on train (+\$14,667)** while its extended leg loses
**-\$38,264**. A deterministic-argmax policy with any preference for buying
spends all seven tickets, and on a 192-step grid that runs to 19:55 the exits
land in the 50 bps tier. The wide env made three things harder at once versus
v1 — 192 steps instead of 126, 20 slots instead of 10, a 609-dimensional
observation instead of 209, and premarket/after-hours actions that v1's onset
gate had forbidden — and 250k–800k steps on 152 training days is not enough to
learn a clock *and* a selection rule. `plan/rl2/rlenv.py` now carries an
`RL2_RTH_ONLY` switch to test exactly that hypothesis; it is the first item on
the "what to try next" list, not a result.

**No RL row here is evidence about the market.** They are reported so the
record is complete.

### 3.5 Approach 2 — offline RL

`plan/rl2/offline.py`. Behaviour data logged on TRAIN days only from a
uniform-random legal policy plus an epsilon-greedy policy driven by the
approach-1 bandit (itself trained on train rows only): **57,984 transitions,
304 episodes**. d3rlpy 2.8.1 has **no discrete IQL** (`IQLConfig` is
continuous-action only), so DiscreteCQL is the reported learner and
DiscreteBCQ was the intended stand-in.

| | train | val | **test** |
|---|---|---|---|
| DiscreteCQL, seed 0, 50k steps | +5,356 (+\$5.12/tkt) | -10,732 (-\$48.34/tkt) | **-105,703 (-\$74.02/tkt, -\$8,705/month)** |

Positive in-sample, negative on validation, badly negative on test — and it
inherits approach 3's failed positive control, because it learns in the same
environment. The remaining seeds and the BCQ arm were cancelled for CPU (see
Part 5); one seed is enough to show the shape.

### 3.6 The iteration pass — what happens when you take the clock away

The first pass said the bandit's entire signal was `is_ext` / `tod` /
`min_to_1600`. `plan/rl2/bandit2.py` removes that possibility and changes the
question from "which minute" to "which name":

* `--rth 1` drops extended-hours rows from **training** and extended-hours
  minutes from the **entry grid**;
* `--target xs` demeans the target across the names printing at the **same
  (day, minute)** — causal, since every row in a group shares its timestamp —
  so the model is a pure relative-value ranker;
* the test window is extended back to **2025-02 (19 months, 379 days)** so
  "both years positive" has an answer;
* the buy threshold is a quantile of the model's predictions on its **own
  training rows**, so no test information reaches it.

| config | \$/ticket | total \$ | **\$/month** | tkt/day | pct vs random (total / ex-best) |
|---|---|---|---|---|---|
| 26 intraday features, RTH-only, cross-sectional target | -33.97 | -73,978 | **-4,099** | 5.75 | **50.0 / 40.0** |
| **+ 11 multi-day & opening-range features (`feat2`)** | **-31.72** | -61,826 | **-3,426** | 5.14 | **86.7 / 83.3** |

The first row is the cleanest single finding in this study: **strip the clock
out and the 26 intraday features land on the 50th percentile of their own
random control — the median coin flip.** There is no cross-sectional intraday
signal in them on this universe.

The second row is the only place a learned model moved: adding causal
**multi-day position** (5/20/60-day returns, distance to the 20-day high and
low, 20-day volatility, the 5d/60d dollar-volume ratio, price vs the 20-day
average) and the **opening range** (opening gap, position inside the
09:30–10:00 range, break of its high) lifts the policy from the 50th to the
**86.7th percentile** of its matched random control. That is real and it is
not enough: the bar's percentile leg is 90, the row is still -\$31.72/ticket,
and both years are negative.

### 3.7 Every row against the bar

`plan/rl2/bar_table.py` restates every result file as \$/month net.
\$/month = total x 21 / test days, the same convention for policies and
controls.

| row | days | total \$ | **\$/month** | \$/ticket | note |
|---|---|---|---|---|---|
| **bandit foresight h=30 (POSITIVE CONTROL)** | 255 | +268,994 | **+22,152** | +150.70 | **the only row that clears the bar** |
| rules holdout seed 0 :: held-out year | 255 | +4,305 | **+355** | +14.11 | best honest row |
| HOLD | 255 | 0 | **0** | 0.00 | beats every learned policy |
| bandit real h=30, 100 bps threshold | 255 | -942 | **-78** | -1.90 | 5th threshold tried |
| rules holdout seed 3 | 255 | -7,747 | -638 | -7.34 | |
| bandit real h=30, train-q 0.995 | 255 | -13,928 | -1,147 | -12.15 | |
| **bandit2 feat2, RTH, cross-sectional** | 379 | -61,826 | **-3,426** | -31.72 | 86.7th pct |
| RANDOM-RTH-greedy (30 seeds) | 255 | -43,620 | **-3,592** | -24.44 | the honest opponent |
| bandit2 26-feature, RTH, cross-sectional | 379 | -73,978 | -4,099 | -33.97 | 50.0th pct |
| bandit real h=30 (5 seeds) | 255 | -46,884 … -82,687 | -3,861 … -6,810 | -26.28 … -46.35 | |
| offline CQL | 255 | -105,703 | -8,705 | -74.02 | |
| PPO real (3 seeds) | 255 | -110,236 … -135,468 | -9,078 … -11,156 | -61.76 … -75.89 | |
| MaskablePPO leak30 (FAILED positive control) | 255 | -153,034 | -12,603 | -85.73 | |
| MaskablePPO real (5 seeds) | 255 | -118,058 … -197,077 | -9,722 … -16,230 | -66.14 … -110.41 | |
| RANDOM-ANY (v1's "random") | 255 | -203,374 | -16,748 | -113.94 | straw man |

**How hard is the bar here?** \$7,500/month is **34% of what perfect
30-minute foresight earns on this universe** (+\$22,152/month). At the 7-ticket
cap and ~21 trading days a month, \$7,500/month is **+\$51 per \$15,000
ticket = +34 bps net per round trip**, on top of the 20 bps the round trip
already costs. Nothing in this study got within an order of magnitude of it.

### 3.8 Two late controls that changed the reading

**(a) The RTH-only diagnostic rescues most of approach 3's positive control —
but not all of it.** `RL2_RTH_ONLY=1` masks every buy and sell outside
09:30–16:00 and changes nothing else. Same seed, same 250,000 steps:

| MaskablePPO, leak30 (30-min foresight in the observation) | train | val | **test** |
|---|---|---|---|
| full 04:00–19:55 action grid | -\$17.22/tkt | -\$18.51/tkt | **-\$88.40/tkt** |
| **RTH-only action grid** | -\$16.08/tkt | -\$13.88/tkt | **-\$14.46/tkt** |

Removing the extended-hours action space is worth **\$74 of the \$88**: 6
extended fills instead of hundreds, `ext_pnl` -\$364 instead of -\$124,189. So
the hypothesis in Part 3.4 was right about the mechanism — and the arm still
has no power, because with thirty minutes of foresight it is **still losing
\$14.46/ticket**. MaskablePPO at 250k steps on 152 training days cannot exploit
information that the approach-1 bandit turns into +\$150.70/ticket. **The
online-RL rows in this document remain uninformative about the market**; what
they now measure is an agent that needs either far more steps or a much smaller
observation than 609 dimensions.

**(b) The shuffled-target control beats the real model on the
cross-sectional branch, which kills the "86.7th percentile" reading.**

| feat2, RTH-only, cross-sectional target | \$/ticket | \$/month | tkt/day | pct vs random (total / ex-best) |
|---|---|---|---|---|
| **real** | -31.72 | -3,426 | 5.14 | 86.7 / 83.3 |
| **shuffled target** | **-23.51** | -3,016 | 6.11 | **96.7 / 96.7** |

A model trained on labels permuted across (name, t) rows within each day does
**better** than the real model and sits **higher** in the random distribution.
The lesson is about the metric, not the market: **"percentile vs a matched
random control" is contaminated by the policy's ticket-rate and entry-time
profile**, which a LightGBM-threshold policy produces whatever it was trained
on. Only the shuffled control isolates information, and here it says the
cross-sectional branch has none. Part 3.6's "the multi-day features moved the
needle" therefore stands only for the raw-target branch, whose own shuffled
control is reported in the table above it.

### 3.9 The full iteration table, and why "percentile vs random" had to be retired

Nineteen months of walk-forward (2025-02 → 2026-08, 379 test days), quarterly
refit, train-quantile thresholds, `feat2` unless noted:

| config | \$/ticket | **\$/month** | tkt/day | pct vs random (total / ex-best) | 2025 | 2026 |
|---|---|---|---|---|---|---|
| RTH, **raw** target, q0.99, h=30, **seed 0** | **-14.99** | **-1,434** | 4.56 | 100.0 / 100.0 | -1,233 | -24,648 |
| RTH, raw, q0.99, h=30, seed 1 | -25.10 | -2,366 | 4.49 | 100.0 / 100.0 | -7,371 | -35,326 |
| RTH, raw, q0.995, h=15 | -22.93 | -1,884 | 3.91 | 100.0 / 100.0 | -9,950 | -24,053 |
| RTH, raw, q0.999, h=30 | -96.40 | -737 | 0.36 | 23.3 / 20.0 | -5,767 | -7,536 |
| **RTH, raw, q0.99, h=30, SHUFFLED TARGET** | **-23.66** | **-793** | 1.60 | **100.0 / 100.0** | -13,579 | -738 |
| RTH, cross-sectional, q0.99, h=30 | -31.72 | -3,426 | 5.14 | 86.7 / 83.3 | -32,147 | -29,679 |
| **RTH, cross-sectional, SHUFFLED TARGET** | **-23.51** | -3,016 | 6.11 | **96.7 / 96.7** | -29,457 | -24,967 |
| RTH, cross-sectional, 26 features only | -33.97 | -4,099 | 5.75 | 50.0 / 40.0 | -36,623 | -37,355 |
| RTH, cross-sectional, TA exit ladder | -43.66 | -4,647 | 5.07 | 86.7 / 83.3 | -42,911 | -40,960 |
| RTH, cross-sectional, q0.999, h=60 | -0.01 | -0 | **0.26** | 76.7 / 76.7 | -5,334 | +5,334 |

Read the two SHUFFLED rows against the rows above them. **Both shuffled
controls sit at or above the real model's percentile**, and on \$/month the
shuffled raw-target model is *less bad* than the real one. That settles two
things:

* **The percentile-vs-matched-random metric is not a signal test for this
  policy family.** A LightGBM-threshold policy produces a characteristic
  ticket-rate and entry-time profile whatever it was trained on, and that
  profile alone is worth 90+ percentile against a control matched only on
  rate. The bar's percentile leg is therefore necessary but nowhere near
  sufficient, and no row in this study should be credited for clearing it.
  The metric that survives is **\$/month net**, and the metric that isolates
  information is the **shuffled target**.
* **The best learned row is not distinguishable from its own shuffled
  control.** -\$14.99 vs -\$23.66 per ticket at 2.8x the ticket count is a
  difference in trading intensity, not a demonstration of skill.

The q0.999/h=60 row deserves one sentence so it is not mistaken for a result:
it is **-\$0.01/ticket on 99 tickets in 379 days** — a policy that has learned
to abstain, whose break-even is an accident of 99 draws, not an edge.

---

## Part 4 — Verdict

**Nothing reaches the bar. Nothing beats HOLD. Nothing beats a coin flip that
knows the market hours. The one row that clears \$7,500/month is the
positive control, which is handed the future.**

1. **Against the bar (>= \$7,500/month net).** The best honest row in the
   study is the approach-4 rule search, seed 0, at **+\$355/month** — 21x
   short — and it is 1 of 5 seeds whose mean is -\$12.88/ticket. Every other
   approach is negative in \$/month. The foresight control earns
   **+\$22,152/month**, so the bar is **34% of perfect 30-minute foresight**
   on this universe: it asks for **+\$51 per \$15,000 ticket**, i.e. **+34 bps
   net per round trip on top of the 20 bps the round trip costs**, sustained
   at the 7-ticket cap.

2. **The harness is honest and it has power.** Poison: **64 checks, 0
   mismatches** — every feature, mark, print mask and size cap at every
   decision step is bit-identical when every later bar is replaced with
   garbage. Hold-is-zero: exactly \$0. Cost monotonicity: -514 (0x) >
   -52,175 (1x) > -517,121 (10x). The corrected shuffled-target control is
   **negative everywhere** (-\$41.61 … -\$93.13/ticket). Foresight on the
   approach-1 policy shape returns **+\$150.70/ticket at Sharpe 16.8**.

3. **Escaping the gapper pool did not create an edge; it removed an excuse.**
   The causal wide universe has an unconditional net expectancy of about
   **-\$33/ticket at 15 minutes in the regular session**, of which \$30 is the
   round trip — so the *market* part is roughly -\$3, versus v1's gapper pool
   where post-onset fade added real losses on top of the toll. The universe is
   better. The signal is still absent.

4. **What every learned model actually learned is the clock.** The bandit's
   top features by gain are `is_ext`, `tod`, `min_to_1600`. Take that away
   (`--rth 1 --target xs`) and the 26 intraday features land on the **50th
   percentile of their own random control** — the median coin flip. Adding 11
   causal multi-day and opening-range features lifts it to the 86.7th
   percentile — **but its own shuffled-target control reaches 96.7**, so that
   lift is a property of the policy's trading profile, not of the features
   (3.9). The best learned row, -\$14.99/ticket, is not distinguishable from
   its shuffled control at -\$23.66/ticket on 2.8x fewer tickets.

5. **The online-RL arm is uninformative, not null.** Its own foresight control
   fails at 250k **and** 800k steps (-\$88.40 and -\$85.73/ticket) while the
   same control on the approach-1 policy shape earns +\$150.70. Masking the
   extended-hours action space (`RL2_RTH_ONLY=1`) recovers \$74 of the \$88 —
   confirming the mechanism — and the control is **still -\$14.46/ticket with
   thirty minutes of foresight** (3.8). Whatever those MaskablePPO / PPO rows
   are measuring, it is not the market.

6. **Rule search is the only place selection transferred.** Five independent
   searches produced rules averaging -\$12.88/ticket out of sample against
   -\$59.12 for 1,335 unsearched rules of the same shape, and four of five sit
   above the 97th percentile of that null. Training selection is worth about
   **+\$46/ticket out of sample** here. It is real, it is measurable, and it
   is not enough to cross zero.

### The closest miss

**Approach 4, seed 0** — a mean-reversion entry with TA exits:

> buy when `dist_vwap_day < -0.00006` **and** `xs_breadth < -0.0238` **and**
> `log_price < 2.7537`; entries 09:30–16:00 only; exit at +5%, a 3% trailing
> stop, or 240 minutes.

| | held-out year (255 days, touched once) |
|---|---|
| total | **+\$4,305** |
| \$/month | **+\$355** |
| \$/ticket | **+\$14.11** over 305 tickets (1.20/day) |
| Sharpe | 0.39 |
| max DD | -\$10,234 |
| percentile in the unsearched null | **99.93** |
| matched-random control at the same rate | -\$78.32/ticket |

**What it would need to reach the bar.** At +\$14.11/ticket it makes
\$355/month; the bar is \$7,500. Two ways to close a 21x gap, and neither is
available:

* **More tickets at the same edge.** \$7,500/month at +\$14.11/ticket needs
  **25 tickets/day**. The cash-account rule caps it at 7, and the rule only
  fires 1.2 times a day on a 61-name universe — widening the universe by 4x
  would be needed even to reach the cap.
* **More edge at the same rate.** At 1.2 tickets/day it would need
  **+\$297/ticket = +198 bps net per trade**, which is 2x what *perfect*
  30-minute foresight pays (+\$150.70).

The only honest reading is that this rule is 1 of 5 seeds, four of which lost,
and that its +\$355/month is inside the noise of a maximum taken over 1,800
candidate evaluations. It is recorded as the closest miss, not as a candidate.
**It should not be traded.** The only legitimate next step for it is a
pre-registered re-run on data that did not exist when this was written.

---

## Part 5 — Caveats

1. **Universe SIZE drifts up over the sample** — 44 names/day in 2024-10 to 87
   in 2026-07 — because `data/pt_halal` quarterly-statement coverage grew as
   earlier campaigns ran. Membership at D uses only information dated <= D, so
   this is not look-ahead; but *which* names have a cached statement file at
   all is uneven across time, which makes early-period results noisier than
   late-period ones. The shares half of that confound **was** fixed (Part 1.2);
   the statements half was not, because `data/pt_halal` belongs to a
   concurrently-running halal rebuild and was left alone deliberately.
2. **`industry_clean` and `sector_clean` read PRESENT-DAY labels**, and a
   symbol with no label is refused. Label coverage (728 of 4,575 liquid
   names/day) is what bounds the universe to ~61 names/day, not the ratio
   tests alone. A business-model classification barely moves, and it is
   applied identically to every policy and control, so it cannot create a
   return edge — but it does shape which names exist.
3. **Grouped-daily closes are split-ADJUSTED** to the present while the
   point-in-time share count is not, so `mcap = shares x prev_close` is wrong
   across a split. Same convention as every engine backtest in this repo;
   recorded, not silently inherited.
4. **The universe is 191 distinct symbols** over two years — halal-PASS,
   liquid, mostly mid- and large-cap. That is the frame, and it is a frame in
   which a 15-minute cross-sectional edge is exactly where one would least
   expect to find one.
5. **The online-RL arm never demonstrated power** (Part 3.4), so its five
   MaskablePPO seeds and three PPO seeds are not evidence about the market.
   The offline arm inherits the same defect.
6. **Compute was severely constrained.** The Cornell VPN was down for the
   whole session (`ssh unicorn-login-01` timed out; no Cisco adapter had an
   address), so nothing ran on the cluster, and the 4-core PC was shared with
   another agent's `wn_model` / `wn_rules` / `rotation_sim` / `vs2_test` jobs.
   The MaskablePPO-real-800k run and the offline CQL seed 1 / BCQ arms were
   cancelled to free CPU; `bandit2` gained `--block` (quarterly refit) and
   `--rounds 200` so a sweep would fit. Neither weakens the walk-forward
   discipline — a block's model still sees only rows dated before the block
   starts — but both mean the sweeps are coarser than they would be on the
   cluster.
7. **Multiple testing.** This document reports ~45 configurations. The
   \$-1.90/ticket row (approach 1 at a 100 bps threshold) is the best of five
   thresholds; the +\$355/month row is the best of five search seeds. Neither
   is corrected for that and neither should be believed.
8. **No market-impact model** beyond the 20%-of-trailing-volume cap; no
   overnight risk, by construction; the forced flatten uses each symbol's last
   printed bar, which for a name that stops printing mid-afternoon is a price
   from earlier in the day.

---

## Part 6 — Ranked list of what to try next

In descending order of expected value, given everything above:

1. **The online-RL arm still has no power; shrink it before believing any RL
   number.** `RL2_RTH_ONLY=1` was run in this session and recovered $74 of
   the $88 (3.8), so the extended-hours action space was most of the problem —
   and the foresight control is still -$14.46/ticket. What is left to try, in
   order: cut the observation from 609 dims (20 slots x 26 features) to
   something a 2-layer MLP can use on 152 training days; evaluate the
   STOCHASTIC policy instead of the deterministic argmax, which currently
   forces 7.0 tickets/day on every single row; and only then spend steps. The
   cluster is the right place for this and the VPN was down all session.
2. **Execution, not selection.** The measured cost structure says so: the
   regular-session round trip is \$30 of a \$33 unconditional loss, and
   extended-hours exits cost \$150–\$175. v1's audit made the same
   recommendation (Qlib RL on the child-order schedule) and it is still
   untried. Nothing in selection-land came close to \$51/ticket; shaving 5 bps
   a side off the toll is worth \$15/ticket and is a *much* easier problem.
3. **Widen the universe rather than deepen the model — ALREADY IN FLIGHT.**
   The binding constraint on the closest miss is that it fires 1.2 times a day
   on 61 names. The label-coverage funnel (Part 1.4) says 728 names/day carry
   a label out of 4,575 that clear the liquidity screen, so backfilling labels
   and EDGAR statements across the screen multiplies the halal universe. The
   parallel UNIVERSE-QUOTES line has already taken it from 61 to **278
   PASS names/day** and is reading this study's `data/massive/m1w` cache
   through `backfill_m1w.py --universe`. Every approach here should be re-run
   on that universe before anything else is tried, because more independent
   bets at a small edge is the only route to the bar that does not require a
   20x edge improvement.
4. **Multi-day features earned their keep; go further in that direction.**
   The only measurable lift in the whole study (50th → 86.7th percentile) came
   from adding multi-day position and the opening range. Overnight gaps,
   earnings proximity (`data/earnings_dates.json` exists), sector/peer
   relative strength and an index-relative return are all causal, cheap, and
   in the same family.
5. **The mean-reversion family, pre-registered.** The closest miss is a
   below-VWAP entry on a down-breadth day in lower-priced names with a TA exit
   ladder. It should be re-run on data that did not exist when this was
   written, with the rule fixed in advance, before any further search is done
   on it.
6. **Redesign the entry-rate control.** Every random control here had to be
   matched to a policy's ticket rate by hand. A cleaner design draws the
   control's entry times from the policy's own realized entry-time
   distribution, so the comparison isolates *which name* from *when*.

---

## Reproducing

```
python plan/rl2/universe.py --stage screen      # causal liquidity screen
python plan/rl2/backfill_shares.py              # de-campaigned PIT shares
python plan/rl2/universe.py --stage halal       # + point-in-time halal gate
python plan/rl2/backfill_m1w.py                 # 1-min bars -> data/massive/m1w
python plan/rl2/manifest.py                     # MANIFEST_m1w.json
python plan/rl2/panel.py                        # per-day minute tensors
python plan/rl2/features.py                     # 26 causal features + targets
python plan/rl2/features2.py                    # + 11 multi-day / opening-range
python plan/rl2/honesty.py                      # poison, hold-zero, cost, foresight
python plan/rl2/profile_universe.py             # unconditional expectancy
python plan/rl2/baselines.py                    # HOLD + 4 random controls x30
python plan/rl2/bandit.py  --horizon 30 --variant real --seed 0
python plan/rl2/bandit2.py --rth 1 --target xs --feat feat2 --block 3
python plan/rl2/rules.py   --mode holdout --seed 0
python plan/rl2/rules_null.py --mode draws
python plan/rl2/train.py   --algo maskppo --variant real --seed 0 --steps 250000
python plan/rl2/offline.py --algo cql --seed 0
python plan/rl2/report.py      > plan/rl2/out/report.md
python plan/rl2/bar_table.py   > plan/rl2/out/bar_table.md
```

Python: `C:\cornell\venvs\rl` (gymnasium 1.0.0, stable-baselines3 2.9.0,
sb3-contrib 2.9.0, torch 2.14 CPU, lightgbm 4.7.0, d3rlpy 2.8.1). The engine's
Python was never touched. `data/massive/m1w/` and
`data/massive/MANIFEST_m1w.json` are left in place as a reusable causal cache
for other lines.
