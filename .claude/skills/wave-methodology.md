---
description: Wave trading methodology -- per-stock parameters, methods, and how they work
---

## Core Strategy: Never Lose

Buy dips, sell recoveries, never sell at a loss. 100% capital per stock bucket. Compound profits.

## Three Methods

### 1. Original
- Buy when price dips X% from recent N-day high
- Sell when price gains Y% above buy price
- Never sell at a loss -- hold until profitable
- No protection against buying at exhausted peaks
- Best for: stocks with few trades or no long winning streaks

### 2. Smart Exhaustion
- Same buy/sell as Original
- **After N consecutive wins, pause 30 days**
- During pause: if stock drops **10%+ from pause-start price**, override and buy the deep dip
- N varies per stock (found via backtest)
- Prevents buying at peaks after winning streaks
- Best for: most stocks (26/39 benefit from this)

### 3. Exhaust + Gain Lock (Combined)
- Same as Smart Exhaustion
- **Plus: if cash hits Lx multiplier, stop trading entirely**
- Locks profits and walks away
- Best for: volatile stocks that can crash after big runs (AMD, AMSC)

## Per-Stock Optimized Parameters (from 1Y backtest)

| Stock | Method | Dip | Sell | LB | Extra | Return |
|-------|--------|-----|------|----|-------|--------|
| VRT | Exhaust | 2.0% | +12% | 5 | N=6 | +495% |
| LRCX | Exhaust | 3.0% | +15% | 10 | N=3 | +442% |
| FIX | Exhaust | 2.5% | +11% | 10 | N=10 | +441% |
| AMSC | Exh+Lock | 3.0% | +13% | 7 | N=7, L=4x | +352% |
| AMD | Exh+Lock | 2.5% | +10% | 7 | N=5, L=4x | +317% |
| MPWR | Exhaust | 3.0% | +11% | 5 | N=3 | +220% |
| TSM | Exhaust | 3.5% | +15% | 5 | N=6 | +175% |
| ANET | GainLock | 4.0% | +15% | 5 | L=2.5x | +159% |
| ONTO | Exhaust | 2.5% | +15% | 10 | N=4 | +129% |
| HUBB | Exhaust | 3.5% | +6% | 10 | N=5 | +127% |
| JBL | Exhaust | 3.0% | +12% | 5 | N=4 | +119% |
| ARM | Exhaust | 1.5% | +10% | 5 | N=5 | +114% |
| MLI | GainLock | 2.5% | +6% | 10 | L=2x | +106% |
| REGN | Exhaust | 5.0% | +6% | 5 | N=6 | +106% |
| CEG | GainLock | 1.5% | +8% | 5 | L=2x | +102% |
| PH | Exhaust | 2.0% | +10% | 5 | N=6 | +97% |
| ROST | Original | 3.0% | +6% | 10 | -- | +84% |
| SNPS | Exhaust | 4.0% | +8% | 5 | N=5 | +70% |
| IR | Exhaust | 1.5% | +6% | 5 | N=3 | +66% |
| AIT | Exhaust | 5.0% | +11% | 7 | N=4 | +61% |
| MLM | Exhaust | 1.5% | +6% | 5 | N=5 | +55% |
| LLY | Exhaust | 1.5% | +15% | 7 | N=3 | +53% |
| TT | Exhaust | 1.5% | +6% | 5 | N=5 | +51% |
| AWI | Exhaust | 1.5% | +6% | 5 | N=5 | +40% |
| CDNS | Exhaust | 1.5% | +13% | 5 | N=4 | +37% |
| LMB | Exhaust | 1.5% | +8% | 5 | N=7 | +30% |
| GWW | Original | 3.0% | +12% | 5 | -- | +27% |
| RMD | Exhaust | 2.0% | +8% | 5 | N=4 | +18% |
| PNR | Exhaust | 1.5% | +10% | 10 | N=3 | +15% |
| COST | Original | 3.0% | +6% | 7 | -- | +14% |
| SHW | Original | 5.0% | +10% | 7 | -- | +11% |
| ISRG | Exhaust | 4.0% | +6% | 5 | N=3 | +7% |
| SNPS duplicate removed |
| AAON | Original | 3.0% | +11% | 10 | -- | +6% |
| LII | Exhaust | 3.5% | +8% | 5 | N=3 | +2% |
| MANH | Exhaust | 3.0% | +10% | 5 | N=3 | -8% |
| BMI | Original | 1.5% | +10% | 5 | -- | -12% |
| IOT | Original | 1.5% | +10% | 7 | -- | -14% |
| TGLS | Original | 2.0% | +8% | 10 | -- | -34% |
| DOCS | Exhaust | 1.5% | +10% | 5 | N=5 | -41% |

## Parameter Explanation

| Parameter | What it means | Range | Impact |
|-----------|--------------|-------|--------|
| **Dip%** | Stock must drop this much from recent high to buy | 1.5-5% | Lower = more trades = more compounding. Higher = fewer but safer entries |
| **Sell%** | Gain above buy price needed to sell | +6% to +15% | Lower = faster exits, more trades. Higher = bigger gains per trade |
| **Lookback** | Days to look back for "recent high" | 5, 7, 10 | 5 = short memory, more signals. 10 = longer memory, remembers higher peaks |
| **N wins** | Consecutive wins before exhaustion pause | 3-10 | Lower = pauses sooner (safer). Higher = more trades before pause |
| **L (lock)** | Multiplier at which to stop trading | 2x-5x | Locks profits and walks away. Prevents giving back gains |
| **Pause days** | How long to pause after exhaustion | 30 days | Fixed. During pause, only buys 10%+ dips (override) |
| **Dip override** | During pause, buy if stock drops this much | 10% | Catches crashes during the rest period |

## Method Selection Guide

| Stock behavior | Best method | Why |
|---------------|-------------|-----|
| Long winning streaks then crash | **Exhaust** | Pauses before the crash |
| Volatile with big swings | **Exh+Lock** | Locks gains before reversal |
| Steady grower, few trades | **Original** | No winning streaks to exhaust |
| Spikes to 2-3x quickly | **GainLock** | Lock and walk away |

## Stats

- **5 stocks hit 4x+** (>300%): VRT, LRCX, FIX, AMSC, AMD
- **15 stocks hit 2x+** (>100%)
- **Avg return: +104%** vs B&H +52%
- **Method distribution:** Exhaust 26, Original 8, GainLock 3, Exh+Lock 2
- **Top 10 portfolio ($100K):** $385,640 (3.9x)

## Recalibration

Run quarterly to update per-stock params:
```bash
python plan/wave_best_method_per_stock.py
```
Then update `trading/wave_config.py` with new optimal params per stock.

## Halal Filter (applied before wave trading)

Only trade stocks that pass all 3 criteria:
- Loans/MCap <= 10% (or combined <= 20%)
- Cash/MCap <= 10% (or combined <= 20%)
- Haram revenue < 5%

7 stocks excluded as haram: TDW, SHOO, PHM, TSCO, BKE, EXP, FTDR
See `/halal-check` skill for details.
