# "The ORB Strategy (High Odds Breakout Technique)"

- SMB Capital | 2025-03-06 | 28:17 | 158.8k views | `KFqSicS7HOo`

## CLAIM
"Breakouts within the first 15 to 30 minutes of the trading day, before
most [traders are positioned]"; a strategy that "offers clear rules for
entry, stop placement and targets".

## EXACT MECHANICS
- **Opening range = the high and low of the first 15 OR 30 minutes** --
  not 5. "Big players establish [positions]" inside it.
- Entry on the break of the range with volume; he works on 2-minute bars.
- **Stop: "a few cents below that breakout bar"** -- the SIGNAL bar, not
  the range low. A materially tighter stop than the other ORB videos.
- Targets: 1R partials plus measured moves / prior levels.
- Filters named on his examples: short interest over 20%, a catalyst,
  confluence with VWAP, and waiting past 09:45 on one of them.

## WHAT NEEDS FUTURE INFORMATION
- "Measured move" targets drawn off later structure. **UNTESTABLE-AS-
  STATED**; the causal stand-in is the fixed R multiple he also uses.
- Point-in-time short interest: no feed here.

## HALAL
He takes both directions; long side only. Compatible.

## CONFIG MAPPING
`V1OR15` and `V1OR30` -- the same `or_clock` machinery at 15 and 30
minutes, stop at the OR low, 2R. His "few cents below the breakout bar"
stop is what `struct_stop_bars=1` produces when `struct_floor_mode` is
left off, so both stop doctrines are represented in the battery.
