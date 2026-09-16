# "The ICT Silver Bullet Strategy They Don't Want You To See" + "How To Start ICT Day Trading For Beginners 2026"

- The Trading Geek 2026-07-17 (29:53, **124.7k views**) | Michael Whitman 2026-07-20 (16:01) | `rU0vQUTNXVE`, `T0q2caAR_QY`
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
'One very specific strategy... high risk-to-reward trade setups.' The Silver Bullet is described as 'a one-hour intraday setup built around liquidity, the sweep, and the fair value gap'.

## EXACT MECHANICS
Three ordered steps, each stated explicitly:
1. **A LIQUIDITY SWEEP**: 'it has to sweep some form of [liquidity]'
   -- price runs the prior high (short side) or the prior low (long
   side).
2. **DISPLACEMENT**: after the sweep, a decisive move back the other
   way.
3. **ENTRY on a point of interest inside the displacement** -- 'your
   entry model is either going to be a fair value gap or [an order
   block]' -- with the stop at the swept extreme, 'a much tighter
   stop loss'.
4. **Target: the opposite side's liquidity** -- 'if price sweeps the
   low and gives you [a long] entry, you want to be targeting the
   most recent high.'
- The AM Silver Bullet restricts all of this to **10:00-11:00 ET**.

## WHAT NEEDS FUTURE INFORMATION
- 'The most recent high' as a target is a level that exists at
  decision time, so it is causal -- but it is a level the engine has
  no target kwarg for. The fixed 2R is used instead and the
  swing-high target is **queued**.
- 'Displacement' is judged by eye. Modelled as the reclaim bar taking
  out the previous bar's high.

## HALAL
The demonstrated trade is a short. **Long side only** here: sweep the
LOW, reclaim, buy.

## CONFIG MAPPING
The sweep leg is `V9SWP` / `W9SWP` (`sweep_reclaim=(20, 3)`); the FVG
leg is `V9FVG` / `W9FVG`; the 10:00-11:00 AM window is `V9SB` /
`W9SB`. **They are run as SEPARATE configs, not as a conjunction** --
the engine takes whichever trigger fires first, so a true AND of
sweep-then-FVG is a queued refinement, said out loud rather than
claimed.
