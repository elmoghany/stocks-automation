"""Final backtest: 2/2.5/3% dip x 10/11/12% sell, lookback 5d, all 21 stocks."""

import numpy as np
import pandas as pd
import yfinance as yf

SYMBOLS = [
    "LRCX", "TSM", "VRT", "AMSC", "AMD", "LLY", "ANET", "FIX",
    "TDW", "TJX", "MLI", "RMD", "HUBB", "ETN", "CDNS", "DECK",
    "AWI", "ISRG", "CTAS", "BMI", "FICO",
]

COMBOS = [
    (2.0, 10), (2.0, 11), (2.0, 12),
    (2.5, 10), (2.5, 11), (2.5, 12),
    (3.0, 10), (3.0, 11), (3.0, 12),
]

STARTING_CASH = 100_000
LOOKBACK = 5


def run(closes, highs, dip_pct, sell_pct):
    cash = STARTING_CASH
    trades = []
    in_trade = False
    entry_price = quantity = entry_day = 0
    peak_cash = cash

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
                trades.append({"g": round(gain, 1), "d": i - entry_day})
                if cash > peak_cash:
                    peak_cash = cash
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return round((final - STARTING_CASH) / STARTING_CASH * 100, 1), len(trades), round((peak_cash - STARTING_CASH) / STARTING_CASH * 100, 1)


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
                ret, n, peak = run(closes, highs, dip, sell)
                results[key] = {"ret": ret, "trades": n, "peak": peak}

            rows.append({"sym": sym, "entry": entry_price, "bah": bah, "results": results})
            print(f"  {sym} done", flush=True)

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    rows.sort(key=lambda r: max(r["results"][k]["ret"] for k in r["results"]), reverse=True)

    # Header
    print(f"\n{'='*155}")
    print(f"  LOOKBACK 5d -- 2/2.5/3% DIP x 10/11/12% SELL -- 12 MONTHS -- $100K PER STOCK")
    print(f"{'='*155}")

    header = f"  {'Stock':<6} {'Entry$':>8} {'B&H':>6} |"
    for dip, sell in COMBOS:
        label = f"d{dip}s{sell}"
        header += f" {label:>8} {'#':>3} |"
    print(header)
    print(f"  {'-'*150}")

    totals = {f"d{d}s{s}": 0 for d, s in COMBOS}
    total_bah = 0
    n = len(rows)

    # Track 3x hits
    hits_3x = {f"d{d}s{s}": 0 for d, s in COMBOS}
    beats_bah = {f"d{d}s{s}": 0 for d, s in COMBOS}

    for r in rows:
        bah = r["bah"]
        total_bah += bah

        best_key = max(r["results"], key=lambda k: r["results"][k]["ret"])

        line = f"  {r['sym']:<6} ${r['entry']:>7.2f} {bah:>+5.0f}% |"
        for dip, sell in COMBOS:
            key = f"d{dip}s{sell}"
            res = r["results"][key]
            totals[key] += res["ret"]
            if res["ret"] > bah:
                beats_bah[key] += 1
            if res["peak"] >= 200 or res["ret"] >= 200:
                hits_3x[key] += 1
            mark = "*" if key == best_key else " "
            line += f" {res['ret']:>+7.0f}%{mark} {res['trades']:>3} |"
        print(line)

    # Averages
    print(f"  {'-'*150}")
    best_avg_key = max(totals, key=lambda k: totals[k])
    avg_line = f"  {'AVG':<6} {'':>8} {total_bah/n:>+5.0f}% |"
    for dip, sell in COMBOS:
        key = f"d{dip}s{sell}"
        mark = "*" if key == best_avg_key else " "
        avg_line += f" {totals[key]/n:>+7.0f}%{mark} {'':>3} |"
    print(avg_line)
    print(f"  * = best combo for that stock/average")

    # Summary
    print(f"\n{'='*155}")
    print(f"  SUMMARY")
    print(f"{'='*155}")
    print(f"  {'Combo':<12} {'Avg Return':>12} {'vs B&H':>10} {'Beats B&H':>12} {'Hits 3x':>10}")
    print(f"  {'-'*60}")

    for dip, sell in COMBOS:
        key = f"d{dip}s{sell}"
        avg = totals[key] / n
        vs = avg - total_bah / n
        print(f"  d{dip}/s{sell}    {avg:>+11.1f}% {vs:>+9.1f}% {beats_bah[key]:>10}/{n} {hits_3x[key]:>8}/{n}")

    print(f"  {'B&H':<12} {total_bah/n:>+11.1f}%")

    best_d, best_s = max(COMBOS, key=lambda c: totals[f"d{c[0]}s{c[1]}"])
    best_key = f"d{best_d}s{best_s}"
    print(f"\n  WINNER: {best_d}% dip + {best_s}% sell + lookback 5d")
    print(f"  Avg return: {totals[best_key]/n:+.1f}% | Beats B&H: {beats_bah[best_key]}/{n} | Hits 3x: {hits_3x[best_key]}/{n}")

    # Portfolio value
    print(f"\n  PORTFOLIO VALUE ($100K x {n} = ${n*100}K):")
    for dip, sell in COMBOS:
        key = f"d{dip}s{sell}"
        total_val = sum(STARTING_CASH * (1 + r["results"][key]["ret"]/100) for r in rows)
        print(f"    d{dip}/s{sell}: ${total_val:>12,.0f}  ({(total_val - n*STARTING_CASH)/(n*STARTING_CASH)*100:+.1f}%)")

    bah_total = sum(STARTING_CASH * (1 + r["bah"]/100) for r in rows)
    print(f"    B&H:      ${bah_total:>12,.0f}  ({(bah_total - n*STARTING_CASH)/(n*STARTING_CASH)*100:+.1f}%)")
    print()


if __name__ == "__main__":
    main()
