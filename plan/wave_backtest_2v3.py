"""Backtest: 2% dip vs 3% dip, with 10/11/12% sell targets. All 21 stocks."""

import numpy as np
import pandas as pd
import yfinance as yf

SYMBOLS = [
    "LRCX", "TSM", "VRT", "AMSC", "AMD", "LLY", "ANET", "FIX",
    "TDW", "TJX", "MLI", "RMD", "HUBB", "ETN", "CDNS", "DECK",
    "AWI", "ISRG", "CTAS", "BMI", "FICO",
]

COMBOS = [
    (2, 10), (2, 11), (2, 12),
    (3, 10), (3, 11), (3, 12),
]

STARTING_CASH = 100_000
LOOKBACK = 15


def run(closes, highs, dip_pct, sell_pct):
    cash = STARTING_CASH
    trades = []
    in_trade = False
    entry_price = quantity = entry_day = 0

    for i in range(LOOKBACK, len(closes)):
        price = float(closes.iloc[i])
        if not in_trade:
            recent_high = float(highs.iloc[max(0, i - LOOKBACK):i].max())
            dip = (recent_high - price) / recent_high * 100
            if dip >= dip_pct and cash > price:
                quantity = int(cash // price)
                entry_price = price
                entry_day = i
                cash -= quantity * price
                in_trade = True
        else:
            gain = (price - entry_price) / entry_price * 100
            if gain >= sell_pct:
                cash += quantity * price
                trades.append({"pnl_pct": round(gain, 1), "days": i - entry_day})
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    ret = (final - STARTING_CASH) / STARTING_CASH * 100
    return round(ret, 1), len(trades)


def main():
    print("Fetching data...\n", flush=True)

    rows = []
    for sym in SYMBOLS:
        try:
            t = yf.Ticker(sym)
            df = t.history(period="1y")
            if df.empty or len(df) < 40:
                continue

            closes = df["Close"]
            highs = df["High"]
            entry_price = round(float(closes.iloc[0]), 2)
            last_price = round(float(closes.iloc[-1]), 2)
            bah = round((last_price - entry_price) / entry_price * 100, 1)

            results = {}
            for dip, sell in COMBOS:
                key = f"d{dip}s{sell}"
                ret, n = run(closes, highs, dip, sell)
                results[key] = {"ret": ret, "trades": n}

            rows.append({"sym": sym, "entry": entry_price, "bah": bah, "results": results})
            print(f"  {sym} done", flush=True)

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    rows.sort(key=lambda r: max(r["results"][k]["ret"] for k in r["results"]), reverse=True)

    # Header
    print(f"\n{'='*130}")
    print(f"  2% DIP vs 3% DIP -- SELL 10/11/12% -- 12 MONTHS -- $100K PER STOCK")
    print(f"{'='*130}")

    header = f"  {'Stock':<6} {'Entry$':>8} {'B&H':>6} |"
    for dip, sell in COMBOS:
        header += f" {'d'+str(dip)+'s'+str(sell):>7} {'#':>3} |"
    print(header)
    print(f"  {'-'*125}")

    totals = {f"d{d}s{s}": 0 for d, s in COMBOS}
    total_bah = 0
    n = len(rows)

    for r in rows:
        bah = r["bah"]
        total_bah += bah

        best_key = max(r["results"], key=lambda k: r["results"][k]["ret"])
        best_ret = r["results"][best_key]["ret"]

        line = f"  {r['sym']:<6} ${r['entry']:>7.2f} {bah:>+5.0f}% |"
        for dip, sell in COMBOS:
            key = f"d{dip}s{sell}"
            res = r["results"][key]
            totals[key] += res["ret"]
            mark = "*" if key == best_key else " "
            line += f" {res['ret']:>+6.0f}%{mark} {res['trades']:>3} |"
        print(line)

    # Averages
    print(f"  {'-'*125}")
    best_avg_key = max(totals, key=lambda k: totals[k])
    avg_line = f"  {'AVG':<6} {'':>8} {total_bah/n:>+5.0f}% |"
    for dip, sell in COMBOS:
        key = f"d{dip}s{sell}"
        mark = "*" if key == best_avg_key else " "
        avg_line += f" {totals[key]/n:>+6.0f}%{mark} {'':>3} |"
    print(avg_line)
    print(f"  * = best combo for that stock/average")

    # Summary
    print(f"\n{'='*130}")
    print(f"  SUMMARY")
    print(f"{'='*130}")
    print(f"  {'Combo':<12} {'Avg Return':>12} {'vs B&H':>10} {'Beats B&H':>12}")
    print(f"  {'-'*50}")

    for dip, sell in COMBOS:
        key = f"d{dip}s{sell}"
        avg = totals[key] / n
        vs = avg - total_bah / n
        beats = sum(1 for r in rows if r["results"][key]["ret"] > r["bah"])
        print(f"  {dip}%dip {sell}%sell {avg:>+11.1f}% {vs:>+9.1f}% {beats:>10}/{n}")

    print(f"  {'B&H':<12} {total_bah/n:>+11.1f}%")

    best_d, best_s = max(COMBOS, key=lambda c: totals[f"d{c[0]}s{c[1]}"])
    best_key = f"d{best_d}s{best_s}"
    print(f"\n  WINNER: {best_d}% dip + {best_s}% sell (avg {totals[best_key]/n:+.1f}%)")
    print()


if __name__ == "__main__":
    main()
