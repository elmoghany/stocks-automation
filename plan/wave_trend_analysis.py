"""Test: Does adding trend/slope filter improve returns?
Also: Does using 2Y data for params vs 1Y data give better FORWARD results?

Question 1: Should we only buy when the trend is UP?
Question 2: Should we calibrate params from 2Y history instead of 1Y?
"""

import numpy as np
import pandas as pd
import yfinance as yf

TOP_STOCKS = ["FIX", "VRT", "LRCX", "AMD", "TSM", "ANET", "AMSC", "MLI", "MPWR"]
LOOKBACK = 5
CASH = 100_000


def ema(closes, period):
    return closes.ewm(span=period, adjust=False).mean()


# ============================================================
# STRATEGY A: No trend filter (current approach)
# ============================================================
def backtest_no_filter(closes, highs, dip, sell):
    cash = CASH
    trades = []
    in_trade = False
    ep = q = 0

    for i in range(LOOKBACK, len(closes)):
        p = float(closes.iloc[i])
        if not in_trade:
            rh = float(highs.iloc[max(0, i - LOOKBACK):i].max())
            if (rh - p) / rh * 100 >= dip and cash > p:
                q = int(cash // p); ep = p; cash -= q * p; in_trade = True
        else:
            if (p - ep) / ep * 100 >= sell:
                cash += q * p
                trades.append({"g": round((p-ep)/ep*100, 1), "d": i})
                in_trade = False

    final = cash + (q * float(closes.iloc[-1]) if in_trade else 0)
    return round((final - CASH) / CASH * 100, 1), len(trades)


# ============================================================
# STRATEGY B: Only buy when EMA20 > EMA50 (uptrend)
# ============================================================
def backtest_uptrend_only(closes, highs, dip, sell):
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)

    cash = CASH
    trades = []
    in_trade = False
    ep = q = 0

    for i in range(50, len(closes)):
        p = float(closes.iloc[i])
        e20 = float(ema20.iloc[i])
        e50 = float(ema50.iloc[i])
        uptrend = e20 > e50

        if not in_trade:
            rh = float(highs.iloc[max(0, i - LOOKBACK):i].max())
            if uptrend and (rh - p) / rh * 100 >= dip and cash > p:
                q = int(cash // p); ep = p; cash -= q * p; in_trade = True
        else:
            if (p - ep) / ep * 100 >= sell:
                cash += q * p
                trades.append({"g": round((p-ep)/ep*100, 1), "d": i})
                in_trade = False

    final = cash + (q * float(closes.iloc[-1]) if in_trade else 0)
    return round((final - CASH) / CASH * 100, 1), len(trades)


# ============================================================
# STRATEGY C: Only buy when price > EMA50 AND EMA20 > EMA50 (strong uptrend)
# ============================================================
def backtest_strong_uptrend(closes, highs, dip, sell):
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)

    cash = CASH
    trades = []
    in_trade = False
    ep = q = 0

    for i in range(50, len(closes)):
        p = float(closes.iloc[i])
        e20 = float(ema20.iloc[i])
        e50 = float(ema50.iloc[i])
        strong = e20 > e50 and p > e50

        if not in_trade:
            rh = float(highs.iloc[max(0, i - LOOKBACK):i].max())
            if strong and (rh - p) / rh * 100 >= dip and cash > p:
                q = int(cash // p); ep = p; cash -= q * p; in_trade = True
        else:
            if (p - ep) / ep * 100 >= sell:
                cash += q * p
                trades.append({"g": round((p-ep)/ep*100, 1), "d": i})
                in_trade = False

    final = cash + (q * float(closes.iloc[-1]) if in_trade else 0)
    return round((final - CASH) / CASH * 100, 1), len(trades)


# ============================================================
# STRATEGY D: Adaptive -- uptrend uses tight dip, downtrend uses wide dip
# ============================================================
def backtest_adaptive_trend(closes, highs, dip, sell):
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)

    cash = CASH
    trades = []
    in_trade = False
    ep = q = 0

    for i in range(50, len(closes)):
        p = float(closes.iloc[i])
        e20 = float(ema20.iloc[i])
        e50 = float(ema50.iloc[i])
        uptrend = e20 > e50

        # Adaptive: tight dip in uptrend, wide in downtrend
        actual_dip = dip if uptrend else dip * 2.5
        actual_sell = sell if uptrend else sell * 0.5  # take quick profits in downtrend

        if not in_trade:
            rh = float(highs.iloc[max(0, i - LOOKBACK):i].max())
            if (rh - p) / rh * 100 >= actual_dip and cash > p:
                q = int(cash // p); ep = p; cash -= q * p; in_trade = True
        else:
            if (p - ep) / ep * 100 >= actual_sell:
                cash += q * p
                trades.append({"g": round((p-ep)/ep*100, 1), "d": i})
                in_trade = False

    final = cash + (q * float(closes.iloc[-1]) if in_trade else 0)
    return round((final - CASH) / CASH * 100, 1), len(trades)


def best_params(closes, highs, strategy_fn):
    best = (-999, 2.5, 11)
    for d in [1.5, 2, 2.5, 3, 3.5, 4, 5]:
        for s in [6, 8, 10, 11, 12, 13, 15]:
            ret, _ = strategy_fn(closes, highs, d, s)
            if ret > best[0]:
                best = (ret, d, s)
    return best[1], best[2], best[0]


def main():
    print("=" * 130)
    print("  QUESTION 1: DOES TREND FILTER IMPROVE RETURNS?")
    print("=" * 130)
    print()

    # Test 4 strategies on 1Y data
    print(f"  {'Stock':<6} | {'No Filter':>12} {'#':>3} | {'Uptrend':>12} {'#':>3} | "
          f"{'Strong Up':>12} {'#':>3} | {'Adaptive':>12} {'#':>3} | {'Best'}")
    print(f"  {'-'*110}")

    totals = {"A": 0, "B": 0, "C": 0, "D": 0}
    wins = {"A": 0, "B": 0, "C": 0, "D": 0}

    for sym in TOP_STOCKS:
        print(f"  Fetching {sym}...", end=" ", flush=True)
        tk = yf.Ticker(sym)
        df = tk.history(period="1y")
        if df.empty:
            print("NO DATA"); continue

        c = df["Close"]; h = df["High"]

        _, _, retA = best_params(c, h, backtest_no_filter)
        _, nA = backtest_no_filter(c, h, *best_params(c, h, backtest_no_filter)[:2])

        _, _, retB = best_params(c, h, backtest_uptrend_only)
        _, nB = backtest_uptrend_only(c, h, *best_params(c, h, backtest_uptrend_only)[:2])

        _, _, retC = best_params(c, h, backtest_strong_uptrend)
        _, nC = backtest_strong_uptrend(c, h, *best_params(c, h, backtest_strong_uptrend)[:2])

        _, _, retD = best_params(c, h, backtest_adaptive_trend)
        _, nD = backtest_adaptive_trend(c, h, *best_params(c, h, backtest_adaptive_trend)[:2])

        best_label = max([("A", retA), ("B", retB), ("C", retC), ("D", retD)], key=lambda x: x[1])
        for label, ret in [("A", retA), ("B", retB), ("C", retC), ("D", retD)]:
            totals[label] += ret
            if ret == best_label[1]:
                wins[label] += 1

        print(f"{retA:>+11.0f}% {nA:>3} | {retB:>+11.0f}% {nB:>3} | "
              f"{retC:>+11.0f}% {nC:>3} | {retD:>+11.0f}% {nD:>3} | {best_label[0]}")

    n = len(TOP_STOCKS)
    print(f"  {'-'*110}")
    print(f"  {'AVG':<6} | {totals['A']/n:>+11.0f}%     | {totals['B']/n:>+11.0f}%     | "
          f"{totals['C']/n:>+11.0f}%     | {totals['D']/n:>+11.0f}%     |")
    print(f"  {'WINS':<6} | {wins['A']:>11}     | {wins['B']:>11}     | "
          f"{wins['C']:>11}     | {wins['D']:>11}     |")

    print(f"\n  A = No filter (current)")
    print(f"  B = Only buy in uptrend (EMA20 > EMA50)")
    print(f"  C = Only buy in strong uptrend (price > EMA50 AND EMA20 > EMA50)")
    print(f"  D = Adaptive (tight dip in uptrend, wide dip + quick exit in downtrend)")

    # ============================================================
    print(f"\n{'='*130}")
    print(f"  QUESTION 2: SHOULD WE USE 2Y DATA TO CALIBRATE PARAMS?")
    print(f"  Test: calibrate on first year, test on second year (walk-forward)")
    print(f"{'='*130}\n")

    print(f"  {'Stock':<6} | {'1Y params on 1Y':>16} | {'2Y params on 1Y':>16} | "
          f"{'1Y-only calib':>16} | {'2Y calib better?':>18}")
    print(f"  {'-'*90}")

    y1_wins = 0; y2_wins = 0

    for sym in TOP_STOCKS:
        print(f"  Fetching {sym} 2Y...", end=" ", flush=True)
        tk = yf.Ticker(sym)
        df2 = tk.history(period="2y")
        df1 = tk.history(period="1y")
        if df2.empty or df1.empty or len(df2) < 200:
            print("NO DATA"); continue

        c1 = df1["Close"]; h1 = df1["High"]
        c2 = df2["Close"]; h2 = df2["High"]

        # Calibrate on 1Y, test on 1Y (current approach)
        d1, s1, ret_1y_on_1y = best_params(c1, h1, backtest_no_filter)

        # Calibrate on 2Y, apply those params on last 1Y
        d2, s2, _ = best_params(c2, h2, backtest_no_filter)
        ret_2y_on_1y, _ = backtest_no_filter(c1, h1, d2, s2)

        better = "2Y" if ret_2y_on_1y > ret_1y_on_1y else "1Y"
        if better == "2Y":
            y2_wins += 1
        else:
            y1_wins += 1

        print(f"d{d1}/s{s1} {ret_1y_on_1y:>+6.0f}% | "
              f"d{d2}/s{s2} {ret_2y_on_1y:>+6.0f}% | "
              f"d{d1}/s{s1} {ret_1y_on_1y:>+6.0f}% | "
              f"{'>> 2Y BETTER' if better == '2Y' else '1Y better'}")

    print(f"\n  Result: 1Y calibration wins {y1_wins}/{len(TOP_STOCKS)}, "
          f"2Y calibration wins {y2_wins}/{len(TOP_STOCKS)}")

    # ============================================================
    print(f"\n{'='*130}")
    print(f"  QUESTION 3: WALK-FORWARD TEST -- calibrate on year 1, trade year 2")
    print(f"  (Most realistic test: uses only past data, no future peeking)")
    print(f"{'='*130}\n")

    print(f"  {'Stock':<6} | {'Y1 calib':>10} | {'Y2 forward':>12} {'#Tr':>4} | "
          f"{'Y2 B&H':>8} | {'Wave vs B&H':>12}")
    print(f"  {'-'*65}")

    total_fwd = 0; total_bah2 = 0; n_fwd = 0

    for sym in TOP_STOCKS:
        tk = yf.Ticker(sym)
        df2 = tk.history(period="2y")
        if df2.empty or len(df2) < 400:
            continue

        c_all = df2["Close"]; h_all = df2["High"]
        midpoint = len(c_all) // 2

        # Year 1: calibrate
        c_y1 = c_all.iloc[:midpoint]; h_y1 = h_all.iloc[:midpoint]
        d_cal, s_cal, ret_cal = best_params(c_y1, h_y1, backtest_no_filter)

        # Year 2: forward test with Y1 params
        c_y2 = c_all.iloc[midpoint:]; h_y2 = h_all.iloc[midpoint:]
        fp2 = float(c_y2.iloc[0]); lp2 = float(c_y2.iloc[-1])
        bah2 = round((lp2 - fp2) / fp2 * 100, 1)

        ret_fwd, n_fwd_trades = backtest_no_filter(c_y2, h_y2, d_cal, s_cal)

        total_fwd += ret_fwd; total_bah2 += bah2; n_fwd += 1
        vs = ret_fwd - bah2

        print(f"  {sym:<6} | d{d_cal}/s{s_cal} {ret_cal:>+5.0f}% | {ret_fwd:>+11.0f}% {n_fwd_trades:>4} | "
              f"{bah2:>+7.0f}% | {vs:>+11.0f}% {'WAVE' if vs > 0 else 'B&H'}")

    if n_fwd > 0:
        print(f"  {'-'*65}")
        print(f"  {'AVG':<6} | {'':>10} | {total_fwd/n_fwd:>+11.0f}%      | "
              f"{total_bah2/n_fwd:>+7.0f}% | {(total_fwd-total_bah2)/n_fwd:>+11.0f}%")

    # ============================================================
    print(f"\n{'='*130}")
    print(f"  CONCLUSIONS")
    print(f"{'='*130}")
    print(f"""
  1. TREND FILTER:
     Look at which strategy won above (A/B/C/D).
     If A (no filter) wins, trend doesn't help -- just buy every dip.
     If B/C wins, adding trend filter avoids buying in downtrends.
     If D wins, adaptive approach is best -- different behavior per regime.

  2. 1Y vs 2Y CALIBRATION:
     If 1Y wins, recent data is more relevant -- market regimes change.
     If 2Y wins, more data captures more patterns -- more robust.

  3. WALK-FORWARD:
     This is the most honest test. If wave beats B&H using only past-calibrated
     params, the strategy is genuinely predictive, not just curve-fitted.
""")


if __name__ == "__main__":
    main()
