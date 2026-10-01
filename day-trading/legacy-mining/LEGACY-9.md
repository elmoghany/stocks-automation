# LEGACY-9: cost-aware selection (2026-10-01)

**Question.** COST-RESCORE found that the rankers pick expensive names: 31–51 bps/side on entry, against about 6 for a typical fill. Does the gross edge of the old lines (CHAMPION-REPLAY R4, live C37F-hf3, HOLD1-hf3) live in the expensive names, the cheap ones, or both? And can a causal cost filter, or a cost-adjusted ranking, keep the edge and cut the toll?

**Short answer.**
- **There is no edge to keep.** Gating or re-ranking R4 on cost erases its edge. Every cost-aware R4 variant is indistinguishable from a cost-gated random pick (best z = +1.18). Every one is negative once its top 5 legs are removed.
- **The gate itself is real, but it is hygiene, not alpha.** In the random gapper frame, a causal half-spread gate at 10 bps lifts net by **+$31.8 per ticket**:
  - +$17.5 of that is gross, +$14 is cost saved;
  - 29 of 30 seeds improve, and Y1, Y2 and the 22-day OOS all improve.
  - Expensive gappers lose **before** cost. The estimated spread is a negative-gross signal, not only a toll.
- Even gated, random gapper entries still net about **−$4.5 per ticket** at central cost. That is about −$210/month at 2.2 tickets/day.

## Method (all causal, honest harness)

**Estimator.**
- `cp_cost` max(Corwin–Schultz, Abdi–Ranaldo)/2 on the 30 one-minute bars `[em−30, em−1]`.
- `em` is the first print after the decision minute, so bars in `(t, em)` are empty. The estimate uses only data dated ≤ t.
- Same estimator as PESSIMISM-AUDIT's EVID ("upper").

**Cost charged per side.**
- **central:** 0.5·half + 4.4 bps before 10:30, 3.1 after. Max-of-two runs about 2× the median estimator (PESSIMISM-AUDIT 1c).
- **upper (EVID):** 1.0·half + the same 4.4 / 3.1 bps.
- **flat 15:** 15 bps/side.

**Sizing.** $10k tickets. In the engine runs, `cp_sim.TICKETS=[10k]*7`. In the ledger analysis, notional = min($10k, actual), so vol-capped legs stay small.

**Data.**
- R4 + 30 random seeds: `plan/pa_out/cp_r4_legs.json` (444 in-sample days).
- C37F-hf3 and HOLD1-hf3: ledgers with the legacy slip undone, as in COST-RESCORE.
- Engine re-runs: `cp_sim` (gap-through fills, defer trigger, no stop), monkeypatched in-process. The base run reproduces R4 at **+$45.97 per ticket** central.
- Y1 runs to 2025-08-01. Y2 runs 2025-08-01 → 2026-08-01. **OOS** is the 22 days from 2026-08-03 to 2026-09-01, which R4 never saw.

Calibration: R4's mean EVID is 27.4 bps/side. COST-RESCORE / PESSIMISM-AUDIT published 28.75. This analysis's central estimate is 15.5 bps/side, and the mean entry estimate is 27.6 (median 14.4).

## Findings

### 1. Where the gross lives (leg buckets, skip-and-stay-flat)

All figures are $ per $10k ticket.

**R4 legs vs the random control, by entry half-spread quintile:**

| entry half (bps) | R4 n | R4 gross | R4 net central | RND gross | R4 − RND |
|---|---:|---:|---:|---:|---:|
| < 3.9 | 193 | +182 | +170 | +11.8 | +170 |
| 3.9–10 | 172 | −44 | −59 | +7.5 | −51 |
| 10–12 | 214 | +25 | +14 | +2.7 | +22 |
| 12–34 | 193 | −54 | −77 | −10.3 | −44 |
| > 34 | 193 | +224 | +173 | −39.4 | +263 |

- **R4's gross is bimodal.** It sits in the cheapest and the dearest quintiles, and the middle three are flat to negative.
- **R4's expensive half is Y1-only.** For h > 12: Y1 +$2,674/month, Y2 −$575/month. For h ≤ 12: Y1 +$776, Y2 +$1,625.
- On the ledger, h ≤ 8 looks like the "keep the edge, halve the toll" filter:
  - +$73.6 per ticket net central;
  - +$1,121/month;
  - both years positive.
- **But that is a leg-filter mirage.** Its net is +$26.6k in total, its top 5 legs are +$33.9k, and ex-top-5 it is −$7.3k. See point 3.

**The random frame and the live rules lose gross monotonically as cost rises.**
- Random, ungated, in-sample:

  | half (bps) | 0–5 | 5–10 | 10–20 | 20–40 | > 40 |
  |---|---:|---:|---:|---:|---:|
  | gross $/ticket | +6 / +9 | +26 / +1 | −1 / −7 | −31 / +5 | −53 / −31 |

  The two figures are Y1 / Y2. The > 40 bucket is 24% of trades.
- C37F by quintile:

  | quintile | cheapest | 2 | 3 | 4 | dearest |
  |---|---:|---:|---:|---:|---:|
  | gross $/ticket | +11 | −6 | +9 | −38 | −82 |

- So in these frames the expensive names are not "edge we can't afford". **They are losers before cost.**

### 2. Causal gate inside the engine (random frame, 30 seeds, $10k)

Per ticket:

| frame | n/seed | gross | net central | net @15 flat |
|---|---:|---:|---:|---:|
| random, no gate | 1,164 | −10.20 | **−36.33** | −35 |
| random, gate h ≤ 10 | 988 | +7.37 | **−4.52** | −15 |
| Δ | | +17.5 | **+31.8** (29/30 seeds) | |

By period, net central per ticket:

| period | no gate | gate h ≤ 10 |
|---|---:|---:|
| Y1 | −44.4 | +3.1 |
| Y2 | −30.1 | −10.2 |
| OOS | −20.6 | +1.7 |

The gate cuts mean entry cost from about 18.7 to about 9 bps/side central.

**Live C37F-hf3 ledger (approximate: the gated legs are dropped, not replaced):**
- Base: 4.14 tickets/day, gross −$21.0, net central −$52.4 per ticket, **−$4,554/month**.
- h ≤ 10: 1.27 tickets/day, gross +$17.8, net +$3.9 per ticket, **+$104/month**. Y1 −$22, Y2 +$201.
- At flat 15 bps it is −$11.0 per ticket.
- So the gate turns a −$4.5k/month line into about break-even, mostly by not trading.

HOLD1 at h ≤ 10 is +$34.6 per ticket on 130 legs (0.29 a day, +$213/month). The sample is too thin to use.

### 3. Cost-aware R4 inside the engine (a gated name passes its slot to the next coil name)

Per ticket and $/month, in-sample:

| variant | tkt/day | gross | net central | $/month central | Y1 / Y2 $/month | OOS 22d $ | ex-top-5 $/month | z vs gated RND |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| R4, no gate | 2.17 | +68.0 | +46.0 | +2,098 | +3,451 / +1,058 | −4,428 | −750 | +5.10 (vs ungated) |
| gate h ≤ 8 | 2.25 | +27.5 | +14.6 | +692 | +905 / +529 | +1,716 | −763 | +1.18 |
| gate h ≤ 10 | 1.96 | −8.5 | −19.8 | −813 | −1,081 / −606 | +1,269 | −1,702 | −0.79 |
| gate h ≤ 12 / 15 / 20 | ~2.0 | −8 to −9 | −20 to −21 | −823 / −911 / −946 | all negative | +1.0–2.7k | ≈ −1,750 | — |
| rank = cheapest name | 1.81 | +15.7 | +4.9 | +187 | ≈ 0 / + | +452 | −599 | +0.52 |
| rank = cost tier (≤ 5, ≤ 10, rest), then coil | 2.19 | +23.2 | +11.1 | +510 | −1.0 / +22.2 per ticket | +2,880 | −693 | +0.94 |
| one random seed, gate h ≤ 10 (reference) | 2.21 | +25.0 | +12.7 | +586 | | | −100 | — |

Gating reshuffles the day's path:
- At h ≤ 10, the 408 legs it shares with base R4 net +$11.2 per ticket.
- Its 500 replacement legs net −$41.0.
- The base R4's winning cheap legs mostly do not recur, because their timing depended on the expensive trade before them.

Two more signs that the R4 edge was path-specific tail, not something the cost-aware variants inherit:
- The threshold response is non-monotone: +692 at h ≤ 8, then −813 to −946 for h ≤ 10 through 20.
- Every variant is negative ex-top-5.

The OOS gain from gating (+$1–2.9k over 22 days, against −$4.4k ungated) is suggestive but tiny: about 40 legs.

### 4. Liquidity and price are not cost proxies in gappers

- corr(entry half-spread, log trailing-30-minute $ volume) = **−0.02**.
- Mean entry central cost is about 15 bps/side in every dv30 quintile.
- A dv30 ≥ $2M filter on R4 legs keeps +$128 per ticket, but it is the same tail (Y2 +$717/month), not a cost effect.
- R4 by price quintile is non-monotone.
- Use the spread estimator itself, not volume or price.

## TAKEAWAYS

1. **A spread gate on every gapper entry, as hygiene.**
   - **Rule:** before any marketable gapper entry at decision minute t, compute max(CS, AR)/2 on the 30 one-minute bars ending at t (`plan/lm9_feat.half_at`). If it is above 10 bps, skip the name and try the next candidate.
   - **Expected effect at $10k:**
     - **+$32 per ticket** against the ungated rule: +$17.5 gross, +$14 cost.
     - About **+$1,300–1,500/month** of losses avoided at 2–2.2 tickets a day.
     - On C37F-like live rules (the ledger approximation), roughly −$4.5k → about $0/month.
   - **Absolute level:** gated random entries are still about −$4.5 per ticket (about −$200/month). This is a floor-raiser for whatever entry signal is used, not a strategy.
   - **Why it is causal:** wide one-minute CS/AR spreads mark thin, bouncing microcaps. Their bar-open fills are poor and their moves fade: gross −$31 to −$53 per ticket above 40 bps.
   - **How to test:**
     - Monkeypatch the gate into `rotation_sim` for C37F-hf3 and HOLD1-hf3 in-engine, not the ledger drop, plus a 30-seed control.
     - Then check it on paper fills: live quote spread at entry against the estimate.
2. **Price each candidate at its own estimated cost, not a flat bps.**
   - Gated names run about **9 bps/side central** (≈ $12 per round trip at $10k). Ungated R4 runs 15.5 (≈ $22) and random 18.7 (≈ $26).
   - Any new gapper signal should be re-scored as gross − (0.5·half + 3–4.4) per side, leg by leg. A flat 10–15 bps hides the fact that expected gross falls as spread rises.
   - **How to test:** `lm9_ana.py`-style buckets on the new line's legs. Its gross must be positive in the h ≤ 10 bucket in both years.
3. **(Understanding, not a rule.)** In gapper frames, the estimated spread is a **negative-gross predictor**:
   - random, Y1 / Y2 gross per ticket: +$6 / +$9 below 5 bps, against −$53 / −$31 above 40;
   - C37F: monotone, from +$11 down to −$82.
   - Any ranker that drifts toward the wide-spread names (coil, champ, LightGBM at 31 bps) is selecting losers, not just paying more.
   - Candidate check for other lines: does their edge survive with h_e as a control feature?

## DISCARD

- **Cost-adjusted re-ranking of R4.** This covers gates at 8, 10, 12, 15 and 20, rank-by-cheapest, and cost-tier then coil.
  - None beats a cost-gated random pick: z −0.8 to +1.18, percentile 13–87.
  - All are negative ex-top-5, and the response is non-monotone in the threshold.
  - R4's edge is a handful of path-dependent tail legs; gating reshuffles the path and the edge goes.
- **The "R4 h ≤ 8 legs = +$1,121/month, both years" leg-filter number.** It is a skip-and-stay-flat artefact: top 5 legs +$33.9k against a total of +$26.6k. In-engine it is +$692/month at z 1.18.
- **Dollar-volume and price filters as cost proxies in gappers.** They are uncorrelated with the spread estimate (r = −0.02).
- **Selecting the expensive tail in hope of bigger moves.** R4's h > 12 bucket is Y1-only (Y2 −$575/month). In random and C37F frames the dear names lose gross.

## Files

- `plan/lm9_feat.py`: causal per-leg entry-cost features → `plan/lm9_out/feat.json`
- `plan/lm9_ana.py`: bucket and filter tables on R4, RND, C37F and HOLD1 legs → `lm9_out/ana.txt`
- `plan/lm9_sim.py`: in-engine gated R4 + 30-seed controls, $10k → `lm9_out/sim_legs.json` (about 9 minutes)
- `plan/lm9_simana.py`, `plan/lm9_rnd.py`: summaries
- `plan/lm9_cheap.py`, `plan/lm9_cheap_ana.py`: rank-by-cost variants (about 9 minutes)

`plan/lm9_out/` (24 MB) is not committed. To rebuild it, run `lm9_feat` → `lm9_sim` → `lm9_cheap`.
