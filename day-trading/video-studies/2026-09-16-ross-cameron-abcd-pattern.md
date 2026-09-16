# "ABCD Pattern: A Beginners Day Trading Strategy"

- Ross Cameron / Warrior Trading | 2022-06-06 | 14:52 | 144.5k views |
  `IHeJROuEzRU`
- Cross-checked against NetPicks `p_pq97LEiVw` and StocksToTrade
  `nUsu5K82FN8`, which teach the same letters with the same entry.

## CLAIM
A named chart pattern with a defined entry: "similar to a bull flag".

## EXACT MECHANICS
- **A**: the initial spike high. Defining condition: during the pullback
  price "does NOT break through high of day -- it cannot break through
  that level, or it's no longer an ABCD pattern."
- **B**: the pullback low, "often a double bottom". "The pullback cannot
  come [all the way back down]."
- **C**: "the first candle to make a new high out of this pattern" -- an
  aggressive entry, stop at B.
- **D**: "most traders will wait to buy the break... as it breaks through
  the high [of A], for example 7.50, that's where you're buying."
- Stop: the double bottom (B). The 9 moving average is referenced as
  context.

## WHAT NEEDS FUTURE INFORMATION
- The pattern's own definition ("it cannot break through high of day") is
  a look-BACK statement at the signal bar -- the running high so far --
  so it is causal. Drawn on a finished chart it LOOKS like a prediction;
  implemented strictly as "A did not exceed the running high through A".
- "Double bottom" is discretionary; modelled as "the pullback low holds
  above a fixed fraction of the A leg".

## HALAL
Compatible.

## CONFIG MAPPING
`V7ABCD`: new `abcd_entry=(leg_pct, max_pull_frac, max_wait)`; entry is
leg D (the stop-buy through A), stop at B, 2R.
