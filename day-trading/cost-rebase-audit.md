# COST-REBASE (2026-09-16/17) — measure the toll instead of assuming it

**Mandate.** *"UNIVERSE-QUOTES measured the real inside spread at 2–6 bps.
Every result in this project charges 10 bps/side — 2–5× conservative, ≈ $19 a
ticket. Build a MEASURED, causal, per-name per-minute cost model, validate it,
and re-run the best of every line under it. Then: under measured costs, what is
the best net $/month any existing policy reaches, and what IC / tickets-per-day
would the bar now require?"*

---

## Verdict, in one table

Every row is the best of its line, on its own splits and seeds, priced two
ways: the incumbent ladder (which each column reproduces to the digit) and the
measured model.

| line — best row | published $/ticket | published $/month | **measured $/ticket** | **measured $/month** | control pct, measured |
|---|---|---|---|---|---|
| **WIDE-NET LightGBM, refit on the measured label, 1/day** | — | — | **−26.61** | **−559** | **100.0** |
| WIDE-NET LightGBM as published, 1 ticket/day | −3.35 | −70 | −85.15 | −1,788 | 33.3 |
| VS2 `W8RSd` (green-on-red) | +18.1 | +267 | −82.0 | −1,209 | n/a |
| RL-SCOUT v2, rules seed 0 | +14.11 | +355 | −59.97 | −1,506 | 100.0 |
| UNIVERSE-QUOTES, relabelled limit policy | +0.06 | +7 | −44.34 | −4,489 | **3.3** |
| **UNIVERSE-QUOTES, refit on the measured label** | — | — | **−22.76** | **−1,792** | **100.0** |
| HOLD1-hf2 | −180.76 | −3,410 | −353.59 | −6,670 | n/a |
| C37F-hf2 (live rules) | **−55.08 at ZERO toll** | −4,023 | **−246.93** | **−18,037** | n/a |

**The best net $/month any existing policy reaches under measured costs is
−$559/month** (wide-net refit, one ticket a day). Under the most generous
variant of the model — spread only, no impact at all — no row clears
+$500/month either. **FAIL, by more than $8,000/month.**

Three findings, in the order that matters:

1. **The premise is only half true.** The measured *half-spread* on the causal
   wide universe is **2.8 bps** at the median — so the spread half of the
   incumbent 10 bps/side ladder is indeed 2–5× conservative, exactly as
   UNIVERSE-QUOTES said. But the incumbent ladder charges **no market impact at
   all**, and a $15,000 ticket is **2.6% of the trailing 10-minute dollar
   volume** of the median name in this universe. Under a square-root law with
   the coefficient at the top of the published range that is **9.2 bps** — as
   big as the whole assumed toll. Total measured cost: **12.05 bps/side at the
   median, above 10 bps on 63% of fills.** The rebase is a wash on the wide
   universe and a catastrophe on the gapper pool; it is **not** the free money
   the arithmetic promised.

2. **C37F — the live benchmark the entire loop is measured against — is priced
   with NO transaction cost on either side.** `rotation_sim` sets
   `slippage_bps` only for configs that define `cfg["slip"]` (rotation_sim.py
   :1477 and :1512). `C37F` does not; `HOLD1` does. Inverting
   `pnl = (exit·(1−slip) − entry)·shares` straight off the published ledgers
   gives an implied per-side cost of **0.000 bps for C37F-hf2** and **10.07 bps
   for HOLD1-hf2**. The EXPERIMENTS-INDEX header's claim that every honest
   number carries "10 bps/side" is false for the whole C37/C37F family. The
   live benchmark is therefore not −$55/ticket under any toll at all: under the
   measured toll it is **−$246/ticket**.

3. **The gapper pool is not the wide universe, and the 2–6 bps number does not
   transfer to it.** On the 176 REAL inside books the live paper sessions
   logged, the model is **unbiased on the books the live rules would actually
   trade** (median ratio 1.01 over 17 observations, model wider 53% of the
   time) — and those books have a **28.5 bps median full spread**, an order of
   magnitude wider than the wide universe's. Measured on the C37F/HOLD1
   ledgers, the per-side toll is **81–87 bps**, not 10 and not 3.

**The break-even information coefficient moves the wrong way.** At 7 tickets a
day it goes **0.150 → 0.188** under measured costs (0.141 under spread-only).
Achieved ρ is still 0.033. The gap widens from 4.5× to **5.7×**.

---

## Part 0 — The first finding came before any measurement

Before a single basis point was estimated, the identity work turned up
something that changes how every C37* row in this repo should be read.

```
rotation_sim.py:1477    if cfg.get("slip"):
                            kwk["slippage_bps"] = cfg["slip"] * 1e4
rotation_sim.py:1512    if cfg.get("slip"):
                            kw["slippage_bps"] = cfg["slip"] * 1e4
```

`CFGS["C37F"]` has no `slip` key. `CFGS["HOLD1"]` has `slip=0.001`. So C37F
runs at `slippage_bps=None` → `slip = 0.0`, and the only cost it can pay is the
50 bps `pm_spread_bps` premarket haircut — which, under the `RS_CROSS=1` epoch,
it never pays, because no fill can happen before 09:30.

Measured, not inferred. `plan/cr_rot.py --reprice` inverts the engine's own
P&L expression on the two published ledgers:

| ledger | legs | implied per-side exit cost |
|---|---|---|
| `rotation_trades_C37F_hf2.json` | 1,607 | **0.000 bps** (median) |
| `rotation_trades_HOLD1_hf2.json` | 415 | **10.071 bps** (median) |

So the −$55/ticket benchmark, the −$215/day figure quoted in the index, the
whole C37/C37F/MX/T/XH family — all of it is **gross of costs**. HOLD1's
−$182/ticket is the only rotation row that was ever charged anything.

---

## Part 1 — The model (`plan/cr_cost.py`)

### 1.1 What it is made of

The entitled instrument is the same one UNIVERSE-QUOTES found: 1-second
aggregates (`/v3/quotes`, `/v3/trades`, `/v2/last/nbbo` are all 403 on this
tier). `data/massive/trades/{SYM}_{DATE}.json.gz` holds
`[[t_ms, o, h, l, c, v, n], …]` for 09:30–16:05 ET. `n` is the transaction
count in that second, so a second with **n ≥ 2** brackets the inside quote.

For a fill of `$N` in `(symbol, day, minute m)`, from windows that **end
strictly before m**:

```
spread_bps = max( HL2 , CS , AR )
   HL2 = median over the last 5 minutes of the per-minute median
         (high−low)/mid, in bps, of seconds with n >= 2 prints
   CS  = Corwin–Schultz (2012) over the trailing 30 one-minute bars
   AR  = Abdi–Ranaldo (2017) over the same bars
half_spread_bps = max(1.0, spread_bps / 2)

impact_bps = Y · sigma_win_bps · sqrt( N / DV_win )
   DV_win  = trailing 10 minutes of dollar volume
   sigma_win = stdev of 1-minute log returns over the same window,
               scaled to the window's own horizon, in bps
   Y = IMPACT_COEF = 1.0

cost_bps(side) = max(1.0, half_spread_bps + impact_bps)
```

Four judgement calls, all stated rather than buried:

* **`max` of three estimators, not the mean.** The conservative choice; it
  charges drift as spread when the tape is drifting. Part 3 reports the
  spread-only variant so the reader can see the other end.
* **Roll (1984) is computed and reported but excluded from the max.** Its
  median on this data is 18.6 bps — three times every other estimator — which
  is the known high-frequency breakdown of the serial-covariance estimator.
* **Y = 1.0** is the top of the published range for the square-root law
  (Almgren et al. 2005 and the Torre/BARRA line put it at roughly 0.3–1.0).
  The form is horizon-invariant: `sigma_T · sqrt(Q/V_T)` is the same number
  whether T is ten minutes or a day. **The whole ladder Y ∈ {0, 0.3, 0.5, 1.0}
  is reported everywhere**, because the difference between Y = 0 and Y = 1 is
  larger than any edge in this repo.
* **A passive (resting-limit) fill is charged impact only**, not the
  half-spread: it did not cross, it was crossed to. That is the measured
  analogue of UNIVERSE-QUOTES' `passive_bps = 0.0`, and strictly more
  expensive than theirs.

### 1.2 The fallback ladder — conservative where the data is thin

Never returns 0, in this order:

| tier | what it uses | when |
|---|---|---|
| `win` | the trailing 5-minute window | ≥ 2 minutes with an HL2 |
| `wide` | the trailing 30-minute window | otherwise |
| `prior` | the **prior session's** day-median for the same symbol | no usable window today |
| `legacy` | **10.0 bps**, the incumbent assumption | no tape at all |

Tier 4 prices an uncached symbol-day exactly as the project prices it today, so
missing data can never make a name look cheap. Every result below reports its
tier mix.

### 1.3 Extended hours

The tape is 09:30–16:05 only, so nothing outside the regular session is
measured. Outside `[09:30, 16:00)` the model charges
`max(measured, ext_floor_bps)`, where `ext_floor_bps` is **60** for the
wide-net / rl2 / UQ ladder (their `FEE_BPS + EXT_BPS`) and **10** for the
day-trading engine, which pays its 50 bps `pm_spread_bps` haircut separately
and unchanged. An extended-hours fill is therefore **never cheaper** under the
measured model than under the flat one.

### 1.4 The engine hook

`day-trading.py::simulate_trades` gained `cost_model` / `cost_bps_fn`. With the
flag off, `_slip(i)` returns the same float `slip` at all eight call sites.
Nothing else in the repo was edited: `rotation_sim.py`, `vs2_wide.py`,
`plan/rl2/*`, `plan/wn_*.py` and `plan/uq_*.py` are all reached by
import-and-wrap (`plan/cr_engine.py`).

---

## Part 2 — Is it right? Three validations it was not fitted to

### 2.1 The live book (`plan/cr_validate.py --stage live`)

`data/liquidity_truth.json` holds **176 real inside books** logged by the live
paper sessions at known ET minutes (9 days, 35 symbol-days, 146 premarket / 15
post-open); 124 carry both bid and ask. The 1-second tape was fetched for those
symbol-days in **both** sessions (`data/massive/trades_pm` = 04:00–09:30,
`data/massive/trades` = 09:30–16:05) and the model's spread at the same minute
— computed causally, from bars strictly before it — compared to the logged one.

**The split that matters.** The live sessions logged a book either because they
were about to trade it (`PASS + ENTERED`, `ARMED stop-buy`, `clean book`,
`tightest of day`) or because they **refused** it on the 0.5% spread cap
(`veto SPREAD …`). A backtest cost model only ever has to price the first
population.

| group (ledger's own note) | n | median REAL spread | median MODEL | median ratio | model wider |
|---|---|---|---|---|---|
| **tradeable** (armed / entered / clean / tightest) | 17 | **28.5 bps** | **22.5 bps** | **1.01** | 53% |
| vetoed (the 0.5% cap refused it) | 83 | 178.0 bps | 38.1 bps | 0.18 | 6% |
| other | 19 | 64.3 bps | 28.6 bps | 0.65 | 21% |
| all 119 estimable | 119 | 136.6 | 35.1 | 0.27 | 15% |

**Read it as: the model is calibrated where it is used and understates where it
is not.** On books the strategy would trade, the median ratio is 1.01 and the
median absolute error is 6.7 bps — unbiased. On books the live veto refuses, it
understates by 5×, which matters only for a backtest that trades books the live
rules would never touch. Spearman over all 119 is +0.34; Pearson +0.14.

Two limitations, stated: n = 17 in the tradeable group, and 106 of the 119 are
premarket, where the tape is sparse. This is the only true NBBO this project
owns and it is small.

### 2.2 The UNIVERSE-QUOTES estimators

Part 5 of `universe-quotes-audit.md` published six estimator medians on the
same universe. Recomputed here on 15,787 decision points over 50 days
(`plan/cr_out/validate_tape.json`):

| estimator | UNIVERSE-QUOTES median | this line's median | mean | p90 |
|---|---|---|---|---|
| Corwin–Schultz | 2.01 | **1.88** | 4.21 | 9.97 |
| Abdi–Ranaldo | 5.57 | **4.56** | 8.57 | 21.64 |
| observed 1-second range (n ≥ 2) | 1.74 (n≥5) / 4.22 (n≥10) | 0.00 | 1.59 | 4.47 |
| Roll (1984) | 18.59 | 8.14 | 13.94 | 34.92 |
| **this model = max(HL2, CS, AR)** | — | **5.19** | 9.13 | 21.21 |

CS and AR reproduce to within 0.1–1.0 bps; Roll is lower here because it is
computed on 1-minute closes built from the tape itself. The model's spread
median of 5.19 bps ⇒ a **half-spread of 2.6 bps**, squarely inside the audit's
2–6 bps range. The two measurements agree, and the 10 bps/side ladder really is
2–5× the *spread*.

The per-side cost actually charged at those same decision minutes on a $15,000
ticket is **11.0 bps at the median, 20.7 mean, 58.6% above 10 bps** — the
difference being the impact term the incumbent ladder never charged.

### 2.3 What price was available (`--stage tape`, V3)

The question the fill engine asks is "what could you actually get". Decision
minutes were bucketed by the model's predicted half-spread and compared with
the median distance from the mark (last printed close ≤ m−1) to the first print
of minute m:

| predicted half-spread (bps) | observed |mark → first print| (bps) | n |
|---|---|---|
| 0.01 | 4.41 | 1,215 |
| 1.23 | 2.10 | 1,215 |
| 2.49 | 3.01 | 1,215 |
| 3.29 | 3.55 | 1,215 |
| 4.40 | 4.44 | 1,214 |
| 6.00 | 5.64 | 1,215 |
| 8.61 | 7.00 | 1,215 |
| 16.72 | 12.07 | 1,215 |

**Slope 0.577, intercept 2.09 bps, r = 0.958.** The prediction is strongly
monotone in what the tape actually does, sits almost exactly on the diagonal
through the middle of the distribution (4.40 → 4.44, 6.00 → 5.64), and
**over-states at the wide end by ~40%** — the conservative direction. The
lowest bucket is the model's 1 bp floor firing on minutes with no usable
second, where the observed move is larger than predicted; that is the one place
the floor is too low, and it is 12% of rows.

---

## Part 3 — What the measured cost actually IS

`plan/cr_out/cost_decomp.json`, 4,400 fills sampled across the causal wide
universe (tiers: 4,250 `win`, 150 `prior`), $15,000 tickets:

| component | median (bps/side) | mean | p75 | p90 |
|---|---|---|---|---|
| half-spread | **2.77** | 5.85 | 6.72 | 13.95 |
| square-root impact (Y = 1.0) | **9.21** | 19.43 | 18.00 | 42.04 |
| **total** | **12.05** | 25.28 | 25.46 | 52.78 |

**63% of fills cost more than the incumbent 10 bps.** By time of day:

| window | half-spread | impact | total | share above 10 bps |
|---|---|---|---|---|
| 09:30–09:45 | 2.66 | 10.57 | **18.54** | 79% |
| 09:46–10:30 | 5.59 | 10.00 | 16.93 | 76% |
| 10:31–12:30 | 2.45 | 7.86 | 11.00 | 56% |
| 12:31–16:00 | 1.85 | 6.09 | 8.97 | 46% |

And the impact-coefficient ladder, which is the honest range of this whole
study:

| Y | median total bps/side | mean | share above 10 bps |
|---|---|---|---|
| 0.0 (spread only) | **2.66** | 5.89 | 16% |
| 0.3 | 6.30 | 11.88 | 34% |
| 0.5 | 8.15 | 15.87 | 43% |
| **1.0 (headline)** | **12.54** | 25.85 | 65% |

Priced across the whole 208,054-row wide-net cross-section, the aggregate
change against the flat-10 ladder is:

| variant | mean entry cost (bps) | mean $/row vs flat-10 |
|---|---|---|
| spread only (Y = 0) | 12.03 | **+8.85** |
| Y = 0.3 | 15.41 | +0.93 |
| Y = 0.5 | 17.66 | −4.35 |
| **Y = 1.0** | 23.30 | **−17.55** |

**The break-even impact coefficient is Y ≈ 0.33.** Below it the rebase is a
discount, above it a surcharge. Nothing in the literature puts Y that low for a
marketable order; 0.3 is the *bottom* of the published range. So the most
generous defensible reading of the measured evidence is that the incumbent
10 bps ladder is **about right**, not 2–5× too conservative.

---

## Part 4 — Every line, re-priced

Method: eligibility, ticket size and ranking are all cost-invariant
(`notional = min($15k, volcap·Pe)`; `printed`/`ok` are printability tests), so a
cost swap cannot move which rows exist or how big they are. Where a harness's
*path* is also cost-independent the ledger is re-priced exactly and the premise
is proved; where it is not, the harness is re-run with the engine flag on.

**Every flat-10 column below is a reproduction, not a copy.** Four independent
published numbers came back to the digit through this machinery:

| published row | source | reproduced here |
|---|---|---|
| wide-net LightGBM, 1 ticket/day | `widenet-audit.md` −$3.35/tkt | **−$3.35/tkt, 96.7 pct** |
| wide-net break-even ρ, 1/day and 7/day | `wn_need` 0.320 / 0.150 | **0.320 / 0.150** |
| UQ relabelled limit policy | `universe-quotes-audit.md` +$0.06/tkt, +$7/mo | **+$0.06/tkt, +$7/mo, 8/12, 100 pct** |
| RL-SCOUT v2 rules seed 0 | `rl2-audit.md` +$14.11/tkt, +$355/mo | **+$14.11/tkt, +$355/mo** |

### 4.1 The rotation anchors (C37F-hf2, HOLD1-hf2)

Full ledgers, `plan/cr_rot.py --reprice`:

| row | tickets | $/ticket | $/month | months + | ex-best-day | entry cost bps: median / mean / p90 |
|---|---|---|---|---|---|---|
| **C37F-hf2 published (ZERO toll)** | 1,607 | −55.08 | −4,023 | 5/22 | −98,092 | 0 / 0 / 0 |
| C37F-hf2 spread-only (Y=0) | 1,607 | −116.47 | −8,507 | 1/22 | −195,092 | **13.6** / 24.2 / 56.8 |
| C37F-hf2 Y=0.3 | 1,607 | −156.88 | −11,459 | 0/22 | −259,803 | 21.0 / 42.4 / 104.2 |
| **C37F-hf2 measured (Y=1)** | 1,607 | **−246.93** | **−18,037** | 0/22 | −404,012 | 31.9 / 82.1 / 204.4 |
| **HOLD1-hf2 published (10 bps)** | 415 | −180.76 | −3,410 | 7/22 | −80,474 | 10 / 10 / 10 |
| HOLD1-hf2 spread-only | 415 | −198.77 | −3,749 | 6/22 | −87,850 | 11.3 / 22.1 / 51.3 |
| HOLD1-hf2 Y=0.3 | 415 | −249.71 | −4,710 | 5/22 | −108,948 | 21.0 / 42.9 / 96.6 |
| **HOLD1-hf2 measured** | 415 | **−353.59** | −6,670 | 3/22 | −151,990 | 25.7 / 81.7 / 211.2 |

Tier mix on the traded set: 95% `win`, 4% `prior`, 1% `legacy` — the tape covers
the names that actually filled.

**The distribution is violently right-skewed, and that is itself the finding.**
The median gapper fill costs 32 bps a side; the 90th percentile costs 204. The
driver is participation: for the C37F ledger the median fill is 0.8% of the
trailing 10-minute *dollar* volume, but **11% of fills exceed 20% of it**, and
the pool's median 10-minute volatility is **181 bps** against the wide
universe's 61. A $15,000 ticket is a large order in a thin, fast name — which
is exactly what a +10% gapper is.

**Independent corroboration of the spread half.** The spread-only variant's
median entry cost on the C37F fills is **13.57 bps a side ⇒ a 27.1 bps full
spread**. The live paper sessions' real books on names they would actually
trade have a **28.5 bps median full spread** (Part 2.1). Two instruments that
share no code and no data agree to 5% on a population the wide universe's 2–6
bps number misses by a factor of five.

**The path effect, bounded.** C37F's stop and trail levels are struck off
`entry`, which moves when the cost moves, so route A freezes a path that would
in fact shift. `plan/cr_rot.py --subsample --days 40` runs the same 37 traded
days through the engine twice:

| config | label | route A flat | engine flat | route A measured | engine measured |
|---|---|---|---|---|---|
| C37F | year | −17.28 (162 tkt) | −17.30 (162) | −191.24 (162) | −159.00 (148) |
| C37F | y2025 | −19.33 (136) | −19.40 (134) | −192.19 (136) | −267.10 (132) |
| HOLD1 | year | +109.72 (38) | +107.80 (38) | −24.12 (38) | −31.90 (38) |
| HOLD1 | y2025 | −315.57 (37) | −317.80 (37) | −483.83 (37) | −507.80 (37) |

Route A reproduces the engine's flat numbers to ~$2/ticket (cents-rounding in
the dumps). The path effect on C37F is ±$33–75 a ticket with opposite signs on
the two labels — noise on 37 days, and in neither direction does it rescue
anything. HOLD1's ticket count is unchanged in both years, as its
cost-independent path requires.

### 4.2 WIDE-NET (`plan/cr_rerun.py --stage wn`)

Walk-forward LightGBM, held-out year, one $15k ticket at 09:35 and top-k at
every RTH slot, through `wn_oos`'s own `pick` / `random_null` / `summarize`:

| policy | cost | tickets | $/ticket | $/month | months + | random | pct | ex-best | inverted |
|---|---|---|---|---|---|---|---|---|---|
| model, 1/day | flat10 | 251 | −3.35 | −70 | 5/12 | −27.66 | 96.7 | −2,788 | −69.32 |
| model, 1/day | spread-only | 251 | −33.16 | −696 | 5/12 | −36.04 | 46.7 | −10,121 | −100.03 |
| model, 1/day | Y=0.3 | 251 | −48.76 | −1,024 | 3/12 | −47.56 | 36.7 | −14,018 | −121.56 |
| model, 1/day | **measured** | 251 | **−85.15** | **−1,788** | 2/12 | −74.43 | 33.3 | −23,111 | −171.78 |
| **refit on the measured label, 1/day** | measured | 251 | **−26.61** | **−559** | 3/12 | −74.43 | **100.0** | −7,664 | — |
| top-3 all slots | flat10 | 6,759 | −20.73 | −11,721 | 0/12 | −26.38 | 100.0 | −142,210 | |
| top-3 all slots | measured | 6,759 | −56.36 | −31,869 | 0/12 | −42.71 | 0.0 | −382,893 | |
| **refit, top-3** | measured | 6,765 | **−15.08** | −8,536 | 0/12 | −42.68 | **100.0** | −103,400 | |
| refit, top-5 | measured | 11,275 | −15.52 | −14,644 | 0/12 | −42.96 | 100.0 | −176,403 | |
| refit, top-7 | measured | 15,785 | −15.92 | −21,029 | 0/12 | −42.97 | 100.0 | −252,716 | |

Two things are worth reading twice.

* **The incumbent model's percentile collapses (96.7 → 33.3) under measured
  costs.** Not because the toll rose uniformly, but because the model was
  *selecting the expensive names*: re-priced at the measured spread with no
  impact at all, its single ticket still falls from −$3.35 to −$33.16 while the
  unconditional cross-section gets $8.85/row **cheaper**. Part of the wide-net
  model's apparent skill was a liquidity premium it was not being charged for.
* **Refitting on the measured label recovers the relative edge and not the
  absolute one.** The refit model sits at the **100th percentile** against its
  30-seed random control at every k, beating random by $27–28 a ticket — real,
  reproducible skill — and still loses $559–21,029 a month.

### 4.3 RL-SCOUT v2 (`--stage rl2`)

The rl2 harness's path is provably cost-independent (exits compare
`mark / px_in` on raw fill prices, sizing is `notional/px`, the $500 minimum
tests `sh·px`). Proved, not assumed: re-running with the fee tripled moves **0
of 56 legs'** entry/exit minutes or prices. So its ledger is re-priced exactly.

| row | cost | tickets | $/ticket | $/month | months + | random (30 seeds) | pct | ex-best |
|---|---|---|---|---|---|---|---|---|
| rules seed 0 | flat10 | 305 | **+14.11** | +355 | 6/11 | −47.18 ± 9.00 | 100.0 | +2,263 |
| rules seed 0 | spread-only | 305 | −37.98 | −954 | 2/11 | −121.48 ± 8.61 | 100.0 | −13,651 |
| rules seed 0 | **measured** | 305 | **−59.97** | **−1,506** | 2/11 | −129.83 ± 8.51 | 100.0 | −20,351 |

The one apparently-positive row in the whole project goes to −$1,506/month.
Note *why* it is so cost-sensitive: 82 of its 305 held-out tickets exit outside
09:30–16:00 and carry +$6,211 of the +$4,305 total, and extended-hours fills
keep the 60 bps floor under the measured model. Its edge over a rate-matched
random control actually *grows* (+$61 → +$70 a ticket) — the same pattern as
the wide-net refit: skill survives the re-pricing, the level does not.

### 4.4 UNIVERSE-QUOTES' rank-for-the-fill limit policy (`--stage uq`)

The published closest miss of the previous line: the model relabelled on the
limit-fill P&L, posting the top 3 at 10 bps with a 1-minute rest, account-legal
(one position at a time, ≤ 7 tickets a day). Re-run through `uq_relabel` /
`uq_strat` with `uq_econ.price_ticket`'s two cost legs routed through the
measured model — the passive entry charged impact only, the market exit charged
half-spread plus impact.

| row | cost | tickets | $/ticket | $/month | months + | ex-best | random (30 seeds) | pct |
|---|---|---|---|---|---|---|---|---|
| relabelled, limit | flat10 | 1,210 | **+0.06** | **+7** | 8/12 | −1,533 | −15.67 ± 6.71 | **100.0** |
| relabelled, market | flat10 | 1,492 | −17.93 | −2,238 | 3/12 | | | |
| inverted, limit | flat10 | 1,316 | −21.61 | −2,380 | 2/12 | | | |
| **relabelled, limit** | **measured** | 1,210 | **−44.34** | **−4,489** | **0/12** | −55,140 | −40.55 ± 6.41 | **3.3** |
| relabelled, market | measured | 1,492 | −77.29 | −9,647 | 0/12 | −117,287 | | |
| inverted, limit | measured | 1,316 | **−43.25** | −4,762 | 1/12 | −58,721 | | |

Mean measured cost charged: 17.0 bps/side over 163,276 lookups, 48.5% of them
above 10 bps; tiers 99.9% `win`.

**This is the sharpest result in the study.** The UNIVERSE-QUOTES headline was
not merely "+$7/month" — it was "+$15.73 a ticket over a 30-seed random
control, 100th percentile, inverted loses at −$21.61". Under a measured toll
the edge is **−$3.79 a ticket, 3.3rd percentile, and the inverted control
(−$43.25) is statistically indistinguishable from the model (−$44.34)**. The
ranking's apparent skill was, to a first approximation, a *selection of names
whose execution cost the flat ladder under-charged*. It is the same artefact
the wide-net model shows in 4.2, and it is only visible once the cost varies by
name and minute.

Caveat, stated: this is the published policy re-priced, not refit. §4.6 runs
the refit, because §4.2 shows refitting can restore a relative edge.

### 4.5 VS2's closest miss, `W8RSd` (`--stage vs2`)

The green-on-red relative-strength config, re-run through `vs2_wide` with the
engine flag on (the runner is wrapped, not edited: `day_cands` tags each
candidate's sliced frame by identity so the engine call can be given the right
symbol). Nothing else changed — same universe, same clock, same 20%-of-volume
cap, same `pm_spread_bps`.

| label | cost | days | tickets | total | $/ticket | months + | ex-best | maxDD |
|---|---|---|---|---|---|---|---|---|
| wy1 | flat10 (published) | 162 | 162 | +8,094 | **+50.0** | 11 mo | +3,350 | |
| wy2 | flat10 (published) | 177 | 177 | −1,954 | −11.0 | 12 mo | −8,816 | |
| **both** | **flat10** | 339 | 339 | **+6,140** | **+18.1** | **+$267/mo** | −5,466 | |
| wy1 | **measured** | 162 | 162 | −12,382 | **−76.4** | 4/11 | −17,075 | 18,796 |
| wy2 | **measured** | 177 | 177 | −15,417 | **−87.1** | 4/12 | −21,974 | 16,160 |
| **both** | **measured** | 339 | 339 | **−27,799** | **−82.0** | **−$1,209/mo** | | |

Mean measured cost 46.3 bps per side, 68% of evaluations above 10 bps. (Note
the engine evaluates `cost_bps_fn` once per **bar** of the frame, not per fill,
so an engine-run tally is a per-bar distribution; the rotation tallies in 4.1
are per-fill, two per ticket.)

The +$18.1/ticket that made `W8RSd` the video line's closest miss becomes
−$82.0. A green-on-red relative-strength rule *selects for* the thin, fast name
on a weak tape, which is precisely the name whose execution the flat ladder
under-charges. Third instance of the same mechanism.

### 4.6 The UQ policy, refit on the measured label (`--stage uqrefit`)

Symmetry with 4.2: the limit-fill LABEL itself is rebuilt under measured costs
(`uq_label.build` with `uq_econ.price_ticket`'s legs routed through the model),
the ranker refit on it month by month, and the account-legal simulator re-run.
Every artifact is redirected into `plan/cr_out`; not one byte of `plan/uq_out`
is written.

| row | tickets | tkts/day | $/ticket | $/month | months + | random (30 seeds) | edge | pct |
|---|---|---|---|---|---|---|---|---|
| published policy, re-priced | 1,210 | 4.82 | −44.34 | −4,489 | 0/12 | −40.55 ± 6.41 | −3.79 | 3.3 |
| **refit on the measured label** | 941 | 3.75 | **−22.76** | **−1,792** | 3/12 | −40.55 ± 6.41 | **+17.79** | **100.0** |
| refit, market entry | 1,500 | 5.98 | −23.41 | −2,938 | 1/12 | | | |
| refit, inverted | 1,324 | 5.28 | **−85.01** | −9,417 | 1/12 | | | |

Same story as 4.2, told by a different harness: **refitting on the measured
label restores a real, controlled edge — +$17.79 a ticket over 30 random
seeds, 100th percentile, and the inverted control now loses by $62 a ticket
rather than tying — and the level is still −$1,792/month.** The refit also
becomes *more selective* (4.82 → 3.75 tickets a day): given a cost that varies
by name and minute, the ranker declines the expensive fills.

### 4.7 The rotation line's random control

`C37F-R` / `HOLD1-R` — the same machinery, the same gap allowance, the same
costs, only the **pick** is random — do not exist in `rotation_sim.CFGS` (the
auto-generated `-R` siblings are built only for the VS2 and MX families), so
they are injected at runtime by `plan/cr_rot.py`. Ten `ROTREP` replicates over
the matched 40-day window, run twice (flag off, flag on).

| config / label | flat: ranked | flat: random (10 seeds) | measured: ranked | measured: random (10 seeds) | edge, flat → measured |
|---|---|---|---|---|---|
| C37F, year | −17.30 | **+33.21 ± 45.64** | −159.00 | −198.70 ± 56.36 | −50.5 → **+39.7** |
| C37F, y2025 | −19.40 | −41.66 ± 28.32 | −267.10 | −289.25 ± 46.80 | +22.3 → +22.2 |
| HOLD1, year | +107.80 | −11.44 ± 90.29 | −31.90 | −143.62 ± 85.14 | +119.2 → +111.7 |
| HOLD1, y2025 | −317.80 | −342.63 ± 61.41 | −507.80 | −546.61 ± 61.21 | +24.8 → +38.8 |

**And here the mechanism of 4.2 / 4.4 / 4.5 does NOT appear.** The gapper
ranking's edge over a random pick is essentially unchanged by the cost model
(±$10 on a ±$45–90 seed spread; the one large move, C37F-year, goes the *other*
way). So "the ranker was selecting the names the flat toll under-charged" is a
property of the **wide-universe** rankers, not a universal law. On the gapper
pool the measured toll is simply a large, roughly uniform tax that both the
ranked config and its control pay.

Caveat on the control's tier mix, stated because it cuts the wrong way for the
comfortable conclusion: the engine evaluates the cost function once per **bar**
of the 07:00–15:00 frame, so 27% of the control's evaluations land on the
`prior`-session fallback and 6.5% on the flat-10 `legacy` rung — the random
picks reach names whose tape was not fetched. The `legacy` rung is *cheaper*
than a measured gapper fill (10 bps against a 32 bps median), so the control is
flattered, and the ranked config still beats it under measured costs.

### 4.8 Coverage — what was run, and what was not

| line | measured re-run | 30-seed control under measured costs | aug2026 stub |
|---|---|---|---|
| WIDE-NET | yes, + refit | yes (30 / 12 for top-k) | yes: 4 tickets, +$1,497 |
| UNIVERSE-QUOTES | yes, + refit | yes (30) | n/a (its split ends 2026-08-01) |
| RL-SCOUT v2 | yes (exact re-price) | yes (30, rate-matched) | n/a (holdout ends 2026-08-07) |
| VS2 `W8RSd` | yes (engine) | **no** — VS2's own 30-seed `-R`/`-E` controls were never run for `W8RSd` even in the original line (`vs2wide_results_wd.json` has no `#r` keys); only its four deterministic gate-matched controls exist | wy2 label covers it |
| C37F / HOLD1 | ledger re-price (full) + matched 37-day engine subsample | 10 seeds on the 40-day subsample (4.7) | n/a |

The one thing worth flagging as a gap: **`W8RSd` has no random control under
measured costs**, because it never had a 30-seed control under flat costs
either. Its −$82.0/ticket is reported against its own published +$18.1, not
against a null.

---

## Part 5 — The break-even IC, redone with the measured toll

`plan/cr_rerun.py --stage need` runs `wn_need`'s exact machinery — synthetic
score `ρ·z(pnl) + √(1−ρ²)·noise`, buy the top-k per (day, slot), sweep ρ — on
the measured cross-section. Its flat-10 leg reproduces `wn_need`'s published
0.320 and 0.150 exactly, which is what makes the columns comparable.

**ρ needed for $7,500/month:**

| configuration | flat10 | spread-only | Y=0.3 | **measured (Y=1)** |
|---|---|---|---|---|
| 1 ticket a day, any RTH slot | 0.320 | 0.333 | 0.343 | **0.367** |
| 3 a day | 0.207 | 0.208 | 0.218 | 0.243 |
| **7 a day** | **0.150** | 0.141 | 0.155 | **0.188** |

And the curve at k = 7, $/month:

| ρ | flat10 | spread-only | measured |
|---|---|---|---|
| 0.00 | −3,823 | −2,588 | −6,272 |
| 0.05 | −703 | +472 | −3,185 |
| 0.10 | +3,011 | +4,059 | +263 |
| 0.20 | +12,756 | +13,085 | +8,516 |
| 0.50 | +53,352 | +50,562 | +42,855 |

**Achieved ρ on this universe is 0.033.** Under the incumbent ladder the bar
needed 4.5× that; under the measured toll it needs **5.7×**; under the most
generous spread-only reading, 4.3×. Re-baselining the cost model moves the
requirement by **±6–25%** — it does not move it by the factor of four that
would be needed.

**What tickets-per-day would buy.** The curve is close to linear in k at fixed
ρ, so at ρ = 0.033 the measured-cost P&L per slot is negative at every k: more
tickets multiply a negative expectancy. There is no tickets-per-day that
reaches $7,500/month at the achieved IC. To reach the bar at the measured toll
you need either ρ ≈ 0.19 at seven tickets a day, or ρ ≈ 0.10 at roughly 30
tickets a day — which the account rules (one position at a time, ≤ $100k/day)
forbid.

---

## Part 6 — The honesty battery

| check | result |
|---|---|
| **engine identity** — pre-COST-REBASE `day-trading.py` (git `acb2730`) vs the edited one, on the REAL kwargs of C37F / HOLD1 / W8RSd resolved by their own harnesses | **756 symbol-days, 742 legs, 0 mismatches** |
| **engine identity, measured path** — flag ON with a cost function returning each config's own legacy ladder | **756/756 identical** |
| **cross-section identity** — flat-10 re-pricing vs `data/massive/wn/table.npz` | 208,054 rows, worst \|diff\| **$0.000151**, 0 over tolerance (the residual is float32 noise in the cached label; this reconstruction is float64) |
| **published-row reproduction** | wide-net −$3.35/tkt; `wn_need` ρ 0.320 / 0.150; UQ +$0.06/tkt +$7/mo; rl2 +$14.11/tkt +$355/mo — all to the digit |
| **poison P1, future** — destroy every 1-second bar at or after the fill minute | **150 checks, 0 leaks** |
| **poison P2, past** — destroy the bars BEFORE it instead | 150 checks, **148 moved** (the model does read its inputs) |
| **poison P3, engine** — measured path fed the legacy ladder | **160/160 days identical** |
| **poison P4** — P&L monotone in the impact coefficient | PASS (cost sums 1,423 / 5,338 / 13,166 at Y = 0 / 1 / 3) |
| **poison P5** | 340 lookups, 0 non-positive, 0 NaN |
| **estimator identity** — vectorised CS/AR vs `plan/liquidity_estimators.py`'s reference | 318 checks, 0 mismatches, worst **7.1e-15 bps** |
| **estimator identity** — cumulative-sum form vs the scalar form | 2,080 checks, 0 mismatches, worst 3.4e-13 bps |
| **rl2 path-cost-independence** — fee tripled | 56 legs, **0 moved** |
| **the guardrail** — fraction of fills where the measured cost EXCEEDS 10 bps | **63%** (wide universe), **86%** (gapper pool). The change is not one-directional. |
| **tier mix** — how often the model falls back | wide universe 97% `win` / 3% `prior` / 0.02% `legacy`; rotation ledgers 95 / 3 / 2 |

**One thing this line did NOT do**, and it should be said plainly: the full
flag-off C37F rotation pass was started and abandoned after 55 minutes at
50/251 days (18% CPU on a machine running three other research lines).
Identity is therefore proved directly against the pre-edit engine on 756
symbol-days rather than through a 500-day rotation, and `plan/idgate.py --rot`
still asserts the published shard rows, which are unchanged.

---

## Part 7 — Conclusions

### What was established

1. **The toll is measured now, not assumed**, per (symbol, day, minute), from a
   causal trailing window, with a four-tier fallback that never returns zero
   and a poison test that proves it cannot see its own fill bar.
2. **The spread half of the incumbent ladder is 2–5× conservative, exactly as
   UNIVERSE-QUOTES said — and the impact half of the real cost was never
   charged at all.** Median half-spread 2.8 bps; median square-root impact on a
   $15k ticket 9.2 bps; total 12.05 bps/side against an assumed 10. The
   break-even impact coefficient is **Y ≈ 0.33**, below the bottom of the
   published range.
3. **C37F, the live benchmark, pays no toll at all.** Every C37/C37F/MX row in
   this repo is a gross number. Under the measured toll C37F-hf2 is
   −$246/ticket, −$17,994/month.
4. **The gapper pool's real books are 28.5 bps wide at the median on the
   tradeable ones**, ten times the wide universe. The measured toll there is
   81–87 bps a side. The 2–6 bps finding is a property of the
   $2M-ADV/$3-price causal wide universe and does not transfer.
5. **Nothing turns positive.** Every best-of-line row is negative under
   measured costs, and the best is about **−$559/month** (wide-net refit on the
   measured label, 1 ticket/day). Even under the most generous spread-only
   reading, no row clears $500/month.
6. **Skill survives the re-pricing; level does not.** Under measured costs the
   wide-net refit (100th pct, +$27–28/tkt over random at every k), the UQ
   refit (100th pct, +$17.79/tkt, inverted −$85 vs model −$23) and the rl2
   rule (100th pct, +$70/tkt) all still beat their 30-seed controls. The toll
   is not what stands between this project and the bar — it is smaller than
   the deficit by an order of magnitude.
7. **Three of the four wide-universe rankers were partly selecting the names
   the flat toll under-charged; the gapper ranker was not.** WIDE-NET's
   percentile falls 96.7 → 33.3, UQ's 100 → 3.3 (with the inverted control
   tying the model), VS2's `W8RSd` flips +$18.1 → −$82.0 — all while the
   *unconditional* cross-section gets cheaper at Y = 0. The rotation line's
   ranked-vs-random edge, by contrast, is unchanged to within a tenth of a
   seed-spread. A cost model that does not vary by name cannot see this class
   of artefact at all.
8. **The break-even IC moves 0.150 → 0.188 (7 tickets/day), the wrong way.**
   Achieved ρ 0.033. Under the most generous variant it moves to 0.141. The
   factor needed is 4.3–5.7×.

### Closest miss

**The wide-net LightGBM refit on the measured label, one $15,000 ticket a day
at 09:35: −$26.61/ticket over 251 held-out-year tickets, −$559/month, 3 of 12
months positive, 100th percentile against its 30-seed random control
(−$74.43/ticket), ex-best −$7,664.** It needs to be about **$53 a ticket**
better to pass — more than twice the entire measured round trip, so even
abolishing transaction costs entirely would not get there.

Runner-up, and the more interesting of the two because it is account-legal at
3.75 tickets a day: **the UNIVERSE-QUOTES limit policy refit on the measured
label — −$22.76/ticket over 941 tickets, −$1,792/month, 100th percentile,
+$17.79/ticket over 30 random seeds, inverted at −$85.01.**

### Ranked next ideas

1. **Re-price the whole index, then re-read the ladder.** The single most
   valuable thing this line produced is not a strategy — it is the discovery
   that the benchmark is priced at zero and the "conservative" ladder is
   roughly right once impact is charged. Every retraction-ladder row in
   `EXPERIMENTS-INDEX.md` should carry its actual toll in its row, and the
   header's blanket "10 bps/side" claim should be corrected.
2. **Stop treating cost as the binding constraint. It is not, and now that is
   measured rather than argued.** The gap at 7 tickets a day is
   ρ = 0.033 against 0.188. Even setting the toll to **zero**, the wide-net
   refit's gross is far short. The next line should spend its entire budget on
   new *information*, as UNIVERSE-QUOTES' idea #1 already said.
3. **If the gapper line is continued at all, it must be priced.** A config that
   pays nothing is not a benchmark. Adding `slip` to C37F (and re-baselining
   `plan/idgate.py`'s ROT_EXPECT with a dated note) is a half-hour job and it
   changes the sign of several historical comparisons — every ranked-vs-random
   comparison where only one side carried `slip` is suspect.
4. **Trade later in the day, not at 09:35.** The measured toll is 18.5 bps a
   side in the first fifteen minutes and 9.0 after 12:30 — a $28/ticket
   difference on a round trip, which is larger than any per-ticket edge
   measured in this repo. Every model here takes its ticket at the open
   because that is where the features are freshest; the cost of that choice was
   invisible until now.
5. **Buy the impact coefficient rather than assume it.** The whole spread
   between "the rebase is worth +$8.85/row" and "−$17.55/row" is Y. A few
   hundred live $15k marketable orders with recorded arrival mid and fill price
   would pin it down in a month of paper trading, and it is the one number in
   this model that no amount of aggregate data can settle.

---

## Files

| | |
|---|---|
| `plan/cr_cost.py` | the measured model: per-minute statistics, the estimators, the tier ladder, `CostModel` |
| `plan/cr_tape.py` | extends `uq_sec1`'s 1-second cache to the gapper pool; premarket window for the live-book test |
| `plan/cr_validate.py` | the three validations |
| `plan/cr_table.py` | the re-priceable wide-net cross-section + the flat-10 identity |
| `plan/cr_engine.py` | import-and-wrap adapters (rotation_sim, vs2_wide, rl2) |
| `plan/cr_rerun.py` | the re-runs: wn / rl2 / uq / vs2 / rot / need |
| `plan/cr_rot.py` | the rotation ledgers: re-pricing + the matched engine subsample |
| `plan/cr_ident.py` | the engine identity gate against the pre-edit `day-trading.py` |
| `plan/cr_poison.py` | the honesty battery |
| `plan/cr_out/` | every report this document quotes |
| `data/massive/cost1/` | per-(symbol, day) per-minute statistics |
| `data/massive/trades/`, `data/massive/trades_pm/` | the 1-second tape, extended |
