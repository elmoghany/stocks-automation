# Video study: "How I'd Trade $4 Into $2,000 In Only 5 Days"

- **Source**: https://youtu.be/-xuQXmQWMCk (Riley Coleman, ~22 min)
- **Watched**: 2026-08-09 · watch-skill index `7627e6d22231d9a2`
  (follow-ups: `watch-skill ask 7627e6d22231d9a2 "<question>"`)
- **Market/instrument**: S&P 500 futures (ES / micro MES), 1-minute
  chart, long AND short, ~45-60 min of trading per morning
- **Claimed result in the video**: one live short worth ~+$5,000 at 3R
  with $1,500 risked; he says he started at <$100/trade and scaled

## The strategy, step by step (his 5-step entry checklist)

1. **LOCATION (15-min chart, before anything else)**
   Mark key support/resistance zones: overnight high/low, prior-day
   extremes, 2-touch trendlines. Trades are only hunted AT these
   zones — "the first thing I'm looking for isn't an entry, it's
   location." Also check the macro news calendar (Forex Factory, US,
   high-impact releases) so nothing surprises you intraday.

2. **CATALYST: the "unhealthy move" (5-min chart)**
   An overextended thrust — candles abnormally large vs the recent
   ones (he visualizes with a fair-value-gap indicator; the FVG boxes
   mark the overextension). Thesis: overextended moves tend to be
   given back; the snapback is the trade. Works best to the downside
   ("when the market sells off, it sells off very quickly").

3. **TREND BROKEN (1-min chart)**
   Do not predict the reversal — wait for the swing structure to
   actually flip: after an uptrend (higher highs/lows), demand a
   printed LOWER LOW. "I like to wait until the market has actually
   shown me the downtrend has started."

4. **FAILED CONTINUATION (the trap)**
   After the structure break, wait for the market to ATTEMPT to
   resume the old trend — and get rejected (big opposing candle
   immediately after the attempt). The trapped traders on the failed
   attempt fuel the move.

5. **ENTRY TRIGGER: stop-market beyond the rejection extreme**
   Order sits below the rejection low (short) — you are filled only
   if price confirms through it. No fill = no trade. If the checklist
   isn't met, "I shut down for the day and go do something else."

## Trade management (what he actually does in the live example)

- **Stop at structure**: above the failed-attempt high — the risk R
  is defined by the setup's geometry, not a fixed %.
- **Targets**: beginners → fixed bracket at 2R or 3R ("a 30-40% win
  rate is enough at 2-3R"). The math: at 1:3, one win pays for three
  losses; never take negative risk-reward.
- **When the move accelerates**: trail the stop candle-by-candle
  ("every time a candlestick closes, I move it above the high").
- **At 3R unrealized**: tighten the trail — protect the win, stay in
  only if it keeps "printing candlesticks lower."
- **Exit context beats R-math**: near the next 15-min support zone he
  expects a bounce and refuses to donate profits back; he was stopped
  at ~3R (+$5,000) as the market bounced exactly there.

## What our experiments already proved about these ideas

Independent of the video, our campaigns had already validated cousins
of half of it (convergent evidence is worth noting):
- His "wait until the market has shown you" = our first-crossing rule
  (V100: waiting for the +10% print is FREE, even slightly positive).
- His trapped-trader reversal candle = our Trigger C (2% surge, 5c
  dip, bullish reversal candle) — already in every champion.
- His "location first" premarket-high anchoring = our coil signal
  (price/premarket-high), the strongest causal rank we ever measured.
- His news-day awareness = our per-name news flags proved USELESS as
  a rank (Z-campaign) — but macro-calendar gating is untested.

## Experiments derived (F-series, on the Z104/C37 base)

| id | video idea | our translation | status |
|----|-----------|-----------------|--------|
| F001 | enter only on break beyond the confirmation candle | pattern entries become STOP-BUYS above the pattern candle high (fill only on break) | queued |
| FC01 | control | stop-buy below the pattern LOW (nonsense direction, must fail) | queued |
| F002 | stop at structure, not fixed % | stop = min of last 3 lows at entry, capped at -8% | queued |
| F003 | fixed 2R bracket | target = entry + 2x structure-risk, no scale-out | queued |
| F004 | fixed 3R bracket | same at 3R | queued |
| F007 | tighten at 3R | trail drops to 10% once unrealized >= 3x initial risk | queued |
| F008 | unhealthy-move snapback | new entry trigger: outsized down-thrust inside an up-gapped name, stop-buy above first bullish candle | wave 2 |
| F009 | macro news calendar | no NEW tickets +/-30 min around CPI/FOMC/NFP releases | wave 2 (needs date table) |
| F010 | acceleration candle-trail | when candle range >= 2x ATR(10), stop = prior candle low | wave 2 |

Guardrails as always: both years vs the champion, adjacency, controls
must fail, identity gates after every engine edit.

## Results

(to be filled when the F-series completes)

## Honest fit assessment

His edge lives in two-sided index reversals with structure stops —
our system is long-only single-name momentum. The mechanics that
translate are the ENTRY CONFIRMATION geometry and the R-based exit
brackets; the reversal-shorting core does not. Expectation set
accordingly: F001/F002 are the serious candidates (they refine
mechanics we know work), the brackets likely fight our fat-tail
economics (scale-out/trail already beat fixed targets in the
S-campaign — but never R-structure-based ones, hence the test).
