"""Find the absolute best methodology per stock targeting 400%+ return.

For each stock, test ALL combinations:
- Dip: 1.5, 2, 2.5, 3, 3.5, 4, 5%
- Sell: 6, 8, 10, 11, 12, 13, 15%
- Method: Original, Smart Exhaust (N=3-12), Gain Lock (2x-5x)
- Lookback: 5, 7, 10

Find the single best combo per stock. Sort by return.
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


def method_original(closes, highs, dip, sell, lookback):
    cash = CASH; in_trade = False; ep = q = ed = 0; n = 0; peak = CASH
    for i in range(lookback, len(closes)):
        p = float(closes.iloc[i])
        if not in_trade:
            rh = float(highs.iloc[max(0, i-lookback):i].max())
            if (rh-p)/rh*100 >= dip and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
        else:
            if (p-ep)/ep*100 >= sell:
                cash += q*p; n += 1; in_trade = False
                if cash > peak: peak = cash
    final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
    return final, n, peak, in_trade


def method_exhaust(closes, highs, dip, sell, lookback, max_wins):
    cash = CASH; in_trade = False; ep = q = ed = 0; n = 0; peak = CASH
    consec = 0; pause_until = 0; pause_price = 0
    for i in range(lookback, len(closes)):
        p = float(closes.iloc[i])
        if not in_trade:
            if i < pause_until:
                if pause_price > 0 and (pause_price-p)/pause_price*100 >= DIP_OVERRIDE and cash > p:
                    q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True; consec = 0
                continue
            rh = float(highs.iloc[max(0, i-lookback):i].max())
            if (rh-p)/rh*100 >= dip and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
        else:
            if (p-ep)/ep*100 >= sell:
                cash += q*p; n += 1; in_trade = False; consec += 1
                if cash > peak: peak = cash
                if consec >= max_wins:
                    pause_until = i + PAUSE_DAYS; pause_price = p; consec = 0
    final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
    return final, n, peak, in_trade


def method_gainlock(closes, highs, dip, sell, lookback, lock_mult):
    cash = CASH; in_trade = False; ep = q = ed = 0; n = 0; peak = CASH; locked = False
    for i in range(lookback, len(closes)):
        if locked: break
        p = float(closes.iloc[i])
        if not in_trade:
            rh = float(highs.iloc[max(0, i-lookback):i].max())
            if (rh-p)/rh*100 >= dip and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
        else:
            if (p-ep)/ep*100 >= sell:
                cash += q*p; n += 1; in_trade = False
                if cash > peak: peak = cash
                if cash >= CASH * lock_mult: locked = True
    if locked: final = cash
    else: final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
    return final, n, peak, in_trade and not locked


def method_exhaust_lock(closes, highs, dip, sell, lookback, max_wins, lock_mult):
    """Combined: exhaust stop + gain lock."""
    cash = CASH; in_trade = False; ep = q = ed = 0; n = 0; peak = CASH
    consec = 0; pause_until = 0; pause_price = 0; locked = False
    for i in range(lookback, len(closes)):
        if locked: break
        p = float(closes.iloc[i])
        if not in_trade:
            if i < pause_until:
                if pause_price > 0 and (pause_price-p)/pause_price*100 >= DIP_OVERRIDE and cash > p:
                    q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True; consec = 0
                continue
            rh = float(highs.iloc[max(0, i-lookback):i].max())
            if (rh-p)/rh*100 >= dip and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
        else:
            if (p-ep)/ep*100 >= sell:
                cash += q*p; n += 1; in_trade = False; consec += 1
                if cash > peak: peak = cash
                if cash >= CASH * lock_mult: locked = True
                elif consec >= max_wins:
                    pause_until = i + PAUSE_DAYS; pause_price = p; consec = 0
    if locked: final = cash
    else: final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
    return final, n, peak, in_trade and not locked


def find_best(closes, highs):
    best = {"final": 0}

    dips = [1.5, 2, 2.5, 3, 3.5, 4, 5]
    sells = [6, 8, 10, 11, 12, 13, 15]
    lookbacks = [5, 7, 10]

    for lb in lookbacks:
        for d in dips:
            for s in sells:
                # Original
                f, n, pk, stk = method_original(closes, highs, d, s, lb)
                if f > best["final"]:
                    best = {"final": f, "method": "Original", "dip": d, "sell": s,
                            "lb": lb, "trades": n, "peak": pk, "stuck": stk, "extra": ""}

                # Exhaust
                for mw in [3, 4, 5, 6, 7, 8, 10, 12]:
                    f, n, pk, stk = method_exhaust(closes, highs, d, s, lb, mw)
                    if f > best["final"]:
                        best = {"final": f, "method": "Exhaust", "dip": d, "sell": s,
                                "lb": lb, "trades": n, "peak": pk, "stuck": stk,
                                "extra": f"N={mw}"}

                # Gain Lock
                for lm in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
                    f, n, pk, stk = method_gainlock(closes, highs, d, s, lb, lm)
                    if f > best["final"]:
                        best = {"final": f, "method": "GainLock", "dip": d, "sell": s,
                                "lb": lb, "trades": n, "peak": pk, "stuck": stk,
                                "extra": f"{lm}x"}

                # Combined
                for mw in [4, 5, 6, 7, 8, 10]:
                    for lm in [3.0, 4.0, 5.0]:
                        f, n, pk, stk = method_exhaust_lock(closes, highs, d, s, lb, mw, lm)
                        if f > best["final"]:
                            best = {"final": f, "method": "Exh+Lock", "dip": d, "sell": s,
                                    "lb": lb, "trades": n, "peak": pk, "stuck": stk,
                                    "extra": f"N={mw},L={lm}x"}

    return best


def main():
    rows = []
    print("Finding best methodology per stock (brute force)...\n", flush=True)

    for sym in HALAL_STOCKS:
        try:
            tk = yf.Ticker(sym)
            df = tk.history(period="1y")
            if df.empty or len(df) < 40: continue
            c = df["Close"]; h = df["High"]
            fp = float(c.iloc[0]); lp = float(c.iloc[-1])
            bah = round((lp-fp)/fp*100, 1)

            best = find_best(c, h)
            ret = round((best["final"]-CASH)/CASH*100, 1)
            peak_ret = round((best["peak"]-CASH)/CASH*100, 1)

            rows.append({"sym": sym, "bah": bah, "best": best, "ret": ret, "peak_ret": peak_ret})

            hit = ">>> 4x+ <<<" if ret >= 300 else ("3x+" if ret >= 200 else "")
            print(f"  {sym}: {best['method']:<10} d{best['dip']}/s{best['sell']}/lb{best['lb']} "
                  f"{best['extra']:<12} {ret:>+6.0f}% ({best['trades']}t) B&H:{bah:+.0f}% {hit}", flush=True)

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    rows.sort(key=lambda r: -r["ret"])

    # Table
    print(f"\n{'='*145}")
    print(f"  BEST METHOD PER STOCK -- TARGET 400%+ -- SORTED BY RETURN")
    print(f"{'='*145}")
    print(f"  {'#':>3} {'Stock':<6} {'B&H':>7} | {'Method':<10} {'Dip':>4} {'Sell':>5} {'LB':>3} {'Extra':<14} | "
          f"{'Return':>8} {'Peak':>8} {'#Tr':>4} {'Stuck':>5} | {'Target':>8}")
    print(f"  {'-'*120}")

    total_ret = 0; total_bah = 0; hits_4x = 0; hits_3x = 0; hits_2x = 0

    for i, r in enumerate(rows, 1):
        b = r["best"]
        stk = "YES" if b["stuck"] else "--"

        if r["ret"] >= 300: target = "4x+ HIT"; hits_4x += 1
        elif r["ret"] >= 200: target = "3x+"; hits_3x += 1
        elif r["ret"] >= 100: target = "2x+"; hits_2x += 1
        else: target = ""

        total_ret += r["ret"]; total_bah += r["bah"]

        print(f"  {i:>3} {r['sym']:<6} {r['bah']:>+6.0f}% | {b['method']:<10} {b['dip']:>3.1f}% {b['sell']:>+4.0f}% "
              f"{b['lb']:>3} {b['extra']:<14} | "
              f"{r['ret']:>+7.0f}% {r['peak_ret']:>+7.0f}% {b['trades']:>4} {stk:>5} | {target:>8}")

    n = len(rows)
    print(f"  {'-'*120}")
    print(f"  {'':>3} {'AVG':<6} {total_bah/n:>+6.0f}% | {'':>42} | {total_ret/n:>+7.0f}%")

    print(f"\n  SUMMARY:")
    print(f"    Stocks hitting 4x+ (>300%):  {hits_4x}/{n}")
    print(f"    Stocks hitting 3x+ (>200%):  {hits_3x+hits_4x}/{n}")
    print(f"    Stocks hitting 2x+ (>100%):  {hits_2x+hits_3x+hits_4x}/{n}")
    print(f"    Avg return:                  {total_ret/n:+.1f}%")
    print(f"    Avg B&H:                     {total_bah/n:+.1f}%")

    # Method distribution
    methods = {}
    for r in rows:
        m = r["best"]["method"]
        methods[m] = methods.get(m, 0) + 1
    print(f"\n  METHOD DISTRIBUTION:")
    for m, cnt in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"    {m:<12} {cnt:>3} stocks")

    # Top portfolio
    top = [r for r in rows if r["ret"] >= 100]
    if top:
        nt = len(top)
        per = CASH / min(nt, 10)
        use = top[:10]
        total = sum(per * (1 + r["ret"]/100) for r in use)
        total_bah_p = sum(per * (1 + r["bah"]/100) for r in use)
        print(f"\n  TOP {len(use)} PORTFOLIO ($100K / {len(use)} = ${per:,.0f} each):")
        print(f"    Wave:  ${total:,.0f} ({(total-CASH)/CASH*100:+.1f}%)")
        print(f"    B&H:   ${total_bah_p:,.0f} ({(total_bah_p-CASH)/CASH*100:+.1f}%)")

    print()


if __name__ == "__main__":
    main()
