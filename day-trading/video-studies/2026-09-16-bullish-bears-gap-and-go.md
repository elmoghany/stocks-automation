# "Gap and Go and Gap Fill Popular Day Trading Strategies"

- Bullish Bears | 2026-06-11 | 13:19 | `39PR3Ox8b2k`
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
No P&L claim. A survey of how small-cap gappers are traded.

## EXACT MECHANICS
- Universe: small caps / 'penny stocks' in the **$3 to $10 range**.
- Premarket routine: take the premarket gapper list, **map out support
  and resistance from the premarket session**, check gap percent,
  float (lower float = more volatile), volume and breaking news.
- The trade is the break of those mapped premarket levels after the
  open; the 'gap fill' variant fades back toward the prior close.

## WHAT NEEDS FUTURE INFORMATION
- 'Map out support and resistance' is a chart read; the only
  mechanisable version of it is the premarket high, which the engine
  already trades (`extra_break_high`, champion parity).
- **Gap fill is a SHORT** on a gap-up name. Dropped.
- Float as of the date: measured and rejected in the V-series.

## HALAL
Long side compatible; the gap-fill side is not taken (short).

## CONFIG MAPPING
Confirms the price band this campaign already uses (`min_px` $3) and
the premarket-high break already in the engine. **No new config.**
