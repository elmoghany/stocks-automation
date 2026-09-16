# "The Only VWAP Strategy I Use Every Day (15 Years of Trading)"

- Trader Drysdale | 2026-06-13 | 15:53 | 44.8k views | `Z2uJRbkb2pA`

## CLAIM
"Setup two" of his VWAP-wave system. "On a true range day, a fade at the
upper band has a 70 to 80% probability of reaching VWAP before breaking
through to new highs on the session. On a trend day, 20 to 30%." Sized
for a $500 futures account; "this is not a get-rich-quick strategy".

## EXACT MECHANICS
1. Price must be INSIDE the VWAP +/- 1 standard-deviation bands (the
   "value area").
2. Price must TEST an edge (upper or lower band).
3. There must be a REJECTION: "a wick, a stall, a strong close back
   inside."
4. Entry at the rejection; **stop just beyond the wick**; **target =
   VWAP**.
5. **No trades in the first 15 minutes** -- "the value area hasn't
   formed yet, you have no real reference, you're trading blind."
6. **Time stop**: "if price hasn't hit VWAP in, let's say, 60 minutes, I
   close the trade... time is a cost."
7. Account rules: stop after two losses in a row; one setup per day while
   learning; nothing 30 minutes around CPI/FOMC/NFP; risk ~2% per trade.

## WHAT NEEDS FUTURE INFORMATION
- "Is today a range day or a trend day" is the entire conditioning
  variable and he reads it by eye from the morning's rotation. The causal
  proxy used here is rule 1 itself -- price inside the bands AT the
  signal bar -- which is what the condition looks like in the moment.
- "Acceptance outside the bands" is discretionary; not modelled.

## HALAL
His demonstrated trade is a SHORT at the upper band. **The short side is
dropped.** The long side -- "price touches the lower band, rejection wick
to the upside, buyers step in and I buy, stop goes below the wick, we
target the VWAP" -- is stated in the video in those words and is what is
tested.

## CONFIG MAPPING
`V6VWB` (1 sigma) and `V6VWB2` (2 sigma): `vwap_entry=("band", k)`,
`struct_floor_mode="sig_low"` (stop under the wick), `vwap_target=True`
(a resting limit at session VWAP), `time_stop_min=60`, entries from
09:45 (his 15-minute rule), cutoff 12:00.
This is the only MEAN-REVERSION-entry-with-a-MEASURED-target rule this
campaign has run. Everything before it was a breakout or a hold.
