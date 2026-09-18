# RESUME: DIRECTION-DETECTOR (paused 2026-09-17, ~30 min in)

**Status: PAUSED BEFORE ANY RESULT EXISTS.** Context was read, the
machinery was surveyed, two of the ~nine planned modules were written,
and one cache build was started and then stopped on the pause
instruction. **No number in this line has been measured. Nothing here
is a finding.** Everything below is plan + inventory so the line can be
picked up cold.

Agent name for NOTES / index / audit: **DIRECTION-DETECTOR**.
Working dir: `C:\cornell\stocks-automation\day-trading`.
Interpreter: `C:\cornell\venvs\rl\Scripts\python.exe`.

---

## 1. The question, as I understood it

CHAMPION-REPLAY ended with a measured ceiling and a measured gap:

- A **perfect day-type oracle that RE-RANKS** the champion's machinery
  (fill all 7 tickets a day from the names that will finish highest,
  not merely veto the champion's own picks) earns **+$488.47/ticket,
  +$65,810/month, 22/22 months positive, and +$162.03/ticket AT THE
  MEASURED TOLL**. So the frame can carry the target if direction is
  predictable.
- Its `up30` detector reached **AUC 0.876 / xs-IC +0.343** and was a
  **volatility forecast**; traded, it lost to a coin (−$71.28/tkt vs
  random −$54.87).
- The same pipeline on the **directional** target `upc5` (15:00 close
  ≥ +5% above the decision price) gave **AUC 0.629, xs-IC +0.050,
  t = +6.7** — the repo's familiar ceiling, and **3.8× below the 0.188
  break-even correlation** COST-REBASE computed for 7 tickets/day at
  the measured toll.

**This line's question:** can that 0.050 be pushed materially higher on
THIS panel (scanner universe incl. premarket-only crossers, 09:35–10:00
decision times) via (a) better targets, (b) better features, (c) better
model class, (d) selecting the day-types where direction is
predictable — and what does the best honest detector earn when it
re-ranks R4 (champion machinery, coil as an ORDER, stop deleted) at
measured costs?

Standing mandate: net ≥ $7,500/month over the two-year Massive window,
$15k same-day tickets (≤7/day), long-only, never future/end-of-day
information at decision time. **Halal IGNORED for the search** (user
direction 2026-09-17), applied post-hoc at the end.

Pass bar = EXPERIMENTS-INDEX header. The honest number is the
**measured-toll** one (`cp_cost` / `cr_cost`), not flat 10 bps.

---

## 2. What is already on disk and must be REUSED, NOT MODIFIED

All of this is CHAMPION-REPLAY's and it is complete — this is the
single biggest reason the line is cheap to restart.

| asset | what it is | size |
|---|---|---|
| `data/massive/cp_panel/{date}.npz` | whole gapper tape on a fixed 04:00–16:00 minute grid | **466 dates** |
| `data/massive/cp_feat/{date}.npz` | verified causal feature grid, every 5 min 09:30→15:00 (67 cols) | **466 dates** |
| `data/massive/cp_prior/{date}.json.gz` | prior-only context for every US ticker (dvol60, range60, nhist, prevclose, prevrange, ret5) | 542 dates |
| `data/massive/cp/rows.npz` + `cols.json` | the cross-section table: **448,313 rows × 35 cols**, 466 dates, decision times 09:35/10:00/10:30/11:00/12:00/13:00/14:00 | 31 MB |
| `data/massive/cp/scores_dir.npz` | CHAMPION-REPLAY's `upc5` walk-forward scores (the 0.050 baseline to beat) | |
| `plan/cp_lib.py` | `Day` (causal cumulative views), `crossed_by`, `cross_minute`, `features`, `halal_set` | |
| `plan/cp_feat.py` | the grid builder + `--verify` (44,762 checks, worst 6.0e-08) | |
| `plan/cp_scan.py` | `load()` → the table above | |
| `plan/cp_detect.py` | walk-forward LightGBM, 6 expanding folds, min 120 train days, AUC/IC/precision/lift + shuffled/random/inverted controls | |
| `plan/cp_sim.py` | the sequential-ticket engine (one position at a time, $15k×6+$10k, ≤7/day, ≤$100k/day, deferred fill at the next printed bar's OPEN, gap-through sells clamped into [L,H], −8% stop, pressure-modulated 20/10/40 trail, bearish-engulfing exit, rotation, 14:30 cutoff, 15:00 flatten) | |
| `plan/cp_cost.py` | measured per-fill toll from the 1-minute tape, calibrated to `cr_cost` (medians 38.59 vs 38.15 bps, Spearman +0.966) | |
| `plan/cp_run.py` | `run_batch`, `dates()`, `selftest()`, `controls()` (30 seeds in each row's own frame), `oracle_scores()`, `model_scores()` | |
| `plan/cr_cost.py` | the 1-second-tape cost model | |
| `plan/lx_*.py` | limit-at-bid fills | |
| `data/massive/trades/` | 1-second aggregates `[ts_ms, o, h, l, c, v, n]` | **72,322 symbol-days** |
| `data/massive/cost1/` | per-minute cost statistics | 29,632 |
| `data/massive/m1etf/` | SPY + 6 halal ETFs, 1-min bars, UTC timestamps | 7 syms × **448 dates (ends 2026-08-06)** |
| `data/news_hist/`, `data/filings_hist/` | CATALYST-MINER's corpora | 2,851 / 2,617 symbol files |
| `data/halal_list.json` | 472 PASS names (post-hoc only) | |

**R4, the row to re-rank** (`cp_run.RECOMB`):
`dict(rank="coil", stop_pct=None)` — champion machinery, coil as an
ORDER, −8% stop deleted. Published: 965 tickets, 2.17/day, 444
sessions, **+$69.18/tkt flat10, +$3,035/month, 100th pct on total AND
ex-best vs 30 seeds in its own frame, edge +$108.92/tkt z=+5.01,
inverted −$201.08, both years positive (+$110.98 / +$36.56)** — and
**−$90.27/tkt at the measured toll**, with 5 of 965 legs carrying 119%
of P&L.

---

## 3. What I wrote (committed, untested)

Two modules, both `--build`-only, neither has been run to completion:

- **`plan/dd_prior.py`** — extended PRIOR-ONLY context per (symbol,
  date) from grouped-daily, same emit-before-fold contract as
  `cp_prior`. Fields: `ret1 ret20 hi60 lo60 vol20 amihud60 dvol5 dvolr
  ngap60 gapwin60 prevvolr`. (`ngap60` = the name's own gapper
  FREQUENCY over the prior 60 sessions; `gapwin60` = the share of those
  that closed green — both are new to the repo.)
  - **Started, stopped at 26 of 542 dates.** The build accumulates from
    the first grouped-daily date, so it **must be re-run from scratch**;
    the 26 partial files are simply overwritten.
  - **It is too slow as written: ~8 s/date → ~72 min** on a box already
    at 100% CPU. Before re-running, apply the optimisation in §5.
- **`plan/dd_own.py`** — the name's OWN post-cross history on its PRIOR
  gapper days (`own_n own_med_rc own_mean_rc own_win own_med_mfe
  own_med_mae own_last_rc own_since`), cross minute = LAST rule,
  deferred fill, emit-before-fold. **Never run.**

Also written (a scratch cache, gitignored):
`data/massive/dd_syms.json` — the 7,473-symbol union of the panel.

Nothing else exists. `plan/dd_feat.py`, `dd_sec.py`, `dd_table.py`,
`dd_model.py`, `dd_bucket.py`, `dd_econ.py`, `dd_poison.py`,
`direction-detector-audit.md` are all **unwritten**.

---

## 4. Facts measured during the survey (small, but real, and they change the plan)

These are the only empirical things this session established. They are
coverage/inventory facts, not results.

1. **1-second tape covers 36.9% of the decision rows.** Of the 70,814
   rows at 09:35+10:00, **26,129 have a `data/massive/trades` file.**
   So the mandate's "order-flow proxies from 1-second bars" can only be
   a **partial-coverage block**, and its coverage is *non-random* (the
   tape was fetched where the liquid names are). It must be run as a
   separate ablation on the subset where it exists, with the coverage
   stated — never silently imputed, because "has a tape file" is a
   liquidity proxy and would leak selection into the model.
2. **News/filings coverage is also non-random.** 2,737 of the 5,746
   unique gapper symbols at 09:35/10:00 have a `news_hist` file, but
   that corpus was built for the WIDE universe, so the indicator "has a
   news file" ≈ "was liquid enough for the wide universe". Same
   treatment: ablation block, coverage stated. CATALYST-MINER already
   measured the catalyst block's IC delta at **+0.0008 / −0.0038 /
   −0.0007** at h30/h60/h120, so the prior is that it buys nothing.
3. **`m1etf` ends 2026-08-06** (448 dates × 7 symbols = 3,136 files),
   while the panel runs to **2026-09-01 (466 dates)**. SPY is therefore
   missing for the whole aug-2026 block, and **QQQ is not in the cache
   at all**. Either fetch (`plan/cm_etf.py` pattern, `SYMS` list) or
   accept SPY-only with 18 NaN dates.
4. **m1etf timestamps are UTC**; `zoneinfo("America/New_York")` is
   available and converts correctly across the DST boundary (verified:
   2024-10-22 08:00Z → 04:00−04:00; 2025-01-15 09:00Z → 04:00−05:00).
5. **The box has 4 logical processors and was at 100% load with ~30
   competing python processes** from other research lines. Every design
   choice below assumes single-threaded, cache-once execution.
6. **`cp_sim` is fast**: 20 dates × 2 configs = 3.0 s even under that
   load, i.e. a 444-session × 30-seed control sweep is minutes, not
   hours. The engine is not the bottleneck; the caches are.
7. Panel symbol union = **7,473**; only 33% of grouped-daily's 11,094
   names/day, so filtering `dd_prior` emission to the panel union is
   worth ~1/3 and no more.

---

## 5. The plan, in the order it should be executed

### Step 0 — fix `dd_prior` speed, then build the three caches
`dd_prior._stats` is pure-Python per (symbol, date): 11,094 symbols ×
542 dates ≈ 6M calls. Two changes make it affordable:
  - emit only for symbols in `data/massive/dd_syms.json` **and** only
    for dates in `cp_lib.panel_dates()` (history still accumulates over
    every grouped-daily date — do **not** skip the fold);
  - replace the medians/loops with numpy over a per-symbol ring buffer.

Then, in this order (all single-threaded, all in background):
```
"C:\cornell\venvs\rl\Scripts\python.exe" plan/dd_prior.py --build
"C:\cornell\venvs\rl\Scripts\python.exe" plan/dd_own.py   --build
```

### Step 1 — `plan/dd_feat.py` (NOT YET WRITTEN)
**Decision already taken and worth keeping: build on a REDUCED decision
grid, not cp_feat's 67 columns.** Grid =
`[(9,35), (9,45), (10,0), (10,30), (11,0), (12,0), (13,0), (14,0)]` —
cp_scan's own TIMES plus 09:45. That is 8 columns instead of 67 and it
joins row-for-row onto `cp_scan.load()`.

Feature blocks (all causal, bars ≤ m and prior sessions only):

- **A. Order flow from 1-MINUTE bars (100% coverage).** Window = last
  N ∈ {10, 30} PRINTED bars ending at m. `up_share`, `upvol_share`,
  `clpos` (mean (c−l)/(h−l)), `ret10/ret30`, `rngmean`, `volr_10_30`,
  `dvol_accel`. **Vectorisation note (already worked out):** reuse
  `cp_feat._pressure_grid`'s searchsorted trick, but do NOT truncate
  the row — `np.searchsorted(cumn_row, cumn_row[GRID] - nbars,
  side="right")` on the FULL row gives the identical answer (values
  after m all have cumn ≥ cn ≥ target), so it is one call per name
  instead of one per (name, grid minute). That turns ~16M calls into
  ~250k.
- **A′. Session structure.** `hl_pos` (position in the session range —
  needs a `runlow_from(M_OPEN)`, the mirror of `cp_lib.runhigh_from`),
  `ret_open`, `dist_pmhigh`, `above_vwap_frac` (cumsum of
  `c > cumdv/cumv`), `mins_since_high`, `newhigh_frac`.
- **B. Premarket structure (static).** `pm_low_gain`, **`pm_range_pos`**
  (= (open last − pm low)/(pm high − pm low), the mandate's "premarket
  range position"), `pm_vwap_dist`, `pm_ret_late` (08:00→09:29),
  `pm_dvol_late_share`, `open_vs_pmhigh`, `pm_dens`.
- **C. Multi-day (static).** from `dd_prior` (§3) + cp_scan's existing
  `ret5`, `prevrange`, `nhist`, `dvol60`, `prior_range`, `shares`.
- **D. Breadth / crowding (day-level).** `n_cross` at m (the mandate's
  crowding proxy — `elig_last[:, gi].sum()`), `n_cross_pm`,
  `xs_med_gain`, `xs_med_hi_gain`, `xs_med_rvol`, `spy_pm_ret`,
  `spy_ret_open`, `spy_sigma`. **Caution:** a day-level constant cannot
  move WITHIN-day cross-sectional IC at all; it only matters for the
  bucket policy in Step 4. Do not let it inflate a reported IC.
- **E. Own post-cross history (static).** from `dd_own`.
- **F. 1-second order flow — SEPARATE, ABLATION ONLY, 36.9% coverage.**
  `plan/dd_sec.py`, at 09:35 and 10:00 only (~15k symbol-day file
  reads): uptick share, trade-count skew (`n` field), ask-side vs
  bid-side volume by 1-second bar direction, over [t−10min, t).

`dd_feat.py` must ship `--verify` (recompute a random sample through an
obviously-causal slow path and assert equality, as `cp_feat.verify`
does) before any model is fitted on it.

### Step 2 — `plan/dd_table.py`
Join cp_scan's 35 columns + dd blocks into one table. Add the **new
targets**, all measured strictly after the decision minute:
  - `sgn1500` — sign of the net return to 15:00
  - `sgn60`, `sgn120` — sign of the net return to +60 / +120 min
  - **`payoff`** — "closes ≥ +5% above the decision price AND never
    below −8%" (the champion's actual payoff shape; needs `mae`)
  - `net12` — cost-aware: net return > +12 bps (COST-REBASE's measured
    12.05 bps/side median). Consider also a per-fill version using
    `cp_cost` rather than a flat 12 bps.
  - keep `upc5` as the **published baseline to beat (IC +0.050)**.

### Step 3 — `plan/dd_model.py`
Walk-forward, monthly refits (cp_detect uses 6 expanding folds / min
120 train days — monthly refits are finer and are what the mandate
asks for). Model classes: LightGBM binary (baseline), **lambdarank on
within-day ordering**, a small calibrated logistic, and an ensemble.
Report **calibration (reliability curve / Brier), not just AUC**.
Controls every time: 30-seed random, inverted, **corrected shuffled
labels — permuted WITHIN day** (permuting globally destroys the
cross-section and makes the control too easy), poison on features and
events, foresight ladder.

Report per target: OOS AUC, cross-sectional IC + t, top-decile
precision/lift — and then whether it transfers to $/ticket, which is
the only column that decides anything.

### Step 4 — `plan/dd_bucket.py`
IC per day-type bucket (gap size, premarket $vol, float/shares,
catalyst class, `n_cross` crowding). The question is whether direction
is predictable SOMEWHERE even if not on average. Then a policy that
trades only the predictable buckets. **Guard:** bucket-hunting over
~2,800 buckets is what CATALYST-MINER did — it found 1 bucket with
t > +2 and 1,831 with t < −2. Pre-register the bucket grid and report
the whole distribution of t, not the maximum.

### Step 5 — `plan/dd_econ.py`
Re-rank R4 with each detector variant: `cp_run.run_batch` with
`dict(rank="model", stop_pct=None, _scores=...)`. Scores exist at 8
decision minutes; **forward-fill them across cp_feat's 67-column grid**
(a score computed at 10:00 is legitimately available at 10:05 — this is
causal and must be stated). Note the trap in CHAMPION-REPLAY's own
`model_scores`: unscored minutes are `-inf` for every name, so the rank
degenerates to panel order rather than abstaining.

Report per variant: $/ticket (gross / flat10 / **measured**),
$/month net, tickets/day, months positive, ex-best and ex-top-5 legs,
control percentile vs 30 seeds **in its own frame**, aug-2026 — and
say again, if it is, that **CHAMPION-REPLAY declared aug-2026
UNINFORMATIVE on this panel** (a single random seed earned
+$167.68/tkt on 22 sessions). Also run limit-at-bid fills via `lx` if
cheap.

### Step 6 — `plan/dd_poison.py`
Poison (corrupt every bar strictly after the decision minute, recompute
the whole feature block, assert 0 moved — and assert 0 moved at the
level of the PICKS, not just the arrays), hold-is-zero, cost monotone
in Y, foresight ladder + anti-foresight mirror.

### Step 7 — post-hoc halal
`data/halal_list.json` (472 names) on the best policy.
**Expect the CHAMPION-REPLAY result to repeat:** as a *universe* the
screen HELPS (−$73.01 → −$42.91/tkt), but as a *post-hoc filter* only
6.4% of legs survive and those are worth −$104.37/tkt.

### Step 8 — deliverables
`day-trading/direction-detector-audit.md`, `plan/dd_*`, NOTES entry
"DIRECTION-DETECTOR (2026-09-17)", and the EXPERIMENTS-INDEX row
(replace the paused one).

---

## 6. Ownership (what this line may write)

OWN: `plan/dd_*.py`, `day-trading/direction-detector-audit.md`,
`day-trading/RESUME-DIRECTION-DETECTOR.md`, NOTES append, its own
EXPERIMENTS-INDEX row, and **additions only** to `rotation_sim.py`'s
`CFGS`.
REUSE, DO NOT MODIFY: `plan/cp_*.py`, `plan/cr_*.py`, `plan/wn_*.py`,
`plan/cat_*.py`, `plan/uq_*.py`, `plan/lx_*.py`, `plan/causal.py`.

## 7. Two things to keep in front of you while doing this

- **The bar is the measured toll, not flat 10 bps.** Gapper fills cost
  **31.9 bps/side median (COST-REBASE) / 36.7 (cp_cost)**, ≈ $203 a
  round trip on a $15,000 ticket. Break-even ρ at 7 tickets/day is
  **0.188**. A detector at IC 0.10 is still not enough.
- **CHAMPION-REPLAY's own warning:** an enormous AUC meant nothing
  because the target was range. Every target in Step 2 must be checked
  for the same disease — the tell is feature importance dominated by
  `sigma1`, `rvol_now`, `hi_gain`, `prior_range`, `prevrange`.

## 8. Relaunch, exactly

```
cd C:\cornell\stocks-automation\day-trading
# 0. optimise dd_prior._stats per §5 Step 0, then:
"C:\cornell\venvs\rl\Scripts\python.exe" plan/dd_prior.py --build
"C:\cornell\venvs\rl\Scripts\python.exe" plan/dd_own.py   --build
# 1..8 per §5 -- dd_feat.py onward is unwritten.
```
Sanity check that the inherited stack is intact before anything else:
```
"C:\cornell\venvs\rl\Scripts\python.exe" plan/cp_feat.py --verify
"C:\cornell\venvs\rl\Scripts\python.exe" plan/cp_run.py  --selftest
```
