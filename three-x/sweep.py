"""Run the strategy grid through Vibe-Trading's own runner (backtest.runner.main).

Each config gets a real run dir (config.json + code/signal_engine.py). Vibe fetches
the data (yfinance, dividend/split adjusted), simulates and writes artifacts; this
script only generates the runs and keeps the equity curves. Resumable.

Usage: vt/Scripts/python sweep.py <grid: singles|pairs|smoke> [workers]
"""
import contextlib
import io
import json
import multiprocessing as mp
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
RUNS = Path(r"E:\strategy-repos\runs")
RESULTS = HERE / "results"
VT_AGENT = r"E:\strategy-repos\Vibe-Trading\agent"
START, END = "2012-01-01", "2026-11-04"
CASH = 100_000
REGIME = {"regime_code": "QQQ", "regime_n": 200}

# Top-50 US names that pass the project's halal list (2026-11 list and top-50, so hindsight-biased).
TOP50_HALAL = ("NVDA MSFT AAPL GOOGL AMZN META AVGO TSLA LLY V XOM MA JNJ PLTR CVX CSCO INTC MU "
               "ISRG NOW QCOM TXN").split()


def single_configs():
    out = [{"family": "bh"}]
    out += [{"family": "sma_trend", "n": n} for n in (20, 50, 100, 200)]
    out += [{"family": "sma_cross", "fast": a, "slow": b} for a, b in ((5, 20), (10, 30), (20, 50), (50, 200))]
    out += [{"family": "donchian", "entry": a, "exit": b} for a, b in ((20, 10), (55, 20), (100, 50), (252, 50))]
    out += [{"family": "macd", "fast": 12, "slow": 26, "signal": 9, "trend": t} for t in (0, 1)]
    out += [{"family": "rsi_pullback", "n": 2, "th": t, "exit_n": 5} for t in (5, 10, 25)]
    out += [{"family": "rsi_pullback", "n": 14, "th": 40, "exit_n": 20, "trend_n": 100}]
    out += [{"family": "bb_revert", "n": 20, "k": k, "trend": t} for k in (1.5, 2.0) for t in (0, 1)]
    out += [{"family": "atr_trail", "entry": a, "k": k} for a, k in ((20, 2), (20, 3), (50, 4), (100, 5))]
    out += [{"family": "abs_mom", "n": n} for n in (21, 63, 126, 252)]
    out += [{"family": "vol_target", "target": t, "n": n} for t in (0.4, 0.6, 0.8) for n in (50, 200)]
    out += [{"family": "dip_buy", "dd": a, "exit_dd": b} for a, b in ((0.2, 0.02), (0.3, 0.05), (0.4, 0.1))]
    out += [{"family": "seasonal", "months": [11, 12, 1, 2, 3, 4]}]
    out += [{"family": "turn_of_month", "before": 3, "after": 3}]
    # The trend-following families again, only while QQQ is above its 200-day average.
    gated = [c for c in out if c["family"] in ("bh", "sma_trend", "donchian", "atr_trail", "abs_mom")]
    return out + [{**c, **REGIME} for c in gated]


def rotation_configs():
    out = [{"family": "rotate", "n": n, "every": e} for n in (10, 21, 63, 126) for e in (1, 5, 21)]
    out += [{"family": "rotate", "n": n, "every": 5, "vol_adj": 1} for n in (21, 63)]
    out += [{"family": "rotate", "n": n, "every": 5, "trend_n": 50} for n in (21, 63)]
    return out + [{**c, **REGIME} for c in out[:6]]


# Partners for AMD from other sectors. "list" = on the project's halal list. "other" = not on it, but
# held by the SPUS shariah ETF or given a PASS ruling (MRNA, KO): these need a halal decision before use.
SECTORS = {
    "energy": {"list": "XOM CVX EOG".split(), "other": "COP SLB DVN HAL".split()},
    "bio": {"list": "LLY JNJ REGN VRTX ISRG".split(), "other": "ABBV GILD BIIB ABT TMO DHR MRK MRNA".split()},
    "materials": {"list": "NEM SCCO".split(), "other": "FCX LIN NUE APD ALB".split()},
    "consumer_ind": {"list": [], "other": "PG PEP KO NKE EMR".split()},
    "growth": {"list": "NVDA MU PLTR AVGO TSLA META VRT ANET APP SHOP CRWD CVNA LRCX COHR PWR".split(),
               "other": "CEG VST UBER AXON TSM NFLX COIN HOOD NET DELL RKLB IONQ".split()},
}
# Second stocks for the AMD-first rules: growth and high volume, plus four from other sectors.
FIRST_PARTNERS = SECTORS["growth"]["list"] + SECTORS["growth"]["other"] + "XOM LLY REGN NEM".split()


def first_configs():
    entries = ("trend", "lthm", "minervini", "breakout", "selloff", "dip")
    exits = ("sma50", "sma100", "trail25", "target50")
    sizing = ({"mode": "first", "size": 1.0}, {"mode": "first", "size": 0.5},
              {"mode": "first", "size": 1.0, "steps": 3, "fall": 0.10},
              {"mode": "first", "size": 1.0, "steps": 4, "fall": 0.08},
              {"mode": "both", "size": 0.5})
    return [{"family": "first", "entry": e, "exit": x, "min_hold": 21, "bench_code": "SPY", **s}
            for e in entries for x in exits for s in sizing]


def first_jobs():
    return [(["AMD", t], {**c, "pool": "sector"}) for t in FIRST_PARTNERS for c in first_configs()]


def auto_jobs():
    """AMD first, the second stock chosen each January from earlier data only (see build_growth_partner.py)."""
    chosen = json.loads((RESULTS / "growth_partner.json").read_text(encoding="utf-8"))
    jobs = []
    for label, by_year in chosen.items():
        names = sorted(set(by_year.values()) - {"AMD"})
        for c in first_configs():
            jobs.append((["AMD"] + names, {**c, "pool": "sector", "uni": label, "partner_by_year": by_year}))
    return jobs


def sector_jobs():
    configs = rotation_configs()
    configs = configs + [{**c, "cash": 1} for c in configs]
    return [(["AMD", t], {**c, "pool": "sector"})
            for groups in SECTORS.values() for names in groups.values() for t in names for c in configs]


def switch_jobs():
    """Hold a stock or cash for at least 21 or 42 trading days (about 30 or 60 calendar days)."""
    configs = [{"family": "switch", "n": n, "trend_n": t, "min_hold": h, "sticky": s}
               for n in (63, 126) for t in (0, 50, 200) for h in (21, 42) for s in (0, 1)]
    return [(["AMD", t], {**c, "pool": "sector"})
            for groups in SECTORS.values() for names in groups.values() for t in names for c in configs]


def batch2_configs():
    out = [{"family": "gap_drift", "gap": g, "vol_mult": v, "hold": h} for g, v, h in
           ((0.03, 1.5, 20), (0.03, 2, 60), (0.05, 1.5, 40), (0.05, 2, 60), (0.08, 2, 60), (0.08, 2, 120), (0.05, 2, 120))]
    out += [{"family": "high_52w", "near": n, "exit_n": e} for n, e in ((0.02, 50), (0.05, 50), (0.02, 100), (0.1, 20))]
    out += [{"family": "squeeze", "pct": q, "exit_n": e} for q, e in ((0.2, 20), (0.2, 50), (0.4, 50))]
    out += [{"family": "down_days", "days": d} for d in (2, 3, 4)]
    out += [{"family": "rs_leader", "n": n, "trend_n": t, "bench_code": "QQQ"} for n, t in ((50, 50), (100, 50), (200, 100))]
    return out


def topk_jobs():
    pit = json.loads((RESULTS / "pit_top50.json").read_text(encoding="utf-8"))
    tag = lambda names: sorted(f"{n}.US" for n in names)
    today = {"2016": tag(["AMD"] + TOP50_HALAL)}
    universes = {"pit": {y: tag(v["halal"]) for y, v in pit.items() if v["halal"]},
                 "pitamd": {y: tag(set(v["halal"]) | {"AMD"}) for y, v in pit.items() if v["halal"]},
                 "todaybiased": today}
    jobs = []
    for uni, elig in universes.items():
        codes = sorted({c[:-3] for names in elig.values() for c in names})
        for n in (21, 63, 126, 252):
            for k in (1, 2):
                for every in (5, 21):
                    for gate in (False, True):
                        cfg = {"family": "topk", "uni": uni, "n": n, "k": k, "every": every, "elig": elig}
                        jobs.append((codes, {**cfg, **REGIME} if gate else cfg))
                for extra in ({"vol_adj": 1}, {"trend_n": 50}):
                    jobs.append((codes, {"family": "topk", "uni": uni, "n": n, "k": k, "every": 5, "elig": elig, **extra}))
    return jobs


def grid(name):
    if name == "topk":
        return topk_jobs()
    if name == "batch2":
        return [([t], c) for t in ["AMD"] + TOP50_HALAL for c in batch2_configs()]
    if name == "overnight":
        return [([t], {"family": "overnight", "interval": "1H"}) for t in ["AMD"] + TOP50_HALAL]
    if name == "smoke":
        return [(["AMD"], {"family": "bh"}), (["AMD"], {"family": "sma_trend", "n": 50}),
                (["AMD", "NVDA"], {"family": "rotate", "n": 63, "every": 5})]
    if name == "first":
        return first_jobs()
    if name == "auto":
        return auto_jobs()
    if name == "sectors":
        return sector_jobs()
    if name == "switch":
        return switch_jobs()
    if name == "refs":  # buy-and-hold curves for the reference comparisons
        partners = [t for groups in SECTORS.values() for names in groups.values() for t in names]
        return [([t], {"family": "bh", "pool": "sector"}) for t in partners]
    if name == "pairs_cash":
        return [(["AMD", t], {**c, "cash": 1}) for t in TOP50_HALAL for c in rotation_configs()]
    if name == "singles":
        return [([t], c) for t in ["AMD"] + TOP50_HALAL for c in single_configs()]
    if name == "pairs":
        pair_cfg = rotation_configs() + [c for c in single_configs() if c["family"] in ("bh", "sma_trend", "donchian")]
        return [(["AMD", t], c) for t in TOP50_HALAL for c in pair_cfg]
    raise ValueError(name)


def key(codes, cfg):
    if cfg.get("family") == "ladder":
        return f"{cfg['uni']}__ladder__{cfg['tag']}"
    if cfg.get("family") == "amdcycle":
        return f"AMD__amdcycle__{cfg['tag']}"
    tail = "_".join(f"{k}{v}" for k, v in sorted(cfg.items())
                    if k not in ("family", "regime_n", "regime_code", "elig", "uni", "bench_code", "interval", "pool", "partner_by_year"))
    tail = tail.replace("[", "").replace("]", "").replace(", ", "-").replace(".", "p")
    gate = "_qqq" if cfg.get("regime_code") else ""
    gate += "_h1" if cfg.get("interval") else ""
    head = cfg["uni"] if cfg.get("uni") else "+".join(codes)
    return f"{head}__{cfg['family']}{gate}__{tail}".rstrip("_")


def run_one(job):
    codes, cfg = job
    name = key(codes, cfg)
    folder = ("curves_hourly" if cfg.get("interval") else "curves_amd" if cfg.get("family") == "amdcycle"
              else "curves_ladder" if cfg.get("family") == "ladder"
              else "curves_sector" if cfg.get("pool") == "sector" else "curves")
    keep = RESULTS / folder / f"{name}.csv"
    if keep.exists() or (RESULTS / "curves" / f"{name}.csv").exists():
        return name, "cached", None
    run_dir = RUNS / name
    (run_dir / "code").mkdir(parents=True, exist_ok=True)
    template = (HERE / "signal_template.py").read_text(encoding="utf-8")
    src = template.replace('PARAMS = {"family": "bh"}', "PARAMS = " + repr(cfg), 1)
    (run_dir / "code" / "signal_engine.py").write_text(src, encoding="utf-8")
    start = cfg.get("start") or ("2015-01-01" if cfg.get("elig") else START)
    all_codes = [f"{c}.US" for c in codes] + ([f"{cfg['regime_code']}.US"] if cfg.get("regime_code") else [])
    cfg_run = dict(cfg)
    if cfg.get("bench_code"):
        all_codes.append(f"{cfg['bench_code']}.US")
        cfg_run["bench_code"] = f"{cfg['bench_code']}.US"
    if cfg.get("regime_code"):
        cfg_run["regime_code"] = f"{cfg['regime_code']}.US"
    if cfg.get("market"):
        cfg_run["market"] = [f"{m}.US" for m in cfg["market"]]
        all_codes += cfg_run["market"]
    if cfg.get("bench_code") or cfg.get("regime_code") or cfg.get("market"):
        src = template.replace('PARAMS = {"family": "bh"}', "PARAMS = " + repr(cfg_run), 1)
        (run_dir / "code" / "signal_engine.py").write_text(src, encoding="utf-8")
    (run_dir / "config.json").write_text(json.dumps({
        "codes": all_codes, "start_date": "2024-12-01" if cfg.get("interval") else start, "end_date": cfg.get("end") or END, "source": "yfinance",
        "interval": cfg.get("interval", "1D"), "engine": "daily", "initial_cash": CASH,
        "position_adjustment": "rebalance", "rebalance_tolerance": 0.1, "slippage_us": 0.0005,
    }), encoding="utf-8")
    from backtest.runner import main
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            main(run_dir)
    except (Exception, SystemExit) as exc:
        return name, "error", f"{exc!r} {sink.getvalue()[-300:]}"
    eq = run_dir / "artifacts" / "equity.csv"
    if not eq.exists():
        return name, "error", sink.getvalue()[-300:]
    keep.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(eq, keep)
    metrics = run_dir / "artifacts" / "metrics.csv"
    if metrics.exists():
        (RESULTS / "metrics").mkdir(exist_ok=True)
        shutil.copyfile(metrics, RESULTS / "metrics" / f"{name}.csv")
    shutil.rmtree(run_dir, ignore_errors=True)
    return name, "ok", None


def init_worker():
    sys.path.insert(0, VT_AGENT)
    os.chdir(VT_AGENT)


if __name__ == "__main__":
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
    os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
    RUNS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    jobs = grid(sys.argv[1])
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    t0, done, errs = time.time(), 0, []
    with mp.Pool(workers, initializer=init_worker) as pool:
        for name, status, err in pool.imap_unordered(run_one, jobs):
            done += 1
            if status == "error":
                errs.append((name, err))
                print("ERR", name, (err or "")[:300], flush=True)
            if done % 50 == 0 or done == len(jobs):
                print(f"{done}/{len(jobs)} {time.time() - t0:.0f}s errors={len(errs)}", flush=True)
    (RESULTS / f"errors_{sys.argv[1]}.json").write_text(json.dumps(errs, indent=1), encoding="utf-8")
