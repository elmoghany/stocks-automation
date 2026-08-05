"""Screen halal stocks: 1Y vs 2Y wave backtest comparison."""

import numpy as np
import pandas as pd
import yfinance as yf

# 39 halal stocks (removed 7 haram: TDW, SHOO, PHM, TSCO, BKE, EXP, FTDR)
STOCKS = [
    "FIX", "VRT", "LRCX", "AMD", "MPWR", "TSM", "ANET", "REGN",
    "ONTO", "AMSC", "ROST", "JBL", "MLI", "PH", "HUBB", "ARM",
    "AIT", "MLM", "LLY", "CEG", "TT", "AWI", "CDNS", "GWW",
    "IR", "PNR", "RMD", "COST", "LMB", "SHW", "ISRG", "SNPS",
    "AAON", "LII", "BMI", "MANH", "IOT", "TGLS", "DOCS",
]

LOOKBACK = 5
CASH = 100_000


def backtest(closes, highs, dip, sell):
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
                trades.append(round((p - ep) / ep * 100, 1))
                in_trade = False

    final = cash + (q * float(closes.iloc[-1]) if in_trade else 0)
    return round((final - CASH) / CASH * 100, 1), len(trades)


def best_params(closes, highs):
    best = (-999, 2.5, 11)
    for d in [1.5, 2, 2.5, 3, 3.5, 4, 5]:
        for s in [6, 8, 10, 11, 12, 13, 15]:
            ret, _ = backtest(closes, highs, d, s)
            if ret > best[0]:
                best = (ret, d, s)
    return best[1], best[2], best[0]


def main():
    rows = []
    print("Fetching data (1Y + 2Y)...\n", flush=True)

    for sym in STOCKS:
        try:
            tk = yf.Ticker(sym)

            # 1 year
            df1 = tk.history(period="1y")
            if df1.empty or len(df1) < 40:
                print(f"  {sym}: NO 1Y DATA"); continue

            c1 = df1["Close"]; h1 = df1["High"]
            e1 = float(c1.iloc[0]); l1 = float(c1.iloc[-1])
            bah1 = round((l1 - e1) / e1 * 100, 1)
            d1, s1, ret1 = best_params(c1, h1)
            _, n1 = backtest(c1, h1, d1, s1)

            # 2 year
            df2 = tk.history(period="2y")
            if df2.empty or len(df2) < 100:
                bah2 = None; d2 = s2 = ret2 = n2 = None
            else:
                c2 = df2["Close"]; h2 = df2["High"]
                e2 = float(c2.iloc[0]); l2 = float(c2.iloc[-1])
                bah2 = round((l2 - e2) / e2 * 100, 1)
                d2, s2, ret2 = best_params(c2, h2)
                _, n2 = backtest(c2, h2, d2, s2)

            rows.append({
                "sym": sym,
                "bah1": bah1, "d1": d1, "s1": s1, "ret1": ret1, "n1": n1,
                "bah2": bah2, "d2": d2, "s2": s2, "ret2": ret2, "n2": n2,
            })

            r2s = f"{ret2:+.0f}%" if ret2 is not None else "N/A"
            print(f"  {sym}: 1Y d{d1}/s{s1} {ret1:+.0f}% | 2Y d{d2}/s{s2} {r2s}", flush=True)

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    # Sort by 1Y return
    rows.sort(key=lambda r: -(r["ret1"] or 0))

    # Print table
    print(f"\n{'='*140}")
    print(f"  39 HALAL STOCKS -- 1Y vs 2Y WAVE BACKTEST -- $100K -- SORTED BY 1Y RETURN")
    print(f"{'='*140}")
    print(f"  {'#':>3} {'Stock':<6} | {'B&H 1Y':>8} {'Params':>8} {'#Tr':>4} {'Wave 1Y':>9} | "
          f"{'B&H 2Y':>8} {'Params':>8} {'#Tr':>4} {'Wave 2Y':>9} | {'1Y vs 2Y':>10} {'Insight'}")
    print(f"  {'-'*135}")

    t1_final = 0; t1_bah = 0; t2_final = 0; t2_bah = 0
    n_2y = 0
    consistent = 0; improved = 0; degraded = 0

    for i, r in enumerate(rows, 1):
        p1 = f"d{r['d1']}/s{r['s1']}"
        r1s = f"{r['ret1']:>+8.0f}%"
        b1s = f"{r['bah1']:>+7.0f}%"

        t1_final += CASH * (1 + r["ret1"] / 100)
        t1_bah += CASH * (1 + r["bah1"] / 100)

        if r["ret2"] is not None:
            p2 = f"d{r['d2']}/s{r['s2']}"
            r2s = f"{r['ret2']:>+8.0f}%"
            b2s = f"{r['bah2']:>+7.0f}%"
            t2_final += CASH * (1 + r["ret2"] / 100)
            t2_bah += CASH * (1 + r["bah2"] / 100)
            n_2y += 1

            # Insight: compare 1Y vs 2Y
            diff = r["ret2"] - r["ret1"]
            if r["d1"] == r["d2"] and r["s1"] == r["s2"]:
                insight = "same params work"
                consistent += 1
            elif r["ret2"] > r["ret1"] * 1.5:
                insight = "2Y much better -- compound longer"
                improved += 1
            elif r["ret2"] > r["ret1"]:
                insight = "2Y better -- more cycles"
                improved += 1
            elif r["ret2"] > r["ret1"] * 0.5:
                insight = "2Y weaker -- params shifted"
                degraded += 1
            else:
                insight = "2Y much weaker"
                degraded += 1

            diff_s = f"{diff:>+9.0f}%"
        else:
            p2 = "N/A"; r2s = "     N/A"; b2s = "    N/A"
            diff_s = "       --"; insight = "no 2Y data"

        print(f"  {i:>3} {r['sym']:<6} | {b1s} {p1:>8} {r['n1']:>4} {r1s} | "
              f"{b2s} {p2:>8} {r.get('n2',''):>4} {r2s} | {diff_s} {insight}")

    # Totals
    n = len(rows)
    print(f"  {'-'*135}")
    tc1 = n * CASH
    tc2 = n_2y * CASH
    print(f"  {'':>3} {'':>6} | {(t1_bah-tc1)/tc1*100:>+7.0f}% {'':>8} {'':>4} {(t1_final-tc1)/tc1*100:>+8.0f}% | "
          f"{(t2_bah-tc2)/tc2*100 if tc2 else 0:>+7.0f}% {'':>8} {'':>4} {(t2_final-tc2)/tc2*100 if tc2 else 0:>+8.0f}%")

    # Insights
    print(f"\n{'='*140}")
    print(f"  INSIGHTS")
    print(f"{'='*140}")

    print(f"\n  1. PARAMETER STABILITY:")
    print(f"     Same params work in both periods: {consistent}/{n_2y} stocks")
    print(f"     2Y better (more compounding time): {improved}/{n_2y} stocks")
    print(f"     2Y weaker (market regime changed):  {degraded}/{n_2y} stocks")

    # Find stocks where 2Y > 2x of 1Y (compounding acceleration)
    compounders = [(r["sym"], r["ret1"], r["ret2"]) for r in rows
                   if r["ret2"] is not None and r["ret2"] > r["ret1"] * 1.8 and r["ret1"] > 20]
    if compounders:
        print(f"\n  2. COMPOUNDING ACCELERATORS (2Y > 1.8x of 1Y return):")
        for sym, r1, r2 in sorted(compounders, key=lambda x: -x[2]):
            print(f"     {sym:<6} 1Y: {r1:+.0f}% -> 2Y: {r2:+.0f}% (compounding multiplied {r2/max(r1,1):.1f}x)")
        print(f"     >> These stocks benefit MOST from longer holding periods")

    # Find stocks where params changed significantly
    param_shifts = [(r["sym"], r["d1"], r["s1"], r["d2"], r["s2"], r["ret1"], r["ret2"])
                    for r in rows if r["d2"] is not None and (r["d1"] != r["d2"] or r["s1"] != r["s2"])]
    if param_shifts:
        print(f"\n  3. PARAMETER SHIFTS (optimal params changed between 1Y and 2Y):")
        for sym, d1, s1, d2, s2, r1, r2 in param_shifts[:10]:
            print(f"     {sym:<6} 1Y: d{d1}/s{s1} ({r1:+.0f}%) -> 2Y: d{d2}/s{s2} ({r2:+.0f}%)")
        print(f"     >> Consider using 2Y params -- they capture more market regimes")

    # Find stocks where wave beats B&H by most
    wave_advantage = [(r["sym"], r["ret1"] - r["bah1"], r["ret1"], r["bah1"])
                      for r in rows if r["ret1"] > r["bah1"]]
    wave_advantage.sort(key=lambda x: -x[1])
    if wave_advantage:
        print(f"\n  4. BIGGEST WAVE ADVANTAGE OVER B&H (1Y):")
        for sym, adv, wave, bah in wave_advantage[:10]:
            print(f"     {sym:<6} Wave: {wave:+.0f}% vs B&H: {bah:+.0f}% (wave adds +{adv:.0f}%)")

    # Recommendation
    top_both = [(r["sym"], r["ret1"], r["ret2"]) for r in rows
                if r["ret2"] is not None and r["ret1"] > 50 and r["ret2"] > 100]
    if top_both:
        print(f"\n  5. RECOMMENDED (>50% in 1Y AND >100% in 2Y):")
        for sym, r1, r2 in sorted(top_both, key=lambda x: -x[2]):
            print(f"     {sym:<6} 1Y: {r1:+.0f}% | 2Y: {r2:+.0f}%")

    print()


if __name__ == "__main__":
    main()
