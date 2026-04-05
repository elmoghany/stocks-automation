"""Brute force: find EVERY parameter combo that gets AMD to 3x ($300K+).

Test thousands of combinations of:
- dip%: 0.5 to 5 in 0.5 steps
- sell%: 2 to 20 in 0.5 steps
- lookback: 5 to 20 in 1 steps

Find ALL combos that hit 3x. Then show the best ones.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from itertools import product


def run(closes, highs, dip_pct, sell_pct, lookback):
    cash = 100_000
    trades = []
    in_trade = False
    entry_price = quantity = entry_day = 0
    peak_cash = cash

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
                    "entry_date": str(closes.index[entry_day].date()),
                    "exit_date": str(closes.index[i].date()),
                    "buy": round(entry_price, 2),
                    "sell": round(price, 2),
                    "gain": round(gain, 1),
                    "days": i - entry_day,
                    "cash": round(cash, 2),
                })
                if cash > peak_cash:
                    peak_cash = cash
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return final, trades, in_trade, peak_cash


def main():
    print("Fetching AMD 1Y data...", flush=True)
    t = yf.Ticker("AMD")
    df = t.history(period="1y")
    closes = df["Close"]
    highs = df["High"]

    fp = float(closes.iloc[0])
    lp = float(closes.iloc[-1])
    print(f"AMD: ${fp:.2f} -> ${lp:.2f} ({(lp-fp)/fp*100:+.1f}% B&H)\n")

    # Brute force search
    winners = []
    total_combos = 0

    dip_range = np.arange(0.5, 5.5, 0.5)
    sell_range = np.arange(2, 21, 0.5)
    look_range = range(5, 21)

    total = len(dip_range) * len(sell_range) * len(look_range)
    print(f"Testing {total:,} parameter combinations...", flush=True)

    for dip_pct in dip_range:
        for sell_pct in sell_range:
            for lookback in look_range:
                total_combos += 1
                final, trades, still_in, peak = run(closes, highs, dip_pct, sell_pct, lookback)

                if peak >= 300_000 or final >= 300_000:
                    winners.append({
                        "dip": round(dip_pct, 1),
                        "sell": round(sell_pct, 1),
                        "look": lookback,
                        "final": round(final, 0),
                        "peak": round(peak, 0),
                        "trades": len(trades),
                        "still_in": still_in,
                        "trade_list": trades,
                    })

        print(f"  dip={dip_pct:.1f}% done, {len(winners)} winners so far", flush=True)

    print(f"\nTested {total_combos:,} combos. Found {len(winners)} that hit 3x.\n")

    if not winners:
        print("NO COMBO HITS 3x. Showing top 10 closest:")
        # Rerun and collect top 10
        top = []
        for dip_pct in dip_range:
            for sell_pct in sell_range:
                for lookback in look_range:
                    final, trades, still_in, peak = run(closes, highs, dip_pct, sell_pct, lookback)
                    top.append((final, peak, round(dip_pct,1), round(sell_pct,1), lookback, len(trades), still_in))
        top.sort(key=lambda x: -max(x[0], x[1]))
        for i, (f, p, d, s, l, n, si) in enumerate(top[:10], 1):
            print(f"  {i}. dip={d}% sell=+{s}% look={l}d | final=${f:,.0f} peak=${p:,.0f} | {n} trades | open={si}")
        return

    # Sort winners by final value
    winners.sort(key=lambda x: -x["final"])

    # Show top 20
    print(f"{'='*100}")
    print(f"  ALL COMBOS THAT HIT 3x ($300K+) ON AMD -- TOP 20")
    print(f"{'='*100}")
    print(f"  {'#':>3} {'Dip%':>5} {'Sell%':>6} {'Look':>5} {'Trades':>7} "
          f"{'Peak$':>10} {'Final$':>10} {'Return':>8} {'Open?':>6}")
    print(f"  {'-'*70}")

    for i, w in enumerate(winners[:20], 1):
        ret = (w["final"] - 100_000) / 100_000 * 100
        open_s = "YES" if w["still_in"] else "--"
        print(f"  {i:>3} {w['dip']:>4.1f}% {w['sell']:>+5.1f}% {w['look']:>4}d {w['trades']:>7} "
              f"${w['peak']:>9,.0f} ${w['final']:>9,.0f} {ret:>+7.1f}% {open_s:>6}")

    # Show trade details for #1
    best = winners[0]
    print(f"\n{'='*100}")
    print(f"  BEST: dip={best['dip']}% sell=+{best['sell']}% lookback={best['look']}d")
    print(f"  Result: $100K -> ${best['final']:,.0f} (peak ${best['peak']:,.0f})")
    print(f"{'='*100}")

    if best["trade_list"]:
        print(f"\n  {'#':>3} {'Entry':<12} {'Exit':<12} {'Buy':>9} {'Sell':>9} "
              f"{'Gain%':>7} {'Days':>5} {'Cash After':>12}")
        print(f"  {'-'*80}")
        for j, t in enumerate(best["trade_list"], 1):
            print(f"  {j:>3} {t['entry_date']:<12} {t['exit_date']:<12} "
                  f"${t['buy']:>8.2f} ${t['sell']:>8.2f} "
                  f"{t['gain']:>+6.1f}% {t['days']:>5}d ${t['cash']:>11,.2f}")

    if best["still_in"]:
        print(f"\n  !! Open trade dragging final value below peak")

    # Summary of winning parameter ranges
    dips = [w["dip"] for w in winners]
    sells = [w["sell"] for w in winners]
    looks = [w["look"] for w in winners]

    print(f"\n{'='*100}")
    print(f"  3x PARAMETER SWEET SPOT")
    print(f"{'='*100}")
    print(f"  Dip%:     {min(dips):.1f}% to {max(dips):.1f}% (most common: {max(set(dips), key=dips.count):.1f}%)")
    print(f"  Sell%:    +{min(sells):.1f}% to +{max(sells):.1f}% (most common: +{max(set(sells), key=sells.count):.1f}%)")
    print(f"  Lookback: {min(looks)}d to {max(looks)}d (most common: {max(set(looks), key=looks.count)}d)")
    print(f"  Total 3x combos: {len(winners)} out of {total_combos:,} tested ({len(winners)/total_combos*100:.2f}%)")
    print()


if __name__ == "__main__":
    main()
