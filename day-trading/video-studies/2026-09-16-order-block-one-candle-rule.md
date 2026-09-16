# "The ONLY 1 Minute Scalping Strategy You Need For 2026" (the one-candle rule / order block)

- `IKv5ha6aA2k` (2026-01-04) plus the order-block sections of `795tKU5Zxu8` and `T0q2caAR_QY`
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
'This one candle rule makes trading so [simple]... it solves 90% of my trading [problems]', explicitly for 'the first 90 minutes of [the open]'.

## EXACT MECHANICS
- An **order block** is the last opposite-colour candle before an
  impulsive move. Mark its high and low.
- **Entry** is a LIMIT into the block: 'your entry can either be at
  the top of [the block]... entry number two is at the MIDDLE of the
  order block.'
- **Stop** below the block ('your risk is going to be all the way
  [below it]').
- Window: the first 90 minutes.

## WHAT NEEDS FUTURE INFORMATION
- The block is identified AFTER the impulsive move, which is causal
  at the moment of entry but is drawn on a finished leg in every
  example shown.
- **The entry is a resting BUY LIMIT into a zone.** This engine's buy
  path is a stop-buy; a buy-side limit fill model is not implemented.
  The CONFIRMATION variant (retrace into the zone, then take out the
  prior bar's high) is what is tested, and the limit variant is
  QUEUED and labelled -- it would systematically get BETTER fills, so
  not modelling it is the conservative choice, not a favourable one.

## HALAL
Long side only. Compatible.

## CONFIG MAPPING
Same machinery as the fair value gap: `V9FVG` / `W9FVG`. The order
block and the FVG are the same object approached from two sides (an
untraded zone left by an impulse).
