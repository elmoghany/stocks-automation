"""UNIVERSE+QUOTES (2026-09-16) -- constraint 1, stage 3: rebuild the
CAUSAL wide universe on the widened fundamentals/label coverage.

MEMBERSHIP RULE -- character for character the one in plan/rl2/universe.py
  On trading date D a symbol is ELIGIBLE iff
    (a) halal-PASS point-in-time at D, via
        plan/penny_ax11b_massive.halal_pt(sym, D, prev_close) under
        HALAL_STRICT=1 PT_FILED=1, with the data sources of
        plan/uq_halal.py (same rules, more names answerable);
    (b) over the PRIOR 60 trading days (>= 40 of them present) its MEDIAN
        dollar volume was >= $2,000,000 and its MEDIAN close >= $3.00 --
        read straight out of plan/rl2/out/screen.json.gz, which is the
        incumbent screen, not a re-derivation;
    (c) it printed a 1-minute bar on D (enforced later, at panel build).
  plus (a') the supplementary SIC-group haram screen of uq_halal, which
  can only refuse more.

Nothing about D's own outcome enters. prev_close is the previous TRADING
day's grouped-daily close.

OUTPUT  plan/uq_out/universe/{D}.json     [{"symbol","prev_close","mdv","mpx"}]
        plan/uq_out/universe_stats.json   the per-date funnel
        plan/uq_out/universe_delta.json   before/after vs plan/rl2/out

Usage:
  python plan/uq_universe.py [--workers 8] [--limit N]
"""
import gzip
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

GD = ROOT / "data" / "massive" / "gd"
RL2 = HERE / "rl2" / "out"
OUT = HERE / "uq_out"
UDIR = OUT / "universe"


def _load_gd(d):
    with gzip.open(GD / f"{d}.json.gz", "rt") as f:
        return json.load(f)


def _worker(args):
    dates, screen_part, prev_of = args
    import uq_halal
    m = uq_halal.load()
    out = {}
    for d in dates:
        pc = {r["T"]: r.get("c") for r in _load_gd(prev_of[d])}
        f_lab = f_sec = f_sic = f_sh = f_pt = f_pass = 0
        keep = []
        for sym, mdv, mpx in screen_part[d]:
            p = pc.get(sym)
            if not p:
                continue
            if not m.industry_clean(sym):
                continue
            f_lab += 1
            if not m.sector_clean(sym):
                continue
            f_sec += 1
            if uq_halal.haram_sic_fail(sym)[0]:
                continue
            f_sic += 1
            if uq_halal.shares_asof_uq(sym, d):
                f_sh += 1
            if (ROOT / "data" / "pt_halal" / f"{sym}.json").exists():
                f_pt += 1
            if m.halal_pt(sym, d, p):
                f_pass += 1
                keep.append({"symbol": sym, "prev_close": round(float(p), 4),
                             "mdv": round(mdv, 1), "mpx": round(mpx, 4)})
        (UDIR / f"{d}.json").write_text(json.dumps(keep))
        out[d] = {"screen": len(screen_part[d]), "labelled": f_lab,
                  "sector_ok": f_sec, "sic_ok": f_sic, "shares": f_sh,
                  "pt_halal": f_pt, "pass": f_pass}
    return out, uq_halal.stats()


def main():
    argv = sys.argv[1:]
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv \
        else 8
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    UDIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(RL2 / "screen.json.gz", "rt") as f:
        screen = json.load(f)
    dates = sorted(screen)
    trading = json.loads((RL2 / "trading_dates.json").read_text())
    ti = {d: i for i, d in enumerate(trading)}
    prev_of = {d: trading[ti[d] - 1] for d in dates}
    if limit:
        dates = dates[:limit]
    print(f"universe: {len(dates)} dates, screen "
          f"{min(len(screen[d]) for d in dates)}.."
          f"{max(len(screen[d]) for d in dates)} names/day", flush=True)
    chunks = [dates[i::workers] for i in range(workers)]
    jobs = [(c, {d: screen[d] for d in c}, {d: prev_of[d] for d in c})
            for c in chunks if c]
    t0 = time.time()
    stats, calls = {}, {}
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for st, ca in ex.map(_worker, jobs):
            stats.update(st)
            for k, v in ca.items():
                calls[k] = calls.get(k, 0) + v
            print(f"  ..{len(stats)}/{len(dates)} dates "
                  f"({time.time()-t0:.0f}s)", flush=True)
    keys = ["screen", "labelled", "sector_ok", "sic_ok", "shares",
            "pt_halal", "pass"]
    mean = {k: sum(stats[d][k] for d in stats) / len(stats) for k in keys}
    ps = [stats[d]["pass"] for d in stats]
    rep = {"dates": len(stats), "mean_funnel": {k: round(v, 1)
                                                for k, v in mean.items()},
           "pass_min": min(ps), "pass_max": max(ps),
           "pass_total": sum(ps), "shares_calls": calls,
           "per_date": stats}
    (OUT / "universe_stats.json").write_text(json.dumps(rep, indent=1))
    # before / after
    old = json.loads((RL2 / "universe_stats.json").read_text())["per_date"]
    ops = [old[d]["pass"] for d in stats if d in old]
    delta = {
        "before": {"mean_pass_per_day": round(sum(ops) / len(ops), 1),
                   "total_symbol_days": sum(ops),
                   "mean_labelled": round(sum(old[d]["labelled"]
                                              for d in stats if d in old)
                                          / len(ops), 1)},
        "after": {"mean_pass_per_day": round(sum(ps) / len(ps), 1),
                  "total_symbol_days": sum(ps),
                  "mean_labelled": round(mean["labelled"], 1)},
    }
    oldsyms = set()
    for d in stats:
        f = RL2 / "universe" / f"{d}.json"
        if f.exists():
            oldsyms |= {r["symbol"] for r in json.loads(f.read_text())}
    newsyms = set()
    for d in stats:
        newsyms |= {r["symbol"] for r in
                    json.loads((UDIR / f"{d}.json").read_text())}
    delta["symbols_before"] = len(oldsyms)
    delta["symbols_after"] = len(newsyms)
    delta["kept_from_before"] = len(oldsyms & newsyms)
    delta["dropped_from_before"] = sorted(oldsyms - newsyms)
    (OUT / "universe_delta.json").write_text(json.dumps(delta, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_date"},
                     indent=1))
    print(json.dumps({k: v for k, v in delta.items()
                      if k != "dropped_from_before"}, indent=1))
    print(f"dropped from the incumbent universe: "
          f"{len(delta['dropped_from_before'])} symbols "
          f"{delta['dropped_from_before'][:20]}")


if __name__ == "__main__":
    main()
