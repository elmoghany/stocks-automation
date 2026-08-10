# Video study: "My Trading Strategy Is Boring, But It Makes Me $44,000/Month"

- **Source**: https://youtu.be/8gBcSlqRdTg (Jdub Trades, 27:18)
- **Watched**: 2026-08-10 · watch-skill index `9cde21c0a9a8e8e0`
- **Market/instrument**: OPTIONS (bought calls/puts, e.g. "the 265
  puts", 30 contracts) on liquid large caps — TSLA, NVDA — with QQQ/SPY
  used as market context. Both directions. Stats frame: $44,322/month,
  66.67% win rate, 5.24 profit factor.

## HALAL VERDICT (checked FIRST per template)

**Method AS TAUGHT: NOT halal — the wrapper, not the underlying.**
- Instrument: exchange-traded OPTIONS (premium for a right, gharar-
  laden; excluded categorically by this project's rules, same as the
  E-book decision). Shorts are expressed via puts — same problem.
- The UNDERLYINGS are fine: TSLA and NVDA are both on our halal list
  (verified against halal_universe.json — both pass current-quarter
  ratios). QQQ/SPY are mixed-index ETFs (unscreenable) but he uses
  them only as context, not positions.
- **The mechanical core is instrument-neutral and halal-compatible**:
  break-and-retest entries on shares, long side, work identically.
  This is the OPPOSITE of the futures video: there the method died
  with the instrument; here the method transplants cleanly.

## The strategy, step by step

Three setups, all one mechanism — "break & retest", minimal
discretion, no indicators:
1. **Opening-range break & retest** (his favorite): mark the opening
   candle range; when price BREAKS it, do not chase — wait for the
   pullback to RETEST the broken level; enter on resumption. Failed
   retest (close back through the level) = no trade.
2. **Order-block break & retest**: same mechanic off the last
   consolidation block before an impulse.
3. **Previous-day-high/low retest**: PDH/PDL as the levels; e.g.
   short the PDH rejection toward PDL when higher timeframes lean
   bearish (his TSLA 265-put example, ~$12,000 on 30 contracts).
Context filter: trade the name in the direction of QQQ/SPY's move
(relative weakness/strength intraday).

## Relation to our system

We already trade the BREAK (5-min ORB stop-buy, PMH stop-buy). His
core claim is that the RETEST entry beats the break entry: fewer
false breakouts, better price, tighter structure risk. Directly
testable long-only on our gappers — and unlike the futures video's
R-brackets, this changes the ENTRY, not the tail-funding exits.

## Experiments derived (G-series, on the Z104 base)

| id | config | status |
|----|--------|--------|
| G001 | break&retest, tol 0.5%, wait 20 bars | running |
| G002 | tol 1.0% (adjacency) | running |
| G003 | tol 0.25% (adjacency) | running |
| G004 | tol 0.5%, wait 40 (patience axis) | running |
| GC01 | CONTROL: retest of level+2% (nonsense level) | running |

Engine: `orb_retest=(tol_pct, max_wait[, level_offset])` in
simulate_trades — a break arms the retest; entry fills only on
pullback-touch then resumption through the pullback high; close back
below level−tol cancels. Applies to ORB and PMH triggers; pattern
(Trigger C) entries unchanged. Identity gate: S095 + Z104 EXACT with
the kwarg unset.

## Results (G-series complete, 2026-08-10)

vs the Z104 base ($646,581 / 2yr):

| id | config | 2-yr total | delta |
|----|--------|-----------|-------|
| GC01 | CONTROL: nonsense level (+2%) | $575,517 | -$71k — BEST of the family |
| G002 | tol 1.0% | $538,182 | -$108k |
| G001 | tol 0.5% | $503,929 | -$143k |
| G004 | tol 0.5%, wait 40 | $490,300 | -$156k |
| G003 | tol 0.25% | $482,417 | -$164k |

VERDICT: break-and-retest REJECTED, and the gradient tells the whole
story -- the LESS the retest requirement binds (nonsense level, wide
tolerance), the closer to the plain-break baseline; the tighter it
binds, the worse. The control beating every real-level variant means
the broken level carries NO entry information on our names; the
retest is pure tax, paid in forfeited runners that never pull back.
Second confirmation (after F001/FC01) that entry microstructure is
not where this system's money lives. C37 unchanged.

## Prior expectation (stated before results)

Honest priors cut both ways: retest entries SHOULD reduce false
breakouts (his 66% win rate lives there), but our F-series just
proved entry microstructure barely matters in fast gappers, and a
mandatory pullback WAITS while the monster runs — the tail we must
never cap is exactly the move that never looks back. If G001 loses,
it will be because the best gappers don't retest.
