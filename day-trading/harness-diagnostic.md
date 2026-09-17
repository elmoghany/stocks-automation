# HARNESS-DIAGNOSTIC (2026-09-17)

**The question.** "Why is nothing even close — something is wrong." Two candidates:

- **(A)** the harness / data / cost stack is biased against us, and a real edge is being hidden by the measurement;
- **(B)** the harness is honest, and the same-day, long-only, halal, market-order frame contains almost no harvestable drift.

The way to tell them apart is not another config. It is to push **known positives** — effects the literature says must be there, and things we have independent ground truth for — through the *same* stack and see whether it can find money when money is there.

**Verdict: (B), with one qualification that matters.** Every known positive shows up with the right sign and the right order of magnitude. The harness's own zero-information baseline is **−$0.07 to +$1.24 per ticket at zero cost** across four horizons, i.e. *exactly zero*, and **−$28.6 with the toll on**, i.e. *exactly the toll*. It is not subtracting anything of its own. What is missing is the drift: in this window **100% of the universe's return accrued overnight** (+40.4% cumulative) while the **open→close leg was −10.3% cumulative**, and the frame is only allowed to hold during the negative leg. The qualification: the single constraint hiding the most money is **not** the halal screen (dropping it makes things *worse*) and **not** the long-only rule (worth $0 to a random picker) — it is the **market-order / immediacy assumption**, worth **+$3,190/month**, followed by the same-day rule at **+$1,009…+$1,893/month**.

Files: `plan/hd_lib.py`, `plan/hd_decomp.py`, `plan/hd_recon.py`, `plan/hd_foresight.py`, `plan/hd_intraday.py`, `plan/hd_frame.py`. Outputs in `data/massive/hd/*.json`.

---

## 0. A data finding that makes the whole diagnostic possible

`data/massive/gd/{D}.json.gz` (Polygon grouped daily) carries `o` and `c` for every US ticker. Validated against the minute tape on 789 random symbol-days:

| field | median &#124;difference&#124; vs minute bars | p90 |
|---|---|---|
| gd `o` vs the 09:30 minute-bar **open** | **0.0000%** | 0.0000% |
| gd `c` vs the last RTH minute **close** | 0.0483% | 0.1941% |

gd `o` **is** the regular-session open, to the cent. So the overnight/intraday split and the whole frame ablation can be run on **4,000–5,000 names a day**, halal or not, over all 448 study dates — which no minute-bar cache in this repo covers for the non-halal arm. (gd is split-adjusted, **not** dividend-adjusted, which biases the overnight leg *down* by roughly the dividend yield. Conservative for the claim being made.)

Bar coverage of the causal wide panel: `plan/rl2/out/panel_stats.json` — 27,209 symbol-days, **`no_bars: 0`**. There is no coverage hole to blame.

---

## 1. Overnight vs intraday — the known positive (Lou, Polk & Skouras 2019)

The published result: essentially all of the US equity return accrues close→open; open→close is flat or negative. 448 dates, 2024-10-22 → 2026-08-06, equal-weight, membership read at D−1 so nothing about D enters.

| universe | names/day | **overnight** mean | t (NW) | cum | **intraday** mean | t (NW) | cum |
|---|---:|---:|---:|---:|---:|---:|---:|
| halal_strict (the intraday universe every result in the index uses) | 64 | **+8.32 bp** | +1.46 (+1.48) | **+40.4%** | **−1.02 bp** | −0.13 (−0.15) | **−10.3%** |
| halal_wide | 283 | +5.25 bp | +1.37 | +24.6% | +1.15 bp | +0.22 | +2.5% |
| liquid (no halal screen) | 4,503 | +4.41 bp | +1.34 | +20.5% | +0.32 bp | +0.07 | **−0.6%** |

Per year on halal_strict: overnight Y1 +4.70 bp / Y2 +11.36 bp; intraday Y1 −2.77 bp / Y2 −1.64 bp. **Both years negative intraday.**

And on the index ETFs — including the non-halal replication reference:

| | overnight | t | cum | intraday | t | cum | buy&hold |
|---|---:|---:|---:|---:|---:|---:|---:|
| SPY | +3.95 bp | +1.24 | +18.1% | +2.87 bp | +0.65 | +11.6% | +31.8% |
| SPUS | +5.88 bp | +1.57 | +28.2% | +2.23 bp | +0.45 | +7.9% | +38.4% |
| HLAL | +4.79 bp | +1.40 | +22.4% | +3.44 bp | +0.74 | +14.2% | +39.8% |
| SPSK | +2.42 bp | +2.39 | +11.3% | −2.66 bp | −2.31 | −11.3% | −1.3% |
| SPRE | +7.41 bp | +3.01 | +38.4% | −6.56 bp | −1.52 | −26.8% | +1.3% |
| UMMA | +9.34 bp | +1.77 | +47.6% | +0.28 bp | +0.06 | −1.0% | +46.2% |
| SPWO | +35.50 bp | +6.94 | +375.1% | −26.57 bp | −4.60 | −70.6% | +39.9% |

**Overnight > intraday on 7 of 7 instruments and 3 of 3 universes.** The effect replicates. The stack can see it.

### In dollars — the overnight ticket (OUTSIDE the frame, diagnostic only)

$15,000 ticket bought at the close and sold at the next open, halal_strict universe, 447 pairs:

| hold | gross $/tkt | net @ 10 bps/side | net @ 2.77 bps/side (measured half-spread) | $/month @ 147 tkts, 10 bps |
|---|---:|---:|---:|---:|
| overnight (1 session) | +$12.48 | **−$17.51** | +$4.17 | −$2,574 |
| 3 sessions | +$42.33 | +$12.27 | +$34.00 | +$1,804 |
| 5 sessions | +$72.31 | **+$42.19** | +$63.96 | **+$6,202** |

**Read this carefully.** The 3- and 5-session rows are *capital-infeasible* at 7 tickets a day: 7 × $15k × 5 concurrent days = $525,000 of capital, not $100,000. At the capital the account actually has, a 5-day rotation runs ≈1.4 tickets/day → **+$1,240/month** — which is the equity premium and lands on top of the buy-and-hold row below. The harness is internally coherent; there is no free lunch hiding in the hold length.

The 1-session row is the one that is capital-feasible (7 × $15k = $105k overnight), and it is **negative at 10 bps and positive at the measured half-spread**. The entire overnight drift (8.3 bp) is roughly the size of one round trip at the incumbent toll (20 bp) — which is the whole story of this project in one line.

## 2. Buy-and-hold — is the data even pointed the right way?

$100,000, equal-weight, daily rebalanced onto that day's eligible names:

| | total on $100k | $/month | ann. | max DD |
|---|---:|---:|---:|---:|
| halal_strict | +$22,850 | **+$1,071** | +12.30% | −34.9% |
| halal_wide | +$26,842 | +$1,258 | +14.34% | −26.0% |
| liquid | +$18,743 | +$879 | +10.17% | −22.4% |
| SPY | +$31,756 | +$1,489 | +16.78% | — |
| SPUS | +$38,364 | +$1,798 | +20.04% | — |
| HLAL | +$39,775 | +$1,864 | +20.73% | — |

Positive everywhere. The market rose, the data says so, the universe is not broken. **Note the scale**: the whole equity premium on this account's capital is worth about **$1,100–$1,900/month**. The loop target is **$7,500/month** — 4–7× the market's entire return on the same money, to be extracted from a 6.5-hour window that, in this window, returned *less than nothing*.

## 3. Cost-model reconciliation — is the harness pessimistic vs. the live book?

Every completed round trip in the live paper campaign (20 of them across 19 scored days — 20 is the population, not a sample; the cash account holds one position at a time) re-priced through the harness convention (entry = the OPEN of the live fill minute, exit = the CLOSE of the live exit minute, same share count, flat 10 bps/side + 50 outside RTH).

| | value |
|---|---:|
| live mean P&L / trade | **−$222.13** |
| harness mean P&L / trade | **−$215.32** |
| mean (harness − live) | **+$6.81** |
| median (harness − live) | **+$12.52** |
| 95% bootstrap CI on the mean | **[−$32.44, +$42.52]** |
| fraction of trades where the harness is worse | 9 / 20 (45%) |
| mean gross difference (harness − live, before toll) | +$65.35 |
| mean toll the harness charged | $58.51 |
| mean entry slippage the LIVE book paid vs the bar open | **+$83.31** |

**The harness does not underestimate live P&L — it is marginally generous.** The interval straddles zero; the sign is positive. The reason is visible in the last row: the live campaign's marketable-limit sweeps paid on average **$83 more per entry** than the bar open the harness fills at, and the flat toll does not quite claw that back. Whatever is losing the money, it is not the harness being harsh about fills.

Corroborating measurement from the tape (`plan/cr_out/cost_decomp.json`, 4,400 fills): median **half-spread 2.77 bps**, median total with a conservative square-root impact term at coefficient 1.0 (top of the published range) **12.05 bps**. The incumbent flat 10 bps sits *inside* that, not above it.

## 4. Foresight ladder — the ceiling, and the zero-information floor

Same frame throughout: one position at a time, ≤7 tickets/day, $15,000, 20%-of-trailing-5-minute-volume cap, flat by 15:00, entry at the open of the bar after the decision bar, exit at the close of the bar H minutes later. 448 days, causal wide universe.

| H | **perfect foresight** $/tkt | at 0 bps | $/month @ 7/day | **random** $/tkt (30 seeds) | **random at 0 bps** | anti-foresight |
|---:|---:|---:|---:|---:|---:|---:|
| 5 min | +$322.32 | +$350.75 | +$47,380 | −$28.36 ± 2.60 | **−$0.07** | −$358.15 |
| 10 min | +$352.96 | +$381.20 | +$51,885 | −$28.56 ± 2.12 | **−$0.30** | −$386.34 |
| 30 min | +$399.53 | +$427.27 | +$58,731 | −$28.62 ± 2.40 | **−$0.52** | −$432.03 |
| 60 min | +$510.52 | +$538.26 | +$75,046 | −$26.75 ± 4.13 | **+$1.24** | −$517.10 |

Monotone, as it must be. Two things in this table decide the question:

1. **The zero-information column is zero.** A random long ticket in this universe, held 5 / 10 / 30 / 60 minutes, at no cost, earns −$0.07 / −$0.30 / −$0.52 / +$1.24. The harness is not leaking. There is no phantom drag. (First-principles check: the universe's whole-session open→close drift is −1.02 bp = −$1.53 on a $15k ticket; a 30-minute slice of that is −$0.13, and the seed-mean noise is ±$2.4. Consistent.)
2. **The toll column is the toll.** Random with costs on is −$28.4 to −$28.6, against $30.00 of round-trip fee on a full $15k ticket (slightly less because the volume cap shrinks some tickets). **The entire baseline loss of this frame is the fee, and nothing else.** The harness's published unconditional number of −$33/ticket (RL-SCOUT v2) is this, confirmed independently.

### What the target costs in information terms

- Break-even needs $28.62/ticket of gross edge = **6.70% of perfect 30-minute foresight**.
- $7,500/month at 147 tickets needs $51.02 net = $79.64 gross = **18.64% of perfect 30-minute foresight**.
- The best honest gross edge over a matched random control ever measured in this repo: CLOSE-MOMENTUM +$9.04, UNIVERSE-QUOTES +$14.73…+$26.81, WIDE-NET +$24, VS2 `W8RSd` +$52.8…+$55.3 (not both-years-stable), and this line's own best naive selector +$9.16 → **2.1% – 12.9% of perfect information, clustering at 2–6%.**

So the demonstrated skill of this project is roughly **one third of what it takes to pay the toll**, and roughly **one eighth of what it takes to hit the target**. That is the honest scale of "nothing is even close".

## 5. Supplementary — is "buy the name that's running" the problem?

The live benchmark (C37F-hf2, −$55/ticket) is **worse than this frame's zero-information baseline** (−$28.6). That extra −$26/ticket is neither the harness nor the toll. The +10% gapper pool cannot be used to attribute it (membership is conditioned on the day's own RTH high — "MX-SERIES RETRACTION #2"), so the same instinct was measured on the **causal** universe: 7 sequential tickets/day, 30-minute holds, 448 days.

| selector | $/tkt | $/tkt @ 0 bps | edge vs random | z |
|---|---:|---:|---:|---:|
| `vwap_lo` — furthest **below** VWAP | **−$18.61** | +$9.02 | **+$9.16** | **3.04** |
| `rvol_lo` — lowest relative volume | −$21.33 | −$2.53 | +$6.44 | 2.14 |
| `mom` — most extended above the session open | −$23.09 | +$5.41 | +$4.68 | 1.55 |
| `vwap_hi` | −$23.87 | +$4.42 | +$3.90 | 1.30 |
| `rvol_hi` | −$25.86 | +$4.15 | +$1.91 | 0.63 |
| `rev` — least extended | −$27.12 | +$0.83 | +$0.65 | 0.22 |
| random (30 seeds) | −$27.77 | +$0.28 | — | — |

"Buy strength" is **not** intrinsically bad — inside a causal universe it beats random by +$4.68. The −$26/ticket the live rule gives away is therefore attributable to the **pool**, not to the instinct: the +10% gapper screen selects microcaps whose spread and impact are far above the wide universe's, and whose membership is outcome-conditioned. The best of six naive causal selectors (buy the most beaten-down name relative to VWAP) reaches **+$9.16/ticket of real edge at z = 3.04** — genuine, replicable, and still **$18.61 short of break-even**.

## 6. Frame ablation — which constraint is the money behind?

Same instrument for all rows (the gd open/close grid, so the non-halal arm has full coverage), same twenty simple policies searched under every setting: rank on one of ten strictly-pre-open features, both signs, take the top 7 at $15,000 each at the open, flatten at the stated exit. `gap` is deliberately excluded — a policy that buys at the open cannot have observed the open. The best-of-twenty is an in-sample maximum and is labelled as one; the matched random control is printed beside it so the search premium is visible.

| constraint | **ON** $/month (random) | **OFF** $/month (random) | Δ best | Δ random |
|---|---:|---:|---:|---:|
| same-day only | −$2,432 (−$3,841) | −$1,424 (−$1,948) | **+$1,009** | +$1,893 |
| long-only | −$2,432 (−$3,841) | −$1,553 (−$3,841) | +$880 | **+$0** |
| costs charged | −$2,432 (−$3,841) | **+$1,980** (+$569) | **+$4,412** | +$4,411 |
| market orders (10 bps → 2.77 bps measured half-spread) | −$2,432 (−$3,841) | **+$757** (−$652) | **+$3,190** | +$3,189 |
| halal screen | −$2,432 (−$3,841) | **−$3,141** (−$4,527) | **−$709** | −$686 |

(Also run: halal_wide, the middle universe — −$2,616, i.e. between the two. So the effect is monotone in the screen and points the same way.)

How to read each row:

- **Costs / immediacy dominate.** +$4,412/month from removing costs entirely, +$3,190 from charging the *measured* half-spread instead of the flat 10 bps. And the random control moves by **exactly the same amount** in both rows (+$4,411 / +$3,189) — proving the gain is the fee and not extra edge. This is the constraint the target is hiding behind, and it is the same finding UNIVERSE-QUOTES reached from the 1-second tape (limit fills worth +$2,460/month; measured inside spread 2–6 bps vs the 10 bps ladder).
- **Same-day is second**, and it is *drift*, not *edge*: the best policy gains +$1,009 but a **random** picker gains +$1,893. Holding overnight does not make you smarter, it puts you in the only window that pays.
- **Long-only costs nothing measurable.** The random control moves **$0**, and the best-of-40 beating the best-of-20 by $880 is what searching twice as many policies buys you by luck. There is no evidence the short side is where retail edge lives *in this family*.
- **The halal screen is not the problem — it helps.** Dropping it makes the best policy **$709/month worse** and the random control $686/month worse. This is worth saying plainly because it has been the standing suspicion: the halal universe is 64 names a day against 4,503, and it *still* outperforms. The screen is not what is between this project and the target.
- **Even with costs at zero**, the best of twenty simple policies makes **+$1,980/month** and a random picker makes +$569 — so the whole searchable opportunity in this family, before a basis point is charged, is about **$1,400/month above random, 19% of the target.** Independent confirmation, from a completely different instrument, of CLOSE-MOMENTUM's "3.8× short at zero cost".

---

## Verdict

**(B). The harness is honest; the frame is empty.** Four independent checks say the measurement is not the problem: the harness's zero-information baseline is −$0.07 to +$1.24 per ticket at zero cost and −$28.6 with the toll on, which is the fee and nothing else; re-pricing all 20 live round trips through it lands **+$6.81/trade above** the live book (95% CI [−$32, +$43]), with the live entries paying $83 more than the bar the harness fills at; the bar cache has zero coverage holes on 27,209 symbol-days; and the published overnight/intraday decomposition replicates with the right sign on 7 of 7 ETFs and 3 of 3 universes. What the same data shows is that in 2024-10 → 2026-08 the halal universe returned **+40.4% overnight and −10.3% open-to-close**, and the equity premium on this account's capital is worth about **$1,100/month** — so the frame forbids the only leg that paid and targets 7× the market's entire return on the same money. An honest expectation for the same-day, long-only, halal, market-order frame at 7 × $15,000 tickets/day is **−$4,200/month with no skill (the toll), about −$2,400 to −$2,700/month with the best simple causal rule one can find in-sample, and roughly break-even (±$500/month) in the single best honest result this project has ever produced** (UNIVERSE-QUOTES, +$7/month) — not $7,500. The single constraint that moves it most is **not** the halal screen (relaxing it is worth **−$709/month**, i.e. the screen is helping) and **not** long-only (worth **$0** to a random picker); it is the **market-order / immediacy assumption**, worth **+$3,190/month** on the measured half-spread, followed by the **same-day rule** at **+$1,009/month of policy and +$1,893/month of pure overnight drift**. Stated as information, not as a recommendation: the target is 18.6% of perfect 30-minute foresight, the toll alone is 6.70%, and the best honest edge ever measured here is 2–6% — which is why nothing has been close, and why nothing in this frame will be.
