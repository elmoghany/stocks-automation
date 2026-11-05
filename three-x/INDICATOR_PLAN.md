# AMD indicator test plan

Backtest only, no orders. Daily bars, long-only, cash between trades, last 3 years. Started 2026-11-05.

## Goal

Find buy and sell signals that replace counting days, and are right at least 75% of the time.

## Tested so far

- **Standard indicators:** RSI, stochastic, stochRSI, CCI, ROC, MACD, moving average crosses, distance from averages, z-score, Bollinger, Keltner, OBV, MFI, ADX, Aroon, Heikin-Ashi, Supertrend.
- **Price action:** highs and lows over any lookback, time since them, swing retracements, candle patterns, divergences, volume spikes.
- **Context:** VIX, QQQ, SMH, relative strength, earnings timing, VWAP from reports, volatility.
- **Result:** many pass 75% on one period, but scrambled data does about as well, so none is proven yet. See `results/amd_ta_brainstorm.csv` and `results/amd_ta_rules.csv`.

## Repos checked

TradingView's scripts are read for the idea only, rewritten in Python and not run on TradingView. No downloaded code is run.

| Repo (github.com/) | Indicators | License | Use |
|---|---|---|---|
| everget/tradingview-pinescript-indicators | ~187 Pine | GPL-3.0 | High |
| deepentropy/lightweight-charts-indicators | 1,869 TypeScript ports | MIT, some MPL-2.0 upstream | High, noisy |
| xgboosted/pandas-ta-classic | ~240 Python | MIT | High |
| romulodl/ttj-indicators | 47 Pine | None, ideas only | High |
| freqtrade/technical | ~35 Python | GPL-3.0 | Medium |
| facioquo/stock-indicators-dotnet | 86 C# | Apache-2.0 | Medium |
| just-nilux/legendary_ta | ~6 Python | None, ideas only | Niche |
| Ooples-Finance-LLC/OoplesFinance.StockIndicators | 774 C# | Apache-2.0 | Catalog |
| ArunKBhaskar/PineScript | ~15 Pine | MPL-2.0 | ICT ideas |
| Heavy91/TradingView_Indicators | 4 Pine | None, ideas only | Low |
| pAulseperformance/awesome-pinescript | Link list | MIT | Pointers |

Avoided because they look ahead: centered DPO, Ichimoku chikou, whole-window regression bands, repainting Nadaraya-Watson, forward-looking fractals and zigzag.

## New indicators to test

- **Trend and adaptive:** KAMA, FRAMA, TRAMA, OTT, AlphaTrend, SSL.
- **Momentum:** QQE, WaveTrend, Stochastic Connors RSI, Laguerre RSI, CTI, Trendscore, Phase Change Index.
- **Volatility:** Squeeze Momentum, Williams VIX Fix, Waddah Attar, Volatility Ratio.
- **Volume:** VFI, VPCI, NVI, Weis Wave, Pocket Pivot.
- **Reversal:** Leledc exhaustion, TD Setup, liquidity sweep, failure swing.
- **Market structure:** fair value gap first touch, market structure trailing stop.
- **Regime, as filters:** Hurst, Choppiness, Stiffness.

## How each one is tested

A signal counts as working only if it passes all of these, in order. This list is fixed before any result.

1. **No look-ahead:** the signal is identical when later data is removed.
2. **Reliable in 2025-26:** at least 75% right, on at least 5 signals. Right means +15% before -15% (wide), or +10% before -5% (tight). Sells are the mirror image. Both are compared with any day, because AMD's rise makes buys look good.
3. **Reliable in 2024:** at least 75% on at least 3 signals. 2024 played no part in choosing it.
4. **Better than luck:** more signals pass than on data rotated by a random shift.
5. **Makes money in Vibe-Trading:** beats holding in 2025-26 and loses less than holding in 2024, with at least 4 buys.
6. **Lumibot agrees:** an independent re-run gives a similar result.

## Order of work

1. Test all new indicators alone, and with a short fixed list of filters.
2. Backtest what passes, along with the two earlier buy pairs: down 5% in 2 days while SMH is within 5% of its high, and RSI(2) below 45 while QQQ is below its 100-day average.
3. Look for a filter that tells a 2024-type market from a 2025-type one, since most of the difference lies there.
4. Try different signal types in pairs only if a single type shows something real, to avoid fishing.
5. If anything passes everything, test it on years before 2023, which it has never seen, with the user's approval, then consider tracking it on paper. Real money needs the user's explicit go-ahead.

## Limits

Three years and 12 reports is a small sample. Passing 75% on 5 to 10 signals can still be luck, which is why steps 3 to 6 exist. Any result here comes from AMD's own history and a strong rise.
