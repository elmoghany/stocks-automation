---
description: Run or manage the wave trader (Never Lose swing trading system)
---

## Strategy: Never Lose + Smart Exhaustion

Three methods per stock (see `/wave-methodology` for full details):
1. **Original** -- buy dips, sell gains, no protection
2. **Smart Exhaust** -- pause 30d after N consecutive wins, 10% dip override during pause
3. **Exh+Lock** -- exhaust + lock profits at Lx multiplier

Each stock has its own optimized method, params, and exhaustion threshold.

## Top 10 Stocks (per-stock optimized)

| Stock | Method | Dip | Sell | LB | Extra | Return |
|-------|--------|-----|------|----|-------|--------|
| VRT | Exhaust | 2.0% | +12% | 5 | N=6 | +495% |
| LRCX | Exhaust | 3.0% | +15% | 10 | N=3 | +442% |
| FIX | Exhaust | 2.5% | +11% | 10 | N=10 | +441% |
| AMSC | Exh+Lock | 3.0% | +13% | 7 | N=7,L=4x | +352% |
| AMD | Exh+Lock | 2.5% | +10% | 7 | N=5,L=4x | +317% |
| MPWR | Exhaust | 3.0% | +11% | 5 | N=3 | +220% |
| TSM | Exhaust | 3.5% | +15% | 5 | N=6 | +175% |
| ANET | GainLock | 4.0% | +15% | 5 | L=2.5x | +159% |
| ONTO | Exhaust | 2.5% | +15% | 10 | N=4 | +129% |
| HUBB | Exhaust | 3.5% | +6% | 10 | N=5 | +127% |

## Portfolio Backtest Results ($100K)

| Approach | Final | Return |
|----------|-------|--------|
| Top 10 per-stock optimized | $385,640 | 3.9x |
| All 39 halal stocks (smart exhaust) | avg +85% | 1.85x |
| Buy & hold | avg +52% | 1.52x |

## Running

```bash
# SIM mode (paper trading, $100K starting cash)
python -m trading.wave_main --mode SIM --ignore-hours

# Sandbox (E*TRADE sandbox API)
python -m trading.wave_main --mode SANDBOX --account 0

# Real (production, live orders)
python -m trading.wave_main --mode REAL --account 0
```

## Key Files

| File | Purpose |
|------|---------|
| `trading/wave_main.py` | Entry point, hourly polling loop |
| `trading/wave_trader.py` | Core logic, trade lifecycle, Never Lose rules |
| `trading/wave_config.py` | Per-stock params, swap pairs, defaults |
| `trading/wave_indicators.py` | Bollinger Bands, RSI, ATR, SMA |
| `trading/wave_sectors.py` | Sector momentum and rotation |
| `data/wave_trades.json` | Active + completed trades |
| `data/wave_orders.json` | All order attempts (statistics) |

## Features

- **Per-stock calibrated parameters** from 1Y backtest
- **Sector rotation** -- buys in oversold sectors first
- **Wash sale protection** -- skip blocked stocks, swap to similar stock
- **Never Lose** -- hold until profitable, no stop losses
- **Lookback 5 days** -- key finding: shorter memory = more trades = more compounding

## Recalibrating

Run backtests quarterly to update per-stock params:

```bash
# Brute force find best params per stock
python plan/wave_backtest_all21.py

# Test specific dip/sell combos
python plan/wave_backtest_final.py

# AMD-specific 3x search
python plan/wave_backtest_amd_3x.py

# Wave pattern analysis
python plan/wave_analysis.py
```

Then update `trading/wave_config.py` with new optimal params.
