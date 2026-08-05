"""Backtest grid: test 3%, 5%, 7%, 9% dip thresholds across all 21 stocks.

For each stock x dip%, find the best sell% and show the return.
100% capital, compound, never sell at a loss.
"""

import numpy as np
import pandas as pd
import yfinance as yf


SYMBOLS = [
    "LRCX", "TSM", "VRT", "AMSC", "AMD", "LLY", "ANET", "FIX",
    "TDW", "TJX", "MLI", "RMD", "HUBB", "ETN", "CDNS", "DECK",
    "AWI", "ISRG", "CTAS", "BMI", "FICO",
]

DIP_THRESHOLDS = [3, 5, 7, 9]


def run_backtest(closes, highs, starting_cash, dip_pct, sell_pct, lookback=10):
    cash = starting_cash
    trades = []
    in_trade = False
    entry_price = quantity = entry_day = 0

    for i in range(lookback, len(closes)):
        price = float(closes.iloc[i])

        if not in_trade:
            recent_high = float(highs.iloc[max(0, i - lookback):i].max())
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
                trades.append({
                    "pnl_pct": round(gain, 2),
                    "hold_days": i - entry_day,
                })
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return final, trades, in_trade


def optimize_for_dip(closes, highs, starting_cash, dip_pct):
    """Find the best sell% for a given dip%."""
    best_final = 0
    best_sell = 0
    best_trades = []
    best_in = False

    for sell_pct in [2, 3, 4, 5, 6, 8, 10, 12, 15, 20]:
        for lookback in [10, 15]:
            final, trades, still_in = run_backtest(
                closes, highs, starting_cash, dip_pct, sell_pct, lookback
            )
            if final > best_final:
                best_final = final
                best_sell = sell_pct
                best_trades = trades
                best_in = still_in

    ret = (best_final - starting_cash) / starting_cash * 100
    return {
        "final": best_final,
        "return_pct": round(ret, 2),
        "sell_pct": best_sell,
        "num_trades": len(best_trades),
        "avg_gain": round(np.mean([t["pnl_pct"] for t in best_trades]), 1) if best_trades else 0,
        "avg_hold": round(np.mean([t["hold_days"] for t in best_trades]), 0) if best_trades else 0,
        "still_in": best_in,
    }


def main():
    starting_cash = 100_000
    grid = {}  # {symbol: {dip%: result}}

    print("Fetching data and backtesting...\n", flush=True)

    for sym in SYMBOLS:
        try:
            t = yf.Ticker(sym)
            df = t.history(period="1y")
            if df.empty or len(df) < 40:
                continue

            closes = df["Close"]
            highs = df["High"]

            # Buy & hold
            fp = float(closes.iloc[0])
            lp = float(closes.iloc[-1])
            bah = (lp - fp) / fp * 100

            grid[sym] = {"bah": round(bah, 1)}

            for dip in DIP_THRESHOLDS:
                result = optimize_for_dip(closes, highs, starting_cash, dip)
                grid[sym][dip] = result

            print(f"  {sym}: B&H {bah:+.0f}% | "
                  f"3%dip: {grid[sym][3]['return_pct']:+.0f}% ({grid[sym][3]['num_trades']}t) | "
                  f"5%dip: {grid[sym][5]['return_pct']:+.0f}% ({grid[sym][5]['num_trades']}t) | "
                  f"7%dip: {grid[sym][7]['return_pct']:+.0f}% ({grid[sym][7]['num_trades']}t) | "
                  f"9%dip: {grid[sym][9]['return_pct']:+.0f}% ({grid[sym][9]['num_trades']}t)")

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    # ====== MAIN RESULTS TABLE ======
    print(f"\n{'='*120}")
    print(f"  RETURN % BY DIP THRESHOLD -- ALL 21 STOCKS -- 1 YEAR -- $100K -- NEVER LOSE")
    print(f"{'='*120}")
    print(f"  {'Stock':<6} {'B&H':>7} {'|':>2} "
          f"{'3% dip':>8} {'sell%':>5} {'#tr':>4} {'|':>2} "
          f"{'5% dip':>8} {'sell%':>5} {'#tr':>4} {'|':>2} "
          f"{'7% dip':>8} {'sell%':>5} {'#tr':>4} {'|':>2} "
          f"{'9% dip':>8} {'sell%':>5} {'#tr':>4} {'|':>2} {'Best':>6}")
    print(f"  {'-'*115}")

    totals = {d: 0 for d in DIP_THRESHOLDS}
    total_bah = 0
    best_dip_count = {d: 0 for d in DIP_THRESHOLDS}

    sorted_syms = sorted(grid.keys(),
                         key=lambda s: max(grid[s][d]["return_pct"] for d in DIP_THRESHOLDS),
                         reverse=True)

    for sym in sorted_syms:
        g = grid[sym]
        bah = g["bah"]
        total_bah += bah

        cols = []
        best_d = 0
        best_ret = -999

        for d in DIP_THRESHOLDS:
            r = g[d]
            totals[d] += r["return_pct"]
            cols.append(f"{r['return_pct']:>+7.0f}% {r['sell_pct']:>4}% {r['num_trades']:>4}")
            if r["return_pct"] > best_ret:
                best_ret = r["return_pct"]
                best_d = d

        best_dip_count[best_d] += 1
        best_s = f"{best_d}%"

        print(f"  {sym:<6} {bah:>+6.0f}% | {cols[0]} | {cols[1]} | {cols[2]} | {cols[3]} | {best_s:>5}")

    # ====== AVERAGES ======
    n = len(grid)
    print(f"  {'-'*115}")
    avg_cols = []
    for d in DIP_THRESHOLDS:
        avg_cols.append(f"{totals[d]/n:>+7.0f}%{'':>5}{'':>5}")
    print(f"  {'AVG':<6} {total_bah/n:>+6.0f}% | {avg_cols[0]} | {avg_cols[1]} | {avg_cols[2]} | {avg_cols[3]} |")

    # ====== SUMMARY ======
    print(f"\n{'='*120}")
    print(f"  SUMMARY")
    print(f"{'='*120}")
    print(f"  {'Dip %':<10} {'Avg Return':>12} {'vs B&H':>10} {'Best for # stocks':>20}")
    print(f"  {'-'*55}")
    avg_bah = total_bah / n
    for d in DIP_THRESHOLDS:
        avg = totals[d] / n
        vs = avg - avg_bah
        print(f"  {d}% dip     {avg:>+11.1f}% {vs:>+9.1f}% {best_dip_count[d]:>15} stocks")
    print(f"  B&H        {avg_bah:>+11.1f}%{'':>10}{'':>20}")

    # Winner
    best_overall = max(DIP_THRESHOLDS, key=lambda d: totals[d])
    print(f"\n  WINNER: {best_overall}% dip threshold "
          f"(avg {totals[best_overall]/n:+.1f}% vs B&H {avg_bah:+.1f}%)")
    print()


if __name__ == "__main__":
    main()
