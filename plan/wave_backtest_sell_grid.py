"""Backtest grid: fixed 3% dip, test sell targets 3/5/7/9/11/13/15% across all 21 stocks.

$100K per stock, 1 year, never sell at a loss, compound profits.
"""

import numpy as np
import pandas as pd
import yfinance as yf

SYMBOLS = [
    "LRCX", "TSM", "VRT", "AMSC", "AMD", "LLY", "ANET", "FIX",
    "TDW", "TJX", "MLI", "RMD", "HUBB", "ETN", "CDNS", "DECK",
    "AWI", "ISRG", "CTAS", "BMI", "FICO",
]

DIP_PCT = 3
SELL_TARGETS = [3, 5, 7, 9, 11, 13, 15]
STARTING_CASH = 100_000
LOOKBACK = 10


def run_backtest(closes, highs, sell_pct):
    cash = STARTING_CASH
    trades = []
    in_trade = False
    entry_price = quantity = entry_day = 0

    for i in range(LOOKBACK, len(closes)):
        price = float(closes.iloc[i])

        if not in_trade:
            recent_high = float(highs.iloc[max(0, i - LOOKBACK):i].max())
            dip = (recent_high - price) / recent_high * 100
            if dip >= DIP_PCT and cash > price:
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
    return round(ret, 1), len(trades), trades


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
            for sp in SELL_TARGETS:
                ret, n, tlist = run_backtest(closes, highs, sp)
                avg_hold = round(np.mean([t["days"] for t in tlist]), 0) if tlist else 0
                results[sp] = {"ret": ret, "trades": n, "avg_hold": int(avg_hold)}

            rows.append({"sym": sym, "entry": entry_price, "bah": bah, "results": results})
            print(f"  {sym} done", flush=True)

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    # Sort by best return across any sell%
    rows.sort(key=lambda r: max(r["results"][sp]["ret"] for sp in SELL_TARGETS), reverse=True)

    # Header
    print(f"\n{'='*140}")
    print(f"  FIXED 3% DIP -- SELL TARGET COMPARISON -- 12 MONTHS -- $100K PER STOCK")
    print(f"{'='*140}")

    header = f"  {'Stock':<6} {'Entry$':>8} {'B&H':>6} |"
    for sp in SELL_TARGETS:
        header += f" {'s'+str(sp)+'%':>7} {'#':>3} |"
    print(header)
    print(f"  {'-'*135}")

    totals = {sp: 0 for sp in SELL_TARGETS}
    total_bah = 0
    n = len(rows)

    for r in rows:
        bah = r["bah"]
        total_bah += bah

        best_sp = max(SELL_TARGETS, key=lambda sp: r["results"][sp]["ret"])
        best_ret = r["results"][best_sp]["ret"]

        line = f"  {r['sym']:<6} ${r['entry']:>7.2f} {bah:>+5.0f}% |"
        for sp in SELL_TARGETS:
            res = r["results"][sp]
            totals[sp] += res["ret"]
            mark = "*" if sp == best_sp else " "
            line += f" {res['ret']:>+6.0f}%{mark} {res['trades']:>3} |"
        print(line)

    # Averages
    print(f"  {'-'*135}")
    avg_line = f"  {'AVG':<6} {'':>8} {total_bah/n:>+5.0f}% |"
    best_avg_sp = max(SELL_TARGETS, key=lambda sp: totals[sp])
    for sp in SELL_TARGETS:
        mark = "*" if sp == best_avg_sp else " "
        avg_line += f" {totals[sp]/n:>+6.0f}%{mark} {'':>3} |"
    print(avg_line)
    print(f"  * = best sell% for that stock/average")

    # Trade frequency table
    print(f"\n{'='*140}")
    print(f"  TRADE COUNT & AVG HOLD DAYS BY SELL TARGET")
    print(f"{'='*140}")

    header2 = f"  {'Stock':<6} |"
    for sp in SELL_TARGETS:
        header2 += f" s{sp}%: {'#':>3}t {'hold':>4}d |"
    print(header2)
    print(f"  {'-'*115}")

    total_trades = {sp: 0 for sp in SELL_TARGETS}
    total_hold = {sp: [] for sp in SELL_TARGETS}

    for r in rows:
        line = f"  {r['sym']:<6} |"
        for sp in SELL_TARGETS:
            res = r["results"][sp]
            total_trades[sp] += res["trades"]
            if res["avg_hold"] > 0:
                total_hold[sp].append(res["avg_hold"])
            line += f"       {res['trades']:>3}t {res['avg_hold']:>4}d |"
        print(line)

    print(f"  {'-'*115}")
    total_line = f"  {'TOTAL':<6} |"
    for sp in SELL_TARGETS:
        avg_h = round(np.mean(total_hold[sp])) if total_hold[sp] else 0
        total_line += f"       {total_trades[sp]:>3}t {avg_h:>4}d |"
    print(total_line)

    # Summary
    print(f"\n{'='*140}")
    print(f"  SUMMARY: SELL TARGET IMPACT (fixed 3% dip buy)")
    print(f"{'='*140}")
    print(f"  {'Sell%':<8} {'Avg Return':>12} {'vs B&H':>10} {'Total Trades':>14} {'Avg Hold':>10} {'Trades/Mo':>10}")
    print(f"  {'-'*70}")
    for sp in SELL_TARGETS:
        avg_ret = totals[sp] / n
        vs = avg_ret - total_bah / n
        avg_h = round(np.mean(total_hold[sp])) if total_hold[sp] else 0
        tpm = round(total_trades[sp] / n / 12, 1)
        print(f"  +{sp}% sell   {avg_ret:>+11.1f}% {vs:>+9.1f}% {total_trades[sp]:>14} {avg_h:>8}d {tpm:>9}/mo")
    print(f"  B&H        {total_bah/n:>+11.1f}%")

    best = max(SELL_TARGETS, key=lambda sp: totals[sp])
    print(f"\n  WINNER: +{best}% sell target (avg {totals[best]/n:+.1f}%)")
    print()


if __name__ == "__main__":
    main()
