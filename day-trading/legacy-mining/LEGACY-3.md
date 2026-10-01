# LEGACY-3 — entry triggers of the old champions, on honest data (2026-10-01)

**Question.** C37 and its predecessors entered on a 5-bar "ORB" break, a
premarket-high (PMH) stop-buy, and eight reversal-candle / indicator
triggers (`morning_star, hammer, rising_three, bullish_spinning_top,
rsi_cross_up, macd_cross_up, tweezer_bottom, bullish_engulfing`). On honest
trades, which triggers make money, at what time of day, and do they beat
entering the same name at a random minute?

**Short answer.** On the honest epoch the trigger layer is **mostly a
market order under another name**. 92% of "ORB" fills and 100% of PMH
fills are the same bar and the same price as a plain buy at the next bar
open after the decision. Candle and indicator triggers fire on 4% of
tickets, because the ORB check runs first and pre-empts them. **No trigger
type and no time-of-day bucket is positive after a realistic 12–18
bps/side.** One thing is worth keeping: on the bar after the name qualifies,
**entering right away beat entering at a random minute in the next 30**,
by +$69/ticket paired at a $10k ticket. That gap is driven by the tails,
so it tells you not to wait. It does not give you a profit.

## Method (no lookahead, no existing file edited)

- `plan/lm3_trig.py` imports `plan/rotation_sim.py` and runs the
  **untouched C37F** config through `run_day`. The epoch is the honest one
  (`POOL_HYGIENE=1 RS_CROSS=1 RS_DEFER=1`, gap-through/clamped fills).
  Halal is ignored: `halal_pt` returns True, in-process only. The script
  wraps `simulate_trades` and `_memo_sim` so that every **decision** (a
  name armed at `entry_start`) is recorded with the engine's own `trig`
  field. On the same name, minute, budget and exits it also runs three
  controls with every trigger switched off:
  - **imm**: market buy at the first eligible bar (`rand_entry=(1)`).
  - **rnd0..2**: market buy at a uniformly random bar 0–29 min later
    (`rand_entry=(30, seed)`, 3 seeds).
  - The controls are drawn **unconditionally at decision time**, so the
    "all decisions" comparisons cannot see whether the trigger fires later.
- **Sample:** a 1-in-7 day stride (offset 3) across both labels: 64
  sessions, 285 decisions, 240 tickets (3.75 per day). A full run takes
  about 7 h on this machine and would have broken the 2 h cap. The
  sample's ticket stream reproduces the run's P&L to the cent (−$1,133 vs
  −$1,133).
- **Full-ledger cross-check** (`plan/lm3_tod.py`): the time-of-day and
  ticket-index split of all **2,036** tickets in the saved honest ledger
  `data/massive/rotation_trades_C37F_rs_def.json` (C37F-df, 445 days; that run carried the HALAL_STRICT env, so its pool differs slightly from the halal-ignored sample).
- **Units:** every $ figure is the leg's return on its own notional ×
  $10,000 (one $10k ticket). Net = gross − 2 × bps × $1. Net @15 bps
  means −$30 per round trip, which is the gapper cost (pessimism-audit:
  12–18 bps/side for +10% gappers). Net @6 bps (−$12) is the
  liquid-name cost and is optimistic for this pool.
- Script: `python plan/lm3_report.py <out.json>`. The data stays in the
  session scratchpad and is not committed (the run rules allow only .md
  and lm3_*.py files).

## Findings

### 1. What the C37F triggers actually are

`simulate_trades` builds its "opening range" from the **first 5 bars with
volume in the window, and the window starts at 07:00**. In practice that is
a 5-bar *premarket* high. The level only ratchets up while entries are
open. Under RS_CROSS a name is armable only after an **in-session +10%
print**, and by then it has almost always cleared that early-premarket
high. So the "ORB" stop-buy fires on the first bar after arming, at
`max(level, open) = open`. That is a market order.

| trigger | share of tickets | fill identical to the plain "imm" buy |
|---|---:|---:|
| ORB (5-bar 07:00 high, ratchet) | 210/240 = 88% | 194/210 = **92%** |
| PMH stop-buy | 21/240 = 9% | 21/21 = **100%** |
| all 8 candle / indicator patterns together | 9/240 = 4% | 0/9 |

The C11-era finding that "ORB ≈ 3× pattern entries" and that "early entries
only paid when the triggers got FAST" was really a finding about **market
entries vs. waiting for a reversal candle**. It was never about an
opening-range concept.

### 2. P&L per trigger, honest (sample, $10k ticket)

| trigger | n | win | gross $/tkt | 95% CI | net @6 | net @15 | ex-top-5 | Y1 / Y2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | 240 | 65% | +7.1 | [−58, +73] | −4.9 | −22.9 | −27.1 | −51 / +47 |
| ORB (ratchet) | 210 | 67% | +10.7 | [−58, +76] | −1.3 | −19.3 | −28.4 | −72 / +64 |
| PMH stop-buy | 21 | 52% | −37.3 | [−328, +276] | −49 | −67 | — | +32 / −89 |
| patterns (9 tickets, 5 types) | 9 | 56% | ≈ +20 | n/a | | | | |

The 9 pattern tickets were: morning_star 2 (+119), bullish_engulfing 2
(+176), tweezer_bottom 2 (−8), macd_cross_up 2 (−206), bullish_spinning_top
1 (+84). That is too few to read anything. hammer, rising_three and
rsi_cross_up never fired.

There is independent evidence from the CHAMPION-REPLAY ablation
(`data/massive/cp/ablate.md`, 444 sessions, causal universe). There the
*true* 09:30 opening-range break and the PMH-only trigger replaced the
mimic's market entry: ORB-only **−$72.90**, market entry **−$49.99**,
PMH-only **−$35.50** gross per $15k ticket (1,288 / 1,242 / 1,271
tickets). A real 09:30 ORB stop-buy was **$23 worse** than buying at
once. PMH was $14 better. Both gaps are about one standard error.

### 3. Trigger × time of day

In the sample, every bucket except 11:30–13:00 has a CI that spans zero.
11:30–13:00 shows +$101/tkt [+19, +192], both years positive. **That does
not hold on the full 2,036-ticket honest ledger:**

| entry time (full C37F-df ledger) | n | win | gross $/tkt | net @15 | Y1 | Y2 |
|---|---:|---:|---:|---:|---:|---:|
| 09:30–09:45 | 509 | 65% | **+10.8** | −19.2 | −19.6 | +35.6 |
| 09:45–10:00 | 195 | 66% | −27.1 | −57.1 | +47.0 | −83.2 |
| 10:00–10:30 | 326 | 73% | −18.1 | −48.1 | −38.1 | −1.8 |
| 10:30–11:30 | 390 | 69% | −2.9 | −32.9 | +21.9 | −26.9 |
| 11:30–13:00 | 375 | 70% | −12.4 | −42.4 | −7.5 | −17.3 |
| 13:00–14:30 | 241 | 66% | +1.7 | −28.3 | −18.4 | +17.1 |
| **all** | 2036 | | **−5.5** | −35.5 | | |

No bucket is positive in both years, and none survives 6 bps, let alone 15.
By ticket index (0–6) the range is −$17.6 to +$10.6 with no monotone
pattern, so the 09:00-hour "golden hour" from the C11 study does not show
up on honest data. The same goes for the 11:30–13:00 bucket: it was a
sampling artifact.

### 4. Trigger vs a random minute in the same name (the VIDEO-MINER claim)

Paired on the same decision, with identical exits (the −8% stop is struck
off the entry, so there is no structural-stop advantage in either arm):

| comparison | n | $/tkt difference | 95% CI |
|---|---:|---:|---:|
| trigger − random≤30m, conditional on the trigger firing | 230 | +67.5 | [+5, +129] |
| ORB (ratchet) − random≤30m, conditional | 203 | +84.0 | [+22, +143] |
| trigger − immediate, conditional | 230 | −1.6 | ≈ 0 (92% identical) |
| **immediate − random≤30m, ALL decisions (lookahead-free)** | 231 | **+68.8** | **[+5, +133]**; Y1 +29.5 / Y2 +95.3; **median +6.2, 54% > 0** |

Unconditional levels per ticket: immediate +$5.0, trigger +$7.1, random
−$13.5 / −$26.5 / −$18.6 across the 3 seeds.

**Verdict on "ORB beats a random minute by $30–42" (VS2):** this
**replicates in sign and roughly in size** on the champion's own decisions,
and here it is lookahead-free. **But on C37F what beats the random minute
is not a breakout shape. It is entering on the bar right after the name
qualifies.** The champion's ORB and PMH triggers add nothing on top of
that (trigger − immediate = −$1.6). The gap is also tail-driven: the median
paired difference is +$6. The random-delay profile is not monotone either
(0–4 min −$64, 10–19 min +$3 to +$10, 25–29 min −$48). So read this as
"don't hand the tails to a random delay", not as a clean decay curve. It is
also cost-sized: the immediate entry itself is only +$5 gross, which is
−$25 net at gapper costs.

### 5. Side observation (exits dominate entries)

Within the ORB tickets, exits by reason were: bearish-candle exit 130
tickets at +$233; −8% stop 38 at **−$781**; 15:00 flatten 39 at −$92;
scale-out 3 at +$1,747. Which entry fired explains almost nothing. What
happens after entry explains almost everything. That belongs to the exit
analysts (LEGACY-6 / -11).

## TAKEAWAYS

1. **Replace the trigger layer with an explicit market entry: "buy at the
   open of the bar after the decision bar".** This is causal. The decision
   bar is complete, and RS_DEFER already makes the qualifying bar
   unfillable. Expected change: **≈ $0/ticket** (trigger − immediate =
   −$1.6, 92–100% identical fills), so +$5 gross and −$25 net per $10k
   ticket at 15 bps. At about 79 tickets a month that is about **−$2,000
   a month net**: no edge, but no edge lost. What you gain is honesty and
   simplicity in the live paper code. The "ORB" in C37F is a 07:00
   premarket high, and live tooling that treats it as a 09:30 opening
   range is running a *different*, historically worse rule (CP ablation:
   true 09:30 ORB −$23/ticket vs market). **Test:** run C37F vs C37F with
   `entry_mode="market_at_start"` over the full 445 days. Pass if the
   difference is within ±$5/ticket and the fills match ≥90%.
2. **Never delay a ticket once a name is chosen. No "wait for a pullback
   or setup in the next 30 min" overlay.** On the same decisions, a
   random delay of up to 30 minutes cost **$69/ticket** at $10k (CI +5 to
   +133, both years the same sign). The mechanism is fresh-momentum
   continuation right after the in-session qualification. It is causal,
   because the delay is drawn before the outcome is known. This prevents a
   loss rather than producing a gain: about **+$69 × 79 ≈ $5.4k a month
   relative to a delayed-entry variant**, and the absolute level stays
   negative net. **Test:** the full-day run of `plan/lm3_trig.py`
   (`LM3_STRIDE=1`, 10 seeds, about 7 h) or a 2-of-7 stride. Pass if the
   paired imm − rnd CI excludes 0 in both years and the median is > 0.
   The current median of +$6 is the weak point.
3. **If a breakout trigger is wanted for a new strategy, define it from
   regular-session bars only** (09:30–09:35 OR or the PMH level) **and
   always pair it with the imm and random-minute controls used here.** On
   gappers a real 09:30 ORB lost to market entry (−$23), and PMH beat it
   (+$14, within one SE). Expected value as a stand-alone rule: under
   $15/ticket gross, i.e. **negative net**. Worth testing only as a
   timing layer on a ranker that is already positive, such as the
   CP-R4 coil line: does PMH-only beat immediate on R4's own decisions?
   One `cp_sim` run with `trigger="pmh"` vs `"defer"` under R4's config,
   paired by decision.

## DISCARD

- **Candle-pattern entry triggers** (bullish engulfing, hammer, morning
  star, tweezer bottom, spinning top, rising three) and **MACD/RSI-cross
  entries.** Under the champion's precedence they fire on 4% of tickets
  (3 of the 8 never fired), and the sample is unreadable (9 tickets). The
  VS2 pattern-like mechanics clustered at −$27 to −$39/ticket. Keep the
  bearish-engulfing pattern as an **exit**, where it is the only profitable
  exit bucket. Drop the bullish patterns as entries.
- **C37F's "ORB" as an opening-range concept.** It is a 07:00-premarket
  5-bar high, so in practice it is a market order.
- **The PMH stop-buy as a C37F entry.** 9% of tickets, 100% identical to
  the immediate buy, −$37 gross.
- **Time-of-day tuning of entries.** The sample's 11:30–13:00 "+$101"
  became −$12 on the full honest ledger. No bucket is positive in both
  years. The C11-era "golden hour" does not survive honest fills.
- **Ticket-index rules** (e.g. "only the first N tickets"): there is no
  monotone pattern, and the range is −$18 to +$11.

## Files

- `plan/lm3_trig.py`: decision-level trigger + imm + random-minute
  recorder (no edits to rotation_sim or day-trading).
- `plan/lm3_report.py`: the per-trigger, time-of-day, paired, delay, exit
  and identity tables.
- `plan/lm3_tod.py`: the time-of-day and ticket-index split of the full
  C37F-df ledger.
