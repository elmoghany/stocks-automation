# Video study: "This Boring Day Trading Strategy Grew a Small Account to $10,000/month"

- **Source**: https://www.youtube.com/watch?v=I0CCwV427Lw
- **Watched**: 2026-08-10 · index `7dbedebfbb35c65b`
- **Instrument**: index FUTURES (minis/micros; NinjaTrader/Tradeify
  prop-style broker), long AND short. Trader background: options ->
  futures day trading.

## HALAL VERDICT (first)

**NOT halal as taught** — same profile as the Riley Coleman study:
futures contracts + shorting + leveraged/prop accounts. No further
engineering on the strategy as a whole.

## Mechanics taught

1. **ORB (opening range breakout)** on 15-minute candles — break above
   = long, below = short (they trade the break, not the chase).
2. **~50% retest entry**: after the breakout candle, expect a pullback
   of ~half the move on the next candle; enter there.
3. **Bands as trend filter**: stay with trades only while the trend
   bands stay green ("if you're just using bands for trend, they're
   great").
4. **KPLs (key pivot levels)**: prior structure levels as areas of
   interest, not signals.

## Overlap with our validated/rejected set

- ORB: already core to our system (5-min flavor, stop-buys).
- 50% retest entry: the G-series JUST rejected the retest family on
  our gappers (control beat every real level) — this is the same
  mechanic, weaker form. No retest.
- KPLs/location: coil already carries this and won the Z-campaign.
- **Bands trend filter: the one untested mechanic.** Translation: an
  EMA-cloud trend gate (e.g., 9>21 EMA on 1-min) required at entry.
  Candidate for the consolidated H-series — logged, with the honest
  prior that entry-side GATES have lost 100% of their trials here.

## Experiments

No standalone series. "Band trend gate at entry" goes to the H-series
dedupe pool (H-candidate: ema_gate=(9,21) required green at fill).

## Verdict

Nothing adoptable directly (haram wrapper; mechanics either already
ours, already rejected, or queued for the consolidated test).
