# "The 'First Pullback Rule' That Nobody Talks About"

- Jdub Trades | 2025-12-28 | 14:53 | 44.4k views | `XMQkS9o18LM`
- Same channel as the batch-1 break-and-retest study (2026-08-10), a
  DIFFERENT mechanic. Noted for the dedupe record.

## CLAIM
"$69,000 in the past month, 58% win rate, 2.61 profit factor, 82% day win
percentage, average win-to-loss 1.86" -- with his own disclaimer that
the results are not typical.

## EXACT MECHANICS
- **Window**: the first 90 minutes after 09:30. "That's usually when we
  establish trends... the best trading opportunities."
- **Step 1**: a clear trend -- "a very bullish and impulsive move higher"
  on the lower timeframes.
- **Step 2**: wait for the FIRST pullback into a level. The levels, in
  his order: the 1 / 5 / 15-minute opening range, a down-close candle
  ("order block"), higher-timeframe key levels (previous day high/low),
  and -- "strictly for momentum trades" -- the **9 EMA**.
- **Step 3**: entry "after this candle closed above its previous candle",
  or a stop-buy just above the 5-minute range high.
- **Stop**: below the level (5-minute range high / key pivot).
- **Target**: "high of day plus continuation", or **a fixed 1-to-2
  risk-reward**.
- Doctrine: "We never want to be buying breakouts. We want to be buying
  on pullbacks."

## WHAT NEEDS FUTURE INFORMATION
- "High of day" as a target is the day's outcome. **UNTESTABLE-AS-
  STATED**; replaced by the fixed 1:2 he gives in the same breath.
- "A clear trend" and "the personality of a ticker" are discretionary;
  modelled causally as a RISING 9 EMA at the signal bar.

## HALAL
He trades both directions (the NVDA example is a short). Long side only
here. Compatible.

## CONFIG MAPPING
`V3EMA`: new `ema_pullback=(9, 0.25)` -- a DOWN-CLOSE bar that touches
within 0.25% of a RISING 9 EMA but closes above it, then a stop-buy
through that bar's high, stop at its low, fixed 2R, 09:35-11:00.
The "pullback into the 5-minute opening range high" variant is `V1ORBx`
(`or_clock` + `orb_retest`).
