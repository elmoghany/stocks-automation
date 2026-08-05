---
description: Penny-stock morning workflow — Robinhood scan, cache refresh, screen, live watch, order (7AM-noon ET)
---

The full Cameron Ross morning workflow. Data sources: Robinhood MCP
(scanner, 1-min bars with real premarket volume, float/sector), Finnhub
(news 18h), E*TRADE (live quotes/volume + orders). Run during 7AM-noon ET.

## Step 1 — Run the saved Robinhood scan (all rules server-side)

Call MCP tool `run_scan` with scan_id `5f132877-7730-4a18-9e72-b3f0d2c9df83`
(filters: Last >$2 NO CEILING, %Change>=10% 1d, RelVolume>=5x 30d,
sorted %Change desc; C1 adopted 2026-08-03: ceiling+float removed). Results are live. If empty: no A+ gapper today — DO
NOT force a trade; the edge comes from patience (see NOTES-DAYTRADING.md).

## Step 2 — Refresh the Robinhood caches for the candidates

DAY PICK (calm-gap rule, $15k/day total): among qualifying gappers,
trade the HIGHEST-GAIN one whose 7AM price is <= prev_close x 1.20 --
if the leader gapped hotter than +20% at 7AM it is an exhausted
overnight move (they bleed); walk down to the next calm one (check top
4), else skip the day. The $2k+ days are intraday developers: modest
7AM gap, then a +100-300% session run our trail rides. For each scan hit (top 3 max for cache refresh):
1. `get_equity_fundamentals` (bounds=extended) → update
   `data/rh_fundamentals.json`: keys float, shares_outstanding, market_cap,
   sector, industry, avg_volume_30d, avg_volume_2wk, fetched, source.
2. `get_equity_historicals` symbols=[SYM], interval=minute, bounds=extended,
   start_time=TODAY 11:00Z, end_time=now (window 7AM-NOON ET; 7AM = 11:00 UTC summer,
   12:00 UTC in winter) → write `data/rh_bars/{SYM}_{YYYY-MM-DD}.csv` with
   header `begins_at,open,high,low,close,volume` — SKIP bars where
   interpolated=true. day-trading.py merges these over yfinance
   automatically (Robinhood wins on overlapping minutes).

## Step 3 — Verify rules + news (python, uses the caches)

```bash
python day-trading.py screen SYM1 SYM2 ...   # 6-rule table; news via
                                              # Finnhub (lazy, last gate)
python day-trading.py livescreen SYMS --prod # E*TRADE real-time cross-check
```

Trade only symbols passing ALL rules including news-within-18h.

## Step 4 — Watch for the entry, then order

```bash
python day-trading.py livebars PICK --prod   # live 1-min candles + patterns
```

Entry per current calibration (NOTES-DAYTRADING.md, 2026-08-04, C02 spec):
DEFAULT = any bullish reversal pattern OR 5-minute opening-range breakout
(break of the first-5-volume-bars high) OR premarket-high stop-buy (break
of the premarket high, one-shot), no volume gate, entry only while price
>= prev_close x1.10. Size up to 20% of trailing 10-MINUTE volume (was
10%/5min). RIDE with a PRESSURE-MODULATED trail (C21): base 20% from peak, TIGHTEN
to 10% when rolling 10-min sell pressure <= -0.3, WIDEN to 40% when buy
pressure >= +0.3 (pressure = volume-weighted close position in bar
range, 20k-share floor); -8% hard stop; bank 1/3 at +25% UNLESS buyers
still dominate (P >= +0.3) -- then keep the full position riding.
Ignore lone 1-bar wicks >3x surrounding closes when tracking peaks. EVERYTHING flat
by NOON same day (1PM extension tested and withdrawn by user).
(C21: Y1 +$395,243 / Y2 +$519,641, ZERO negative months both years;
avg +22.6% of capital per trading day; 93% survives 10bps slippage.)
UNIVERSE: any clean ticker >= $2 -- NO price ceiling (the $75 cap
silently deleted the mid/large-cap earnings gappers that carried
Jan-Mar 2025; scanner must not cap price). Live halal via current
data IS point-in-time correct; walk up to 8 calm candidates for the
first compliant one. Position ~$15k (capped at 20% of trailing 10-min volume; PDT needs
$25k+ equity). Expect roughly: half of qualifying days trade, ~3 of 4
traded days win, losses capped ~-$1,500, profit concentrated in a few
big trailing winners. ALWAYS flat by NOON.

UNFILLED-BUY RULE (1 minute): place LIMIT at trigger +0.5%; if not
filled in 60s, CANCEL. If price ran <= +2% above trigger, re-place at
market price once; beyond +2% DO NOT CHASE -- the ORB ratchet re-arms
at each new high and will produce the next trigger. If price fell back
below the trigger, cancel and wait (pullback often gives a pattern
entry). In paper sessions log both the assumed trigger fill AND the
price 60s later -- that spread is the live slippage measurement.

UNFILLED-SELL RULES (asymmetric: sells are NEVER abandoned):
- Stop/trail exits: limit at stop level -1% (marketable); unfilled in
  60s -> escalate to bid -2%, repeat every 60s until flat. Position
  size <= 20% of 10-min volume guarantees exit liquidity exists.
- Scale-out +25%: NOT a resting limit (the C21 skip decides at the
  touch using pressure) -- the 1-min watcher sells with a marketable
  limit when banking is chosen.
- Pressure-flip/bearish exits: marketable limit -0.5%, same 60s
  escalation.
- NOON FLATTEN: start 11:57 at bid -1%, escalate 11:59 to bid -2%;
  flat by 12:00 without exception.
- Known residual: halt/gap-throughs fill at the reopen, not the stop
  (sim behaves the same; the backtest's worst day was exactly this).

Orders go through E*TRADE (LIMIT only):
```bash
python test_extended_order.py --session EXTENDED --account 0   # preview
# add --confirm to place; needs daily prod token (--auth / --verifier)
```

## Backtesting note

Backtests run offline against merged Robinhood-CSV + yfinance data:
`python day-trading.py backtest SYM --days 7` (also candletest / gridtest /
pairtest / optimize). To backtest a past gapper day properly, fetch its
1-min bars via `get_equity_historicals` for that date (bounds=extended) and
write the CSV first — Robinhood 1-min history reaches ~2+ weeks back,
5minute reaches ~3+ months (write 5-min caches for older dates).

## Rules recap (all enforced in day-trading.py)

Gate ORDER (lazy -- each stage only runs if the prior passed):
1. FREE: price $2+ (no ceiling) + up >=10% + rvol >=5x (one quote/history call)
2. HALAL: loans/mcap <=10%, deposits/mcap <=10%, combined <=20%, haram
   revenue <5%, no haram industry (see /halal-check) -- FIRST expensive
   gate so no time is wasted on non-halal stocks
3. hot sector (float rule DROPPED 2026-08-03 -- float shown as info only)
4. news within 18h (Finnhub first, Yahoo second -- FH:/YF: tags)
Trading: buy AND sell inside 7AM-noon, force-flat at noon; $2 floor and +10% re-checked AT ENTRY per bar (NO price ceiling);
trade top-2 qualifying gappers/day.
WARNING from live testing: low-mcap gappers frequently fail halal on the
cash or debt ratio (small mcap denominator) -- expect the halal gate to
eliminate many scanner hits; that is by design.

## Paper-session ops hardening (2026-08-05, after the Day-2 timer stall)

The Day-2 background agent's single 5-min background timer silently
died 10:34-11:42 ET (78-min coverage gap). Mandatory pattern for every
future paper session:

1. DUAL TIMERS: every cycle the agent arms TWO staggered background
   timers (300s scan timer + 600s backup). On wake it checks the log's
   last-cycle timestamp: if the cycle already ran, the backup exits
   quietly; if not, it runs the cycle. Never rely on a single timer.
2. MAIN-SESSION WATCHDOG: the coordinating session keeps a ~25-min
   ScheduleWakeup loop that checks data/paper/{date}.md mtime; if
   stale >10 min during session hours, SendMessage-nudge the agent
   (it died once already: "no active task" on nudge = it was dead).
3. STRUCTURED DAY FILES (user directive): every session produces, in
   the repo, alongside the markdown log:
   - data/paper/{date}.md      -- narrative log (existing format)
   - data/paper/{date}.json    -- machine-readable: config, trades
     (entry/exit px, times, sizes, P&L), every candidate with per-gate
     decisions (rvol ours-vs-RH, halal ratios, calm-gap open vs
     prev_close, instrument-type), coverage_gaps, lessons
   - data/paper/news/{date}/{SYM}.json -- Finnhub headlines for EVERY
     symbol that appeared on the scan that day (script:
     python plan/paper_news.py DATE SYM SYM ...), fetched same day
     (free tier only reaches back ~1 year; same-day capture is cheap
     and permanent)
   All three are committed+pushed at close-out with the day's verdict.
