"""AMD strategy built from the patterns in AMD_QUARTERS.md, one addition per version. Backtest only, no orders.

Settings were fixed before any backtest of this rule, and every addition stays in, so nothing here is chosen by results.
Pattern 5 (quarter shapes) is not an addition, because a shape is only known after the quarter. The patterns were read from these
same 3 years, so this is an in-sample test and flatters the rule. Runs in Vibe-Trading, $100k, data through 2026-11-05.

Usage: venvs/vt/Scripts/python amd_strategy.py <lumibot job path>. Writes results/amd_strategy*.csv.
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
WINDOWS = {"oct25": "2025-10-01", "3y": A.FROM}
BASE_RULE = {"rule": "patterns", "cadence": "D", "fall": 0.20, "bounce": 0.10, "near": 0.09, "below": 0.07, "confirm": 0.05, "min_days": 10, "target": 0.28}
VERSIONS = {"v3.0": ("pattern 1: buy the second low", {}),
            "v3.1": ("+ pattern 2: half size unless lows are rising", {"regime": 1}),
            "v3.2": ("+ pattern 3: 10% trail on days 26-53", {"regime": 1, "tops": 1}),
            "v3.3": ("+ pattern 4: sell half at +28% unless long base or crash", {"regime": 1, "tops": 1, "rise": 1}),
            "v3.4": ("+ pattern 6: next day after a report", {"regime": 1, "tops": 1, "rise": 1, "nextday": 1})}
FINAL = VERSIONS["v3.4"][1]
BLOCKS = json.loads((A.RES / "amd_shape_blocks.json").read_text(encoding="utf-8"))
VERSIONS["v3.5"] = ("+ pattern 5: no position when the quarter so far looks like a bad shape", {**FINAL, "shape_blocks": BLOCKS})

spec = importlib.util.spec_from_file_location("signal_template", Path(__file__).parent / "signal_template.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def rule_list():
    out = {"hold": {"rule": "hold", "cadence": "W"}}
    for version, (_, extra) in VERSIONS.items():
        out[version.replace(".", "p")] = {**BASE_RULE, **extra}
    for fall in (0.18, 0.20, 0.22):
        for bounce in (0.08, 0.10, 0.12):
            for confirm in (0.03, 0.05, 0.08):
                for target in (0.25, 0.28, 0.31):
                    name = f"n_f{int(fall * 100)}_b{int(bounce * 100)}_c{int(confirm * 100)}_t{int(target * 100)}"
                    out[name] = {**BASE_RULE, **FINAL, "fall": fall, "bounce": bounce, "confirm": confirm, "target": target}
    return out


RULES = rule_list()


def job(window, name):
    return ["AMD"], {**A.BASE, "end": END, "trade_from": WINDOWS[window], **RULES[name], "tag": f"S_{window}_{name}"}


def curve(window, name):
    eq = pd.read_csv(A.RES / "curves_amd" / f"AMD__amdcycle__S_{window}_{name}.csv", usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
    eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
    return eq[~eq.index.duplicated()].loc[WINDOWS[window]:]


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "0"  # today's bar is needed
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        for name, status, err in pool.imap_unordered(sweep.run_one, [job(w, n) for w in WINDOWS for n in RULES]):
            if status == "error":
                print("ERROR", name, str(err)[:400])
    raw = yf.download("AMD", start=A.BASE["start"], end=END, auto_adjust=True, progress=False)
    frame = pd.DataFrame({"close": raw["Close"].squeeze(), "open": raw["Open"].squeeze()}).dropna()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    rows = []
    for name in RULES:
        row = {"rule": name}
        for window in WINDOWS:
            eq = curve(window, name)
            row[f"{window}_value"] = eq.iloc[-1]
            row[f"{window}_dd"] = float(np.min(eq / eq.cummax() - 1))
            if window == "3y":
                x = eq.values
                win = np.array([x[i + 252] / x[i] for i in range(0, len(x) - 252, 21)])
                row.update({"y1": eq.loc[A.FROM:A.YEAR2].iloc[-1] / eq.iloc[0], "y2": eq.loc[A.YEAR2:A.YEAR3].iloc[-1] / eq.loc[A.YEAR2:].iloc[0], "y3": eq.iloc[-1] / eq.loc[A.YEAR3:].iloc[0],
                            "windows_2x": float((win >= 2).mean()), "windows_3x": float((win >= 3).mean())})
                if name != "hold":
                    state = rules._amdcycle(frame, {**job(window, name)[1], "want_state": 1}).reindex(eq.index).ffill()
                    weight = rules._amdcycle(frame, job(window, name)[1]).reindex(eq.index).ffill().fillna(0.0)
                    row.update({"trades": int(state.iloc[-1] - state.iloc[0]), "invested": float(weight.mean())})
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(A.RES / "amd_strategy.csv", index=False)
    pd.set_option("display.width", 200, "display.max_columns", 20, "display.max_rows", 40)
    fmt = lambda v: f"{v:,.2f}"
    show = ["rule", "oct25_value", "oct25_dd", "3y_value", "3y_dd", "y1", "y2", "y3", "invested", "trades", "windows_2x", "windows_3x"]
    print(table[~table.rule.str.startswith("n_")][show].to_string(index=False, float_format=fmt))
    near = table[table.rule.str.startswith("n_")]
    hold = table[table.rule == "hold"].iloc[0]
    print(f"\nnearby settings of v3.4: {len(near)}; beat held over 3 years {(near['3y_value'] > hold['3y_value']).sum()}, since Oct 2025 {(near.oct25_value > hold.oct25_value).sum()}")
    print(f"3 years quartiles {near['3y_value'].quantile(.25):,.0f} / {near['3y_value'].median():,.0f} / {near['3y_value'].quantile(.75):,.0f}, range {near['3y_value'].min():,.0f} to {near['3y_value'].max():,.0f}")
    print(f"since Oct 2025 quartiles {near.oct25_value.quantile(.25):,.0f} / {near.oct25_value.median():,.0f} / {near.oct25_value.quantile(.75):,.0f}, range {near.oct25_value.min():,.0f} to {near.oct25_value.max():,.0f}")

    eq = curve("3y", "v3p4")
    cfg = job("3y", "v3p4")[1]
    weight = rules._amdcycle(frame, cfg).loc[A.FROM:]
    state = rules._amdcycle(frame, {**cfg, "want_state": 1}).loc[A.FROM:]
    print("\nv3.4 trades over 3 years (signal at the close, filled next open)")
    trades = []
    for day in state.index[state.diff().fillna(state) != 0]:
        later = frame.index[frame.index > day]
        fill = frame.open.loc[later[0]] if len(later) else float("nan")
        before = weight.shift().fillna(0).loc[day]
        action = "buy " if weight.loc[day] > before else "sell"
        size = "all" if weight.loc[day] == 0 else f"to {weight.loc[day]:.0%}"
        trades.append({"signal": day.date(), "action": action.strip(), "close": frame.close.loc[day], "fill": fill, "invested_after": weight.loc[day], "account": eq.asof(day) / eq.iloc[0]})
        print(f"  {day.date()} {action} {size:8s} close {frame.close.loc[day]:7.2f} fill {fill:7.2f} account {eq.asof(day) / eq.iloc[0]:.2f}x")
    pd.DataFrame(trades).to_csv(A.RES / "amd_strategy_trades.csv", index=False)
    print(f"  now invested {weight.iloc[-1]:.0%}, account {eq.iloc[-1] / eq.iloc[0]:.2f}x")
    reports = pd.to_datetime(A.REPORTS).sort_values()
    reports = reports[reports >= "2023-10-01"]
    for version in ("v3p4", "v3p5"):
        eq = curve("3y", version)
        print(f"\n{version} account change between report dates, against AMD")
        q = []
        full = eq.reindex(frame.index.union(eq.index)).ffill()
        for a, b in zip(reports[:-1], list(reports[1:])):
            if a >= eq.index[0] or b > eq.index[0]:
                start = max(a, eq.index[0])
                acc = full.asof(b) / full.asof(start) - 1
                amd = frame.close.asof(b) / frame.close.asof(start) - 1
                q.append(acc)
                print(f"  {a.date()}: account {acc:+.1%}, AMD {amd:+.1%}")
        q = np.array(q)
        print(f"  quarters at 20%+: {(q >= .2).sum()} of {len(q)}; losing: {(q < 0).sum()}; median {np.median(q):+.1%}")
    lb = [{"name": sweep.key(*job(w, v)), "codes": ["AMD"], "cfg": job(w, v)[1], "start": WINDOWS[w], "end": "2026-11-05"} for w in WINDOWS for v in ("v3p4", "v3p5")]
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(lb, f)


if __name__ == "__main__":
    main()
