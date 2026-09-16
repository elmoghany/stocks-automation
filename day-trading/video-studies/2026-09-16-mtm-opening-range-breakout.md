# "The Opening Range Breakout Strategy That Prints Money Every Morning (ORB)"

- Master The Market | 2026-07-01 | 9:33 | 1.5k views | `h87RSv5xeOY`
- Transcript pulled with yt-dlp; the watch-skill MCP could not acquire
  YouTube this session (see the VS2 pre-registration in NOTES). What that
  costs is the frame/OCR channel: rules that are only DRAWN on the chart
  and never spoken are not captured. Everything below was spoken.

## CLAIM
"$250 per day is $5,000 per month." One live example (GBH, +$250).

## EXACT MECHANICS
- **Opening range** = the first 5 minutes of price action AFTER 09:30.
  On a 1-minute chart, candles 1-5. He states the level for the day's
  example ($4.32) and says he got it "by using the high of that first 5
  minutes".
- **Entry** = buy the break of the OR high (filled $4.38 on a $4.32
  level -- a stop-buy just through it).
- **Risk level** = the LOW of the opening range. "Relatively tight and
  small risk by using the low of that opening range."
- **Profit**: "most of these are going to go maybe 10 or 15% above their
  opening range breakout level before they start to come back down... it
  is very important to secure your profits into those 10 and 15% moves."
- **1-minute refinement**: the better entry is the RETEST -- price pushes
  through the level, "comes right back down into that breakout level,
  turns it into a bit of support, before starting the next leg up".
- **Selection**: gapping up strongly into the open, low float, strong
  volume, short-sale restricted, a news catalyst; narrow to 3-5 names.

## WHAT NEEDS FUTURE INFORMATION
- "Take profit into daily/weekly resistance" is a discretionary level off
  a higher timeframe. **UNTESTABLE-AS-STATED**; the causal stand-in is
  his own numeric one, +10% / +15% off the entry.
- "Short-sale restricted" needs the SSR list as of that date (no feed
  here). "Low float" was measured and rejected in the V-series.

## HALAL
Long-only, cash, same-day. Compatible. Only the selection filters would
need extra data.

## CONFIG MAPPING
`V1ORB` (+10% bank), `V1ORBb` (+15%, entries to 12:00), `V1ORBr` (2R),
`V1ORBx` (the retest refinement), `V1ORBe` (ride the 9 EMA out).
Engine: new `or_clock=(09:30, 5)` + `struct_floor_mode="or_low"`.
**THIS IS NOT THE ENGINE'S EXISTING `orb`**: that one anchors the range
on the first bars of the SIM WINDOW, which under rotation starts at
07:00, i.e. a PREMARKET opening range. The 09:30 range is a different
object and has never been tested in this campaign.
