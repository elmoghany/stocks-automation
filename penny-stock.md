# Penny Stock Strategy (Cameron Ross) — Original Prompt

Saved 2026-08-01. Implemented in `penny-stocks.py`.

## Prompt (verbatim)

add another python file for trading pennystock, call it penny-stocks.py and in
it add the following cameron ross strategy.

1) screen stocks to trade only penny stocks between $2 and $16.
2) stock has to have breaking news that day in the early morning from 7 am to
   10 am est.
3) stock has to be up at least 10+%
4) stock has to be in hot sector or high demand sector this period i.e. ai
   stocks, biotech
5) stock has to have relative volume of 5x the normal volume for the last 50
   day moving average ... 5x relative volume.
6) avg per share gain 0.18, avg loss per share 0.15
7) avg position 1150
8) stocks with float under 16m
9) use candle sticks for entry and sell positions using 1 min candle i.e.
   bullish hammer, inverted hammer, dragonfly doji, bullish spinning top,
   bullish englufing, tweezer bottom, morning star, rising three. and use
   neutral doji, and use bearish candle sticks like hanging man, shooting
   star, gravestone doji, bearish spinning top, engulfing bearish, tweezer
   tops, evening dojistar, three black crows, evening star, falling three.
   for this point if we want to summarize it, it would be a strong surge
   followed by a dip, then buy when the dip inverts to up upward. and then
   sell when reaching 0.18 or 0.2 profit per share.

## How it maps to code

| Rule | Where in `penny-stocks.py` |
|---|---|
| 1. Price $2–$16 | `PRICE_MIN` / `PRICE_MAX`, `screen_symbol()` |
| 2. News 7–10 AM ET today | `NEWS_START` / `NEWS_END`, yfinance news timestamps |
| 3. Up ≥10% | `MIN_DAY_GAIN_PCT` |
| 4. Hot sector (AI, biotech…) | `HOT_SECTORS` substring match on sector/industry |
| 5. 5x relative volume vs 50d avg | `MIN_REL_VOLUME`, `REL_VOLUME_LOOKBACK` |
| 6. +$0.18 gain / −$0.15 stop | `GAIN_PER_SHARE`, `GAIN_PER_SHARE_MAX`, `LOSS_PER_SHARE` |
| 7. ~1150 share position | `POSITION_SHARES` |
| 8. Float < 16M | `MAX_FLOAT` |
| 9. 1-min candlestick entry/exit | `Candles` class + `simulate_trades()` state machine: SCAN → surge → DIPPING → ARMED → buy on bullish reversal → LONG → sell at target/stop/bearish pattern |

## Commands

```bash
python penny-stocks.py screen SYM1 SYM2 ...     # 6-rule screener table
python penny-stocks.py patterns SYM             # label today's 1-min candles
python penny-stocks.py backtest SYM --days 5    # sim trades on recent 1-min data
```

## Known data limitations (yfinance)

- News timestamps are approximate/incomplete — a production scanner needs a
  real-time news feed (Benzinga, etc.).
- `floatShares` is patchy for small caps (shows `?` when missing).
- 1-min history only goes back ~7 days.
