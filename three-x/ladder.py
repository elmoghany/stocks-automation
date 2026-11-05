"""One strategy, one new addition per version: v1.0, v1.1, v1.2 and so on (user order 2026-11-04).

Fixed before any ladder result was seen:
  - Every run goes through Vibe-Trading's runner. AMD is first choice; the second stock is chosen each January
    from earlier data (the six labels in growth_partner.json), so no version assumes which stock would win.
  - The additions and their order are the ADDITIONS list below.
  - Periods are 252 bars, restarted every 21. A period counts only if the position changed in it.
  - Train: periods starting before 2021, all finished by the end of 2021. Holdout: periods starting in 2022 on.
    2021 starts are in neither. Every choice uses train only; the holdout is reported, never used to choose.
  - Score = share of periods reaching 2x + share reaching 3x. An addition is kept if its best setting raises the
    train score by at least 0.02. Otherwise it is logged as tested and the next version builds on the last kept one.
  - Goal: 3x in at least 50% of holdout periods. A version reaching it would still need Lumibot and cost checks.

Protocol v2, added after v1 kept raising the train score while the holdout collapsed (v1.23): the same additions in the
same order, but one is kept only if its train score also does not fall in either half of train (starts 2013-2016 and
2017-2020). The holdout had already been seen when v2 was written, so v2's holdout is not a clean test.

Usage: venvs/vt/Scripts/python ladder.py [workers] [v1|v2]. Resumable: finished curves are reused.
Writes results/ladder.csv or results/ladder_v2.csv.
"""
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import sweep

HERE = Path(__file__).parent
RES = HERE / "results"
LABELS = json.loads((RES / "growth_partner.json").read_text(encoding="utf-8"))
POOL = json.loads((RES / "growth_pool.json").read_text(encoding="utf-8"))
HOLD, STEP, MIN_GAIN = 252, 21, 0.02
TRAIN_END, HOLD_START = pd.Timestamp("2021-01-01"), pd.Timestamp("2022-01-01")
MARKET = ["QQQ", "SMH"]

spec = importlib.util.spec_from_file_location("signal_template", HERE / "signal_template.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)

EARN = json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))
VIX = pd.Series(json.loads((RES / "vix_close.json").read_text(encoding="utf-8")))
HALF = pd.Timestamp("2017-01-01")


def fear_days(high, low):
    """Days the VIX closed below low, having closed above high within the past 21 bars."""
    return list(VIX.index[(VIX < low) & (VIX.rolling(21).max() > high)])


# (version, addition, where the idea comes from, settings to try)
ADDITIONS = [
    ("v1.1", "market filter: no stocks while QQQ is below its average", "Faber; Vibe-Trading regime skills", [{"regime": 200}, {"regime": 100}]),
    ("v1.2", "sector filter: buy AMD only while SMH is above its average", "Minervini leading group; pysystemtrade", [{"sector": 100}, {"sector": 200}]),
    ("v1.3", "earnings-style gap entry: big gap up on heavy volume", "post-earnings drift; Vibe-Trading skills", [{"gap": (0.08, 2)}, {"gap": (0.05, 2)}, {"gap": (0.10, 3)}]),
    ("v1.4", "size by trend strength, resized monthly", "Carver, pysystemtrade", [{"forecast": 1}]),
    ("v1.5", "start with half, add the rest once it is winning", "Turtle pyramiding; freqtrade position adjustment", [{"pyramid": (0.5, 0.15)}, {"pyramid": (0.5, 0.25)}]),
    ("v1.6", "tighter trailing stop after a big gain", "Minervini sell rules", [{"lock": (1.0, 0.15)}, {"lock": (0.5, 0.15)}]),
    ("v1.7", "pick the second stock when selling: strongest of the top 30 by dollar volume", "user request; Bensdorp ranking", [{"use_pool": 1}]),
    ("v1.8", "buy AMD early when the market recovers from a fall", "O'Neil follow-through; Bensdorp", [{"rebound": 0.15}, {"rebound": 0.20}]),
    ("v1.9", "buy in steps on each fall", "user request; freqtrade DCA", [{"steps": 3, "fall": 0.10}, {"steps": 4, "fall": 0.08}]),
    # From here on the additions were designed after seeing the 2022-2025 trades of v1.0-v1.9, which lost mostly to
    # whipsaw chains. Choices still use train only, but the holdout is no longer fully clean for these versions.
    ("v1.10", "trailing stop scaled to each stock's volatility", "chandelier exit; Vibe-Trading ATR skills", [{"trail_k": 4}, {"trail_k": 6}, {"trail_k": 8}]),
    ("v1.11", "hold each position longer before any exit", "user request: 30 days or more", [{"min_hold": 42}, {"min_hold": 63}]),
    ("v1.12", "after a stop-out, rebuy only on a new high", "Turtle, Darvas", [{"reentry_high": 55}, {"reentry_high": 126}]),
    ("v1.13", "buy only while also above the 50-day average", "Minervini", [{"above50": 1}]),
    ("v1.14", "buy only while beating the S&P 500", "relative strength; Bensdorp", [{"rs": 50}, {"rs": 100}]),
    ("v1.15", "skip the second stock while it is too volatile", "volatility filter; Carver", [{"vol_cap": 0.6}, {"vol_cap": 0.8}, {"vol_cap": 1.0}]),
    ("v1.16", "half the money in the second stock", "user request: $50k or $100k", [{"second_size": 0.5}]),
    ("v1.17", "stay in cash after a run of losing trades", "equity-curve filters; freqtrade protections", [{"cooldown": (2, 42)}, {"cooldown": (3, 63)}]),
    ("v1.18", "stay in cash after a large account drawdown", "freqtrade MaxDrawdown protection", [{"brake": (0.25, 63)}, {"brake": (0.35, 63)}]),
    # Proposed by a helper that searched repos and papers. It reported the evidence as mostly portfolio-level or indirect.
    ("v1.19", "let the second stock run unless AMD is clearly stronger", "pysystemtrade buffering; Novy-Marx and Velikov", [{"let_run": 0.0}, {"let_run": 0.10}, {"let_run": 0.25}]),
    ("v1.20", "hard stop while a new trade has not yet gained 20%", "Han, Zhou and Zhu stop-loss momentum", [{"early_stop": 0.10}, {"early_stop": 0.12}, {"early_stop": 0.15}]),
    ("v1.21", "second stock must rise through many small gains", "Da et al. frog-in-the-pan", [{"id_gate": 0.02}, {"id_gate": 0.04}, {"id_gate": 0.06}]),
    ("v1.22", "the trend must be built mostly overnight", "Lou, Polk and Skouras", [{"overnight": 63}, {"overnight": 126}, {"overnight": 252}]),
    ("v1.23", "skip the second stock right after a huge one-day jump", "Bali et al. MAX effect", [{"spike": 0.08}, {"spike": 0.10}, {"spike": 0.12}]),
    ("v1.24", "pick the second stock when selling, by steadiest climb", "Clenow, Stocks on the Move", [{"use_pool": 1, "smooth": 0.15}, {"use_pool": 1, "smooth": 0.20}]),
    ("v1.25", "buy AMD when fear on the VIX fades", "volatility-regime skills in Vibe-Trading", [{"fear_days": fear_days(30, 25)}, {"fear_days": fear_days(40, 30)}]),
    ("v1.26", "after a bad earnings reaction, sell and wait for the next report", "Brandt et al. earnings reaction; helper reported summary-level evidence", [{"veto": x, "earn": EARN} for x in (0.06, 0.10, 0.15)]),
]


def tag_of(version, params):
    return f"{version.replace('.', 'p')}_{hashlib.md5(repr(sorted(params.items())).encode()).hexdigest()[:8]}"


def jobs_for(version, params):
    """The same rule on every way of choosing the second stock."""
    base = {"family": "ladder", "bench_code": "SPY", "market": MARKET, **params, "tag": tag_of(version, params)}
    if params.get("use_pool"):
        names = sorted({n for v in POOL.values() for n in v} - {"AMD"})
        return [(["AMD"] + names, {**base, "uni": "pool_top30", "pool_by_year": POOL})]
    return [(["AMD"] + sorted(set(by_year.values()) - {"AMD"}), {**base, "uni": label, "partner_by_year": by_year})
            for label, by_year in LABELS.items()]


class Bars:
    def __init__(self):
        names = sorted({n for by_year in LABELS.values() for n in by_year.values()} | {n for v in POOL.values() for n in v} | {"AMD", "SPY", *MARKET})
        raw = yf.download(names, start="2012-01-01", end=sweep.END, auto_adjust=True, progress=False)
        raw.index = pd.DatetimeIndex(raw.index).tz_localize(None).normalize()
        self.raw = raw
        self.frames = {}

    def frame(self, k):
        if k not in self.frames:
            f = pd.DataFrame({"open": self.raw["Open"][k], "close": self.raw["Close"][k], "volume": self.raw["Volume"][k]}).dropna()
            f.attrs["bench"] = self.raw["Close"]["SPY"]
            self.frames[k] = f
        return self.frames[k]

    def trades(self, codes, cfg):
        data = {k: self.frame(k) for k in codes}
        market = {m: self.raw["Close"][m].dropna() for m in MARKET}
        return rules._ladder(data, codes, cfg, market)["__state__"]


def windows(name, trades):
    path = RES / "curves_ladder" / f"{name}.csv"
    eq = pd.read_csv(path, usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
    eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
    eq = eq[~eq.index.duplicated()]
    eq = eq[eq.index >= "2013-02-01"]
    count = trades.reindex(eq.index, method="ffill").fillna(0).values
    x, rows = eq.values, []
    for i in range(0, len(eq) - HOLD, STEP):
        rows.append((eq.index[i], x[i + HOLD] / x[i], count[i + HOLD] > count[i], float(np.min(x[i:i + HOLD + 1] / np.maximum.accumulate(x[i:i + HOLD + 1]) - 1))))
    return pd.DataFrame(rows, columns=["start", "mult", "traded", "dd"])


def summary(w):
    hit2, hit3 = (w.mult >= 2) & w.traded, (w.mult >= 3) & w.traded
    return {"n": len(w), "pct_2x": hit2.mean(), "pct_3x": hit3.mean(), "median": w.mult.median(), "worst": w.mult.min(),
            "pct_idle": (~w.traded).mean(), "dd": w.dd.median(), "score": hit2.mean() + hit3.mean()}


def score(jobs, bars):
    w = pd.concat([windows(sweep.key(c, cfg), bars.trades(c, cfg)) for c, cfg in jobs])
    train, hold = w[w.start < TRAIN_END], w[w.start >= HOLD_START]
    return {**{f"train_{k}": v for k, v in summary(train).items()}, **{f"hold_{k}": v for k, v in summary(hold).items()},
            "train_a_score": summary(train[train.start < HALF])["score"], "train_b_score": summary(train[train.start >= HALF])["score"]}


def references(bars):
    """Reference 1: AMD held. Reference 2: half AMD and half that year's second stock, held 12 months."""
    close = bars.raw["Close"].ffill(limit=5)
    close = close[close.index >= "2013-02-01"]
    r1, r2 = [], []
    amd = close["AMD"].values
    for i in range(0, len(close) - HOLD, STEP):
        d = close.index[i]
        m1 = amd[i + HOLD] / amd[i]
        r1.append((d, m1, True, 0.0))
        for by_year in LABELS.values():
            other = close[by_year[str(d.year)]].values
            if np.isfinite(other[i]) and np.isfinite(other[i + HOLD]):
                r2.append((d, 0.5 * (m1 + other[i + HOLD] / other[i]), True, 0.0))
    out = []
    for name, rows in (("Reference 1: AMD held", r1), ("Reference 2: half AMD, half second stock, held", r2)):
        w = pd.DataFrame(rows, columns=["start", "mult", "traded", "dd"])
        train, hold = w[w.start < TRAIN_END], w[w.start >= HOLD_START]
        out.append({"version": name, **{f"train_{k}": v for k, v in summary(train).items()}, **{f"hold_{k}": v for k, v in summary(hold).items()}})
    return out


def base_rule():
    """v1.0: the AMD-first rule with the best train score across the yearly second stocks, from the sweep's grid."""
    import sector_score as ss
    jobs = {sweep.key(c, cfg): (c, cfg) for c, cfg in sweep.auto_jobs()}
    eq = pd.DataFrame({n: s for n in jobs if (s := ss.curve(n)) is not None}).sort_index().ffill(limit=5)
    assert eq.shape[1] == len(jobs), f"auto grid incomplete: {eq.shape[1]} of {len(jobs)}"
    chg, first, raw = ss.changes(eq, jobs)
    refs = ss.Refs(eq.index, raw)
    rows = []
    for c in eq.columns:
        w = ss.window_table(eq, chg, refs, first, c, end=TRAIN_END - pd.Timedelta(days=1))
        rows.append({"rule": ss.rule(c), "hit2": ((w.mult >= 2) & w.traded).mean(), "hit3": ((w.mult >= 3) & w.traded).mean(), "median": w.mult.median()})
    table = pd.DataFrame(rows).groupby("rule").mean().assign(score=lambda d: d.hit2 + d.hit3).sort_values(["score", "median"], ascending=False)
    table.to_csv(RES / "ladder_base_choice.csv")
    print(table.head(8).to_string(float_format=lambda v: f"{v:.3f}"), flush=True)
    best = table.index[0]
    cfg = next(cfg for c, cfg in sweep.auto_jobs() if sweep.key(c, cfg).split("__", 1)[1] == best)
    return {k: cfg[k] for k in ("entry", "exit", "min_hold", "mode", "size", "steps", "fall") if k in cfg}


def run_jobs(pool, jobs):
    failed = [(name, err) for name, status, err in pool.imap_unordered(sweep.run_one, jobs) if status == "error"]
    if failed:
        raise RuntimeError(failed[:2])


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
    os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    protocol = sys.argv[2] if len(sys.argv) > 2 else "v1"
    suffix = "" if protocol == "v1" else f"_{protocol}"
    shown = lambda setting: str({k: ("..." if k in ("earn", "fear_days") else v) for k, v in setting.items()})
    bars = Bars()
    ledger = references(bars)
    current = base_rule()
    with mp.Pool(workers, initializer=sweep.init_worker) as pool:
        run_jobs(pool, jobs_for("v1.0", current))
        best = score(jobs_for("v1.0", current), bars)  # v2 starts from the same base rule
        ledger.append({"version": "v1.0", "addition": "base AMD-first rule, best on train", "source": "Bensdorp, Minervini and others", "setting": str(current), "kept": True, **best})
        for version, addition, source, settings in ADDITIONS:
            version = version.replace("v1.", f"{protocol}.")
            tries = []
            for setting in settings:
                params = {**current, **setting}
                jobs = jobs_for(version, params)
                run_jobs(pool, jobs)
                tries.append((setting, score(jobs, bars)))
            setting, result = max(tries, key=lambda t: (t[1]["train_score"], t[1]["train_median"]))
            kept = result["train_score"] >= best["train_score"] + MIN_GAIN
            if protocol == "v2":
                kept = kept and result["train_a_score"] >= best["train_a_score"] and result["train_b_score"] >= best["train_b_score"]
            ledger.append({"version": version, "addition": addition, "source": source, "setting": shown(setting), "kept": kept, **result})
            if kept:
                current, best = {**current, **setting}, result
            pd.DataFrame(ledger).to_csv(RES / f"ladder{suffix}.csv", index=False)
            print(f"{version} kept={kept} train_score={result['train_score']:.3f} train_3x={result['train_pct_3x']:.3f} hold_2x={result['hold_pct_2x']:.3f} hold_3x={result['hold_pct_3x']:.3f} hold_median={result['hold_median']:.2f}", flush=True)
    (RES / f"ladder{suffix}_final.json").write_text(json.dumps(current, default=str, indent=1), encoding="utf-8")
    show = ["version", "kept", "train_pct_2x", "train_pct_3x", "train_median", "hold_pct_2x", "hold_pct_3x", "hold_median", "hold_worst"]
    print(pd.DataFrame(ledger)[show].to_string(index=False, float_format=lambda v: f"{v:.2f}"))


if __name__ == "__main__":
    main()
