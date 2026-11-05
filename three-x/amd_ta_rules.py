"""Buy and sell AMD on technical indicators instead of days, in Vibe-Trading, $100k, cash between trades, next-open fills, 5 bp slippage.

The signal list comes from amd_ta_study.py and amd_ta_scan.py, and was fixed before any backtest of these rules. Rules are ranked on 2025-2026,
which is also where the signals were studied, so that result flatters them. 2024 played no part in the choice and is shown as the check.

Usage: venvs/vt/Scripts/python amd_ta_rules.py <lumibot job path>. Writes results/amd_ta_rules.csv.
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
WINDOWS = {"y2526": ("2025-01-02", END), "y24": ("2024-01-02", "2025-01-01")}
BUYS = ("stoch_below20", "stoch_up20", "stochfast_below10", "cci_below100", "cci_up100", "rsi_below40", "rsi_up40", "band_below0", "band_up0", "roc_below10", "off25", "rsi40_off20")
SELLS = ("stoch_above85", "stoch_down80", "cci_above100", "cci_down100", "rsi_down65", "rsi_down70", "below20d", "macd_down", "macd_down_pos", "band_down1", "roc_above15", "trail15", "trail25")

spec = importlib.util.spec_from_file_location("signal_template", Path(__file__).parent / "signal_template.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def rule_list():
    out = {"hold": {"rule": "hold", "cadence": "W"}, "days_12_7": {"rule": "quarter", "cadence": "D", "buy_on": "day", "day": 12, "before_next": 7}}
    for b in BUYS:
        for s in SELLS:
            for f in (0, 1):
                out[f"{b}__{s}" + ("__above200" if f else "")] = {"rule": "ta", "cadence": "D", "buy": b, "sell": s, "above200": f, "min_days": 10}
    return out


RULES = rule_list()


def job(window, name):
    begin, end = WINDOWS[window]
    return ["AMD"], {**A.BASE, "end": end, "trade_from": begin, **RULES[name], "tag": f"T_{window}_{name}"}


def curve(window, name):
    eq = pd.read_csv(A.RES / "curves_amd" / f"AMD__amdcycle__T_{window}_{name}.csv", usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
    eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
    return eq[~eq.index.duplicated()].loc[WINDOWS[window][0]:]


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
    os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
    jobs = [job(w, n) for w in WINDOWS for n in RULES]
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        for k, (name, status, err) in enumerate(pool.imap_unordered(sweep.run_one, jobs), 1):
            if status == "error":
                print("ERROR", name, str(err)[:300], flush=True)
            if k % 100 == 0:
                print(f"{k}/{len(jobs)}", flush=True)
    raw = yf.download("AMD", start=A.BASE["start"], end=END, auto_adjust=True, progress=False)
    frame = pd.DataFrame({k.lower(): raw[k].squeeze() for k in ("Open", "High", "Low", "Close", "Volume")}).dropna()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    rows = []
    for name in RULES:
        row = {"rule": name}
        for window in WINDOWS:
            eq = curve(window, name)
            row[f"{window}_value"] = eq.iloc[-1]
            row[f"{window}_dd"] = float(np.min(eq / eq.cummax() - 1))
            if RULES[name]["rule"] == "ta":
                pos = rules._amdcycle(frame, job(window, name)[1]).reindex(eq.index).fillna(0.0)
                row[f"{window}_buys"] = int((pos.diff().fillna(pos) > 0).sum())
                row[f"{window}_invested"] = float(pos.mean())
        rows.append(row)
    t = pd.DataFrame(rows)
    t.to_csv(A.RES / "amd_ta_rules.csv", index=False)
    pd.set_option("display.width", 220, "display.max_columns", 20, "display.max_rows", 60, "display.max_colwidth", 44)
    fmt = lambda v: f"{v:,.2f}"
    refs = t[t.rule.isin(["hold", "days_12_7"])]
    print(refs[["rule", "y2526_value", "y2526_dd", "y24_value", "y24_dd"]].to_string(index=False, float_format=fmt))
    grid = t[~t.rule.isin(["hold", "days_12_7"])].copy()
    hold = t[t.rule == "hold"].iloc[0]
    days = t[t.rule == "days_12_7"].iloc[0]
    print(f"\n{len(grid)} rules. On 2025-26: beat held {(grid.y2526_value > hold.y2526_value).sum()}, beat the day rule {(grid.y2526_value > days.y2526_value).sum()}. On 2024: made money {(grid.y24_value > 100000).sum()}, beat held {(grid.y24_value > hold.y24_value).sum()}, beat the day rule {(grid.y24_value > days.y24_value).sum()}")
    show = ["rule", "y2526_value", "y2526_dd", "y2526_buys", "y2526_invested", "y24_value", "y24_dd", "y24_buys"]
    print("\nbest 15 on 2025-26")
    print(grid.sort_values("y2526_value", ascending=False).head(15)[show].to_string(index=False, float_format=fmt))
    active = grid[grid.y2526_buys >= 4]
    print("\nbest 15 on 2025-26 with at least 4 buys")
    print(active.sort_values("y2526_value", ascending=False).head(15)[show].to_string(index=False, float_format=fmt))
    top = grid.sort_values("y2526_value", ascending=False).head(20)
    print(f"\nbest 20 on 2025-26, in 2024: median ${top.y24_value.median():,.0f}, made money {(top.y24_value > 100000).sum()}, beat held {(top.y24_value > hold.y24_value).sum()}")
    parts = grid.rule.str.split("__", expand=True)
    grid["buy"], grid["sell"], grid["filter"] = parts[0], parts[1], parts[2].fillna("no filter")
    for col in ("buy", "sell", "filter"):
        print(f"\nby {col}: median value")
        print(grid.groupby(col)[["y2526_value", "y24_value"]].median().sort_values("y2526_value", ascending=False).round(0).astype(int).to_string())
    best = grid.sort_values("y2526_value", ascending=False).iloc[0].rule
    for name in dict.fromkeys((best, active.sort_values("y2526_value", ascending=False).iloc[0].rule)):
        eq = curve("y2526", name)
        pos = rules._amdcycle(frame, job("y2526", name)[1]).reindex(eq.index).fillna(0.0)
        print(f"\ntrades of {name}")
        for day in pos.index[pos.diff().fillna(pos) != 0]:
            print(f"  {day.date()} {'buy ' if pos.loc[day] else 'sell'} close {frame.close.loc[day]:.2f}, account ${eq.loc[day]:,.0f}")
        print(f"  end {eq.index[-1].date()}: {'holding' if pos.iloc[-1] else 'in cash'}, ${eq.iloc[-1]:,.0f}")
    lb = [{"name": sweep.key(*job(w, best)), "codes": ["AMD"], "cfg": job(w, best)[1], "start": WINDOWS[w][0], "end": "2026-11-05" if w == "y2526" else "2024-12-31"} for w in WINDOWS]
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(lb, f)


if __name__ == "__main__":
    main()
