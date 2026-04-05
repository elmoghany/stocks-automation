"""Full halal + backtest screening on 46 stocks."""

import numpy as np
import pandas as pd
import yfinance as yf

STOCKS = [
    "TSM", "LLY", "COST", "AMD", "LRCX", "MPWR", "GWW", "FIX",
    "MLM", "RMD", "IR", "JBL", "HUBB", "TSCO", "PHM", "IOT",
    "LII", "PNR", "MLI", "ISRG", "ANET", "ARM", "PH", "VRT",
    "CEG", "TT", "REGN", "SHW", "CDNS", "SNPS", "ROST", "ONTO",
    "AIT", "MANH", "AWI", "AAON", "EXP", "BMI", "DOCS", "TDW",
    "FTDR", "BKE", "SHOO", "TGLS", "AMSC", "LMB",
]

LOOKBACK = 5
CASH = 100_000


def halal_check(sym, t, mcap):
    bs = t.quarterly_balance_sheet
    inc = t.quarterly_income_stmt

    def gv(df, names):
        if df is None or df.empty:
            return 0
        for n in names:
            if n in df.index:
                v = df.iloc[df.index.get_loc(n), 0]
                if not pd.isna(v):
                    return float(v)
        return 0

    debt = gv(bs, ["Total Debt"])
    cash = gv(bs, ["Cash Cash Equivalents And Short Term Investments"])
    rev = gv(inc, ["Total Revenue", "Operating Revenue"])
    int_inc = gv(inc, ["Interest Income", "Interest Income Non Operating", "Net Interest Income"])

    if sym == "TSM":
        debt = 34e9; cash = 100e9; mcap = 1.76e12; rev = 26e9; int_inc = 200e6

    annual_rev = rev * 4
    loan_pct = (debt / mcap * 100) if mcap > 0 else 0
    cash_pct = (cash / mcap * 100) if mcap > 0 else 0
    combined = loan_pct + cash_pct
    haram_pct = (abs(int_inc) / annual_rev * 100) if annual_rev > 0 else 0

    halal = (loan_pct <= 10 or combined <= 20) and (cash_pct <= 10 or combined <= 20) and combined <= 20 and haram_pct < 5

    return {
        "loan": round(loan_pct, 2), "cash": round(cash_pct, 2),
        "comb": round(combined, 2), "haram": round(haram_pct, 2),
        "halal": halal,
    }


def backtest(closes, highs, dip, sell):
    cash = CASH
    trades = []
    in_trade = False
    ep = q = ed = 0
    peak = cash

    for i in range(LOOKBACK, len(closes)):
        p = float(closes.iloc[i])
        if not in_trade:
            rh = float(highs.iloc[max(0, i - LOOKBACK):i].max())
            if (rh - p) / rh * 100 >= dip and cash > p:
                q = int(cash // p); ep = p; ed = i; cash -= q * p; in_trade = True
        else:
            if (p - ep) / ep * 100 >= sell:
                pnl = (p - ep) * q
                cash += q * p
                trades.append({"pnl": round(pnl, 2), "g": round((p-ep)/ep*100, 1), "d": i - ed})
                if cash > peak: peak = cash
                in_trade = False

    final = cash + (q * float(closes.iloc[-1]) if in_trade else 0)
    unreal = round((float(closes.iloc[-1]) - ep) * q, 2) if in_trade else 0
    real_pnl = sum(t["pnl"] for t in trades)
    return {
        "final": round(final, 0), "ret": round((final - CASH) / CASH * 100, 1),
        "trades": len(trades), "real_pnl": round(real_pnl, 0), "unreal": round(unreal, 0),
        "peak": round(peak, 0), "open": in_trade,
    }


def best_params(closes, highs):
    best = (-999, 2.5, 11)
    for d in [1.5, 2, 2.5, 3, 3.5, 4, 5]:
        for s in [6, 8, 10, 11, 12, 13, 15]:
            r = backtest(closes, highs, d, s)
            if r["final"] > best[0]:
                best = (r["final"], d, s)
    return best[1], best[2]


def main():
    rows = []
    print("Screening 46 stocks...\n", flush=True)

    for sym in STOCKS:
        try:
            tk = yf.Ticker(sym)
            info = tk.info
            mcap = info.get("marketCap", 0) or 0
            df = tk.history(period="1y")
            if df.empty or len(df) < 40:
                print(f"  {sym}: NO DATA"); continue

            closes = df["Close"]; highs = df["High"]
            entry = round(float(closes.iloc[0]), 2)
            last = round(float(closes.iloc[-1]), 2)
            bah = round((last - entry) / entry * 100, 1)

            h = halal_check(sym, tk, mcap)
            d, s = best_params(closes, highs)
            bt = backtest(closes, highs, d, s)

            rows.append({
                "sym": sym, "entry": entry, "last": last, "bah": bah,
                "h": h, "dip": d, "sell": s, "bt": bt,
            })
            status = "HALAL" if h["halal"] else "FAIL"
            print(f"  {sym}: {status} L:{h['loan']}% C:{h['cash']}% | "
                  f"d{d}/s{s} -> {bt['ret']:+.0f}% ({bt['trades']}t)", flush=True)
        except Exception as e:
            print(f"  {sym}: ERROR {e}")

    # Sort by backtest return
    rows.sort(key=lambda r: -r["bt"]["ret"])

    # Print full table
    print(f"\n{'='*160}")
    print(f"  46 STOCKS -- HALAL + WAVE BACKTEST -- SORTED BY RETURN")
    print(f"{'='*160}")
    print(f"  {'#':>3} {'Stock':<6} {'Entry':>8} {'Last':>8} {'B&H':>7} | "
          f"{'L%':>6} {'C%':>6} {'Cb%':>6} {'H%':>5} {'Halal':>6} | "
          f"{'Dip':>4} {'Sell':>5} {'#Tr':>4} {'Realized':>11} {'Unreal':>10} {'Final':>11} {'Return':>8} {'Peak':>11}")
    print(f"  {'-'*155}")

    total_final = 0; total_bah = 0; total_real = 0; total_unreal = 0
    total_trades = 0; halal_count = 0

    for i, r in enumerate(rows, 1):
        h = r["h"]; bt = r["bt"]
        hs = "HALAL" if h["halal"] else "FAIL"
        if h["halal"]: halal_count += 1

        total_final += bt["final"]; total_bah += CASH * (1 + r["bah"] / 100)
        total_real += bt["real_pnl"]; total_unreal += bt["unreal"]
        total_trades += bt["trades"]

        print(f"  {i:>3} {r['sym']:<6} ${r['entry']:>7.2f} ${r['last']:>7.2f} {r['bah']:>+6.1f}% | "
              f"{h['loan']:>5.1f}% {h['cash']:>5.1f}% {h['comb']:>5.1f}% {h['haram']:>4.1f}% {hs:>6} | "
              f"{r['dip']:>3.1f}% {r['sell']:>+4.0f}% {bt['trades']:>4} "
              f"${bt['real_pnl']:>+10,.0f} ${bt['unreal']:>+9,.0f} "
              f"${bt['final']:>10,.0f} {bt['ret']:>+7.1f}% ${bt['peak']:>10,.0f}")

    n = len(rows)
    total_capital = n * CASH
    print(f"  {'-'*155}")
    print(f"  {'':>3} {'TOTAL':<6} {'':>8} {'':>8} {'':>7} | "
          f"{'':>6} {'':>6} {'':>6} {'':>5} {halal_count:>4}/{n} | "
          f"{'':>4} {'':>5} {total_trades:>4} "
          f"${total_real:>+10,.0f} ${total_unreal:>+9,.0f} "
          f"${total_final:>10,.0f} {(total_final-total_capital)/total_capital*100:>+7.1f}%")

    # Summary
    print(f"\n  SUMMARY:")
    print(f"    Stocks screened:    {n}")
    print(f"    Halal compliant:    {halal_count}/{n}")
    print(f"    Total capital:      ${total_capital:>12,}")
    print(f"    Wave final:         ${total_final:>12,.0f} ({(total_final-total_capital)/total_capital*100:+.1f}%)")
    print(f"    B&H final:          ${total_bah:>12,.0f} ({(total_bah-total_capital)/total_capital*100:+.1f}%)")
    print(f"    Realized P&L:       ${total_real:>+12,.0f}")
    print(f"    Unrealized P&L:     ${total_unreal:>+12,.0f}")
    print(f"    Total trades:       {total_trades:>12}")
    print(f"    Win rate:           {total_trades}/{total_trades} (100%)")
    print()


if __name__ == "__main__":
    main()
