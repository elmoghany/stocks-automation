# "VWAP Bands Trading Strategy (The 68/95/99 Rule)"

- Mind Math Money | 2026-07-13 | 9:39 | 15.8k views | `sRWvYmScLYQ`
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
Frames VWAP bands as standard deviations: 68/95/99% of price action
inside 1/2/3 sigma.

## EXACT MECHANICS
- Bands = VWAP +/- 1, 2, 3 standard deviations.
- The stated long play: **'buy pullbacks to the VWAP'** when the trend
  is up -- 'right here could be a buying opportunity' as price returns
  to the line; a bullish engulfing at the line is 'another buy'.
- Outer bands are treated as stretched/mean-reverting.

## WHAT NEEDS FUTURE INFORMATION
'When the trend is up' is a chart read; modelled as the signal bar
closing above VWAP.

## HALAL
Long side compatible.

## CONFIG MAPPING
`V5VWB` (`vwap_entry=("bounce", 0.1)`) is this rule; `V6VWB` /
`V6VWB2` are the 1- and 2-sigma band versions with a VWAP target.
