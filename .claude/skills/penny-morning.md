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
NOT force a trade; the edge comes from patience (see NOTES-PENNY.md).

## Step 2 — Refresh the Robinhood caches for the candidates

Trade the TOP TWO qualifying gappers each day ($15k each, up to $30k
deployed). For each scan hit (top 3 max for cache refresh):
1. `get_equity_fundamentals` (bounds=extended) → update
   `data/rh_fundamentals.json`: keys float, shares_outstanding, market_cap,
   sector, industry, avg_volume_30d, avg_volume_2wk, fetched, source.
2. `get_equity_historicals` symbols=[SYM], interval=minute, bounds=extended,
   start_time=TODAY 11:00Z, end_time=now (window 7AM-NOON ET; 7AM = 11:00 UTC summer,
   12:00 UTC in winter) → write `data/rh_bars/{SYM}_{YYYY-MM-DD}.csv` with
   header `begins_at,open,high,low,close,volume` — SKIP bars where
   interpolated=true. penny-stocks.py merges these over yfinance
   automatically (Robinhood wins on overlapping minutes).

## Step 3 — Verify rules + news (python, uses the caches)

```bash
python penny-stocks.py screen SYM1 SYM2 ...   # 6-rule table; news via
                                              # Finnhub (lazy, last gate)
python penny-stocks.py livescreen SYMS --prod # E*TRADE real-time cross-check
```

Trade only symbols passing ALL rules including news-within-18h.

## Step 4 — Watch for the entry, then order

```bash
python penny-stocks.py livebars PICK --prod   # live 1-min candles + patterns
```

Entry per current calibration (NOTES-PENNY.md, 2026-08-03): DEFAULT =
any bullish reversal pattern OR opening-range breakout (break of the
first-3-volume-bars high), no volume gate, RIDE with a 20% trailing stop
and a -5% hard stop. Position ~$15k (capped at 10% of bar volume; PDT
needs $25k+ equity). Expect roughly: half of qualifying days trade, ~60%
of traded days win, losses capped ~-$1,500, profit concentrated in a few
big trailing winners. ALWAYS flat by NOON.

Orders go through E*TRADE (LIMIT only):
```bash
python test_extended_order.py --session EXTENDED --account 0   # preview
# add --confirm to place; needs daily prod token (--auth / --verifier)
```

## Backtesting note

Backtests run offline against merged Robinhood-CSV + yfinance data:
`python penny-stocks.py backtest SYM --days 7` (also candletest / gridtest /
pairtest / optimize). To backtest a past gapper day properly, fetch its
1-min bars via `get_equity_historicals` for that date (bounds=extended) and
write the CSV first — Robinhood 1-min history reaches ~2+ weeks back,
5minute reaches ~3+ months (write 5-min caches for older dates).

## Rules recap (all enforced in penny-stocks.py)

Gate ORDER (lazy -- each stage only runs if the prior passed):
1. FREE: price $2+ (no ceiling) + up >=10% + rvol >=5x (one quote/history call)
2. HALAL: loans/mcap <=10%, deposits/mcap <=10%, combined <=20%, haram
   revenue <5%, no haram industry (see /halal-check) -- FIRST expensive
   gate so no time is wasted on non-halal stocks
3. hot sector (float rule DROPPED 2026-08-03 -- float shown as info only)
4. news within 18h (Finnhub first, Yahoo second -- FH:/YF: tags)
Trading: buy AND sell inside the same day's 7AM-noon window, force-flat
at window close; $2 floor and +10% re-checked AT ENTRY per bar (NO price ceiling);
trade top-2 qualifying gappers/day.
WARNING from live testing: low-mcap gappers frequently fail halal on the
cash or debt ratio (small mcap denominator) -- expect the halal gate to
eliminate many scanner hits; that is by design.
