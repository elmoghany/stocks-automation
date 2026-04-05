"""Backtest optimized Never Lose strategy on all 21 PASS stocks.

For each stock: find the best (dip%, sell%, lookback) combo that maximizes return.
100% capital, compound profits, never sell at a loss.
"""

import numpy as np
import pandas as pd
import yfinance as yf


SYMBOLS = [
    "LRCX", "TSM", "VRT", "AMSC", "AMD", "LLY", "ANET", "FIX",
    "TDW", "TJX", "MLI", "RMD", "HUBB", "ETN", "CDNS", "DECK",
    "AWI", "ISRG", "CTAS", "BMI", "FICO",
]


def optimize_stock(symbol, df, starting_cash):
    """Find the best parameters for a stock."""
    closes = df["Close"]
    highs = df["High"]

    first_price = float(closes.iloc[0])
    last_price = float(closes.iloc[-1])
    bah_shares = int(starting_cash // first_price)
    bah_final = bah_shares * last_price + (starting_cash - bah_shares * first_price)
    bah_return = (bah_final - starting_cash) / starting_cash * 100

    best = None

    for dip_pct in [2, 3, 4, 5, 6, 8, 10]:
        for sell_pct in [3, 4, 5, 6, 8, 10, 12, 15]:
            for lookback in [10, 15, 20]:
                cash = starting_cash
                trades = []
                in_trade = False
                entry_price = quantity = entry_day = 0

                for i in range(lookback, len(closes)):
                    price = float(closes.iloc[i])

                    if not in_trade:
                        recent_high = float(highs.iloc[max(0, i-lookback):i].max())
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
                                "entry_date": str(closes.index[entry_day].date()),
                                "exit_date": str(closes.index[i].date()),
                                "entry": round(entry_price, 2),
                                "exit": round(price, 2),
                                "pnl_pct": round(gain, 2),
                                "hold_days": i - entry_day,
                                "cash_after": round(cash, 2),
                            })
                            in_trade = False

                final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)

                if best is None or final > best["final"]:
                    best = {
                        "final": final,
                        "trades": trades,
                        "dip_pct": dip_pct,
                        "sell_pct": sell_pct,
                        "lookback": lookback,
                        "still_in": in_trade,
                    }

    ret = (best["final"] - starting_cash) / starting_cash * 100
    best["return_pct"] = round(ret, 2)
    best["bah_return"] = round(bah_return, 2)
    best["bah_final"] = round(bah_final, 2)
    best["beats_bah"] = ret > bah_return
    best["symbol"] = symbol
    best["num_trades"] = len(best["trades"])

    if best["trades"]:
        best["avg_gain"] = round(np.mean([t["pnl_pct"] for t in best["trades"]]), 2)
        best["avg_hold"] = round(np.mean([t["hold_days"] for t in best["trades"]]), 1)
    else:
        best["avg_gain"] = 0
        best["avg_hold"] = 0

    return best


def main():
    starting_cash = 100_000
    all_results = []

    print(f"\n{'='*120}")
    print(f"  OPTIMIZED NEVER LOSE BACKTEST -- ALL 21 STOCKS -- 1 YEAR -- $100K EACH")
    print(f"{'='*120}\n")

    for sym in SYMBOLS:
        print(f"Optimizing {sym}...", end=" ", flush=True)
        try:
            t = yf.Ticker(sym)
            df = t.history(period="1y")
            if df.empty or len(df) < 40:
                print("NO DATA")
                continue

            result = optimize_stock(sym, df, starting_cash)
            all_results.append(result)

            marker = "BEATS B&H" if result["beats_bah"] else ""
            print(f"dip={result['dip_pct']}% sell=+{result['sell_pct']}% "
                  f"look={result['lookback']}d | "
                  f"{result['num_trades']} trades | "
                  f"Wave: {result['return_pct']:+.1f}% vs B&H: {result['bah_return']:+.1f}% "
                  f"{marker}")

        except Exception as e:
            print(f"ERROR: {e}")

    # Sort by return
    all_results.sort(key=lambda x: -x["return_pct"])

    # Summary table
    print(f"\n{'='*120}")
    print(f"  RESULTS RANKED BY WAVE RETURN")
    print(f"{'='*120}")
    print(f"  {'#':>3} {'Stock':<6} {'Dip%':>5} {'Sell%':>6} {'Look':>5} {'Trades':>7} "
          f"{'AvgGain':>8} {'AvgHold':>8} {'Wave $':>11} {'Wave %':>8} "
          f"{'B&H %':>8} {'vs B&H':>8} {'Winner':>10}")
    print(f"  {'-'*110}")

    total_wave = 0
    total_bah = 0
    beats_count = 0

    for i, r in enumerate(all_results, 1):
        vs = r["return_pct"] - r["bah_return"]
        winner = "WAVE" if r["beats_bah"] else "B&H"
        if r["beats_bah"]:
            beats_count += 1
        total_wave += r["final"]
        total_bah += r["bah_final"]

        print(f"  {i:>3} {r['symbol']:<6} {r['dip_pct']:>4}% {r['sell_pct']:>+5}% "
              f"{r['lookback']:>4}d {r['num_trades']:>7} "
              f"{r['avg_gain']:>+7.1f}% {r['avg_hold']:>7.1f}d "
              f"${r['final']:>10,.0f} {r['return_pct']:>+7.1f}% "
              f"{r['bah_return']:>+7.1f}% {vs:>+7.1f}% {winner:>10}")

    # Show trade details for top 5
    print(f"\n{'='*120}")
    print(f"  TRADE DETAILS -- TOP 5 STOCKS")
    print(f"{'='*120}")

    for r in all_results[:5]:
        print(f"\n  {r['symbol']}: dip>={r['dip_pct']}%, sell +{r['sell_pct']}%, "
              f"lookback {r['lookback']}d")
        print(f"  $100K -> ${r['final']:,.0f} ({r['return_pct']:+.1f}%) | "
              f"B&H: {r['bah_return']:+.1f}%")
        if r["trades"]:
            for j, t in enumerate(r["trades"], 1):
                print(f"    {j}. {t['entry_date']} buy ${t['entry']:.2f} -> "
                      f"{t['exit_date']} sell ${t['exit']:.2f} "
                      f"({t['pnl_pct']:+.1f}%, {t['hold_days']}d) "
                      f"-> ${t['cash_after']:,.0f}")
        if r["still_in"]:
            print(f"    !! Still holding position")

    # Grand summary
    total_wave_ret = (total_wave - starting_cash * len(all_results)) / (starting_cash * len(all_results)) * 100
    total_bah_ret = (total_bah - starting_cash * len(all_results)) / (starting_cash * len(all_results)) * 100

    print(f"\n{'='*120}")
    print(f"  GRAND SUMMARY")
    print(f"{'='*120}")
    print(f"  Stocks tested:          {len(all_results)}")
    print(f"  Wave beats B&H:         {beats_count} / {len(all_results)} "
          f"({beats_count/len(all_results)*100:.0f}%)")
    print(f"  Total capital:          ${starting_cash * len(all_results):,} "
          f"($100K x {len(all_results)} stocks)")
    print(f"  Wave total value:       ${total_wave:,.0f} ({total_wave_ret:+.1f}%)")
    print(f"  B&H total value:        ${total_bah:,.0f} ({total_bah_ret:+.1f}%)")
    print(f"  Wave advantage:         {total_wave_ret - total_bah_ret:+.1f}%")
    print(f"  Winner:                 {'WAVE TRADING' if total_wave > total_bah else 'BUY & HOLD'}")
    print()


if __name__ == "__main__":
    main()
