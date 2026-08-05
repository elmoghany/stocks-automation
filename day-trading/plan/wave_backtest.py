"""Backtest mean reversion strategy on 21 PASS stocks over 1 year.
Find optimal parameters per stock for wave trading."""

import json
import numpy as np
import pandas as pd
import yfinance as yf

SYMBOLS = [
    "LRCX", "TSM", "VRT", "AMSC", "AMD", "LLY", "ANET", "FIX",
    "TDW", "TJX", "MLI", "RMD", "HUBB", "ETN", "CDNS", "DECK",
    "AWI", "ISRG", "CTAS", "BMI", "FICO",
]


def sma(closes, period=20):
    return closes.rolling(window=period).mean()


def bollinger_bands(closes, period=20, num_std=2.0):
    middle = sma(closes, period)
    std = closes.rolling(window=period).std()
    return middle, middle + num_std * std, middle - num_std * std


def rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(high, low, close, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()


def backtest_stock(symbol, df):
    """Backtest mean reversion on 1 year of daily data.

    Strategy: Buy when RSI < buy_threshold AND price < lower BB.
              Sell when RSI > sell_threshold OR price > upper BB OR stop hit.

    Test multiple parameter combos and find the best for this stock.
    """
    if df is None or len(df) < 60:
        return None

    closes = df["Close"]
    highs = df["High"]
    lows = df["Low"]
    volumes = df["Volume"]

    # Compute indicators once
    sma_20 = sma(closes, 20)
    bb_mid, bb_upper, bb_lower = bollinger_bands(closes, 20, 2.0)
    rsi_14 = rsi(closes, 14)
    atr_14 = atr(highs, lows, closes, 14)
    avg_vol = volumes.rolling(20).mean()

    # Stock characteristics
    avg_price = float(closes.mean())
    price_std = float(closes.std())
    avg_daily_range = float((highs - lows).mean())
    avg_atr = float(atr_14.dropna().mean())
    volatility = float(closes.pct_change().std() * np.sqrt(252) * 100)

    # Typical wave amplitude: average distance from trough to peak
    # Find local mins and maxs using 5-day windows
    wave_highs = closes.rolling(10, center=True).max()
    wave_lows = closes.rolling(10, center=True).min()
    wave_amplitudes = ((wave_highs - wave_lows) / wave_lows * 100).dropna()
    avg_wave_pct = float(wave_amplitudes.mean())
    median_wave_pct = float(wave_amplitudes.median())

    # How often does RSI go below thresholds?
    rsi_below_30_pct = float((rsi_14 < 30).sum() / len(rsi_14) * 100)
    rsi_below_35_pct = float((rsi_14 < 35).sum() / len(rsi_14) * 100)
    rsi_above_70_pct = float((rsi_14 > 70).sum() / len(rsi_14) * 100)
    rsi_above_65_pct = float((rsi_14 > 65).sum() / len(rsi_14) * 100)

    # How often does price touch or cross Bollinger bands?
    below_lower_bb = float((closes < bb_lower).sum() / len(closes) * 100)
    above_upper_bb = float((closes > bb_upper).sum() / len(closes) * 100)

    # Backtest with the strategy
    # Try RSI buy thresholds: 30, 35
    # Try RSI sell thresholds: 65, 70
    # Try stop multipliers: 1.5, 2.0
    best_result = {"score": -999, "total_trades": 0, "wins": 0, "losses": 0,
                    "win_rate": 0, "total_pnl_pct": 0, "avg_pnl_pct": 0,
                    "avg_hold_days": 0, "max_win_pct": 0, "max_loss_pct": 0}
    best_params = {"rsi_buy": 30, "rsi_sell": 70, "stop_multiplier": 1.5}

    for rsi_buy in [28, 30, 33, 35, 38, 40]:
        for rsi_sell in [60, 65, 70, 75]:
            for stop_mult in [1.5, 2.0, 2.5]:
                trades = simulate(closes, rsi_14, bb_lower, bb_upper, bb_mid, atr_14,
                                  rsi_buy, rsi_sell, stop_mult)
                if len(trades) >= 2:
                    wins = sum(1 for t in trades if t["pnl"] > 0)
                    total_pnl = sum(t["pnl"] for t in trades)
                    avg_pnl = total_pnl / len(trades)
                    win_rate = wins / len(trades) * 100
                    avg_hold = np.mean([t["hold_days"] for t in trades])

                    # Score: win_rate * avg_pnl (want both high)
                    score = win_rate * avg_pnl if avg_pnl > 0 else avg_pnl

                    if best_result is None or score > best_result["score"]:
                        best_result = {
                            "score": score,
                            "total_trades": len(trades),
                            "wins": wins,
                            "losses": len(trades) - wins,
                            "win_rate": round(win_rate, 1),
                            "total_pnl_pct": round(total_pnl, 2),
                            "avg_pnl_pct": round(avg_pnl, 2),
                            "avg_hold_days": round(avg_hold, 1),
                            "max_win_pct": round(max(t["pnl"] for t in trades), 2),
                            "max_loss_pct": round(min(t["pnl"] for t in trades), 2),
                        }
                        best_params = {
                            "rsi_buy": rsi_buy,
                            "rsi_sell": rsi_sell,
                            "stop_multiplier": stop_mult,
                        }

    return {
        "symbol": symbol,
        "avg_price": round(avg_price, 2),
        "volatility_annualized": round(volatility, 1),
        "avg_atr": round(avg_atr, 2),
        "avg_atr_pct": round(avg_atr / avg_price * 100, 2),
        "avg_wave_pct": round(avg_wave_pct, 1),
        "median_wave_pct": round(median_wave_pct, 1),
        "rsi_below_30_freq": round(rsi_below_30_pct, 1),
        "rsi_below_35_freq": round(rsi_below_35_pct, 1),
        "rsi_above_70_freq": round(rsi_above_70_pct, 1),
        "below_lower_bb_freq": round(below_lower_bb, 1),
        "above_upper_bb_freq": round(above_upper_bb, 1),
        "best_params": best_params,
        "best_result": best_result,
    }


def simulate(closes, rsi_vals, bb_lower, bb_upper, bb_mid, atr_vals,
             rsi_buy_thresh, rsi_sell_thresh, stop_mult):
    """Simulate trades: buy when RSI < threshold AND price < lower BB.
    Sell when RSI > sell_thresh OR price > upper BB OR stop hit."""
    trades = []
    in_trade = False
    entry_price = 0
    entry_day = 0
    stop_price = 0

    for i in range(30, len(closes)):
        price = closes.iloc[i]
        rsi_val = rsi_vals.iloc[i]
        lower = bb_lower.iloc[i]
        upper = bb_upper.iloc[i]
        mid = bb_mid.iloc[i]
        atr_val = atr_vals.iloc[i]

        if pd.isna(rsi_val) or pd.isna(lower) or pd.isna(atr_val):
            continue

        if not in_trade:
            # Entry: RSI below threshold AND price at/below lower band
            if rsi_val < rsi_buy_thresh and price <= lower:
                entry_price = price
                entry_day = i
                stop_price = price - stop_mult * atr_val
                in_trade = True
        else:
            # Exit conditions
            hold_days = i - entry_day
            exit_reason = None

            if price <= stop_price:
                exit_reason = "stop_loss"
            elif rsi_val > rsi_sell_thresh and price >= upper:
                exit_reason = "target_upper_band"
            elif rsi_val > rsi_sell_thresh and price >= mid:
                exit_reason = "target_sma"
            elif hold_days >= 15:
                exit_reason = "time_stop"

            if exit_reason:
                pnl_pct = (price - entry_price) / entry_price * 100
                trades.append({
                    "entry": round(float(entry_price), 2),
                    "exit": round(float(price), 2),
                    "pnl": round(pnl_pct, 2),
                    "hold_days": hold_days,
                    "reason": exit_reason,
                })
                in_trade = False

    return trades


def main():
    results = []
    for sym in SYMBOLS:
        print(f"Analyzing {sym}...", end=" ", flush=True)
        try:
            t = yf.Ticker(sym)
            df = t.history(period="1y")
            if df.empty:
                print("NO DATA")
                continue
            result = backtest_stock(sym, df)
            if result:
                results.append(result)
                bp = result.get("best_params", {})
                br = result.get("best_result", {})
                print(f"Trades={br.get('total_trades',0)} WinRate={br.get('win_rate',0)}% "
                      f"TotalPnL={br.get('total_pnl_pct',0)}% RSI_buy={bp.get('rsi_buy','?')} "
                      f"RSI_sell={bp.get('rsi_sell','?')}")
            else:
                print("INSUFFICIENT DATA")
        except Exception as e:
            print(f"ERROR: {e}")

    # Save results
    with open("plan/wave_stock_stats.json", "w") as f:
        json.dump(results, f, indent=2)

    # Print summary table
    print("\n" + "=" * 120)
    print(f"{'Stock':<7} {'Vol%':>6} {'ATR%':>6} {'Wave%':>6} {'RSI<30':>7} {'RSI>70':>7} "
          f"{'<LBB':>5} {'>UBB':>5} {'Trades':>6} {'WinR%':>6} {'PnL%':>7} {'AvgPnL':>7} "
          f"{'RSIb':>5} {'RSIs':>5} {'Stop':>5}")
    print("-" * 120)
    for r in sorted(results, key=lambda x: x.get("best_result", {}).get("total_pnl_pct", 0), reverse=True):
        bp = r.get("best_params", {})
        br = r.get("best_result", {})
        print(f"{r['symbol']:<7} {r['volatility_annualized']:>5.1f}% {r['avg_atr_pct']:>5.2f}% "
              f"{r['avg_wave_pct']:>5.1f}% {r['rsi_below_30_freq']:>6.1f}% {r['rsi_above_70_freq']:>6.1f}% "
              f"{r['below_lower_bb_freq']:>4.1f}% {r['above_upper_bb_freq']:>4.1f}% "
              f"{br.get('total_trades', 0):>6} {br.get('win_rate', 0):>5.1f}% "
              f"{br.get('total_pnl_pct', 0):>6.2f}% {br.get('avg_pnl_pct', 0):>6.2f}% "
              f"{bp.get('rsi_buy', '?'):>5} {bp.get('rsi_sell', '?'):>5} {bp.get('stop_multiplier', '?'):>5}")


if __name__ == "__main__":
    main()
