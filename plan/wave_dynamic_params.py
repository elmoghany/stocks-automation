"""Backtest dynamic parameters vs fixed on all 39 halal stocks.

Dynamic 1: Sell% scales down when price is overextended above 200d MA
Dynamic 2: Dip% scales with current ATR vs average ATR
Dynamic 3: Time-based sell reduction (lower target after 20+ days held)
Dynamic ALL: All three combined
"""

import numpy as np
import pandas as pd
import yfinance as yf

HALAL_STOCKS = [
    "FIX", "VRT", "LRCX", "AMD", "MPWR", "TSM", "ANET", "REGN",
    "ONTO", "AMSC", "ROST", "JBL", "MLI", "PH", "HUBB", "ARM",
    "AIT", "MLM", "LLY", "CEG", "TT", "AWI", "CDNS", "GWW",
    "IR", "PNR", "RMD", "COST", "LMB", "SHW", "ISRG", "SNPS",
    "AAON", "LII", "BMI", "MANH", "IOT", "TGLS", "DOCS",
]

CASH = 100_000
PAUSE_DAYS = 30
DIP_OVERRIDE = 10


def ema(closes, period):
    return closes.ewm(span=period, adjust=False).mean()


def atr(high, low, close, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([high-low, (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()


def best_base(closes, highs):
    """Find best base dip/sell/lookback."""
    best = (-999, 2.5, 11, 5, 6)
    for d in [1.5, 2, 2.5, 3, 3.5, 4, 5]:
        for s in [6, 8, 10, 11, 12, 13, 15]:
            for lb in [5, 7, 10]:
                for nw in [3, 4, 5, 6, 7, 8, 10, 99]:
                    f = run_exhaust(closes, highs, d, s, lb, nw, None, None, None)
                    if f > best[0]:
                        best = (f, d, s, lb, nw)
    return best[1], best[2], best[3], best[4]


def run_exhaust(closes, highs, dip, sell, lookback, max_wins,
                ema200=None, atr_vals=None, avg_atr=None,
                dynamic_sell=False, dynamic_dip=False, dynamic_time=False):
    """Run with optional dynamic adjustments."""
    cash = CASH; in_trade = False; ep = q = ed = 0; trades = 0; peak = CASH
    consec = 0; pause_until = 0; pause_price = 0

    start = max(lookback, 200 if ema200 is not None else lookback)

    for i in range(start, len(closes)):
        p = float(closes.iloc[i])

        # Dynamic dip: scale with ATR
        actual_dip = dip
        if dynamic_dip and atr_vals is not None and avg_atr is not None:
            cur_atr = float(atr_vals.iloc[i])
            mean_atr = float(avg_atr.iloc[i])
            if not pd.isna(mean_atr) and mean_atr > 0:
                vol_ratio = cur_atr / mean_atr
                actual_dip = dip * max(0.5, min(2.0, vol_ratio))

        # Dynamic sell: reduce when overextended
        actual_sell = sell
        if dynamic_sell and ema200 is not None:
            e200 = float(ema200.iloc[i])
            if e200 > 0:
                above_200 = (p - e200) / e200 * 100
                if above_200 > 50:
                    actual_sell = sell * 0.4
                elif above_200 > 30:
                    actual_sell = sell * 0.6
                elif above_200 > 15:
                    actual_sell = sell * 0.8

        if not in_trade:
            if i < pause_until:
                if pause_price > 0 and (pause_price-p)/pause_price*100 >= DIP_OVERRIDE and cash > p:
                    q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True; consec = 0
                continue

            rh = float(highs.iloc[max(0, i-lookback):i].max())
            if (rh-p)/rh*100 >= actual_dip and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
        else:
            hold_days = i - ed
            gain = (p - ep) / ep * 100

            # Dynamic time: reduce target over time
            time_sell = actual_sell
            if dynamic_time:
                if hold_days > 40:
                    time_sell = max(1.0, actual_sell * 0.3)
                elif hold_days > 30:
                    time_sell = max(1.0, actual_sell * 0.5)
                elif hold_days > 20:
                    time_sell = max(1.0, actual_sell * 0.75)

            if gain >= time_sell:
                cash += q * p; trades += 1; in_trade = False; consec += 1
                if cash > peak: peak = cash
                if max_wins < 99 and consec >= max_wins:
                    pause_until = i + PAUSE_DAYS; pause_price = p; consec = 0

    final = cash + (q * float(closes.iloc[-1]) if in_trade else 0)
    return final


def main():
    rows = []
    print("Testing dynamic parameters on 39 halal stocks...\n", flush=True)

    for sym in HALAL_STOCKS:
        try:
            tk = yf.Ticker(sym)
            df = tk.history(period="1y")
            if df.empty or len(df) < 200: continue
            c = df["Close"]; h = df["High"]; l = df["Low"]
            fp = float(c.iloc[0]); lp = float(c.iloc[-1])
            bah = round((lp-fp)/fp*100, 1)

            ema200 = ema(c, 200)
            atr_vals = atr(h, l, c, 14)
            avg_atr = atr_vals.rolling(50).mean()

            d, s, lb, nw = best_base(c, h)

            # A: Fixed (smart exhaust, best params)
            fA = run_exhaust(c, h, d, s, lb, nw)
            retA = round((fA-CASH)/CASH*100, 1)

            # B: Dynamic sell only
            fB = run_exhaust(c, h, d, s, lb, nw, ema200, dynamic_sell=True)
            retB = round((fB-CASH)/CASH*100, 1)

            # C: Dynamic dip only
            fC = run_exhaust(c, h, d, s, lb, nw, atr_vals=atr_vals, avg_atr=avg_atr, dynamic_dip=True)
            retC = round((fC-CASH)/CASH*100, 1)

            # D: Dynamic time only
            fD = run_exhaust(c, h, d, s, lb, nw, dynamic_time=True)
            retD = round((fD-CASH)/CASH*100, 1)

            # E: All dynamic combined
            fE = run_exhaust(c, h, d, s, lb, nw, ema200, atr_vals, avg_atr,
                            dynamic_sell=True, dynamic_dip=True, dynamic_time=True)
            retE = round((fE-CASH)/CASH*100, 1)

            best_val = max(retA, retB, retC, retD, retE)
            if retE == best_val: best_tag = "ALL"
            elif retB == best_val: best_tag = "dSell"
            elif retC == best_val: best_tag = "dDip"
            elif retD == best_val: best_tag = "dTime"
            else: best_tag = "Fixed"

            rows.append({
                "sym": sym, "bah": bah, "d": d, "s": s, "lb": lb, "nw": nw,
                "A": retA, "B": retB, "C": retC, "D": retD, "E": retE,
                "best": best_tag,
            })
            print(f"  {sym}: Fixed:{retA:+.0f}% dSell:{retB:+.0f}% dDip:{retC:+.0f}% "
                  f"dTime:{retD:+.0f}% ALL:{retE:+.0f}% Best:{best_tag}", flush=True)

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    rows.sort(key=lambda r: -r["E"])

    # Table
    print(f"\n{'='*130}")
    print(f"  DYNAMIC PARAMS BACKTEST -- 39 HALAL STOCKS")
    print(f"{'='*130}")
    print(f"  {'#':>3} {'Stock':<6} {'B&H':>7} | {'Fixed':>8} | {'dSell':>8} | {'dDip':>8} | {'dTime':>8} | {'ALL':>8} | {'Best':>6}")
    print(f"  {'-'*85}")

    tA = tB = tC = tD = tE = tBAH = 0
    wA = wB = wC = wD = wE = 0

    for i, r in enumerate(rows, 1):
        best_val = max(r["A"], r["B"], r["C"], r["D"], r["E"])
        if r["A"] == best_val: wA += 1
        if r["B"] == best_val: wB += 1
        if r["C"] == best_val: wC += 1
        if r["D"] == best_val: wD += 1
        if r["E"] == best_val: wE += 1

        tA += r["A"]; tB += r["B"]; tC += r["C"]; tD += r["D"]; tE += r["E"]; tBAH += r["bah"]

        print(f"  {i:>3} {r['sym']:<6} {r['bah']:>+6.0f}% | {r['A']:>+7.0f}% | {r['B']:>+7.0f}% | "
              f"{r['C']:>+7.0f}% | {r['D']:>+7.0f}% | {r['E']:>+7.0f}% | {r['best']:>6}")

    n = len(rows)
    print(f"  {'-'*85}")
    print(f"  {'':>3} {'AVG':<6} {tBAH/n:>+6.0f}% | {tA/n:>+7.0f}% | {tB/n:>+7.0f}% | "
          f"{tC/n:>+7.0f}% | {tD/n:>+7.0f}% | {tE/n:>+7.0f}% |")

    print(f"\n  SUMMARY:")
    print(f"    {'Method':<25} {'Avg Return':>12} {'vs Fixed':>10} {'Wins Best':>10}")
    print(f"    {'-'*60}")
    print(f"    {'Fixed (exhaust)':<25} {tA/n:>+11.1f}% {'baseline':>10} {wA:>10}")
    print(f"    {'+ Dynamic Sell':<25} {tB/n:>+11.1f}% {(tB-tA)/n:>+9.1f}% {wB:>10}")
    print(f"    {'+ Dynamic Dip':<25} {tC/n:>+11.1f}% {(tC-tA)/n:>+9.1f}% {wC:>10}")
    print(f"    {'+ Dynamic Time':<25} {tD/n:>+11.1f}% {(tD-tA)/n:>+9.1f}% {wD:>10}")
    print(f"    {'ALL Combined':<25} {tE/n:>+11.1f}% {(tE-tA)/n:>+9.1f}% {wE:>10}")
    print(f"    {'Buy & Hold':<25} {tBAH/n:>+11.1f}%")

    print(f"\n  dSell = Sell% scales down when >15/30/50% above 200d EMA")
    print(f"  dDip  = Dip% scales with ATR/avgATR ratio")
    print(f"  dTime = After 20/30/40d held, reduce sell target to 75/50/30%")
    print(f"  ALL   = All three combined")
    print()


if __name__ == "__main__":
    main()
