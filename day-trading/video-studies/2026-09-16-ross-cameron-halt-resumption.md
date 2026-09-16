# "Dip & Rip on HALT Resumption!"

- Ross Cameron / Warrior Trading | 2024-07-02 | 20:15 | 23.3k views |
  `ZAwjAWD45Uw`
- Companion: "Trading Halts Explained" (`FN-uqfbEVKw`, 53.9k views) and
  TraderTV's "The ONLY Halt Trading Strategy You Need" (`FchWSzr4MV8`).

## CLAIM
"I really like trading around circuit-breaker halts." The day shown had
eight halts up before the first halt down; the stock went +300%.

## EXACT MECHANICS
- A LULD circuit-breaker halt fires on a ~10% move in 5 minutes; the
  stock reopens ~5 minutes later.
- The trade: **on RESUMPTION, take the momentary dip and buy the rip** --
  "coming out of the first halt... I look for just the momentary [dip]".
- Halts stack: "if it halts up once, twice, three times, that's
  [continuation]". "Trade things that are moving higher."

## WHAT NEEDS FUTURE INFORMATION
- The halt COUNT SO FAR is causal; "eight halts before the first halt
  down" is a post-hoc description of a finished day and is NOT a rule.
  Only the causal part is tested.
- The resumption auction print is not in 1-minute bars. The engine sees
  a halt as a GAP IN THE TAPE with both edges inside the regular session
  (`_halt_gap`), which is the honest proxy and is already used to stop
  phantom fills. **Stated limitation, not hidden.**

## HALAL
Long-only. Compatible; the halal gate removes many halted micro-caps on
its own.

## CONFIG MAPPING
`V8HALT`: new `halt_resume=(max_wait,)` -- after a >= 5-minute
regular-session tape gap, buy the first bar within N bars that takes out
the previous bar's high; stop at that bar's low; 2R. This is the one
place the engine's halt guard is deliberately inverted, and only for this
trigger.
