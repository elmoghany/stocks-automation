# "Fair Value Gap (FVG) Trading Strategy Explained (ICT)" + "I Fixed ICT's FVG Strategy" + "Every ICT Trading Strategy Explained in 13 Minutes"

- LogicaTrading EN 2026-02-19 (7:32) | Trading Nut 2026-03-15 (11:53) | Smart Risk 2025-10-18 (12:59, **541.5k views**) | `cLXzOINydGc`, `N5XI5n-gBFY`, `vGyREXEwLIk`
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
The FVG is presented as the core ICT entry model.

## EXACT MECHANICS
- A **fair value gap** is a three-candle imbalance: price moves so
  sharply that candle 1's high and candle 3's low do not overlap,
  'leaving behind this gap... buy orders haven't [been filled]'.
- The bullish (positive) FVG is the long setup; the bearish one is
  the short.
- Entry: price RETRACES into the gap and continues; the canonical
  version rests a LIMIT at the top of the gap.
- 'Not every fair value gap is suitable for entry. We must learn how
  to filter' -- the filters given are directional context and gap
  size.

## WHAT NEEDS FUTURE INFORMATION
- The filters ('is it valid') are taught by example, not by a rule.
  The only numeric one that survives is a MINIMUM GAP SIZE, which is
  what gets parameterised.
- The resting-limit entry needs a BUY-side limit fill model that this
  engine does not have (its buy path is a stop-buy). **The
  CONFIRMATION variant is implemented instead** -- price must retrace
  into the gap and then take out the previous bar's high -- and the
  limit version is queued and labelled.

## HALAL
Long side only. Compatible.

## CONFIG MAPPING
`V9FVG` / `W9FVG`: new `fvg_entry=(max_wait, min_gap_pct)`.
