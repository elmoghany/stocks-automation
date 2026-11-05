"""Re-run a Vibe-Trading strategy config in Lumibot's own Yahoo backtester (independent engine).

Signals use the same rule functions as signal_template.py. Lumibot supplies the data, the
clock, the fills, the fees and the portfolio accounting.

Usage: venvs/lb/Scripts/python lb_check.py '<json list of jobs>'
  job = {"name": str, "codes": ["AMD"], "cfg": {...}, "start": "2025-11-03", "end": "2026-11-03"}
  codes and cfg may be omitted when name is a config from sweep.py.
Appends one JSON line per job to results/lumibot_checks.jsonl.
"""
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
os.environ.setdefault("IS_BACKTESTING", "True")
os.chdir(r"E:\strategy-repos\lb_runs") if Path(r"E:\strategy-repos\lb_runs").is_dir() else None

import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402
from lumibot.backtesting import YahooDataBacktesting  # noqa: E402
from lumibot.entities import TradingFee  # noqa: E402
from lumibot.strategies import Strategy  # noqa: E402

sys.path.insert(0, str(HERE))
import sweep  # noqa: E402

spec = importlib.util.spec_from_file_location("signal_template", HERE / "signal_template.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)
SLIPPAGE = TradingFee(percent_fee=0.0005)  # same 5 bp per side as the Vibe-Trading runs


class ConfigStrategy(Strategy):
    parameters = {"codes": ["AMD"], "cfg": {"family": "bh"}}

    def initialize(self):
        self.sleeptime = "1D"
        self.history = 420
        self.started = False

    def _bars(self, sym):
        df = self.get_historical_prices(sym, self.history, "day").df
        return df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]

    def _rebalance_today(self, last_bar):
        """Only act on the same signal dates Vibe-Trading used; a rolling window cannot count them."""
        dates = self.parameters.get("signal_dates")
        return dates is None or last_bar in dates or not self.started

    def on_trading_iteration(self):
        p = self.parameters["cfg"]
        codes = self.parameters["codes"]
        last_bar = self._bars("QQQ").index[-1].strftime("%Y-%m-%d")
        if not self._rebalance_today(last_bar):
            return
        self.started = True
        if self.parameters.get("weights"):  # stateful rules: decided once over the full history
            targets = self.parameters["weights"][last_bar]
        elif p["family"] in ("rotate", "topk"):
            # Signal for today's bar: `every` is handled by _rebalance_today.
            today = {**p, "every": 1}
            if "elig" in p:  # the list is in Vibe's "NVDA.US" form, Lumibot's data is keyed "NVDA"
                today["elig"] = {y: [c.replace(".US", "") for c in names] for y, names in p["elig"].items()}
            data = {}
            for c in codes:
                try:
                    bars = self._bars(c)
                except (AttributeError, KeyError, TypeError):  # not listed yet on this date
                    continue
                if len(bars) > p["n"] + 1:
                    data[c] = bars
            have_codes = list(data)
            sig = (rules._rotate if p["family"] == "rotate" else rules._topk)(data, have_codes, today)
            targets = {c: float(sig[c].iloc[-1]) if c in sig else 0.0 for c in codes}
        else:
            data = {c: self._bars(c) for c in codes}
            targets = {c: float(rules._single(data[c], p).iloc[-1]) / len(codes) for c in codes}
        if p.get("regime_code"):
            r = self._bars(p["regime_code"].replace(".US", ""))["close"]
            if not r.iloc[-1] > r.rolling(p["regime_n"]).mean().iloc[-1]:
                targets = {c: 0.0 for c in codes}
        value = self.portfolio_value
        for c, weight in sorted(targets.items(), key=lambda kv: kv[1]):  # sells first, so the cash exists
            held = self.get_position(c)
            if weight == 0 and not held:  # may not be listed yet on this date
                continue
            price = self.get_last_price(c)
            have = float(held.quantity) if held else 0.0
            want = int(value * weight * 0.995 / price)
            if abs(want - have) * price > value * 0.1 or (want == 0 and have > 0):
                if want < have:
                    self.submit_order(self.create_order(c, have - want, "sell"))
                elif want > have:
                    self.submit_order(self.create_order(c, want - have, "buy"))


def curve_path(name):
    for folder in ("curves", "curves_sector", "curves_ladder", "curves_amd"):
        if (HERE / "results" / folder / f"{name}.csv").exists():
            return HERE / "results" / folder / f"{name}.csv"
    return None


def signal_dates(name, cfg):
    """The bars on which Vibe-Trading re-picked: every Nth bar of that run's own calendar."""
    every = cfg.get("every")
    if not every or every == 1:
        return None
    idx = pd.read_csv(curve_path(name), usecols=["timestamp"]).timestamp.str[:10]
    first = cfg["n"] if cfg["family"] == "topk" else 0
    return set(idx.iloc[first::every])


def stateful_plan(job):
    """Decisions for switch and AMD-first rules: the trade dates and each day's target weights."""
    codes, cfg = job["codes"], job["cfg"]
    tickers = sorted(set(codes) | {"SPY", "QQQ", "SMH"})
    bars = yf.download(tickers, start="2012-01-01", end=sweep.END, auto_adjust=True, progress=False)
    bars.index = pd.DatetimeIndex(bars.index).tz_localize(None).normalize()
    data = {}
    for c in codes:
        data[c] = pd.DataFrame({"open": bars["Open"][c], "close": bars["Close"][c], "volume": bars["Volume"][c]}).dropna()
        data[c].attrs["bench"] = bars["Close"]["SPY"]
    if cfg["family"] == "amdcycle":
        sig = {codes[0]: rules._amdcycle(data[codes[0]], cfg)}
        state = sig[codes[0]]
    elif cfg["family"] == "ladder":
        sig = rules._ladder(data, codes, cfg, {m: bars["Close"][m].dropna() for m in ("QQQ", "SMH")})
        state = sig.pop("__state__")
    elif cfg["family"] == "first":
        sig = rules._first(data, codes, cfg)
        state = sig.pop("__state__")
    else:
        sig = rules._switch(data, codes, cfg)
        state = sig[codes[0]] + 2 * sig[codes[1]]
    weights = pd.DataFrame(sig)
    keys = weights.index.strftime("%Y-%m-%d")
    trade_days = set(keys[(state.diff().fillna(0) != 0).values])
    return trade_days, {k: {c: float(v) for c, v in row.items()} for k, row in zip(keys, weights.to_dict("records"))}


def resolve(job):
    """A job may name a sweep config instead of spelling out codes and cfg."""
    if "codes" in job:
        return job
    for grid_name in ("pairs", "pairs_cash", "topk", "singles", "first", "auto", "switch", "sectors"):
        for codes, cfg in sweep.grid(grid_name):
            if sweep.key(codes, cfg) == job["name"]:
                return {**job, "codes": codes, "cfg": cfg}
    raise KeyError(job["name"])


def vibe_multiple(name, a, b):
    path = curve_path(name)
    if path is None:
        return None
    eq = pd.read_csv(path, usecols=["timestamp", "equity"])
    eq = eq[(eq.timestamp.str[:10] >= a) & (eq.timestamp.str[:10] <= b)].equity
    return float(eq.iloc[-1] / eq.iloc[0]) if len(eq) else None


def run(job):
    job = resolve(job)
    start = datetime.fromisoformat(job["start"])
    end = datetime.fromisoformat(job["end"])
    params = {"codes": job["codes"], "cfg": job["cfg"], "signal_dates": signal_dates(job["name"], job["cfg"])}
    if job["cfg"]["family"] in ("first", "switch", "ladder", "amdcycle"):
        params["signal_dates"], params["weights"] = stateful_plan(job)
    result = ConfigStrategy.backtest(
        YahooDataBacktesting, start, end, budget=100_000,
        parameters=params,
        benchmark_asset="QQQ", buy_trading_fees=[SLIPPAGE], sell_trading_fees=[SLIPPAGE],
        show_plot=False, show_tearsheet=False, save_tearsheet=False, show_indicators=False,
        save_logfile=False, quiet_logs=True, show_progress_bar=False,
    )
    row = {"name": job["name"], "start": job["start"], "end": job["end"],
           "total_return": float(result.get("total_return", float("nan"))),
           "max_dd": float((result.get("max_drawdown") or {}).get("drawdown", float("nan")))}
    row["multiple"] = 1 + row["total_return"]
    row["vibe_multiple"] = vibe_multiple(job["name"], job["start"], job["end"])
    with (HERE / "results" / "lumibot_checks.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    print(row, flush=True)


if __name__ == "__main__":
    for job in json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")):
        run(job)
