# "BEST VWAP Trading Strategy [87% Win Rate]"

- Sean Solano | 2024-08-26 | 13:17 | 217.9k views | `18cy7G2zz_Y`
- Same family: Humbled Trader `dgfQkFSzhiY` (622k views), Mind Math Money
  `sRWvYmScLYQ`, Beginner Trading `g2BoJzUBxNc`, PBInvesting `qEwHPHtzCko`.

## CLAIM
"87% win rate" in the title. No trade log, no sample size, no period. The
number is unfalsifiable as given and is treated as a claim, not evidence.

## EXACT MECHANICS
Two entries, both on the 1-minute VWAP:
1. **Bounce / reject**: price is ABOVE VWAP, moves down to the line and
   "we see an instant bounce" -- buy it; stop below VWAP.
2. **Break and retest**: price breaks VWAP down, fails, then RECLAIMS it
   -- "now that we've reclaimed this VWAP line" -- buy the reclaim. He
   distinguishes a RISKY entry (as it crosses back up) from a SAFE entry
   (wait for a candle to CLOSE over the line). Stop below the low of the
   failed break; "targets to the next highs".
3. He wants volume on the break.

## WHAT NEEDS FUTURE INFORMATION
- "Target the next highs" is a chart read; replaced by a fixed 2R.
- Humbled Trader's version adds a REGIME claim -- "if it breaks down VWAP
  twice between 9:30 and 11:00, it fades all day" -- which is a
  same-session, causal statement and is captured by requiring the signal
  bar to be above VWAP.

## HALAL
Long side only. Compatible.

## CONFIG MAPPING
`V5VWR` = the SAFE reclaim (`vwap_entry=("reclaim",)`: a completed bar
closes back above VWAP having closed below it; buy the next open).
`V5VWB` = the bounce (`vwap_entry=("bounce", tol)`: price above VWAP dips
to within tol% of it and closes back above). Stop = the signal bar's low,
fixed 2R.
