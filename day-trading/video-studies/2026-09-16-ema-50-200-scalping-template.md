# "The BEST Simple 1 Minute EMA Scalping Strategy (High Win Rate BACKTEST!)" and the 1-minute EMA scalping genre

- `Macxr4jOJJQ` plus `bO_qQi-NJEo`, `IKv5ha6aA2k`, `Pj1pltM_DXA`, `9D4gJ9LdOvA`, `ohtnf4H_HMA`, `u5bLGLfQBjg` -- seven videos teaching the same template with different EMA pairs (9/21, 8/21, 34, 50/200, 21/100)
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
'High win rate', '86% win rate', '90% accurate entry and exit signals'. One of them shows a backtest on the 1-minute chart; none shows a trade log, a sample size or a cost assumption.

## EXACT MECHANICS
The template, stated identically across the genre:
1. **A bullish EMA CROSS** -- 'the 50-period EMA has crossed above
   the 200-period EMA. This is also [the trend filter].'
2. **A PULLBACK to the fast EMA** -- 'price pulls back to the
   50-period EMA, once this happens, there [is the entry]'.
3. Entry on the confirmation candle; stop below the pullback low;
   **target a fixed 1.5 risk-to-reward**.
The other videos swap the pair (9/21, 8/21, 34, 21/100) and some add
MACD or RSI confirmation.

## WHAT NEEDS FUTURE INFORMATION
Nothing needs the future. The win-rate claims are unfalsifiable as
given -- no period, no sample, no costs -- and the genre is exactly
the indicator-entry family this campaign has already rejected three
times (on the LEAKY cache, so it is re-testable here, which is why it
is run rather than dismissed).

## HALAL
Long side only. Compatible.

## CONFIG MAPPING
`V3E50` / `W3E50`: `ema_gate=(50, 200)` (the engine's existing cross
gate) + new `ema_pullback=(50, 0.15)` + `target_r=1.5`. `V3EMA` /
`W3EMA` is the 9-EMA member of the same family.
