# "The Micro Pullback Trading Strategy"

- Ross Cameron / Warrior Trading | 2024-08-26 | 0:56 | 65.9k views |
  `TI-xDErgLQM`

## CLAIM
None numeric (it is a short). It states the entry he is best known for.

## EXACT MECHANICS
"The stock pops up right here -- this first pop, those are the
high-frequency trading algos -- and then usually it's going to pause just
for a moment. **And if it pushes higher, that's where I'm buying.** This
is called a micro pullback."

Mechanised: a new high of the session-so-far, then a SHORT pause (bars
that fail to exceed it), then a bar that takes out the PREVIOUS bar's
high -> stop-buy at that level, stop at the pause bar's low.

## WHAT NEEDS FUTURE INFORMATION
Nothing, as stated. The only judgement is the length of "a moment",
parameterised as a 1-3 bar pause and swept.

## HALAL
Long-only momentum on shares. Compatible.

## CONFIG MAPPING
`V2MPB` (pause <= 3 bars after a >= 3% pop, stop = the pause bar's low,
2R), `V2MPB1` (1-bar pause), `V2MPBh` (no target, hold to the flatten).
Engine: new `micro_pullback=(max_pause, pop_pct)`.
NOTE vs prior art: the engine's own SCAN->DIPPING->ARMED path is also a
dip entry, but it fires on a BULLISH CANDLE CLOSE after a cents-defined
dip, with a percentage stop. The micro pullback is a STOP-BUY through the
prior bar's high with a STRUCTURE stop. Different trigger, different
stop, never tested here.
