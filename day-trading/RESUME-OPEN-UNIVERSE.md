# RESUME — OPEN-UNIVERSE (paused 2026-09-17)

Agent: **OPEN-UNIVERSE**. Audit so far: `open-universe-audit.md` (Parts 0–4 written and current).
Working dir for every command below: `C:\cornell\stocks-automation\day-trading`.
Interpreter: `C:\cornell\venvs\rl\Scripts\python.exe` (always `-u`; the PowerShell `Start-Process` redirect buffers otherwise).

---

## 1. State per test

| test | state | what exists | what is left |
|---|---|---|---|
| **0 universe + caches** | **DONE** | `plan/ou_out/universe.json.gz`, `universe_stats.json`, `minute_pairs.json`; `data/massive/m1o` complete; `data/massive/MANIFEST_m1o.json` | — |
| **cost model** | **DONE** | `plan/ou_out/spread_table.json`, `daily_cost.npz`; `data/massive/cost1o` (867 symbols) | optional: `--validate` (daily vs 1-second) never finished, see §4 |
| **1 frame ablation** | **DONE** | `plan/ou_out/frame.json` (65 cells), log `data/massive/ou_frame2.log` | optional: `--stage close1559` (flatten at 15:59 instead of the gd close) **never run** |
| **2 WIDE-NET on m1o** | **PARTIAL** | table (3.76M rows), sweep (5 horizons), top-k policies (288 rows), walk-forward seeds 0 and 1 | shuffle control finishing; `--stage oos` never run; seed 2; catalyst block never added |
| **3 limit-at-bid** | **PARTIAL — fetch running** | `plan/ou_out/limit_pairs.json` (8,243 symbol-days), `limit_picks.json`; fetch ~2,000/8,243 done | finish fetch, then `--stage score` |
| **4 sector-neutral / large-cap** | **DONE** (inside Test 1) | in `frame.json`: `sector-neutral *`, `open_mcap*` (causal) | — |
| **5 halal post hoc** | **DONE** | `plan/ou_out/halal_posthoc.json`, log `data/massive/ou_halal2.log` | — |

### Background jobs left running at the pause (both resumable, safe to kill)

```
# 1-second tape for Test 3 — ~50 min remaining at the pause, resumable per symbol-day
#   (writes data/massive/trades/{SYM}_{DATE}.json.gz; skips what is already there)
$env:MASSIVE_TH_INTERVAL="0.2"
C:\cornell\venvs\rl\Scripts\python.exe -u plan/ou_limit.py --stage fetch --workers 32
#   log: data/massive/ou_limit_fetch.log

# shuffled-label control for the walk-forward ranker — was on fold 2026-02 of 13
C:\cornell\venvs\rl\Scripts\python.exe -u plan/ou_model.py --stage wf --h h30 --seed 0 --shuffle
#   log: data/massive/ou_wf_shuf.log   output: plan/ou_out/model_scores_h30_s0_shuf.npy
```

---

## 2. Relaunch commands, in order

```powershell
# --- finish TEST 2 -------------------------------------------------------
# (a) the shuffled-label control, if plan/ou_out/model_scores_h30_s0_shuf.npy is absent
python -u plan/ou_model.py --stage wf --h h30 --seed 0 --shuffle
# (b) a third seed, so the seed spread can be reported (rl2-audit's lesson:
#     one seed is not a result)
python -u plan/ou_model.py --stage wf --h h30 --seed 2
# (c) the only place a dollar is counted: model policies + 30-seed random +
#     inverted + shuffled + FORESIGHT positive control, both cost models
python -u plan/ou_model.py --stage oos --h h30
#     -> plan/ou_out/model_oos_h30.json
# (d) optional: h60, where the sweep's IC was highest (+0.0175)
python -u plan/ou_model.py --stage wf  --h h60 --seed 0
python -u plan/ou_model.py --stage oos --h h60

# --- finish TEST 3 -------------------------------------------------------
python -u plan/ou_limit.py --stage fetch --workers 32     # resumes
python -u plan/ou_limit.py --stage score                  # -> plan/ou_out/limit.json

# --- the rest of the honesty battery (identity/bars/picks already PASS) ---
python -u plan/ou_poison.py --stage cost
python -u plan/ou_poison.py --stage monotone

# --- optional, and worth doing: the mandate's own exit --------------------
# every Test-1 number flattens at the gd CLOSE (the closing auction). The
# mandate says 15:59. hd measured gd `c` at 4.83 bps from the last RTH minute
# close = $7.25 on a $15k ticket = a quarter of the round trip.
python -u plan/ou_frame.py --stage close1559 --seeds 30   # -> plan/ou_out/frame_1559.json

# --- optional: the daily-vs-1-second cost validation ----------------------
python -u plan/ou_cost.py --validate                      # SLOW, see §4
```

---

## 3. Caches and files this line depends on

**Owned by this line (safe to rebuild):**

| path | size | notes |
|---|---:|---|
| `data/massive/m1o/` | **1.79 GB**, 868 npz | one file per symbol; `dates` + `o,h,l,c,v` (n_dates, 960) float32 |
| `data/massive/MANIFEST_m1o.json` | 1 KB | symbol/date/byte counts, layout, fetch method, identity check |
| `data/massive/cost1o/` | ~1.8 GB, 867 npz | per-minute `spread` / `dv_win` / `sig_win` on the 09:30–16:05 grid |
| `plan/ou_out/table.npz` | **402 MB** | the 3,756,872-row ticket table (git-ignored: `day-trading/data/*` is ignored but `plan/ou_out` is NOT, so this one file is deliberately **not committed** — rebuild it, do not hunt for it) |
| `plan/ou_out/universe.json.gz` | 14 MB | committed |
| `plan/ou_out/daily_cost.npz` | ~60 MB | **not committed**, rebuild with `--build-daily` |
| `plan/ou_out/spread_table.json`, `spread_gt_1sec.json` | small | committed |
| `plan/ou_out/frame.json`, `sweep.json`, `policy.json`, `halal_posthoc.json`, `poison.json`, `table_stats.json`, `minute_pairs.json`, `screen_union.json`, `universe_stats.json`, `limit_pairs.json`, `limit_picks.json` | small | committed |
| `plan/ou_out/model_scores_h30_s{0,1}.npy`, `vol_profile.npy` | small | committed |

**Read, never modified:** `data/massive/gd/`, `data/massive/cost1/`, `data/massive/trades/` (Test 3 ADDS to it, 8,243 new symbol-days), `data/hgr_ticker_meta.json` (Test 0 topped it up with 457 rows and rewrote nothing), `plan/rl2/` (`features.compute_day`, `universe.py`, `out/screen.json.gz`, `out/trading_dates.json`, `out/universe/`), `plan/uq_out/universe/`, `plan/wn_table.py`, `plan/wn_lib.py`, `plan/cr_cost.py`, `plan/uq_sec1.py`, `data/halal_list.json`, `data/sic_codes.json`, `data/earnings_dates.json`.

### Rebuild from nothing

```powershell
python -u plan/ou_universe.py --stage union     # -> plan/ou_out/screen_union.json
python -u plan/ou_meta.py                       # tops up data/hgr_ticker_meta.json
python -u plan/ou_universe.py --stage build     # -> universe.json.gz, minute_pairs.json
$env:MASSIVE_TH_INTERVAL="0.15"
python -u plan/ou_backfill.py --workers 40      # ~70 min, ~7,000 API calls
python -u plan/ou_cost.py --selftest-minute     # MUST pass before anything else
python -u plan/ou_cost.py --build-minute --workers 10    # ~7 min
python -u plan/ou_cost.py --build-spread-table
python -u plan/ou_cost.py --build-daily
python -u plan/ou_table.py --stage profile      # ~10 min
python -u plan/ou_table.py --stage build --block 32     # ~77 min, 7 GB peak RSS
python -u plan/ou_poison.py --stage identity    # MUST pass before any P&L is read
```

### m1o fetch status — complete, and NOT scoped down

Planned: the mandate's top-600-per-date subset = **268,800 symbol-days / 867 symbols / 448 dates**.
Stored: **378,869 symbol-days** across **868 symbols**, 2024-10-22 … 2026-08-06, **0 failures**, **1.79 GB**.
More than planned because the range endpoint returns every date a symbol printed, not only the dates it was in the top 600 — kept, because it costs nothing and lets the minute universe be redefined without refetching. The table build used **268,348** of the planned 268,800 (452 symbol-days had no bars, 0.17%).

---

## 4. Traps (all of these cost time once already)

1. **`plan/ou_out/daily_cost.npz` must be rebuilt after any change to `spread_table.json`.** `DailyCost` reads the npz, not the table.
2. **`ou_cost.py --validate` is slow** — it calls `cr_cost.CostModel._rolling`, a 395-iteration Python loop, once per sampled symbol-day. Use `ou_cost.rolling_batch` instead (it is proven equal to 3.6e-16 relative) or cut `nmax` to ~400.
3. **`ou_table.py --stage build` peaks at ~7 GB RSS** with `--block 32`. Lower the block if RAM is tight; it only changes how many times the cache is read.
4. **Anything that prices many picks must group lookups by symbol.** `MinuteCost.vec` now does; the first cut re-read a 2 MB npz per pick and ran 25 minutes without finishing.
5. **`plan/ou_poison.py --stage identity` is the gate for every measured-cost number.** It caught a missing `(1 + entry cost)` factor in the re-pricing (WIDE-NET's `notional` is the gross ticket, cash out is `notional·(1+c_en)`). It now passes at worst $0.00046 on a $15,000 notional over 12.1M row checks.
6. **`L.mcap()` is a present-day snapshot and is NOT causal. Use `L.mcap_matrix()`.** See the retracted result below.
7. Other research lines share this machine and the Polygon quota (`plan/lx_*.py`, `plan/hgr_*.py`, `plan/rotation_sim.py` were all running). Expect 3–5× wall-clock inflation on CPU-bound stages.

---

## 5. Findings so far

**Headline: FAIL, and the reason is not the one the mandate expected.**

1. **Breadth LOWERS the ceiling.** 64 halal names → 2,532 open names takes the zero-cost ceiling from **+$1,980 to +$1,015/month**. The edge a simple pre-open ordering gets over a 30-seed random control is monotone in book depth and **dies at the tail**: +$25.14/ticket on the 600 deepest books, +$20.31 on the top 300, +$2.02 on rank 601+, **−$1.52 (43rd percentile) on rank 1201+**.
2. **Depth raises it, and not enough.** Top-600 by prior-60-session median dollar volume (fully causal): zero-cost **+$3,732/month**, measured toll **+$1,215**, account-legal ($100k/day) **+$981** — **7.6× short**, Y1 negative, 11/22 months positive, 64% of the total in one day, best of 20 in sample with the runner-up at +$257.
3. **LEAK CAUGHT #1 — present-day market cap.** Slicing on `hgr_ticker_meta.market_cap` (a 2026-09 snapshot) printed **+$4,942/month zero-cost and +$527 net** on mid caps. With market cap computed causally (present-day shares × the **previous** close) it collapses to **+$896 / −$3,515** and the size effect disappears entirely. Fixed in `ou_lib.mcap_matrix`.
4. **LEAK CAUGHT #2 — the present-day halal list, and it is bigger.** A **random** picker inside today's `halal_list.json` beats a random picker inside the point-in-time list by **$941–$1,494/month (+$6.4…+$10.2 a ticket, 4.3–6.8 bp/day)** on the same universe and dates. The gate's debt/cash tests are ratios to market cap, so names that rose are likelier to pass today. **Any backtest that applies `data/halal_list.json` retroactively is inflated by about that much** — relevant right now, because the gate is being repaired and the list was swapped 415 → 472 mid-run.
5. **The measured toll is cheap on deep books and expensive at the open.** Top-600 median **4.30 bps/side** (half 2.83 + impact 1.29) against the incumbent 10 and COST-REBASE's 12.05 on the halal wide universe — but over the **289,152 fills the intraday policies actually take**, all at 09:35/09:45, it is **15.06 bps/side with 61.4% above 10 bps**, because the impact window is five minutes long at the open. **The hour this universe has an edge in is the hour it is most expensive to trade.**
6. **The intraday (minute) arm is decisively negative.** 396 orderings × decision times × 5 horizons: the best top-30 beats random by **+$15…+$20.50/ticket** with IC 0.009–0.020 and its own mirror as the worst row — real, small, and less than a $30 round trip. Best account-legal measured row of 288: **−$59/month at k = 1**; best k = 7: **−$1,563/month**. The walk-forward ranker chose **1–10 boosting rounds out of 600** on 1.5–2.3M training rows in 13 folds — the same "the label is noise" verdict WIDE-NET got on a table 23× smaller.
7. The winning intraday ordering is **short-horizon momentum in the first fifteen minutes** (`ret15+`, `ret30+`, `dist_lo+`, `prev_day_ret+` at 09:35–09:45), opposite in sign to CLOSE-MOMENTUM's 15:30 reversal. Different hour, different sign — not a contradiction.
8. **`rl2/out/screen.json.gz`, the "liquid" universe every prior line used as its no-halal reference, is 30% exchange-traded products** (411,667 ETF symbol-days of 1.55M). It is the worst cell in the Test-1 table on every cost column.

### Honesty battery so far

| check | result |
|---|---|
| identity vs `harness-diagnostic.md` (3 universes) | reproduces **to the dollar** (−$2,432 / +$1,980 / −$2,616 / −$3,141) |
| identity, flat ladder on stored legs vs `wn_table.day_block` | 12,078,885 row checks, worst **$0.00046** on $15,000 |
| `MinuteCost` vs `cr_cost.CostModel._rolling` | 120 symbol-days, worst **3.6e-16** relative (spread), 7.1e-12 (σ) |
| poison, bars after minute m | **160 array checks / 0 mismatches** |
| poison, carried to the PICK | **8,448 pick checks / 0 mismatches** |
| m1o grid vs naive per-bar zoneinfo | AAPL, 339,009 bars, **byte-identical** |
| poison (cost), hold-is-zero, cost-monotone, foresight, shuffled labels, inverted | **NOT YET RUN** — commands in §2 |

### Ranked next ideas

1. **Decide later in the session.** The edge is at 09:35–09:45 and so is the 15 bps toll. The sweep never tried 10:30–13:00 *with* the orderings that work at the open — `rvol30+`/`bar_range5+` @12:00 was the best h120 row (−$13.72 vs random −$34.22) and mid-session impact is ~half the open's. That is the one cell where the two curves might cross.
2. **Finish Test 3.** A resting limit recovers the half-spread (2.83 bps ≈ $4.25/ticket) but **not** the impact term, which is 12 of the 15 bps at 09:35 — so the analytic ceiling on this lever is ~$625/month at 147 tickets, against a −$1,563/month gap. Worth measuring, not worth hoping for.
3. **Size down.** Impact scales as √(Q/DV); at $5,000 a ticket the 09:35 impact term falls by 42%. The mandate fixes the ticket at $15k, but the *measurement* of what a smaller ticket would cost is one line and would say whether the frame is capital-constrained or edge-constrained.
4. **Report the liquidity gradient to the halal line.** The PIT halal universe sits at 122 names/day inside the top-600 — the two screens interact, and the halal gate is being rebuilt right now.
5. Re-run Test 1 with the mandate's true exit (15:59, not the closing auction) — `--stage close1559` is written and never run.
