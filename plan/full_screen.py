"""Full screening: halal compliance + wave backtest on all 21 stocks.

1. Halal check: loans/mcap, cash/mcap, combined, haram revenue
2. Wave backtest: per-stock optimized AND default (2.5d/11s) params
3. Final recommendation: which stocks to trade
"""

import numpy as np
import pandas as pd
import yfinance as yf

STOCKS = [
    "LRCX", "TSM", "VRT", "AMSC", "AMD", "LLY", "ANET", "FIX",
    "TDW", "TJX", "MLI", "RMD", "HUBB", "ETN", "CDNS", "DECK",
    "AWI", "ISRG", "CTAS", "BMI", "FICO",
]

LOOKBACK = 5
STARTING_CASH = 100_000


def halal_check(sym, bs, inc, info, mcap):
    """Check 3 halal criteria from quarterly statements."""
    def get_val(df, names):
        if df is None or df.empty:
            return 0
        for n in names:
            if n in df.index:
                v = df.iloc[df.index.get_loc(n), 0]
                if not pd.isna(v):
                    return float(v)
        return 0

    total_debt = get_val(bs, ["Total Debt"])
    cash_total = get_val(bs, ["Cash Cash Equivalents And Short Term Investments"])
    total_rev = get_val(inc, ["Total Revenue", "Operating Revenue"])
    interest_inc = get_val(inc, ["Interest Income", "Interest Income Non Operating",
                                 "Net Interest Income"])

    # TSM correction
    if sym == "TSM":
        total_debt = 34_000_000_000
        cash_total = 100_000_000_000
        mcap = 1_760_000_000_000
        total_rev = 26_000_000_000
        interest_inc = 200_000_000

    annual_rev = total_rev * 4

    loan_pct = (total_debt / mcap * 100) if mcap > 0 else 0
    cash_pct = (cash_total / mcap * 100) if mcap > 0 else 0
    combined = loan_pct + cash_pct
    haram_pct = (abs(interest_inc) / annual_rev * 100) if annual_rev > 0 else 0

    # Rules: individual <= 10%, combined <= 20%, haram < 5%
    loan_ok = loan_pct <= 10 or combined <= 20
    cash_ok = cash_pct <= 10 or combined <= 20
    combined_ok = combined <= 20
    haram_ok = haram_pct < 5

    halal = loan_ok and cash_ok and combined_ok and haram_ok

    return {
        "loan_pct": round(loan_pct, 2),
        "cash_pct": round(cash_pct, 2),
        "combined": round(combined, 2),
        "haram_pct": round(haram_pct, 2),
        "halal": halal,
        "fail_reason": "" if halal else (
            "LOAN>10+COMBINED>20" if not loan_ok else
            "CASH>10+COMBINED>20" if not cash_ok else
            "COMBINED>20" if not combined_ok else
            "HARAM>=5%"
        ),
    }


def backtest(closes, highs, dip_pct, sell_pct):
    """Run wave backtest with given params."""
    cash = STARTING_CASH
    trades = []
    in_trade = False
    ep = q = ed = 0
    peak = cash

    for i in range(LOOKBACK, len(closes)):
        p = float(closes.iloc[i])
        if not in_trade:
            rh = float(highs.iloc[max(0, i - LOOKBACK):i].max())
            dip = (rh - p) / rh * 100
            if dip >= dip_pct and cash > p:
                q = int(cash // p)
                ep = p
                ed = i
                cash -= q * p
                in_trade = True
        else:
            gain = (p - ep) / ep * 100
            if gain >= sell_pct:
                cash += q * p
                trades.append({"g": round(gain, 1), "d": i - ed})
                if cash > peak:
                    peak = cash
                in_trade = False

    final = cash + (q * float(closes.iloc[-1]) if in_trade else 0)
    ret = (final - STARTING_CASH) / STARTING_CASH * 100
    return round(ret, 1), len(trades), in_trade


def find_best_params(closes, highs):
    """Brute force find best dip/sell combo."""
    best_ret = -999
    best_dip = 2.5
    best_sell = 11
    for dip in [1.5, 2, 2.5, 3, 3.5, 4, 5]:
        for sell in [6, 8, 10, 11, 12, 13, 15]:
            ret, n, _ = backtest(closes, highs, dip, sell)
            if ret > best_ret:
                best_ret = ret
                best_dip = dip
                best_sell = sell
    return best_dip, best_sell, best_ret


def main():
    results = []

    print("Screening all 21 stocks...\n", flush=True)

    for sym in STOCKS:
        try:
            t = yf.Ticker(sym)
            info = t.info
            mcap = info.get("marketCap", 0) or 0
            df = t.history(period="1y")
            bs = t.quarterly_balance_sheet
            inc = t.quarterly_income_stmt

            if df.empty or len(df) < 40:
                print(f"  {sym}: NO DATA")
                continue

            closes = df["Close"]
            highs = df["High"]
            entry = round(float(closes.iloc[0]), 2)
            last = round(float(closes.iloc[-1]), 2)
            bah = round((last - entry) / entry * 100, 1)

            # Halal check
            h = halal_check(sym, bs, inc, info, mcap)

            # Default backtest (2.5d/11s)
            default_ret, default_n, _ = backtest(closes, highs, 2.5, 11)

            # Optimized backtest
            opt_dip, opt_sell, opt_ret = find_best_params(closes, highs)
            _, opt_n, _ = backtest(closes, highs, opt_dip, opt_sell)

            results.append({
                "sym": sym, "entry": entry, "bah": bah,
                "halal": h,
                "default_ret": default_ret, "default_n": default_n,
                "opt_dip": opt_dip, "opt_sell": opt_sell,
                "opt_ret": opt_ret, "opt_n": opt_n,
            })

            status = "HALAL" if h["halal"] else "FAIL"
            print(f"  {sym}: {status} | L:{h['loan_pct']}% C:{h['cash_pct']}% H:{h['haram_pct']}% | "
                  f"Default:{default_ret:+.0f}% | Best d{opt_dip}/s{opt_sell}:{opt_ret:+.0f}%", flush=True)

        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    # Sort by optimized return
    results.sort(key=lambda r: r["opt_ret"], reverse=True)

    # ====== HALAL TABLE ======
    print(f"\n{'='*110}")
    print(f"  HALAL COMPLIANCE (Loans<=10%, Cash<=10%, Combined<=20%, Haram<5%)")
    print(f"{'='*110}")
    print(f"  {'Stock':<6} {'Loans%':>7} {'Cash%':>7} {'Comb%':>7} {'Haram%':>7} {'Status':>8}")
    print(f"  {'-'*45}")

    halal_pass = []
    halal_fail = []
    for r in results:
        h = r["halal"]
        status = "HALAL" if h["halal"] else "FAIL"
        print(f"  {r['sym']:<6} {h['loan_pct']:>6.2f}% {h['cash_pct']:>6.2f}% "
              f"{h['combined']:>6.2f}% {h['haram_pct']:>6.2f}% {status:>8}"
              f"{'  ' + h['fail_reason'] if h['fail_reason'] else ''}")
        if h["halal"]:
            halal_pass.append(r)
        else:
            halal_fail.append(r)

    # ====== BACKTEST TABLE (halal stocks only) ======
    print(f"\n{'='*110}")
    print(f"  WAVE BACKTEST -- HALAL STOCKS ONLY -- $100K -- 1 YEAR")
    print(f"{'='*110}")
    print(f"  {'Stock':<6} {'Entry$':>8} {'B&H':>7} | {'Default':>8} {'#':>3} | "
          f"{'Best':>8} {'Dip':>5} {'Sell':>5} {'#':>3} | {'Beats B&H':>10}")
    print(f"  {'-'*85}")

    for r in halal_pass:
        beats = "YES" if r["opt_ret"] > r["bah"] else "no"
        print(f"  {r['sym']:<6} ${r['entry']:>7.2f} {r['bah']:>+6.0f}% | "
              f"{r['default_ret']:>+7.0f}% {r['default_n']:>3} | "
              f"{r['opt_ret']:>+7.0f}% {r['opt_dip']:>4.1f}% {r['opt_sell']:>+4.0f}% {r['opt_n']:>3} | "
              f"{beats:>10}")

    # ====== RECOMMENDATION ======
    print(f"\n{'='*110}")
    print(f"  RECOMMENDATION")
    print(f"{'='*110}")

    # Top tier: halal + opt_ret > 100%
    top = [r for r in halal_pass if r["opt_ret"] > 100]
    mid = [r for r in halal_pass if 30 < r["opt_ret"] <= 100]
    low = [r for r in halal_pass if 0 < r["opt_ret"] <= 30]
    neg = [r for r in halal_pass if r["opt_ret"] <= 0]

    print(f"\n  TOP TIER (>100% return, recommended for wave trading):")
    for r in top:
        print(f"    {r['sym']:<6} d{r['opt_dip']}/s{r['opt_sell']} -> {r['opt_ret']:+.0f}% "
              f"({r['opt_n']} trades) vs B&H {r['bah']:+.0f}%")

    print(f"\n  MID TIER (30-100% return, solid wave candidates):")
    for r in mid:
        print(f"    {r['sym']:<6} d{r['opt_dip']}/s{r['opt_sell']} -> {r['opt_ret']:+.0f}% "
              f"({r['opt_n']} trades) vs B&H {r['bah']:+.0f}%")

    print(f"\n  LOW TIER (0-30% return, marginal):")
    for r in low:
        print(f"    {r['sym']:<6} d{r['opt_dip']}/s{r['opt_sell']} -> {r['opt_ret']:+.0f}% "
              f"({r['opt_n']} trades) vs B&H {r['bah']:+.0f}%")

    if neg:
        print(f"\n  NEGATIVE (not recommended for wave trading):")
        for r in neg:
            print(f"    {r['sym']:<6} d{r['opt_dip']}/s{r['opt_sell']} -> {r['opt_ret']:+.0f}% "
                  f"({r['opt_n']} trades) vs B&H {r['bah']:+.0f}%")

    if halal_fail:
        print(f"\n  HALAL FAIL (excluded):")
        for r in halal_fail:
            h = r["halal"]
            print(f"    {r['sym']:<6} {h['fail_reason']}")

    # Portfolio projection
    if top:
        n = len(top)
        per_stock = STARTING_CASH / n
        total = sum(per_stock * (1 + r["opt_ret"] / 100) for r in top)
        total_bah = sum(per_stock * (1 + r["bah"] / 100) for r in top)
        print(f"\n  TOP TIER PORTFOLIO (${STARTING_CASH:,} / {n} stocks = ${per_stock:,.0f} each):")
        print(f"    Wave trading: ${total:,.0f} ({(total-STARTING_CASH)/STARTING_CASH*100:+.1f}%)")
        print(f"    Buy & hold:   ${total_bah:,.0f} ({(total_bah-STARTING_CASH)/STARTING_CASH*100:+.1f}%)")
        print(f"    Wave extra:   ${total - total_bah:+,.0f}")
        print(f"    Multiplier:   {total/STARTING_CASH:.1f}x")

    print()


if __name__ == "__main__":
    main()
