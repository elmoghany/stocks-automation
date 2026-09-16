# "SIMPLEST Trading Strategy: 5-Min Opening Range Breakout"

- Bear Bull Traders | 2025-06-19 | 10:07 | 32.9k views | `tv0oXA0bIBQ`
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
His 'five minute opening range breakout trade book'.

## EXACT MECHANICS
- 5-minute opening range; he works the 1-minute for the entry.
- **He waits for a PULLBACK after the break to get a better entry**
  rather than buying the break itself.
- Moving-average and VWAP confluence at the pullback ('today is entry
  from the VWAP').
- Stop just below the pullback; he describes being 'stopped out at
  break-even' after moving the stop up.

## WHAT NEEDS FUTURE INFORMATION
Break-even stop moves are discretionary in timing; the engine's
`breakeven_at` is the parameterised version and was measured and
rejected in the S-series (on the leaky cache -- re-testable, but not a
priority).

## HALAL
Long side compatible.

## CONFIG MAPPING
`V1ORBx` (break then retest) is his pullback entry; `V5VWR` / `V5VWB`
are the VWAP-confluence version.
