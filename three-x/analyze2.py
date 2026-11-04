"""Faster, stricter scoring of Vibe-Trading curves against 3x in 12 months.

Adds what analyze.py lacks: at each start date only configs tradable at that date compete,
meaning the stock was in that January's point-in-time top-50 halal list (AMD always allowed,
as the user named it). The "todaybiased" universe never competes; it is shown as a control.

Groups: singles / amd_pairs / rotation (point-in-time) / rotation_today (biased control).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
CURVES = HERE / "results" / "curves"
PIT = json.loads((HERE / "results" / "pit_top50.json").read_text(encoding="utf-8"))
TARGET = 3.0
HOLD, STEP = 252, 21
SWITCH_COST = 0.001


def load():
    frames = {}
    for f in sorted(CURVES.glob("*.csv")):
        df = pd.read_csv(f, usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp")
        s = df["equity"]
        s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
        frames[f.stem] = s[~s.index.duplicated()]
    return pd.DataFrame(frames).sort_index().ffill(limit=5)


def group_of(name):
    head = name.split("__")[0]
    if head in ("pit", "pitamd"):
        return "rotation"
    if head == "todaybiased":
        return "rotation_today"
    return "amd_pairs" if "+" in head else "singles"


def names_of(name):
    head = name.split("__")[0]
    return head.split("+")


def tradable(name, year):
    head = name.split("__")[0]
    if head in ("pit", "pitamd"):
        return True
    if head == "todaybiased":
        return False
    allowed = set(PIT.get(str(max(year, 2016)), {"halal": []})["halal"]) | {"AMD"}
    return all(n in allowed for n in names_of(name))


def walk(log_ret, eq, cols, lookback, how):
    """Each month: rank eligible configs on trailing data only, then hold the winner 12 months."""
    rows = []
    idx = eq.index
    cols_arr = np.array(cols)
    x = eq[cols].values
    r = log_ret[cols].values
    for i in range(lookback, len(idx) - HOLD, STEP):
        year = idx[i].year
        allowed = np.array([tradable(c, year) for c in cols])
        start, now = x[i - lookback], x[i]
        ok = allowed & np.isfinite(start) & np.isfinite(now) & (now != start) & np.isfinite(x[i + HOLD])
        if not ok.any():
            continue
        mult = now / start
        if how == "return":
            s = mult
        else:
            win = r[i - lookback + 1:i + 1]
            vol = np.nanstd(win, axis=0)
            s = np.divide(np.nanmean(win, axis=0), vol, out=np.full(len(cols), np.nan), where=vol > 0)
        s = np.where(ok, s, -np.inf)
        j = int(np.nanargmax(s))
        path = x[i:i + HOLD + 1, j]
        rows.append({"start": idx[i].date().isoformat(), "pick": cols_arr[j],
                     "mult": path[-1] / path[0] * (1 - SWITCH_COST),
                     "dd": float(np.nanmin(path / np.fmax.accumulate(path) - 1))})
    return pd.DataFrame(rows)


def summarize(wf):
    return {"n_starts": len(wf), "pct_3x": (wf.mult >= TARGET).mean(), "pct_2x": (wf.mult >= 2).mean(),
            "pct_loss": (wf.mult < 1).mean(), "median": wf.mult.median(), "mean": wf.mult.mean(),
            "worst": wf.mult.min(), "best": wf.mult.max(), "worst_dd": wf.dd.min()}


if __name__ == "__main__":
    eq = load()
    log_ret = np.log(eq).diff()
    groups = {}
    for c in eq.columns:
        groups.setdefault(group_of(c), []).append(c)
    print({k: len(v) for k, v in groups.items()}, "bars", len(eq), eq.index[0].date(), eq.index[-1].date())

    rows = []
    for name, s in eq.items():
        s = s.dropna()
        s = s[s.ne(s.iloc[0]).cummax()]
        if len(s) < 300:
            continue
        roll = (s / s.shift(HOLD)).dropna()
        rows.append({"config": name, "group": group_of(name), "cagr": (s.iloc[-1] / s.iloc[0]) ** (252 / len(s)) - 1,
                     "max_dd": (s / s.cummax() - 1).min(), "pct_win_3x": (roll >= TARGET).mean(),
                     "median_12m": roll.median(), "worst_12m": roll.min(), "best_12m": roll.max(),
                     "last_12m": s.iloc[-1] / s.iloc[-HOLD - 1]})
    table = pd.DataFrame(rows).sort_values("pct_win_3x", ascending=False)
    table.to_csv(HERE / "results" / "hindsight_table.csv", index=False)
    pd.set_option("display.width", 220, "display.max_columns", 20, "display.max_colwidth", 56)
    fmt = {"cagr": "{:.0%}".format, "max_dd": "{:.0%}".format, "pct_win_3x": "{:.1%}".format,
           "median_12m": "{:.2f}".format, "worst_12m": "{:.2f}".format, "best_12m": "{:.2f}".format,
           "last_12m": "{:.2f}".format}
    print("\n=== HINDSIGHT, best per group by share of 12m windows at 3x+ (selection bias: NOT evidence) ===")
    for g in table.group.unique():
        print(f"-- {g}")
        print(table[table.group == g].head(8).drop(columns="group").to_string(index=False, formatters=fmt))
    print("\nlast 12 months, best overall:")
    print(table.sort_values("last_12m", ascending=False).head(10).drop(columns="group").to_string(index=False, formatters=fmt))

    summary = []
    pools = {"singles": groups.get("singles", []), "amd_pairs": groups.get("amd_pairs", []),
             "rotation_pit": groups.get("rotation", []),
             "pit_only": [c for c in groups.get("rotation", []) if c.startswith("pit__")],  # AMD not assumed
             "all_tradable": sum((groups.get(g, []) for g in ("singles", "amd_pairs", "rotation")), [])}
    for pool, cols in pools.items():
        if not cols:
            continue
        for how in ("return", "sharpe"):
            for years in (1, 2, 3, 5):
                wf = walk(log_ret, eq, cols, 252 * years, how)
                if wf.empty:
                    continue
                wf.to_csv(HERE / "results" / f"wf_{pool}_{how}_{years}y.csv", index=False)
                summary.append({"pool": pool, "rank_by": how, "lookback_y": years, **summarize(wf)})
    s = pd.DataFrame(summary)
    s.to_csv(HERE / "results" / "walk_forward_summary.csv", index=False)
    print("\n=== WALK-FORWARD: pick on trailing data only, then hold 12 months, restarted monthly ===")
    print(s.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
