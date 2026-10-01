# LEGACY-14: old-champion components added to R4 on honest data

**Question.** S095/C35, S093/C34, Z104, W109 and the AX/X/S/R series used pieces that C37 and R4 dropped or changed. Do any of them still add money on the honest pool?

**Answer.** **None of the dropped components adds money.** Two retained old components still carry R4:

- the bearish-engulfing exit
- the pressure-modulated trail

One old lead that was never tested, sizing up on entry pressure, is positive in-sample but rests on the tail and loses out of sample.

The larger finding is about R4 itself. On $10k tickets at 15 bps/side, **R4 is +$2,055/month, and its five best legs make +$2,756/month.** The other 960 legs lose **−$701/month**. Almost every component delta below comes down to whether a variant keeps those five legs.

## Frame

- **Engine.** `plan/cp_sim.py` (CHAMPION-REPLAY), which is where R4 is defined.
  - Pick: coil rank as an order. No stop.
  - Fill: at the next printed bar's open after the decision (RS_DEFER-equivalent).
  - Universe: the live-scanner LAST universe, 444 sessions from 2024-10-22 to 2026-07-31.
  - Stops and trail fill gap-through. Halal is ignored.
  - I did not use `rotation_sim`, because R4 does not exist there.
- **Identity check.** `plan/lm14_run.py` job `R4_15k` reproduces the published **965 legs / +$66,760.10** exactly. The extra rules sit in a copy of `_walk_exit` that is byte-equivalent when they are off. `cp_sim.py` is not edited.
- **Tickets and costs.** All rows use flat **$10k tickets**. Cost is **15 bps/side**, the middle of 12–18 for +10% gappers. 22 months; Y1 ends at 2025-08-01.
- **Delta column.** A paired, day-level difference against R4.
- **Caveat.** R4 was chosen on this same sample (coil rank and no stop were picked in-sample). In-sample, every perturbation is biased against the variant, so read small negatives as roughly zero.

## Findings

### 1. Components C37/R4 dropped or never had (each added to R4)

| component (origin) | tkts | $/tkt gross | $/tkt @15 | $/mo @15 | Δ $/mo vs R4 | paired t | Δ Y1 / Y2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **R4 baseline** | 965 | +68.0 | +46.8 | **+2,055** | — | — | — |
| scale-out 1/3 @ +25% (AX06, adopted in AX18) | 965 | +50.2 | +29.0 | +1,273 | −781 | −2.04 | −1,309 / −342 |
| scale-out 1/3 @ +15% | 965 | +50.3 | +29.2 | +1,279 | −776 | −1.73 | −1,426 / −234 |
| scale-out 1/3 @ +50% (S037–S045 "later banking") | 965 | +58.0 | +36.8 | +1,614 | −441 | −1.57 | −791 / −149 |
| scale-out @ +25%, skipped when pressure ≥ +0.3 (C21) | 965 | +62.6 | +41.4 | +1,817 | −238 | −1.25 | −416 / −89 |
| wick guard 3× (X319) | 965 | +68.0 | +46.8 | +2,055 | **0** | — | inert |
| 1 PM exits + 12:30 last entry (C08/X064) | 880 | +57.7 | +35.8 | +1,431 | −624 | −1.65 | −120 / −1,043 |
| strict-noon entry cutoff (C10) | 806 | +59.8 | +37.8 | +1,384 | −670 | −1.36 | +145 / −1,350 |
| time stop 120 min (S033–36 family) | 1718 | +33.1 | +12.9 | +1,005 | −1,050 | −1.87 | −208 / −1,751 |
| exit if underwater after 60 / 120 min | 2086 / 1523 | +23.3 / +40.4 | +3.0 / +19.9 | +282 / +1,379 | −1,773 / −675 | −1.89 / −1.57 | both years − |
| ORB-break stop-buy, armed, re-rank every 5 min (C02 orb5) | 940 | +52.2 | +30.9 | +1,320 | −734 | −0.85 | −647 / −807 |
| ORB-break, armed, 30-min patience (≈ 10:00 stale-pick escape) | 909 | +10.3 | −10.4 | −430 | −2,485 | −2.05 | −3,450 / −1,681 |
| premarket-high stop-buy, re-rank 5 / 30 min (C02 PMH) | 979 / 970 | +35.4 / +13.4 | +13.4 / −8.5 | +595 / −377 | −1,459 / −2,432 | −1.29 / −1.65 | both years − |

How the armed-trigger rows work:

- One name is armed at a time, and the trigger level is known at arm time.
- If it has not triggered after `rearm` minutes, the book re-ranks.
- I did **not** reuse cp_sim's own `orb` mode. When the top name will not trigger within 60 minutes, that mode moves to the second name at the same minute, which is look-ahead.

What happens to the five tail legs:

- **Scale-outs** cut them (MNPR $21.4k → $14.7–16.6k).
- **Armed triggers and patience** miss them (ORB_r30 and PMH_r30 miss MNPR).
- **Earlier exits** lose money even on the very legs they cut. On the 404 legs UW60 cuts, the cuts make −$84.8k versus −$79.9k when R4 holds them to its own exit, so drifters partly recover by 15:00.
- **Removing the re-entry the cut enables** does not save it either. UW60 without re-entry is +$1,092/mo against R4's +$2,055.

The old notes said time stops and early exits amputate the tail, and that still holds.

### 2. Old components R4 still has, removed one at a time

| removed | $/mo @15 | Δ $/mo | t | Δ Y1 / Y2 | body (ex-R4-top-5) $/mo |
|---|---:|---:|---:|---:|---:|
| (none: R4) | +2,055 | — | — | — | −701 |
| bearish-engulfing-while-green exit | −345 | **−2,400** | −1.84 | −2,997 / −1,903 | −1,573 |
| pressure modulation of the trail (C11/X219: 10% when p10 ≤ −0.3, 40% when ≥ +0.3) | −132 | **−2,187** | −1.64 | −4,111 / −584 | −1,223 |
| the trail entirely | +1,400 | −654 | −0.66 | −232 / −1,007 | −369 |
| trail 30% instead of 20% (AX16) | +1,151 | −903 | −0.84 | −1,433 / −462 | −297 |
| 35% gap allowance for the top name (only 20% for all) | +1,690 | −365 | −1.40 | 0 / −669 | −1,066 |
| calm-gap gate entirely (gap7 ≤ 35/20%) | +2,087 | +32 | +0.13 | −170 / +201 | −669 (inert) |

Two exits survive: the bearish-engulfing exit and the pressure-modulated trail. Each is worth about $2.2–2.4k/month, negative to remove in both years, and each helps the body as well as the tail. The calm-gap gate is inert. The plain trail is ambiguous: removing it or widening it improves the body but loses YIBO and ARMP.

**Honesty defect in the surviving exit.** cp_sim and `day-trading.py` both fill the bearish exit at the **close of the pattern bar**, the bar whose close defines the pattern. That breaks cp_sim's own "decision bar's close is never a fill" convention. Filled at the next printed open instead:

- **−$586/month** (t −1.60, both years negative), about −$13/ticket, or about −0.3% per bearish exit.
- **Honest R4 at $10k / 15 bps is +$1,468/month**: Y1 +$2,539, Y2 +$577, body −$1,152/month.

### 3. Ticket schedule, re-entry ladder, front-loading (analysis of `pa_out/cp_r4_legs.json`)

The old C34 finding was that entry #1 is best ($1,204, 71% win) and entries 1–3 are 73% of profit. That justified C35's $25k first ticket. On the honest R4 ledger it is reversed.

| entry # of day | n | mean ret | $/tkt @15 ($10k) | Y1 / Y2 |
|---|---:|---:|---:|---:|
| 1 | 444 | +0.06% | **−24.1** | −68.5 / +10.0 |
| 2 | 279 | +0.80% | +49.5 | +171 / −34 |
| 3 | 136 | +0.99% | +68.9 | +60 / +76 |
| 4 | 71 | +2.78% | +247.8 | +113 / +379 |
| 5–7 | 35 | — | positive, tiny n | — |

- **Random-pick control (30 seeds):** flat at −$26 to −$44 per entry slot, so the gradient comes from R4's path, not from slot position.
- **Capping entries per day** (1 / 2 / 3 / 7): −$487 / +$141 / +$567 / +$2,298 per month. **Do not cap.**
- **Front-loading** (an extra $10k on entry #1) adds 444 × −$24 / 22 = **−$487/month**.
- **Stop-trading-after-a-loss:** after one losing leg, −$476/month; after two, +$2,134 (vs +$2,298 for no stop). The leg after a loser averages +$247, after a winner +$78. There is no hot hand. Days are independent, as the old notes said.
- **Entry hour:**
  - 09:35–10:00: +$31/tkt
  - 10:00–10:30: −$74/tkt in both years (worst slot)
  - 14:00–14:30: −$58/tkt
  - Other hours are positive but the means come from the tail.

### 4. Old lead never tested: entry pressure as a SIZE input (`plan/lm14_press.py`, `lm14_pgate.py`)

Old note: "p_entry ≥ +0.30 averages $751 vs $213–263; never tested as sizing." Bucketing R4's legs by causal pressure30 at the decision minute:

| bucket | n | $/tkt @15 | Y1 / Y2 | ex-top-3 |
|---|---:|---:|---:|---:|
| p30 ≥ +0.30 | 306 | **+147.4** | +267 / +58 | −2.5 |
| 0 ≤ p30 < +0.30 | 227 | −14.4 | −85 / +35 | −73 |
| p30 < 0 | 79 | +55 | mixed | — |
| NaN (thin tape) | 353 | −2.5 | | |

- **As a GATE** (skip the name, take the next coil name): −$2,947/month at a 0.30 threshold and −$2,633/month at 0.15. The **inverted gate also loses** (−$2,006/month). Any change to the pick path loses the tail.
- **As a SIZE** ($20k when p30 ≥ 0.30):
  - In-sample: **+$1,303/month** (Y1 +$1,768 / Y2 +$915, t +1.03). Random 2× sizing on the same 32% of tickets would be expected to add about +$651, so roughly half the gain is real tilt.
  - The gain comes from doubling MNPR, ARMP and SGN. The body gets worse (−$1,072 vs −$701/month).
  - **Out of sample (Aug 2026, 22 sessions):** R4 is **−$4,392** and the sized version is **−$7,885**. Too small to refute, but nothing confirms it.

### 5. Components that can't be tested here, or don't apply

- **Halt-aware stops:** R4 has no stop. Inapplicable.
- **10:00 stale-pick escape:** structurally inert in R4's defer-fill frame, because a pick always fills on the next bar. Its armed-trigger form is priced in table 1 (patience costs about $1.7k/month more than a fast re-rank).
- **Sector tiers:** AX13 was already identical with and without them.
- **News tiers:** no causal news field in the cp frame, and the CATALYST lines own that question.
- **Half-profit compounding:** equal to flat under the $100k cap (old finding).

## TAKEAWAYS

1. **Treat the old exit stack as the reusable asset, filled honestly, and test it off the gapper pool.**
   - Rule: hold long with no stop and no scale-out. Exit when (a) a bar closes as a bearish engulfing while the position is green, selling at the **next bar's open**, or (b) the trail fires: 20% off peak, tightened to 10% when 10-bar signed-volume pressure ≤ −0.3, widened to 40% when ≥ +0.3. Otherwise flatten at 15:00.
   - On R4's entries it is worth about +$2.2–2.4k/month per piece at $10k / 15 bps. Honest R4 with this stack is **+$34/ticket, about +$1,470/month** at 2.1 tickets/day. The body is −$1,150/month and the tail pays for it, so a month without a +40% runner is negative.
   - Test: swap this stack in as the exit of the wide-universe entry lines (CAT R15, RL2, UQ, CM; about 6 bps/side) on their own legs and `m1w` bars. Use a paired day-level delta, Y1/Y2, and the same 30-seed random-entry control with identical exits.
   - Expected: volatility there is about ⅕ of the gappers', so **about +$10–30/ticket**, or **+$100–400/month** at their low ticket rates. Worth one run because it is a pure exit swap with no new prediction.
2. **Pressure as a size tilt, not a gate** (the only never-tested old lead that is positive in-sample).
   - Rule: on the coil-ranked R4 pick, use a $20k ticket when pressure30 at the decision minute is ≥ +0.30, otherwise $10k. Never skip a name on pressure.
   - In-sample: **+$1,303/month at 15 bps (both years +), about +$94 per upsized ticket at about 0.7 upsized tickets/day.** About half of that beats random 2× sizing.
   - It was negative on the 22-session Aug-2026 block and lives on the tail. **Test it only alongside R4 on new sessions** (Sep 2026 onward), against a matched random-upsize control. Adopt it only if the tilt beats random on at least 60 new sessions.
3. **Fix the bearish-exit fill convention everywhere before any further comparison.**
   - Both engines sell at the pattern bar's own close. Moving the fill to the next open costs about −$13/ticket on R4 (−$586/month).
   - Test: add a next-open bearish fill flag to the live paper code's backtest harness, then re-baseline every line that uses the bearish exit. Expect all of them to drop by about 0.3% per bearish exit.

## DISCARD

- **Scale-out ladders** (any trigger from +15 to +50%, with or without the pressure skip): they cut the tail. −$238 to −$781/month.
- **Front-loaded first tickets and entry-count caps:** entry #1 is the worst slot on honest data (−$24/tkt). C35's premise has reversed.
- **10:00 stale-pick escape, ORB/PMH armed stop-buys, waiting on a pick:** patience costs $1.7–2.5k/month. Fill on the next bar, or re-rank.
- **1 PM exits, noon cutoffs, time stops, underwater exits:** −$620 to −$1,770/month. Cutting drifters loses even on the cut legs.
- **Pressure as an entry gate** (either direction).
- **Wick guard 3×, the calm-gap gate:** inert (Δ $0 / +$32).
- **Stop-after-a-loss, daily loss throttles:** the leg after a loss is better than the leg after a win.
- **R4 as a base for stacking components.** Its five best legs are 134% of its P&L, and any rule that changes the pick path loses $2–3k/month in both directions. Its body is negative at 15 bps (−$701/month, or −$1,152 with honest bearish fills), and its Aug-2026 out-of-sample block is −$4.4k.

## Files

- `plan/lm14_legs.py`: ticket-slot, hour, exit-reason and loss-stop analysis of the saved R4 legs.
- `plan/lm14_run.py`: the 23 variant jobs plus the identity check. Batches were `all`, `b2` (retained-component removals) and `b3` (bearish next-open fill).
- `plan/lm14_score.py`: $10k / per-side-bps scorer with paired day-level t.
- `plan/lm14_press.py`, `plan/lm14_pgate.py`: pressure buckets, gate and size tests; `oos` argument for the Aug-2026 block.
- Leg dumps are in the session scratchpad only (not committed).
