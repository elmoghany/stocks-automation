# Python trading-library audit — W-campaign Phase 3.2 + 0.3 (2026-08-21)

Scope: survey the pip ecosystem for libraries that help THIS system, install
the three approved ones (pandas-ta, quantstats, alphalens-reloaded), and rule
per-library: ADOPT / BORROW / SKIP, with reasons.

House context this audit respects (and every verdict is checked against):

* The engine — `day-trading.py::simulate_trades` + `plan/rotation_sim.py` —
  is PATH-DEPENDENT (one-position rotation, trail state, ticket redeploy).
  No vectorised backtester can replace it; the engine stays the source of
  truth for every P&L number. Libraries may feed it or report on it, never
  re-simulate it.
* Prior audit (commit d9cd49b) already borrowed the four transferable ideas
  from vectorbt / backtesting.py / zipline / NautilusTrader: feature cache
  (`plan/feature_cache.py`), CausalView (`plan/causal.py`), data manifest
  (`plan/data_manifest.py`), and risk/drawdown columns in rotation_sim.
  Nothing below re-covers those four libraries.
* STANDING LAW: "gates subtract, only ordering adds." Anything whose value
  proposition is a trade FILTER (meta-labeling-as-filter included) is a gate
  — documented and SKIPPED, not tested. Pressure-scaled SIZING was already
  rejected in the S-campaign as leverage-masquerading-as-alpha — any
  library idea in the dynamic-sizing family is likewise documented-and-
  skipped. New signals are welcome only as ORDERING inputs (rank factors)
  or as extra entry/exit VOCABULARY to be tested under the full guardrail
  battery.

---

## 0. Install record, the numpy/pandas conflict, and the two-stack
## identity experiment that exonerated it (Phase 0.3)

`pip install --user pandas-ta quantstats alphalens-reloaded` succeeded and
all three imported clean:

| package            | installed | final home                              |
|--------------------|-----------|------------------------------------------|
| pandas-ta          | 0.4.71b0  | research venv `C:\cornell\venvs\ta-research` ONLY |
| quantstats         | 0.0.81    | user site, runs on the system stack      |
| alphalens-reloaded | 0.4.6     | user site, runs on the system stack      |

THE CONFLICT, PRECISELY: the system site-packages had pandas 3.0.5 /
numpy 2.5.1 — the stack every engine baseline was computed on. Two pins in
the new dependency chain are incompatible with it:

* `pandas-ta 0.4.71b0 -> numba 0.61.2 -> numpy >=1.24, <2.3`
* `alphalens-reloaded 0.4.6 -> pandas >=1.5.0, <3.0`

pip therefore placed **numpy 2.2.6 and pandas 2.3.3 in the USER site**
(`%APPDATA%\Python\Python312\site-packages`), and the user site shadows the
system site for every plain `python` run — including the engine. Effective
interpreter versions changed: pandas 3.0.5 -> 2.3.3, numpy 2.5.1 -> 2.2.6.

IDENTITY GATE, RUN TWICE — once under the shadow, once after restoring the
system stack. The two runs are the controlled experiment, and the result is
better than either single run could be:

```
                      shadowed 2.3.3/2.2.6   restored 3.0.5/2.5.1   expect
S095 year                +513,965 EXACT         +513,965 EXACT     +513,965
S095 y2025               +649,573 EXACT         +649,573 EXACT     +649,573
Z104 year                 -29,460 moved          -29,460 moved     +225,646
Z104 y2025            (leg not reached)         -1,872 moved       +417,040
```

Reading this correctly took both runs:

* Z104 year missing its expectation looked at first like the shadow
  breaking the engine. It is not: the restored baseline stack produces the
  **identical** -29,460. The divergence is stack-INDEPENDENT — pandas
  2.3.3/numpy 2.2.6 and pandas 3.0.5/numpy 2.5.1 give byte-identical
  engine output on every leg measured under both. **The library install is
  exonerated: it changed no engine number.**
* What DID move Z104 is a concurrent, unrelated event: the 2026-08-21
  full-breadth m1 backfill (the long-disclosed coverage-bias close-out)
  was running during this audit — `data/massive/m1` grew from 8,472 files
  to 108,991 between this audit's first probe and its last. Z104 is the
  LEGACY full-scan config; its candidate pool just grew ~13x, so its
  2026-08-14-epoch expectation no longer describes the same experiment.
  S095's pool (walk-8 over gappers2, all bars pre-existing) is untouched
  by the backfill — exactly why it stays EXACT everywhere.
* Adjudicating Z104's new value is NOT this audit's call: the session that
  owns the backfill institutionalized `plan/idgate.py` the same night,
  with a `--prepool` replay that must reproduce the OLD value exactly on
  the OLD file set to prove the delta is the data and only the data. That
  mechanism, not this document, re-baselines Z104.

RESOLUTION TAKEN (conservative, engine-first) — even with the install
exonerated, the shadow was removed, because a user-site pandas/numpy
changes the interpreter process-wide for every session on the machine and
happened to be identity-neutral THIS time:

1. Uninstalled ONLY the user-site pandas + numpy. System stack verified
   restored: pandas 3.0.5 / numpy 2.5.1, both resolving from system
   site-packages paths. (Inert `~andas*`/`~umpy*` remnant dirs remain in
   the user site because a concurrent python process held DLLs open; they
   are not importable and can be deleted any time.)
2. quantstats and alphalens-reloaded re-verified ON the restored system
   stack (alphalens' `pandas<3.0` pin is metadata-only; the IC pipeline
   runs fine under pandas 3.0.5 — smoke-tested end-to-end; quantstats'
   demo stats reproduce to the digit under both stacks).
3. pandas-ta canNOT run on the system stack (numba refuses numpy 2.5), so
   it lives in an isolated research venv with its own pandas 2.3.3 /
   numpy 2.2.6, where the cdl probe reproduces identically:

   `python -m venv C:\cornell\venvs\ta-research`
   `C:\cornell\venvs\ta-research\Scripts\python -m pip install pandas-ta quantstats alphalens-reloaded`

STANDING POLICY FROM THIS INCIDENT: **nothing that touches pandas/numpy
goes into the user site, ever** — the user site silently shadows the engine
interpreter for every process on the machine, and next time the stacks may
not agree. Research stacks go in venvs; any install near the engine's
dependency floor re-runs the identity gate (now `plan/idgate.py`) before
its numbers are trusted. Runs that started during the shadow window
(2026-08-21 ~00:00–01:26 local) are retroactively fine for S095/Z104 — the
stacks were measured identical on these paths — but that is a measured
fact, not something that could have been assumed.

---

## 1. pandas-ta 0.4.71b0 — the XP-series dependency (ADOPT, with one caveat)

What it is: pure-python technical analysis on DataFrames.
`df.ta.indicators()` reports 154 entries; the category listing sums to 149
(momentum 43, overlap 36, trend 20, volatility 16, volume 19, statistics 10,
candle 3, cycle 2, performance 2 — the remainder are utility/composite
helpers), plus a 62-name candlestick pattern interface
`ta.cdl_pattern(open_, high, low, close, name=...)`.

### 1a. The caveat that changes the plan: candles mostly delegate to TA-Lib

Probed hands-on against a cached m1 file
(`data/massive/m1/AAOI_2024-11-08.csv`, 573 bars). Without TA-Lib installed,
`cdl_pattern(name="all")` prints `[i] Requires TA-Lib to use <name>` for
**60 of the 62 patterns** and returns only the two natively-implemented
ones:

```
columns: ['CDL_DOJI_10_0.1', 'CDL_INSIDE']   (573 rows, 183 nonzero)
value set: {0.0, 100.0}
```

Label format (TA-Lib convention, one column per pattern, name-prefixed
`CDL_`): 0 = no pattern, +100 = bullish instance, -100 = bearish instance
(a few TA-Lib patterns emit ±200 for stronger variants). Multi-candle
patterns label the COMPLETION bar, which is exactly the causality we need —
the label exists at the close of the bar that completes the pattern, same
contract as our own `patterns_at` labels.

So: **pandas-ta alone does not deliver the pattern set. The XP-series
dependency is really pandas-ta + TA-Lib** (see §4a — `ta-lib` 0.7.1 on PyPI ships a
cp312/win_amd64 binary wheel, confirmed against the PyPI index during this
audit, so this is no longer the historical build pain). pandas-ta remains the right
harness: it handles the DataFrame plumbing, column naming, and gives the
native indicator layer with no C dependency.

### 1b. The 62-pattern set, mapped against our vocabulary

Full `ta.CDL_PATTERN_NAMES` (62): 2crows, 3blackcrows, 3inside, 3linestrike,
3outside, 3starsinsouth, 3whitesoldiers, abandonedbaby, advanceblock,
belthold, breakaway, closingmarubozu, concealbabyswall, counterattack,
darkcloudcover, doji, dojistar, dragonflydoji, engulfing, eveningdojistar,
eveningstar, gapsidesidewhite, gravestonedoji, hammer, hangingman, harami,
haramicross, highwave, hikkake, hikkakemod, homingpigeon, identical3crows,
inneck, inside, invertedhammer, kicking, kickingbylength, ladderbottom,
longleggeddoji, longline, marubozu, matchinglow, mathold, morningdojistar,
morningstar, onneck, piercing, rickshawman, risefall3methods,
separatinglines, shootingstar, shortline, spinningtop, stalledpattern,
sticksandwich, takuri, tasukigap, thrusting, tristar, unique3river,
upsidegap2crows, xsidegap3methods.

BULLISH overlap with the champion's eight-member `C37_BUY_SET`
(bullish_engulfing, bullish_spinning_top, hammer, morning_star,
rising_three, tweezer_bottom, macd_cross_up, rsi_cross_up):

| ours                  | pandas-ta/TA-Lib equivalent                    |
|-----------------------|------------------------------------------------|
| hammer                | `hammer` (stricter: TA-Lib requires downtrend context via a 10-bar body average; ours is shape-only + dip) |
| bullish_engulfing     | `engulfing` == +100                            |
| bullish_spinning_top  | `spinningtop` == +100                          |
| morning_star          | `morningstar` (penetration param, default 0.3) |
| rising_three          | `risefall3methods` == +100                     |
| tweezer_bottom        | **no TA-Lib equivalent** — nearest are `matchinglow` (equal closes, not lows) and `ladderbottom`; our implementation stays |
| macd_cross_up         | native `ta.macd` + cross helper (no TA-Lib)    |
| rsi_cross_up          | native `ta.rsi` + cross helper (no TA-Lib)     |

Conclusion on the bullish side: nothing to replace. Six of eight are
already covered by our own labelers, TA-Lib's stricter trend-context
definitions are a DIFFERENT signal (worth a controlled A/B someday, not a
swap), and tweezer_bottom has no library equivalent at all.

BEARISH extension candidates for the XP-series sell_set study. Our current
bearish vocabulary (12): hanging_man, shooting_star, gravestone_doji,
bearish_spinning_top, bearish_engulfing, tweezer_top, evening_star,
evening_doji_star, three_black_crows, falling_three, rsi_cross_down,
macd_cross_down. The library adds **~14 genuinely new bearish labels**:

* `darkcloudcover` — the classic bearish counterpart of piercing; the most
  credible single addition (widely studied, unambiguous definition).
* `2crows`, `upsidegap2crows`, `identical3crows` — gap-and-fail families;
  interesting precisely because our runners are gap names.
* `advanceblock`, `stalledpattern` — three-white-soldiers DECAY patterns:
  uptrend continuation weakening, which is thematically exactly "the surge
  is exhausting" (our exit problem statement).
* `onneck`, `inneck`, `thrusting` — weak-rally-into-supply continuation
  shorts; in our long-only frame they read as "bounce is failing" exits.
* `harami` / `haramicross` == -100 — inside-bar reversal after a run.
* `tristar` == -100, `eveningdojistar` variant via `dojistar` == -100.
* `hikkake` / `hikkakemod` == -100 — false-breakout traps.
* `3linestrike` == -100, `abandonedbaby` == -100 — rare but high-signal.

XP-series design note (respecting standing law): these enter as SELL-side
vocabulary in `sell_set` — exit patterns under the existing per-pattern
pairtest/X-grid machinery — NOT as entry gates. Exits have been a flat
optimum through six independent rejections (latest: T-series stall release),
so the honest prior is that most of these will not clear the +$30k/both-
years/0-negm bar; the reason to run XP anyway is that the 12-name bearish
set was never widened, and "the surge is exhausting" patterns
(advanceblock/stalledpattern/darkcloudcover) are the first exit family that
targets WINNER decay rather than loser-cutting — a different mechanism than
every rejected time-stop.

### 1c. Indicator layer (native, no TA-Lib): verified working

`ta.rsi`, `ta.macd` (columns `MACD_12_26_9 / MACDh / MACDs`), `ta.squeeze`
(`SQZ_ON/OFF/NO` — the Bollinger-inside-Keltner compression flag) all ran
clean on the AAOI m1 file. `squeeze` is the textbook cousin of our `coil`
(last/high-so-far ≥ 0.95): a volatility-compression rank factor candidate
for a future ordering study — ordering, so it is on the additive path.

VERDICT: **ADOPT** as the XP-series pattern/indicator harness and for
prototyping rank-factor candidates — **run exclusively from the research
venv** (`C:\cornell\venvs\ta-research`, see §0: its numba dependency cannot
import on the engine's numpy 2.5.1, and bending the engine interpreter to
accommodate a research library is exactly the process-wide shadowing §0's
policy now forbids). It never touches the engine: labels are computed
offline to CSV/JSON, compared against our own labelers, and only patterns
that survive the full battery get a hand-written implementation in
`day-trading.py` (the engine keeps zero new dependencies — same policy that
kept the engine dependency-free through the first audit).

---

## 2. quantstats 0.0.81 — reporting only (ADOPT for the weekly memo)

What it is: portfolio analytics on a pd.Series of RETURNS — ~60 stats
(`qs.stats.*`) and an HTML tearsheet generator (`qs.reports.html`).

Probe: fabricated a 20-business-day P&L series on a $100k account
(seeded rng, one -$1,199 RARE-style stop day), converted to returns via the
equity curve, and generated the full pipeline:

* `qs.stats.sharpe/sortino/max_drawdown/win_rate/profit_factor/cvar/
  ulcer_index/tail_ratio/consecutive_losses` — all returned clean numbers.
* `qs.reports.html(returns, output=...)` — wrote a ~358 KB self-contained
  tearsheet (scratchpad `qs_demo_tearsheet.html`). Pipeline proven, and
  re-proven on the restored system stack (pandas 3.0.5/numpy 2.5.1) with
  bit-identical stat values (sharpe 3.1298, maxdd -0.02846, pf 1.5801 on
  the seeded demo series under both stacks).
* `qs.reports.metrics(display=False)` returns the full table; printing it
  on a default Windows console dies on cp1252 (`'﹪'` glyph) — run with
  `PYTHONIOENCODING=utf-8` or keep `display=False` and format ourselves.

Metrics ADOPTED for the weekly campaign memo (complementing the risk columns
rotation_sim already carries — max_dd, max_dd_pct_of_peak, win_days_pct,
best/worst day, tickets_per_day_avg):

| metric                        | why it earns a line                          |
|-------------------------------|----------------------------------------------|
| Sharpe + Prob. Sharpe         | comparability across weeks; PSR guards the small-n delusion on ~5-day samples |
| Sortino                       | our distribution is deliberately right-skewed (tail premium); downside-only vol is the honest denominator |
| Profit factor + payoff ratio  | maps directly onto the winner-median/loser-median hold-time work |
| CVaR (95%, daily)             | expected shortfall of a bad day; pairs with the flat-ticket $ cap |
| Ulcer index + longest DD days | drawdown DEPTH×DURATION, catches slow bleeds that max_dd misses |
| Consecutive losses            | the live-morale number; also feeds the "is the edge decaying" question |

Caveats that keep it OUT of the engine: (1) it wants percent returns — with
flat $15k tickets on a $100k cash account, compounding percent math is a
distortion, so we feed the actual equity curve and read the $ numbers from
our own ledger, quantstats only for the ratio-family stats; (2) it imports
yfinance for benchmark fetching — never pass a benchmark symbol from engine
context, pass `benchmark=None` or a local series; (3) monthly-bucket stats
are uninformative at our sample sizes (same lesson as the monthly bootstrap
in the C38 battery).

VERDICT: **ADOPT, reporting-only.** Zero engine surface. The weekly memo
gets a standard stats block + tearsheet from the paper-ledger equity curve.

---

## 3. alphalens-reloaded 0.4.6 — the Phase 3.3 pre-sim IC filter (ADOPT)

What it is: single-factor evaluation — information coefficient (rank-IC),
quantile spreads, turnover — BEFORE any backtest. Maintained fork of
Quantopian's alphalens. Its `pandas<3.0` pin is what dragged the user-site
pandas 2.3.3 in (see §0), but the pin is metadata-only: the library imports
AND the full IC pipeline runs clean on the engine's pandas 3.0.5 /
numpy 2.5.1 — verified by smoke test after the restoration. Use it from the
system interpreter; never let pip "fix" the pin by downgrading pandas.

What an IC analysis needs (confirmed from the installed signatures):

1. **factor**: a MultiIndex (date, asset) Series — the signal value per
   candidate per decision time.
2. **forward returns**: either derived by the library from a wide
   date×asset `prices` frame (`get_clean_factor_and_forward_returns(factor,
   prices, quantiles=5, periods=(1,5,10), max_loss=0.35)`) or — the hook
   that actually fits us — **supplied directly** via
   `alphalens.utils.get_clean_factor(factor, forward_returns, ...)`.
3. Then `performance.factor_information_coefficient(factor_data)` gives
   per-day Spearman rank-IC per horizon; `mean_information_coefficient`
   aggregates. Smoke-tested end-to-end on synthetic data (8 assets × 60
   days): returns `factor_data` with columns `['1D','5D','factor',
   'factor_quantile']` and a clean IC frame.

Sketch for OUR pipeline (design only — deliberately NOT run in this phase):

* Decision time = ticket time. For each traded day d and each candidate in
  the CAUSAL pool (`day_candidates`, biased_pool=False), factor value =
  `coil` (last/high-so-far at t) or `pressure(30)` (null-pressure rows
  DROPPED, not zero-filled — the 20k-share trust floor stays a trust floor).
  Both come straight from the feature cache, which is already built through
  CausalView, so the factor timestamp is leak-proof by construction.
* Forward return = the horizon the ticket actually lives: entry-time price
  → 14:30 window close (and a 30m/60m pair alongside, matching the
  10-30m profit band from the hold-time study). Computed from the same m1
  bars via CausalView `.future()` with `allow_lookahead` declared — this is
  an ANALYSIS, not a trading path, and the loud logging is the point.
  These go in as user-supplied `forward_returns` via `get_clean_factor`;
  the library's own prices-shift path assumes close-to-close daily cadence,
  which is not our horizon.
* Read-out: mean rank-IC and its t-stat per factor per horizon, plus the
  quantile-spread monotonicity. NOTE the known result this must reproduce:
  the random-rank control (NC60) loses $188,607 vs C37H, so coil/pressure
  ranking demonstrably carries information — coil/pressure ICs are the
  CALIBRATION anchors that tell us what a "real" IC looks like at our n.
* THE ACTUAL PURPOSE (Phase 3.3): any future sentiment / forecast / model
  score must post a rank-IC comparable to the anchors — measured on the
  causal pool, halal 45-day filing lag applied, CausalView timestamps —
  BEFORE it earns a rotation_sim run. This is a research-queue filter, i.e.
  it decides which EXPERIMENTS run, not which TRADES happen — it gates
  compute, not tickets, so it does not collide with "gates subtract."
  Signals that pass enter the engine as ORDERING inputs only.

VERDICT: **ADOPT** as the pre-sim IC filter for Phase 3.3 candidate signals.
Pre-sim only; the engine and its guardrail battery remain the sole
adoption authority.

---

## 4. Survey-only (not installed)

### 4a. TA-Lib — worth it exactly when XP goes to full width
C library + python wrapper; 61 of the 62 CDL patterns pandas-ta names are
implemented here, in C, with trend-context definitions. Historical Windows
pain (compile the C lib yourself / hunt unofficial wheels) is over: the
`ta-lib` 0.7.1 PyPI release ships cp312/win_amd64 binary wheels (checked
against the PyPI index during this audit). **BORROW-when-needed:**
install it the day the XP-series moves from "our 12 bearish labels" to "the
full 26-name bearish sweep" (§1b) — that is its only use here; every
indicator we use day-to-day exists natively in pandas-ta. Keep it out of
the default environment until then — and when the day comes it goes into
the research venv alongside pandas-ta, never the user site (§0 policy).

### 4b. PyPortfolioOpt / skfolio — overkill, and aimed at the wrong problem
Mean-variance/Black-Litterman/HRP portfolio construction (skfolio adds an
sklearn-style API and CV). Our K-series question is "equal-split top-k
one-position rotation, k small"; these libraries answer "continuous-weight
allocation across a large cross-section from estimated moments." Covariance
estimation on 17-bars-a-day penny-stock names with ~7% pool coverage is
noise in, confident weights out — and dynamic weighting is adjacent to the
sizing family the S-campaign already rejected (weights that scale with
conviction are pressure-scaled sizing wearing a suit). **SKIP.** If K-series
ever needs more than equal-split, the first upgrade is rank-IC-weighted
splits measured in our own harness, not an optimizer.

### 4c. mlfinlab — the ideas conflict with standing law; document, don't test
López de Prado toolkit: triple-barrier labeling, meta-labeling, purged CV,
fractional differentiation. The two headline features are exactly what the
law forbids: **triple-barrier labels exist to train a model that DECIDES
WHICH SIGNALS TO TAKE — meta-labeling-as-filter is a gate** (documented-
and-skipped, per the campaign brief), and its companion prescription
"meta-label to SIZE positions" is the S-campaign's rejected family verbatim.
Two ideas are legitimately good and already ours in spirit: purged/embargoed
CV (our both-years walk-forward + 45-day halal lag are purge/embargo by
construction) and event-based sampling (our gapper scan IS an event
sampler). Licensing seals it: mlfinlab went closed/subscription years ago
and the open forks are stale. **SKIP** (with the two borrowed-in-spirit
ideas noted as already implemented).

### 4d. pybroker — a second opinion we don't need
Event-driven walk-forward backtester with ML hooks and bootstrapped metrics.
It is a BACKTESTING ENGINE — and the engine is the one thing we do not
outsource: porting one-position rotation + trail state + ticket redeploy
into pybroker's model would be a re-implementation with new leak surfaces,
to obtain numbers we already produce with exact-identity guarantees. Its
bootstrapped-confidence-interval reporting is the only enviable feature and
quantstats/our own bootstrap cover it. **SKIP.**

### 4e. bt — tree-structured rebalancing, wrong abstraction
Flexible strategy-tree backtester (allocate/rebalance nodes over daily
data). Built for portfolio REBALANCING cadence, not intraday one-position
rotation with path-dependent trails; expressing C37 in bt is not possible
without abusing the framework. **SKIP.**

### 4f. ffn — quantstats' smaller sibling
`ffn` is the stats/utility layer bt sits on (drawdown series, calc_stats,
rebase). Everything it offers arrives with quantstats (which we adopt) or
is already a rotation_sim column. Two reporting stacks is one too many.
**SKIP.**

### 4g. riskfolio-lib — same verdict as PyPortfolioOpt, larger surface
CVaR/EVaR/CDaR-optimised allocation, risk parity, HRP variants — a bigger,
more academic PyPortfolioOpt. Same mismatch: continuous-weight cross-
sectional allocation vs our sequential one-position rotation; same
moment-estimation impossibility on our data; same sizing-family adjacency.
Its risk MEASURES (CVaR/CDaR definitions) are worth reading about; we get
the computations from quantstats. **SKIP.**

---

## 5. What we actually take, ranked

1. **alphalens-reloaded — pre-sim IC filter (ADOPT).** Highest leverage per
   line of code: it decides which Phase 3.3 signals earn engine time, with
   coil/pressure ICs as calibration anchors. Ordering-only by design.
2. **pandas-ta — XP-series harness (ADOPT, research venv only).** The
   pattern-label plumbing and native indicator layer for widening the
   bearish sell_set study; winning patterns get re-implemented in-engine,
   never imported.
3. **quantstats — weekly-memo reporting (ADOPT).** Tearsheet + the six-row
   stats block from the paper equity curve. Zero engine surface.
4. **TA-Lib — deferred BORROW.** Install only when XP needs the 60
   TA-Lib-backed patterns; 0.7.1's cp312/win_amd64 wheel makes it cheap then.
5. **Borrowed-in-spirit, no install:** purged/embargoed CV and event-based
   sampling (mlfinlab) — confirm our walk-forward + 45-day lag already
   implement them, and cite that lineage in the notes.
6. **SKIP:** mlfinlab (meta-label filter = gate; meta-label sizing =
   S-campaign reject), PyPortfolioOpt / skfolio / riskfolio-lib (allocation
   optimisers vs one-position rotation; sizing-adjacent), pybroker / bt
   (second backtest engines — the engine is not outsourced), ffn
   (subsumed by quantstats).

Environment postscript: quantstats and alphalens-reloaded run on the
engine's own stack (pandas 3.0.5 / numpy 2.5.1, verified); pandas-ta runs
ONLY from `C:\cornell\venvs\ta-research`. The user-site pandas/numpy shadow
the install created was removed the same night after a two-stack identity
experiment proved it changed no engine number (§0) — and the same
experiment caught the REAL mover, the concurrent full-breadth m1 backfill,
which shifted the legacy Z104 gate and is the parallel session's
`--prepool` replay to adjudicate. Standing policy: nothing that touches
pandas/numpy ever goes into the user site — research stacks live in venvs,
and any install near the engine's dependencies re-runs the identity gate
before its numbers are trusted.
