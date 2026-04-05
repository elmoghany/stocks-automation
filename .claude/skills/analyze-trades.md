---
description: Analyze SIM trading performance -- P&L, win rate, sector breakdown from data/trades.json
---

Trade log format (each entry in data/trades.json):
```json
{"timestamp": "ISO", "action": "BUY|SELL", "symbol": "X", "quantity": N, "price": P, "total": T, "reason": "...", "sector": "Tech|Energy|Minerals"}
```

SIM starts with $100,000 initial cash.

Steps:
1. Read `data/trades.json`. If it doesn't exist or is empty, tell the user no trade data is available.
2. Read `data/portfolio_state.json` if it exists (has holdings, cash, total_value).
3. Compute and display:
   - **Summary**: total trades, buys, sells, date range
   - **Round-trips**: match BUY/SELL pairs per symbol (FIFO). For each completed round-trip: P&L = (sell_price - buy_price) * qty. Show count, total P&L, win rate (% profitable).
   - **By sector**: P&L and trade count for Tech, Energy, Minerals
   - **Best/worst**: largest single winner and loser (symbol, P&L, dates)
   - **Open positions**: symbols bought but not fully sold, with unrealized P&L if portfolio_state.json has current prices
   - **Cash remaining**: from portfolio_state.json or computed from $100k minus net buys
4. If `data/trading.log` exists, report the date range and approximate number of cycles (count lines matching "=== Cycle").
5. Present as a concise table. Flag concerning patterns (one sector dominating losses, win rate below 40%, heavy concentration in few stocks).
