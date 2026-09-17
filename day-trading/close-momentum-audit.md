# CLOSE-MOMENTUM — the last hour, the noon window, and the published market intraday momentum effect

**Agent:** CLOSE-MOMENTUM · **Date:** 2026-09-16 · **Verdict: FAIL, 3.8× short even at zero cost.**

Every prior line in this campaign flattened at 15:00, so the last hour of the
session had never been traded. This line traded it, on the causal wide halal
universe and on the halal index ETFs, and tested the one published,
peer-reviewed intraday effect that speaks directly to it.

**The one-line result.** The published effect (Gao, Han, Li, Zhou 2018, *JFE*)
is **not present** in this window — not in the halal ETFs, not in SPY itself,
and not in single names, where the sign of its key predictor *flips between the
two halves of the sample*. What *is* present in the last hour is the opposite:
a weak, both-years-stable **reversal**. A composite built from it with its sign
and membership fixed on Y1 alone beats a matched random pick by **+$9 to +$18
per ticket** at 100th percentile of 30 seeds, with the inverted mirror and the
shuffled-label control both failing as they should. It is still **−$13.27 per
ticket net** at the seven-ticket rate, because the whole edge is smaller than
the toll. And the number that ends the line: **at zero cost the same
configuration earns +$13.43/ticket = +$1,949/month, against a bar of
$7,500/month.** There is no cost assumption, no universe widening and no better
estimator that closes a 3.8× gap in a frictionless world.

---

## Part 0 — What was run, and where it lives

| artifact | what it is |
|---|---|
| `plan/cm_etf.py` | 1-minute bars for SPUS, HLAL, SPSK, SPRE, UMMA, SPWO (+ SPY as the non-halal replication reference) into **`data/massive/m1etf`**, a cache separate from `m1w` so the RL-v2 manifest's coverage accounting stays exactly true. 3,136 files, 1 EMPTY. |
| `plan/cm_etf_study.py` | the published regressions and their tradeable forms on those ETFs → `data/massive/cm/etf_study.json` |
| `plan/cm_lib.py` | panel, causal late-session features, and the **clock-exit ticket engine** |
| `plan/cm_rows.py` | the decision-row table → `rows_wide.npz` (244,881 rows), `rows_gap.npz` (94,293 rows) |
| `plan/cm_single.py` | the runner, the unconditional profiles, the random/shuffled/foresight controls |
| `plan/cm_configs.py` | the pre-registered sweep — **510 rows** per universe |
| `plan/cm_controls.py` | 30-seed random, inverted mirror, shuffled label, percentiles, daily-P&L bootstrap |
| `plan/cm_rev.py` | the late-session reversal composite (Y1-only sign) and the cost-ladder sensitivity |
| `plan/cm_model.py` | rank IC per feature, and a LightGBM Y1→Y2 arm with its own shuffled-target control |
| `plan/cm_honesty.py` | poison (arrays **and** selections), hold-is-zero, cost monotonicity, foresight, identity gate, half-day audit |
| `plan/cm_report.py` | emits every table below → `data/massive/cm/report.md` |

Nothing outside `plan/cm_*`, this file, `NOTES-DAYTRADING.md` and one index
row was written. `plan/rl2/` (universe builder, panel, frozen volume profile,
`Daily`), `plan/liquidity_estimators.py` and
`plan/penny_ax11b_massive.halal_pt` were reused unmodified.

### The harness

Identical to `plan/rl2/sim.py` except for the exit convention, which the
mandate fixes and which rl2 cannot express:

* **entry** = the **next bar's open** × (1 + cost); availability is read off
  bar *m*, never bar *m+1*. A name whose *m+1* does not print spends the
  attempt and books nothing.
* **exit** = the **stated bar's close** × (1 − cost). `15:59` is the last
  regular-session minute, so it is an approximation of the closing print that
  stays on the cheap side of the 16:00 cost cliff; `15:55` and `15:50` are
  reported as sensitivities throughout.
* $15,000 tickets ×6 then $10,000, ≤ 7 concurrent, ≤ $100,000/day, one open
  ticket per symbol, long only.
* 20 % of the trailing-5-minute volume as the size cap; below $500 notional the
  order is dropped and **no ticket is consumed**.
* 10 bps per side, +50 bps outside 09:30–16:00 (no reported row is outside).
* **Splits:** Y1 = 2024-10-22…2025-07-31 (193 d), Y2 = 2025-08-01…2026-07-31
  (251 d), aug2026 = 2026-08-03…2026-08-06 (4 d stub, never in $/month).
  `$/month = total × 21 / days`, the convention of `plan/wn_lib.py` and
  `plan/rl2/bar.py`.

### The arithmetic of the bar, stated up front

$7,500/month ÷ 21 days ÷ 7 tickets = **+$51.02 net per $15,000 ticket** =
**+34 bps net** = **+54 bps gross** on a round trip that costs 20 bps. Every
number below should be read against +54 bps gross.

---

## Part 1 — Hypothesis 1(a): the published effect on the halal index ETFs

This is the cleanest test available: one series per ETF, no universe
construction, no cross-sectional selection, nothing fitted. SPY is included as
the *replication reference* — it is not halal and is never traded in a reported
row — so that a null on SPUS/HLAL can be told apart from "the published effect
has decayed in this window".

Measures on the ET-minute grid (k = ET minute − 240):
`r_first = c[359]/o[330] − 1` (09:30 open → 10:00),
`r_2last = c[689]/c[659] − 1` (14:59 → 15:29),
`r_last = c[719]/c[689] − 1` (15:29 → 15:59).
Newey–West(5) t-statistics.

| ETF | n | slope on `r_first` | t | slope on `r_2last` | t | mean `r_last` | sign match |
|---|---|---|---|---|---|---|---|
| **SPUS** | 448 | +0.0347 | **+0.85** | +0.0316 | **+0.40** | +0.32 bp | 47.5 % |
| **HLAL** | 448 | +0.0092 | **+0.24** | −0.0431 | **−0.47** | +0.40 bp | 46.2 % |
| SPSK | 447 | −0.0524 | −0.90 | −0.3916 | −2.81 | −3.35 bp | 38.9 % |
| SPRE | 442 | +0.0251 | +0.75 | −0.1469 | −2.17 | −3.64 bp | 44.8 % |
| UMMA | 438 | +0.0398 | +1.09 | −0.2743 | −2.72 | −6.86 bp | 45.9 % |
| SPWO | 384 | +0.0195 | +0.58 | +0.0493 | +0.44 | −1.49 bp | 42.4 % |
| **SPY (reference)** | 448 | +0.0420 | **+0.77** | +0.0308 | **+0.40** | +0.02 bp | 47.3 % |

**Say it plainly: the published effect is not in this window, and not because
the halal ETFs are odd — it is not in SPY either.** Both slopes are positive
with the sign the paper predicts and both are indistinguishable from zero
(|t| < 0.9, R² ≤ 0.003). The sign-match rate between the first and last
half-hour is *below* 50 % on every instrument. The mean last-half-hour return
on the two liquid halal equity ETFs is +0.32 bp and +0.40 bp, against a 20 bps
round trip.

The three t-statistics that do clear 2 — SPSK (−2.81), SPRE (−2.17), UMMA
(−2.72) — are all **negative** (reversal, not momentum) and all on the three
*least* liquid instruments ($0.9M–$2.7M/day). A negative coefficient of the
next half-hour return on the previous one in thin closing prints is the
textbook signature of bid–ask bounce, not an effect to trade. They are reported
because they were measured, not because they are usable.

Tradeable form — one $15,000 ticket a day, decide on the 15:29 bar, fill at the
15:30 open, exit at the 15:59 close:

| row | n | $/ticket | $/month | Y1 | Y2 |
|---|---|---|---|---|---|
| SPUS · always | 448 | −29.29 | −615.2 | −28.56 | −29.33 |
| SPUS · `r_first > 0` | 223 | −28.59 | −298.9 | −26.58 | −28.98 |
| SPUS · `r_2last > 0` | 212 | −31.56 | −313.6 | −35.15 | −27.96 |
| SPUS · both > 0 | 107 | −31.00 | −155.5 | −30.06 | −29.61 |
| SPUS · `r_first < 0` (mirror) | 219 | −29.68 | −304.7 | −29.86 | −29.53 |
| HLAL · always | 448 | −29.23 | −613.8 | −29.25 | −28.65 |
| HLAL · `r_first > 0` | 212 | −29.51 | −293.2 | −28.21 | −29.27 |
| SPY · always | 448 | −29.97 | −629.3 | −29.33 | −30.15 |
| SPY · `r_first > 0` | 249 | −30.19 | −352.4 | −27.97 | −31.16 |

Every conditioning lands within $2 of the unconditioned row, and within $2 of
its own mirror. **−$29.29 on a $15,000 ticket is $30.00 of toll minus $0.71 of
drift**: the ETF rows are a clean read of the cost ladder and nothing else.
The market-timing variant (gate SPUS/HLAL on the SPUS first-half-hour or
second-to-last-half-hour sign) is in `etf_study.json` and moves nothing.

---

## Part 2 — The unconditional shape of the afternoon

Before any signal: what does a random eligible name in the causal wide universe
pay, entry by entry and exit by exit? 448 dates, 191 names, 60.7 names/day.
`gross bp` is the cost-free return of every eligible row; `net $ on $15k` is the
same after the 20 bps round trip.

| entry → exit | rows | gross bp | se | **t** | net $ on $15k | Y1 gross | Y2 gross |
|---|---|---|---|---|---|---|---|
| 12:00 → 14:00 | 17,806 | **+7.58** | 1.26 | **+6.02** | −$22.74 | +3.05 | +9.47 |
| 13:00 → 14:00 | 17,287 | **+6.35** | 0.90 | **+7.06** | −$20.46 | +5.93 | +6.48 |
| 12:00 → 15:00 | 17,806 | +3.75 | 1.53 | +2.45 | −$24.36 | −1.92 | +6.43 |
| 12:00 → 15:59 | 17,806 | +3.00 | 1.76 | +1.70 | −$25.48 | −4.69 | +7.40 |
| 14:00 → 15:00 | 17,492 | −3.37 | 0.86 | −3.92 | −$35.02 | −5.03 | −2.27 |
| **14:00 → 15:30** | 17,492 | **−6.05** | 1.01 | **−5.99** | −$39.02 | −7.46 | −5.13 |
| 15:00 → 15:30 | 19,279 | −1.86 | 0.57 | −3.26 | −$32.75 | −1.01 | −2.53 |
| 15:00 → 15:59 | 19,279 | +1.08 | 0.89 | +1.21 | −$28.36 | −0.82 | +2.55 |
| **15:15 → 15:30** | 19,414 | **−2.91** | 0.42 | **−6.93** | −$34.32 | −2.50 | −3.09 |
| 15:30 → 15:50 | 21,187 | +2.67 | 0.52 | +5.13 | −$25.97 | +0.24 | +4.21 |
| 15:30 → 15:55 | 21,187 | +2.28 | 0.60 | +3.80 | −$26.55 | +0.28 | +3.74 |
| **15:30 → 15:59** | 21,187 | **+3.41** | 0.68 | **+5.01** | −$24.87 | +1.26 | +5.18 |
| **15:45 → 15:59** | 22,898 | **+2.21** | 0.49 | **+4.51** | −$26.66 | +3.38 | +2.19 |

Three things are new here, and none of them had been measured before on this
universe:

1. **The afternoon has a shape.** It sags from 14:00 to about 15:15
   (14:00 → 15:30 is −6.05 bp at t = −6.0, both years negative) and then lifts
   into the close (15:30 → 15:59 is +3.41 bp at t = +5.0, both years positive).
   The last-half-hour drift is real and it survives a split-sample.
2. **It is far too small.** +3.41 bp is **$5.12** on a $15,000 ticket. The bar
   needs +54 bps gross. Selection would have to multiply the drift by **16×**.
3. **The cost cliff is the whole game and this line stays on the right side of
   it.** Every one of these exits is at or before minute 719, so none pays the
   +50 bps extended tier. (An exit *through* 16:00 shows a much larger gross
   drift and a much worse net — it is priced at 60 bps a side and loses ~$82 a
   ticket. This study never takes that exit.)

The matching random-pick ticket expectancies (12 seeds, the real ladder and
size cap) are in `rand_profile_wide.json`; the best afternoon row there is
12:00 → 14:00 at **−$15.91/ticket** and the last-hour rows sit at −$22 to −$26.

---

## Part 3 — The pre-registered sweep: 510 configs, four hypotheses

`plan/cm_configs.py`, each spec × 3 exit bars × topk ∈ {1, 3, 7}, every
directional signal run with its mirror.

**Median over all 510 configs: −$22.00 per ticket**, against a $30 round trip.
The gross edge of the whole family is indistinguishable from zero, exactly as
in WIDE-NET (median −$27) and VS2 (median −$27).

### 3.1 Hypothesis 1 and 4 — the last half hour — are dead, with controls

| config | tickets | $/ticket | $/month | random | **edge** | pct total | pct ex-best | **inverted** | shuffled | daily t |
|---|---|---|---|---|---|---|---|---|---|---|
| H1-first \| 15:59 \| k7 | 3,100 | −21.42 | −3,112 | −22.31 | **+0.89** | 70.0 | 70.0 | **−19.56** | −22.98 | −5.43 |
| H1-first \| 15:59 \| k1 | 443 | −18.29 | −380 | −22.95 | +4.66 | 76.7 | 76.7 | **−14.70** | −21.86 | −1.64 |
| H1-mid \| 15:59 \| k7 | 3,099 | −24.67 | −3,584 | −22.31 | −2.36 | 6.7 | 6.7 | −17.69 | −23.87 | −6.59 |
| H1x-rank-first \| 15:59 \| k7 | 3,100 | −21.42 | −3,112 | −22.31 | +0.89 | 70.0 | 70.0 | −19.48 | −22.98 | −5.43 |
| H4-dm-sum \| 15:59 \| k7 | 3,101 | −21.61 | −3,141 | −22.31 | +0.70 | 70.0 | 70.0 | −20.02 | −22.63 | −5.23 |
| H4-flat@15:30 \| 15:59 \| k7 | 3,100 | −20.70 | −3,008 | −22.31 | +1.61 | 86.7 | 83.3 | −20.70 | −23.75 | −5.80 |

Read the **inverted** column. For every hypothesis-1 row the mirror is
*better than the config*: buying the names whose first half-hour was **worst**
beat buying the ones whose first half-hour was best, by $2–$4 a ticket. A
signal whose reversal outperforms it is not a signal. The largest "edge over
random" in the family is +$1.61, and it belongs to `H4-flat@15:30` — the config
with **no signal at all**, which just buys seven arbitrary names at 15:30. The
window is worth about a dollar and a half a ticket; the published ordering is
worth nothing.

The cross-sectional form (`H1x-rank-first`, `H4-dm-first`) is arithmetically
the same ordering as the raw form within a day, and returns the same numbers —
recorded so nobody re-runs it.

Market timing and the paper's own volatility conditioning do not rescue it:
`H1m-breadth+` (trade only when the halal universe's equal-weight session
return is positive) is −$11.91 to −$15.56/ticket at k = 1 and −$23 at k = 7;
`H1v-hivol` (top-30 % of Y1 `sigma30`) is −$15.04 to −$16.01.

### 3.2 Hypothesis 2 — late-session continuation on causal state

Every H2 row is negative. The best is `H2-rvol@15:00 | 15:59 | k1` at
**−$1.95/ticket, −$41/month**: buy the single highest-relative-volume name at
15:00, hold to the close. It sits at the 100th percentile of its 30-seed random
control (which pays −$26.29), its mirror pays −$20.22 and its shuffled control
−$20.82 — so there *is* a real +$24/ticket of selection there. It is still
negative, its bootstrap daily t is **−0.11**, and one ticket a day cannot reach
$7,500/month even at +$51 (it would need **+$357**).

### 3.3 Hypothesis 3 — the noon window (WIDE-NET's ranked idea #4)

This is where all the positive rows are, and all of them are one ticket a day.

| config | tickets | $/ticket | $/month | Y1 | Y2 | aug2026 | months + | ex-best | daily t | $/mo p5 |
|---|---|---|---|---|---|---|---|---|---|---|
| H3-rvol@12:00→15:59 \| k1 | 448 | **+37.34** | **+784.1** | **−26.83** | +88.88 | −100.69 | 11/23 | +11,231 | **+1.08** | **−331** |
| H3-rvol@12:00→14:00 \| k1 | 448 | +25.66 | +538.9 | −9.59 | +51.48 | +106.18 | 10/23 | +8,081 | +1.17 | −198 |
| H3-flat@12:00→14:00 \| k1 | 448 | +12.64 | +265.4 | −37.17 | +49.96 | +73.82 | 13/23 | +3,468 | +0.67 | −392 |
| H3-vwap@12:00→15:59 \| k1 | 446 | +12.50 | +261.3 | −26.02 | +47.53 | −328.23 | 11/23 | +789 | +0.47 | −616 |
| H3-rvol@12:00→13:00 \| k1 | 448 | +5.13 | +107.7 | −12.71 | +17.47 | +91.41 | 14/23 | −272 | +0.32 | −440 |

The best of them, `H3-rvol@12:00→15:59|k1`, **passes four legs of the bar and
fails three**: 100th percentile on total *and* ex-best, mirror −$29.56,
shuffled −$22.94 — but **Y1 is −$26.83 while Y2 is +$88.88** (fails "both years
positive"), aug2026 is −$100.69 (fails sign consistency), and the bootstrap of
its own daily P&L gives t = +1.08 with a 5th percentile of **−$331/month**.
It is a single high-relative-volume name a day held through the afternoon: a
lottery ticket whose 2025-2026 half happened to win. It does not scale — the
same rule at k = 3 is **−$2.20/ticket** and at k = 7 is **−$15.72**. The edge,
such as it is, lives entirely in the single most-active name and evaporates the
moment a second ticket is added, which is the definition of a configuration
that cannot be sized to the mandate.

### 3.4 Exit sensitivity (15:50 / 15:55 / 15:59)

Consistent across every last-hour family: the **15:59 exit is the best of the
three**, 15:55 is $1–3 worse and 15:50 is $3–6 worse. For the reversal
composite at k = 7: −$13.27 (15:59), −$16.34 (15:55), −$19.11 (15:50). The
drift really is concentrated in the final minutes, which is also why it cannot
be harvested — the only way to get more of it is to cross 16:00 and pay 60 bps
a side.

---

## Part 4 — What is actually there: late-session reversal

### 4.1 The measurement

Rank IC of every causal feature against the realized **net** return of the
ticket the decision opens (`plan/cm_model.py`):

**15:30 → 15:59** (n = 21,187)

| feature | IC all | IC Y1 | IC Y2 |
|---|---|---|---|
| `dist_hi` | **−0.0362** | −0.0307 | −0.0427 |
| `ret_open` | −0.0318 | −0.0014 | −0.0419 |
| `breadth` | −0.0299 | −0.0045 | −0.0359 |
| `dist_vwap` | −0.0288 | −0.0505 | −0.0200 |
| **`r_first`** | **−0.0223** | **+0.0288** | **−0.0394** |
| `sigma30` | +0.0169 | +0.0107 | +0.0226 |

**15:00 → 15:59** (n = 19,279)

| feature | IC all | IC Y1 | IC Y2 |
|---|---|---|---|
| **`r_mid`** (the 14:30→15:00 return) | **−0.0452** | −0.0376 | −0.0503 |
| `dist_vwap30` | −0.0418 | −0.0587 | −0.0358 |
| `dist_hi` | −0.0284 | −0.0286 | −0.0332 |
| `dist_vwap` | −0.0222 | −0.0118 | −0.0291 |
| `xs_rank_mid` | −0.0196 | −0.0154 | −0.0211 |

Two findings:

* **`r_first` is the one feature whose sign flips between the halves of the
  sample** (+0.029 in Y1, −0.039 in Y2). That is the mandate's hypothesis 1 and
  it is the least stable thing in the table. Whatever the 2018 paper measured,
  a decision rule built on it here would have been trained to do the opposite
  of what the next year rewarded.
* **`r_mid` — the published second-to-last half-hour predictor — has a stable
  IC of −0.045 with the *wrong sign*.** On this universe the last half hour
  *reverses* the one before it, in Y1 (−0.038) and in Y2 (−0.050) alike. This
  is the single most consistent relationship the line found, and it is the
  exact negation of the hypothesis it was sent to test.

### 4.2 The composite, built the honest way

Sign **and** membership chosen on Y1 alone (a feature is in iff |IC_Y1| ≥ 0.02),
weights fixed at 1 on within-day cross-sectional z-scores, no coefficient
fitted. Y2 and aug2026 read once per exit bar.

| entry → exit | k | tickets | $/ticket | $/month | Y1 | Y2 | aug | random | **edge** | pct | inverted | shuffled | t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15:00 → 15:55 | 1 | 442 | **+6.20** | **+128.5** | −4.05 | +15.16 | −66.96 | −27.08 | **+33.28** | 100.0 | −31.76 | −26.70 | +0.60 |
| 15:00 → 15:59 | 1 | 443 | −0.58 | −12.1 | −20.73 | +18.36 | −222.61 | −26.29 | +25.71 | 100.0 | −22.82 | −26.19 | −0.04 |
| 15:30 → 15:59 | 3 | 1,326 | −6.02 | −374.3 | −5.28 | −3.80 | −179.68 | −23.56 | +17.54 | 100.0 | −22.97 | −22.80 | −0.90 |
| **15:30 → 15:59** | **7** | **3,095** | **−13.27** | **−1,925.2** | **−12.02** | **−12.10** | −144.91 | −22.31 | **+9.04** | **100.0** | −23.01 | −23.25 | −3.17 |
| 15:30 → 15:55 | 7 | 3,095 | −16.34 | −2,369.9 | −16.91 | −14.59 | −97.22 | −23.79 | +7.45 | 100.0 | −24.52 | −24.28 | −4.57 |
| 15:00 → 15:59 | 7 | 3,098 | −19.65 | −2,854.3 | −23.66 | −15.24 | −104.36 | −25.26 | +5.61 | 96.7 | −29.27 | −22.71 | −3.68 |

**The `15:30 → 15:59 | k7` row is the one to look at**, because seven tickets a
day is the only rate that can reach $7,500/month at all. It is the most
*consistent* row this line produced: Y1 −$12.02 and Y2 −$12.10, identical to
eight cents, at the full ticket rate, at the 100th percentile of 30 random
seeds on total and ex-best, with the mirror at −$23.01 and the shuffled control
at −$23.25 — i.e. **the controls all land on the random pick, and the config is
+$9.04 above them.** That is a genuine, reproducible, out-of-sample selection
premium in the last half hour. It is also, at −$13.27/ticket,
**$64 per ticket away from the bar.**

### 4.3 The fitted arm, which does no better

LightGBM on the 17 causal features, trained on Y1 rows only, read on Y2, three
seeds, with a shuffled-target refit as the control that separates information
from policy shape (rl2 §3.8(b) retired the percentile metric for exactly this
reason):

| entry → exit | k | real seeds ($/ticket on Y2) | IC on Y2 | shuffled-target seeds |
|---|---|---|---|---|
| 15:30 → 15:59 | 7 | −16.42, −16.69, −17.48 | **−0.016, −0.010, −0.013** | −19.33, −21.96, −12.68 |
| 15:00 → 15:59 | 7 | −17.09, −21.47, −21.35 | +0.016, +0.019, +0.024 | −23.46, −18.65, −29.03 |
| 12:00 → 15:59 | 7 | −9.38, −20.05, −14.87 | −0.014, −0.016, −0.013 | −15.43, −14.71, −18.34 |

At 15:30 the fitted model's **out-of-sample IC is negative on all three seeds**:
what Y1 taught it about the last half hour was actively wrong for Y2, which is
`r_first`'s sign flip showing up again. At 15:00 the model does achieve a
positive, three-seed-consistent IC of **+0.016 … +0.024**, and that is the
honest ceiling of the information set here. It sits exactly where WIDE-NET
(ρ = 0.03) and UNIVERSE+QUOTES (ρ = 0.033) left it, against a break-even of
0.126–0.15.

---

## Part 5 — What the toll is worth, and why it cannot save this

UNIVERSE+QUOTES measured the real inside spread on this universe at **2–6 bps**
(half-spread 1–3), so the incumbent 10 bps/side ladder is 2–5× conservative and
that line's ranked idea #2 was to re-baseline it. This is what re-baselining
would actually buy — the same Y1-selected composite, repriced:

| config | fee bps/side | tickets | $/ticket | $/month | Y1 | Y2 |
|---|---|---|---|---|---|---|
| REV 15:30→15:59 k7 | **10 (incumbent)** | 3,095 | −13.27 | −1,925 | −12.02 | −12.10 |
| REV 15:30→15:59 k7 | 5 | 3,095 | **+0.08** | **+12** | +1.30 | +1.26 |
| REV 15:30→15:59 k7 | 2 (measured spread) | 3,095 | **+8.09** | **+1,174** | +9.29 | +9.28 |
| REV 15:30→15:59 k7 | **0 (frictionless)** | 3,095 | **+13.43** | **+1,949** | +14.62 | +14.63 |
| REV 15:00→15:59 k7 | 10 | 3,098 | −19.65 | −2,854 | −23.66 | −15.24 |
| REV 15:00→15:59 k7 | 2 | 3,098 | +1.50 | +218 | −2.61 | +5.97 |
| REV 15:00→15:59 k7 | 0 | 3,098 | +6.79 | +986 | +2.65 | +11.27 |
| RANDOM 15:30→15:59 k7 | 10 | — | −22.43 | — | — | — |
| RANDOM 15:30→15:59 k7 | 0 | — | **+4.56** | — | — | — |

Three readings, in order of importance:

1. **The frictionless ceiling is +$1,949/month.** Give this line a perfect
   broker, a zero spread, no fees and no impact, and the best configuration it
   found earns **26 % of the bar**. That is the number that closes the
   question: no amount of execution work, universe widening or cost
   re-baselining bridges a 3.8× gap that exists *before any cost is charged*.
2. **At the measured spread the composite is real but small.** +$8.09/ticket,
   +$1,174/month, Y1 +$9.29 and Y2 +$9.28 — an unusually stable pair. If the
   cost ladder is ever re-baselined on live fills (UQ's idea #2, still the
   highest-value open item in the campaign), this is what the last hour
   contributes: about a sixth of the target.
3. **The zero-cost random row is +$4.56/ticket**, so of the +$13.43 frictionless
   total, **$4.56 is the window and $8.87 is the selection.** That split is
   worth remembering: two thirds of the frictionless edge is genuine ranking
   skill, and it is still nowhere near enough.

---

## Part 6 — The gapper pool as the second universe: not a result

The mandate asked for the +10 % gapper pool under `RS_CROSS = 1` as a second
universe. It was built (`rows_gap.npz`, 94,293 rows, 10,477 symbol-days, 2,836
symbols; bar coverage 96.9 %, so coverage bias is small) with the +10 % cross
re-derived from the bars so that arming is causal. The sweep then produced rows like
`H3-flat@12:00→15:59 | k7` at **+$65.47/ticket, +$9,268/month** and, the
largest of all, `H3-vwap@12:00→15:59 | k7` at **+$116.74/ticket,
+$16,514/month** — 2.2× the bar, on 3,018 tickets, with a bootstrap t of
+2.45.

**It is not a result, for four independent reasons, and the harness's own
controls say so before any of them:**

1. **The shuffled control beats the real config.** Across the gap sweep the
   shuffled-label control lands at **+$41 to +$116 per ticket** — higher than
   the configs it is supposed to control — and the random control at 12:00 is
   **+$31.00/ticket**. When a control that has had all information destroyed
   outperforms the signal, the P&L is a property of the row population, not the
   ranking. (`H3-flat@12:00→15:59|k7`: real +65.47, random +31.00, shuffled
   **+77.94**. `H3-vwap@12:00→15:59|k7`: real +116.74, random +31.00,
   shuffled **+86.74**. Across every positive gap row the shuffled control
   sits between **+$77.94 and +$198.29 a ticket** — destroying all the
   information makes the strategy *better*.)
2. **It is a lottery distribution.** The top **10 of 3,020 tickets carry
   116.9 %** of the total. Median ticket: **−8.0 bp**. Mean: +99.7 bp. The
   winners are INHD 7.375 → 43.37, BMGL 21.59 → 72.12, MTC 0.63 → 1.97 — single-
   afternoon 2×–6× squeezes in micro-caps, priced at 10 bps a side with no
   spread widening and a 20 %-of-volume cap that barely binds.
3. **Pool membership is still conditioned on the day's own outcome**, the leak
   at the head of the retraction ladder (MX-SERIES RETRACTION #2, +$181k).
   Re-deriving the cross from bars makes *arming* causal; it does not make
   *membership* causal.
4. **94 % of it is not halal.** Only 177 of the 2,836 symbols are halal-PASS
   point-in-time anywhere in the causal wide universe, and only **1,107 of
   94,293 rows (1.2 %)** are both halal-PASS and RS-crossed. Restricted to
   those — the only tradeable subset — the pool yields ~0.25 tickets a day and
   the best row is +$487/month on 77 tickets with t = +1.10 and a shuffled
   control of +$205. There is nothing there to measure.

The hypothesis-1 configs on the gap pool, for the record, are at
−$68 to −$204/ticket and at the 0th–30th percentile of their random controls.

---

## Part 7 — The adversarial battery

| check | result |
|---|---|
| **poison** — garbage on every bar strictly after the decision minute, panel rebuilt from scratch, 20 days × 5 cut points (12:00, 13:00, 15:00, 15:30, 15:45) | **1,900 array checks / 0 mismatches**; **2,400 selection checks / 0 mismatches** — every feature, the print mask, the size cap, *and the identity of the top-1/3/7 names chosen* are bit-identical |
| **hold-is-zero** | 0 tickets, $0.00 |
| **cost monotonicity** | 0× **+$4,558** > 1× **−$79,300** > 10× **−$834,029** |
| **identity gate** | **15,529 tickets** recomputed from (px_in, px_out, shares, minutes) alone across 8 random configs: **0 mismatches, worst \|diff\| $0.0000000000**, 0 tickets below the $500 floor |
| **foresight** (score = the trade's own realized net return) | 15:30→15:59 k1 **+$296.93/tkt, +$6,110/mo**; k7 **+$154.07/tkt, +$21,825/mo**; 15:00→15:59 k7 **+$189.04/tkt, +$26,468/mo**; 12:00→15:59 k7 **+$358.54/tkt, +$50,050/mo** |
| **random** | 30 seeds per controlled row, matched on eligibility, window, exit bar, topk, fills and costs |
| **inverted** | every directional signal run with its sign flipped |
| **shuffled** | 10 seeds, (fill, exit, cap) triple permuted across rows **within each day** — the corrected form (rl2 §2.4) |
| **early closes** | **5 half days** in the window (2024-11-29, 2024-12-24, 2025-07-03, 2025-11-28, 2025-12-24), all 13:00 closes. `plan/market_calendar.HALF_DAYS` covers 2026-2027 only and is **empty** here, so they are detected from the bars. 15:30 and 15:00 decisions on those dates have **0 eligible rows** (no bar printed, the causal gate drops them); the 12:00 decision has **178** rows whose "15:59" exit is in fact the official 13:00 close — honest pricing, mislabelled clock, 1.1 % of dates |

**The bar is 34 % of foresight.** Foresight at the reported policy shape earns
+$21,825/month at 15:30; the target is $7,500. The harness can learn, and the
null has power.

### One look-ahead found and fixed, before any number was reported

`Panel._derive` computed the session-open reference as the open of the day's
**first regular-session print, whenever it happened**. For a name whose first
print of the day was at 15:00, a 10:00 decision would have been handed a price
from five hours in its future — contaminating `ret_open`, `gap` and `r_first`.
`Panel.open_ref(m)` now masks the reference to names that have actually printed
by minute *m*. It was caught by writing the poison test before the results, not
after. Every number in this document is post-fix.

---

## Part 8 — Verdict, the closest miss, and what it would need

### Verdict: **FAIL.**

| leg of the bar | best last-hour row (`REV 15:30→15:59 k7`) | best row of the whole sweep (`H3-rvol@12:00→15:59 k1`) |
|---|---|---|
| ≥ $7,500/month net | **−$1,925** ✗ | **+$784** ✗ (9.6× short) |
| both years positive | −$12.02 / −$12.10 ✗ (stable, stably negative) | −$26.83 / +$88.88 ✗ |
| ≥ 90th pct vs random, total | 100.0 ✓ | 100.0 ✓ |
| ≥ 90th pct vs random, ex-best | 100.0 ✓ | 100.0 ✓ |
| inverted control fails | −$23.01 ✓ | −$29.56 ✓ |
| shuffled control fails | −$23.25 ✓ | −$22.94 ✓ |
| poison passes | ✓ (1,900 + 2,400 checks, 0) | ✓ |
| aug2026 sign-consistent | −$144.91 ✗ | −$100.69 ✗ |

### The closest miss, stated with the number it needs

**`REV | 15:30 → 15:59 | k7`** — the Y1-selected late-session reversal
composite, seven $15,000 tickets a day, decided on the 15:29 bar, filled at the
15:30 open, flattened at the 15:59 close.

* **What it is:** −$13.27/ticket, −$1,925/month, 3,095 tickets over 448 days,
  Y1 −$12.02 / Y2 −$12.10, maxDD −$45,476, 6/23 months positive.
* **What it has:** +$9.04/ticket over a matched 30-seed random control, 100th
  percentile on total *and* ex-best, mirror −$23.01, shuffled −$23.25. Real,
  reproducible selection skill, stable across both halves of the sample.
* **What it would need:** **+$51.02/ticket**, i.e. **+$64.29/ticket more** than
  it makes, i.e. an edge over random of **+$73.33/ticket** instead of +$9.04 —
  **8.1× the selection premium it demonstrated.** In IC terms: ρ ≈ 0.13–0.15
  against the ρ ≈ 0.02 the fitted arm achieved out of sample, the same 4–7×
  information gap WIDE-NET and UNIVERSE+QUOTES both measured.
* **Even with the toll removed entirely** it is +$1,949/month — **3.8× short.**
  This is the decisive fact: the last hour does not contain $7,500/month of
  harvestable drift for a seven-ticket, long-only, halal, $100k/day account,
  at any cost assumption.

### Ranked next ideas

1. **Stop searching price-and-volume features on this universe. The ceiling is
   now measured three ways and it is the same number.** WIDE-NET ρ = 0.03,
   UNIVERSE+QUOTES ρ = 0.033, CLOSE-MOMENTUM's fitted arm ρ = +0.016…+0.024 out
   of sample — against a break-even of 0.126–0.15. Four independent lines
   searching four different hypothesis families have landed on the same
   information ceiling. The binding constraint is the *inputs*, and no further
   estimator, window or universe re-cut moves it.
2. **Re-baseline the cost ladder on live fills — but size the prize honestly.**
   This line puts a number on it that the campaign did not have: at the measured
   2 bps half-spread the best configuration goes from −$1,925 to **+$1,174/month**,
   a $3,099/month swing. That is the largest single move any change has produced
   in this campaign — and it is still 6.4× short. Do it because every historical
   number is wrong without it, not because it is a strategy.
3. **The one genuinely new input available today: the closing auction itself.**
   Every positive gross drift measured here is concentrated in the final
   minutes, and the harness deliberately never takes the 16:00 print because the
   ladder charges 60 bps for it. Whether the closing cross actually costs 60 bps
   is an **assumption with no measurement behind it** and is worth ~$75/ticket.
   Measure it on live paper fills (MOC/LOC orders on SPUS and on two wide-universe
   names) before any further backtest prices an exit through 16:00 either way.
4. **`r_mid` at 15:00 with the reversal sign is the most stable relationship in
   this repo** (IC −0.038 Y1, −0.050 Y2). It does not pay at 10 bps a side. It
   is the right pre-registered candidate if idea 2 or 3 changes the toll, and it
   should be re-run *unchanged* on that day rather than re-searched.
5. **Do not re-run hypothesis 1 in any form.** It was tested at the index level
   on two halal ETFs and on SPY (t ≤ 0.9 everywhere), cross-sectionally, with
   market timing, with the paper's own volatility conditioning, at three exit
   bars and three ticket rates, on two universes. Its key predictor's IC flips
   sign between the halves of the sample. It is exhausted.
6. **The noon window is exhausted as a *selection* problem too.** The only
   positive rows are one ticket a day; the identical rule at k = 3 is
   −$2.20/ticket and at k = 7 is −$13.62. An edge that lives in the single
   most-active name and dies on the second ticket cannot be sized to a
   $100k/day account, whatever its t-statistic.

---

*Reproduce: `python plan/cm_etf.py` → `plan/cm_etf_study.py` →
`plan/cm_rows.py --universe wide|gap` → `plan/cm_single.py --stage profile` →
`plan/cm_configs.py` → `plan/cm_controls.py` → `plan/cm_rev.py` →
`plan/cm_rev.py --stage cost` → `plan/cm_model.py` → `plan/cm_honesty.py` →
`plan/cm_report.py > data/massive/cm/report.md`. Engine Python:
`C:\cornell\venvs\rl`; no package was installed.*
