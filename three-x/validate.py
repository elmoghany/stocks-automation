"""Stress fixed candidates in Vibe-Trading: higher slippage plus its own statistical validation.

The candidate list is fixed before this runs: the current walk-forward picks plus two hindsight
leaders, labelled as such. Writes results/validate/<name>_<bp>bp.json and results/validate.csv.

Usage: venvs/vt/Scripts/python validate.py
"""
import contextlib
import io
import json
import os
import shutil
import sys
from pathlib import Path

import pandas as pd

import sweep

CANDIDATES = {
    "AMD+PLTR__rotate__every21_n63": "walk-forward pick (1y, 2y, 3y lookback)",
    "AMD+PLTR__rotate__every1_n10": "walk-forward pick (5y lookback)",
    "pitamd__topk__every21_k1_n126": "walk-forward pick (point-in-time rotation)",
    "AMD+NVDA__rotate__every21_n126": "hindsight leader, AMD+NVDA",
    "AMD+MU__rotate__every21_n126": "hindsight leader, last 12 months",
    "AMD__bh": "baseline",
}
SLIPPAGE_BP = (5, 15, 30)
WINDOWS = {"2023": ("2023-01-01", "2023-12-31"), "2024": ("2024-01-01", "2024-12-31"),
           "2025": ("2025-01-01", "2025-12-31"), "last12m": ("2025-11-03", "2026-11-03")}
OUT = sweep.RESULTS / "validate"


def find(name):
    for grid_name in ("pairs", "topk", "singles"):
        for codes, cfg in sweep.grid(grid_name):
            if sweep.key(codes, cfg) == name:
                return codes, cfg
    raise KeyError(name)


def window_mult(eq, a, b):
    s = eq[(eq.index >= a) & (eq.index <= b)]
    return float(s.iloc[-1] / s.iloc[0])


def run(name, bp):
    from backtest.runner import main

    codes, cfg = find(name)
    run_dir = sweep.RUNS / f"val_{name}_{bp}bp"
    (run_dir / "code").mkdir(parents=True, exist_ok=True)
    template = (sweep.HERE / "signal_template.py").read_text(encoding="utf-8")
    src = template.replace('PARAMS = {"family": "bh"}', "PARAMS = " + repr(cfg), 1)
    (run_dir / "code" / "signal_engine.py").write_text(src, encoding="utf-8")
    (run_dir / "config.json").write_text(json.dumps({
        "codes": [f"{c}.US" for c in codes], "start_date": "2015-01-01" if cfg.get("uni") else sweep.START,
        "end_date": sweep.END, "source": "yfinance", "interval": "1D", "engine": "daily",
        "initial_cash": sweep.CASH, "position_adjustment": "rebalance", "rebalance_tolerance": 0.1,
        "slippage_us": bp / 10_000,
        "validation": {"monte_carlo": {"n_simulations": 1000, "seed": 7},
                       "bootstrap": {"n_bootstrap": 1000, "confidence": 0.95, "seed": 7},
                       "walk_forward": {"n_windows": 5}},
    }), encoding="utf-8")
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        main(run_dir)
    eq = pd.read_csv(run_dir / "artifacts" / "equity.csv", usecols=["timestamp", "equity"],
                     parse_dates=["timestamp"], index_col="timestamp").equity
    eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
    val_path = run_dir / "artifacts" / "validation.json"
    val = json.loads(val_path.read_text(encoding="utf-8")) if val_path.exists() else {}
    roll = (eq / eq.shift(252)).dropna()
    row = {"name": name, "bp": bp, "why": CANDIDATES[name], "max_dd": float((eq / eq.cummax() - 1).min()),
           "pct_win_3x": float((roll >= 3).mean()), "median_12m": float(roll.median()),
           **{w: window_mult(eq, a, b) for w, (a, b) in WINDOWS.items()}}
    (OUT / f"{name}_{bp}bp.json").write_text(json.dumps({**row, "validation": val}, indent=1), encoding="utf-8")
    shutil.rmtree(run_dir, ignore_errors=True)
    return row


if __name__ == "__main__":
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
    os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
    sys.path.insert(0, sweep.VT_AGENT)
    os.chdir(sweep.VT_AGENT)
    OUT.mkdir(exist_ok=True)
    rows = []
    for name in CANDIDATES:
        for bp in SLIPPAGE_BP:
            row = run(name, bp)
            rows.append(row)
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items() if k != "why"}, flush=True)
            pd.DataFrame(rows).to_csv(OUT.parent / "validate.csv", index=False)
