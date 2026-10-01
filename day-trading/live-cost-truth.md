# LIVE-COST-TRUTH (2026-10-01): what a $15k order costs per side, from our own paper legs

Part of PESSIMISM-AUDIT. Question: what does a $15k order on Robinhood actually cost per side,
against the 10 bps/side flat and the ~12 bps/side "measured" (`cr_cost` Y=1) models the backtests charge?
Halal ignored.

Script: `plan/lct_cost.py` writes `plan/lct_out/legs.json`. It reuses the 42-leg fill list in
`plan/pa_live.py`, adds a hand-labelled leg table built from the ledgers (trigger type, stop
level, signal bar, logged bid/ask), and reads Polygon m1 bars (`plan/pa_out/m1`) and the 1-second
tape (`data/massive/trades{,_pm}`, which covers the 10 symbol-days from 08-10 to 08-21 only).

## Read this first: there are no real Robinhood fills

All 21 tickets (42 legs, Days 5–24, 2026-08-10 → 09-17; Day 25, 09-18, was flat) are
**paper**. Every ledger says `REAL_ORDER false`. Each fill was **booked by a convention**
against a live RH quote or L2 book (inside ask, a sweep of the displayed levels, inside bid,
`bid × 0.999`, or the stop level itself). So what we can measure is:

1. **The market's toll** at the moment of each order: the half-spread from logged quotes
   (n = 17), plus any sweep past the touch. This is the genuine cost a real order would pay.
2. **How the booked fill compares** with three references: the logged mid, the fill-minute
   OPEN that a bar backtest would use, and the fill-minute VWAP.

Robinhood price improvement (PFOF) can't be measured from these logs. It can only lower the
real cost.

## Headline table (bps per side, positive = cost to us)

| bucket | n legs | vs logged mid (n) med / mean | vs minute OPEN med / mean | vs minute VWAP med / mean | vs backtest's own booking price med / mean | half-spread at order (n) med / mean |
|---|---|---|---|---|---|---|
| all | 42 | (12) 11.5 / 13.6 | 20.1 / 39.8 | 7.4 / 13.7 | 3.9 / 12.3 | (17) 13.0 / 14.4 |
| stop-buy entries (B premarket/session-high, A ORB) | 12 | (3) 15.7 / 24.4 | 67.7 / 71.0 † | 15.7 / 20.1 † | **0.0 / 1.9** | (6) 19.0 / 24.6 |
| Trigger C pattern entries | 9 | (6) 12.2 / 12.2 | 17.5 / 26.3 | 5.9 / 11.3 | **5.7 / 19.5** | (7) 13.0 / 12.0 |
| ladder exits (14:50–15:00) | 18 | (3) 4.0 / 5.5 | 7.3 / 17.7 | 7.3 / 18.3 | 7.3 / 17.7 | (4) 3.1 / 3.1 |
| stop / trail exits | 3 | — | 76.8 / 88.3 | −3.0 / −32.6 ‡ | 0.0 / 0.0 ‡ | — |
| premarket legs | 9 | (4) 10.6 / 12.4 | 31.6 / 46.5 | 5.9 / 4.9 | 0.0 / 0.8 | (6) 17.8 / 22.1 |
| regular-session legs | 33 | (8) 11.5 / 14.2 | 18.7 / 38.0 | 8.8 / 16.1 | 5.9 / 15.5 | (11) 11.0 / 10.1 |
| RTH, liquid (fill-minute $vol ≥ $1.5M, so the ticket is ≤ 1% of the minute), excl. stops | 12 | (5) 12.0 / 9.1 | 10.5 / 29.1 | 9.2 / 11.7 | 4.4 / 6.6 | (6) 8.7 / 10.0 |
| RTH, thin (< $1.5M/min) | 19 | (3) 11.0 / 22.6 | 18.7 / 39.9 | 5.0 / 25.5 | 12.8 / 22.7 | (5) 11.0 / 10.2 |

† A stop-buy fires part-way up a rising minute, so the minute's open and VWAP sit below the
trigger by construction. That gap is the momentum path. The backtest already books at the
trigger (or at the open if the bar gaps through it), so it isn't an extra cost.
‡ The stop and trail exits were booked AT the stop level. GTLB's 09:31 trail was booked at
51.56 while that bar's low was 50.28, which puts the booking 118 bps better than the minute
VWAP. This convention is **optimistic** and isn't a market cost.

The liquidity split uses the fill minute's dollar volume. `liquidity_truth.json` overlaps
the traded legs at only about 12 order-time books: its 176 observations are mostly
premarket veto reads on other names (median spread 1.25%, a selected wide sample). Its
order-time quotes for the traded legs are already in the half-spread column.

Small-sample warning. Bootstrap 90% intervals: half-spread in RTH (n = 11) median 11.0
[4.2, 13.4], mean 10.1 [6.8, 13.4]. Booked fill vs mid (n = 12) median 11.5 [6.1, 14.3],
mean 13.6 [8.5, 20.0]. Fill vs minute VWAP for RTH legs excluding stops (n = 30) median 9.2
[4.1, 17.9], mean 20.9 [11.5, 31.3]. The means come from 3–4 legs: an ANGX exit of 3,040
shares into a thin bid (+58 bps past the bid), NEOV (+90 entry lag, +109 exit) and LFST
(+148 on entry). Medians are trustworthy to about ±5 bps; means to about ±10.

## Decomposition: what the market charges vs what our execution added

**A. Market cost (half-spread plus sweep past the touch).**
- **Entries** are in gapper or momentum names, 09:30–10:20 or premarket. The logged
  half-spread was about 11–15 bps in RTH: RDDT 15.1 at 09:32, SMMT 13.4, AXTI 11.0, CRML
  13, MRVI 6.1, VICR about 23. Premarket it was 3.5 (QCOM) up to 64 (GTLB at 08:08).
  Sweeping past the inside ask at $15k cost **0–6 bps**: NEOV 6.2 and GTLB 1.9 over two to
  three levels. It was zero on every other entry.
- **Ladder exits** happen at 14:50–14:58 in names that have calmed down. Half-spread was
  **2–4 bps** (MRVL 2.1, OKTA 4.0, GTLB 2.0, LFST 4.2). A $15k sell cleared at the inside
  bid in every liquid case. The single real impact event was ANGX (3,040 shares, $0.02M per
  minute): 58 bps past the bid. That's a thin-name problem, not a $15k problem.

**B. Our own execution and booking (not market cost).**
- **Stop-buys were booked at the trigger** (c_bt median 0.0). Simulating a real stop-market
  order on the 1-second tape (the VWAP of the first 3 s after a print at or above the
  trigger): FRMI +2.5, BE +4.1, ANGX 0.0, RDDT −3.9, HIVE −22 (thin premarket), MRVL +10.8.
  **Median +1.2 bps, n = 6.** Chasing above the level is small. The real cost of a stop-buy
  is that it fires into a wide momentum spread (B half-spread median 19).
- **Trigger C entries arrived 0–1 bars after the signal close + 1 bar open** that the
  backtest books (lag median 1 min). The fill paid a **median 5.7 bps above that open (mean
  19.5)**: MRVI +43, NEOV +90, CRML +26, SMMT +20, AXTI −16, QCOM −2. This is latency drift
  in a moving name and the biggest controllable item. It cuts both ways (median small, tail
  large).
- **Ladder exit haircut.** Since 2026-09-02 the watcher books exits at **`bid × 0.999`**, a
  deliberate 10 bps below the bid, on top of the spread (GTLB, QCOM, AXTI, VICR: c_touch =
  10.0 each). It's a paper convention, not a market cost. A marketable limit at the bid in
  these names would very likely have filled at the bid, since $15k is a small fraction of the
  displayed bid in names this size.
- **The LFST entry (+148 bps vs the minute VWAP)** came from a book sweep of 12.06–12.10
  booked when the tape traded around 11.89. It was a ledger artefact on Day 5.
- **Stop and trail exits booked at the level** are optimistic by 0 to 118 bps (gap-through).
  Current backtests already use gap-through fills here (C37F-fm), so this only affects the
  paper P&L.

## What a careful limit or marketable-limit execution would cost

- **Regular-session entry in a gapper or momentum name before 10:30.** Expect half-spread
  10–15 bps plus 0–5 bps of sweep: **about 12 bps/side**, unless the order rests passively,
  which gives up fills (LIMIT-EXEC).
- **Regular-session exit 14:50–15:00 in a liquid name.** Half-spread 2–4 bps, at the bid,
  with no haircut: **about 3–4 bps/side**.
- **Premarket.** Half-spread median 18 and mean 22 with a fat tail (64). The 50 bps premarket
  charge in the sim stays defensible.
- **Thin names** (< $0.5M per minute). Exits can cost 30–110 bps (ANGX, NEOV, CRML). Size the
  ticket, don't change the cost constant.

## Recommendation

For **regular-session $15k fills in liquid names, use 8 bps/side**: about 12 on a morning
momentum entry and about 4 on an afternoon exit. A credible range is 5–12 given n ≈ 30
RTH legs. If the harness can price the two sides separately, use **12 bps on entries in
09:30–10:30 and 4 bps on exits after 14:00**. This is consistent with PESSIMISM-AUDIT checks
1–2, which give 6 bps all day and 9 bps at the open on the wide universe.

Against the incumbents:

- **The flat 10 bps/side is about 2 bps/side conservative**, about $6 per round trip on
  $15k. That isn't the reason everything loses.
- **The ~12 bps "measured" model is about 4 bps/side too high** for these fills, and much
  more on the wide universe according to check 1.
- What live cost does show is two **execution** items worth more than the cost constant:
  1. Trigger C fills land 1 minute late: median +6 bps, mean +20.
  2. The paper ledgers' `bid × 0.999` exit haircut adds 10 bps that a real marketable limit
     wouldn't pay.

None of these numbers is a real Robinhood execution. The first real fills, even a handful,
would replace this whole table.
