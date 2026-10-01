# LEGACY-10: market regime. Why R4 made money in year 1 and roughly broke even in year 2

**Question.** R4 (the C37/Z104 machinery with coil ranking and no stop, from CHAMPION-REPLAY, on the causal universe with RS_CROSS, hygiene and gap-through fills) earned most of its money in 2024-10 to 2025-07 (Y1). From 2025-08 to 2026-07 (Y2) it was close to break-even. Could a switch built only from data known before each session (trade, size down or sit out) have kept the Y1 edge and avoided the Y2 bleed?

**Data used.** All of it was already saved. No fetching.
- `plan/pa_out/cp_r4_legs.json`: 965 R4 legs over 444 sessions, plus 30 random-pick controls in the same frame (identity to the published $66,760.10).
- `data/massive/gd`: grouped daily bars from 2024-08-05 to 2026-09-01. Features come from SPY, QQQ, IWM, IWC, XBI and ARKK, plus small-cap breadth, gapper counts and gapper follow-through.
- Honest C37 dumps used as a cross-check: `rotation_trades_{C37F,HOLD1}_hf3.json`, `C37F_rs_def(_aug).json`.

**Causality and costs.** Every feature for day D uses closes through D-1 only. Each leg is re-priced at a flat $10k ticket (1e4 x leg return), because 315 of the 965 R4 legs had a notional under $5k.

Cost is 15 bps/side ($30 a round trip, the gapper central cost). Rows marked with the R4 own-fill estimate use 28.75 bps ($57.50).

**Scripts.**
- `plan/lm10_feat.py`: builds the regime features.
- `plan/lm10_regime.py`: Y1-vs-Y2 decomposition, terciles, walk-forward over 426 rules, shuffle null.
- `plan/lm10_tail.py`: pool-quality and tail ICs, frozen rules against random day subsets.
- `plan/lm10_composite.py`: the fixed TREND/CALM label.

## Findings

### 1. The difference between the years is the right tail, not the core

| at $10k, 15 bps/side | Y1 (193 days) | Y2 (251 days) |
|---|---:|---:|
| legs, tickets/day | 423, 2.19 | 542, 2.16 |
| gross $/ticket | +113.7 | +58.2 |
| **net $/ticket** | **+83.7** | **+28.2** |
| net $/month | +3,851 | +1,279 |
| median leg (gross) | +32.8 | +37.3 |
| win rate | 58.2% | 57.4% |
| top-5 legs, sum | +70,229 | +38,279 |
| ex-top-5 gross $/ticket | **-53.0** | **-12.5** |
| winsorized net $/ticket (legs capped at +-15%) | **-83.1** | **-44.0** |
| legs at +15% or more | 20 (4.7%) | 15 (2.8%) |
| random pool net $/ticket | -50.2 | -30.0 |

- The median leg, the win rate and the winsorized core are the same in both years, or slightly better in Y2.
- Y1 is better only because it caught more home runs: MNPR, YIBO, SGN and RNAZ, all in 2024-10 and 2025-01/02.
- Without its tail, R4 loses money in both years at a realistic cost.
- So "what differed" is mostly **how often the tail fired**, not a market regime that switched the core edge off.

### 2. A broad search for a regime filter finds nothing beyond noise

I tested 75 pre-day features. The panel included SPY/QQQ/IWM/IWC/XBI/ARKK 1/5/20-day return, distance from the 20- and 50-day mean, 10/20-day realized vol and the 5d/20d vol ratio. It also had prior-day and 5-day counts of +10% gappers, prior-day gapper close/open and close-location, the count of 50%+ runners, small-cap % up and % above MA20, small-cap dollar-volume surge, and R4's own trailing 5/10/20-day P&L plus the random pool's trailing P&L.

| check | result |
|---|---|
| Best Y1 in-sample gain from a fitted threshold, against 200 day-shuffled copies of the whole panel | **14th percentile of the null.** The real features fit Y1 no better than noise does. |
| Top-10 Y1-fit rules (by $/ticket) applied frozen to Y2 raw P&L, compared with random day subsets of the same size | 2 good (IWC 5d/20d vol ratio low: 98th pct; ARKK vol ratio low: 95th), 2 significantly *harmful* (ARKK vol20 low: 2nd and 3rd pct), the rest in between |
| Winsorized walk-forward | almost every rule "improves" Y2, but only because the winsorized base is negative and any rule trades less: the mean of **all 426** rules is +$997/month. Trading less, not a regime effect. |
| Fit on Y2, test on Y1 | the same picture: top rules lose $1–7k/month of raw Y1 P&L, because they skip the tail days |
| Strategy momentum (R4 trailing 5/10/20-day P&L) | IC from -0.03 to -0.09; terciles inconsistent. **Not useful.** |
| Gapper counts, small-cap breadth, gapper follow-through | no feature has a pool IC above 0.10 with the same sign in both years |

### 3. One coherent, threshold-robust effect: large-cap uptrend with no vol spike (post hoc, so read with care)

The pool-quality ICs give a consistent sign in both years for one family of features.
- Large-cap trend: QQQ_ma20 IC +0.18/+0.09, SPY_ma20 +0.15/+0.09, QQQ_ma50 +0.14/+0.08.
- Vol spike, measured as 5d/20d realized vol: SPY -0.19/-0.06, IWM -0.15/-0.07, QQQ -0.13/-0.06.

No single feature clears 2 sigma in Y2. Combined, they give an un-fitted label with natural thresholds:

> **TC (trend & calm) for day D** = SPY close > its 20-day mean AND QQQ close > its 20-day mean AND SPY 5-day realized vol < SPY 20-day realized vol, all as of D-1's close.

TC is true on 50% of sessions (224 of 444).

| R4 at $10k, net 15 bps | Y1 TC | Y1 not-TC | Y2 TC | Y2 not-TC |
|---|---:|---:|---:|---:|
| tickets | 248 | 175 | 252 | 290 |
| net $/ticket | **+176** | -48 | **+132** | -62 |
| net $/ticket, ex-top-3 legs | +4 | — | +19 | — |
| legs at +15% or more | 18 | 2 | 10 | 5 |
| $/month, traded only on TC | **+4,761** | | **+2,782** | |
| $/month, always traded | +3,851 | | +1,279 | |
| at 28.75 bps: TC-only vs always | +4,019 vs +2,585 | | **+2,202 vs +32** | |

- **Day bootstrap of the R4 TC minus not-TC difference:** +$211/ticket, 90% CI [+49, +379], P(diff <= 0) = 1.7%.
- **The random pool improves as well,** so this is a market effect and not only an R4 effect. Winsorized, the pool is +$38/ticket better on TC days in Y1 and +$17 in Y2. For TREND alone it is +$20/ticket, 90% CI [+1, +37].
- **It is robust to threshold changes:**
  - vol ratio cut at 0.9, 1.0 or 1.1; MA20 vs MA50; SPY alone vs SPY+QQQ; QQQ's vol ratio instead of SPY's
  - on-days are +$89 to +$258/ticket and off-days -$21 to -$160 in both years for every one of these variants
  - "SPY 5d/20d vol < 1" alone does most of the work: Y2 on +107, off -125
- **Some variants are weaker:**
  - the IWM-based version: Y2 +67 vs -5
  - the absolute-vol version (SPY vol20 < 15%): Y2 +64 vs -27
- **TC catches 28 of the 35 tail legs on 52% of the tickets.** The biggest Y1 leg, MNPR on 2024-10-24, fell on a not-TC day, yet TC-only still beats always-trade in Y1.
- **Cross-check on other honest legacy dumps, with the same frozen label and gross $/ticket on TC vs not-TC days:**
  - **HOLD1-hf3:** Y1 -7 vs **-340**; Y2 -4 vs **-136**. Holding a gapper long to the close on a not-TC day is where the damage is.
  - **C37F-hf3:** Y1 -12 vs -14 (no effect); Y2 -9 vs -36.
  - **C37F rs_def:** Y1 **-11 vs +37 (reversed)**; Y2 +12 vs -6.
  - **C37F rs_def, Aug 2026 (true holdout, 22 days):** -51 vs +5 (reversed, small n).
  - **Overall:** the filter helps hold-type gapper longs and is mixed for the fast-rotation C37.

**Overfitting warning.** The TC family was chosen after I had seen both years' ICs. The fitted-quantile search failed its shuffle null. With 75 features, about 4 false "hits" per column are expected. The things that argue against pure luck are:
- the economic story: momentum longs in small caps need a risk-on, non-panicking tape
- the sign is the same in both years for R4 and for the pool
- robustness to the thresholds
- the HOLD1 confirmation

The things that argue for luck are:
- the R4 gain is tail-driven (ex-top-3 TC is about $0 to +$19/ticket)
- the C37 rotation result is mixed
- the 22-day Aug 2026 holdout is reversed

**Treat it as a hypothesis with a pre-registered forward test, not as a result.**

## TAKEAWAYS

1. **Regime gate for gapper longs that hold (R4-type, no stop).**
   - **Rule:** take new gapper-long entries only on TC days (SPY>MA20 & QQQ>MA20 & SPY rv5<rv20, all at the prior close). On other days, sit out, or trade half size if you want to keep tail exposure.
   - **Expected (honest R4 frame, $10k, 15 bps):** about +$130–175 net per ticket on TC days vs about -$50/ticket otherwise. That is **+$2.8k/month (Y2) to +$4.8k/month (Y1)** against +$1.3k–3.9k always-on.
   - **Haircut for the post-hoc choice and the tail dependence:** budget **about +$1–1.5k/month** with roughly one ticket/day on TC days.
   - **Test:** run the cp_sim R4 replay, with the label frozen *now*, on sessions not yet scored: Aug–Sep 2026 and any new paper days. Pass if TC-minus-not-TC is above $0/ticket and the TC-only line is net-positive at 15 bps over at least 60 sessions. Also run it on 2024-08-05 to 2024-10-21 if cp_panel can be extended back.

2. **Risk switch for any close-holding gapper long (HOLD1-type).**
   - **Rule:** on not-TC days, do not carry a gapper long past the morning. Flatten by 10:30 or skip the day.
   - **Expected:** HOLD1 not-TC days averaged -$136 to -$340 gross/ticket against about -$5 on TC days, in both years. At one ticket/day that avoids about **$1.5k–3.5k/month of losses**, which is about 9–11 not-TC days a month x -$136…-$340 + cost. It does not create an edge (TC days are about $0 gross).
   - **Test:** re-score the HOLD1 and R4 dumps with not-TC exits forced at 10:30 using the saved m1 bars, then run Aug 2026 as a holdout.

3. **Measure the tail, not the mean.**
   - R4's year-to-year swing is how often legs of +15% or more appear: 4.7% vs 2.8%, and 5.6% on TC days vs 1.5% otherwise.
   - Any future gapper line should report the tail-leg rate by regime and the winsorized $/ticket next to the raw figure.
   - A strategy whose winsorized core is negative should be sized for the tail, at small and steady size on TC days, not judged by monthly P&L.
   - **Test:** add "tail rate | TC" and "winsor $/tkt" columns to the next COST-RESCORE-style table.

## DISCARD
- **Prior-week or prior-month strategy P&L** as an on/off switch (r4_tr5/10/20, random-pool trailing P&L). The IC is about 0 and the sign is unstable.
- **Number of +10% gappers in prior days,** the 50%+ runner count and small-cap dollar-volume surges. There is no stable relation to pool quality or R4 P&L.
- **Small-cap breadth** (% up, % above MA20) and **prior-day gapper follow-through**. Weak in Y1, gone in Y2.
- **Quantile-fitted regime thresholds picked by best in-sample P&L.** The best Y1 fit sits at the 14th percentile of a shuffled-feature null, and the frozen Y2 results range from +$1.1k to -$1.6k/month.
- **Judging any regime filter on winsorized or "trade less" P&L.** When the base is negative, every filter looks good. Compare against random day subsets of the same size.
- **Expecting a regime switch to rescue the C37 fast rotation.** It is negative gross in every regime cell, and the effect there is mixed or reversed.
