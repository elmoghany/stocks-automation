"""Test Exhaustion Stop + Gain Lock on all 39 halal stocks.

Compare: Original vs Exhaustion (10 wins, 50d pause) vs Gain Lock (3x stop)
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

LOOKBACK = 5
CASH = 100_000


def best_params(closes, highs, strategy_fn):
    best = (-999, 2.5, 11)
    for d in [1.5, 2, 2.5, 3, 3.5, 4, 5]:
        for s in [6, 8, 10, 11, 12, 13, 15]:
            ret, _, _, _ = strategy_fn(closes, highs, d, s)
            if ret > best[0]:
                best = (ret, d, s)
    return best[1], best[2], best[0]


def original(closes, highs, dip, sell):
    cash = CASH; in_trade = False; ep = q = ed = 0; trades = []; peak = CASH
    for i in range(LOOKBACK, len(closes)):
        p = float(closes.iloc[i])
        if not in_trade:
            rh = float(highs.iloc[max(0, i-LOOKBACK):i].max())
            if (rh-p)/rh*100 >= dip and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
        else:
            if (p-ep)/ep*100 >= sell:
                cash += q*p; trades.append(1); in_trade = False
                if cash > peak: peak = cash
    final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
    return round((final-CASH)/CASH*100, 1), len(trades), round((peak-CASH)/CASH*100, 1), in_trade


def with_exhaustion(closes, highs, dip, sell, max_wins=10, pause_days=50):
    cash = CASH; in_trade = False; ep = q = ed = 0; trades = []; peak = CASH
    consec = 0; pause_until = 0
    for i in range(LOOKBACK, len(closes)):
        p = float(closes.iloc[i])
        if not in_trade:
            if i < pause_until: continue
            rh = float(highs.iloc[max(0, i-LOOKBACK):i].max())
            if (rh-p)/rh*100 >= dip and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
        else:
            if (p-ep)/ep*100 >= sell:
                cash += q*p; trades.append(1); in_trade = False; consec += 1
                if cash > peak: peak = cash
                if consec >= max_wins:
                    pause_until = i + pause_days; consec = 0
    final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
    return round((final-CASH)/CASH*100, 1), len(trades), round((peak-CASH)/CASH*100, 1), in_trade


def with_gain_lock(closes, highs, dip, sell, lock_mult=3.0):
    cash = CASH; in_trade = False; ep = q = ed = 0; trades = []; peak = CASH; locked = False
    for i in range(LOOKBACK, len(closes)):
        if locked: break
        p = float(closes.iloc[i])
        if not in_trade:
            rh = float(highs.iloc[max(0, i-LOOKBACK):i].max())
            if (rh-p)/rh*100 >= dip and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
        else:
            if (p-ep)/ep*100 >= sell:
                cash += q*p; trades.append(1); in_trade = False
                if cash > peak: peak = cash
                if cash >= CASH * lock_mult: locked = True
    if locked: final = cash
    else: final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
    return round((final-CASH)/CASH*100, 1), len(trades), round((peak-CASH)/CASH*100, 1), in_trade and not locked


def main():
    rows = []
    print("Testing all 39 halal stocks...\n", flush=True)

    for sym in HALAL_STOCKS:
        try:
            tk = yf.Ticker(sym)
            df = tk.history(period="1y")
            if df.empty or len(df) < 40: continue
            c = df["Close"]; h = df["High"]
            fp = float(c.iloc[0]); lp = float(c.iloc[-1])
            bah = round((lp-fp)/fp*100, 1)

            # Original best
            d, s, _ = best_params(c, h, original)
            o_ret, o_n, o_peak, o_stuck = original(c, h, d, s)

            # Exhaustion with same params
            e_ret, e_n, e_peak, e_stuck = with_exhaustion(c, h, d, s)

            # Gain lock with same params
            g_ret, g_n, g_peak, g_stuck = with_gain_lock(c, h, d, s)

            rows.append({
                "sym": sym, "bah": bah, "dip": d, "sell": s,
                "o_ret": o_ret, "o_n": o_n, "o_peak": o_peak, "o_stuck": o_stuck,
                "e_ret": e_ret, "e_n": e_n, "e_peak": e_peak, "e_stuck": e_stuck,
                "g_ret": g_ret, "g_n": g_n, "g_peak": g_peak, "g_stuck": g_stuck,
            })
            best_strat = max([("Orig", o_ret), ("Exhaust", e_ret), ("Lock", g_ret)], key=lambda x: x[1])
            print(f"  {sym}: d{d}/s{s} | Orig:{o_ret:+.0f}% Exhaust:{e_ret:+.0f}% Lock:{g_ret:+.0f}% | Best: {best_strat[0]}", flush=True)

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    rows.sort(key=lambda r: -max(r["o_ret"], r["e_ret"], r["g_ret"]))

    # Table
    print(f"\n{'='*140}")
    print(f"  39 HALAL STOCKS -- ORIGINAL vs EXHAUSTION STOP vs GAIN LOCK")
    print(f"{'='*140}")
    print(f"  {'#':>3} {'Stock':<6} {'B&H':>7} {'Dip':>4} {'Sell':>5} | "
          f"{'Original':>9} {'#':>3} {'Stk':>4} | "
          f"{'Exhaust':>9} {'#':>3} {'Stk':>4} | "
          f"{'GainLock':>9} {'#':>3} {'Stk':>4} | {'Best':>8}")
    print(f"  {'-'*130}")

    t_o = t_e = t_g = t_bah = 0
    o_wins = e_wins = g_wins = 0
    o_stuck_count = e_stuck_count = g_stuck_count = 0

    for i, r in enumerate(rows, 1):
        best_val = max(r["o_ret"], r["e_ret"], r["g_ret"])
        if r["o_ret"] == best_val: best_s = "Orig"; o_wins += 1
        elif r["e_ret"] == best_val: best_s = "Exhaust"; e_wins += 1
        else: best_s = "Lock"; g_wins += 1

        os = "YES" if r["o_stuck"] else "--"
        es = "YES" if r["e_stuck"] else "--"
        gs = "YES" if r["g_stuck"] else "--"
        if r["o_stuck"]: o_stuck_count += 1
        if r["e_stuck"]: e_stuck_count += 1
        if r["g_stuck"]: g_stuck_count += 1

        t_o += r["o_ret"]; t_e += r["e_ret"]; t_g += r["g_ret"]; t_bah += r["bah"]

        print(f"  {i:>3} {r['sym']:<6} {r['bah']:>+6.0f}% {r['dip']:>3.1f}% {r['sell']:>+4.0f}% | "
              f"{r['o_ret']:>+8.0f}% {r['o_n']:>3} {os:>4} | "
              f"{r['e_ret']:>+8.0f}% {r['e_n']:>3} {es:>4} | "
              f"{r['g_ret']:>+8.0f}% {r['g_n']:>3} {gs:>4} | {best_s:>8}")

    n = len(rows)
    print(f"  {'-'*130}")
    print(f"  {'':>3} {'AVG':<6} {t_bah/n:>+6.0f}% {'':>4} {'':>5} | "
          f"{t_o/n:>+8.0f}% {'':>3} {o_stuck_count:>3}s | "
          f"{t_e/n:>+8.0f}% {'':>3} {e_stuck_count:>3}s | "
          f"{t_g/n:>+8.0f}% {'':>3} {g_stuck_count:>3}s |")

    print(f"\n  SUMMARY:")
    print(f"    {'Strategy':<25} {'Avg Return':>12} {'Wins Best':>10} {'Stuck Count':>12}")
    print(f"    {'-'*60}")
    print(f"    {'Original':<25} {t_o/n:>+11.1f}% {o_wins:>10} {o_stuck_count:>12}")
    print(f"    {'Exhaustion (10w/50d)':<25} {t_e/n:>+11.1f}% {e_wins:>10} {e_stuck_count:>12}")
    print(f"    {'Gain Lock (3x)':<25} {t_g/n:>+11.1f}% {g_wins:>10} {g_stuck_count:>12}")
    print(f"    {'Buy & Hold':<25} {t_bah/n:>+11.1f}%")

    # Portfolio
    print(f"\n  PORTFOLIO ($100K x {n} = ${n*100}K):")
    print(f"    Original:   ${n*CASH + int(t_o/100*CASH):>12,} ({t_o/n:+.1f}% avg)")
    print(f"    Exhaustion: ${n*CASH + int(t_e/100*CASH):>12,} ({t_e/n:+.1f}% avg)")
    print(f"    Gain Lock:  ${n*CASH + int(t_g/100*CASH):>12,} ({t_g/n:+.1f}% avg)")
    print(f"    B&H:        ${n*CASH + int(t_bah/100*CASH):>12,} ({t_bah/n:+.1f}% avg)")
    print()


if __name__ == "__main__":
    main()
