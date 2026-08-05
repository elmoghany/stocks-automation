"""Backtest: 9/20 EMA Pullback Strategy on AMD (high frequency, uptrend riding).

Strategy:
  - Uptrend confirmed: 9 EMA > 20 EMA, both sloping up
  - BUY: Price pulls back to 9 EMA zone (within 0.5% of 9 EMA)
         OR price enters the 9-20 EMA channel
  - SELL: Price bounces X% above entry (quick scalp)
  - Never sell at a loss (Never Lose still applies)
  - Target: 4+ trades per month

Also test variations:
  A. EMA pullback with fixed % target
  B. EMA pullback selling at prior swing high
  C. EMA pullback with trailing exit (sell when closes below 9 EMA after profit)
"""

import numpy as np
import pandas as pd
import yfinance as yf


def ema(closes, period):
    return closes.ewm(span=period, adjust=False).mean()


def rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def is_uptrend(ema9, ema20, i, lookback=5):
    """Uptrend: 9 EMA > 20 EMA and both sloping up over lookback days."""
    if i < lookback:
        return False
    e9 = float(ema9.iloc[i])
    e20 = float(ema20.iloc[i])
    e9_prev = float(ema9.iloc[i - lookback])
    e20_prev = float(ema20.iloc[i - lookback])
    return e9 > e20 and e9 > e9_prev and e20 > e20_prev


def strategy_a_fixed_target(closes, ema9, ema20, rsi_vals, starting_cash,
                            sell_pct, pullback_zone_pct):
    """Buy at 9 EMA pullback, sell at fixed % gain."""
    cash = starting_cash
    trades = []
    in_trade = False
    entry_price = entry_day = quantity = 0

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        e9 = float(ema9.iloc[i])
        e20 = float(ema20.iloc[i])

        if not in_trade:
            # Buy: price pulled back to within zone of 9 EMA, in uptrend
            near_ema9 = abs(price - e9) / e9 * 100 <= pullback_zone_pct
            in_ema_channel = e20 <= price <= e9 * 1.005

            if is_uptrend(ema9, ema20, i) and (near_ema9 or in_ema_channel) and cash > price:
                quantity = int(cash // price)
                entry_price = price
                entry_day = i
                cash -= quantity * price
                in_trade = True
        else:
            gain_pct = (price - entry_price) / entry_price * 100
            hold_days = i - entry_day

            if gain_pct >= sell_pct:
                cash += quantity * price
                trades.append({
                    "entry_date": str(closes.index[entry_day].date()),
                    "exit_date": str(closes.index[i].date()),
                    "entry": round(entry_price, 2),
                    "exit": round(price, 2),
                    "qty": quantity,
                    "pnl": round((price - entry_price) * quantity, 2),
                    "pnl_pct": round(gain_pct, 2),
                    "hold_days": hold_days,
                    "cash_after": round(cash, 2),
                })
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return final, trades, in_trade


def strategy_b_swing_high(closes, highs, ema9, ema20, starting_cash,
                          pullback_zone_pct):
    """Buy at 9 EMA pullback, sell at prior 10-day swing high."""
    cash = starting_cash
    trades = []
    in_trade = False
    entry_price = entry_day = quantity = 0
    sell_target = 0

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        high = float(highs.iloc[i])
        e9 = float(ema9.iloc[i])
        e20 = float(ema20.iloc[i])

        if not in_trade:
            near_ema9 = abs(price - e9) / e9 * 100 <= pullback_zone_pct
            in_ema_channel = e20 <= price <= e9 * 1.005

            if is_uptrend(ema9, ema20, i) and (near_ema9 or in_ema_channel) and cash > price:
                quantity = int(cash // price)
                entry_price = price
                entry_day = i
                cash -= quantity * price
                # Target: recent 10-day high
                sell_target = float(highs.iloc[max(0, i-10):i].max())
                # Apply 20% range tolerance
                min_gain = (sell_target - price) * 0.80
                sell_min = price + min_gain
                in_trade = True
        else:
            if price >= sell_min and price > entry_price:
                cash += quantity * price
                trades.append({
                    "entry_date": str(closes.index[entry_day].date()),
                    "exit_date": str(closes.index[i].date()),
                    "entry": round(entry_price, 2),
                    "exit": round(price, 2),
                    "target": round(sell_target, 2),
                    "qty": quantity,
                    "pnl": round((price - entry_price) * quantity, 2),
                    "pnl_pct": round((price - entry_price) / entry_price * 100, 2),
                    "hold_days": i - entry_day,
                    "cash_after": round(cash, 2),
                })
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return final, trades, in_trade


def strategy_c_trailing_ema(closes, ema9, ema20, starting_cash,
                            pullback_zone_pct, min_profit_pct):
    """Buy at 9 EMA pullback, sell when price closes below 9 EMA after min profit."""
    cash = starting_cash
    trades = []
    in_trade = False
    entry_price = entry_day = quantity = 0
    max_price = 0

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        e9 = float(ema9.iloc[i])
        e20 = float(ema20.iloc[i])

        if not in_trade:
            near_ema9 = abs(price - e9) / e9 * 100 <= pullback_zone_pct
            in_ema_channel = e20 <= price <= e9 * 1.005

            if is_uptrend(ema9, ema20, i) and (near_ema9 or in_ema_channel) and cash > price:
                quantity = int(cash // price)
                entry_price = price
                entry_day = i
                max_price = price
                cash -= quantity * price
                in_trade = True
        else:
            if price > max_price:
                max_price = price

            gain_pct = (price - entry_price) / entry_price * 100

            # Sell when: gained at least min_profit AND price closes below 9 EMA
            # (trend weakening, take profit before it reverses)
            if gain_pct >= min_profit_pct and price < e9:
                cash += quantity * price
                trades.append({
                    "entry_date": str(closes.index[entry_day].date()),
                    "exit_date": str(closes.index[i].date()),
                    "entry": round(entry_price, 2),
                    "exit": round(price, 2),
                    "max_price": round(max_price, 2),
                    "qty": quantity,
                    "pnl": round((price - entry_price) * quantity, 2),
                    "pnl_pct": round(gain_pct, 2),
                    "hold_days": i - entry_day,
                    "cash_after": round(cash, 2),
                })
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return final, trades, in_trade


def print_trades(trades, label):
    if not trades:
        print(f"    No trades")
        return
    print(f"    {'#':>3} {'Entry':<12} {'Exit':<12} {'Buy':>9} {'Sell':>9} "
          f"{'P&L':>10} {'Gain%':>7} {'Days':>5} {'Cash After':>12}")
    print(f"    {'-'*95}")
    for i, t in enumerate(trades, 1):
        print(f"    {i:>3} {t['entry_date']:<12} {t['exit_date']:<12} "
              f"${t['entry']:>8.2f} ${t['exit']:>8.2f} "
              f"${t['pnl']:>+9.2f} {t['pnl_pct']:>+6.2f}% "
              f"{t['hold_days']:>5}d ${t['cash_after']:>11,.2f}")


def main():
    starting_cash = 100_000

    print("Fetching AMD 1Y data...", flush=True)
    t = yf.Ticker("AMD")
    df = t.history(period="1y")
    closes = df["Close"]
    highs = df["High"]

    first_price = float(closes.iloc[25])
    last_price = float(closes.iloc[-1])
    bah_return = (last_price - first_price) / first_price * 100

    ema9 = ema(closes, 9)
    ema20 = ema(closes, 20)
    rsi_vals = rsi(closes, 14)

    print(f"AMD: ${first_price:.2f} -> ${last_price:.2f} ({bah_return:+.1f}% buy&hold)")
    print(f"Trading days: {len(df)}\n")

    # ====== Strategy A: Fixed % targets ======
    print(f"{'='*100}")
    print(f"  STRATEGY A: EMA PULLBACK + FIXED % TARGET")
    print(f"{'='*100}")

    best_a = None
    for sp in [2, 2.5, 3, 3.5, 4, 5, 6]:
        for pz in [0.5, 1.0, 1.5, 2.0, 2.5]:
            final, trades, still_in = strategy_a_fixed_target(
                closes, ema9, ema20, rsi_vals, starting_cash, sp, pz
            )
            ret = (final - starting_cash) / starting_cash * 100
            if best_a is None or final > best_a[0]:
                best_a = (final, trades, still_in, sp, pz, ret)

    final, trades, still_in, sp, pz, ret = best_a
    print(f"  Best: sell at +{sp}%, pullback zone {pz}%")
    print(f"  Trades: {len(trades)} | "
          f"Trades/month: {len(trades)/12:.1f} | "
          f"Win rate: {sum(1 for t in trades if t['pnl']>0)/max(len(trades),1)*100:.0f}%")
    if trades:
        print(f"  Avg gain: {np.mean([t['pnl_pct'] for t in trades]):.2f}% | "
              f"Avg hold: {np.mean([t['hold_days'] for t in trades]):.1f}d")
    print(f"  Result: $100K -> ${final:,.0f} ({ret:+.1f}%)")
    print(f"\n  Trade details:")
    print_trades(trades, "A")

    # ====== Strategy B: Sell at prior swing high ======
    print(f"\n{'='*100}")
    print(f"  STRATEGY B: EMA PULLBACK + SELL AT PRIOR SWING HIGH")
    print(f"{'='*100}")

    best_b = None
    for pz in [0.5, 1.0, 1.5, 2.0, 2.5]:
        final, trades, still_in = strategy_b_swing_high(
            closes, highs, ema9, ema20, starting_cash, pz
        )
        ret = (final - starting_cash) / starting_cash * 100
        if best_b is None or final > best_b[0]:
            best_b = (final, trades, still_in, pz, ret)

    final, trades, still_in, pz, ret = best_b
    print(f"  Best: pullback zone {pz}%")
    print(f"  Trades: {len(trades)} | "
          f"Trades/month: {len(trades)/12:.1f} | "
          f"Win rate: {sum(1 for t in trades if t['pnl']>0)/max(len(trades),1)*100:.0f}%")
    if trades:
        print(f"  Avg gain: {np.mean([t['pnl_pct'] for t in trades]):.2f}% | "
              f"Avg hold: {np.mean([t['hold_days'] for t in trades]):.1f}d")
    print(f"  Result: $100K -> ${final:,.0f} ({ret:+.1f}%)")
    print(f"\n  Trade details:")
    print_trades(trades, "B")

    # ====== Strategy C: Trailing EMA exit ======
    print(f"\n{'='*100}")
    print(f"  STRATEGY C: EMA PULLBACK + TRAILING EMA EXIT (sell when closes below 9 EMA after profit)")
    print(f"{'='*100}")

    best_c = None
    for pz in [0.5, 1.0, 1.5, 2.0, 2.5]:
        for mp in [1, 2, 3, 4, 5]:
            final, trades, still_in = strategy_c_trailing_ema(
                closes, ema9, ema20, starting_cash, pz, mp
            )
            ret = (final - starting_cash) / starting_cash * 100
            if best_c is None or final > best_c[0]:
                best_c = (final, trades, still_in, pz, mp, ret)

    final, trades, still_in, pz, mp, ret = best_c
    print(f"  Best: pullback zone {pz}%, min profit {mp}% before trailing exit")
    print(f"  Trades: {len(trades)} | "
          f"Trades/month: {len(trades)/12:.1f} | "
          f"Win rate: {sum(1 for t in trades if t['pnl']>0)/max(len(trades),1)*100:.0f}%")
    if trades:
        print(f"  Avg gain: {np.mean([t['pnl_pct'] for t in trades]):.2f}% | "
              f"Avg hold: {np.mean([t['hold_days'] for t in trades]):.1f}d")
    print(f"  Result: $100K -> ${final:,.0f} ({ret:+.1f}%)")
    print(f"\n  Trade details:")
    print_trades(trades, "C")

    # ====== COMPARISON ======
    bah_shares = int(starting_cash // first_price)
    bah_final = bah_shares * last_price + (starting_cash - bah_shares * first_price)

    print(f"\n{'='*100}")
    print(f"  AMD -- FINAL COMPARISON")
    print(f"{'='*100}")
    print(f"  Buy & Hold:         $100K -> ${bah_final:>10,.0f}  ({bah_return:>+7.1f}%)")

    for label, result in [("A. Fixed Target", best_a),
                          ("B. Swing High", best_b),
                          ("C. Trailing EMA", best_c)]:
        final = result[0]
        trades = result[1]
        ret = (final - starting_cash) / starting_cash * 100
        freq = len(trades) / 12
        print(f"  {label:<21} $100K -> ${final:>10,.0f}  ({ret:>+7.1f}%)  "
              f"{len(trades)} trades ({freq:.1f}/mo)")

    print()
    all_results = [
        ("Buy & Hold", bah_final),
        ("A. Fixed Target", best_a[0]),
        ("B. Swing High", best_b[0]),
        ("C. Trailing EMA", best_c[0]),
    ]
    winner = max(all_results, key=lambda x: x[1])
    print(f"  WINNER: {winner[0]} (${winner[1]:,.0f})")
    print()


if __name__ == "__main__":
    main()
