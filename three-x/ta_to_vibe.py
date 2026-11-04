"""Turn TradingAgents' ratings into positions and run them in Vibe-Trading.

TradingAgents' own backtest only scores ratings, it holds no portfolio, so the dollars come from
here. Mapping fixed before seeing the ratings: Buy/Overweight = fully in, Underweight/Sell = flat,
Hold = keep the previous position, flat until the first Buy. Decisions on date D fill at the next
open through Vibe's normal one-bar shift. A second mapping, added after seeing the ratings, reads
them as trims (POST_HOC below); it is post-hoc and is reported as such.

Usage: venvs/vt/Scripts/python ta_to_vibe.py
Writes results/ta_vibe.csv.
"""
import contextlib
import io
import json
import os
import shutil
import sys

import pandas as pd

import sweep

RUNS = {"AMD": "v2_amd", "NVDA": "v2_nvda", "MU": "v2_mu"}
IN, OUT = {"Buy", "Overweight"}, {"Underweight", "Sell"}
POST_HOC = {"Buy": 1.0, "Overweight": 1.0, "Hold": 1.0, "Underweight": 0.5, "Sell": 0.0}
END = "2026-11-03"


def positions(ticker):
    entries = json.loads((sweep.RESULTS / f"ta_{RUNS[ticker]}.json").read_text(encoding="utf-8"))
    entries = sorted((e for e in entries if e["ticker"] == ticker), key=lambda e: e["date"])
    held, out = 0.0, {}
    for e in entries:
        if e["rating"] in IN:
            held = 1.0
        elif e["rating"] in OUT:
            held = 0.0
        out[e["date"]] = held
    return out, entries


def run(name, by_code, start):
    from backtest.runner import main

    codes = sorted(by_code)
    cfg = {"family": "external", "by_code": {f"{c}.US": w for c, w in by_code.items()}}
    run_dir = sweep.RUNS / name
    (run_dir / "code").mkdir(parents=True, exist_ok=True)
    src = (sweep.HERE / "signal_template.py").read_text(encoding="utf-8").replace(
        'PARAMS = {"family": "bh"}', "PARAMS = " + repr(cfg), 1)
    (run_dir / "code" / "signal_engine.py").write_text(src, encoding="utf-8")
    (run_dir / "config.json").write_text(json.dumps({
        "codes": [f"{c}.US" for c in codes], "start_date": start, "end_date": END, "source": "yfinance",
        "interval": "1D", "engine": "daily", "initial_cash": sweep.CASH, "position_adjustment": "rebalance",
        "rebalance_tolerance": 0.1, "slippage_us": 0.0005}), encoding="utf-8")
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        main(run_dir)
    eq = pd.read_csv(run_dir / "artifacts" / "equity.csv").equity
    shutil.rmtree(run_dir, ignore_errors=True)
    return float(eq.iloc[-1] / eq.iloc[0]), float((eq / eq.cummax() - 1).min())


if __name__ == "__main__":
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
    os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
    sys.path.insert(0, sweep.VT_AGENT)
    os.chdir(sweep.VT_AGENT)
    rows = []
    for ticker in RUNS:
        pos, entries = positions(ticker)
        start = min(pos)
        counts = pd.Series([e["rating"] for e in entries]).value_counts().to_dict()
        mult, dd = run(f"ta_{ticker}", {ticker: pos}, start)
        # Added after seeing the ratings, because AMD never got a Buy and its reports advise trims.
        pos2 = {e["date"]: POST_HOC[e["rating"]] for e in entries}
        mult2, dd2 = run(f"ta_trim_{ticker}", {ticker: pos2}, start)
        hold_all = {start: 1.0}
        bh, bh_dd = run(f"ta_bh_{ticker}", {ticker: hold_all}, start)
        rows.append({"ticker": ticker, "start": start, "decisions": len(entries), "ratings": counts,
                     "ta_multiple": mult, "ta_dd": dd, "ta_trim_multiple": mult2, "ta_trim_dd": dd2,
                     "bh_multiple": bh, "bh_dd": bh_dd})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(sweep.RESULTS / "ta_vibe.csv", index=False)
