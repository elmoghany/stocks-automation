# "This 'Green on Red Rule' Finds Stocks BEFORE They Breakout"

- Freedom Team Trading | 2026-01-11 | 10:38 | `DWWl8A_f0_A`
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
A rule that 'finds stocks before they break out'.

## EXACT MECHANICS
**RELATIVE STRENGTH**: if the broad market is RED on the day and a
stock is GREEN, institutions are accumulating it -- buy it. Scan for
stocks green while the index is red; stop loss below a nearby low;
'target a one-hour, two-hour trade'.

## WHAT NEEDS FUTURE INFORMATION
The rule itself is causal (both sides are known now). What it needs is
**an index minute series aligned to every date**: only one SPY day
(2025-04-09) exists in `data/massive/m1`. It also needs a non-gapper
universe, because on this pool every eligible name is up >= 10%.

## HALAL
Long-only. Compatible.

## CONFIG MAPPING
**NEEDS A WIDE UNIVERSE + AN INDEX FEED. Queued, not run.** This is
the single most promising untested mechanic in the batch precisely
because it is orthogonal to everything already measured (it is a
cross-sectional rule, not a shape rule).
