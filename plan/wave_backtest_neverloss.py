"""Backtest the Never Lose wave strategy on all 21 PASS stocks over 1 year.

Uses the actual per-stock calibrated targets from wave_config.py:
- Buy when price dips to lower Bollinger Band or RSI < 35
- Sell within 20% range of target (sell_min to sell_target)
- Never sell at a loss -- hold until profitable
- Sector rotation: prioritize oversold sectors for buying
- Track all trades, P&L, hold times
"""

import json
import sys
import os
import numpy as np
import pandas as pd
import yfinance as yf

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.wave_config import WAVE_STOCKS, SELL_RANGE_TOLERANCE


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


def backtest_stock(symbol, df, cfg):
    """Backtest Never Lose strategy on 1 year of daily data.

    Buy: price <= lower BB OR RSI < 35, AND dip >= 50% of median_down
    Sell: price >= sell_min (80% of target gain) -- within the 20% range
    Never sell at a loss. Hold until profitable.
    """
    if df is None or len(df) < 40:
        return None

    closes = df["Close"]
    highs = df["High"]
    lows = df["Low"]

    bb_mid, bb_upper, bb_lower = bollinger_bands(closes, 20, 2.0)
    rsi_vals = rsi(closes, 14)

    med_down_pct = cfg["med_down_pct"]
    sell_pct = cfg["sell_pct"]
    min_dip_pct = med_down_pct * 0.50  # need at least 50% of median dip

    trades = []
    in_trade = False
    entry_price = 0
    entry_day = 0
    entry_date = ""
    sell_target = 0
    sell_min = 0
    quantity = 0

    # Simulate with $5000 per trade (5% of $100K)
    trade_budget = 5000

    for i in range(30, len(closes)):
        price = float(closes.iloc[i])
        date = str(closes.index[i].date())
        rsi_val = float(rsi_vals.iloc[i]) if not pd.isna(rsi_vals.iloc[i]) else 50
        lower = float(bb_lower.iloc[i]) if not pd.isna(bb_lower.iloc[i]) else price * 0.95

        if not in_trade:
            # Check buy conditions
            recent_high = float(closes.iloc[max(0, i-20):i].max())
            current_dip = (recent_high - price) / recent_high * 100

            should_buy = (
                current_dip >= min_dip_pct
                and (price <= lower or rsi_val < 35)
            )

            if should_buy:
                entry_price = price
                entry_day = i
                entry_date = date
                quantity = int(trade_budget // price)
                if quantity <= 0:
                    continue

                # Calculate sell range
                sell_target = round(price * (1 + sell_pct / 100), 2)
                gain_amount = sell_target - price
                sell_min = round(price + gain_amount * (1 - SELL_RANGE_TOLERANCE), 2)
                in_trade = True

        else:
            # Check sell conditions (Never Lose: only sell at profit)
            hold_days = i - entry_day

            if price >= sell_min:
                # Sell within range
                pnl = (price - entry_price) * quantity
                pnl_pct = (price - entry_price) / entry_price * 100
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": date,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(price, 2),
                    "sell_target": sell_target,
                    "sell_min": sell_min,
                    "quantity": quantity,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "hold_days": hold_days,
                    "rsi_at_entry": round(rsi_val, 1),
                    "hit_target": price >= sell_target,
                })
                in_trade = False

    # If still in trade at end of period, mark as open
    open_trade = None
    if in_trade:
        final_price = float(closes.iloc[-1])
        unrealized = (final_price - entry_price) / entry_price * 100
        hold_days = len(closes) - 1 - entry_day
        open_trade = {
            "entry_date": entry_date,
            "entry_price": round(entry_price, 2),
            "current_price": round(final_price, 2),
            "sell_target": sell_target,
            "sell_min": sell_min,
            "quantity": quantity,
            "unrealized_pnl": round((final_price - entry_price) * quantity, 2),
            "unrealized_pct": round(unrealized, 2),
            "hold_days": hold_days,
        }

    return {"trades": trades, "open_trade": open_trade}


def main():
    symbols = list(WAVE_STOCKS.keys())
    all_results = {}
    portfolio_start = 100_000
    total_realized = 0
    total_unrealized = 0
    total_trades = 0
    total_wins = 0
    total_invested_days = 0
    max_hold = 0

    print(f"\n{'=' * 130}")
    print(f"  NEVER LOSE WAVE STRATEGY BACKTEST -- 1 YEAR -- 21 STOCKS -- $100K PORTFOLIO")
    print(f"{'=' * 130}\n")

    for sym in symbols:
        cfg = WAVE_STOCKS[sym]
        print(f"Backtesting {sym}...", end=" ", flush=True)

        try:
            t = yf.Ticker(sym)
            df = t.history(period="1y")
            if df.empty:
                print("NO DATA")
                continue

            result = backtest_stock(sym, df, cfg)
            if result is None:
                print("INSUFFICIENT DATA")
                continue

            trades = result["trades"]
            open_trade = result["open_trade"]

            if trades:
                wins = sum(1 for t in trades if t["pnl"] > 0)
                losses = sum(1 for t in trades if t["pnl"] <= 0)
                total_pnl = sum(t["pnl"] for t in trades)
                avg_pnl_pct = np.mean([t["pnl_pct"] for t in trades])
                avg_hold = np.mean([t["hold_days"] for t in trades])
                max_hold_t = max(t["hold_days"] for t in trades)
                win_rate = wins / len(trades) * 100
                total_realized += total_pnl
                total_trades += len(trades)
                total_wins += wins
                total_invested_days += sum(t["hold_days"] for t in trades)
                max_hold = max(max_hold, max_hold_t)

                print(f"{len(trades)} trades | {wins}W/{losses}L ({win_rate:.0f}%) | "
                      f"PnL ${total_pnl:+.2f} | Avg {avg_pnl_pct:+.1f}% | "
                      f"Avg hold {avg_hold:.0f}d | Max hold {max_hold_t}d")
            else:
                print("0 trades (no buy signals)")

            if open_trade:
                total_unrealized += open_trade["unrealized_pnl"]
                print(f"  └─ OPEN: bought {open_trade['entry_date']} @ ${open_trade['entry_price']}, "
                      f"now ${open_trade['current_price']} ({open_trade['unrealized_pct']:+.1f}%), "
                      f"held {open_trade['hold_days']}d, target ${open_trade['sell_min']}-${open_trade['sell_target']}")

            all_results[sym] = result

        except Exception as e:
            print(f"ERROR: {e}")

    # Save results
    with open("plan/wave_backtest_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Summary table
    print(f"\n{'=' * 130}")
    print(f"  RESULTS BY STOCK")
    print(f"{'=' * 130}")
    print(f"  {'Stock':<6} {'Tier':<4} {'Trades':>6} {'Wins':>5} {'Win%':>6} "
          f"{'Total PnL':>10} {'Avg PnL%':>9} {'Avg Hold':>9} {'Max Hold':>9} {'Open?':>6}")
    print(f"  {'-' * 120}")

    sorted_results = sorted(
        all_results.items(),
        key=lambda x: sum(t["pnl"] for t in x[1]["trades"]) if x[1]["trades"] else 0,
        reverse=True,
    )

    for sym, result in sorted_results:
        cfg = WAVE_STOCKS[sym]
        trades = result["trades"]
        open_t = result["open_trade"]

        if trades:
            wins = sum(1 for t in trades if t["pnl"] > 0)
            total_pnl = sum(t["pnl"] for t in trades)
            avg_pnl = np.mean([t["pnl_pct"] for t in trades])
            avg_hold = np.mean([t["hold_days"] for t in trades])
            max_h = max(t["hold_days"] for t in trades)
            win_pct = wins / len(trades) * 100
        else:
            wins = 0
            total_pnl = 0
            avg_pnl = 0
            avg_hold = 0
            max_h = 0
            win_pct = 0

        open_s = "YES" if open_t else "--"

        print(f"  {sym:<6} {cfg['tier']:<4} {len(trades):>6} {wins:>5} {win_pct:>5.0f}% "
              f"${total_pnl:>+9.2f} {avg_pnl:>+8.2f}% {avg_hold:>8.1f}d {max_h:>8}d {open_s:>6}")

    # Grand totals
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    avg_hold_overall = total_invested_days / total_trades if total_trades > 0 else 0
    total_return = total_realized / portfolio_start * 100

    print(f"\n{'=' * 130}")
    print(f"  GRAND TOTALS")
    print(f"{'=' * 130}")
    print(f"  Starting capital:     ${portfolio_start:,.2f}")
    print(f"  Total trades:         {total_trades}")
    print(f"  Wins / Losses:        {total_wins}W / {total_trades - total_wins}L")
    print(f"  Win rate:             {overall_win_rate:.1f}%")
    print(f"  Realized P&L:         ${total_realized:+,.2f} ({total_return:+.2f}%)")
    print(f"  Unrealized P&L:       ${total_unrealized:+,.2f}")
    print(f"  Total P&L:            ${total_realized + total_unrealized:+,.2f}")
    print(f"  Avg hold per trade:   {avg_hold_overall:.1f} days")
    print(f"  Max hold any trade:   {max_hold} days")
    print(f"  Tax (24% short-term): ${total_realized * 0.24:,.2f}")
    print(f"  Net after tax:        ${total_realized * 0.76:+,.2f}")
    print(f"  Net return after tax: {total_realized * 0.76 / portfolio_start * 100:+.2f}%")
    print(f"  Annualized return:    {total_return:+.2f}% (pre-tax)")
    print()


if __name__ == "__main__":
    main()
