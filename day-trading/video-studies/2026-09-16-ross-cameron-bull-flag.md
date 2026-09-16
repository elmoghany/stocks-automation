# "Bull Flag Pattern - The #1 Beginner Day Trading Strategy"

- Ross Cameron / Warrior Trading | 2022-06-06 | 18:47 | 259k views |
  `UNoPqBWuLC0`

## CLAIM
"The #1 beginner day trading strategy"; a worked example risking 15 cents
against a ~35 cent target.

## EXACT MECHANICS
- **Pole**: a strong move up on INCREASING volume.
- **Flag**: a small pullback -- "one, two, three candles" -- on LIGHT
  volume. "High volume on the move up, light volume on the pullback, and
  then volume comes back in as it breaks out. That's the perfect volume
  profile."
- **Entry**: "the [candle] to make a new high is the entry" -- a stop-buy
  through the high of the pullback candle. He will sometimes buy just
  BEFORE the break "if I already see volume coming in".
- **Stop**: "your stop is the low of this [pullback] candle."
- **Target**: "what's the high of day... well that's your profit target";
  in his worked numbers 15c risk against ~35c (~2.3R).
- **Named failure mode**: the false breakout; avoided by demanding the
  volume profile above and preferring "a fresh five-minute breakout".

## WHAT NEEDS FUTURE INFORMATION
- "Target the high of day" is the day's outcome. **UNTESTABLE-AS-
  STATED**; replaced by his own ~2R.
- "If I already see volume coming in" as a pre-break entry is a tape read
  (level 2 / time and sales). **NOT TESTABLE** -- no historical book.

## HALAL
Long-only shares, same-day. Compatible.

## CONFIG MAPPING
`V4FLAG` (6 bars inside 2% after a >= 5% pole) and `V4FLAGw` (5 bars
inside 3% after a >= 4% pole); stop at the flag low; 2R. Engine: new
`flag_break=(n, max_range_pct, pole_pct)`.
