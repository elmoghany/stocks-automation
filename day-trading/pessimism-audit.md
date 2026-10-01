# PESSIMISM-AUDIT (2026-10-01) — are the results biased TOO BAD?

User, 2026-10-01: *"something is wrong — it is not realistic that everything
loses money."* Every earlier audit hunted biases that made results too GOOD.
This one hunts the opposite: cost and fill conventions that make results too
BAD. Halal ignored per the user's update the same day (each line re-scored on
its own saved universe, no post-hoc halal step).

Known going in: a zero-information random ticket at zero cost is ≈ $0 (the
harness adds no drag); with costs it is ≈ −$28/ticket ≈ the $30 round trip
(10 bps/side on $15k); the best policies beat random by +$17…+$26/ticket
gross. So the whole question is whether the COST and FILL conventions are
pessimistic.

Scope of THIS file (coordinator, 2026-10-01): checks 1 (impact model), 2
(fill-price bias) and 3 (double counting), and the cost estimate below.
Checks 4 (live ground truth) and 5 (re-score) are owned by two parallel
agents and are written up by them.

## Cost model verdict

**Best evidence-based cost for a $15k marketable regular-session fill on the
causal wide universe: CENTRAL 6 bps/side, RANGE 3–10.5 bps/side (mean, which
is what P&L averages). For decisions at 09:30–10:30: CENTRAL 9, RANGE 4.5–15.6.**

| component (mean bps/side) | low | central | high | evidence |
|---|---|---|---|---|
| half-spread, all day | 3.4 | 5.0 | 7.4 | median-of-three CS/AR/HL2 vs production max-of-three (1c) |
| half-spread, 09:30–10:30 | 5.0 | 8.0 | 11.2 | same (1c) |
| impact of the $15k order itself | 0.0 | 1.0 | 3.1 (4.4 at the open) | single ≥ $15k print adds ≈ 0; all ≥ $15k seconds add ≤ 3.1 (1b) |
| minute open/close fill convention | −0.5 | 0.0 | 0.0 | open vs first-10-s VWAP ≈ 0, slight bounce in our favour (2) |
| **total, all day** | **2.9** | **6.0** | **10.5** | |
| **total, 09:30–10:30** | **4.5** | **9.0** | **15.6** | |

Medians are much lower (1–5 bps/side) — the distribution is right-skewed by
thin minutes, so a rule that avoids the widest-spread minutes pays less than
the mean.

**What this says about the conventions in use:**

* **Flat 10 bps/side (most published rows): pessimistic by ≈ 4 bps/side
  (≈ $12 per $15k round trip) on all-day fills in the central case, ~fair for
  09:30–10:30 entries, never more than ~6.5 bps/side too high even at the low
  end.** It is the top of the evidence range, not far outside it.
* **The measured `cr_cost` model at Y = 1 ("measured" columns of COST-REBASE,
  LIMIT-EXEC, CHAMPION-REPLAY, OPEN-UNIVERSE, CATALYST-MINER): strongly
  pessimistic** — it charges 30.8 bps/side mean (14.0 median) on the same
  sample against the evidence's 6 (range 3–10.5): **≈ 20–25 bps/side too
  high at the mean, ≈ $60–75 per round-trip ticket**, almost all of it the
  square-root impact term (23.6 mean charged vs ≤ 3.1 observed) plus the
  max-of-three spread. Every "measured" number in the repo should be read
  as a floor, not a central estimate. The COST-REBASE conclusion "the 10 bps
  ladder is about right, not 2–5× too conservative" rested on Y ≥ 0.33; the
  tape says Y for a single $15k order is ≈ 0–0.13 (3.1 / 23.6).
* **Not covered:** the gapper pool. Its half-spread is several times the wide
  universe's (COST-REBASE: real tradeable gapper books ≈ 28 bps full spread),
  so for gapper lines use the measured half-spread at the fill + ≤ 4 bps
  impact, not the 6 bps central. Extended-hours fills keep their 50–60 bps
  ladder (not tested here).

For the re-score: use **6 bps/side central, 3 optimistic, 10.5
pessimistic** (all-day fills), or **9 / 4.5 / 15.6** where the line's entries
are concentrated at 09:30–10:30; random baseline re-scored at the same level
(zero-cost random ≈ $0 → ≈ −$3 × bps per ticket on $15k).

---

## Check 1 — the square-root impact term (prime suspect)

`plan/pa_impact.py` → `plan/pa_out/impact.json`. Same sample design as
`cr_out/_decomp.py` (cost1 symbol-days, 11 fixed minutes, $15k), 3× larger:
1,200 symbol-days, 13,200 fills.

### 1a. Daily ADV / daily σ instead of the trailing 10-minute window

`impact = Y · σ · sqrt(N / V)` at the same Y = 1.0; daily version uses the
mean prior-20-session dollar volume (gd, v·c) and the stdev of the prior 20
close-to-close log returns, strictly before the trade date.

| | median bps/side | mean | p75 | p90 | share > 5 bps |
|---|---|---|---|---|---|
| impact, 10-min window (production) | 10.00 | 23.63 | 21.03 | 48.52 | 69.8% |
| **impact, daily ADV20 + daily σ20** | **7.08** | **13.60** | 13.72 | 28.08 | **64.3%** |
| half-spread (max of HL2/CS/AR) | 3.23 | 7.13 | 8.12 | 17.11 | |
| total, window | 14.01 | 30.76 | | | (67.7% > 10) |
| total, daily | 12.23 | 20.74 | | | (59.2% > 10) |

Participation: $15k is 2.8% of the trailing 10-minute dollar volume (median;
mean 23%, p90 33%) but under 0.05% of daily ADV at the median (p75 0.1%,
p90 0.3%). By time of day the
window model's impact is 12.8 bps at 09:30–09:45 vs 7.0 after 12:30; the
daily model is flat at 7.1 by construction.

The "horizon-invariant" argument in `cr_cost.py` is right in expectation
(σ_T·sqrt(Q/V_T) is invariant if returns are i.i.d. and volume uniform), and
the data mostly agree: the median ratio σ_1min·√390 / σ_daily is 1.10 (mean
1.34, p90 2.12 — microstructure noise and the opening burst inflate the
window σ). **Switching to the textbook daily inputs cuts the impact by ~30% at
the median and ~42% at the mean, but it does not remove it: 64% of fills still
carry > 5 bps.** The window choice is not the main pessimism. The coefficient
Y — i.e. whether a single $15k marketable order causes square-root impact at
all — is. Hence 1b.

### 1b. Empirical bound from the 1-second tape

300 symbol-days of the wide-universe tape. For each second whose dollar volume
is ≥ $15k vs seconds < $15k in the SAME symbol and minute (38,222 paired
minutes, 226,099 big seconds): signed move from the pre-bar price (previous
printed close) to the last price k seconds later, sign = the bar's tick
direction. The tick-signed move is positive by construction for both groups
(it includes the bounce); the **difference big − small** is the extra move
that comes with ≥ $15k of flow — an upper bound on what a $15k order causes,
since big prints also carry information.

| k | big − small, median | mean (se) | mean, 09:30–10:30 |
|---|---|---|---|
| 1 s | 1.01 | 2.52 (0.07) | 3.97 |
| 5 s | 1.21 | 2.86 (0.07) | |
| 10 s | 1.33 | 3.00 (0.08) | |
| 30 s | 1.37 | 3.15 (0.10) | 4.40 |

**The sharper test: a ≥ $15k second made of ≤ 3 prints** (i.e. close to one
$15k order hitting the book — 36,479 such seconds, ~120 per symbol-day, so the
market absorbs them routinely):

| k | big(≤3 prints) − small, median | mean (se) | mean, 09:30–10:30 |
|---|---|---|---|
| 1 s | −0.15 | −0.20 (0.07) | −0.15 |
| 5 s | −0.24 | −0.52 (0.09) | −0.73 |
| 30 s | −0.50 | −1.02 (0.16) | −1.96 |

A single ≥ $15k print moves the price **no more than a small print does** —
at every horizon, including the open. The +3 bps in the all-big group comes
from bursts of many prints (information / momentum flow), not from size.

**Verdict check 1: PESSIMISTIC.** The production impact term charges 10.0 bps
median / 23.6 bps mean per side; the tape's upper bound on what size adds is
1.4 / 3.1 bps (4.4 at the open) and its single-order estimate is ≈ 0. The
impact term over-charges by **~8.6 bps/side at the median and ~20 bps/side at
the mean (≈ $26–$60 per round-trip ticket)**. This affects every number
priced with `cr_cost` at Y = 1 ("measured" columns of COST-REBASE, LIMIT-EXEC,
CHAMPION-REPLAY, OPEN-UNIVERSE, CATALYST-MINER). It does NOT affect the
flat-10-bps columns, which never charged impact.

### 1c. The other half — the half-spread estimator is also the conservative one

`plan/pa_spread.py` → `pa_out/spread_modes.json` (600 symbol-days × 11
minutes, impact off):

| spread_mode | half-spread median | mean | mean 09:30–10:30 |
|---|---|---|---|
| **max(HL2, CS, AR)** (production) | 3.42 | **7.42** | 11.22 |
| median of the three | 1.00 | 3.36 | 5.04 |
| Corwin–Schultz | 1.22 | 3.67 | 5.70 |
| HL2 (1-second range) | 1.00 | 2.13 | 2.83 |

The max of three noisy estimators is ~2.2× the median-of-three at the mean;
COST-REBASE's own tape check (Part 2.3) found it over-states by ~40% at the
wide end. With no true NBBO for the wide universe (quotes are 403 on this
tier), the honest half-spread range is **3.4–7.4 bps mean** per side.

## Check 2 — fill-price bias (next-minute OPEN entries, minute CLOSE exits)

`plan/pa_fillbias.py` → `pa_out/fillbias.json`. 300 tape symbol-days, 30,616
minutes. Signed so **+ = the convention is optimistic for us** (bought below /
sold above the 10-second VWAP).

| condition | entry: open vs first-10s VWAP, mean (se) | exit: close vs last-10s VWAP, mean | P(open upticks) / P(downticks) vs prev close |
|---|---|---|---|
| all minutes | +0.05 (0.06) | +0.04 | 37.5% / 37.6% |
| prior minute up (momentum buy) | +0.11 (0.08) | +0.01 | 35.4% / **41.3%** |
| prior minute down (reversal buy) | +0.03 (0.10) | +0.03 | 41.1% / 35.3% |
| prior 5-min top decile | **+0.47 (0.34)** | +0.35 | 37.9% / 42.4% |
| 09:31–10:30, prior 5-min top decile | +0.56 (0.64) | +0.54 | 40.2% / 43.8% |

Medians are 0.00 everywhere. There is a mild bid-ask bounce **in our favour**:
after an up minute the next open is a downtick 41% vs uptick 35% of the time,
so the open print a momentum buy is filled at sits slightly more often at the
bid than the ask.

**Verdict check 2: FAIR, if anything slightly OPTIMISTIC** (by ≈ 0.1–0.6
bps/side for momentum entries). The open/close convention is not a source of
pessimism.

## Check 3 — double counting

(Read of every harness; file:line in `day-trading.py`, `rotation_sim.py`,
`cr_cost.py`, `cr_engine.py`, `lx_engine.py`, `wn_*`, `uq_*`, `cp_cost.py`,
`cp_sim.py`, `ou_cost.py`, `cm_lib.py`, `cat_cost.py`, `rl2/sim.py`.)

**No double count found.** `day-trading.py::simulate_trades` `_slip(i)`
(2482) returns either the flat slip or the measured cost, never both, applied
once per leg (entry 2769/3112/3226/3277, exit 3313/3336/3549/3574); the 50 bps
`pm_spread_bps` haircut fires only before 09:30 (2344, 2349).
`rotation_sim.py` passes `slip=0.001` (1533, 1568). `cr_cost.py:602-605`,
`cr_engine.py:184-188`, `cat_cost.py:59-61`, `cp_sim.py:228-232`,
`cp_cost.py:132`, `ou_cost.py:213-217`, `lx_engine.py:795-809`,
`uq_fills.py:92/194/234`, `wn_table.py:106`, `wn_exits.py:71-98`,
`cm_lib.py:88/397/408`, `rl2/sim.py:43/120/154/165`, `hd_lib.py:108`,
`ou_lib.py:132`: one cost per leg, `FEE_BPS` never stacked on a slip, the
extended-hours floor only outside [09:30, 16:00).

Three pessimistic paths that are not double counts:

| path | where | effect |
|---|---|---|
| A. opening-minute impact plug: trailing DV = 0 / σ undefined at 09:30–09:32 → flat 10 bps impact on top of the prior-session half-spread | `cr_cost.py:582-588`, `lx_engine.py:323-334`, `cp_cost.py:127-130` | +5–8 bps/side on 09:30–09:32 fills only (gapper rotation entries at the open) |
| B. hold-to-flatten exits land after hours (m1w panels run to ~19:56) → 60 bps exit at an after-hours price | `rl2/features.py:203-206`, `uq_fills.py:138-141`, `rl2/sim.py:158-165` | ≈ +50 bps on that exit, hold-to-flatten horizon only (already documented, `widenet-audit.md`; best rows use 15–120 min holds) |
| C. volatility charged twice in the measured model: CS/AR absorb intraminute drift that the σ term in impact also charges | `cr_cost.py:527` | ≈ +0.5–1.3 bps/side |

**Verdict check 3: fair for the flat-cost harnesses; the measured model is
pessimistic** (path C ≈ 1 bp everywhere, path A 5–8 bps at 09:30–09:32, on
top of check 1).

## Files

- `plan/pa_impact.py` → `plan/pa_out/impact.json` (check 1a/1b)
- `plan/pa_spread.py` → `plan/pa_out/spread_modes.json` (check 1c)
- `plan/pa_fillbias.py` → `plan/pa_out/fillbias.json` (check 2)
