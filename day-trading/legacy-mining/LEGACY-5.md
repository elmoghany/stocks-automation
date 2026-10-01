# LEGACY-5: ticket sequence and rotation (why ticket #1 loses)

**Question.** In R4 (coil rank, no stop, 09:35 start, one position at a time, rotation), ticket #1 loses money at gapper cost while tickets #2 and later carry the profit. Is that because of the time of day, because later picks have proven themselves (selection), or because of how the previous trade turned out?

**Short answer.** It is none of the three as asked. The variable that matters is **how long the name has been on the scanner** at the moment we buy. Ticket #1 is always the 09:36 entry, and a third of those #1 tickets go into a name that was already on the scanner at the open (an opening gapper). Those legs average −127 gross per $10k. Later tickets do well only when their name crossed the scanner more than 10 minutes before entry. The rule "only trade after a win" has the wrong sign, and "start at 10:00" fixes the wrong variable.

**Major caveat up front.** R4 itself depends on a handful of trades. Without its best 5 legs it makes **−$1,347/month** at 15 bps/side, and 2026 nets about −$8 per $10k ticket. Every rule below changes how a lottery behaves. None of them creates a base edge.

## Data and method (honest, nothing new simulated)

- **Inputs:**
  - `plan/pa_out/cp_r4_legs.json`: R4, 965 legs over 444 sessions (2024-10-22 to 2026), plus 30 random-pick seeds in the same frame. This is the post-retraction cp_sim: next-printed-bar open fills, gap-through stop fills, causal LAST-scanner universe.
  - `plan/crs_cp_r5_legs.json`: R5, which uses coil rank, a 10:00 start and a −2% stop, plus 30 random seeds. It serves as a replication where the clock is controlled.
  - The `data/massive/cp_feat` cache, used to get each name's first eligible grid minute (5-minute grid) for "minutes since cross".
- **P&L units.** All P&L is scaled to a **$10k ticket**: gross × 10,000 / notional. The cost is **15 bps/side, i.e. $30 per round trip** (gapper central). Columns at 6, 12 and 18 bps/side are given where useful. $/month = sum / 444 days × 21.
- **Shadow rules (the key to keeping this causal without re-simulating).** A skipped ticket is still "taken" as a *virtual* position. The engine's sequence, timing and budget stay exactly as in the dump, and only the kept legs earn money. Dropping a leg from the dump is therefore an exact, implementable evaluation: the live bot tracks a paper position instead of a real one.
- **Scripts:**
  - `plan/lm5_seq.py`: ordinal, clock, prior result and shadow rules.
  - `plan/lm5_seq2.py`: minutes since cross, compared with random and with the R5 replication.
  - `plan/lm5_seq3.py`: threshold sweep and tail-robust $/month.

## Findings

### 1. By ordinal: R4 compared with a random pick in the same frame (gross / net@15, $ per $10k ticket)

| ticket | R4 n | R4 gross | R4 net@15 | R4 net $/mo | RND gross |
|---|---:|---:|---:|---:|---:|
| #1 | 444 | +5.9 | −24.1 | −507 | −13.8 |
| #2 | 279 | +79.6 | +49.6 | +655 | −12.0 |
| #3 | 136 | +99.0 | +69.0 | +444 | +4.1 |
| #4 | 71 | +278.2 | +248.2 | +833 | −7.6 |
| #5+ | 35 | +616.3 | +586.3 | +971 | −2.3 |

- **Random picks show no ordinal gradient** (−14, −12, +4, −8, −2). So "later" in itself is not an edge. The gradient exists only under the coil rank, which makes it a selection × context effect.
- **The #2+ profit sits in the tail.** Excluding the top 5 legs, the #2+ mean is **+9 gross** (median +36), which is −21 net. The top legs are YIBO at +287%, MNPR at +214%, FLYE at +120% (a #1), ARMP and HUIZ.
- **R5, which starts at 10:00, kills the "ordinal" story:** #1 −31.4 against #2 −32.3 against #3+ −15.5 gross. Once #1 is no longer the 09:36 leg, it stops being special.

### 2. Clock: not the causal variable

- R4 entries by time window, ticket #2 and later only (#1 is always 09:36):

  | window | gross per $10k |
  |---|---:|
  | 09:45–10:00 | +301 |
  | 10:00–10:30 | **−44** |
  | 10:30–11:00 | +346 |
  | 11:00–12:00 | +44 |
  | 12:00+ | +145 |

  This does not trend with time of day.
- "Shadow until 10:00" gives +$1,587/month, which is **worse** than R4 as-is at +$2,397/month. It throws away the strong 09:45–10:00 #2 legs.
- The champion audit's real re-simulated version (R6: coil + 10:00 start + no stop) is −27 gross per ticket. Moving the start to 10:00 changes which names get picked, and the result is worse.
- **Within each clock bucket, the minutes since cross separates winners from losers** (R4, ticket #2 and later):

| entry window | since ≤10 min | since >10 min |
|---|---:|---:|
| before 10:00 | −38.5 (n=56) | **+650.9** (n=51) |
| 10–11 | −92.5 (n=66) | **+226.4** (n=113) |
| 11:00 and later | +53.2 (n=46) | **+127.2** (n=189) |

### 3. Prior-trade outcome: wrong sign for "only after a win"

| R4, ticket #2 and later | n | gross | net@15 $/mo | RND gross |
|---|---:|---:|---:|---:|
| previous leg WON | 399 | +108 | +1,478 | −3.1 |
| previous leg LOST | 122 | +277 | +1,425 | −16.0 |
| #1 won → later legs | 363 | +98 | +1,174 | −1.3 |
| #1 lost → later legs | 158 | +262 | +1,730 | −18.8 |

Legs after a loss are *better*, but the gap comes from tail legs, and the random picks show the reverse small tilt. Read it as no usable signal. "Live only after #1 wins" gives +$1,174/month against +$2,397/month for R4 as-is, so it throws money away. This agrees with the old NOTES finding that a losing first trade does not spoil the day.

### 4. Minutes since cross (the variable that matters)

| slice | n | R4 gross | R4 ex-top-5 | R4 boot95 gross | RND gross |
|---|---:|---:|---:|---|---:|
| since ≤10 min | 612 | −5.2 | −65 | [−87, +78] | −14.5 |
| since >10 min | 353 | **+234.7** | **+31** | **[+51, +479]** | −6.9 / −8.0 / +2.2 (by bucket) |
| #1 on the scanner already at 9:30 (opening gapper) | 133 | **−127.4** | −242 | [−299, +46] | −20.2 |
| #1 crossed after 9:30 | 311 | +62.9 | −48 | [−59, +197] | −4.9 |
| #2+ since ≤10 | 168 | −34.6 | −116 | [−136, +68] | — |
| #2+ since >10 | 353 | +234.7 | +31 (trimmed both ends: +53) | [+48, +476] | — |

- The **mechanism** that fits the data: a coil rank (closest to the session high) applied to a name that *just* crossed buys the top of the initial spike.
  - Fresh legs are held longer (median 130 minutes against 79), meaning they bleed until the flatten.
  - The same coil applied to a name that crossed 10 or more minutes ago and is *still* pressing the high buys a name that has held its gain. That works like a consolidation breakout.
- **The random control shows a smaller version of the same effect** (fresh −14.5 against older −7 to +2 gross). The coil rank amplifies it.
- **R5 replication** (different clock and different stop): the fresh-cross legs are **−56 gross, boot95 [−88, −19]**, which excludes zero. R5's older legs are about −17 ex-top-5. The direction holds. R5 is still negative overall.

### 5. Shadow-rule results (R4 sequence untouched)

| rule | n | gross /$10k | net@15 /$10k | net@15 $/mo | ex-top-5 $/mo | months+ | H1 / H2 net@15 |
|---|---:|---:|---:|---:|---:|---:|---|
| R4 as-is | 965 | +82.5 | +52.5 | +2,397 | −1,347 | 13/22 | +86 / +18 |
| skip ticket #1 | 521 | +147.8 | +117.8 | +2,903 | — | 12/22 | +215 / +16 |
| shadow until 10:00 | 414 | +111.1 | +81.1 | +1,587 | — | 12/22 | +135 / +20 |
| live only after #1 won | 363 | +98.4 | +68.4 | +1,174 | — | 12/22 | +130 / +14 |
| skip #1 if it was on the scanner at 9:30 | 832 | +116.1 | +86.1 | +3,387 | — | 13/22 | +130 / +40 |
| **skip since-cross ≤10 min** | 353 | **+234.7** | **+204.7** | **+3,417** | **+10** | 13/22 | +338 / +68 |

- **Threshold sweep for the since-cross rule (R4):**

  | threshold T | net@15 $/mo | ex-top-5 $/mo |
  |---|---:|---:|
  | 5 min | +2,270 | −1,201 |
  | **10 min** | **+3,417** | **+10** |
  | **15 min** | **+3,492** | **+85** |
  | **20 min** | **+3,346** | **−61** |
  | 30 min | +1,855 | −314 |
  | 60 min | +1,497 | −346 |

  The plateau is 10–20 minutes, so the result is not a knife-edge. By year, net@15 per $10k: 2024 +768, 2025 +189, 2026 +10. It stays positive every year, but 2026 is close to zero.
- **R5 sweep** (dropped-leg gross per $10k): T=5 −83, T=10 −56, T=20 −49. Monthly loss: −$5,280 → −$2,273 at T=10 and −$1,535 at T=20.
- **Where the gain comes from.** At T=10 the R4 legs that get dropped average −5.2 gross. About 85% of the +$1,020/month improvement is **avoided cost**: 612 legs with roughly zero gross edge, each paying $30. The rest is avoided losses. Avoiding costs this way is real money and fully causal.

## TAKEAWAYS

### 1. Scanner-age gate (the main idea)

**Rule:** do not buy a name whose first scanner appearance (`elig_last`, i.e. LAST ≥ cross threshold) was **10 minutes or less before** the decision minute. Track a skipped ticket as a shadow position so that the rotation timing stays the same, or just filter it out of the candidate list.

**Expected value at $10k tickets, 15 bps/side:**

| version | trades/day | net per trade | $/month |
|---|---:|---:|---:|
| as-observed (shadow, R4) | 0.8 | about +$205 | about +$3,400 |
| tail-robust: drop the top and bottom 5 legs | 0.8 | about +$23 | about +$400 |
| ex-top-5 legs only | 0.8 | — | about $0 |

The certain part is about **+$870/month in costs no longer paid**, compared with R4 as-is.

**How to test** (one cp_sim run when the box is free):
1. Add the gate inside the eligibility mask (`since_cross > 10`). That is a *real* re-simulation in which later picks can change, which the shadow version above does not do.
2. Run it against the same-frame 30-seed random control with the same gate.
3. Repeat on `cp_run.dates(oos=True)`.
4. Report both the as-observed and the ex-top-5 $/month.

**Pass condition:** better than the random gate at the 90th percentile or above, ex-top-5 ≥ 0, and positive in both halves.

### 2. Never take the 09:36 ticket on an opening gapper

**Rule:** if the top-ranked name at 09:35 was already on the scanner at 09:30 (`first eligible grid == 09:30`), skip it or shadow it.

**Numbers:**
- R4: 133 legs (0.3/day) at −127 gross / −157 net, so skipping them adds about **+$990/month**.
- The random control shows the same sign (−20 against −5 gross).
- The bootstrap confidence interval crosses zero ([−299, +46]), and the rule is fully contained in Takeaway 1.

**Use:** treat it as the cheapest version of Takeaway 1, to run if the live code can only change ticket #1. Test it the same way.

### 3. Use "minutes since first scanner appearance" as a feature in the new line

**Idea:** add this as a standard causal feature for the mean-reversion / TA-exit research. In both engines, a name that is fresh to the scanner and sitting at the high of day is a spike top:
- R5 fresh legs: −56 gross, CI excludes zero.
- Random-pick fresh legs: about −8 gross worse than older ones.

**What it suggests:** this is where a *short* or fade setup would look, and where *long* entries should stay out.

**How to test:** use it as a bucketed feature in the existing bucket studies (lm12-style). Check whether the sign holds across the 10-, 20- and 30-minute buckets and in both halves.

## DISCARD

- **Ordinal rules:** "skip the first signal" and "ticket #1 is bad". This is an artifact. #1 is simply the 09:36 opening-spike leg, and in R5 (10:00 start) #1 ≈ #2. Also drop **ordinal sizing**: C35's "front-load $25k into entry #1" puts the most money on the worst ticket.
- **Clock gates:** "start at 10:00". The time of day is not the variable. The shadow version earns less than R4 as-is, and the re-simulated R6 is −27 gross per ticket.
- **Prior-result gates:** "only after a win", "stand down after a loss", day-so-far circuit breakers. The sign is the opposite of the intuition or is noise, and random picks show nothing.
- **Reading R4's #3+ numbers (+$226/ticket) as an edge.** Excluding the top 5 legs, all of #2+ is +9 gross.

## Files

- `C:\cornell\stocks-automation\day-trading\legacy-mining\LEGACY-5.md` (this file)
- `C:\cornell\stocks-automation\day-trading\plan\lm5_seq.py`, `lm5_seq2.py`, `lm5_seq3.py`. They read saved dumps and the cp_feat cache only, write output to the scratchpad, and each takes about 1–3 minutes.
