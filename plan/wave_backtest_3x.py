"""Find ways to get 3x (300%) return on AMD in 1 year. No leverage. Never lose.

Strategies to test:
1. PYRAMID: Add to winning positions as price rises. Each pullback = add more shares.
   Compound effect: instead of buying once at $100, buy at $100, add at $110, add at $120.
   Sell all at $130. More shares working for you at each level.

2. RAPID COMPOUND: Take small gains (2-3%) very frequently. Reinvest 100% immediately.
   $100K at 2.5% compounded 40 times = $100K * 1.025^40 = $268K.
   Need 40 trades in a year = 3.3/month.

3. MOMENTUM SURFING: Stay in during strong moves, only exit on confirmed reversal.
   Re-enter immediately on next pullback. Maximize time in market.

4. MULTI-ENTRY DCA + FULL EXIT: Buy in 3-5 tranches as price dips.
   When average cost + target% is hit, sell ALL tranches at once for bigger absolute gain.

5. COMBINED: Pyramid during uptrends + rapid compound during chop + momentum surf during breakouts.
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


def strategy_pyramid(closes, ema9, ema20, starting_cash):
    """PYRAMID: Add to winners on each pullback in an uptrend.

    - Buy initial position when price pulls back to 9 EMA
    - Add 50% more on next pullback to 9 EMA (if still profitable)
    - Add 30% more on next pullback
    - Sell ALL when price closes below 20 EMA (trend weakening)
    - Never sell at a loss -- hold until above avg cost
    """
    best = None
    for add1_pct in [30, 40, 50, 60]:
        for add2_pct in [20, 30, 40]:
            for exit_ema in [20]:  # exit when below 20 EMA
                for pullback_pct in [0.5, 1.0, 1.5, 2.0]:
                    for min_profit_exit in [2, 3, 5]:
                        result = _run_pyramid(
                            closes, ema9, ema20, starting_cash,
                            add1_pct, add2_pct, pullback_pct, min_profit_exit
                        )
                        if best is None or result["final"] > best["final"]:
                            best = result
                            best["params"] = {
                                "add1": add1_pct, "add2": add2_pct,
                                "pullback": pullback_pct, "min_profit_exit": min_profit_exit
                            }
    return best


def _run_pyramid(closes, ema9, ema20, starting_cash, add1_pct, add2_pct,
                 pullback_pct, min_profit_exit):
    cash = starting_cash
    total_qty = 0
    total_cost = 0
    adds = 0
    trades = []
    rounds_completed = 0

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        e9 = float(ema9.iloc[i])
        e20 = float(ema20.iloc[i])
        uptrend = e9 > e20 and e9 > float(ema9.iloc[i-5])

        if total_qty == 0:
            # Initial entry: pullback to 9 EMA in uptrend
            if uptrend and abs(price - e9) / e9 * 100 <= pullback_pct and cash > price:
                qty = int(cash * 0.50 // price)  # use 50% for initial
                if qty > 0:
                    cash -= qty * price
                    total_qty += qty
                    total_cost += qty * price
                    adds = 0

        elif adds < 2:
            # Add on pullback (if still profitable)
            avg_cost = total_cost / total_qty
            if uptrend and price > avg_cost and abs(price - e9) / e9 * 100 <= pullback_pct:
                pct = add1_pct if adds == 0 else add2_pct
                invest = cash * pct / 100
                qty = int(invest // price)
                if qty > 0:
                    cash -= qty * price
                    total_qty += qty
                    total_cost += qty * price
                    adds += 1

        if total_qty > 0:
            avg_cost = total_cost / total_qty
            gain_pct = (price - avg_cost) / avg_cost * 100

            # Exit: price below 20 EMA AND we have min profit
            if price < e20 and gain_pct >= min_profit_exit:
                cash += total_qty * price
                trades.append({
                    "pnl": round((price - avg_cost) * total_qty, 2),
                    "pnl_pct": round(gain_pct, 2),
                    "adds": adds,
                    "qty": total_qty,
                })
                total_qty = 0
                total_cost = 0
                adds = 0
                rounds_completed += 1

    final = cash + total_qty * float(closes.iloc[-1])
    return {
        "final": final,
        "trades": trades,
        "rounds": rounds_completed,
        "still_in": total_qty > 0,
    }


def strategy_rapid_compound(closes, ema9, ema20, starting_cash):
    """RAPID COMPOUND: Small gains, very frequent, 100% reinvest."""
    best = None
    for sell_pct in [1.5, 2, 2.5, 3, 3.5, 4]:
        for pullback_pct in [0.3, 0.5, 1.0, 1.5, 2.0]:
            for rsi_thresh in [40, 45, 50, 55]:
                result = _run_rapid(
                    closes, ema9, ema20, rsi(closes), starting_cash,
                    sell_pct, pullback_pct, rsi_thresh
                )
                if best is None or result["final"] > best["final"]:
                    best = result
                    best["params"] = {
                        "sell_pct": sell_pct, "pullback": pullback_pct,
                        "rsi": rsi_thresh,
                    }
    return best


def _run_rapid(closes, ema9, ema20, rsi_vals, starting_cash,
               sell_pct, pullback_pct, rsi_thresh):
    cash = starting_cash
    trades = []
    in_trade = False
    entry_price = quantity = 0

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        e9 = float(ema9.iloc[i])
        e20 = float(ema20.iloc[i])
        rv = float(rsi_vals.iloc[i]) if not pd.isna(rsi_vals.iloc[i]) else 50

        if not in_trade:
            near_ema = abs(price - e9) / e9 * 100 <= pullback_pct
            in_zone = e20 <= price <= e9 * 1.01
            uptrend = e9 > e20

            if uptrend and (near_ema or in_zone) and rv < rsi_thresh and cash > price:
                quantity = int(cash // price)
                entry_price = price
                cash -= quantity * price
                in_trade = True
        else:
            gain = (price - entry_price) / entry_price * 100
            if gain >= sell_pct:
                cash += quantity * price
                trades.append({"pnl_pct": round(gain, 2), "days": 0})
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return {"final": final, "trades": trades, "still_in": in_trade}


def strategy_momentum_surf(closes, ema9, ema20, starting_cash):
    """MOMENTUM SURF: Stay in during runs, exit only on confirmed reversal.
    Re-enter immediately on next pullback. Maximize time in market.
    """
    best = None
    for entry_pct in [0.5, 1.0, 1.5, 2.0]:
        for exit_days_below in [1, 2, 3]:  # exit after N days below 9 EMA
            for min_profit in [1, 2, 3]:
                result = _run_surf(
                    closes, ema9, ema20, starting_cash,
                    entry_pct, exit_days_below, min_profit
                )
                if best is None or result["final"] > best["final"]:
                    best = result
                    best["params"] = {
                        "entry_pct": entry_pct,
                        "exit_days_below": exit_days_below,
                        "min_profit": min_profit,
                    }
    return best


def _run_surf(closes, ema9, ema20, starting_cash, entry_pct, exit_days_below, min_profit):
    cash = starting_cash
    trades = []
    in_trade = False
    entry_price = quantity = 0
    days_below_ema9 = 0

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        e9 = float(ema9.iloc[i])
        e20 = float(ema20.iloc[i])
        uptrend = e9 > e20

        if not in_trade:
            near_ema = abs(price - e9) / e9 * 100 <= entry_pct
            if uptrend and near_ema and cash > price:
                quantity = int(cash // price)
                entry_price = price
                cash -= quantity * price
                in_trade = True
                days_below_ema9 = 0
        else:
            if price < e9:
                days_below_ema9 += 1
            else:
                days_below_ema9 = 0

            gain_pct = (price - entry_price) / entry_price * 100

            # Exit: been below 9 EMA for N days AND have min profit
            if days_below_ema9 >= exit_days_below and gain_pct >= min_profit:
                cash += quantity * price
                trades.append({"pnl_pct": round(gain_pct, 2), "days": 0})
                in_trade = False
                days_below_ema9 = 0

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return {"final": final, "trades": trades, "still_in": in_trade}


def strategy_multi_entry(closes, ema9, ema20, starting_cash):
    """MULTI-ENTRY: Buy in tranches on successive dips. Sell all at target."""
    best = None
    for tranches in [3, 4, 5]:
        for dip_spacing in [1, 1.5, 2, 2.5]:  # % between each buy
            for sell_gain in [3, 4, 5, 6, 8]:
                result = _run_multi(
                    closes, ema9, ema20, starting_cash,
                    tranches, dip_spacing, sell_gain
                )
                if best is None or result["final"] > best["final"]:
                    best = result
                    best["params"] = {
                        "tranches": tranches, "dip_spacing": dip_spacing,
                        "sell_gain": sell_gain,
                    }
    return best


def _run_multi(closes, ema9, ema20, starting_cash, max_tranches, dip_spacing, sell_gain):
    cash = starting_cash
    tranche_size = starting_cash / max_tranches
    trades = []
    total_qty = 0
    total_cost = 0
    last_buy_price = 999999
    buys = 0

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        e9 = float(ema9.iloc[i])
        e20 = float(ema20.iloc[i])
        uptrend = e9 > e20

        # Buy tranche if price dropped enough from last buy
        if uptrend and buys < max_tranches and cash >= tranche_size:
            drop_from_last = (last_buy_price - price) / last_buy_price * 100
            if buys == 0 or drop_from_last >= dip_spacing:
                qty = int(tranche_size // price)
                if qty > 0:
                    cash -= qty * price
                    total_qty += qty
                    total_cost += qty * price
                    last_buy_price = price
                    buys += 1

        # Sell all when avg cost + gain
        if total_qty > 0:
            avg_cost = total_cost / total_qty
            gain_pct = (price - avg_cost) / avg_cost * 100
            if gain_pct >= sell_gain:
                cash += total_qty * price
                trades.append({"pnl_pct": round(gain_pct, 2), "tranches": buys})
                total_qty = 0
                total_cost = 0
                buys = 0
                last_buy_price = 999999

    final = cash + total_qty * float(closes.iloc[-1])
    return {"final": final, "trades": trades, "still_in": total_qty > 0}


def main():
    starting_cash = 100_000

    print("Fetching AMD 1Y data...", flush=True)
    t = yf.Ticker("AMD")
    df = t.history(period="1y")
    closes = df["Close"]
    first_price = float(closes.iloc[25])
    last_price = float(closes.iloc[-1])
    bah_return = (last_price - first_price) / first_price * 100

    ema9 = ema(closes, 9)
    ema20 = ema(closes, 20)

    print(f"AMD: ${first_price:.2f} -> ${last_price:.2f} ({bah_return:+.1f}% buy&hold)\n")

    bah_shares = int(starting_cash // first_price)
    bah_final = bah_shares * last_price + (starting_cash - bah_shares * first_price)

    strategies = {}

    # Strategy 1: Pyramid
    print("Testing PYRAMID...", flush=True)
    r1 = strategy_pyramid(closes, ema9, ema20, starting_cash)
    ret1 = (r1["final"] - starting_cash) / starting_cash * 100
    strategies["1. PYRAMID"] = r1
    print(f"  {len(r1['trades'])} rounds, ${r1['final']:,.0f} ({ret1:+.1f}%)")
    print(f"  Params: {r1['params']}")
    if r1["trades"]:
        for i, t in enumerate(r1["trades"], 1):
            print(f"    Round {i}: +{t['pnl_pct']:.1f}% (${t['pnl']:+,.0f}), {t['adds']} adds, {t['qty']} shares")

    # Strategy 2: Rapid Compound
    print("\nTesting RAPID COMPOUND...", flush=True)
    r2 = strategy_rapid_compound(closes, ema9, ema20, starting_cash)
    ret2 = (r2["final"] - starting_cash) / starting_cash * 100
    strategies["2. RAPID COMPOUND"] = r2
    print(f"  {len(r2['trades'])} trades, ${r2['final']:,.0f} ({ret2:+.1f}%)")
    print(f"  Params: {r2['params']}")
    if r2["trades"]:
        print(f"  Avg gain: {np.mean([t['pnl_pct'] for t in r2['trades']]):.2f}%")
        print(f"  Trades/month: {len(r2['trades'])/12:.1f}")

    # Strategy 3: Momentum Surf
    print("\nTesting MOMENTUM SURF...", flush=True)
    r3 = strategy_momentum_surf(closes, ema9, ema20, starting_cash)
    ret3 = (r3["final"] - starting_cash) / starting_cash * 100
    strategies["3. MOMENTUM SURF"] = r3
    print(f"  {len(r3['trades'])} trades, ${r3['final']:,.0f} ({ret3:+.1f}%)")
    print(f"  Params: {r3['params']}")
    if r3["trades"]:
        print(f"  Avg gain: {np.mean([t['pnl_pct'] for t in r3['trades']]):.2f}%")

    # Strategy 4: Multi-Entry
    print("\nTesting MULTI-ENTRY DCA...", flush=True)
    r4 = strategy_multi_entry(closes, ema9, ema20, starting_cash)
    ret4 = (r4["final"] - starting_cash) / starting_cash * 100
    strategies["4. MULTI-ENTRY"] = r4
    print(f"  {len(r4['trades'])} rounds, ${r4['final']:,.0f} ({ret4:+.1f}%)")
    print(f"  Params: {r4['params']}")

    # ====== FINAL COMPARISON ======
    print(f"\n{'='*90}")
    print(f"  AMD -- STRATEGY COMPARISON -- 1 YEAR -- $100K -- NO LEVERAGE")
    print(f"{'='*90}")
    print(f"  {'Strategy':<25} {'Final':>12} {'Return':>10} {'Trades':>8} {'vs B&H':>10}")
    print(f"  {'-'*75}")
    print(f"  {'Buy & Hold':<25} ${bah_final:>11,.0f} {bah_return:>+9.1f}% {'0':>8} {'--':>10}")

    for name, r in sorted(strategies.items(), key=lambda x: -x[1]["final"]):
        final = r["final"]
        ret = (final - starting_cash) / starting_cash * 100
        n = len(r["trades"])
        vs = ret - bah_return
        marker = " <-- BEATS B&H" if vs > 0 else ""
        print(f"  {name:<25} ${final:>11,.0f} {ret:>+9.1f}% {n:>8} {vs:>+9.1f}%{marker}")

    # Target check
    print(f"\n  TARGET: 3x return = +200% = $300,000")
    best_name, best_r = max(strategies.items(), key=lambda x: x[1]["final"])
    best_ret = (best_r["final"] - starting_cash) / starting_cash * 100
    print(f"  BEST:   {best_name} at +{best_ret:.1f}%")
    gap = 200 - best_ret
    if gap > 0:
        print(f"  GAP:    {gap:.1f}% short of 3x target")
        # What compound rate would be needed?
        if best_r["trades"]:
            n_trades = len(best_r["trades"])
            needed_per_trade = (3.0 ** (1/n_trades) - 1) * 100
            print(f"  MATH:   To hit 3x in {n_trades} trades, need {needed_per_trade:.1f}% per trade compounded")
            for n in [20, 30, 40, 50, 60]:
                rate = (3.0 ** (1/n) - 1) * 100
                print(f"          {n} trades x {rate:.2f}% each = 3x ($300K)")
    else:
        print(f"  3x TARGET ACHIEVED!")

    print()


if __name__ == "__main__":
    main()
