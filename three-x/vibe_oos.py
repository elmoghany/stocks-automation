"""Finish the Vibe agent's out-of-sample step: run its two dev-period picks, unchanged, on later periods.

Usage: venvs/vt/Scripts/python vibe_oos.py
"""
import contextlib
import csv
import io
import json
import os
import shutil
import sys
from pathlib import Path

AGENT_RUN = Path(r"C:\Users\My PC\.vibe-trading\runs\20261104_015016_07_176c2a\dev")
ROOT = Path(r"E:\strategy-repos\runs\vibe_oos")
BH = """import pandas as pd


class SignalEngine:
    def generate(self, data_map):
        n = len(data_map)
        return {k: pd.Series(1.0 / n, index=v.index) for k, v in data_map.items()}
"""
# warmup start, evaluation start, end
PERIODS = {"2023": ("2021-06-01", "2023-01-01", "2023-12-31"), "2024": ("2022-06-01", "2024-01-01", "2024-12-31"),
           "2025": ("2023-06-01", "2025-01-01", "2025-12-31"), "last12m": ("2024-06-01", "2025-11-03", "2026-11-03")}

os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(ROOT)
os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
sys.path.insert(0, r"E:\strategy-repos\Vibe-Trading\agent")
os.chdir(r"E:\strategy-repos\Vibe-Trading\agent")
from backtest.runner import main  # noqa: E402

jobs = {"s4_volfilter_sma50": ("s4", ["AMD.US"]), "s9_amd_nvda_sma100": ("s9", ["AMD.US", "NVDA.US"]),
        "bh_amd": (None, ["AMD.US"]), "bh_amd_nvda": (None, ["AMD.US", "NVDA.US"])}
rows = []
for name, (src, codes) in jobs.items():
    for period, (warm, start, end) in PERIODS.items():
        d = ROOT / f"{name}_{period}"
        shutil.rmtree(d, ignore_errors=True)
        (d / "code").mkdir(parents=True)
        code = (AGENT_RUN / src / "code" / "signal_engine.py").read_text(encoding="utf-8") if src else BH
        (d / "code" / "signal_engine.py").write_text(code, encoding="utf-8")
        (d / "config.json").write_text(json.dumps({
            "source": "yfinance", "codes": codes, "start_date": warm, "end_date": end,
            "evaluation_start_date": start, "interval": "1D", "initial_cash": 100000,
            "commission": 0.001, "engine": "daily", "position_adjustment": "hold"}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            main(d)
        m = next(csv.DictReader(open(d / "artifacts" / "metrics.csv", encoding="utf-8")))
        row = {"strategy": name, "period": period, "multiple": round(1 + float(m["total_return"]), 2),
               "max_dd": round(float(m["max_drawdown"]), 2), "trades": m["trade_count"]}
        rows.append(row)
        print(row, flush=True)
out = Path(r"E:\stocks-automation\three-x\results\vibe_agent_oos.json")
out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
