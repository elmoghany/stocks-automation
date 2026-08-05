"""Adaptive parameter wave trading on AMD -- parameters change based on market conditions.

Instead of fixed dip% and sell%, the system reads the current market state
and adjusts parameters dynamically. Goal: 4x ($400K from $100K) on AMD in 1 year.

Strategies tested:
1. VOLATILITY ADAPTIVE: high vol = bigger targets, low vol = tighter targets
2. MOMENTUM ADAPTIVE: strong momentum = sell later, weak momentum = sell early
3. RSI ADAPTIVE: oversold = buy more aggressively, overbought = take profits faster
4. REGIME SWITCHING: detect uptrend/choppy/downtrend, use different params for each
5. COMBINED: use all signals together
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


def atr(high, low, close, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()


def strategy_1_vol_adaptive(closes, highs, lows, starting_cash):
    """ATR-based adaptive: high volatility = wider targets, low vol = tighter."""
    atr_vals = atr(highs, lows, closes, 14)
    avg_atr = atr_vals.rolling(50).mean()

    best = None
    for dip_base in [1.5, 2, 2.5, 3]:
        for sell_base in [6, 8, 10, 12]:
            for vol_mult in [0.5, 1.0, 1.5, 2.0]:
                cash = starting_cash
                trades = []
                in_trade = False
                entry_price = quantity = entry_day = 0

                for i in range(50, len(closes)):
                    price = float(closes.iloc[i])
                    cur_atr = float(atr_vals.iloc[i])
                    mean_atr = float(avg_atr.iloc[i])
                    if pd.isna(mean_atr) or mean_atr == 0:
                        continue

                    vol_ratio = cur_atr / mean_atr
                    # High vol: widen targets. Low vol: tighten.
                    dip_pct = dip_base * (1 + (vol_ratio - 1) * vol_mult)
                    sell_pct = sell_base * (1 + (vol_ratio - 1) * vol_mult)
                    dip_pct = max(1, min(dip_pct, 15))
                    sell_pct = max(2, min(sell_pct, 25))

                    if not in_trade:
                        recent_high = float(highs.iloc[max(0, i-15):i].max())
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
                            trades.append({"g": round(gain, 1), "d": i - entry_day})
                            in_trade = False

                final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
                if best is None or final > best[0]:
                    best = (final, trades, in_trade, dip_base, sell_base, vol_mult)

    return best


def strategy_2_momentum_adaptive(closes, highs, starting_cash):
    """Momentum-based: strong trend = hold longer for bigger gains, weak = quick exit."""
    ema9 = ema(closes, 9)
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)

    best = None
    for dip_base in [1.5, 2, 2.5, 3]:
        for sell_min in [4, 5, 6]:
            for sell_max in [12, 15, 18, 20]:
                cash = starting_cash
                trades = []
                in_trade = False
                entry_price = quantity = entry_day = 0

                for i in range(50, len(closes)):
                    price = float(closes.iloc[i])
                    e9 = float(ema9.iloc[i])
                    e20 = float(ema20.iloc[i])
                    e50 = float(ema50.iloc[i])

                    # Momentum strength: how far above EMAs
                    if e50 > 0:
                        momentum = (e9 - e50) / e50 * 100
                    else:
                        momentum = 0

                    # Strong momentum = sell later, weak = sell early
                    if momentum > 10:
                        sell_pct = sell_max
                    elif momentum > 5:
                        sell_pct = (sell_min + sell_max) / 2
                    elif momentum > 0:
                        sell_pct = sell_min
                    else:
                        sell_pct = sell_min * 0.8  # weak/downtrend, take quick profits

                    if not in_trade:
                        recent_high = float(highs.iloc[max(0, i-15):i].max())
                        dip = (recent_high - price) / recent_high * 100
                        if dip >= dip_base and cash > price:
                            quantity = int(cash // price)
                            entry_price = price
                            entry_day = i
                            cash -= quantity * price
                            in_trade = True
                    else:
                        gain = (price - entry_price) / entry_price * 100
                        if gain >= sell_pct:
                            cash += quantity * price
                            trades.append({"g": round(gain, 1), "d": i - entry_day})
                            in_trade = False

                final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
                if best is None or final > best[0]:
                    best = (final, trades, in_trade, dip_base, sell_min, sell_max)

    return best


def strategy_3_rsi_adaptive(closes, highs, starting_cash):
    """RSI-based: very oversold = buy aggressively (small dip OK),
    overbought = sell quickly (small gain OK)."""
    rsi_vals = rsi(closes, 14)

    best = None
    for dip_low in [1, 1.5, 2]:        # dip when RSI very low
        for dip_high in [3, 4, 5]:       # dip when RSI normal
            for sell_low in [4, 5, 6]:    # sell target when RSI was low at entry
                for sell_high in [10, 12, 15]:  # sell target when RSI was mid at entry
                    cash = starting_cash
                    trades = []
                    in_trade = False
                    entry_price = quantity = entry_day = 0
                    entry_rsi = 50

                    for i in range(20, len(closes)):
                        price = float(closes.iloc[i])
                        rv = float(rsi_vals.iloc[i]) if not pd.isna(rsi_vals.iloc[i]) else 50

                        if not in_trade:
                            # Adaptive dip: lower RSI = accept smaller dip
                            if rv < 30:
                                dip_pct = dip_low
                            elif rv < 40:
                                dip_pct = (dip_low + dip_high) / 2
                            else:
                                dip_pct = dip_high

                            recent_high = float(highs.iloc[max(0, i-15):i].max())
                            dip = (recent_high - price) / recent_high * 100
                            if dip >= dip_pct and cash > price:
                                quantity = int(cash // price)
                                entry_price = price
                                entry_day = i
                                entry_rsi = rv
                                cash -= quantity * price
                                in_trade = True
                        else:
                            # Adaptive sell: if entered at very low RSI, hold for bigger gain
                            if entry_rsi < 30:
                                sell_pct = sell_high
                            elif entry_rsi < 40:
                                sell_pct = (sell_low + sell_high) / 2
                            else:
                                sell_pct = sell_low

                            # Also: if current RSI > 70, take whatever profit you have
                            gain = (price - entry_price) / entry_price * 100
                            if gain >= sell_pct or (rv > 70 and gain > 2):
                                cash += quantity * price
                                trades.append({"g": round(gain, 1), "d": i - entry_day})
                                in_trade = False

                    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
                    if best is None or final > best[0]:
                        best = (final, trades, in_trade, dip_low, dip_high, sell_low, sell_high)

    return best


def strategy_4_regime(closes, highs, lows, starting_cash):
    """Regime switching: detect uptrend/choppy/downtrend, use completely different params."""
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    atr_vals = atr(highs, lows, closes, 14)

    best = None
    # Uptrend params
    for up_dip in [1.5, 2, 2.5]:
        for up_sell in [8, 10, 12, 15]:
            # Choppy params
            for chop_dip in [3, 4, 5]:
                for chop_sell in [3, 4, 5, 6]:
                    cash = starting_cash
                    trades = []
                    in_trade = False
                    entry_price = quantity = entry_day = 0

                    for i in range(50, len(closes)):
                        price = float(closes.iloc[i])
                        e20 = float(ema20.iloc[i])
                        e50 = float(ema50.iloc[i])

                        # Detect regime
                        if e20 > e50 and price > e20:
                            regime = "uptrend"
                            dip_pct = up_dip
                            sell_pct = up_sell
                        elif e20 > e50:
                            regime = "pullback"
                            dip_pct = up_dip * 0.8
                            sell_pct = up_sell * 0.7
                        else:
                            regime = "choppy"
                            dip_pct = chop_dip
                            sell_pct = chop_sell

                        if not in_trade:
                            recent_high = float(highs.iloc[max(0, i-15):i].max())
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
                                trades.append({"g": round(gain, 1), "d": i - entry_day, "r": regime})
                                in_trade = False

                    final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
                    if best is None or final > best[0]:
                        best = (final, trades, in_trade, up_dip, up_sell, chop_dip, chop_sell)

    return best


def strategy_5_combined(closes, highs, lows, starting_cash):
    """Combined: volatility + momentum + RSI + regime all together."""
    ema9 = ema(closes, 9)
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    rsi_vals = rsi(closes, 14)
    atr_vals = atr(highs, lows, closes, 14)
    avg_atr = atr_vals.rolling(50).mean()

    best = None
    for base_dip in [1.5, 2, 2.5]:
        for base_sell in [6, 8, 10, 12]:
            cash = starting_cash
            trades = []
            in_trade = False
            entry_price = quantity = entry_day = 0
            entry_rsi = 50

            for i in range(50, len(closes)):
                price = float(closes.iloc[i])
                e9 = float(ema9.iloc[i])
                e20 = float(ema20.iloc[i])
                e50 = float(ema50.iloc[i])
                rv = float(rsi_vals.iloc[i]) if not pd.isna(rsi_vals.iloc[i]) else 50
                cur_atr = float(atr_vals.iloc[i])
                mean_atr = float(avg_atr.iloc[i])
                if pd.isna(mean_atr) or mean_atr == 0:
                    continue

                # Regime
                uptrend = e20 > e50 and price > e20
                strong_up = uptrend and e9 > e20

                # Volatility ratio
                vol_ratio = cur_atr / mean_atr

                # Adaptive dip
                dip_pct = base_dip
                if rv < 30:
                    dip_pct *= 0.6   # very oversold, accept tiny dip
                elif rv < 40:
                    dip_pct *= 0.8
                if vol_ratio > 1.3:
                    dip_pct *= 1.3   # high vol, need bigger dip
                elif vol_ratio < 0.7:
                    dip_pct *= 0.7   # low vol, accept smaller dip
                dip_pct = max(0.5, min(dip_pct, 10))

                # Adaptive sell
                sell_pct = base_sell
                if strong_up:
                    sell_pct *= 1.5   # strong trend, hold longer
                elif uptrend:
                    sell_pct *= 1.2
                else:
                    sell_pct *= 0.7   # no trend, take quick profit
                if vol_ratio > 1.3:
                    sell_pct *= 1.2   # high vol, bigger swings available
                sell_pct = max(2, min(sell_pct, 25))

                if not in_trade:
                    recent_high = float(highs.iloc[max(0, i-15):i].max())
                    dip = (recent_high - price) / recent_high * 100
                    if dip >= dip_pct and cash > price:
                        quantity = int(cash // price)
                        entry_price = price
                        entry_day = i
                        entry_rsi = rv
                        cash -= quantity * price
                        in_trade = True
                else:
                    gain = (price - entry_price) / entry_price * 100
                    # Overbought exit: take profit if RSI > 75 and any gain
                    if gain >= sell_pct or (rv > 75 and gain > 3):
                        cash += quantity * price
                        trades.append({"g": round(gain, 1), "d": i - entry_day})
                        in_trade = False

            final = cash + (quantity * float(closes.iloc[-1]) if in_trade else 0)
            if best is None or final > best[0]:
                best = (final, trades, in_trade, base_dip, base_sell)

    return best


def print_result(name, result, starting_cash, bah_ret):
    if result is None:
        print(f"  {name}: No result")
        return

    final = result[0]
    trades = result[1]
    still_in = result[2]
    params = result[3:]
    ret = (final - starting_cash) / starting_cash * 100

    print(f"\n  {name}")
    print(f"  Params: {params}")
    print(f"  Trades: {len(trades)} | "
          f"Win rate: {sum(1 for t in trades if t['g']>0)/max(len(trades),1)*100:.0f}%")
    if trades:
        print(f"  Avg gain: {np.mean([t['g'] for t in trades]):.1f}% | "
              f"Avg hold: {np.mean([t['d'] for t in trades]):.0f}d | "
              f"Trades/mo: {len(trades)/12:.1f}")
        # Show cash growth
        cash = starting_cash
        for t in trades:
            cash *= (1 + t['g'] / 100)
        print(f"  Compounded completed trades: ${cash:,.0f}")
    print(f"  RESULT: $100K -> ${final:,.0f} ({ret:+.1f}%) | "
          f"B&H: {bah_ret:+.1f}% | vs B&H: {ret-bah_ret:+.1f}%")
    if still_in:
        print(f"  !! Still holding open position")
    print(f"  {'>>> 4x TARGET HIT <<<' if final >= 400000 else f'Gap to 4x: {(400000-final)/1000:.0f}K short'}")


def main():
    starting_cash = 100_000

    print("Fetching AMD 1Y data...", flush=True)
    t = yf.Ticker("AMD")
    df = t.history(period="1y")
    closes = df["Close"]
    highs = df["High"]
    lows = df["Low"]

    fp = float(closes.iloc[0])
    lp = float(closes.iloc[-1])
    bah_ret = (lp - fp) / fp * 100

    print(f"AMD: ${fp:.2f} -> ${lp:.2f} ({bah_ret:+.1f}% buy&hold)\n")

    # Fixed baseline for comparison
    print("=" * 90)
    print("  FIXED PARAMS BASELINE: 2% dip, 10% sell, lookback 15")
    cash = starting_cash
    in_t = False
    ep = q = ed = 0
    base_trades = []
    for i in range(15, len(closes)):
        p = float(closes.iloc[i])
        if not in_t:
            rh = float(highs.iloc[max(0,i-15):i].max())
            if (rh-p)/rh*100 >= 2 and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q*p; in_t = True
        else:
            if (p-ep)/ep*100 >= 10:
                cash += q*p; base_trades.append({"g": round((p-ep)/ep*100,1), "d": i-ed}); in_t = False
    base_final = cash + (q*float(closes.iloc[-1]) if in_t else 0)
    base_ret = (base_final - starting_cash) / starting_cash * 100
    print(f"  Trades: {len(base_trades)} | Result: $100K -> ${base_final:,.0f} ({base_ret:+.1f}%)")

    # Test all strategies
    print("\n" + "=" * 90)
    print("  ADAPTIVE STRATEGIES -- AMD -- 1 YEAR -- $100K")
    print("=" * 90)

    print("\nTesting Strategy 1: VOLATILITY ADAPTIVE...", flush=True)
    r1 = strategy_1_vol_adaptive(closes, highs, lows, starting_cash)
    print_result("1. VOLATILITY ADAPTIVE", r1, starting_cash, bah_ret)

    print("\nTesting Strategy 2: MOMENTUM ADAPTIVE...", flush=True)
    r2 = strategy_2_momentum_adaptive(closes, highs, starting_cash)
    print_result("2. MOMENTUM ADAPTIVE", r2, starting_cash, bah_ret)

    print("\nTesting Strategy 3: RSI ADAPTIVE...", flush=True)
    r3 = strategy_3_rsi_adaptive(closes, highs, starting_cash)
    print_result("3. RSI ADAPTIVE", r3, starting_cash, bah_ret)

    print("\nTesting Strategy 4: REGIME SWITCHING...", flush=True)
    r4 = strategy_4_regime(closes, highs, lows, starting_cash)
    print_result("4. REGIME SWITCHING", r4, starting_cash, bah_ret)

    print("\nTesting Strategy 5: COMBINED...", flush=True)
    r5 = strategy_5_combined(closes, highs, lows, starting_cash)
    print_result("5. COMBINED", r5, starting_cash, bah_ret)

    # Final comparison
    print(f"\n{'='*90}")
    print(f"  FINAL COMPARISON -- AMD")
    print(f"{'='*90}")
    strategies = [
        ("Fixed 2%/10%", base_final),
        ("1. Vol Adaptive", r1[0] if r1 else 0),
        ("2. Momentum Adaptive", r2[0] if r2 else 0),
        ("3. RSI Adaptive", r3[0] if r3 else 0),
        ("4. Regime Switching", r4[0] if r4 else 0),
        ("5. Combined", r5[0] if r5 else 0),
        ("Buy & Hold", starting_cash * (1 + bah_ret/100)),
    ]
    strategies.sort(key=lambda x: -x[1])

    print(f"  {'Strategy':<25} {'Final':>12} {'Return':>10} {'vs B&H':>10} {'4x?':>8}")
    print(f"  {'-'*70}")
    for name, final in strategies:
        ret = (final - starting_cash) / starting_cash * 100
        vs = ret - bah_ret
        hit = "YES" if final >= 400000 else "no"
        print(f"  {name:<25} ${final:>11,.0f} {ret:>+9.1f}% {vs:>+9.1f}% {hit:>8}")

    print()


if __name__ == "__main__":
    main()
