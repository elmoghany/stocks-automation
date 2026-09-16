# "5m Opening Range Breakout: The Simplest Day Trading Strategy"

- Aaron / QuantCrawler | 2025-12-10 | 13:33 | 5.2k views | `YL2SJUBoXl0`

## CLAIM
The one honest piece of arithmetic in the batch: "if you target a fixed
one-to-two risk-to-reward, as long as you win on your trades at least 33%
of the time, you are break-even. Anything over 33%, even 34%..." He
refers to "backtesting results on the 5-minute opening range break" but
shows none.

## EXACT MECHANICS
- Mark the **09:30 five-minute candle**; its high and low are the zone.
- Version 1: enter on the break of the zone, **stop at the OTHER side of
  the zone**, target a fixed 1:2.
- Version 2 (his own): wait for a **break and a RETEST** of the zone, or
  a retest of the zone's **MIDPOINT**; smaller stop, same 1:2.
- Timing on his example: range established 09:35, entry 10:01 -- the
  retest can come well after the break.

## WHAT NEEDS FUTURE INFORMATION
Nothing. This is the most mechanisable video in the batch: zone, break,
retest, stop and target are all defined on completed candles.

## HALAL
Instrument-agnostic (he trades futures). The long side on halal shares is
what is tested.

## CONFIG MAPPING
`V1ORBr` (break, stop = OR low, fixed 2R) is his version 1 exactly.
`V1ORBx` (break + `orb_retest` on the clock-anchored level) is version 2.
The midpoint-retest variant is one more parameter on the same machinery;
queued, not run.
