"""Backtest: $100K per stock, 12 months (Apr 2025 - Mar 2026), 3/5/7/9% dips.

For each stock, run all 4 dip thresholds with the best sell% per combo.
Show monthly breakdown and final comparison.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta


SYMBOLS = [
    "LRCX", "TSM", "VRT", "AMSC", "AMD", "LLY", "ANET", "FIX",
    "TDW", "TJX", "MLI", "RMD", "HUBB", "ETN", "CDNS", "DECK",
    "AWI", "ISRG", "CTAS", "BMI", "FICO",
]

DIP_THRESHOLDS = [3, 5, 7, 9]
STARTING_CASH = 100_000


def run_backtest(closes, highs, dip_pct, sell_pct, lookback=10):
    cash = STARTING_CASH
    trades = []
    in_trade = False
    entry_price = quantity = entry_day = 0

    for i in range(lookback, len(closes)):
        price = float(closes.iloc[i])
        date = str(closes.index[i].date())
        month = closes.index[i].strftime("%Y-%m")

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
                pnl = (price - entry_price) * quantity
                cash += quantity * price
                trades.append({
                    "entry_date": str(closes.index[entry_day].date()),
                    "exit_date": date,
                    "exit_month": month,
                    "entry": round(entry_price, 2),
                    "exit": round(price, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(gain, 2),
                    "hold_days": i - entry_day,
                    "cash_after": round(cash, 2),
                })
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return final, trades, in_trade


def optimize_for_dip(closes, highs, dip_pct):
    best_final = 0
    best_sell = 0
    best_trades = []
    best_in = False

    for sell_pct in [2, 3, 4, 5, 6, 8, 10, 12, 15, 20]:
        for lookback in [10, 15]:
            final, trades, still_in = run_backtest(closes, highs, dip_pct, sell_pct, lookback)
            if final > best_final:
                best_final = final
                best_sell = sell_pct
                best_trades = trades
                best_in = still_in

    ret = (best_final - STARTING_CASH) / STARTING_CASH * 100
    return {
        "final": round(best_final, 2),
        "return_pct": round(ret, 1),
        "sell_pct": best_sell,
        "num_trades": len(best_trades),
        "trades": best_trades,
        "still_in": best_in,
        "avg_gain": round(np.mean([t["pnl_pct"] for t in best_trades]), 1) if best_trades else 0,
        "avg_hold": round(np.mean([t["hold_days"] for t in best_trades]), 0) if best_trades else 0,
        "total_pnl": round(sum(t["pnl"] for t in best_trades), 2) if best_trades else 0,
    }


def main():
    print(f"\n{'='*130}")
    print(f"  NEVER LOSE BACKTEST -- 12 MONTHS -- $100K PER STOCK -- 3% / 5% / 7% / 9% DIP THRESHOLDS")
    print(f"{'='*130}\n")

    all_data = {}

    for sym in SYMBOLS:
        print(f"  Fetching {sym}...", end=" ", flush=True)
        try:
            t = yf.Ticker(sym)
            df = t.history(period="1y")
            if df.empty or len(df) < 40:
                print("NO DATA")
                continue

            closes = df["Close"]
            highs = df["High"]
            fp = float(closes.iloc[0])
            lp = float(closes.iloc[-1])
            bah_ret = (lp - fp) / fp * 100
            bah_shares = int(STARTING_CASH // fp)
            bah_final = bah_shares * lp + (STARTING_CASH - bah_shares * fp)

            stock_results = {"bah_ret": round(bah_ret, 1), "bah_final": round(bah_final, 2)}

            for dip in DIP_THRESHOLDS:
                stock_results[dip] = optimize_for_dip(closes, highs, dip)

            all_data[sym] = stock_results

            best_dip = max(DIP_THRESHOLDS, key=lambda d: stock_results[d]["return_pct"])
            print(f"B&H {bah_ret:+.0f}% | "
                  f"3%: {stock_results[3]['return_pct']:+.0f}% ({stock_results[3]['num_trades']}t) | "
                  f"5%: {stock_results[5]['return_pct']:+.0f}% ({stock_results[5]['num_trades']}t) | "
                  f"7%: {stock_results[7]['return_pct']:+.0f}% ({stock_results[7]['num_trades']}t) | "
                  f"9%: {stock_results[9]['return_pct']:+.0f}% ({stock_results[9]['num_trades']}t) | "
                  f"Best: {best_dip}%")

        except Exception as e:
            print(f"ERROR: {e}")

    # ====== MAIN TABLE ======
    print(f"\n{'='*130}")
    print(f"  RESULTS TABLE: RETURN % BY DIP THRESHOLD")
    print(f"{'='*130}")
    print(f"  {'Stock':<6} {'B&H':>7} {'|':>1} "
          f"{'3%dip':>7} {'s%':>3} {'#':>3} {'$final':>10} {'|':>1} "
          f"{'5%dip':>7} {'s%':>3} {'#':>3} {'$final':>10} {'|':>1} "
          f"{'7%dip':>7} {'s%':>3} {'#':>3} {'$final':>10} {'|':>1} "
          f"{'9%dip':>7} {'s%':>3} {'#':>3} {'$final':>10} {'|':>1} {'BEST':>5}")
    print(f"  {'-'*125}")

    sorted_syms = sorted(all_data.keys(),
                         key=lambda s: max(all_data[s][d]["return_pct"] for d in DIP_THRESHOLDS),
                         reverse=True)

    portfolio_totals = {d: 0 for d in DIP_THRESHOLDS}
    portfolio_bah = 0

    for sym in sorted_syms:
        g = all_data[sym]
        bah = g["bah_ret"]
        portfolio_bah += g["bah_final"]

        best_d = max(DIP_THRESHOLDS, key=lambda d: g[d]["return_pct"])

        parts = []
        for d in DIP_THRESHOLDS:
            r = g[d]
            portfolio_totals[d] += r["final"]
            parts.append(f"{r['return_pct']:>+6.0f}% {r['sell_pct']:>2}% {r['num_trades']:>3} ${r['final']:>9,.0f}")

        print(f"  {sym:<6} {bah:>+6.0f}% | {parts[0]} | {parts[1]} | {parts[2]} | {parts[3]} | {best_d:>3}%")

    # ====== TOTALS ROW ======
    n = len(all_data)
    total_capital = STARTING_CASH * n
    print(f"  {'-'*125}")

    avg_parts = []
    for d in DIP_THRESHOLDS:
        avg_ret = (portfolio_totals[d] - total_capital) / total_capital * 100
        avg_parts.append(f"{avg_ret:>+6.0f}%{'':>3}{'':>4} ${portfolio_totals[d]:>9,.0f}")

    bah_avg_ret = (portfolio_bah - total_capital) / total_capital * 100
    print(f"  {'TOTAL':<6} {bah_avg_ret:>+6.0f}% | {avg_parts[0]} | {avg_parts[1]} | {avg_parts[2]} | {avg_parts[3]} |")

    # ====== PORTFOLIO SUMMARY ======
    print(f"\n{'='*130}")
    print(f"  PORTFOLIO SUMMARY ($100K x {n} stocks = ${total_capital/1000:.0f}K total capital)")
    print(f"{'='*130}")
    print(f"  {'Strategy':<20} {'Total Value':>14} {'Total Return':>14} {'vs B&H':>10} {'Avg/Stock':>12}")
    print(f"  {'-'*75}")
    print(f"  {'Buy & Hold':<20} ${portfolio_bah:>13,.0f} {bah_avg_ret:>+13.1f}% {'--':>10} {bah_avg_ret:>+11.1f}%")

    for d in DIP_THRESHOLDS:
        total = portfolio_totals[d]
        ret = (total - total_capital) / total_capital * 100
        vs = ret - bah_avg_ret
        avg_per = ret
        marker = " <-- BEST" if total == max(portfolio_totals.values()) else ""
        print(f"  {f'{d}% dip':<20} ${total:>13,.0f} {ret:>+13.1f}% {vs:>+9.1f}% {avg_per:>+11.1f}%{marker}")

    # ====== WINNER ======
    best_overall = max(DIP_THRESHOLDS, key=lambda d: portfolio_totals[d])
    best_total = portfolio_totals[best_overall]
    best_ret = (best_total - total_capital) / total_capital * 100

    print(f"\n  WINNER: {best_overall}% dip threshold")
    print(f"  ${total_capital/1000:.0f}K invested -> ${best_total:,.0f} ({best_ret:+.1f}%)")
    print(f"  Buy & Hold would be: ${portfolio_bah:,.0f} ({bah_avg_ret:+.1f}%)")
    print(f"  Wave advantage: {best_ret - bah_avg_ret:+.1f}%")
    print(f"  Extra profit: ${best_total - portfolio_bah:+,.0f}")

    # ====== PER DIP: HOW MANY STOCKS BEAT B&H ======
    print(f"\n  {'Dip %':<10} {'Beats B&H':>12} {'Loses to B&H':>14}")
    print(f"  {'-'*40}")
    for d in DIP_THRESHOLDS:
        beats = sum(1 for s in all_data if all_data[s][d]["return_pct"] > all_data[s]["bah_ret"])
        loses = n - beats
        print(f"  {d}% dip     {beats:>10}/{n}   {loses:>12}/{n}")

    print()


if __name__ == "__main__":
    main()
