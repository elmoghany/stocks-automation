# "Liquidity Sweep Trading Strategy Explained"

- `Skn0eSmryO8` (2024-12-18) plus the sweep leg of the Silver Bullet videos
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
Liquidity sweeps as the mechanism behind failed breakouts.

## EXACT MECHANICS
Price runs through an obvious prior low (where stops rest), fails to
hold, and closes back ABOVE that level -- the sweep. The long entry is
the reclaim; the stop is the swept low; the target is the range's
other side.

## WHAT NEEDS FUTURE INFORMATION
Nothing; the swept level and the reclaim are both known at the signal
bar. The 'obvious' level is parameterised as the lowest low of the
prior N bars.

## HALAL
Long side compatible.

## CONFIG MAPPING
`V9SWP` / `W9SWP`: new `sweep_reclaim=(lookback, max_wait)` -- a bar
makes a new 20-bar low but CLOSES back above that prior low, and the
next bar takes out its high. Stop at the swept low, 2R.
