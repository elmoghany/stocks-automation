# LEGACY-13 — the volatility detector (`up30`): honest long-only uses of a range forecast

**Bottom line.** A good range forecast doesn't make money as an exit,
target, sizing or patience rule on R4's entries. Every exit variant is
neutral or negative in a paired test (same entries, only the exit
changes). What the forecast does predict is **where the cost and the
losers are**. On random picks from the same causal universe, tickets on
high-range names lose and tickets on low-range names roughly break even
or slightly profit. That makes it a usable **negative screen**, not an
alpha source. R4's own profit sits entirely in the high-range tercile
and in a handful of tail legs, so any rule that reshuffles R4's picks
loses money against it.

Scope and honesty: this uses the CHAMPION-REPLAY causal engine
(`cp_sim`: RS_DEFER next-printed-bar fills, gap-through sells, live
scanner `Last>$2, >=+10%` universe, one position at a time). No engine
file was edited; policies are injected by wrapping functions in-process
(`plan/lm13_lib.py`). The window is the 444 in-sample sessions
(2024-10-22..2026-07-31). The **2026-08+ OOS block was left untouched**
and is held for the tests proposed below. Tickets are $10k, capped at
20% of trailing 5-minute volume (average actual notional is about $7.0k).
Thresholds come from the first half of R4's legs (dates before
2025-09-12): sigma1 tercile cuts 0.0086 / 0.0170, median 0.0116, and
quintile cuts 0.0063 / 0.0104 / 0.0157 / 0.0242.

## 0. The forecast at entry: `sigma1` is as good as the ML model

The `up30` walk-forward scores exist only at 09:35 and 10:00, and only
after each fold's 120-session warm-up. They cover **459 of R4's 965
legs**. The model's top feature, `sigma1`, is defined on 862 of them.
`sigma1` is the realised s.d. of the name's 1-minute log returns over
its printed bars up to the decision minute, which makes it causal.

| proxy at decision minute | rho with fwd range (MFE−MAE to 15:00) | rho with leg return | n |
|---|---:|---:|---:|
| `up30` score (forward-filled 09:35/10:00) | **+0.619** | +0.002 | 459 |
| `sigma1` | **+0.606** | +0.020 | 862 |
| prevrange / prior_range / hi_gain | +0.41 / +0.37 / +0.33 | ~+0.03 | 965 |
| dvol_now | −0.20 | +0.085 | 965 |

On the 393 legs that have both, the score reaches 0.645 and `sigma1`
reaches 0.548. Neither predicts direction: rho with the leg's return is
about 0. **One line of code (`sigma1`) carries most of the detector's
value and exists on every leg.** That is why every test below uses it.

## 1. Where R4's money is, by range tercile (baseline: R4 at $10k, 965 legs)

R4 at $10k tickets earns $68.0 per ticket gross, $51.1 net at 12 bps,
**$2,241/month at 12 bps** and −$517/month after removing the top 5 legs,
with 11 of 22 months positive.

| sigma1 tercile | legs | gross $/$10k | median | win% | median fwd range | trail / bearish / flatten exits | R4 actual gross $ (ex-top5) |
|---|---:|---:|---:|---:|---:|---|---:|
| low (≤0.0086) | 287 | −12 | +35 | 66% | 5.7% | 3 / 49 / 48% | −3,510 (−9,796) |
| mid | 288 | −9 | +71 | 59% | 10.1% | 8 / 46 / 46% | +2,001 (−8,936) |
| high (>0.0170) | 287 | **+346** | +50 | 57% | 17.0% | 25 / 38 / 37% | **+67,287 (+6,436)** |
| thin (sigma undefined) | 103 | −133 | −217 | 40% | — | | −121 (−7,633) |

All of R4's $65.7k gross is in the high-range tercile, and 80% of that
comes from 5 legs. Split by half, the high tercile trimmed of its top 3
legs is +$96 per $10k in H1 and **−$63 in H2**. Running the identical
pipeline on the `upc5` direction target is still the right call (see the
CP audit).

## 2. Range-conditioned policies, full sequential re-simulation of R4 (`lm13_policy.py`)

All numbers are at $10k tickets. "$/mo" is net at 12 bps/side; "ex-top5"
is the same figure with the 5 best legs removed.

| policy | tickets | gross $/tkt | net12 $/tkt | $/mo net12 | ex-top5 | H1 / H2 $/mo |
|---|---:|---:|---:|---:|---:|---|
| **R4 base** | 965 | +68.0 | +51.1 | **+2,241** | −517 | +3,315 / +865 |
| skip thin (sigma undefined) | 1023 | +67.6 | +49.1 | +2,281 | −477 | +3,434 / +816 |
| drop low tercile | 1046 | +3.4 | −14.1 | −669 | −2,639 | −1,096 / −142 |
| high tercile only | 1019 | +5.2 | −10.7 | −497 | −2,787 | +1,183 / −2,284 |
| CTRL drop high tercile | 947 | +11.3 | −5.6 | −243 | −845 | −313 / −144 |
| trail = clip(8·σ) (lo ½, hi 2×) | 1261 | +21.4 | +4.5 | +260 | −1,407 | |
| trail = clip(12·σ) | 1078 | +11.8 | −5.2 | −254 | −1,585 | |
| trail = clip(20·σ) | 933 | +19.1 | +2.3 | +96 | −1,235 | |
| trail .30 on high-range names | 916 | +35.7 | +18.9 | +786 | −600 | |
| CTRL trail .30 on all | 890 | +35.0 | +18.1 | +733 | −654 | |
| trail .06 on low-range names | 1094 | +42.4 | +25.4 | +1,265 | −1,343 | +2,576 / −280 |
| full target 3σ / 6σ / 12σ | 1382 / 1122 / 1019 | +26 / +15 / +30 | +9.5 / −1.4 / +13.1 | +598 / −71 / +607 | | |
| CTRL flat target 7% / 14% | 1118 / 1012 | +26 / +23 | +9.1 / +6.4 | +462 / +295 | | |
| patience on high-range names: limit −0.5σ√5 (15 min) / −1σ√5 (15 min) / −1σ√5 (30 min) | 946 / 899 / 899 | +22 / +8 / +20 | | +231 / −365 / +147 | | |
| CTRL patience on ALL names (−1σ√5, 15 min) | 674 | −12.7 | −28.9 | −886 | | |

**Every perturbation of R4 lands between −$886 and +$2,281 a month, and
the base sits at the top.** On the random-pick frame, the s.d. of
$/month across seeds is **$840–1,300** (section 4). One path over 22
months can't tell these rows apart. The pattern is what you would expect
from a selected config whose P&L is five legs: any change to the
sequence loses those legs. Because of that, the exit questions were
settled with paired tests instead.

## 3. Paired exit tests (entries fixed, only the exit changes)

Each cell is the change in gross $ per $10k ticket against the base
exit, with its t-statistic in parentheses.

**On R4's 965 legs (`lm13_paired.py`):**

| exit rule | all | low tercile | high tercile | trimmed ±5 legs, all / H1 / H2 |
|---|---:|---:|---:|---|
| trail clip(8σ / 12σ / 20σ) | −26 / −19 / −16 (t −1.8 / −1.3 / −1.1) | +11 / +3 / +3 | −84 / −63 / −52 | −11 / −11 / −9 |
| trail .30 on high-range names | −5 (−0.5) | 0 | −20 | −2.6 / +2.2 / −8.9 |
| trail .06 on low-range names | +0 (+0.1) | +1 | 0 | +0.6 / −0.5 / +0.7 |
| full target 3σ | −44 (−1.1) | +16 (+0.9) | **−253 (−1.8)** | **+15 / +21 / +39** |
| CTRL flat target 3.5% | −49 | +14 | −263 | +16 / +22 / +43 |
| no bearish-engulf exit on high-range names | +8 (+0.5) | 0 | +30 | −4.4 |

**On 4,579 random-pick legs (seeds 0–3, same exits; `lm13_rnd_paired.py`), date-clustered t:**

| exit rule | all | low | mid | high | H1 / H2 |
|---|---:|---:|---:|---:|---|
| trail clip(12σ) | −16 (−1.7) | −28 | −3 | −17 (−2.0) | −17 / −14 |
| trail .10 on all | −16 (−1.7) | −22 | −8 | −16 | −22 / −11 |
| full target 6σ | +2 | −22 | +3 | **+22 (+2.7)** | −5 / +8 |
| flat target 7% | +6 (+1.0) | −18 | +2 | **+35 (+2.5)** | +8 / +5 |
| no bearish exit (all) | +16 (+1.5) | +16 | +31 | +1 | +11 / +20 |

How to read this:

* **Range-scaled trails lose every time**, on both R4's legs and random
  legs, by $12–26 per ticket. The R-series trail (0.20 base, 0.10/0.40
  pressure tiers) is already wide enough. Scaling it by σ only tightens
  it where tails live.
* **A profit target on high-range names depends on the strategy.** On a
  frame with no right-tail edge (random picks), a flat 7% target on
  high-range names adds +$35 per ticket (t 2.5). On R4's tail-harvesting
  picks the same rule costs −$263 per ticket. It is a "do I have an
  edge?" switch, not a free gain. Even with the target, high-range random
  tickets are still at −$3 to −$19 gross.
* A low-range target (3σ, about 2–2.5%) is +$14–16 on both R4 and random
  legs in the trimmed view, but not significant (t ≤ 1.0).

**Sizing, applied after the fact to R4's legs (shares can only scale down):**

| sizing | gross $/mo | net12 $/mo | net12 per $10k deployed | ex-top5 $/mo |
|---|---:|---:|---:|---:|
| as is | +2,984 | +2,244 | +72.8 | −517 |
| inverse-vol (equal risk): × min(1, 0.0116/σ) | +806 | **+200** | +7.9 | −881 |
| CTRL vol-up: × min(1, σ/0.0116) | +2,991 | +2,403 | +98.1 | −358 |
| half size on the low tercile | +3,064 | +2,456 | +97.0 | −305 |

Equal-risk sizing takes away R4's tail and with it 91% of its money.

## 4. The path-free test of a range gate: 11,570 random-pick legs (10 seeds)

These legs are random picks among eligible names with R4's exits, so
R4's ranking luck is not in them. Figures are gross $ per $10k ticket,
with the date-clustered standard error in parentheses.

| sigma1 bucket at decision | legs | mean (se) | trimmed 1% | median | win% | H1 / H2 | median dvol by decision |
|---|---:|---:|---:|---:|---:|---|---:|
| all | 11,570 | +6 (11) | −19 | +51 | 62% | +1 / +12 | $2.6M |
| thin (sigma undefined) | 315 | **−93 (55)** | −143 | −137 | 40% | −183 / +8 | $16k |
| low ≤0.0086 | 3,940 | **+32 (24)** | +11 | +47 | 71% | +47 / +20 | $14.4M |
| mid | 3,772 | +13 (12) | −1 | +69 | 62% | 0 / +25 | $1.9M |
| high >0.0170 | 3,534 | **−22 (20)** | −55 | +38 | 55% | −25 / −17 | $0.63M |
| Q5 >0.0242 | 1,981 | **−45 (31)** | −86 | +17 | 52% | −76 / −5 | $0.55M |
| `up30` score, top tercile | 1,908 | +48 (32) | **−0.2** | +75 | 59% | +45 / +50 | |

High-range names are worse tickets **and** cost more to trade: they are
the thinnest, with median $0.6M traded by the decision minute against
$14M for the low tercile. In the table below, "tiered" cost means 6, 12
and 18 bps a side for the low, mid and high terciles (18 for thin names).

| frame | tickets per seed | $/tkt at $10k, flat 12 / tiered | $/mo at $10k, flat 12 / tiered (seed s.d.) |
|---|---:|---|---|
| random pick, all | 1,157 | −17.6 / −17.5 | −927 / −922 (1,290) |
| drop thin + Q5 (σ>0.0242) | 928 | −3.2 / −0.1 | −135 / −4 (1,390) |
| drop thin + high tercile | 772 | −0.7 / **+5.4** | −26 / +189 (1,000) |
| low tercile only | 395 | +9.0 / **+21.0** | +162 / +377 (800) |
| CTRL high tercile only | 353 | −45.7 / −57.7 | −734 / −927 (750) |

The monotone pattern holds in both halves for the low and high terciles,
but each bucket is only 1–1.7 se from zero. The screen turns a losing
random frame into a break-even one. It does not create income by itself.

## TAKEAWAYS

1. **Range screen as a cost and loser filter for the next entry line,
   not for R4.**
   *Rule:* never open a ticket when `sigma1` at the decision minute is
   undefined (no two consecutive printed minutes) or above 0.017, which
   is the top tercile of eligible +10% names. The range is measured on
   1-minute closes from the name's first premarket print through the
   decision minute.
   *Mechanism:* high realised range forecasts a wide spread and a thin
   tape, with no directional edge. Random high-range tickets are −$22
   gross (−$58 net at 18 bps), and thin ones are −$93.
   *Expected:* about +$17–23 per ticket against the unscreened frame
   (from −$17.6 to between −$0.7 and +$5.4 per ticket). At about 2.5
   tickets a day that is **+$900–1,200 a month of avoided loss**, at $10k
   tickets.
   *Test:* apply the screen as a pre-filter to the mean-reversion line on
   the untouched 2026-08+ OOS block. Use paired runs with and without the
   screen across 30 random-pick seeds, and compare the seed distributions.
   Don't bolt it onto R4: there it removes the tail that is R4's whole
   P&L (−$243/mo against +$2,241).

2. **Flat profit target on high-range names, but only for a strategy
   without a right-tail edge.**
   *Rule:* if `sigma1 > 0.017` at entry, rest a sell limit at entry
   +7%. A gap through it fills at the open.
   *Evidence:* on random legs, high-range tickets gain **+$35 per ticket
   (t 2.5)**, positive in both halves, while low-range tickets lose $18
   with the same target. On R4's tail picks it costs −$263 per ticket.
   *Expected:* applied to roughly a third of tickets, this is
   +$10–12 per ticket overall, about +$500–650 a month at 2.5 tickets a
   day. There is no extra round trip.
   *Test:* run the same paired exit test (entries fixed) on whichever
   entry rule replaces R4, H1 and H2 separately. If the target hurts in
   that paired test, the entry has a right tail worth keeping, so drop
   the target.

3. **Use `sigma1` instead of the `up30` model wherever a range forecast
   is needed.**
   The two rank forward range about equally on traded legs (rho 0.61 vs
   0.62). `sigma1` is defined every minute (89% of R4's legs; the rest
   are the "thin" names the screen drops), while the model covers only
   48% of legs because it scores just 09:35 and 10:00 and needs a
   120-session warm-up. A model gives no dollar value here, and it adds
   a retraining and leakage surface.

## DISCARD

* **Volatility-scaled trailing stops** (clip(k·σ) for k = 8, 12, 20;
  fixed tight or wide trails by range bucket). Every paired test is −$12
  to −$26 per ticket, on R4's legs and on random legs, in both halves.
* **Equal-risk (inverse-vol) sizing.** R4 drops from $2,244 to $200 a
  month at 12 bps. It removes the tail, which is the only source of
  profit.
* **Entry patience / pullback limits on high-range names.** R4 re-sims
  range from −$365 to +$231 a month against +$2,241; patience on all
  names is −$886.
* **"Trade only high-range names" or ranking by `up30`.** It is a
  lottery: R4's high tercile is +$67k gross but +$6k without its top 5
  legs and negative in H2 when trimmed. Random high-range picks are
  −$22 per ticket gross.
* **Re-simulated gate comparisons on a single R4 path.** The seed-to-seed
  s.d. is $840–1,300 a month, so differences under about $2k a month on
  one 22-month path are noise. Use paired or multi-seed tests.

Side note, outside this brief: dropping the bearish-engulfing exit on
random legs is +$16 per ticket (t 1.5, +$11 in H1 and +$20 in H2) and
+$1 on R4's legs. Weak; worth a look only as part of the TA-exit work.

## Files

`plan/lm13_lib.py` (shared helpers, the $10k ticket, decision-minute
capture), `lm13_explore.py` → `lm13_base_legs.json`, `lm13_diag.py`,
`lm13_policy.py` → `lm13_policy.json`, `lm13_paired.py` →
`lm13_paired.json`, `lm13_rnd.py` → `lm13_rnd_legs.json`,
`lm13_rnd_an.py`, `lm13_rnd_paired.py` → `lm13_rnd_paired.json`,
`lm13_seeds.py`. Total compute is about 15 minutes, one process at a
time, with no data fetched.
