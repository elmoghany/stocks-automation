# "Make a Living in 1 Hour a Day Trading the 3 Bar Play" / "Make $2000 a Day Trading the 1 Minute 3 Bar Play" / "Trading The 3 Bar Play: Everything You Need To Know"

- Live Traders (Jared Wesley) | 2019-04-24 (34:34, **2.97M views**), 2021-06-01 (11:15, 38.6k), 2019-07-26 (103:32, 521.5k) | `eXO1EXDnCpE`, `Of9T-cwjfHU`, `xEjUd82NVVg`
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
'Make a living in 1 hour a day'; '$2000 a day on the 1-minute 3 bar play'. The 2.97M-view video is the single most-watched item in this whole batch.

## EXACT MECHANICS
Three bars, named in the video:
1. **A WIDE-RANGE 'IGNITING' BAR** -- a large green candle.
2. **A NARROW-RANGE 'RESTING' BAR** -- 'a wide range igniting bar followed by a narrow range resting bar'.
3. **The trigger bar**: buy the break of the resting bar's high.
- **Stop**: below the resting bar's low (he quotes '$1 stop loss',
  '$1.50 with a stop at ...' on the examples).
- Works on any timeframe: 'a two minute three bar play or a five
  minute three bar play... that's fine.'
- Context filter he uses: the market itself gapping the same way.

## WHAT NEEDS FUTURE INFORMATION
Nothing in the three-bar definition needs the future. The context
('I really like this gap') and the target sizing ('I needed a little
bit of a larger target') are discretionary; the causal stand-in is
the fixed R multiple.

## HALAL
Long-only version tested; he takes both sides.

## CONFIG MAPPING
`V9TB` / `W9TB`: new `three_bar=(wide_mult, narrow_mult)` -- bar i-2
range >= 1.8x the median range of the prior 10 bars AND closes green,
bar i-1 range <= 0.5x bar i-2's, then a stop-buy through bar i-1's
high with the stop at its low, 2R.
NOTE it is a near-relative of `micro_pullback` with a 1-bar pause;
the difference is the explicit WIDE/NARROW range condition, which is
the whole content of the pattern.
