# Video study: "This 1 Minute Scalping Strategy Works Everyday"

- **Watched**: 2026-08-10 · index `8328d19e097d4813`
- **Instrument**: STOCKS (Swedish stock-trading champion lineage),
  1-minute chart, LONG AND SHORT via limit orders.

## HALAL VERDICT (first)

Shares-based — no futures/options/margin pitch in the transcript scan.
The SHORT half is excluded for us; the LONG half is halal-compatible.
Partial transplant candidate.

## Mechanics taught — the "Touch & Turn scalper"

1. The session's FIRST 1-minute candle is treated as the "liquidity /
   manipulation candle" — the open's first push is presumed fake.
2. If that candle is POSITIVE: limit order to SHORT at the high of its
   range (fade the up-manipulation). If NEGATIVE: limit LONG at the
   low (fade the down-flush).
3. Mechanical, no indicators; the fill happens only if price returns
   to touch the extreme ("touch"), then reverses ("turn").

## Overlap with our set

- Fading strength (short side): excluded, and our system's whole
  edge is momentum WITH the move — opposite thesis.
- **The long half is genuinely NEW for us**: a LIMIT-BUY at the
  opening candle's LOW after a negative first minute — buying the
  opening flush inside an up-gapped name. We have never tested a
  limit-order mean-reversion ENTRY; every entry we run is a stop-buy
  into strength or a reversal-candle close. It is an entry ADDITION
  (new trigger), not a gate or tail-cap — the only experiment family
  not yet exhausted by F/G-series.

## Experiments

H-pool candidate: `open_fade_long` — when the 9:30 candle of an
eligible (crossed, halal, calm-gap) name closes RED, rest a limit buy
at that candle's low for N minutes; standard C37 exits. Control: rest
the limit at a level offset above/below (nonsense placement).
