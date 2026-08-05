"""Clean backtest table: stock, entry price, B&H%, 3/5/7/9% dip returns, notes."""

import numpy as np
import pandas as pd
import yfinance as yf

SYMBOLS = [
    "LRCX", "TSM", "VRT", "AMSC", "AMD", "LLY", "ANET", "FIX",
    "TDW", "TJX", "MLI", "RMD", "HUBB", "ETN", "CDNS", "DECK",
    "AWI", "ISRG", "CTAS", "BMI", "FICO",
]

STARTING_CASH = 100_000


def run_backtest(closes, highs, dip_pct, sell_pct, lookback=10):
    cash = STARTING_CASH
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
                trades.append({"pnl_pct": round(gain, 1), "days": i - entry_day})
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    ret = (final - STARTING_CASH) / STARTING_CASH * 100
    return round(ret, 1), len(trades), trades, in_trade


def best_for_dip(closes, highs, dip_pct):
    best_ret = -999
    best_sell = 0
    best_trades = 0
    best_list = []
    best_in = False
    for sell_pct in [2, 3, 4, 5, 6, 8, 10, 12, 15, 20]:
        for lookback in [10, 15]:
            ret, n, tlist, still_in = run_backtest(closes, highs, dip_pct, sell_pct, lookback)
            if ret > best_ret:
                best_ret = ret
                best_sell = sell_pct
                best_trades = n
                best_list = tlist
                best_in = still_in
    return best_ret, best_sell, best_trades, best_list, best_in


def generate_note(sym, bah, results):
    """Generate a short note/tip for each stock."""
    rets = {d: results[d][0] for d in [3, 5, 7, 9]}
    best_dip = max(rets, key=lambda d: rets[d])
    best_ret = rets[best_dip]
    trades_at_best = results[best_dip][2]

    # Determine stock behavior
    if bah > 100:
        trend = "strong uptrend"
    elif bah > 30:
        trend = "moderate uptrend"
    elif bah > 0:
        trend = "mild uptrend"
    else:
        trend = "downtrend"

    # Best dip note
    if best_dip == 3:
        dip_note = "tight dips, trade often"
    elif best_dip == 5:
        dip_note = "moderate dips work best"
    elif best_dip == 7:
        dip_note = "wait for real pullbacks"
    else:
        dip_note = "only deep dips are safe"

    # Compounding note
    if trades_at_best >= 10:
        freq_note = "high freq compounding"
    elif trades_at_best >= 5:
        freq_note = "good trade frequency"
    elif trades_at_best >= 2:
        freq_note = "few trades but solid"
    else:
        freq_note = "rare signals"

    # Special notes
    special = ""
    if best_ret > bah + 50:
        special = " | WAVE MUCH BETTER"
    elif best_ret > bah:
        special = " | wave wins"
    elif best_ret > bah - 10:
        special = " | close to B&H"
    else:
        special = " | B&H better here"

    # Sell% note
    best_sell = results[best_dip][1]
    if best_sell <= 4:
        sell_note = f"quick scalp +{best_sell}%"
    elif best_sell <= 8:
        sell_note = f"medium swing +{best_sell}%"
    else:
        sell_note = f"full wave +{best_sell}%"

    return f"{trend}; best {best_dip}%dip; {sell_note}; {freq_note}{special}"


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
            for d in [3, 5, 7, 9]:
                ret, sell, trades, tlist, still_in = best_for_dip(closes, highs, d)
                results[d] = (ret, sell, trades, tlist, still_in)

            note = generate_note(sym, bah, results)

            rows.append({
                "sym": sym,
                "entry": entry_price,
                "bah": bah,
                "d3": results[3][0],
                "d5": results[5][0],
                "d7": results[7][0],
                "d9": results[9][0],
                "d3_t": results[3][2],
                "d5_t": results[5][2],
                "d7_t": results[7][2],
                "d9_t": results[9][2],
                "note": note,
            })

            best_d = max([3, 5, 7, 9], key=lambda d: results[d][0])
            print(f"  {sym}: entry ${entry_price}, B&H {bah:+.0f}%, best {best_d}%dip -> {results[best_d][0]:+.0f}%")

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    # Sort by best return across any dip
    rows.sort(key=lambda r: max(r["d3"], r["d5"], r["d7"], r["d9"]), reverse=True)

    # Print table
    print(f"\n{'='*160}")
    print(f"  NEVER LOSE WAVE TRADING -- 12 MONTH BACKTEST -- $100K CAPITAL PER STOCK")
    print(f"{'='*160}")
    print(f"  {'Stock':<6} {'Entry$':>8} {'B&H%':>7} | "
          f"{'3%dip':>7} {'(#)':>4} | "
          f"{'5%dip':>7} {'(#)':>4} | "
          f"{'7%dip':>7} {'(#)':>4} | "
          f"{'9%dip':>7} {'(#)':>4} | "
          f"{'Note'}")
    print(f"  {'-'*155}")

    total_bah = 0
    total_d3 = total_d5 = total_d7 = total_d9 = 0

    for r in rows:
        best_val = max(r["d3"], r["d5"], r["d7"], r["d9"])

        # Mark the best dip with *
        d3s = f"{r['d3']:>+6.0f}%{'*' if r['d3']==best_val else ' '}"
        d5s = f"{r['d5']:>+6.0f}%{'*' if r['d5']==best_val else ' '}"
        d7s = f"{r['d7']:>+6.0f}%{'*' if r['d7']==best_val else ' '}"
        d9s = f"{r['d9']:>+6.0f}%{'*' if r['d9']==best_val else ' '}"

        print(f"  {r['sym']:<6} ${r['entry']:>7.2f} {r['bah']:>+6.0f}% | "
              f"{d3s} {r['d3_t']:>3} | "
              f"{d5s} {r['d5_t']:>3} | "
              f"{d7s} {r['d7_t']:>3} | "
              f"{d9s} {r['d9_t']:>3} | "
              f"{r['note']}")

        total_bah += r["bah"]
        total_d3 += r["d3"]
        total_d5 += r["d5"]
        total_d7 += r["d7"]
        total_d9 += r["d9"]

    n = len(rows)
    print(f"  {'-'*155}")

    avg_best = max(total_d3, total_d5, total_d7, total_d9)
    d3m = "*" if total_d3 == avg_best else " "
    d5m = "*" if total_d5 == avg_best else " "
    d7m = "*" if total_d7 == avg_best else " "
    d9m = "*" if total_d9 == avg_best else " "

    print(f"  {'AVG':<6} {'':>8} {total_bah/n:>+6.0f}% | "
          f"{total_d3/n:>+6.0f}%{d3m} {'':>3} | "
          f"{total_d5/n:>+6.0f}%{d5m} {'':>3} | "
          f"{total_d7/n:>+6.0f}%{d7m} {'':>3} | "
          f"{total_d9/n:>+6.0f}%{d9m} {'':>3} | "
          f"* = best dip% for this stock/average")

    print(f"\n  Portfolio ($100K x {n} = ${n*100}K):")
    print(f"    B&H:   ${n*STARTING_CASH + int(total_bah/100*n*STARTING_CASH/n):>12,}")
    print(f"    3%dip: ${n*STARTING_CASH + int(total_d3/100*n*STARTING_CASH/n):>12,} (extra ${int((total_d3-total_bah)/100*STARTING_CASH):>+,} vs B&H)")
    print(f"    5%dip: ${n*STARTING_CASH + int(total_d5/100*n*STARTING_CASH/n):>12,} (extra ${int((total_d5-total_bah)/100*STARTING_CASH):>+,} vs B&H)")
    print(f"    7%dip: ${n*STARTING_CASH + int(total_d7/100*n*STARTING_CASH/n):>12,} (extra ${int((total_d7-total_bah)/100*STARTING_CASH):>+,} vs B&H)")
    print(f"    9%dip: ${n*STARTING_CASH + int(total_d9/100*n*STARTING_CASH/n):>12,} (extra ${int((total_d9-total_bah)/100*STARTING_CASH):>+,} vs B&H)")
    print()


if __name__ == "__main__":
    main()
