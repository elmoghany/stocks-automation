"""Find the maximum possible return on AMD using Never Lose wave trading.

Test every possible parameter combination to find the absolute max return.
Then test hybrid strategies: wave trade + hold core position.
No leverage (haram). Use 100% of capital.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from itertools import product


def sma(closes, period=20):
    return closes.rolling(window=period).mean()


def bollinger_bands(closes, period=20, num_std=2.0):
    middle = sma(closes, period)
    std = closes.rolling(window=period).std()
    return middle, middle + num_std * std, middle - num_std * std


def rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def strategy_1_pure_wave(closes, rsi_vals, bb_lower, starting_cash,
                         min_dip, sell_gain, rsi_thresh, sell_range):
    """Strategy 1: Pure wave -- all in, all out, repeat."""
    cash = starting_cash
    in_trade = False
    entry_price = entry_day = quantity = 0
    sell_min = 0
    trades = []

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        rv = float(rsi_vals.iloc[i]) if not pd.isna(rsi_vals.iloc[i]) else 50
        lower = float(bb_lower.iloc[i]) if not pd.isna(bb_lower.iloc[i]) else price * 0.95

        if not in_trade:
            recent_high = float(closes.iloc[max(0, i-15):i].max())
            dip = (recent_high - price) / recent_high * 100
            if dip >= min_dip and (price <= lower or rv < rsi_thresh) and cash > price:
                quantity = int(cash // price)
                entry_price = price
                entry_day = i
                cash -= quantity * price
                target = price * (1 + sell_gain / 100)
                sell_min = price + (target - price) * (1 - sell_range)
                in_trade = True
        else:
            if price >= sell_min:
                cash += quantity * price
                pnl_pct = (price - entry_price) / entry_price * 100
                trades.append({"pnl_pct": pnl_pct, "days": i - entry_day})
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return final, trades


def strategy_2_rapid_scalp(closes, rsi_vals, bb_lower, starting_cash,
                           min_dip, sell_gain, rsi_thresh):
    """Strategy 2: Rapid scalp -- tiny gains, high frequency."""
    cash = starting_cash
    in_trade = False
    entry_price = entry_day = quantity = 0
    trades = []

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        rv = float(rsi_vals.iloc[i]) if not pd.isna(rsi_vals.iloc[i]) else 50
        lower = float(bb_lower.iloc[i]) if not pd.isna(bb_lower.iloc[i]) else price * 0.95

        if not in_trade:
            recent_high = float(closes.iloc[max(0, i-10):i].max())
            dip = (recent_high - price) / recent_high * 100
            if dip >= min_dip and (price <= lower or rv < rsi_thresh) and cash > price:
                quantity = int(cash // price)
                entry_price = price
                entry_day = i
                cash -= quantity * price
                in_trade = True
        else:
            pnl_pct = (price - entry_price) / entry_price * 100
            if pnl_pct >= sell_gain:
                cash += quantity * price
                trades.append({"pnl_pct": pnl_pct, "days": i - entry_day})
                in_trade = False

    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
    return final, trades


def strategy_3_hold_plus_wave(closes, rsi_vals, bb_lower, starting_cash,
                              hold_pct, min_dip, sell_gain, rsi_thresh):
    """Strategy 3: Hybrid -- hold X% as core position, wave trade the rest.

    Core position: buy and hold (captures uptrend).
    Wave portion: buy dips, sell recoveries (captures waves).
    """
    hold_cash = starting_cash * hold_pct / 100
    wave_cash = starting_cash - hold_cash

    # Core: buy and hold
    first_price = float(closes.iloc[25])
    hold_qty = int(hold_cash // first_price)
    hold_cash_remainder = hold_cash - hold_qty * first_price

    # Wave: trade the rest
    cash = wave_cash
    in_trade = False
    entry_price = entry_day = quantity = 0
    sell_min = 0
    trades = []

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        rv = float(rsi_vals.iloc[i]) if not pd.isna(rsi_vals.iloc[i]) else 50
        lower = float(bb_lower.iloc[i]) if not pd.isna(bb_lower.iloc[i]) else price * 0.95

        if not in_trade:
            recent_high = float(closes.iloc[max(0, i-15):i].max())
            dip = (recent_high - price) / recent_high * 100
            if dip >= min_dip and (price <= lower or rv < rsi_thresh) and cash > price:
                quantity = int(cash // price)
                entry_price = price
                entry_day = i
                cash -= quantity * price
                target = price * (1 + sell_gain / 100)
                sell_min = price + (target - price) * 0.80
                in_trade = True
        else:
            if price >= sell_min:
                cash += quantity * price
                pnl_pct = (price - entry_price) / entry_price * 100
                trades.append({"pnl_pct": pnl_pct, "days": i - entry_day})
                in_trade = False

    final_price = float(closes.iloc[-1])
    hold_value = hold_qty * final_price + hold_cash_remainder
    wave_value = cash + (quantity * final_price if in_trade else 0)
    total = hold_value + wave_value

    return total, trades, hold_value, wave_value


def strategy_4_dca_on_dips(closes, rsi_vals, bb_lower, starting_cash,
                           num_tranches, min_dip, sell_gain, rsi_thresh):
    """Strategy 4: DCA on dips -- split capital into tranches, buy each dip.

    Instead of all-in on one dip, deploy 1/N of capital on each successive dip.
    Sell entire position when average cost + gain% is hit.
    """
    tranche_size = starting_cash / num_tranches
    cash = starting_cash
    total_qty = 0
    total_cost = 0
    entry_prices = []
    trades = []
    last_buy_day = -10

    for i in range(25, len(closes)):
        price = float(closes.iloc[i])
        rv = float(rsi_vals.iloc[i]) if not pd.isna(rsi_vals.iloc[i]) else 50
        lower = float(bb_lower.iloc[i]) if not pd.isna(bb_lower.iloc[i]) else price * 0.95

        # Buy tranche on dip (allow buying every 3+ days)
        if cash >= tranche_size and (i - last_buy_day) >= 3:
            recent_high = float(closes.iloc[max(0, i-15):i].max())
            dip = (recent_high - price) / recent_high * 100
            if dip >= min_dip and (price <= lower or rv < rsi_thresh):
                qty = int(tranche_size // price)
                if qty > 0:
                    cash -= qty * price
                    total_qty += qty
                    total_cost += qty * price
                    entry_prices.append(price)
                    last_buy_day = i

        # Sell all when average cost + gain% is hit
        if total_qty > 0:
            avg_cost = total_cost / total_qty
            target = avg_cost * (1 + sell_gain / 100)
            sell_min = avg_cost + (target - avg_cost) * 0.80

            if price >= sell_min:
                proceeds = total_qty * price
                pnl = proceeds - total_cost
                pnl_pct = (price - avg_cost) / avg_cost * 100
                cash += proceeds
                trades.append({
                    "pnl_pct": pnl_pct,
                    "tranches": len(entry_prices),
                    "avg_cost": round(avg_cost, 2),
                })
                total_qty = 0
                total_cost = 0
                entry_prices = []

    final_price = float(closes.iloc[-1])
    final = cash + total_qty * final_price
    return final, trades


def main():
    starting_cash = 100_000

    print("Fetching AMD 1Y data...", flush=True)
    t = yf.Ticker("AMD")
    df = t.history(period="1y")
    closes = df["Close"]
    first_price = float(closes.iloc[25])
    last_price = float(closes.iloc[-1])
    bah_return = (last_price - first_price) / first_price * 100

    bb_mid, bb_upper, bb_lower = bollinger_bands(closes, 20, 2.0)
    rsi_vals = rsi(closes, 14)

    print(f"AMD: ${first_price:.2f} -> ${last_price:.2f} ({bah_return:+.1f}% buy&hold)\n")

    # ========== STRATEGY 1: Pure Wave (best params) ==========
    best1_final = 0
    best1_params = {}
    best1_trades = []

    for md, sg, rt, sr in product(
        [1, 2, 3, 4, 5],           # min_dip %
        [2, 3, 4, 5, 6, 8, 10],    # sell_gain %
        [30, 35, 38, 40, 45, 50],   # rsi threshold
        [0.15, 0.20, 0.30],         # sell range tolerance
    ):
        final, trades = strategy_1_pure_wave(
            closes, rsi_vals, bb_lower, starting_cash, md, sg, rt, sr
        )
        if final > best1_final:
            best1_final = final
            best1_params = {"min_dip": md, "sell_gain": sg, "rsi": rt, "sell_range": sr}
            best1_trades = trades

    ret1 = (best1_final - starting_cash) / starting_cash * 100
    print(f"STRATEGY 1: PURE WAVE (all-in, all-out)")
    print(f"  Best params: dip>={best1_params['min_dip']}%, sell+{best1_params['sell_gain']}%, "
          f"RSI<{best1_params['rsi']}, range={best1_params['sell_range']:.0%}")
    print(f"  Trades: {len(best1_trades)} | "
          f"Win rate: {sum(1 for t in best1_trades if t['pnl_pct']>0)/max(len(best1_trades),1)*100:.0f}%")
    if best1_trades:
        print(f"  Avg gain: {np.mean([t['pnl_pct'] for t in best1_trades]):.1f}% | "
              f"Avg hold: {np.mean([t['days'] for t in best1_trades]):.0f}d")
    print(f"  Result: $100K -> ${best1_final:,.0f} ({ret1:+.1f}%)")
    print()

    # ========== STRATEGY 2: Rapid Scalp (tiny gains, high freq) ==========
    best2_final = 0
    best2_params = {}
    best2_trades = []

    for md, sg, rt in product(
        [1, 1.5, 2, 2.5, 3],       # tiny dip
        [1, 1.5, 2, 2.5, 3],       # tiny sell gain
        [38, 40, 42, 45, 48, 50],   # loose RSI
    ):
        final, trades = strategy_2_rapid_scalp(
            closes, rsi_vals, bb_lower, starting_cash, md, sg, rt
        )
        if final > best2_final:
            best2_final = final
            best2_params = {"min_dip": md, "sell_gain": sg, "rsi": rt}
            best2_trades = trades

    ret2 = (best2_final - starting_cash) / starting_cash * 100
    print(f"STRATEGY 2: RAPID SCALP (tiny gains, high frequency)")
    print(f"  Best params: dip>={best2_params['min_dip']}%, sell+{best2_params['sell_gain']}%, "
          f"RSI<{best2_params['rsi']}")
    print(f"  Trades: {len(best2_trades)} | "
          f"Win rate: {sum(1 for t in best2_trades if t['pnl_pct']>0)/max(len(best2_trades),1)*100:.0f}%")
    if best2_trades:
        print(f"  Avg gain: {np.mean([t['pnl_pct'] for t in best2_trades]):.1f}% | "
              f"Avg hold: {np.mean([t['days'] for t in best2_trades]):.0f}d")
    print(f"  Result: $100K -> ${best2_final:,.0f} ({ret2:+.1f}%)")
    print()

    # ========== STRATEGY 3: Hold + Wave (hybrid) ==========
    best3_final = 0
    best3_params = {}
    best3_hold = 0
    best3_wave = 0
    best3_trades = []

    for hp, md, sg, rt in product(
        [30, 40, 50, 60, 70],       # hold %
        [2, 3, 4, 5],               # min dip
        [3, 4, 5, 6, 8, 10],        # sell gain
        [35, 38, 40, 45, 50],       # rsi
    ):
        final, trades, hv, wv = strategy_3_hold_plus_wave(
            closes, rsi_vals, bb_lower, starting_cash, hp, md, sg, rt
        )
        if final > best3_final:
            best3_final = final
            best3_params = {"hold_pct": hp, "min_dip": md, "sell_gain": sg, "rsi": rt}
            best3_hold = hv
            best3_wave = wv
            best3_trades = trades

    ret3 = (best3_final - starting_cash) / starting_cash * 100
    print(f"STRATEGY 3: HOLD + WAVE (hybrid)")
    print(f"  Best params: hold {best3_params['hold_pct']}% + wave {100-best3_params['hold_pct']}%, "
          f"dip>={best3_params['min_dip']}%, sell+{best3_params['sell_gain']}%, RSI<{best3_params['rsi']}")
    print(f"  Wave trades: {len(best3_trades)}")
    print(f"  Hold portion: ${best3_hold:,.0f} | Wave portion: ${best3_wave:,.0f}")
    print(f"  Result: $100K -> ${best3_final:,.0f} ({ret3:+.1f}%)")
    print()

    # ========== STRATEGY 4: DCA on Dips ==========
    best4_final = 0
    best4_params = {}
    best4_trades = []

    for nt, md, sg, rt in product(
        [3, 4, 5, 7, 10],           # num tranches
        [2, 3, 4, 5],               # min dip
        [3, 4, 5, 6, 8, 10],        # sell gain
        [35, 38, 40, 45, 50],       # rsi
    ):
        final, trades = strategy_4_dca_on_dips(
            closes, rsi_vals, bb_lower, starting_cash, nt, md, sg, rt
        )
        if final > best4_final:
            best4_final = final
            best4_params = {"tranches": nt, "min_dip": md, "sell_gain": sg, "rsi": rt}
            best4_trades = trades

    ret4 = (best4_final - starting_cash) / starting_cash * 100
    print(f"STRATEGY 4: DCA ON DIPS (buy in tranches)")
    print(f"  Best params: {best4_params['tranches']} tranches, "
          f"dip>={best4_params['min_dip']}%, sell+{best4_params['sell_gain']}%, RSI<{best4_params['rsi']}")
    print(f"  Sell rounds: {len(best4_trades)}")
    if best4_trades:
        print(f"  Avg tranches per round: {np.mean([t['tranches'] for t in best4_trades]):.1f}")
    print(f"  Result: $100K -> ${best4_final:,.0f} ({ret4:+.1f}%)")
    print()

    # ========== COMPARISON ==========
    bah_shares = int(starting_cash // first_price)
    bah_final = bah_shares * last_price + (starting_cash - bah_shares * first_price)

    print(f"{'='*80}")
    print(f"  AMD STRATEGY COMPARISON -- 1 YEAR -- $100K")
    print(f"{'='*80}")
    print(f"  Buy & Hold:        $100K -> ${bah_final:>10,.0f}  ({bah_return:>+7.1f}%)")
    print(f"  1. Pure Wave:      $100K -> ${best1_final:>10,.0f}  ({ret1:>+7.1f}%)  "
          f"{len(best1_trades)} trades")
    print(f"  2. Rapid Scalp:    $100K -> ${best2_final:>10,.0f}  ({ret2:>+7.1f}%)  "
          f"{len(best2_trades)} trades")
    print(f"  3. Hold + Wave:    $100K -> ${best3_final:>10,.0f}  ({ret3:>+7.1f}%)  "
          f"hold {best3_params['hold_pct']}% + wave {100-best3_params['hold_pct']}%")
    print(f"  4. DCA on Dips:    $100K -> ${best4_final:>10,.0f}  ({ret4:>+7.1f}%)  "
          f"{len(best4_trades)} rounds")
    print()

    winner = max(
        [("Buy & Hold", bah_final), ("Pure Wave", best1_final),
         ("Rapid Scalp", best2_final), ("Hold + Wave", best3_final),
         ("DCA on Dips", best4_final)],
        key=lambda x: x[1],
    )
    print(f"  WINNER: {winner[0]} (${winner[1]:,.0f})")
    print()


if __name__ == "__main__":
    main()
