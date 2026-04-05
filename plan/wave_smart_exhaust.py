"""Smart Exhaustion: per-stock flexible wins threshold, 30d pause, override on 10%+ dip.

Rules:
- After N consecutive wins, pause 30 days (N varies per stock)
- During pause: if stock drops 10%+ from pause-start price, override and buy the dip
- Test different N values per stock to find optimal
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
PAUSE_DAYS = 30
DIP_OVERRIDE = 10  # during pause, buy if stock drops 10%+


def smart_exhaust(closes, highs, dip, sell, max_wins):
    """Smart exhaustion with 30d pause and 10% dip override."""
    cash = CASH
    in_trade = False
    ep = q = ed = 0
    trades = []
    peak = CASH
    consec = 0
    pause_until = 0
    pause_price = 0  # price when pause started

    for i in range(LOOKBACK, len(closes)):
        p = float(closes.iloc[i])

        if not in_trade:
            # During pause: only buy if 10%+ dip from pause price
            if i < pause_until:
                if pause_price > 0:
                    drop = (pause_price - p) / pause_price * 100
                    if drop >= DIP_OVERRIDE and cash > p:
                        q = int(cash // p); ep = p; ed = i
                        cash -= q * p; in_trade = True
                        consec = 0  # reset after override
                continue

            rh = float(highs.iloc[max(0, i - LOOKBACK):i].max())
            if (rh - p) / rh * 100 >= dip and cash > p:
                q = int(cash // p); ep = p; ed = i
                cash -= q * p; in_trade = True
        else:
            if (p - ep) / ep * 100 >= sell:
                cash += q * p
                trades.append({"g": round((p-ep)/ep*100, 1), "d": i - ed})
                if cash > peak:
                    peak = cash
                in_trade = False
                consec += 1

                if consec >= max_wins:
                    pause_until = i + PAUSE_DAYS
                    pause_price = p
                    consec = 0

    final = cash + (q * float(closes.iloc[-1]) if in_trade else 0)
    return {
        "ret": round((final - CASH) / CASH * 100, 1),
        "trades": len(trades),
        "peak": round((peak - CASH) / CASH * 100, 1),
        "stuck": in_trade,
        "final": round(final, 0),
    }


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
    return round((final-CASH)/CASH*100, 1), len(trades), in_trade


def best_base_params(closes, highs):
    best = (-999, 2.5, 11)
    for d in [1.5, 2, 2.5, 3, 3.5, 4, 5]:
        for s in [6, 8, 10, 11, 12, 13, 15]:
            ret, _, _ = original(closes, highs, d, s)
            if ret > best[0]: best = (ret, d, s)
    return best[1], best[2]


def main():
    rows = []
    print("Testing smart exhaustion on 39 halal stocks...\n", flush=True)

    for sym in HALAL_STOCKS:
        try:
            tk = yf.Ticker(sym)
            df = tk.history(period="1y")
            if df.empty or len(df) < 40: continue
            c = df["Close"]; h = df["High"]
            fp = float(c.iloc[0]); lp = float(c.iloc[-1])
            bah = round((lp-fp)/fp*100, 1)

            d, s = best_base_params(c, h)
            o_ret, o_n, o_stuck = original(c, h, d, s)

            # Test different exhaust thresholds per stock
            best_exhaust = None
            for n_wins in [3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 99]:
                r = smart_exhaust(c, h, d, s, n_wins)
                if best_exhaust is None or r["ret"] > best_exhaust["ret"]:
                    best_exhaust = r
                    best_exhaust["n_wins"] = n_wins

            diff = best_exhaust["ret"] - o_ret

            rows.append({
                "sym": sym, "bah": bah, "dip": d, "sell": s,
                "o_ret": o_ret, "o_n": o_n, "o_stuck": o_stuck,
                "e": best_exhaust, "diff": diff,
            })

            better = "EXHAUST" if diff > 0 else ("SAME" if diff == 0 else "ORIG")
            print(f"  {sym}: d{d}/s{s} | Orig:{o_ret:+.0f}% | "
                  f"SmartExhaust(n={best_exhaust['n_wins']}): {best_exhaust['ret']:+.0f}% "
                  f"({diff:+.0f}%) {better}", flush=True)

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    rows.sort(key=lambda r: -r["e"]["ret"])

    # Table
    print(f"\n{'='*140}")
    print(f"  SMART EXHAUSTION: per-stock N wins, 30d pause, 10% dip override")
    print(f"{'='*140}")
    print(f"  {'#':>3} {'Stock':<6} {'B&H':>7} {'Dip':>4} {'Sell':>5} | "
          f"{'Original':>9} {'#':>3} {'Stk':>4} | "
          f"{'SmartExh':>9} {'N':>3} {'#':>3} {'Stk':>4} | {'Diff':>7} {'Better':>8}")
    print(f"  {'-'*105}")

    t_o = t_e = t_bah = 0
    e_better = 0; same = 0; o_better = 0
    e_stuck = 0; o_stuck_count = 0

    for i, r in enumerate(rows, 1):
        e = r["e"]
        os = "YES" if r["o_stuck"] else "--"
        es = "YES" if e["stuck"] else "--"
        if r["o_stuck"]: o_stuck_count += 1
        if e["stuck"]: e_stuck += 1

        if r["diff"] > 0: tag = "EXHAUST"; e_better += 1
        elif r["diff"] == 0: tag = "SAME"; same += 1
        else: tag = "ORIG"; o_better += 1

        t_o += r["o_ret"]; t_e += e["ret"]; t_bah += r["bah"]

        print(f"  {i:>3} {r['sym']:<6} {r['bah']:>+6.0f}% {r['dip']:>3.1f}% {r['sell']:>+4.0f}% | "
              f"{r['o_ret']:>+8.0f}% {r['o_n']:>3} {os:>4} | "
              f"{e['ret']:>+8.0f}% {e['n_wins']:>3} {e['trades']:>3} {es:>4} | "
              f"{r['diff']:>+6.0f}% {tag:>8}")

    n = len(rows)
    print(f"  {'-'*105}")
    print(f"  {'':>3} {'AVG':<6} {t_bah/n:>+6.0f}% {'':>10} | "
          f"{t_o/n:>+8.0f}% {'':>3} {o_stuck_count:>3}s | "
          f"{t_e/n:>+8.0f}% {'':>3} {'':>3} {e_stuck:>3}s |")

    print(f"\n  SUMMARY:")
    print(f"    Smart Exhaust better: {e_better}/{n} stocks")
    print(f"    Same result:          {same}/{n} stocks")
    print(f"    Original better:      {o_better}/{n} stocks")
    print(f"    Avg Original:         {t_o/n:+.1f}%")
    print(f"    Avg Smart Exhaust:    {t_e/n:+.1f}%")
    print(f"    Avg B&H:              {t_bah/n:+.1f}%")
    print(f"    Stuck (Original):     {o_stuck_count}/{n}")
    print(f"    Stuck (Exhaust):      {e_stuck}/{n}")

    # Per-stock optimal N
    print(f"\n  OPTIMAL EXHAUST THRESHOLD PER STOCK (where it helps):")
    print(f"  {'Stock':<6} {'N wins':>7} {'Orig':>8} {'Exhaust':>9} {'Gain':>7}")
    print(f"  {'-'*40}")
    for r in sorted(rows, key=lambda x: -x["diff"]):
        if r["diff"] > 0:
            print(f"  {r['sym']:<6} {r['e']['n_wins']:>7} {r['o_ret']:>+7.0f}% {r['e']['ret']:>+8.0f}% {r['diff']:>+6.0f}%")

    # Portfolio
    print(f"\n  PORTFOLIO ($100K x {n} = ${n*100}K):")
    print(f"    Original:       ${n*CASH + int(t_o/100*CASH):>12,} ({t_o/n:+.1f}%)")
    print(f"    Smart Exhaust:  ${n*CASH + int(t_e/100*CASH):>12,} ({t_e/n:+.1f}%)")
    print(f"    B&H:            ${n*CASH + int(t_bah/100*CASH):>12,} ({t_bah/n:+.1f}%)")
    print()


if __name__ == "__main__":
    main()
