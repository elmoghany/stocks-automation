"""Aggressive Never Lose backtest on AMD and NVDA.

Key difference from conservative backtest:
- Use FULL capital per trade (not 5%)
- Reinvest profits immediately
- Trade one stock at a time, rotate when capital frees
- Tighter buy signals (buy more often)
- Show compounding effect
"""

import numpy as np
import pandas as pd
import yfinance as yf


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


def backtest_aggressive(symbol, df, starting_cash, sell_range_pct=0.20):
    """Aggressive Never Lose: use all available cash per trade, reinvest profits.

    Tests multiple parameter combos to find the optimal for max return.
    """
    if df is None or len(df) < 40:
        return None

    closes = df["Close"]
    bb_mid, bb_upper, bb_lower = bollinger_bands(closes, 20, 2.0)
    rsi_vals = rsi(closes, 14)

    # Test different configurations
    best = None

    for min_dip_pct in [2, 3, 4, 5]:
        for sell_gain_pct in [3, 4, 5, 6, 7, 8, 10, 12, 15]:
            for rsi_threshold in [30, 35, 38, 40, 45]:
                result = simulate(
                    closes, bb_lower, bb_upper, bb_mid, rsi_vals,
                    starting_cash, min_dip_pct, sell_gain_pct,
                    rsi_threshold, sell_range_pct,
                )
                if result and (best is None or result["final_value"] > best["final_value"]):
                    best = result
                    best["params"] = {
                        "min_dip_pct": min_dip_pct,
                        "sell_gain_pct": sell_gain_pct,
                        "rsi_threshold": rsi_threshold,
                    }

    return best


def simulate(closes, bb_lower, bb_upper, bb_mid, rsi_vals,
             starting_cash, min_dip_pct, sell_gain_pct,
             rsi_threshold, sell_range_pct):
    """Run a single simulation with given parameters."""
    cash = starting_cash
    trades = []
    in_trade = False
    entry_price = 0
    entry_day = 0
    quantity = 0
    sell_min = 0
    sell_target = 0

    for i in range(30, len(closes)):
        price = float(closes.iloc[i])
        date = str(closes.index[i].date())
        rsi_val = float(rsi_vals.iloc[i]) if not pd.isna(rsi_vals.iloc[i]) else 50
        lower = float(bb_lower.iloc[i]) if not pd.isna(bb_lower.iloc[i]) else price * 0.95

        if not in_trade:
            # Buy conditions
            recent_high = float(closes.iloc[max(0, i-20):i].max())
            current_dip = (recent_high - price) / recent_high * 100

            should_buy = (
                current_dip >= min_dip_pct
                and (price <= lower or rsi_val < rsi_threshold)
                and cash > price  # need enough cash
            )

            if should_buy:
                quantity = int(cash // price)
                if quantity <= 0:
                    continue
                entry_price = price
                entry_day = i
                cash -= quantity * price

                sell_target = price * (1 + sell_gain_pct / 100)
                gain_amount = sell_target - price
                sell_min = price + gain_amount * (1 - sell_range_pct)
                in_trade = True

        else:
            hold_days = i - entry_day

            if price >= sell_min:
                proceeds = quantity * price
                pnl = proceeds - (quantity * entry_price)
                pnl_pct = (price - entry_price) / entry_price * 100
                cash += proceeds

                trades.append({
                    "entry_date": str(closes.index[entry_day].date()),
                    "exit_date": date,
                    "entry": round(entry_price, 2),
                    "exit": round(price, 2),
                    "qty": quantity,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "hold_days": hold_days,
                    "cash_after": round(cash, 2),
                })
                in_trade = False
                quantity = 0

    # Final value
    if in_trade:
        final_price = float(closes.iloc[-1])
        final_value = cash + quantity * final_price
        unrealized_pct = (final_price - entry_price) / entry_price * 100
    else:
        final_value = cash
        unrealized_pct = 0

    if not trades:
        return None

    total_return = (final_value - starting_cash) / starting_cash * 100
    wins = sum(1 for t in trades if t["pnl"] > 0)

    return {
        "trades": trades,
        "total_trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "win_rate": round(wins / len(trades) * 100, 1),
        "starting_cash": starting_cash,
        "final_value": round(final_value, 2),
        "total_return_pct": round(total_return, 2),
        "total_pnl": round(final_value - starting_cash, 2),
        "avg_gain_pct": round(np.mean([t["pnl_pct"] for t in trades]), 2),
        "avg_hold_days": round(np.mean([t["hold_days"] for t in trades]), 1),
        "max_hold_days": max(t["hold_days"] for t in trades),
        "still_in_trade": in_trade,
        "unrealized_pct": round(unrealized_pct, 2),
    }


def print_results(symbol, result):
    if result is None:
        print(f"\n  {symbol}: No trades generated\n")
        return

    params = result.get("params", {})
    trades = result["trades"]

    print(f"\n{'=' * 110}")
    print(f"  {symbol} -- AGGRESSIVE NEVER LOSE BACKTEST (FULL CAPITAL PER TRADE)")
    print(f"{'=' * 110}")
    print(f"  Best params: dip >= {params.get('min_dip_pct')}%, "
          f"sell at +{params.get('sell_gain_pct')}%, "
          f"RSI < {params.get('rsi_threshold')}")
    print(f"  Starting: ${result['starting_cash']:,.2f} -> "
          f"Final: ${result['final_value']:,.2f} "
          f"({result['total_return_pct']:+.1f}%)")
    print()

    print(f"  {'#':>3} {'Entry Date':<12} {'Exit Date':<12} {'Buy':>9} {'Sell':>9} "
          f"{'Qty':>5} {'P&L':>10} {'Gain%':>7} {'Days':>5} {'Cash After':>12}")
    print(f"  {'-' * 100}")

    for i, t in enumerate(trades, 1):
        print(f"  {i:>3} {t['entry_date']:<12} {t['exit_date']:<12} "
              f"${t['entry']:>8.2f} ${t['exit']:>8.2f} "
              f"{t['qty']:>5} ${t['pnl']:>+9.2f} {t['pnl_pct']:>+6.2f}% "
              f"{t['hold_days']:>5}d ${t['cash_after']:>11,.2f}")

    print(f"\n  Summary:")
    print(f"    Trades: {result['total_trades']} | "
          f"Wins: {result['wins']}W / {result['losses']}L ({result['win_rate']}%) | "
          f"Avg gain: {result['avg_gain_pct']:+.2f}% | "
          f"Avg hold: {result['avg_hold_days']:.0f}d | "
          f"Max hold: {result['max_hold_days']}d")
    print(f"    Return: ${result['starting_cash']:,.0f} -> ${result['final_value']:,.0f} "
          f"({result['total_return_pct']:+.1f}%)")
    print(f"    Tax (24%): ${result['total_pnl'] * 0.24:,.0f} | "
          f"Net after tax: ${result['total_pnl'] * 0.76:+,.0f} "
          f"({result['total_return_pct'] * 0.76:+.1f}%)")
    if result["still_in_trade"]:
        print(f"    !! Still in trade at end of period ({result['unrealized_pct']:+.1f}%)")
    print()


def main():
    starting_cash = 100_000

    for symbol in ["AMD", "NVDA"]:
        print(f"\nFetching {symbol} 1Y data...", flush=True)
        t = yf.Ticker(symbol)
        df = t.history(period="1y")

        if df.empty:
            print(f"  No data for {symbol}")
            continue

        print(f"  {len(df)} trading days, "
              f"${float(df['Close'].iloc[0]):.2f} -> ${float(df['Close'].iloc[-1]):.2f}")

        result = backtest_aggressive(symbol, df, starting_cash)
        print_results(symbol, result)

    # Also test combined: alternate between AMD and NVDA
    print(f"\n{'=' * 110}")
    print(f"  COMPARISON: BUY AND HOLD vs NEVER LOSE WAVE TRADING")
    print(f"{'=' * 110}")

    for symbol in ["AMD", "NVDA"]:
        t = yf.Ticker(symbol)
        df = t.history(period="1y")
        if df.empty:
            continue
        start_p = float(df["Close"].iloc[0])
        end_p = float(df["Close"].iloc[-1])
        bah_return = (end_p - start_p) / start_p * 100
        bah_shares = int(starting_cash // start_p)
        bah_final = bah_shares * end_p + (starting_cash - bah_shares * start_p)

        result = backtest_aggressive(symbol, df, starting_cash)
        wave_return = result["total_return_pct"] if result else 0
        wave_final = result["final_value"] if result else starting_cash

        print(f"\n  {symbol}:")
        print(f"    Buy & Hold:      ${starting_cash:,.0f} -> ${bah_final:,.0f} ({bah_return:+.1f}%)")
        print(f"    Never Lose Wave: ${starting_cash:,.0f} -> ${wave_final:,.0f} ({wave_return:+.1f}%)")
        print(f"    Wave advantage:  {wave_return - bah_return:+.1f}% "
              f"({'WAVE WINS' if wave_return > bah_return else 'BUY&HOLD WINS'})")

    print()


if __name__ == "__main__":
    main()
