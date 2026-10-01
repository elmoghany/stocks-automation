# LEGACY-8: time of day and hold length (2026-10-01)

**Question.** Using only honest data, when do the old champions (C37 / R4 and
the family) make and lose money by entry time and by holding time? Where does a
gapper's post-cross drift happen during the day? Is there a better entry window
or forced-exit time than the champion's (entries until 14:30, flatten at 15:00)?

**Short answer.** No. Time of day and hold length are **not levers** for this
family. Three findings are solid and worth keeping as market knowledge:

1. **Gap-openers fade hard all morning.** A name whose 09:30 bar already
   closes at +10% or more loses −154 bp from 09:31 to 11:00 when it has
   ≥ $10M traded (median −164, t-day −6.8, negative in both years and in the
   OOS block). The fade is done by about 12:00.
2. **The champion's exit stack already absorbs that fade.** Filtering
   gap-openers out of C37F makes it worse, not better.
3. **Gapper afternoons are flat, and the last hour is slightly negative.**
   The CLOSE-MOMENTUM lift does not carry over to gappers.

The one apparent time-of-day edge (late 13:00–14:30 first crossers,
+83 bp/trade) **came from one day, 2025-04-09** (the 13:18 tariff-pause rally).
Without that day it is +0.2 bp gross.

Scripts: `plan/lm8_tod.py` (parts A–D), `plan/lm8_late.py`,
`plan/lm8_gapfade.py`, `plan/lm8_gapfilter.py`. They are read-only on saved
dumps and the `cp_panel` cache. All $ figures are **per $10k ticket**. Costs are
**bps per side**, and the central case for gappers is 15. A cost of 15 per side
is $30 per round trip. A cost of 6 is the liquid-name case.

## Data (honest only)

| source | what | n |
|---|---|---|
| `rotation_trades_C37F_hf3.json` | authoritative engine, live C37 rules, post-09-16 harness (RS_CROSS/RS_DEFER, hygiene, gap-through fills) | 1,839 legs / 440 days |
| `rotation_trades_HOLD1_hf3.json` | same first pick, held to 15:00 | 441 |
| `plan/pa_out/cp_r4_legs.json` R4 | coil rank, no stop, causal universe, next-open fills | 965 / 444 days |
| same file, RND0..29 | 30 random-rank seeds on the same machinery, which isolates the **machinery's** time profile from the ranking | 34,901 |
| `data/massive/cp_panel` | whole gapper tape, 04:00–16:00 minute grid, 466 days (incl. Aug-2026 OOS) | 100,125 RTH crossers |

The crosser definition is causal and complete. A name crosses at the first RTH
minute whose close is ≥ 1.10 × prev_close and ≥ $2 (the live-scanner rule; see
the `cp_lib` docstring). Entry is at the **open of the next printed bar**.
Liquidity means cumulative $ volume at the cross minute, which is known at
that minute.

## A. Old champions' honest legs by entry time and hold

Gross $/ticket ($10k), with net at 15 bps per side in brackets. `t` is
day-clustered.

| entry bucket | C37F-hf3 | HOLD1-hf3 | R4 | RND x30 |
|---|---|---|---|---|
| 09:30–09:35 | **−70 (−100)** n257, ex-top5 −141 | **−150** n256 | n/a (starts 09:35) | n/a |
| 09:35–09:45 | +65 (+35) n145, t+1.3 | +44 n76 | +9 n453 | −15 n13.7k |
| 09:45–10:00 | −7 | +202 n29 | +301 n98 (tail) | −10 |
| 10:00–10:30 | −35 | −427 n44 | −44 | −6 |
| 10:30–11:00 | −2 | | +346 n70 (tail) | −17 |
| 11:00–12:00 | −38, t −2.8 | | +44 | +1 |
| 12:00–13:00 | −32, t −2.1 | | +107 | +9 |
| 13:00–14:00 | +34 | | +293 n58 | −5 |
| 14:00–14:30 | −4 | | −28 | +2 |
| **all** | **−19 (−49)** | **−117 (−147)** | +83 (+53), ex-top5 +0.3 | −9 (−39) |

- **Per-bucket differences are noise except at the very first minutes.** RND,
  with 35k legs, spans only −17 to +9 bp across every bucket. The ranking-free
  machinery has no time-of-day shape. R4's good buckets are each a handful of
  tail legs; its ex-top5 is negative in every bucket except 13:00–14:00
  (+20, n58).
- **The 09:30–09:35 entries are C37's worst bucket** (−70 gross, ex-top5 −141;
  HOLD1 −150). The bucket is also where costs peak: pessimism-audit puts
  impact 5–8 bps per side higher at 09:30–09:32. Dropping only those legs
  moves C37F from −19.0 to about −10.7 gross per ticket. That is still
  negative.
- **Hold length cannot be used as a lever.** C37F legs held 15–30 min earn
  +144, and legs held over 240 min earn −318. RND shows the same: +148 at
  15–30 min and −231 beyond 240. This comes from **selection by the exit
  rule**: the bearish exit fires only in profit (100% win, median hold
  20–30 min), so losers are what is left to reach the 15:00 flatten. Part D
  shows that a causal time stop gains nothing.
- **Ticket order in the day (C37F) does not matter:** ticket 0 is −55,
  tickets 1–6 are −39 to +29, and every t is under 1.8.

## B. Post-cross return profile of gappers (the market, not a strategy)

**All 100k crossers, forward from entry (winsorised 1%, bp):**

| horizon | +5m | +15m | +30m | +60m | +120m | +180m | +300m |
|---|---|---|---|---|---|---|---|
| mean (winsorised) | −11 | −24 | −33 | −41 | −51 | −58 | −58 |
| t (day-clustered) | −9.9 | −12.8 | −13.7 | −13.9 | −13.2 | −11.5 | −8.4 |

**The drift is front-loaded:** about 60% of the 2-hour fade happens in the first
30 minutes after the cross. The liquid subset (≥ $2M at cross) has the same
shape: −27 at 30 minutes and −51 at 120 minutes.

**By cohort (liquid, winsorised mean, entry to 15:59):**

| cohort | to close |
|---|---|
| gap-open (09:30) | −215 bp (median −198) |
| cross 09:31–09:59 | +2 |
| cross 10:00–10:59 | −7 |
| cross 11:00–12:59 | −16 |
| cross 13:00–14:30 | +67, **but see the warning below** |

**Clock-time drift of names already crossed (liquid, last→last, bp):**

| window | drift |
|---|---|
| 10:00–10:30 | −22 (t −4.0) |
| 10:30–11:00 | −16 (t −3.7) |
| 11:00–11:30 | −12 (t −4.1) |
| 11:30–14:30 | between −4 and +9, all \|t\| < 2.2 |
| 14:30–15:00 | −12 |
| 15:00–15:30 | +6 |
| 15:30–15:59 | **−4 (t −3.0)** |

So the morning fade ends by about 11:30, the afternoon is flat, and there is
**no last-half-hour lift in gappers**. CLOSE-MOMENTUM's +3.4 bp was measured on
the wide universe and does not transfer here.

### B1. The gap-open fade (`lm8_gapfade.py`; half-days and 2025-04-09 excluded)

Long from the 09:31 open, in bp. "Day-neg" is the share of days on which the
day-mean is negative.

| subset | n | →10:00 | →11:00 | →12:00 | →15:55 | t-day (→11:00) | Y1 / Y2 / OOS (→11:00) | day-neg |
|---|---|---|---|---|---|---|---|---|
| all gap-openers | 15,006 | −30 | −61 | −57 | −65 | −4.0 | −89 / −42 / −47 | 61% |
| ≥ $2M by 09:30 | 9,219 | −58 | −108 | −112 | −118 | −5.5 | −156 / −83 / −41 | 64% |
| ≥ $10M by 09:30 | 6,072 | −77 | **−154** | −174 | −169 | **−6.8** | −222 / −116 / −55 | 67% |
| liquid, gap ≥ +50% | 1,457 | −147 | −298 | −335 | −440 | −5.1 | −340 / −266 / −186 | 68% |
| liquid, gap 10–20% | 5,144 | −37 | −55 | −50 | −61 | −2.1 | −74 / −49 / +3 | 57% |

- After 12:00 the clock windows for liquid gap-openers are around zero.
- 15:00–15:55 is negative again: −19 bp at ≥ $2M (t −2.8) and −25 bp at
  ≥ $10M (t −2.6).
- A cash account cannot short, so this is **knowledge, not a trade**. Do not
  buy gap-openers on the open and hold them. A dip-buy on them before about
  12:00 is still catching a falling knife.

### B2. The late first-crosser "edge" is one event day (`lm8_late.py`)

Liquid names whose first close at +10% or more prints at 13:00–14:30 earned
**+82.8 bp gross** to 15:55 (n 5,711). That looks like +$53 net per trade, but
the day-clustered t was only +0.55. **2025-04-09 alone contributes 1,516 of the
5,711 names** (tariff pause announced at 13:18 ET). Without that day and the
half-days, the cohort is **+0.2 bp gross / −29.8 net** (n 4,195; Y1 −17,
Y2 +16, OOS −83). Every sub-cut is also ≤ 0 net: cumulative $ volume tiers,
"never touched +10% before", intraday breakouts only, and lagged entry. The
one-a-day version earns +$755/month only because of two months
(2025-05 +$19k, 2026-07 +$35k); it is positive in 8 of 24 months with ex-top5
at −65. The matched control is also negative: an already-crossed liquid name
bought at the same minute returns −53. **Warning:** the "cross 13:00–14:30"
cohort rows in `lm8_tod.py` part B include 2025-04-09 and inherit this
contamination.

## C. Forced flatten time (cp legs re-priced on the panel; entries also stop at T)

| flatten at | 10:00 | 11:00 | 12:00 | 13:00 | 14:00 | 14:30 | **15:00** | 15:30 | 15:59 |
|---|---|---|---|---|---|---|---|---|---|
| R4 gross $/tkt | −28 | +45 | +33 | +65 | +76 | +83 | **+82** | +82 | +79 |
| RND gross $/tkt | −16 | −11 | −12 | −11 | −9 | −9 | **−9** | −10 | −8 |

Any flatten time from 14:00 to 15:59 is equivalent to within ±$5. Flattening
earlier only cuts R4's tail winners. **Keep 15:00.** There is nothing to gain
from holding to the close, and the last-hour gapper drift is slightly negative
in any case.

## D. Causal time stop (legs still open N minutes after entry: value of holding on)

This measures final return minus the mark at entry + N.

- **RND:** between −4 and +11 bp at every N from 15 to 180, whether the leg is
  underwater or in profit, with every |t| < 1.2.
- **R4:** positive at every N (+14 to +86, driven by the tail).

**A time stop adds nothing.** This agrees with the cp ablation, where 30- and
60-minute time stops only multiplied tickets.

## E. Gap-opener filter priced on the honest ledgers (`lm8_gapfilter.py`)

Rule: no gap-opener entries before 11:00. Figures are gross $/tkt; the filter
is approximated by dropping legs, without rotating the freed tickets.

| ledger | all | gap-opener < 11:00 | intraday crosser < 11:00 | KEEP (rule) | KEEP strict |
|---|---|---|---|---|---|
| C37F-hf3 | −19.0 | **+0.2** | −34.4 | −25.4 | −28.1 |
| HOLD1-hf3 | −116.8 | −134.1 | −107.1 | −100.1 | −87.7 |
| R4 | +82.5 | +70.9 | +80.8 | +86.7 | +78.5 |
| RND x30 | −8.8 | −14.4 | −8.6 | −4.2 | −4.6 |

The fade hurts only books that **hold** (HOLD1 improves by about +$29 per
ticket without gap-openers). C37's bearish profit-exit, trail and stop already
harvest the opening wiggles, which is why its gap-opener legs are its *best*
early legs. **For any exit-stack book the filter is neutral to negative.**

## TAKEAWAYS

1. **No entries in the first 5 minutes (09:30–09:34) for the rotation family.**
   - Rule: the first eligible entry is 09:35. The cp_sim lines already do
     this; the live C37 rules do not.
   - Evidence: the C37F-hf3 09:30–09:35 bucket is −$70 gross (−$100 net @15),
     n 257, ex-top5 −141, and HOLD1's same bucket is −150. Pessimism-audit
     shows the first minutes also carry an extra 5–8 bps per side of impact.
   - Expected: about **+$8 gross per ticket on the whole book**, plus about
     $1–2 of cost. At C37F's ~4.2 tickets/day that is roughly +$35/day, or
     **about +$700/month**. The book stays negative (C37F goes from −$49 to
     about −$40 net per ticket at 15 bps).
   - Test: in `rotation_sim`, `C37F` with `ENTRY_START=09:35` under the hf3
     harness flags. Pass only if Y1 and Y2 both improve and the
     30-seed-random control with the same start does not improve equally.
     The day-clustered t of the bucket is only −1.5, so this is a hygiene
     rule, not alpha.
2. **For any HOLD-style or mean-reversion long on gappers (the next research
   line), the earliest entry is 12:00, and gap-openers stay excluded before
   then.**
   - Rule: if the 09:30 bar closed ≥ +10% (≥ $2M traded), the name cannot be
     bought before 12:00. Any MR or hold entry on a crossed name waits until
     after 11:30.
   - Evidence: liquid gap-openers drift −108 bp (≥ $2M) to −154 bp (≥ $10M)
     from 09:31 to 11:00, with t-day −5.5 / −6.8, negative in both years and
     in OOS. Clock drift of crossed names is about 0 after 11:30.
   - Expected: no positive edge by itself. It removes a **−$100 to −$150 per
     ticket structural headwind** from a hold-type entry. HOLD1 improves by
     +$29/tkt with the strict filter, which is roughly +$600/month at
     1 tkt/day. Use it as a guard for the MR line, not as a strategy.
   - Test: add it as a pre-filter in the MR line and require the MR signal's
     edge to survive against an "entry at 12:00, no signal" control, which is
     about 0 bp.
3. **Keep the 15:00 flatten; do not move it to the close and do not add time
   stops.**
   - Rule: unchanged.
   - Evidence: flatten times from 14:00 to 15:59 are within ±$5 per ticket on
     R4 and RND. The last half-hour drift in gappers is −4 bp
     (liquid crossed names, t −3.0) and 15:00–15:55 is −19 bp for liquid
     gap-openers. The value of holding on past N minutes is about 0 (RND,
     35k legs).
   - Expected: $0. It prevents spending future runs on these knobs.

## DISCARD

- **Late-afternoon first-crosser longs (13:00–14:30 breakouts held to the
  close):** the +$53/trade net was a single day, 2025-04-09.
- **Carrying CLOSE-MOMENTUM (15:30→15:59) over to gappers:** the sign flips
  negative.
- **Hold-length or time-stop rules:** the hold-length P&L pattern is
  selection by the profit-only exit. Causal time stops are worth 0 ± 5 bp.
- **Moving the entry window later (10:00/11:00/12:00) for exit-stack books:**
  RND buckets are flat (−17 to +9 bp), R4 loses its tail (R6 = R4 with a
  10:00 start is −$45 net at flat10), and the gap-opener filter makes C37F
  worse.
- **Shorting the gap-open fade:** it is the strongest effect found here
  (−150 to −300 bp by 11:00 on liquid or big gaps), but a cash account cannot
  short. The effect would only be worth revisiting with a margin account and
  a real borrow/locate cost model.
