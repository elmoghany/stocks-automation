"""Test fixes to avoid getting stuck at the top. AMD case study.

The problem: after 10 winning trades (+215K), trade 11 bought at $254.84
near the all-time-high. AMD then dropped to $217 and capital is locked 5+ months.

Fixes to test:
1. EXHAUSTION STOP: After N consecutive wins, pause X days
2. OVEREXTENSION: Don't buy if price is too far above 50-day EMA
3. GAIN LOCK: After hitting Xx multiplier, stop trading
4. COOLING PERIOD: Wait X days after every sell before re-entering
5. PROFIT SKIM: After each win, move X% of profits to safe bucket
6. COMBINED: Best combination of above
"""

import numpy as np
import pandas as pd
import yfinance as yf


LOOKBACK = 5
CASH = 100_000
DIP = 2.5
SELL = 10


def ema(closes, period):
    return closes.ewm(span=period, adjust=False).mean()


def base_backtest(closes, highs):
    """Original system -- no protection."""
    cash = CASH; in_trade = False; ep = q = ed = 0; trades = []; peak = CASH
    for i in range(LOOKBACK, len(closes)):
        p = float(closes.iloc[i])
        if not in_trade:
            rh = float(highs.iloc[max(0, i-LOOKBACK):i].max())
            if (rh-p)/rh*100 >= DIP and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
        else:
            if (p-ep)/ep*100 >= SELL:
                cash += q*p; trades.append({"g": round((p-ep)/ep*100,1), "d": i-ed, "day": i})
                if cash > peak: peak = cash
                in_trade = False
    final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
    return final, trades, peak, in_trade


def fix1_exhaustion(closes, highs, max_consecutive=None, pause_days=None):
    """After N consecutive wins, pause for X days."""
    best = (0, 0, 0)
    for mc in (range(3, 12) if max_consecutive is None else [max_consecutive]):
        for pd_ in (range(5, 60, 5) if pause_days is None else [pause_days]):
            cash = CASH; in_trade = False; ep = q = ed = 0; trades = []; peak = CASH
            consec = 0; pause_until = 0
            for i in range(LOOKBACK, len(closes)):
                p = float(closes.iloc[i])
                if not in_trade:
                    if i < pause_until: continue
                    rh = float(highs.iloc[max(0, i-LOOKBACK):i].max())
                    if (rh-p)/rh*100 >= DIP and cash > p:
                        q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
                else:
                    if (p-ep)/ep*100 >= SELL:
                        cash += q*p; trades.append({"g": round((p-ep)/ep*100,1), "d": i-ed})
                        if cash > peak: peak = cash
                        in_trade = False; consec += 1
                        if consec >= mc:
                            pause_until = i + pd_; consec = 0
            final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
            if final > best[0]: best = (final, mc, pd_)
    return best


def fix2_overextension(closes, highs, max_above_ema=None):
    """Don't buy if price is too far above 50-day EMA."""
    ema50 = ema(closes, 50)
    best = (0, 0)
    for mae in (range(5, 40, 5) if max_above_ema is None else [max_above_ema]):
        cash = CASH; in_trade = False; ep = q = ed = 0; trades = []; peak = CASH
        for i in range(50, len(closes)):
            p = float(closes.iloc[i]); e50 = float(ema50.iloc[i])
            if not in_trade:
                above_ema = (p - e50) / e50 * 100
                rh = float(highs.iloc[max(0, i-LOOKBACK):i].max())
                if (rh-p)/rh*100 >= DIP and above_ema <= mae and cash > p:
                    q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
            else:
                if (p-ep)/ep*100 >= SELL:
                    cash += q*p; trades.append({"g": round((p-ep)/ep*100,1), "d": i-ed})
                    if cash > peak: peak = cash
                    in_trade = False
        final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
        if final > best[0]: best = (final, mae)
    return best


def fix3_gain_lock(closes, highs, lock_mult=None):
    """After hitting Xx multiplier, stop trading entirely."""
    best = (0, 0)
    for lm in ([2.0, 2.5, 3.0, 3.5, 4.0] if lock_mult is None else [lock_mult]):
        cash = CASH; in_trade = False; ep = q = ed = 0; trades = []; peak = CASH
        locked = False
        for i in range(LOOKBACK, len(closes)):
            if locked: break
            p = float(closes.iloc[i])
            if not in_trade:
                rh = float(highs.iloc[max(0, i-LOOKBACK):i].max())
                if (rh-p)/rh*100 >= DIP and cash > p:
                    q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
            else:
                if (p-ep)/ep*100 >= SELL:
                    cash += q*p; trades.append({"g": round((p-ep)/ep*100,1), "d": i-ed})
                    if cash > peak: peak = cash
                    in_trade = False
                    if cash >= CASH * lm:
                        locked = True
        final = cash + (q*float(closes.iloc[-1]) if in_trade and not locked else 0)
        if locked: final = cash
        if final > best[0]: best = (final, lm)
    return best


def fix4_cooling(closes, highs, cool_days=None):
    """Wait X days after every sell before re-entering."""
    best = (0, 0)
    for cd in (range(1, 30) if cool_days is None else [cool_days]):
        cash = CASH; in_trade = False; ep = q = ed = 0; trades = []; peak = CASH
        no_buy_until = 0
        for i in range(LOOKBACK, len(closes)):
            p = float(closes.iloc[i])
            if not in_trade:
                if i < no_buy_until: continue
                rh = float(highs.iloc[max(0, i-LOOKBACK):i].max())
                if (rh-p)/rh*100 >= DIP and cash > p:
                    q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
            else:
                if (p-ep)/ep*100 >= SELL:
                    cash += q*p; trades.append({"g": round((p-ep)/ep*100,1), "d": i-ed})
                    if cash > peak: peak = cash
                    in_trade = False; no_buy_until = i + cd
        final = cash + (q*float(closes.iloc[-1]) if in_trade else 0)
        if final > best[0]: best = (final, cd)
    return best


def fix5_skim(closes, highs, skim_pct=None):
    """After each win, move X% of profit to safe bucket."""
    best = (0, 0)
    for sp in ([5, 10, 15, 20, 25, 30, 40, 50] if skim_pct is None else [skim_pct]):
        cash = CASH; safe = 0; in_trade = False; ep = q = ed = 0; trades = []; peak = CASH
        for i in range(LOOKBACK, len(closes)):
            p = float(closes.iloc[i])
            if not in_trade:
                rh = float(highs.iloc[max(0, i-LOOKBACK):i].max())
                if (rh-p)/rh*100 >= DIP and cash > p:
                    q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
            else:
                if (p-ep)/ep*100 >= SELL:
                    cash += q*p
                    profit = (p-ep)*q
                    skim_amt = profit * sp / 100
                    safe += skim_amt; cash -= skim_amt
                    trades.append({"g": round((p-ep)/ep*100,1), "d": i-ed})
                    if cash+safe > peak: peak = cash+safe
                    in_trade = False
        final = cash + safe + (q*float(closes.iloc[-1]) if in_trade else 0)
        if final > best[0]: best = (final, sp)
    return best


def fix6_combined(closes, highs):
    """Best combination: overextension + cooling + skim."""
    ema50 = ema(closes, 50)
    best = (0, {})
    for mae in [10, 15, 20, 25, 30]:
        for cd in [0, 3, 5, 10, 15]:
            for sp in [0, 10, 20, 30]:
                cash = CASH; safe = 0; in_trade = False; ep = q = ed = 0
                trades = []; peak = CASH; no_buy_until = 0
                for i in range(50, len(closes)):
                    p = float(closes.iloc[i]); e50 = float(ema50.iloc[i])
                    if not in_trade:
                        if i < no_buy_until: continue
                        above = (p - e50) / e50 * 100
                        rh = float(highs.iloc[max(0, i-LOOKBACK):i].max())
                        if (rh-p)/rh*100 >= DIP and above <= mae and cash > p:
                            q = int(cash // p); ep = p; ed = i; cash -= q*p; in_trade = True
                    else:
                        if (p-ep)/ep*100 >= SELL:
                            cash += q*p
                            if sp > 0:
                                profit = (p-ep)*q; skim_amt = profit*sp/100
                                safe += skim_amt; cash -= skim_amt
                            trades.append({"g": round((p-ep)/ep*100,1), "d": i-ed})
                            if cash+safe > peak: peak = cash+safe
                            in_trade = False; no_buy_until = i + cd
                final = cash + safe + (q*float(closes.iloc[-1]) if in_trade else 0)
                if final > best[0]:
                    best = (final, {"max_above_ema": mae, "cool_days": cd,
                                    "skim_pct": sp, "trades": len(trades), "peak": peak})
    return best


def main():
    print("Fetching AMD...", flush=True)
    tk = yf.Ticker("AMD")
    df = tk.history(period="1y")
    c = df["Close"]; h = df["High"]
    fp = float(c.iloc[0]); lp = float(c.iloc[-1])
    bah = (lp-fp)/fp*100

    print(f"AMD: ${fp:.2f} -> ${lp:.2f} (B&H {bah:+.1f}%)\n")

    # Base
    base_final, base_trades, base_peak, base_open = base_backtest(c, h)
    base_ret = (base_final-CASH)/CASH*100
    peak_ret = (base_peak-CASH)/CASH*100

    print(f"  ORIGINAL (no protection):")
    print(f"    Trades: {len(base_trades)} | Peak: ${base_peak:,.0f} ({peak_ret:+.0f}%) | "
          f"Final: ${base_final:,.0f} ({base_ret:+.0f}%) | Stuck: {'YES' if base_open else 'NO'}")

    # Fix 1
    f1_final, f1_consec, f1_pause = fix1_exhaustion(c, h)
    f1_ret = (f1_final-CASH)/CASH*100
    print(f"\n  FIX 1 -- EXHAUSTION STOP (pause after {f1_consec} wins for {f1_pause}d):")
    print(f"    Final: ${f1_final:,.0f} ({f1_ret:+.0f}%)")

    # Fix 2
    f2_final, f2_mae = fix2_overextension(c, h)
    f2_ret = (f2_final-CASH)/CASH*100
    print(f"\n  FIX 2 -- OVEREXTENSION (don't buy if >{f2_mae}% above 50-EMA):")
    print(f"    Final: ${f2_final:,.0f} ({f2_ret:+.0f}%)")

    # Fix 3
    f3_final, f3_mult = fix3_gain_lock(c, h)
    f3_ret = (f3_final-CASH)/CASH*100
    print(f"\n  FIX 3 -- GAIN LOCK (stop at {f3_mult}x):")
    print(f"    Final: ${f3_final:,.0f} ({f3_ret:+.0f}%)")

    # Fix 4
    f4_final, f4_cool = fix4_cooling(c, h)
    f4_ret = (f4_final-CASH)/CASH*100
    print(f"\n  FIX 4 -- COOLING PERIOD ({f4_cool}d wait after sell):")
    print(f"    Final: ${f4_final:,.0f} ({f4_ret:+.0f}%)")

    # Fix 5
    f5_final, f5_skim = fix5_skim(c, h)
    f5_ret = (f5_final-CASH)/CASH*100
    print(f"\n  FIX 5 -- PROFIT SKIM ({f5_skim}% of profit to safe bucket):")
    print(f"    Final: ${f5_final:,.0f} ({f5_ret:+.0f}%)")

    # Fix 6
    f6_final, f6_params = fix6_combined(c, h)
    f6_ret = (f6_final-CASH)/CASH*100
    print(f"\n  FIX 6 -- COMBINED (overext <{f6_params['max_above_ema']}% + "
          f"cool {f6_params['cool_days']}d + skim {f6_params['skim_pct']}%):")
    print(f"    Trades: {f6_params['trades']} | Peak: ${f6_params['peak']:,.0f} | "
          f"Final: ${f6_final:,.0f} ({f6_ret:+.0f}%)")

    # Comparison
    print(f"\n{'='*80}")
    print(f"  AMD -- STRATEGY COMPARISON")
    print(f"{'='*80}")
    print(f"  {'Strategy':<45} {'Final':>12} {'Return':>9} {'vs Base':>9}")
    print(f"  {'-'*75}")

    results = [
        ("Buy & Hold", CASH*(1+bah/100), bah),
        ("Original (no protection)", base_final, base_ret),
        (f"Fix 1: Exhaust ({f1_consec} wins, {f1_pause}d pause)", f1_final, f1_ret),
        (f"Fix 2: Overextension (<{f2_mae}% above EMA50)", f2_final, f2_ret),
        (f"Fix 3: Gain lock ({f3_mult}x stop)", f3_final, f3_ret),
        (f"Fix 4: Cooling ({f4_cool}d after sell)", f4_final, f4_ret),
        (f"Fix 5: Skim ({f5_skim}% profit to safe)", f5_final, f5_ret),
        (f"Fix 6: Combined (best of all)", f6_final, f6_ret),
    ]

    results.sort(key=lambda x: -x[1])
    for name, final, ret in results:
        vs = ret - base_ret
        print(f"  {name:<45} ${final:>11,.0f} {ret:>+8.1f}% {vs:>+8.1f}%")

    winner = results[0]
    print(f"\n  WINNER: {winner[0]}")
    print(f"  ${CASH:,} -> ${winner[1]:,.0f} ({winner[2]:+.1f}%)")
    print()


if __name__ == "__main__":
    main()
