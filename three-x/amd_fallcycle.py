"""AMD: buy each big fall, sell the rebound, wait in cash for the next one (user correction 2026-11-05).

The earlier fall rules used an exact percentage checked only on Fridays or month-ends, and typically bought one or two of the
8 falls of 25% or more. Here the stock is watched daily ("D") or weekly ("W"), with at least 10 trading days in each position,
so it is not day trading. USER_RULE was set before any backtest of this rule. The grid shows how much it depends on the numbers.
Runs in Vibe-Trading with data through 2026-11-05. Writes results/amd_fallcycle.csv.

Usage: venvs/vt/Scripts/python amd_fallcycle.py <lumibot job path>
"""
import importlib.util
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import amd_cycle as A
import sweep

END = "2026-11-06"
USER_RULE = "F_D_fall20_look252_steps3_near_high"
EXITS = {"gain25": {"exit": "gain", "gain": 0.25}, "gain40": {"exit": "gain", "gain": 0.40}, "gain60": {"exit": "gain", "gain": 0.60},
         "gain100": {"exit": "gain", "gain": 1.00}, "near_high": {"exit": "near_high"}, "stretched": {"exit": "stretched"}}

spec = importlib.util.spec_from_file_location("signal_template", Path(__file__).parent / "signal_template.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def rules_list():
    out = [("F_hold", {"rule": "hold", "cadence": "W"})]
    for cadence in ("D", "W"):
        for fall in (0.15, 0.20, 0.25, 0.30):
            for look in (126, 252):
                for steps in (1, 2, 3):
                    for name, ex in EXITS.items():
                        for pre in (0, 1):
                            tag = f"F_{cadence}_fall{int(fall * 100)}_look{look}_steps{steps}_{name}" + ("_prereport" if pre else "")
                            out.append((tag, {"rule": "fallcycle", "cadence": cadence, "fall": fall, "look": look, "steps": steps, "min_days": 10, "pre_report": pre, **ex}))
    return out


def job(tag, params):
    return ["AMD"], {**A.BASE, "end": END, **params, "tag": tag}


def mult(eq, a, b=None):
    part = eq.loc[a:b]
    return part.iloc[-1] / part.iloc[0]


def score(tag, params, frame):
    eq = A.curve(tag)
    x = eq.values
    win = np.array([x[i + 252] / x[i] for i in range(0, len(x) - 252, 21)])
    cfg = {**A.BASE, **params}
    weight = rules._amdcycle(frame, cfg).reindex(eq.index).ffill().fillna(0.0)
    trades = 0
    if params["rule"] == "fallcycle":
        state = rules._amdcycle(frame, {**cfg, "want_state": 1}).reindex(eq.index).ffill().fillna(0.0)
        trades = int(state.iloc[-1] - state.iloc[0])
    return {"rule": tag, "three_years": x[-1] / x[0], "first_2y": mult(eq, A.FROM, A.YEAR3), "last_2y": mult(eq, A.YEAR2), "y1": mult(eq, A.FROM, A.YEAR2), "y2": mult(eq, A.YEAR2, A.YEAR3),
            "y3": mult(eq, A.YEAR3), "max_dd": float(np.min(x / np.maximum.accumulate(x) - 1)), "in_market": float((weight > 0).mean()), "avg_invested": float(weight.mean()),
            "trades": trades, "windows_2x": float((win >= 2).mean()), "windows_3x": float((win >= 3).mean()), "windows_median": float(np.median(win))}


def trade_list(tag, params, frame):
    eq = A.curve(tag)
    cfg = {**A.BASE, **params}
    state = rules._amdcycle(frame, {**cfg, "want_state": 1}).reindex(eq.index).ffill().fillna(0.0)
    weight = rules._amdcycle(frame, cfg).reindex(eq.index).ffill().fillna(0.0)
    print(f"\ntrades of {tag}")
    for day in state.index[state.diff().fillna(0) != 0]:
        print(f"  {day.date()} close {frame.close.asof(day):.2f}, invested {weight.loc[day]:.0%}, account {eq.loc[day] / eq.iloc[0]:.2f}x")
    print(f"  end {eq.index[-1].date()}: invested {weight.iloc[-1]:.0%}, account {eq.iloc[-1] / eq.iloc[0]:.2f}x")


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "0"  # today's bar is needed
    all_rules = rules_list()
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        bad = [(n, e) for n, status, e in pool.imap_unordered(sweep.run_one, [job(t, p) for t, p in all_rules]) if status == "error"]
    if bad:
        print("errors", len(bad), str(bad[0])[:500])
    raw = yf.download("AMD", start=A.BASE["start"], end=END, auto_adjust=True, progress=False)
    frame = pd.DataFrame({"close": raw["Close"].squeeze()}).dropna()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    table = pd.DataFrame([score(t, p, frame) for t, p in all_rules])
    table.to_csv(A.RES / "amd_fallcycle.csv", index=False)
    pd.set_option("display.width", 220, "display.max_columns", 20, "display.max_rows", 60, "display.max_colwidth", 46)
    show = ["rule", "three_years", "y1", "y2", "y3", "max_dd", "avg_invested", "trades", "windows_2x", "windows_3x", "windows_median"]
    fmt = lambda v: f"{v:.2f}"
    ref = table[table.rule == "F_hold"].iloc[0]
    print("last close in curves:", A.curve("F_hold").index[-1].date())
    print("AMD held:", ref[show[1:]].astype(float).round(2).to_dict())
    grid = table[table.rule != "F_hold"]
    print(f"\n{len(grid)} rules; beat AMD held over 3 years: {(grid.three_years > ref.three_years).sum()}; quartiles {grid.three_years.quantile(.25):.2f} / {grid.three_years.median():.2f} / {grid.three_years.quantile(.75):.2f}; median trades {grid.trades.median():.0f}")
    print("\nrule set in advance:")
    print(table[table.rule == USER_RULE][show].to_string(index=False, float_format=fmt))
    print("\nbest 10:")
    print(grid.sort_values("three_years", ascending=False).head(10)[show].to_string(index=False, float_format=fmt))
    for label, col in (("fall size", grid.rule.str.extract(r"fall(\d+)")[0]), ("steps", grid.rule.str.extract(r"steps(\d)")[0]), ("check", grid.rule.str.extract(r"F_([DW])_")[0]),
                       ("sale", grid.rule.str.extract(r"steps\d_([a-z0-9_]+?)(?:_prereport)?$")[0]), ("before reports", grid.rule.str.contains("prereport"))):
        print(f"\nby {label}:")
        print(grid.groupby(col).agg(median=("three_years", "median"), best=("three_years", "max"), beat_held=("three_years", lambda s: (s > ref.three_years).mean()),
                                    y3=("y3", "median"), worst_fall=("max_dd", "median"), trades=("trades", "median")).round(2).to_string())
    pick = grid.sort_values("first_2y", ascending=False).iloc[0]
    top = grid.sort_values("first_2y", ascending=False).head(10)
    print(f"\nfair test, ranked on the first 2 years: {pick.rule} made {pick.first_2y:.2f}x then {pick.y3:.2f}x in year 3; top 10 median year 3 {top.y3.median():.2f}x; AMD held {ref.first_2y:.2f}x then {ref.y3:.2f}x")
    back = grid.sort_values("last_2y", ascending=False)
    print(f"backwards, ranked on the last 2 years: {back.iloc[0].rule} made {back.iloc[0].last_2y:.2f}x then {back.iloc[0].y1:.2f}x in year 1; top 10 median year 1 {back.head(10).y1.median():.2f}x; AMD held {ref.last_2y:.2f}x then {ref.y1:.2f}x")
    lookup = dict(all_rules)
    best = grid.sort_values("three_years", ascending=False).rule.iloc[0]
    for tag in (USER_RULE, best, pick.rule):
        trade_list(tag, lookup[tag], frame)
    jobs = [{"name": sweep.key(*job(t, lookup[t])), "codes": ["AMD"], "cfg": job(t, lookup[t])[1], "start": A.FROM, "end": "2026-11-05"} for t in dict.fromkeys((USER_RULE, best, pick.rule))]
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(jobs, f)


if __name__ == "__main__":
    main()
