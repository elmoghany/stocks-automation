# "Master the Opening Range Breakout Strategy (5-Minute Rule)" (Short)

- ForexBee | 2026-07-10 | 0:43 | `MJkL4vWIG0s`
- Transcript via yt-dlp (watch-skill MCP could not acquire YouTube this session).

## CLAIM
The rule compressed into 43 seconds, which makes it unusually crisp.

## EXACT MECHANICS
- Range = the **first 5 to 15 minutes**.
- Entry on the break; **'stop loss goes on the [other side of the
  range]'**; **'the target is usually the same height as the range'**
  -- i.e. a MEASURED MOVE equal to the opening range height.
- Warns about the false breakout.

## WHAT NEEDS FUTURE INFORMATION
Nothing. All three elements are defined on completed candles.

## HALAL
Instrument-agnostic; long side tested.

## CONFIG MAPPING
The measured-move target is the one exit rule in this batch that no
prior config implements. New engine kwarg
`struct_target_mode="or_range"` (target = fill + OR height, a resting
limit set at entry and never moved). Config `V1ORBm` -- wave 2.
