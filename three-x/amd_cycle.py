"""AMD only, last 3 years, weekly or monthly decisions, cash allowed (user order 2026-11-05). Runs in Vibe-Trading.

Run 1: timing around earnings. Run 2: wait for a 20% or 25% fall before buying. Run 3: rules from the study of AMD's
turns (amd_turns.py); STUDY_RULE was set before any run 3 backtest, the others show how much it depends on exact numbers.
The rule list below was fixed before any of these backtests ran. With 3 years and 12 reports there is too little
history to prove anything, so besides the full 3 years a fairer test is shown: rank on the first 2 years, score the last.

Usage: venvs/vt/Scripts/python amd_cycle.py [workers]. Writes results/amd_cycle.csv.
"""
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import sweep

RES = Path(__file__).parent / "results"
FROM, YEAR2, YEAR3 = "2023-11-06", "2024-11-06", "2025-11-06"
REPORTS = [d for d in json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"] if d >= "2022-01-01"]
BASE = {"family": "amdcycle", "start": "2022-06-01", "trade_from": FROM, "reports": REPORTS}
STUDY_RULE = "W_swing_b35_15_s70_15_w4_st0"


def rules_list():
    out = [("reference", "hold", {"rule": "hold", "cadence": "W"})]
    for k in (0, 1, 2):
        for w in (1, 2, 3, 4, 6, 8):
            out.append(("run1", f"W_cash_{k}w_before_until_{w}w_after", {"rule": "earn", "cadence": "W", "k": k, "w": w}))
    for f in (1, 2, 3, 4):
        for sell in ("before", "through"):
            out.append(("run1", f"W_runup_buy_{f}w_before_sell_{sell}", {"rule": "runup", "cadence": "W", "f": f, "sell": sell}))
    for a in (1, 2, 4, 6):
        for b in (2, 4, 6, 8):
            out.append(("run1", f"W_after_wait_{a}w_hold_{b}w", {"rule": "after", "cadence": "W", "a": a, "b": b}))
    out += [("run1", "M_cash_in_report_month", {"rule": "earn", "cadence": "M", "k": 0, "w": 1}),
            ("run1", "M_cash_report_month_and_next", {"rule": "earn", "cadence": "M", "k": 0, "w": 2}),
            ("run1", "M_only_in_report_month", {"rule": "runup", "cadence": "M", "f": 0, "sell": "through"}),
            ("run1", "M_month_after_report", {"rule": "after", "cadence": "M", "a": 0, "b": 1}),
            ("run1", "M_second_month_after_report", {"rule": "after", "cadence": "M", "a": 1, "b": 1}),
            ("run1", "M_two_months_after_report", {"rule": "after", "cadence": "M", "a": 0, "b": 2})]
    exits = {"gain30": {"exit": "target", "gain": 0.30}, "gain50": {"exit": "target", "gain": 0.50}, "gain100": {"exit": "target", "gain": 1.00},
             "trail25": {"exit": "trail"}, "regain": {"exit": "regain"}, "report": {"exit": "report"}}
    for dd in (0.20, 0.25):
        for look in (63, 252):
            for name, ex in exits.items():
                for cadence in ("W", "M"):
                    for post in (0, 1):
                        tag = f"{cadence}_dip{int(dd * 100)}_look{look}_{name}" + ("_afterreport" if post else "")
                        out.append((f"run2_{int(dd * 100)}", tag, {"rule": "dip", "cadence": cadence, "dd": dd, "look": look, "post": post, **ex}))
    for buy_rsi in (30, 35, 40):
        for buy_gap in (0.10, 0.15, 0.20):
            for sell_rsi in (65, 70, 75):
                for sell_gap in (0.10, 0.15, 0.25):
                    for wait in (0, 4):
                        for stop in (0, 0.30):
                            tag = f"W_swing_b{buy_rsi}_{int(buy_gap * 100)}_s{sell_rsi}_{int(sell_gap * 100)}_w{wait}_st{int(stop * 100)}"
                            out.append(("run3", tag, {"rule": "swing", "cadence": "W", "buy_rsi": buy_rsi, "buy_gap": buy_gap, "sell_rsi": sell_rsi,
                                                      "sell_gap": sell_gap, "wait": wait, "stop": stop}))
    return out


def job(tag, params):
    return ["AMD"], {**BASE, **params, "tag": tag}


def curve(tag):
    eq = pd.read_csv(RES / "curves_amd" / f"AMD__amdcycle__{tag}.csv", usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
    eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
    return eq[~eq.index.duplicated()].loc[FROM:]


def score(group, tag, params):
    eq = curve(tag)
    mult = lambda a, b: eq.loc[a:b].iloc[-1] / eq.loc[a:b].iloc[0]
    x = eq.values
    win = [x[i + 252] / x[i] for i in range(0, len(x) - 252, 21)]
    sig = sweep_signal(params, eq.index)
    trades = int((np.diff(sig) != 0).sum())
    return {"group": group, "rule": tag, "three_years": x[-1] / x[0], "first_2y": mult(FROM, YEAR3), "last_2y": mult(YEAR2, None), "y1": mult(FROM, YEAR2), "y2": mult(YEAR2, YEAR3), "y3": mult(YEAR3, None),
            "max_dd": float(np.min(x / np.maximum.accumulate(x) - 1)), "in_market": float(sig.mean()), "changes": trades,
            "windows_2x": float(np.mean(np.array(win) >= 2)), "windows_3x": float(np.mean(np.array(win) >= 3)), "windows_median": float(np.median(win))}


def sweep_signal(params, index):
    import importlib.util
    spec = importlib.util.spec_from_file_location("signal_template", Path(__file__).parent / "signal_template.py")
    rules = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules)
    frame = sweep_signal.frame
    return rules._amdcycle(frame, {**BASE, **params}).reindex(index).ffill().fillna(0.0).values


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
    os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
    import yfinance as yf
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    all_rules = rules_list()
    with mp.Pool(workers, initializer=sweep.init_worker) as pool:
        bad = [(n, e) for n, status, e in pool.imap_unordered(sweep.run_one, [job(t, p) for _, t, p in all_rules]) if status == "error"]
    if bad:
        print("errors", len(bad), str(bad[0])[:500])
    raw = yf.download("AMD", start=BASE["start"], end=sweep.END, auto_adjust=True, progress=False)
    frame = pd.DataFrame({"close": raw["Close"].squeeze()}).dropna()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    sweep_signal.frame = frame
    table = pd.DataFrame([score(g, t, p) for g, t, p in all_rules if (RES / "curves_amd" / f"AMD__amdcycle__{t}.csv").exists()])
    table.to_csv(RES / "amd_cycle.csv", index=False)
    pd.set_option("display.width", 220, "display.max_columns", 20, "display.max_rows", 100, "display.max_colwidth", 44)
    fmt = lambda v: f"{v:.2f}"
    show = ["rule", "three_years", "y1", "y2", "y3", "max_dd", "in_market", "changes", "windows_2x", "windows_3x", "windows_median"]
    ref = table[table.group == "reference"].iloc[0]
    print("AMD held:", ref[show[1:]].astype(float).round(2).to_dict())
    for group in ("run1", "run2_20", "run2_25", "run3"):
        part = table[table.group == group]
        print(f"\n=== {group}: {len(part)} rules; beat AMD held over 3 years: {(part.three_years > ref.three_years).sum()}; median rule {part.three_years.median():.2f}x; median time in the market {part.in_market.median():.0%}")
        print(part.sort_values("three_years", ascending=False).head(8)[show].to_string(index=False, float_format=fmt))
        order = part.sort_values("first_2y", ascending=False)
        pick = order.iloc[0]
        top = order.head(10)
        print(f"fairer test, ranked on the first 2 years: top pick {pick.rule} made {pick.first_2y:.2f}x then {pick.y3:.2f}x in year 3; top 10 median in year 3 {top.y3.median():.2f}x; AMD held in year 3 {ref.y3:.2f}x and {ref.first_2y:.2f}x before that")
        back = part.sort_values("last_2y", ascending=False)
        print(f"same test backwards, ranked on the last 2 years: top pick {back.iloc[0].rule} made {back.iloc[0].last_2y:.2f}x then {back.iloc[0].y1:.2f}x in year 1; top 10 median in year 1 {back.head(10).y1.median():.2f}x; AMD held in year 1 {ref.y1:.2f}x")
    run3 = table[table.group == "run3"]
    print(f"\nrun 3 spread: 3-year multiple quartiles {run3.three_years.quantile(.25):.2f} / {run3.three_years.median():.2f} / {run3.three_years.quantile(.75):.2f}; median trades {run3.changes.median():.0f}; median time in market {run3.in_market.median():.0%}; median worst fall {run3.max_dd.median():.0%}")
    print("\nstudy rule, set in advance:")
    print(table[table.rule == STUDY_RULE][show].to_string(index=False, float_format=fmt))
    for name in (STUDY_RULE, run3.sort_values("three_years", ascending=False).rule.iloc[0]):
        params = next(p for _, t, p in all_rules if t == name)
        eq = curve(name)
        pos = pd.Series(sweep_signal(params, eq.index), index=eq.index)
        change = pos[pos.diff().fillna(pos) != 0]
        print(f"\ntrades of {name}")
        for day, val in change.items():
            print(f"  {day.date()} {'buy ' if val else 'sell'} close {frame.close.asof(day):.2f}, account {eq.loc[day] / eq.iloc[0]:.2f}x")
        print(f"  end {eq.index[-1].date()}: {'still holding' if pos.iloc[-1] else 'in cash'}, account {eq.iloc[-1] / eq.iloc[0]:.2f}x")


if __name__ == "__main__":
    main()
