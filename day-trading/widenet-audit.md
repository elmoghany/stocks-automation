# WIDE-NET (2026-09-16) — buy the top-30 wide, find the pattern where a
# $15,000 ticket usually wins, then backtest it buying only ONE stock

**User direction, 2026-09-16:** *"test buying with multiple $15k tickets — it is
OK to buy the top-30 per day — until you find the pattern on which a $15k
purchase usually wins; analyze the winning pattern; then backtest that pattern
buying only ONE stock. Do it with Massive data."*

**Verdict: FAIL.** No pattern reaches the standing bar of **$7,500/month net**
with one $15,000 ticket a day. The best honest single-ticket-a-day result is
**+$314/month** (24× short) on 31 tickets, and the only breadth configuration
that clears $7,000/month is carried entirely by a day-of-week condition that
does not survive ablation and is not executable under the account's
one-position-at-a-time rule.

The most useful output of the run is not a strategy but a **measurement of the
size of the gap**, in Part 7: to earn $7,500/month you need a sustained daily
cross-sectional information coefficient of **ρ ≈ 0.48** with one ticket a day,
or **ρ ≈ 0.19** with seven. Every honest ranker built here delivers **ρ ≈ 0.03**.

Read `rl2-audit.md` first — this study reuses its causal universe, its feature
block and its cost model, and inherits its conclusions about the +10% gapper
pool. Nothing in `plan/rl2/` was modified.

---

## Part 1 — What was built

### 1.1 The universe (inherited, not re-derived)

`data/massive/m1w/` + `plan/rl2/out/{universe,days,feat}` — the RL-SERIES v2
**causal wide intraday universe**. On date *D* a name is eligible iff it was
halal-PASS point-in-time at *D*, its median dollar volume over the prior **60
trading days** was ≥ $2M and its median close ≥ $3, and it printed a bar on *D*.
Nothing about *D*'s own outcome enters membership — deliberately **not** the
+10% gapper pool, whose membership is conditioned on the day's own regular-
session high (`NOTES-DAYTRADING.md`, "MX-SERIES RETRACTION #2").

**448 trading days, 2024-10-22 → 2026-08-06, 27,209 symbol-days, 191 distinct
symbols, mean 60.7 names/day** (min 30, max 91).

Robinhood `get_equity_fundamentals` on all 191 names (present-day snapshot,
see Part 9.1) describes what that universe actually is:

| | p10 | median | p90 |
|---|---|---|---|
| float | 11.7M sh | **51.0M sh** | 211.8M sh |
| market cap | $181M | **$1.53B** | $12.5B |

Sectors: Technology Services 43, Electronic Technology 36, Health Technology 34,
Producer Manufacturing 23, Commercial Services 11, the rest ≤ 7. **191/191 names
returned fundamentals and 191/191 had a non-null float.** This is a small-to-mid
cap universe, not a penny-stock universe — which matters for Part 7.

### 1.2 The ticket table — `plan/wn_table.py` → `data/massive/wn/table.npz`

One row per (date, symbol, decision time): **380,926 hypothetical $15,000
tickets**, of which **222,762 are causally eligible** (bar *m* printed).

* **14 decision times (ET)** — the five the mandate names (09:35 10:00 10:30
  11:00 13:00), four more regular-session (09:45 12:00 14:00 15:00) and five
  extended-hours (07:00 08:00 09:00 09:25 16:30) so the extended toll is
  measured rather than assumed.
* **32 causal features** — the 26 of `plan/rl2/features.py` (all functions of
  bars with grid index ≤ *m* and grouped-daily rows with date < *D*) plus six
  wide-net additions: `dow`, `sic2` (2-digit SIC, `data/sic_codes.json`),
  `coil` (= rvol30 / bar_range5), `earn_prox` and the two Robinhood earnings
  columns of Part 9.2.
* **5 exit horizons** — 15 / 30 / 60 / 120 minutes and hold-to-forced-flatten.
* **Label** = the realized **net dollar P&L** of the ticket, not a return, so
  the model optimises the thing the mandate is scored on.

**Fills and costs, identical to `plan/rl2/sim.py::run_day`:** a decision at
minute *m* fills at the **open of minute m+1**; **10 bps per side, +50 bps on
any fill outside 09:30–16:00**; notional = min($15,000, 20% of the trailing
5-minute share volume × fill price), and below $500 the order does not happen.
86% of regular-session tickets fill the full $15,000.

### 1.3 A causality bug this study introduced, and the test that caught it

The first cut of `plan/wn_lib.Table.mask` gated the candidate set on
`printed` = *minute m+1 printed*, i.e. on whether the order would turn out to
be fillable. That is future information at decision time, and it silently
removed **19.4% of printed bars** from every candidate list.

`plan/wn_poison.py` failed loudly on it — 95 of 144 array checks mismatched,
all of them on `printed` and `notional`, while `F` never mismatched once. The
gate was changed to `printed_m` (*bar m itself printed*), with a chosen name
whose m+1 did not print booking **$0** — the order did not happen and the day's
ticket is spent, exactly as `plan/rl2/sim.py` does. **Every number below was
recomputed underneath the corrected gate.** The failure is recorded in the
module docstring rather than patched away.

---

## Part 2 — The wide net itself (train window, 193 days, 2024-10-22 → 2025-07-31)

### 2.1 Unconditional expectancy — the toll is the whole problem

$ per $15,000 ticket, **out-of-sample** window, no selection at all:

| decision time | n (OOS) | h15 | h30 | h60 | h120 | to flatten |
|---|---|---|---|---|---|---|
| 07:00 | 4,658 | -46.9 | -45.6 | -47.4 | -49.9 | -36.7 |
| 08:00 | 6,248 | -61.7 | -60.7 | -66.4 | -45.6 | -57.2 |
| 09:00 | 2,574 | -94.2 | -67.6 | -59.8 | -78.2 | -95.2 |
| 09:25 | 4,064 | -63.0 | -58.2 | -58.9 | -69.4 | -77.0 |
| **09:35** | 14,368 | **-31.1** | -31.5 | -36.3 | -45.5 | -75.0 |
| 09:45 | 14,641 | -25.4 | -31.0 | -36.2 | -39.1 | -69.1 |
| 10:00 | 15,068 | -29.9 | -29.6 | -33.5 | -37.8 | -71.6 |
| 10:30 | 14,581 | -29.3 | -28.2 | -31.3 | -30.5 | -64.5 |
| 11:00 | 14,447 | -28.1 | -27.6 | -28.5 | -25.6 | -62.3 |
| 12:00 | 14,004 | -23.9 | -22.3 | -21.0 | **-13.8** | -54.7 |
| **13:00** | 13,858 | -25.1 | -20.0 | **-15.6** | -18.4 | -54.0 |
| 14:00 | 13,891 | -25.4 | -25.2 | -28.2 | -79.9 | -67.2 |
| 15:00 | 14,815 | -24.9 | -28.2 | -76.3 | -69.2 | -62.4 |
| 16:30 | 1,842 | -75.3 | -74.9 | -72.0 | -64.9 | -59.1 |

A 20 bps round trip on $15,000 is **$30**. The regular-session figures sit
between -$15 and -$31, so **the market part of the unconditional expectancy is
between zero and +$15** — there is essentially no adverse drift to fight, only
the toll. Extended-hours entries lose $37–$95 because 60 bps a side twice is
120 bps = $180 of a $15,000 ticket. **Hold-to-flatten is the worst exit at every
hour** (-$54 to -$95), because the day's last print often falls in after-hours
and pays the extended ladder on the way out.

### 2.2 The top-30 orderings — the literal instruction

Top-30 eligible names per decision time by each causal ordering, one $15,000
ticket each, train window. Best 14 of 700 rows:

| time | ordering | horizon | n | $/ticket | win | $/day |
|---|---|---|---|---|---|---|
| 10:00 | gap_asc | h60 | 5,758 | **-11.99** | 0.394 | -358 |
| 10:00 | price_asc | h60 | 5,758 | -12.62 | 0.404 | -376 |
| 10:00 | price_asc | h15 | 5,758 | -13.33 | 0.358 | -398 |
| 10:00 | price_asc | h120 | 5,758 | -13.50 | 0.411 | -403 |
| 10:00 | dollar_volume | h15 | 5,758 | -13.74 | 0.344 | -410 |
| 10:00 | gap_asc | h15 | 5,758 | -13.93 | 0.350 | -415 |
| 10:00 | vwap_above | h15 | 5,758 | -13.94 | 0.353 | -416 |
| 10:00 | liquidity_desc | h15 | 5,758 | -13.94 | 0.348 | -416 |
| 10:00 | gain_now_desc | h15 | 5,758 | -14.22 | 0.351 | -424 |
| 13:00 | rvol_desc | h60 | 5,721 | -14.61 | 0.290 | -433 |

**Not one of the 700 ordering × time × horizon combinations is positive**, and
the spread between the best and the *random* ordering at the same time and
horizon is under $5/ticket. Ordering the wide net by dollar volume, gap, coil,
gain, relative volume, VWAP distance, price or liquidity is worth approximately
nothing. The only thing that matters is **when** you trade, and it is worth
about $50/ticket (10:00 vs 09:00), all of it cost avoidance.

### 2.3 Per-feature deciles — no feature crosses the toll

Train window, all nine regular-session decision times, 30-minute hold. Best
decile of each feature, ranked:

| feature | best decile | $/ticket | n | win |
|---|---|---|---|---|
| log_dv5 | d0 (quietest) | **-5.2** | 6,195 | 0.232 |
| print_density5 | d0 | -8.7 | 4,805 | 0.181 |
| coil | d9 | -10.5 | 6,195 | 0.215 |
| bar_range5 | d0 | -11.4 | 6,195 | 0.196 |
| amihud30 | d9 | -11.5 | 6,195 | 0.294 |
| log_mdv20 | d0 | -13.6 | 6,164 | 0.265 |
| xs_breadth | d5 | -15.0 | 6,189 | 0.352 |
| rvol_profile | d0 | -15.9 | 6,195 | 0.258 |

**Zero of 31 features has a single positive decile anywhere**, at any horizon.
The largest decile spread in the whole table is $23/ticket (log_dv5), against a
$30 toll. A one-feature screen cannot work on this universe — that result is
not a modelling failure, it is an arithmetic one.

---

## Part 3 — The model (`plan/wn_model.py`)

### 3.1 The generalization diagnostic that ends the argument

LightGBM regression on the net-dollar label, 41,094 train rows, early stopping
on the last 20% of **train days**:

> **Early stopping chose 1 round. Held-out-train-day MSE 21,703 against
> 21,701 for the constant mean — R² = −0.00012.**

Walk-forward, refitting once per test month on every row before it, the chosen
round counts were **8, 38, 6, 7, 2, 6, 16, 11, 2, 2, 2, 36** across the 13
folds. A gradient-boosted tree ensemble with 31 causal features, given 165,000
training rows, cannot find one round of signal that survives to the next block
of days. The label is noise at this feature resolution.

### 3.2 TreeSHAP attribution (train, description only)

Computed with LightGBM's exact `pred_contrib=True` (the `shap` package is not
installed and is not needed). Ranked by mean |SHAP| in dollars, with the sign of
the SHAP-vs-value correlation:

| feature | mean abs SHAP ($) | direction |
|---|---|---|
| xs_breadth | 4.75 | **−** (buy when the universe is down) |
| rvol30 | 3.38 | − |
| log_dv5 | 3.29 | − (prefer the quieter tape) |
| sic2 | 3.20 | + |
| prev_day_ret | 3.09 | **−** (buy yesterday's losers) |
| dow | 3.09 | − |
| dist_vwap30 | 2.49 | **−** (buy below the 30-min VWAP) |
| ret15 | 2.45 | − |
| bar_range5 | 2.33 | − |
| gap_vs_prevclose | 2.13 | − |
| … | | |
| earn_rh / earn_fresh / is_ext | 0.00 | never split on |

Top interactions by co-split gain: `bar_range5 × xs_breadth`,
`rvol30 × prev_day_ret`, `bar_range5 × sic2`, `rvol30 × bar_range5`.

**Every large direction is mean-reverting**: down market, down yesterday, below
VWAP, quiet tape. That is the same shape `plan/rl2/rules.py` seed 0 found and
the same shape `MEMORY.md`'s research line nominated. Three independent searches
on two different harnesses agree on the *direction*; none of them makes it pay.

### 3.3 The walk-forward model, one ticket a day (the headline model row)

Model for test month *M* fitted only on rows with date < *M*; one $15,000
ticket a day at 09:35, 30-minute hold, over the **251-day held-out year**:

| | $/ticket | total | $/month | months + | maxDD | Sharpe |
|---|---|---|---|---|---|---|
| **walk-forward LightGBM** | **-3.35** | -842 | -70 | 5/12 | -7,870 | -0.11 |
| random single pick, 30 seeds | -27.66 ± 8 | — | — | — | — | — |
| inverted score | -69.32 | | | | | |
| **shuffled labels** (within train day) | **-30.06** | -7,545 | -631 | 4/12 | -7,837 | |

The model sits at the **96.7th percentile** of the random control; the inverted
score loses; the shuffled-label control lands at **-$30.06, the 36.7th
percentile — indistinguishable from random**, exactly as a clean harness
requires. Monthly: +$918, +$699, +$1,050, +$2,778, +$4,393 in five months
against -$1,201, -$1,622, -$331, -$1,835, -$177, -$3,237, -$2,278 in seven.

**This is the honest centre of the study.** The ranker does find real
selection value — about **+$24/ticket over a coin flip**, and the controls
confirm it is not leakage. It is just that the toll is $30, so a genuinely
skilled ranker lands at **-$3.35/ticket** and the year ends $842 down.

---

## Part 4 — Rule discovery (`plan/wn_rules.py`)

Beam search (width 120, depth 3) over conjunctions of `feature ≤ v` / `> v`
atoms with thresholds from **train quantiles only**, plus decision-time and
SIC atoms, maximising mean $/ticket subject to ≥ 150 train tickets, five seeds
per horizon (seed 0 = the full train window, seeds 1–4 = 70% day-level
bootstraps). A beam is the *strongest* fitter of this family, so a negative
held-out result means the family is exhausted, not under-searched.

### 4.1 Best-on-train

| horizon | seed | train $/tkt | n | rule |
|---|---|---|---|---|
| flat | 2 | +439.01 | 170 | `log_dv5>15.869 AND dist_lo>0.034585 AND dow<=0` |
| flat | 4 | +403.53 | 168 | `dist_hi<=-0.0579 AND dist_lo>0.0517 AND coil<=0.7476` |
| flat | 0 | +376.08 | 153 | `dist_hi<=-0.0579 AND dist_lo>0.0517 AND dow<=0` |
| h30 | 2 | +314.96 | 185 | `gap_vs_prevclose<=-0.0371 AND tod<=0.3594 AND xs_breadth<=-0.0051` |
| h30 | 0 | +250.77 | 154 | `prev_day_ret<=-0.0247 AND xs_breadth<=-0.0081 AND dec==09:45` |

Again a mean-reversion family: buy a name that gapped **down** ≥ 3.7%, or that
fell ≥ 2.5% yesterday, early in the session, when the universe itself is down.

### 4.2 The unsearched null — the context that matters

2,500 rules drawn from the **same generator with the same train quantiles**,
never fitted, evaluated once on the held-out year (2,206 cleared the ticket
floor), 30-minute hold:

| | $/ticket |
|---|---|
| mean | **-31.59** |
| sd | 7.29 |
| median | -31.37 |
| p90 / p95 / p99 | -25.37 / -22.09 / -15.07 |
| **max of 2,206** | **+0.04** |
| **fraction positive** | **0.0005 (1 rule)** |

One unsearched rule of this shape in 2,206 made four cents a ticket. That is
the bar any searched rule has to clear, and it also says the family has
essentially no positive mass to find.

---

## Part 5 — STEP 3: one $15,000 ticket a day, out of sample

251 days, 2025-08-01 → 2026-07-31, touched once per pattern. On each day, at
the **earliest decision time the pattern fires** (the only causal way to
collapse a time-unconstrained rule to one ticket — at 09:35 you cannot know
13:00 will score higher), buy the single best-matching eligible name by the
rule's train-standardised margin. Controls share the eligibility, fills, costs,
exit and *timing*.

| # | h | tkt | $/tkt | total | $/month | months + | maxDD | random (same slots) | pct | inverted | train $/tkt | pattern |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **15** | h60 | 31 | **+121.21** | **+3,758** | **+314** | 6/9 | -3,402 | -45.59 ± 44 | **100** | -52.85 | +152.5 | `rvol30>0.0034 AND xs_breadth<=-0.0081 AND dec==09:45` |
| 2 | flat | 36 | +35.20 | +1,267 | +106 | 6/12 | -3,468 | -31.87 ± 63 | 80 | -38.30 | +376.1 | `dist_hi<=-0.0579 AND dist_lo>0.0517 AND dow<=0` |
| 9 | h30 | 31 | +1.86 | +58 | +5 | 5/9 | -1,311 | -27.33 ± 38 | 80 | -46.58 | +250.8 | `prev_day_ret<=-0.0247 AND xs_breadth<=-0.0081 AND dec==09:45` |
| 17 | h60 | 144 | -0.79 | -114 | -10 | 6/12 | -9,182 | -20.20 | 80 | +24.87 | +138.8 | `rvol30>0.0048 AND amihud30<=0.0021 AND dow>1` |
| 5 | h30 | 62 | -2.91 | -180 | -15 | 5/12 | -4,230 | -23.21 | 73 | -84.03 | +315.0 | `gap<=-0.0371 AND tod<=0.3594 AND xs_breadth<=-0.0051` |
| 6 | h30 | 43 | -11.98 | -515 | -43 | 6/12 | -2,742 | -30.74 | 60 | -82.62 | +292.3 | `gap<=-0.0371 AND tod<=0.3594 AND dow<=0` |
| 0 | flat | 47 | -100.46 | -4,722 | -395 | 5/12 | -6,834 | -35.85 | 10 | -70.60 | **+439.0** | `log_dv5>15.869 AND dist_lo>0.0346 AND dow<=0` |
| 3 | flat | 46 | -249.22 | -11,464 | -959 | 2/12 | -12,799 | -82.98 | 0 | -126.70 | +368.2 | `log_price<=2.7354 AND dist_lo>0.0517 AND dow>3` |

**24 distinct patterns were carried to the held-out year. Mean OOS result
-$65.35/ticket, median -$42.03, and only 3 of 24 are positive** — against a
best-on-train mean of **+$228.3**. The rank correlation between train $/ticket
and OOS $/ticket across the 24 is **Spearman 0.084 (p = 0.70)**: statistically
indistinguishable from no relationship. The best-on-train rule (#0, +$439 on
train) is the *second worst* out of sample (-$100.46). **Selection on train
transfers nothing usable in this family** — which is the opposite of what
`plan/rl2/rules.py`'s mutation search found (+$46/ticket of transfer), and the
difference is instructive: a beam search of width 120 at depth 3 fits the train
window so much harder that it selects pure noise.

### 5.1 The closest miss, in full

> **`rvol30 > 0.0034` AND `xs_breadth ≤ −0.0081` AND decision time = 09:45**,
> exit after **60 minutes**.
> In words: *at 09:45, when the universe's own average name is down ≥ 0.8% on
> the day, buy the name with the highest 30-minute realised volatility; sell an
> hour later.*

| | |
|---|---|
| OOS tickets | 31 (fires on 12% of days) |
| $/ticket | **+121.21** |
| total / $ per month | **+$3,758 / +$314** |
| months positive | 6 of 9 traded |
| Sharpe | 1.93 |
| max drawdown | -$3,402 |
| best ticket / total ex-best | +$2,422 / **+$1,335** (not one-trade-dependent) |
| percentile vs 30-seed random, same slots | **100** (random -$45.59 ± 44) |
| percentile vs 30-seed random, any slot | **100** |
| inverted score | -$52.85 (loses, as required) |
| aug2026 stub | **0 tickets — it did not fire** |
| monthly | +1535, +1495, -242, +247, **-2592**, +918, +1317, +3305, -2225 |

It passes every control it is given. It **fails the mandate by a factor of 24**
($314/month against $7,500), it trades 31 times a year, and it is one of 24
patterns read on the same held-out window — with 24 draws from a null whose sd
is $44 on 31 tickets, a +$121 reading is about 3.8 sd, which the best of 24
draws would reach roughly 3% of the time by chance alone. **Recorded as the closest miss, not believed.**

---

## Part 6 — STEP 4: breadth, and why it does not rescue the result

Top-*k* at **every** regular-session slot, held-out year:

| pattern | k | tickets | $/ticket | $/month | months + | random | pct |
|---|---|---|---|---|---|---|---|
| walk-forward model | 3 | 6,759 | -20.73 | -11,721 | 0/12 | -26.38 | 100 |
| walk-forward model | 5 | 11,265 | -20.79 | -19,599 | 0/12 | -26.65 | 100 |
| walk-forward model | 10 | 22,530 | -24.18 | -45,584 | 0/12 | -26.26 | 100 |
| `log_dv5>15.869 AND dist_lo>0.0346 AND dow<=0`, flat | 3 | 684 | +86.43 | +4,946 | 8/12 | -42.52 | 100 |
| " | 5 | 799 | +87.92 | +5,877 | 8/12 | -39.84 | 100 |
| " | **10** | 838 | **+100.91** | **+7,075** | **8/12** | -39.15 | 100 |

The last row is the only number in this study that comes near $7,500/month, and
**it does not survive contact**:

| variant | train $/tkt | OOS $/tkt | OOS $/month |
|---|---|---|---|
| `log_dv5>15.869 AND dist_lo>0.0346 AND dow<=0` (full) | +221.97 | **+100.91** | +7,075 |
| **drop `dow<=0`** (all weekdays) | -11.50 | **-23.27** | -7,726 |
| drop `dist_lo` | -42.09 | -11.20 | -2,085 |
| drop `log_dv5` | -53.85 | -19.84 | -9,359 |

Removing the Monday condition flips +$100.91 to **-$23.27**. Inside the
2-condition set the weekday breakdown is Mon **+$100.9**, Tue +$14.6,
Wed **-$145.4**, Thu -$51.9, Fri -$45.2 — while **universe-wide there is no
Monday effect at all** (h30: train Mon -$19.4 is the best weekday, OOS Mon
-$33.5 is among the worst; flat OOS Mon -$65.9 vs Tue -$38.1). The result is a
day-of-week cherry-pick with no out-of-sample mechanism behind it.

Three further reasons it is not a strategy: it is **hold-to-flatten**, the worst
exit in Part 2.1; it takes **17.8 tickets a day**, which is $267,000 of same-day
notional against the account's **$100,000/day, ≤7 ticket, one-position-at-a-time**
rule (`MEMORY.md`); and at h15/h30/h60 — the horizons a sequential one-position
account could actually run — the same set gives **-$21, -$28 and -$2 per ticket**.

**Breadth does not beat concentration here.** The model's own top-k rows get
*worse* as k grows, which is what a real but tiny edge looks like: the 3rd-best
name is already indistinguishable from the 10th.

---

## Part 7 — What it would actually take (`plan/wn_need.py`)

No model, no fitting. Take the **real** OOS cross-section of $15,000-ticket P&L
each day, build a synthetic score with a controlled rank correlation ρ to the
true outcome, buy the top *k*, and read off where $/month crosses $7,500.

**09:35 entry, 30-minute hold, 251 OOS days:**

| ρ | k=1 $/month | k=3 $/month | k=7 $/month |
|---|---|---|---|
| 0.00 (coin flip) | -610 | -2,046 | -4,690 |
| 0.05 | +139 | -202 | -1,460 |
| 0.10 | +778 | +1,492 | +1,751 |
| 0.15 | +1,391 | +3,080 | +4,954 |
| 0.20 | +2,172 | +4,881 | +8,250 |
| 0.30 | +3,894 | +8,784 | +14,846 |
| 0.50 | +8,001 | +17,370 | +28,372 |
| 1.00 (perfect foresight) | **+16,035** | +35,863 | +59,799 |

| configuration | ρ needed for $7,500/month |
|---|---|
| **one ticket a day, 09:35, 30-min hold** | **0.477** |
| one ticket a day, 09:35, 120-min hold | 0.348 |
| one ticket a day, any of 9 RTH times, 30-min | 0.320 |
| 3 tickets a day, 09:35, 30-min | 0.267 |
| **7 tickets a day, 09:35, 30-min** | **0.189** |
| 7 tickets a day, any RTH time, 30-min | **0.150** |

And where this study's rankers actually sit on that axis:

| | $/ticket | implied ρ |
|---|---|---|
| random single pick | -29.03 | 0.00 |
| **walk-forward LightGBM single pick** | **-3.35** | **0.033** |
| closest-miss rule (31 tickets) | +121.21 | 0.222 *(on 31 draws — not a sustained ρ)* |

**The gap is a factor of ~4.5 in information coefficient on the most generous
configuration (7 tickets, any RTH time: 0.15 needed vs 0.033 achieved), and a
factor of ~14 on the one-ticket-a-day configuration the mandate actually asks
for.** A sustained daily cross-sectional IC of 0.15 on a 30-minute horizon from
price-and-volume features over ~50 names is not a tuning problem; it is a
different information set.

Note also the ceiling: **perfect foresight, one ticket a day at 09:35, is only
$16,035/month.** The target is 47% of omniscience. With a 120-minute hold
perfect foresight gives $23,508/month and the target is 32% of it.

---

## Part 8 — TA exits do not rescue the entries (`plan/wn_exits.py`)

`MEMORY.md`'s research line and `plan/rl2/rules.py`'s best held-out rule both
use stop / take-profit / trailing exits instead of a fixed horizon. A 192-point
grid (stop ∈ {2,3,5%, none} × take ∈ {3,5,8%, none} × trail ∈ {3,5%, none} ×
tmax ∈ {60,120,240, none}) was scored on **train**, the single best combination
carried to the held-out year **once**, and the whole OOS grid printed beneath it
so the selection is visible. Exits are evaluated on `mark` (the last printed
close at or before each 5-minute step), never an intrabar extreme.

| entry pattern | best-on-train exit | train $/tkt | **OOS, same exit** | best of all 191 exits *on the OOS itself* | OOS grid median |
|---|---|---|---|---|---|
| `log_dv5>15.869 AND dist_lo>0.0346 AND dow<=0` | tmax=240 | +235.25 | **+17.40** ($+68/mo) | +17.40 | -98.83 |
| `dist_hi<=-0.0579 AND dist_lo>0.0517 AND coil<=0.7476` | take 8%, tmax 240 | +80.77 | **-92.20** | +8.68 | -64.07 |
| `dist_hi<=-0.0579 AND dist_lo>0.0517 AND dow<=0` | take 3% | +101.91 | **-74.97** | +168.99 | +30.72 |
| `log_price<=2.7354 AND dist_lo>0.0517 AND dow>3` | tmax=240 | +251.20 | **-277.20** | -102.30 | -165.24 |

Best-on-train exits transfer to **+$17, -$92, -$75, -$277** per ticket. The exit
lever is worth as little as the entry lever on this universe. (The third row's
OOS ceiling of +$169 is what you get by choosing the exit *after* seeing the
answer — printed precisely so nobody mistakes it for a result.)

---

## Part 9 — Robinhood as an analysis input

Robinhood has no deep intraday history, so Massive remains the backtest source.
It was used for four things.

### 9.1 Bar cross-check — `plan/wn_rhcheck.py`, the most consequential finding

Ten universe names on **2026-08-27**, Massive 1-minute bars vs Robinhood
`get_equity_historicals` 1-minute, extended bounds, interpolated bars dropped:

| symbol | session | Massive bars | RH bars | Massive vol | RH vol | **vol ratio M/RH** | median close diff |
|---|---|---|---|---|---|---|---|
| BB | pre | 171 | 140 | 383,115 | 183,197 | **2.09** | 0.00 bps |
| BB | RTH | 390 | 389 | 12,972,032 | 6,155,861 | **2.11** | 0.00 bps |
| BTCT | pre | 328 | 314 | 5,042,683 | 2,375,794 | 2.12 | 0.00 bps |
| BTCT | RTH | 390 | 390 | 15,620,833 | 10,928,905 | 1.43 | 0.00 bps |
| RBRK | RTH | 390 | 390 | 5,550,542 | 2,178,725 | **2.55** | 0.00 bps |
| SRPT | RTH | 383 | 380 | 7,341,888 | 4,345,633 | 1.69 | 0.00 bps |
| XMTR | RTH | 256 | 230 | 428,826 | 199,260 | 2.15 | 0.00 bps |

**Prices agree exactly** — the median close difference on every common bar, for
every name and every session, is **0.00 bps**. That validates the fill prices.

**Volume does not.** Massive reports **1.4×–2.7× Robinhood's volume**, and —
correcting an earlier belief recorded in this project — **the gap is not
specific to premarket**: it is ~2.1× premarket and ~1.4–2.6× in the regular
session. Polygon's consolidated tape includes off-exchange and odd-lot prints
that Robinhood's bars do not.

**Consequence for this study:** the size cap is *20% of Massive's trailing
5-minute volume*, which is ~**40% of the volume a Robinhood account can see**.
The cap binds on 14% of regular-session rows, so the effect on the headline is
small and, critically, **it can only make the results worse, never better** —
every conclusion here is a FAIL, so the direction is conservative. Post-market
comparison is meaningless because Robinhood bundles the closing cross into one
bar (e.g. BB: 133 Massive bars vs 22 RH bars).


**Sensitivity, so the finding is quantified rather than merely noted.** Re-pricing
the walk-forward single pick with the participation cap cut to reflect the
Robinhood-visible tape (the cap already binds on **19.1%** of the picks at 20%
of Massive volume):

| effective cap | mean notional | $/ticket | total | $/month |
|---|---|---|---|---|
| 20% of Massive volume (the headline) | $13,416 | -3.35 | -842 | -70 |
| **20% of RH-visible volume (= 10% of Massive)** | $12,774 | **-3.62** | -907 | -76 |
| 40% of Massive volume (a looser cap) | $14,181 | -2.32 | -582 | -49 |
| every notional halved outright | $6,708 | -1.68 | — | -35 |

**The verdict does not move.** The gap matters for position sizing in live
trading — you will get less stock than this table assumes on a fifth of the
picks — but it changes no conclusion in this document.

### 9.2 Earnings calendar — a real causal catalyst feature, and it is flat

`get_earnings_calendar`, 24 consecutive 31-day windows, **2024-10-01 →
2026-10-01, 51,140 events, no window refused or empty**. All **191/191**
universe symbols covered, 1,714 events on them (median 8 per name = quarterly,
as it should be). Two causal columns were built: `earn_rh` (signed days to the
nearest report, clipped ±5) and `earn_fresh` (the announcement became public
between the previous close and today's open — a prior-session `pm` report or a
today `am` report). Only the **date and am/pm slot** are used; `eps_actual` and
`eps_estimate` were never collected.

| bucket | h30 train | h30 OOS | h120 train | h120 OOS | flat train | flat OOS |
|---|---|---|---|---|---|---|
| fresh announcement | -27.5 | -28.5 | -43.7 | -69.0 | -198.4 | -60.8 |
| reports today | -31.6 | -32.0 | -23.4 | -34.3 | -106.0 | **+91.0** |
| reports tomorrow | -41.2 | -37.2 | -56.9 | -33.3 | -46.0 | +23.0 |
| reported yesterday | -13.3 | -35.3 | -34.1 | -67.7 | -167.7 | -56.7 |
| **no report within 5 days** | -27.4 | -31.4 | -41.2 | -46.8 | -84.8 | -81.9 |

Every bucket is negative except two flat-horizon OOS cells whose train
counterparts have the **opposite sign** (-$106 → +$91). LightGBM never split on
either column (mean |SHAP| = 0.00). **An earnings-proximity flag carries no
tradeable edge on this universe.** This is a clean negative result on a
legitimately causal catalyst feature, which is worth more than the feature would
have been.

*Caveat:* the calendar was pulled in 2026-09, so it is the **realised** schedule;
a name that moved its report date after the fact is mis-flagged on the old date.
The error is small and unsigned, and since the feature is unused it changes
nothing.

### 9.3 News — too shallow for a backtest, usable live

`get_equity_news`, limit 50, five names. **None hit the cap:**

| symbol | articles | oldest | newest |
|---|---|---|---|
| AAOI | 37 | 2026-08-06 | 2026-09-10 |
| RBRK | 39 | 2026-08-04 | 2026-09-14 |
| SRPT | 9 | 2026-08-05 | 2026-09-09 |
| BB | 6 | 2026-08-25 | 2026-09-16 |
| METC | 8 | 2026-08-18 | 2026-08-19 |

**Robinhood news reaches back about 6 weeks**, not 2 years. Catalyst
classification (offering/dilution vs FDA/contract/earnings/none) is therefore
**impossible to backtest** on this window and can only be used live or in paper
trading. Reported as a hard data limit, not attempted.

### 9.4 Live scannability — the pattern is expressible

`get_scanner_filter_specs` confirms the closest-miss pattern can be run as a
live Robinhood scan without proxies:

| pattern condition | live filter |
|---|---|
| `rvol30 > 0.0034` (30-min realised vol) | `FILTER_TYPE_HISTORICAL_VOLATILITY`, or `FILTER_TYPE_AVERAGE_TRUE_RANGE` length 14 interval 30m |
| `xs_breadth ≤ −0.0081` (universe down on the day) | not a per-instrument filter — compute from `FILTER_TYPE_PERCENT_CHANGE_FROM_CLOSE` interval 1d across the watchlist |
| decision time 09:45 | the scheduler, not a filter |
| liquidity / price floor of the universe | `FILTER_TYPE_AVERAGE_VOLUME` (length 60, 1d) and `FILTER_TYPE_CLOSE` |
| halal gate | not scannable — stays on the local list |

Note for anyone writing that scan: PERCENTAGE filters take decimals (0.05 = 5%),
and a filter with non-empty `supported_intervals` returns nothing if the
interval is omitted. The one genuinely missing piece is `xs_breadth`, which has
to be computed client-side from the day's own universe.

---

## Part 10 — The honesty battery

| check | result |
|---|---|
| **poison (features)** — garbage every bar after minute *m*, recompute through `rl2.features.compute_day` and `wn_table.day_block`, 12 days × 4 cut points | **96 array checks, 0 mismatches** (all 32 feature columns + the causal gate) |
| **poison (picks)** — the top-1 pick of all 21 discovered rules at the cut minute | **816 pick checks, 0 mismatches** |
| **poison (direction)** — the label must move, since it prices minute m+1 onward | **48/48 moved** |
| **shuffled labels** — model refit on labels permuted *within each train day*, 300 fixed rounds | -$30.06/tkt, **36.7th percentile — random**, vs the real model's 96.7th |
| **inverted score** | negative on **22 of 24** rules and on the model (-$69.32); it beats the un-inverted rule on 12 of 24, which is exactly the coin flip you expect when the rules carry no OOS signal |
| **random, 30 seeds, same slots** | -$20 to -$83/ticket depending on the pattern's own timing |
| **random, 30 seeds, any slot** | -$42 to -$51/ticket |
| **unsearched null**, 2,206 rules of the same generator | mean -$31.59, **max +$0.04, 0.05% positive** |
| **cost ladder live** | the unconditional table of Part 2.1 reproduces `plan/rl2/profile_universe.py`'s independent measurement (test window, 15-min RTH: -$33.22 there, -$31.1 here at 09:35) and the extended-hours penalty appears at the predicted ~120 bps |
| **earlier failure, recorded** | the m+1 eligibility gate of 1.3 — found by the poison test, fixed, everything recomputed |

---

## Part 11 — Conclusions and ranked next ideas

### What was established

1. **The universe's unconditional expectancy is ≈ the toll and nothing else.**
   Regular-session tickets lose $15–$31 and the round trip costs $30, so the
   market contributes roughly zero. There is no drift to harvest and no drift
   to fight.
2. **No single feature, and no simple ordering, separates winners.** Zero of 31
   features has a positive decile; zero of 700 top-30 ordering configurations is
   positive.
3. **A properly walk-forward ranker does have real skill, and it is worth about
   $24/ticket** — 96.7th percentile against random, inverted loses, shuffled is
   random. It is simply $6 short of the toll.
4. **Every mean-reversion variant agrees on direction and fails on magnitude.**
   Three independent searches (SHAP, beam rules, `rl2`'s mutation search)
   converge on *buy weakness early when the tape is quiet and the market is
   down*, and none of them pays for the spread.
5. **The bar requires ρ ≈ 0.15–0.48 depending on breadth; the achieved ρ is
   0.033.** Perfect foresight with one ticket a day is $16,035/month, so the
   target is 47% of omniscience.
6. **Robinhood volume is ~2× smaller than Massive's in every session** while
   prices match to 0.00 bps — the participation cap is roughly twice as
   optimistic as it looks.

### Closest miss

`rvol30 > 0.0034 AND xs_breadth ≤ −0.0081` at **09:45**, 60-minute exit:
**+$121.21/ticket, +$3,758, +$314/month, 6/9 months positive, Sharpe 1.93,
100th percentile against both random controls, inverted loses.** It needs to be
**24× larger** to pass, and it only fires 31 times a year. To reach the bar it
would need either ~24× the per-ticket edge (implausible) or to fire every day
*and* hold its per-ticket edge at 7 tickets/day (that combination is $7,500/mo —
i.e. it would have to keep +$121/ticket while going from 31 to ~1,750 tickets,
which the ablations say it will not).

### Ranked next ideas

1. **Change the information set, not the model.** Everything here is price and
   volume on 50 names. The measured ceiling of that information set is ρ ≈ 0.03.
   The cheapest genuinely new inputs available to this account are the **live
   order book** (`get_equity_price_book`) and **options flow**
   (`FILTER_TYPE_RELATIVE_OPTIONS_VOLUME`, `TOTAL_CALL_VOLUME`, open interest) —
   neither is in any cache and neither has ever been tested in this project.
   They cannot be backtested two years back, so this is a **paper-trading-first**
   line.
2. **Attack the toll instead of the alpha.** The whole problem is $30 on a
   $15,000 ticket. A limit-order entry that captures rather than pays the spread
   changes the break-even from ρ ≈ 0.10 to ρ ≈ 0.02 — inside what the walk-
   forward model already demonstrates. Requires a fill model for unexecuted
   limits, which the Robinhood price book could calibrate. **Highest
   expected value of anything on this list.**
3. **Widen the universe rather than the net.** 61 names/day is a thin
   cross-section; E[max] over 61 draws is only ~2.3σ. The halal gate's
   `data/pt_halal` coverage — not the market — is what binds it (the funnel goes
   4,575 liquid → 728 labelled → 61 halal-PASS). Extending quarterly-statement
   coverage would widen the daily cross-section and, at a *fixed* ρ, raise the
   top-1 expectation mechanically.
4. **Trade the 12:00–13:00 window, not the open.** Unconditional expectancy is
   best there (-$13.8 at 12:00/h120, -$15.6 at 13:00/h60) and worst at 09:35.
   Every search in this study was drawn to the open by the volatility; the cost
   arithmetic points the other way.
5. **Stop testing hold-to-flatten.** It is the worst exit at every hour because
   the last print often falls in after-hours and pays 60 bps. Any future search
   should exclude it or force a 15:55 exit.
6. **Do not re-run this family.** Beam search at depth 3 over 483 atoms is the
   strongest fitter of the conjunctive family, the unsearched null has 0.05%
   positive mass, and 24 carried patterns averaged -$65/ticket out of sample at
   Spearman 0.08 train-to-OOS. The family is exhausted. If anything, use a
   *weaker* fitter next time — `rl2`'s mutation search transferred +$46/ticket
   where this beam transferred nothing.

### Files

| | |
|---|---|
| `plan/wn_table.py` | the 380,926-ticket labelled table |
| `plan/wn_lib.py` | splits, causal candidate gate, summarisers |
| `plan/wn_mine.py` | top-30 orderings, decile tables, sector table |
| `plan/wn_model.py` | LightGBM + exact TreeSHAP, walk-forward, shuffled control |
| `plan/wn_rules.py` | beam rule search + unsearched null |
| `plan/wn_oos.py` | one-ticket-a-day validation, breadth, random/inverted controls |
| `plan/wn_exits.py` | TA-exit grid |
| `plan/wn_need.py` | the ρ-required measurement of Part 7 |
| `plan/wn_poison.py` | poison test at the feature *and* pick level |
| `plan/wn_rhcheck.py` | Massive vs Robinhood bar cross-check |
| `data/massive/wn/` | table.npz, all reports, RH pulls, logs |
