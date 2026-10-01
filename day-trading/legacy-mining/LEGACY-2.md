# LEGACY-2: coil as an order (why CHAMPION-REPLAY's coil rank "beat random by +$109, z~5")

Analyst: LEGACY-2 of 15, 2026-10-01. This works only from saved caches (the
cp_feat grid and the cp_panel tape, 466 sessions: Y1 = 193 sessions up to
2025-08-01, Y2 = 251, OOS = 22 from 2026-08-01). The harness is cp_sim with the
post-retraction conventions: RS_DEFER fills at the OPEN of the next printed bar,
gap-through sells, and no stop (the R4 frame).

Scripts:
- `plan/lm2_coil_panel.py` builds 4.10M scanner-candidate rows: every eligible
  name x every 5-minute decision from 09:35 to 14:30. Features are causal. Labels
  are r15/r30/r60/r1500 and the return of the R4 exit stack.
- `plan/lm2_coil_analyze.py`, `plan/lm2_coil_engine.py`, `plan/lm2_coil_tiebreak.py`.
- `plan/lm2_coil_timing.py` did not finish inside the 2-hour cap.

Raw outputs are in `plan/lm2_out/*.txt` and are not committed. Every panel
statistic is day-clustered: the mean is taken within a session, and t is
computed across sessions. Costs: net@15 means 15 bps a side (gappers), net@6
means 6 bps a side. Dollar figures are per $10k ticket.

## 1. Headline: most of R4's coil-order edge comes from a hindsight tie-break leak

`cp_sim.rank_key('coil')` sorts on `-coil` with a **stable argsort**. Coil is
last / running high, so a name printing at its high has coil exactly 1.0. At the
median decision minute, **5 eligible names are tied at the top**: 89% of minutes
have 2 or more ties, and 51% have 5 or more. The array index breaks those ties.

The array order is the order of the gapper-pool file (`gappers_novol_*.json`).
On 4 dates checked, that order has a Spearman correlation of **-0.40 to -0.53
with FULL-DAY volume**. Index 0 is the name that will trade the most today, so
breaking ties by index is lookahead.

The table below keeps the R4 frame (rank by coil, no stop, trail + bearish exit,
rotation) and changes only the tie-break. Values are gross bps per ticket
(`lm2_coil_tiebreak.py`).

| tie-break | Y1 | Y2 | OOS | all 444 | net@15 all | $/mo net@15 |
|---|---:|---:|---:|---:|---:|---:|
| array index (what R4 did; leaky) | +110 | +59 | -133 | **+81** | +51 | +2,249 |
| REVERSED index | -77 | +33 | -135 | **-17** | -47 | -1,880 |
| random, 5 seeds (honest) | +27 avg (-13..+58) | +45 avg (+15..+96) | -82 avg | **+37 avg (+21..+69)** | **+7** | ~+300 |
| causal $-volume so far, DESC | +25 | -2 | -126 | +9 | -21 | -1,119 |
| causal $-volume so far, ASC | -62 | +30 | -7 | -9 | -39 | -1,403 |
| (ref) random name among coil >= .98, 10 seeds | -22 +- 18 | +7 +- 22 | -16 +- 58 | -6 +- 13 | -36 | |
| (ref) rank none = first eligible (also index-ordered, so also leaky) | -9 | -15 | +37 | -12 | -42 | -2,831 |

What this shows:
- **Index order vs reversed index alone moves the result by 98 bps per ticket.**
- With an honest random tie-break, the coil order is worth **about +37 bps gross
  ($37/ticket)**. That is about +43 bps more than a random name from the
  coil >= .98 set, and it is positive in both years in 4 of 5 seeds.
- After costs it is **about +$7/ticket net at 15 bps a side, i.e. break-even.**
  It is negative on OOS: -82 to -233 bps across seeds, on 41 tickets, which is a
  tiny sample.
- No causal volume tie-break reproduces the leak. The best one gives +9 bps.
- The audit's "+$108.92/ticket, z=+5.01" for R4 vs random is contaminated. So
  is its "+$51.80 gross" for `rank: coil only`. Its `rank: none` (first
  eligible) row is also ordered by index.
- The champion's own key (coil group >= .95, then pressure) has no exact ties.
  That is part of the reason it looked "worse than plain coil".

## 2. What coil does on the honest panel (all scanner candidates)

Coil quantiles across candidates: p10 .844, p25 .914, p50 .959, p75 .984,
p90 .995. The forward return by coil bucket is about 0 everywhere except the
tails, and the shape **is an inverted U, not monotone**.

r1500 (hold to 15:00), bps (t):

| bucket | <.80 | .80-.90 | .90-.95 | .95-.98 | .98-.995 | >=.995 (at the high) |
|---|---:|---:|---:|---:|---:|---:|
| Y1 | -19 (-1.1) | -9 | -3 | +1 | -8 | **-26 (-3.1)** |
| Y2 | -34 (-1.6) | -2 | +8 | +7 | +0 | **-15 (-1.6)** |
| OOS | -69 | -18 | +9 | +7 | +5 | -19 |

For r60, the >=.995 bucket is -17 (t -3.6) in Y1 and -12 (t -3.0) in Y2. The
.95-.98 bucket is about 0. Filtering on coil >= x makes holds WORSE as x rises:
r1500 at coil >= .995 is -26 / -15 / -19 (Y1 / Y2 / OOS). **Coil does not help
as a "coil >= x" filter, and sitting exactly at the high is the worst of the
upper buckets.**

**By decision time (r1500), the damage sits in the faded tail, early in the
session.**
- coil < .80:
  - 09:35-09:50: **-127 (Y1) / -306 (t -4.9, Y2)**
  - 09:55-10:00: -130 / -226
  - 10:05-10:30: -82 / -171
  - after 10:35: -13 / -85
  - after 12:00: about 0
- coil .80-.90 before 10:30: -31 to -63 in both years.
- The upper buckets are also negative in the first 15 minutes. At 09:35-09:50,
  >=.995 is -73 (Y1) / -29 (Y2).

**By gain so far:** names already up 40% or more lose **-130 to -585 bps at every
coil level**, in both years. Coil cannot rescue extended names; this is the
atlas's "spent move".

**By price and volume:** in $2-5 names and in low-$-volume names, the <.80
bucket is POSITIVE: +66 / +38 by price and +151 / +103 by volume (Y1 / Y2).
Thin names bounce off washouts. Liquid names ($20+ or high dollar volume) keep
fading: <.80 is -52 to -86. So "faded names keep falling" is a liquid-name
effect, and in thin names it reverses.

## 3. Is it momentum near highs? No: it is "near the high without a spike"

Per-(date, t) Spearman IC, day-clustered. Each feature has the same sign in both
years.

| feature | r60 Y1 / Y2 | r1500 Y1 / Y2 | R4 exit Y1 / Y2 |
|---|---|---|---|
| coil | +.010 (t 3.4) / +.022 (t 7.2) | +.019 (t 3.7) / +.027 (t 5.0) | +.000 / +.009 |
| **ret15b (return over the last 15 min)** | **-.049 (t -30) / -.046 (t -28)** | **-.055 (t -30) / -.051 (t -29)** | **-.112 (t -45) / -.108 (t -46)** |
| hi_gain | | -.015 / -.022 | +.040 / +.024 |
| rvol_now | | -.032 / -.032 | +.017 / -.001 |
| pressure30 | | -.007 / -.001 | .000 / +.009 |

Fama-MacBeth inside each decision group (features rank-scaled, so each
coefficient is top minus bottom):

| outcome | coil Y1 / Y2 | ret15b Y1 / Y2 | $-volume so far Y1 / Y2 |
|---|---|---|---|
| r1500 | **+23 bps (t 1.1) / +64 (t 2.9)** | **-84 (t -21) / -70 (t -19)** | -53 (t -4.0) / -23 (t -1.9) |
| r60 | +9 / +38 (t 4.2) | -52 (t -18) / -46 (t -17) | |

**The strongest and most stable cross-sectional fact in this universe is
short-horizon reversal.** Names that just ran for 15 minutes keep giving it
back, and more so under the champion's trail and bearish exits (IC -0.11).

Coil adds a small positive term only once the recent spike is held fixed. A name
sitting near its high that got there quietly ("coiled") beats one that just
spiked there. Names at coil = 1.0 are disproportionately the ones that just
spiked, which is why the >=.995 bucket returns less. So coil measures
consolidation, not momentum. It is also weak: IC .01-.03, against .05-.11 for
reversal.

**Pick value is not robust.** Inside each decision group, the top-coil name
(tie order effectively random) minus the group mean:
- r4: -8 bps (t -0.4) in Y1, +43 (t +1.6) in Y2
- r1500: -15 in Y1, -9 in Y2

## 4. Thresholds that hold in both years

- **Avoid coil < .80 before 10:30.** It is -80 to -306 bps in both Y1 and Y2
  (t up to -4.9). The exception is $2-5 and low-dollar-volume names, where it is
  positive.
- **coil >= .995 is never better than .95-.98** in either year (r60 t about -3).
- **No upper threshold is positive net of costs** in either year
  (.90/.95/.97/.98/.99 all tested).

## TAKEAWAYS

1. **Fix the tie-break before trusting any coil or "first eligible" result.**
   This is a mechanical fix with a causal reason behind it.
   - **Rule:** every rank key in cp_sim, rotation_sim and live that can tie must
     break ties with a causal key or at random, e.g.
     `-round(coil,5) + 1e-7*rand`.
   - **Expected:** R4's +$81/ticket gross becomes about +$37 gross, or about
     +$7 net@15 at $10k. At about 2.1 tickets a day that is roughly $0-300 a
     month, which is break-even.
   - The 2026-09 audit numbers for R1, R4 and "rank none" should be re-stated.
   - **Test:** `plan/lm2_coil_tiebreak.py` (already run). Also grep the live
     scanner and the ranker in day-trading.py for stable sorts over pool order.
2. **Rank by "quiet near the high": high coil and a low last-15-minute return.**
   - **Rule** (causal at decision minute t): score = pct_rank(coil) -
     pct_rank(ret15b) within the scanner set; require gain_now <= 40% and
     decision >= 09:50; break ties at random; use the R4 exit frame.
   - **Causal story:** fresh spikes reverse (IC -0.05 to -0.11, t about -30, in
     both years), and there is a small premium for consolidating near the high.
   - **Expected** (from the FM spreads; speculative): the top pick sits about
     +40-60 bps above the scanner mean (which is about 0). That is about $40-60
     gross and **+$10-30 net@15 per $10k ticket, about $600-1,500 a month at
     2-3 tickets a day**. The R4-exit IC of ret15b is the big lever here.
   - **Test:** add the rank key to a copy of cp_sim (`plan/lmX`). Run both years
     and OOS, with a 30-seed random control and a ret15b-only control. It must
     beat both controls in Y1 and in Y2 separately.
3. **Hard skip for faded names early in the session.**
   - **Rule:** skip any name with coil < .80 (more than 20% below its high)
     before 10:30, if it is >= $5 or in the top two-thirds by dollar volume.
   - **Why:** those candidates average -80 to -300 bps to 15:00 in both years.
     This is pure avoidance.
   - **Expected:** the value depends on how often the current picker lands on
     these names. A random scanner pick does about 10% of the time, which is
     about +$10-25/ticket of avoided loss.
   - **Test:** add it as a gate on the honest-tie-break engine.

## DISCARD

- **"coil >= x" as a filter at any x (.90-.995):** holds get monotonically worse
  as x rises.
- **Preferring coil exactly at the high (>=.995):** that bucket is where the
  spikes are.
- **R4's +$88.7 gross and "+$109 vs random, z=5":** inflated by the leak. Do not
  cite them.
- **The `rank: none` (first eligible) rows in the CHAMPION-REPLAY ablation:**
  they have the same index leak.
- **Coil group + pressure (the champion key):** pressure has about 0 IC (Y1
  -.007, Y2 -.001).
- **Waiting for coil to reset or reclaim as entry timing:** not measured within
  the cap, because `lm2_coil_timing.py` is too slow as written. The time-bucket
  table gives no sign that waiting for coil >= .97 helps; the upper buckets are
  about 0 at every time of day.
- **The 10:00-start and gain <= 40% rows from `lm2_coil_engine.py`:** they run on
  top of the leaky R4, inherit the index tie-break, and say nothing honest.
