"""Backtest: Original Never Lose strategy on AMD -- full target, no 20% range.

Buy when: price dips from recent high by median_down_pct (10.61% for AMD)
Sell when: price hits full median_up_pct (12.93% above buy price)
Never sell at a loss. 100% capital. Compound profits.
"""

import numpy as np
import pandas as pd
import yfinance as yf


def main():
    starting_cash = 100_000

    print("Fetching AMD 1Y data...", flush=True)
    t = yf.Ticker("AMD")
    df = t.history(period="1y")
    closes = df["Close"]
    highs = df["High"]
    lows = df["Low"]

    first_price = float(closes.iloc[0])
    last_price = float(closes.iloc[-1])
    bah_return = (last_price - first_price) / first_price * 100

    print(f"AMD: ${first_price:.2f} -> ${last_price:.2f} ({bah_return:+.1f}% buy&hold)")
    print(f"Trading days: {len(df)}\n")

    # AMD wave stats from our analysis
    med_down_pct = 10.61   # median down wave %
    med_up_pct = 12.93     # median up wave % (full target, no 20% discount)

    # Also test variations of the target
    results = []

    for sell_pct in [med_up_pct, med_up_pct * 0.9, med_up_pct * 0.8,
                     med_up_pct * 0.7, med_up_pct * 0.5,
                     8, 6, 5, 4, 3]:
        for dip_pct in [med_down_pct, med_down_pct * 0.8, med_down_pct * 0.6,
                        med_down_pct * 0.5, med_down_pct * 0.4,
                        8, 6, 5, 4, 3, 2]:
            for lookback in [10, 15, 20]:
                cash = starting_cash
                trades = []
                in_trade = False
                entry_price = quantity = entry_day = 0

                for i in range(lookback, len(closes)):
                    price = float(closes.iloc[i])

                    if not in_trade:
                        recent_high = float(highs.iloc[max(0, i-lookback):i].max())
                        dip_from_high = (recent_high - price) / recent_high * 100

                        if dip_from_high >= dip_pct and cash > price:
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
                                "qty": quantity,
                                "pnl": round((price - entry_price) * quantity, 2),
                                "pnl_pct": round(gain, 2),
                                "hold_days": i - entry_day,
                                "cash_after": round(cash, 2),
                            })
                            in_trade = False

                final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
                ret = (final - starting_cash) / starting_cash * 100
                results.append({
                    "dip_pct": round(dip_pct, 2),
                    "sell_pct": round(sell_pct, 2),
                    "lookback": lookback,
                    "trades": len(trades),
                    "final": round(final, 2),
                    "return_pct": round(ret, 2),
                    "trade_list": trades,
                    "still_in": in_trade,
                })

    # Sort by return
    results.sort(key=lambda x: -x["return_pct"])

    # Print top 10
    print(f"{'='*100}")
    print(f"  TOP 10 PARAMETER COMBINATIONS (out of {len(results)} tested)")
    print(f"{'='*100}")
    print(f"  {'#':>3} {'Dip%':>6} {'Sell%':>6} {'Look':>5} {'Trades':>7} "
          f"{'Final':>12} {'Return':>9} {'Open?':>6}")
    print(f"  {'-'*70}")

    for i, r in enumerate(results[:10], 1):
        open_s = "YES" if r["still_in"] else "--"
        print(f"  {i:>3} {r['dip_pct']:>5.1f}% {r['sell_pct']:>5.1f}% {r['lookback']:>5}d "
              f"{r['trades']:>7} ${r['final']:>11,.0f} {r['return_pct']:>+8.1f}% {open_s:>6}")

    # Show detailed trades for #1
    best = results[0]
    print(f"\n{'='*100}")
    print(f"  BEST: Buy on {best['dip_pct']}% dip, sell at +{best['sell_pct']}%, "
          f"lookback {best['lookback']}d")
    print(f"  Result: $100K -> ${best['final']:,.0f} ({best['return_pct']:+.1f}%)")
    print(f"{'='*100}")

    if best["trade_list"]:
        print(f"\n  {'#':>3} {'Entry':<12} {'Exit':<12} {'Buy':>9} {'Sell':>9} "
              f"{'Qty':>6} {'P&L':>10} {'Gain%':>7} {'Days':>5} {'Cash After':>12}")
        print(f"  {'-'*100}")
        for j, t in enumerate(best["trade_list"], 1):
            print(f"  {j:>3} {t['entry_date']:<12} {t['exit_date']:<12} "
                  f"${t['entry']:>8.2f} ${t['exit']:>8.2f} "
                  f"{t['qty']:>6} ${t['pnl']:>+9.2f} {t['pnl_pct']:>+6.2f}% "
                  f"{t['hold_days']:>5}d ${t['cash_after']:>11,.2f}")

    if best["still_in"]:
        print(f"\n  !! Still holding at end of period")

    # Also show the original exact config
    print(f"\n{'='*100}")
    print(f"  YOUR ORIGINAL CONFIG: Buy on {med_down_pct}% dip, sell at +{med_up_pct}%")
    print(f"{'='*100}")

    original = None
    for r in results:
        if abs(r["dip_pct"] - med_down_pct) < 0.1 and abs(r["sell_pct"] - med_up_pct) < 0.1 and r["lookback"] == 15:
            original = r
            break
    if original is None:
        for r in results:
            if abs(r["dip_pct"] - med_down_pct) < 0.1 and abs(r["sell_pct"] - med_up_pct) < 0.1:
                original = r
                break

    if original:
        print(f"  Trades: {original['trades']} | "
              f"Return: ${starting_cash:,} -> ${original['final']:,.0f} ({original['return_pct']:+.1f}%)")
        if original["trade_list"]:
            for j, t in enumerate(original["trade_list"], 1):
                print(f"    Trade {j}: buy ${t['entry']:.2f} -> sell ${t['exit']:.2f} "
                      f"({t['pnl_pct']:+.1f}%, {t['hold_days']}d, P&L ${t['pnl']:+,.0f})")
        if original["still_in"]:
            print(f"    !! Still holding at end of period")
    else:
        print(f"  Not found in results")

    # Comparison
    bah_shares = int(starting_cash // first_price)
    bah_final = bah_shares * last_price + (starting_cash - bah_shares * first_price)

    print(f"\n{'='*100}")
    print(f"  COMPARISON")
    print(f"{'='*100}")
    print(f"  Buy & Hold:        $100K -> ${bah_final:>10,.0f}  ({bah_return:>+7.1f}%)")
    print(f"  Original config:   $100K -> ${original['final'] if original else 0:>10,.0f}  "
          f"({original['return_pct'] if original else 0:>+7.1f}%)  "
          f"{original['trades'] if original else 0} trades")
    print(f"  Best config:       $100K -> ${best['final']:>10,.0f}  ({best['return_pct']:>+7.1f}%)  "
          f"{best['trades']} trades")
    print(f"  Target (3x):       $100K -> $   300,000  (+200.0%)")
    print()

    # What trade frequency would hit 3x?
    if best["trade_list"]:
        avg_gain = np.mean([t["pnl_pct"] for t in best["trade_list"]])
        n_for_3x = np.log(3) / np.log(1 + avg_gain / 100)
        print(f"  At avg gain of {avg_gain:.1f}% per trade, need {n_for_3x:.0f} trades to hit 3x")
        print(f"  That's {n_for_3x/12:.1f} trades/month over 1 year")
    print()


if __name__ == "__main__":
    main()
