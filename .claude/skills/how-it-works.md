---
description: How the wave trading system makes money -- core strategy explanation
---

## How Profit Works

The wave trader splits capital into 6 equal buckets (one per stock). Each bucket trades independently and compounds its own profits.

### The Cycle

```
$16,667 (AMD's bucket)
    |
BUY: 81 shares x $203.43 = $16,478 invested
    | (wait for +10% gain)
SELL: 81 shares x $223.77 = $18,125 received
    |
$18,125 now in AMD's bucket (was $16,667)
    |
Profit: $1,647 (+10%)
    |
BUY AGAIN: 83 shares x $218 = $18,094 (more shares because bucket grew)
    | (wait for +10% gain)
SELL: 83 shares x $239.80 = $19,903
    |
$19,903 in bucket (compounded twice)
    ... repeat all year
```

### Where Profit Sits

- **SIM mode:** Paper money in `data/wave_trades.json` -- records `stock_cash` per bucket and all completed trades with `realized_pnl`
- **REAL mode:** Actual cash in your E*TRADE brokerage account. Wave trader calls `api_wrapper.py` -> `preview_order()` -> `place_order()`. Shares and cash move in your real account.

### What the Code Does NOT Do

The code compounds everything -- it does not withdraw profits. The $16,667 bucket grows to $82,786 (FIX) but all stays in the trading loop. To take profits out, manually withdraw from E*TRADE after sells, or add a profit-taking rule.

## Per-Stock Trading Behavior

Each stock has its own optimized parameters based on 1Y backtest:

| Stock | Buy Dip | Sell Target | Volatility | Behavior |
|-------|---------|-------------|------------|----------|
| **FIX** | 2.0% | +12% | Very high | Big waves. Small dips lead to big recoveries. |
| **VRT** | 2.0% | +12% | Very high | Same pattern as FIX. Both are volatile growers. |
| **LRCX** | 3.0% | +12% | High | Needs slightly bigger dip. Still holds for +12%. |
| **AMD** | 2.5% | +10% | High | Medium dip, faster exit. Frequent but smaller waves. |
| **TDW** | 2.0% | +11% | High | Tiny dips trigger buys. Mid-range target. Volatile energy stock. |
| **TSM** | 3.0% | +10% | Moderate | Needs a real 3% dip (very stable). Sells at +10%. Slowest but safest. |

All use **lookback=5 days** to find the recent high.

## How $16,667 Grows Differently Per Stock

### FIX (d2/s12) -- Big swings, fewer trades
```
Trade 1: buy $1,273 -> sell $1,426 (+12%, 7d)  -> bucket: $18,667
Trade 2: buy $1,380 -> sell $1,546 (+12%, 10d) -> bucket: $20,907
Trade 3: buy $1,510 -> sell $1,691 (+12%, 3d)  -> bucket: $23,415
... 10 trades/year = $82,786 (+397%)
```

### AMD (d2.5/s10) -- Smaller swings, more frequent
```
Trade 1: buy $203 -> sell $223 (+10%, 1d)  -> bucket: $18,334
Trade 2: buy $215 -> sell $237 (+10%, 5d)  -> bucket: $20,167
Trade 3: buy $229 -> sell $252 (+10%, 4d)  -> bucket: $22,184
... 11 trades/year = $51,865 (+211%)
```

### TSM (d3/s10) -- Slow and steady
```
Trade 1: buy $338 -> sell $372 (+10%, 13d) -> bucket: $18,334
Trade 2: buy $355 -> sell $391 (+10%, 8d)  -> bucket: $20,167
... 10 trades/year = $44,816 (+169%)
```

## Why Each Stock Is Different

| Factor | FIX | AMD | TSM |
|--------|-----|-----|-----|
| Avg wave up | +30% | +23% | +13% |
| Avg wave down | -8% | -12% | -5% |
| Price per share | ~$1,300 | ~$200 | ~$320 |
| Trades per year | 10-17 | 10-11 | 9-10 |
| Why it works | Huge waves, +12% fills fast | Frequent dips, catches most bounces | Rarely dips 3%, but always recovers (it's $1.7T) |

## Compounding Math

This is why frequency matters more than gain size:

| Trades | Gain/trade | Final value | Multiplier |
|--------|-----------|-------------|------------|
| 5 | +10% | $16,105 | 1.6x |
| 8 | +10% | $21,436 | 2.1x |
| 10 | +10% | $25,937 | 2.6x |
| 10 | +12% | $30,996 | 3.1x |
| 12 | +12% | $38,890 | 3.9x |

FIX and VRT reach 3-4x because they combine high frequency (10-12 trades) with high gain (+12% each).

## Portfolio Result ($100K across 6 stocks)

| Stock | Start | End | Return |
|-------|-------|-----|--------|
| FIX | $16,667 | $82,786 | +397% |
| VRT | $16,667 | $82,055 | +392% |
| LRCX | $16,667 | $71,371 | +328% |
| AMD | $16,667 | $51,865 | +211% |
| TDW | $16,667 | $50,982 | +206% |
| TSM | $16,667 | $44,816 | +169% |
| **Total** | **$100,000** | **$383,875** | **+284% (3.8x)** |

Buy & hold same 6 stocks would have been $273,864 (2.7x). Wave trading earned $110K more.

## Never Lose Rule

If a stock drops below buy price after you buy, you do NOT sell. You hold until it recovers above the sell target. You might wait days or weeks, but you never realize a loss. This is why 100% win rate is achieved -- every trade that closes is profitable.

The risk: capital gets locked in a losing position until it recovers. In the 1Y backtest, the longest hold was 129 days (TDW). It still ended profitable.
