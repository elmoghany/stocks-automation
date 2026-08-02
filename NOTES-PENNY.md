# Penny Stocks Trading Notes

Convention: new notes go at the TOP of this file. Each note = a **3-word title**,
then a detailed explanation of what was done and why.
Normal (large-cap wave/value) trading notes live in `NOTES.md`.

---

## News Source Comparison (2026-08-02)

Robinhood MCP has NO news feed (all 53 tools checked; `search` resolves
tickers only). What it has instead: EARNINGS data -- get_earnings_calendar
(market-wide, 31-day window, am/pm timing, high-mcap filter) and
get_earnings_results (8 quarters est-vs-actual EPS per symbol; SCYX next
reports 2026-08-17 pm, tentative). Use for scheduled-catalyst discovery
("which penny biotechs report tomorrow morning?") and earnings-risk checks;
Finnhub stays the rule-2 breaking-news source (timestamps to the second:
SCYX GSK catalyst at 08:04:34, Benzinga). KEY CAVEAT from live test:
Finnhub had NO real catalyst headline for FCUV's +836% day -- only generic
"stocks moving" roundups (which technically pass the 18h rule since they
mention the ticker, but are echo coverage, not catalysts). Sub-1M-float
movers often rip on promotions/filings/social buzz that news APIs miss --
treat the news gate as confirmation, not an absolute veto, when float is
ultra-low and rvol is extreme.

## Robinhood Integration Implemented (2026-08-02)

Wired the Robinhood data into penny-stocks.py + a repeatable workflow:
(1) `data/rh_bars/{SYM}_{DATE}.csv` cache (1-min bars, real premarket
volume, interpolated bars excluded) — _window_data merges them over
yfinance, Robinhood wins on overlapping minutes; (2)
`data/rh_fundamentals.json` cache — float (rule 8 gate, now authoritative:
REPL 77.6M auto-excluded) + sector/industry (rule 4) consulted before
yfinance; (3) RH_SCAN_ID constant = saved server-side scan
5f132877-7730-4a18-9e72-b3f0d2c9df83; (4) rule 1 band now checked AT ENTRY
per bar (like rule 3) instead of at day open — a $1.93 open that runs
through $2+ is tradeable once in band; day filter only requires the band to
be reachable in the window; (5) seeded caches with FCUV Jul 31 premarket
(73 real bars incl. the 8:18-8:30 explosion) + fundamentals for
FCUV/SCYX/TCX/REPL; (6) `.claude/skills/penny-morning.md` = full morning
workflow: run_scan -> refresh caches via MCP -> screen (Finnhub news last)
-> livescreen/livebars (E*TRADE) -> LIMIT order. End-to-end test on merged
real-volume data: optimizer full-ruleset best = trail 20-25% + all-pattern
entries -> $1,000 -> $1,926 (+92.6%) on the one qualifying day (FCUV);
hammer+trail took 1 trade +28.5% (real premarket volume makes vol-confirm
meaningful premarket for the first time — with yfinance it silently
passed on zero volume). Cent-target default on FCUV: 1 trade, -1.9% —
confirms fixed targets waste explosive days; trailing exits capture them.

## Robinhood Data Goldmine (2026-08-02)

Connected the robinhood-trading MCP server (53 tools) and it fills EVERY data
gap yfinance/E*TRADE left, verified live: (1) get_equity_historicals returns
TRUE 1-min OHLCV bars with REAL premarket volume -- FCUV Jul 31 premarket
explosion captured minute-by-minute (8:19 84k shares @ $2.58, 8:20 427k @
$4.38, 8:22 725k @ $7.90, 8:30 601k @ $8.88) where yfinance reported
Volume=0; bars carry session (pre/reg) + interpolated flags; explicit RFC3339
ranges, bounds=extended, split-adjusted; DEPTH: 1-min real at >=2 weeks back
(Jul 20 verified; gone by 3 months), 5-min real at >=3 months -- both beat
yfinance's 7 days. Even 15second/30second intervals exist. (2)
get_equity_fundamentals gives FLOAT directly (FCUV 601K -- 0.6M float
explains the +836% day; SCYX 9.5M, TCX 8.8M pass; REPL 77.6M correctly out),
plus sector/industry (rule 4), avg_volume 2wk/30d + extended-hours day volume
(rvol: FCUV = 21.8x), market cap, PE/PB, 52wk range, company profile. (3)
SCANNER (create_scan/run_scan): full server-side screener on Robinhood's
real-time feed -- created scan 5f132877-7730-4a18-9e72-b3f0d2c9df83 with the
complete rule set: Last BETWEEN $2-16, %Change>=10% (1d, plot=Close --
plot is REQUIRED or the filter errors), RelativeVolume>=5x (1d, length
pinned to 30 by server), Float<=16M; sorted %Change desc; 0 matches on
Sunday (evaluates live day data -- populates Monday premarket). Title stays
'Untitled Scan' (rename only in Legend UI). Filter specs also offer GAP,
VWAP, RSI/MACD/EMA/Bollinger, sector -- room for tighter A+ filters.
Replaces yfinance items #1 (intraday history, better depth + real premarket
vol), #3 (float+sector), #4 (market-wide scan), and most of #2/#6. Morning
workflow upgrade: run_scan (Robinhood, all rules server-side) -> news check
(Finnhub) -> livebars/livescreen (E*TRADE) -> order (E*TRADE). Note: MCP
tools are session-level (Claude calls them); penny-stocks.py python code
still uses yfinance -- for in-script access the robin_stocks python lib with
the same account is the path if needed.

## Etrade Realtime Data (2026-08-02)

Replaced yfinance with E*TRADE real-time data wherever the API allows.
(1) Rules 1/3/5 (price band, up>=10%, rvol>=5x) now compute LIVE from one
batched E*TRADE quote: lastTrade/ExtendedHourQuoteDetail price,
previousClose, totalVolume, averageVolume -- etrade_live_metrics() feeds
screen_symbol(live=...); `screen`/`scan` auto-use it when a token exists
(PROD first, sandbox fallback), yfinance per-symbol fallback otherwise.
Sandbox returns CANNED 2012 data for fixed symbols (ask AMD -> get GOOG),
so sandbox never poisons results (symbols don't match -> fallback).
(2) `livescreen SYMS [--prod]`: full real-time rule table via E*TRADE +
lazy sector/float/news for pre-passers. (3) `livebars SYM [--prod]`: polls
quotes every 10s, assembles LIVE 1-min OHLCV candles (EtradeVolumeFeed.bars),
runs the candlestick engine after each completed minute -- live pattern
detection with true extended-hours volume (fixes yfinance premarket vol=0).
(4) News now Finnhub-first (news_within_18h; FINNHUB_KEY in Credential
Manager; tested live -- caught SCYX's 8:04 AM GSK catalyst headline) with
yfinance fallback, and news is checked LAZILY only after all cheap rules
pass. Float rule <=16M enforced in all commands; E*TRADE quote also returns
sharesOutstanding (float <= sharesOutstanding, usable as sufficient check).
NOT replaceable with E*TRADE: historical intraday bars (no history API --
backtests stay yfinance) and market-wide screening (no screener endpoint --
`scan` stays Yahoo, then livescreen re-verifies real-time). Morning workflow:
scan -> livescreen --prod -> livebars --prod -> place order.

## Two-X Day Hunt (2026-08-02)

Goal: 2x profit in same-day penny trading. Rules consolidated into the sim:
(1) buy AND sell inside the 7-10 AM ET window of the same day -- open
positions force-flattened at the window close (backtest now trades window
bars only); (2) $2-16 band checked PER DAY at the day's window open (was
wrongly using the latest price, which excluded FCUV's monster day because it
ended at $17); (3) up >=10% vs prev close enforced AT ENTRY TIME inside
simulate_trades (prev_close from daily bars); (4) relative volume >=5x the
50-day average required for a day to be tradeable (rvol map in _window_data);
(5) news-within-18h replaces the 7-10AM news rule in the screener
(NEWS_LOOKBACK_HOURS); (6) float <= 16M enforced in ALL trading commands --
_window_data excludes oversized-float symbols before simulating (REPL 59.7M
excluded; unknown float passes best-effort), screener rule8 changed < to <=. Win% columns renamed/changed to Ret% = P&L as % of the
$1000 position. New `optimize` command: trades THE qualifying gapper each day
(biggest gainer meeting 10%+/5x rvol), all-in compounding, grids pct
target/stop AND trailing exits. RESULT (SCYX/TCX/REPL/FCUV, 7d, only Jul 31
FCUV qualified -- +836% window gain): fixed % targets max +6.9%; TRAILING
exits changed everything: trail 20-25% + all-pattern entries -> $1,000 ->
$1,996 (+99.6%) IN ONE DAY == the 2x goal. Key learnings: (a) hammer_family
entries took ZERO trades on the explosive day (marubozu bars, no wicks) --
all-bullish-pattern entry needed on 800% days, hammer calibration was for
normal gappers; (b) yfinance PREMARKET 1-min bars have Volume=0, so the
volume-confirm filter silently passes premarket (avg=0 -> pass) -- volume
confirmation is effectively regular-hours-only; (c) fixed cents/% targets cap
the exact days that can 2x -- ride-the-runner trailing exit is what captures
them; (d) days meeting ALL rules are rare (1 of ~7 days x 4 stocks) -- the 2x
comes from patience for the A+ day, not from daily grinding. Caveat: n=1
qualifying day; thin premarket fills/slippage not modeled; needs live paper
validation.

## Pair Combination Grid (2026-08-02)

Added `pairtest`: every entry signal x every exit signal individually -- 8
bullish candles + rsi_cross_up + macd_cross_up entries, 10 bearish candles +
rsi_cross_down + macd_cross_down exits = 120 combos (target/stop always on,
vol confirm on candles, $1000/trade, 7-10 AM ET, SCYX/TCX/REPL 5d). RSI/MACD
computed on 1-min bars (RSI-14 cross out of 30/70, MACD 12/26/9 signal cross)
in Candles.indicator_bullish/bearish. Findings: (1) exit pattern choice
barely matters -- most exits never fire before target/stop, rows within an
entry table are near-identical; the entry decides the outcome. (2) Profitable
entries: hammer (+$25, only 1 trade), inverted_hammer + bearish_engulfing
exit (+$19.69, 5 trades, 60% -- most robust single pair), dragonfly_doji
(+$5.86 any exit), tweezer_bottom + tweezer_top (+$13). (3) RSI entry lost
(-$19, 10 trades) and MACD entry lost worst (-$75 to -$119, 17 trades) --
oscillator crosses are too slow/noisy for 1-min penny tape; they also never
fire as useful exits. (4) rising_three never formed once (5-candle pattern,
too rare intraday). Conclusion: the hammer FAMILY as a group (+$74) beats
any single pattern -- individual signals are too rare alone; combining the
three wick-rejection candles is what creates enough trades. Defaults stay
hammer_family + vol confirm + strong_if_profit.

## Position Size Grid (2026-08-02)

Changed rule 7 sizing from fixed 1150 shares to POSITION_DOLLARS=$1000 per
trade (shares = $1000 // entry). Added max_trades cap to simulate_trades and
a `gridtest` command: buy-pattern sets x trades/day caps {1,2,3,unlimited},
7-10 AM ET, $1000/trade, sell=strong_if_profit, vol confirm on. Results
(SCYX/TCX/REPL, ~5 days): best = hammer_family with 3/day or unlimited
(identical -- it never fires >3/day): +$74.36 over 8 trades, 62% win,
+$9.29/trade. KEY: capping at 1 trade/day LOSES (-$16, 50% win) -- the
day's first setup is often premature; trades 2-3 carry the profit. Cap 2
= +$41. All non-hammer buy sets lose at every cap. Scaling: P&L is linear
in position size ($1000 -> +$74/wk vs ~$5.5k avg position -> +$713/wk
earlier). At $1000/trade the +$9.29/trade edge is thin vs real frictions
(1-2c spread on ~300 sh = $3-6/round trip) -- needs bigger size or a
tighter-spread stock list to survive costs.

## Candle Window Test (2026-08-01)

Added `candletest` command to penny-stocks.py: grid-tests 5 buy-pattern sets x
4 sell modes on 1-min bars restricted to the 7-10 AM ET window (premarket +
open, prepost=True), and made simulate_trades() configurable (buy_set,
sell_mode). Also switched rule 6 to risk-ratio form: REWARD_RISK=2.0 -> target
+$0.30 vs stop -$0.15 (note: on regular-hours tests the original fixed +$0.18
target actually made more money -- +$1,093 vs +$364 across FCUV/SCYX/TCX --
high win rate beats fat targets on 1-min scalps; small sample though).
7-10 AM grid result (SCYX/TCX/REPL, 5 days): buy=hammer_family (hammer,
inverted hammer, dragonfly doji) WON in all 4 sell modes (+$437..+$908);
every other buy set lost money. Best combo: hammer_family +
strong_if_profit (exit only on bearish engulfing / evening star / 3 black
crows when profitable): +$908 over 10 trades, 60% win. Interpretation:
single-candle wick-rejection signals catch fast premarket dip-inversions;
multi-candle patterns (morning star, rising three) confirm too late for this
window, engulfing whipsaws on thin tape. Caveats: tiny sample; FCUV excluded
(drifted to $17.05, out of band); SCYX had only 17 premarket bars (illiquid);
real premarket spreads are wide -- paper-test before sizing up.
UPDATE: defaults now set (penny stocks only) to hammer_family +
momentum-volume-reversal confirmation (reversal candle volume >= 1.5x
trailing 20-bar avg, ENTRY_VOL_MULT/VOL_AVG_BARS) + strong_if_profit exits.
With vol confirm, 7-10 AM window: +$713 over 8 trades, 62% win (vs +$908/10
without filter -- same per-trade avg, fewer junk entries; the filter also
lifted all_bullish configs from negative to positive). Regular-hours backtest
with the same defaults LOSES money (SCYX -$213, TCX -$196, REPL -$370) --
this is strictly a 7-10 AM morning strategy, matching the news-window rule.

## Penny Stock Strategy (2026-08-01)

Implemented the Cameron Ross momentum day-trading strategy in `penny-stocks.py`
(original prompt saved verbatim in `penny-stock.md`). Screener rules: price
$2-$16, breaking news 7-10 AM ET today, up >=10%, hot sector (AI/biotech/
semis via HOT_SECTORS list), relative volume >=5x the 50-day average, float
under 16M. Trading rules: ~1150-share positions, sell at +$0.18-0.20/share,
hard stop -$0.15/share. Entry engine = 1-min candlestick state machine:
SCAN (find +2% surge within 10 min) -> DIPPING (wait for >=5c retrace) ->
ARMED (buy on first bullish reversal candle: hammer, inverted hammer,
dragonfly doji, bullish spinning top, bullish engulfing, tweezer bottom,
morning star, rising three) -> LONG (exit at target/stop or on bearish
pattern: hanging man, shooting star, gravestone doji, bearish spinning top,
bearish engulfing, tweezer top, evening (doji) star, three black crows,
falling three). CLI: `scan` (discover candidates market-wide via Yahoo screener API, then
full rule check), `screen SYMS`, `patterns SYM`, `backtest SYM --days N`.
The $2-16 band is ENFORCED in backtest/patterns — non-penny stocks (e.g. AMD)
are refused, since cent-based targets only make sense at penny prices. News
rule checks the last SESSION date (weekend scans check Friday's 7-10 AM
window). Day-trading rule: buy and sell always happen the SAME day; any open
position is flattened at the last bar (EOD flatten), never held overnight.
First live scan (Fri Jul 31 2026 session) found 25 gappers;
near-perfect setups FCUV ($11.60, +517%, 45x rvol, 0.4M float), SCYX (+29.8%,
41x rvol, 7.7M float), TCX (+59.2%, 12.6x rvol, 5.7M float) — all failed only
the yfinance news check. Backtests on those three: FCUV +$442 (38 trades),
SCYX +$277 (12 trades, 67% win), TCX +$374 (16 trades) — profitable on real
gappers. yfinance limits: news timestamps approximate/incomplete, float
patchy, 1-min history ~7 days — production needs a real-time scanner feed.
