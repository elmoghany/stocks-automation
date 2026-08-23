# Liquidity estimation without L2 (W-campaign, 2026-08-22)

Historical L2 does not exist and will not be bought (user direction
2026-08-22); the real book exists only live. This study builds the
way around it: **bar-only estimators, calibrated against the real
book observations our live paper sessions log every day.**

## Deliverables

| piece | where |
|---|---|
| estimator library (causal, self-tested) | `plan/liquidity_estimators.py` |
| ground-truth mining of the live ledgers | `plan/extract_liquidity_truth.py` -> `data/liquidity_truth.json` |
| calibration study (idempotent, re-run any time) | `plan/calibrate_liquidity.py` -> `data/liquidity_calibration.json` |

No sim files were touched (`rotation_sim.py`, `data_manifest.py`,
`day-trading.py`, `shared/massive.py`, `idgate.py` all untouched --
identity adjudication in flight). New files only.

## Ground truth: what the live sessions actually saw

Mined from `data/paper_days/2026-08-{10..21}.{json,md}` (Days 5-13):
every veto row, arming row, entry book and bench book-read with a
usable timestamp.

- **176 book observations** transcribed and validated (bid/ask vs the
  ledger's own percent; the build fails loudly on any mismatch).
- **161 primary** (15 are re-quotes of an unchanged book, excluded
  from correlations), **153 with matching bars**, across **9 days,
  35 symbol-day clusters, 146 premarket / 15 post-open**.
- 66 rows carry a displayed-depth number (mixed definitions: shares
  to the limit cap vs inside size -- ordinal use only).
- Bars: `data/rh_bars/{SYM}_{date}.csv` (Days 8-13), falling back to
  `data/massive/m1/` (Days 5-7). 8 rows (ALOY + stale-NNNN 08-10,
  NTHI 08-12) have no bar file yet and are archived for a Massive
  backfill.
- Honest expectation was 20-60; the ledgers held far more because
  Days 5-7 log a book read nearly every cycle.

Caveats that bound everything below: cycle-precision timestamps are
+/-3 min on Days 5-7; ledger spread denominators varied by day (the
truth file re-canonicalizes to mid where bid/ask exist, ordinal
otherwise); serial reads of the same name cluster hard (Spearman on
153 rows overstates effective n -- the cluster-collapsed table is the
guard); and the sample is names the strategy ranked, which is exactly
the population the sim gates (selection bias in our favor here).

## Estimators (all causal: bars strictly BEFORE the decision minute)

`bar_range` (incumbent: median (H-L)/C over 10 bars, byte-identical
to `rotation_sim.spread_proxy`), `corwin_schultz` (2012, with both
paper corrections), `abdi_ranaldo` (2017), `roll` (1984), `amihud`
(2002, x1e6), `no_trade_share` (fraction of the last 30 calendar
minutes with zero prints), plus max-combos. Self-test
(`python plan/liquidity_estimators.py`): a synthetic random walk with
a known 1.0% bid-ask bounce is recovered at Roll 1.04 / CS 0.94 /
AR 0.99 (documented tolerance 0.5x-1.6x); causality is proved
mechanically (every bar at/after ts is poisoned with 9e9 and no
estimate moves); insufficient data returns None, never a number.

## Results (`python plan/calibrate_liquidity.py`)

Spearman vs observed inside spread, decision-minute causal windows
(lookback 30 bars; incumbent 10 per live parity):

| estimator | premarket rho (n) | post-open rho (n) | cluster-collapsed rho (n=31-35) |
|---|---|---|---|
| **bar_range (incumbent)** | **-0.338** (136) | +0.477 (14) | -0.243 |
| corwin_schultz | -0.118 (116) | **+0.909** (12) | +0.099 |
| abdi_ranaldo | +0.497 (116) | +0.740 (12) | **+0.740** |
| roll | +0.380 (116) | +0.463 (12) | +0.429 |
| **amihud** | **+0.667** (116) | +0.720 (12) | +0.704 |
| **no_trade_share** | **+0.541** (138) | +0.716 (15) | +0.692 |
| max(CS, range) | -0.315 (136) | +0.477 (14) | -0.211 |

Head-to-head on the common premarket subset (n=116), paired
bootstrap of (estimator - incumbent): amihud +0.95 ci90
[+0.72,+1.18], AR +0.79 [+0.54,+1.01], no_trade +0.81 [+0.56,+1.05],
all with P(delta>0)=1.00. Post-open no challenger separates from the
incumbent at n=12-14 (all ci90 straddle 0 except CS's +0.07 mean,
not significant).

### The headline: the incumbent is ANTI-correlated premarket

`bar_range` does not merely lose premarket -- its sign is wrong
(rho -0.34 raw, -0.24 cluster-collapsed). Mechanism, verified on the
rows: **22% of premarket book reads sit on tapes whose last 10 bars
are single-print bars with H=L, so the incumbent reads 0.0% --
"perfectly tight" -- while the median REAL spread on those very reads
is 3.2%.** A wide premarket book produces a sparse tape, not a
wide-range one; range conflates volatility with width, and premarket
the conflation inverts. Every V-series premarket spread-veto replay
built on `spread_proxy` inherits this inversion (post-open replay is
fine). This also explains the live finding that premarket veto rates
ran 90-100% against the modelled 50-65%: the sim's proxy cannot see
premarket width at all.

Second trap, same shape: when the tape is too thin to compute an
estimator (<30 bars), live-parity treats missing as "not vetoed" --
but the 22 premarket reads where AR was undefined had a **median real
spread of 1.72%**. Premarket, *insufficient data is itself evidence
of a wide book*. `no_trade_share` is defined on every row and should
be the backstop.

### Winners

- **Premarket: amihud (rho +0.667) with no_trade_share (+0.541,
  always defined) as the backstop; abdi_ranaldo (+0.497, +0.74
  cluster-collapsed) if a percent-unit spread estimate is needed.**
  A rank-mean ensemble of the three adds nothing over amihud alone
  (+0.635 vs +0.667) -- keep it simple.
- **Post-open: KEEP THE INCUMBENT.** Saying so plainly per the brief:
  bar_range is fine after 09:30 (+0.48 raw, +0.85 on the common
  subset) and nothing beats it significantly at n=14. CS's +0.91 is
  promising but 12 points is not a verdict.
- Roll works premarket (+0.38, +0.57 at lookback 60) but is dominated
  by amihud; CS fails premarket for the same reason as the incumbent
  (it is built from ranges).

### Mapping the live 0.5% cap into estimator units (premarket)

Balanced-accuracy cut separating observed <=0.5% books from >0.5%
books, bootstrap ci90 (n=116-138, 30-32 true passes):

| estimator | veto if > | ci90 | balanced acc |
|---|---|---|---|
| **amihud (x1e6)** | **0.243** | [0.037, 0.266] | **0.82** |
| **no_trade_share** | **0.183** | [0.117, 0.183] | **0.80** |
| abdi_ranaldo (%) | 0.241 | [0.123, 0.263] | 0.72 |
| roll (%) | 0.518 | [0.390, 0.611] | 0.71 |
| bar_range (%) | 0.881 | [0.497, 0.934] | 0.56 |

The incumbent's 0.56 is barely above coin-flip; amihud reaches 0.82.
(AR's cut of ~0.24% vs the 0.5% live cap is coherent: AR estimates
the *effective* spread from prints, which run inside the quoted
spread.) The amihud lower ci bound is loose -- with ~30 true passes
the cut is coarse; treat 0.18-0.27 as the working band, re-fit as the
sample grows.

**Deployable premarket rule for the L-series** (when C37F lands):
```
veto if amihud30 is None            # thin tape IS width evidence
     or amihud30 > 0.24            # x1e6 units, band 0.18-0.27
     or no_trade_share30 > 0.18
post-open: unchanged incumbent (bar_range10 > cap mapping as today)
```

### Depth side

Against the 46-56 logged displayed-depth numbers (log shares;
heterogeneous definitions): amihud rho -0.499 (p 4e-4), no_trade
-0.485 (p 2e-4) -- right sign, real signal, but the ground truth
mixes "shares to the limit cap" with "inside displayed size", so this
is a direction check, not a calibration. The Day-9 LPTH lesson stands
in the data: a tight inside quote coexisted with a 200-share ladder;
no bar statistic will fully see that.

## Honest confidence

153 points, 35 clusters, one fortnight of one strategy's candidate
names, mixed bar feeds (RH vs Massive SIP), +/-3-min stamps on the
older third. The premarket sign inversion of the incumbent and
amihud's lead are robust to cluster collapse and paired bootstrap;
the exact cut values are coarse (ci90s above). Post-open is
data-starved (15 reads) -- no change there is justified yet.

## Standing pipeline (recommendation, not a skill edit)

The calibration sample grows for free if live sessions keep doing
what they already do -- log every book read with its act-time stamp.
Recommended (for whoever next edits the live skill): one
machine-readable line per read,
`BOOK sym=X et=HH:MM:SS bid=A bidsz=N ask=B asksz=M [depth_to_cap=K]`,
in the day's md -- it removes the hand-transcription step; the veto
tables in the daily JSON are already ideal. After each new session:
append rows to `plan/extract_liquidity_truth.py`, re-run it, re-run
`plan/calibrate_liquidity.py` (both idempotent).

## Next steps

1. Massive m1 backfill for ALOY/NNNN 2026-08-10, NTHI 2026-08-12
   (8 archived rows), and future days where rh_bars misses a symbol
   (5 req/min budget: trivial).
2. L-series: wire `liquidity_estimators.amihud` +
   `no_trade_share` into the *sim-side* premarket veto replay with
   the cuts above once C37F identity lands; A/B against the
   spread_proxy veto exactly as the V-series did (shuffle + future
   controls already exist in rotation_sim).
3. Re-fit the cap mapping at ~250 observations (roughly +6 sessions
   at current logging rates); revisit post-open once it has ~40
   reads.
4. Depth truth is the weak leg: if live sessions can log
   `depth_to_cap` shares consistently (one number per read), the
   Amihud-vs-depth mapping becomes calibratable the same way.
