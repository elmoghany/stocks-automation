"""RL-SERIES v2 (2026-09-16): the CAUSAL wide intraday universe.

The +10% gapper pool is outcome-conditioned -- a row is in it because the
day's REGULAR-SESSION high cleared +10%, so any look at the name before
that print conditions membership on the future (NOTES "MX-SERIES
RETRACTION #2"). v2 throws the pool away and rebuilds membership from
information that is complete before date D opens.

MEMBERSHIP RULE (nothing about day D's own outcome may enter)
  On each trading date D a symbol is ELIGIBLE iff
    (a) it was halal-PASS point-in-time at D --
        plan/penny_ax11b_massive.halal_pt(sym, D, prev_close) under
        HALAL_STRICT=1 PT_FILED=1, with the de-campaigned point-in-time
        shares cache of plan/rl2/halal2.py;
    (b) over the PRIOR 60 trading days (grouped-daily rows with date < D,
        at least MIN_OBS=40 of them present) its MEDIAN dollar volume was
        >= $2,000,000 and its MEDIAN close was >= $3.00;
    (c) it printed at least one 1-minute bar on D (checked when the bar
        cache is built -- see plan/rl2/backfill_m1w.py).
  prev_close is the grouped-daily close of the previous trading day, i.e.
  strictly before D.

STAGES
  --stage screen   rule (b) only, from data/massive/gd/*.json.gz.
                   -> plan/rl2/out/screen.json.gz  {date: [sym, ...]}
                   -> plan/rl2/out/screen_syms.json  union of symbols
  --stage halal    rule (a) on the screened set, with the full coverage
                   funnel per date.
                   -> plan/rl2/out/universe/{D}.json
                        [{"symbol", "prev_close", "mdv", "mpx"}, ...]
                   -> plan/rl2/out/universe_stats.json

Grouped-daily closes are split-ADJUSTED to the present while the
point-in-time share count is not, so mcap = shares_pt * prev_close_adj is
wrong across a split. This is the same convention v1 and every engine
backtest in this repo uses (the gapper pool's prev_close came from the
same adjusted source); it is recorded, not silently inherited.
"""
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GD = ROOT / "data" / "massive" / "gd"
OUT = HERE / "out"

START = "2024-10-22"          # first decision date of the study
END = "2026-08-06"            # last decision date of the study
LOOKBACK = 60                 # prior trading days for the liquidity screen
MIN_OBS = 40                  # of those 60, how many must have printed
MIN_MDV = 2_000_000.0         # median dollar volume, $
MIN_MPX = 3.0                 # median close, $


def gd_dates():
    """TRADING dates only.

    data/massive/gd holds a file for every weekday, including market
    holidays, whose `results` list is empty. Leaving those in made the
    "previous trading day" of the 20 post-holiday sessions an empty file,
    so prev_close was missing for every symbol and the universe came out
    EMPTY on those dates (2024-11-29, 2024-12-26, 2025-01-02, ...). They
    are dropped once, here, and the 60-day lookback is therefore 60 real
    sessions.
    """
    cache = OUT / "trading_dates.json"
    if cache.exists():
        return json.loads(cache.read_text())
    out = []
    for p in sorted(GD.glob("*.json.gz")):
        with gzip.open(p, "rt") as f:
            if len(f.read(20)) > 3:            # "[]" is 2 bytes
                out.append(p.name[:-8])
    OUT.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out))
    return out


def _load(d):
    return json.loads(gzip.open(GD / f"{d}.json.gz", "rt").read())


def path_safe(s):
    return bool(s) and all(ch.isalnum() or ch in ".-" for ch in s)


def build_matrices(dates):
    """close[D,S], dvol[D,S] float32 with NaN where the name had no row."""
    syms = set()
    rows = []
    for d in dates:
        r = _load(d)
        rows.append(r)
        syms.update(x["T"] for x in r if path_safe(x.get("T")))
    syms = sorted(syms)
    sidx = {s: i for i, s in enumerate(syms)}
    close = np.full((len(dates), len(syms)), np.nan, dtype=np.float32)
    dvol = np.full((len(dates), len(syms)), np.nan, dtype=np.float32)
    for i, r in enumerate(rows):
        for x in r:
            T = x.get("T")
            j = sidx.get(T)
            if j is None:
                continue
            c = x.get("c")
            v = x.get("v")
            if c is None or v is None:
                continue
            close[i, j] = c
            dvol[i, j] = c * v
    return syms, close, dvol


def stage_screen():
    dates = gd_dates()
    t0 = time.time()
    syms, close, dvol = build_matrices(dates)
    print(f"gd: {len(dates)} dates x {len(syms):,} symbols "
          f"({time.time()-t0:.0f}s)", flush=True)
    study = [d for d in dates if START <= d <= END]
    out = {}
    for d in study:
        i = dates.index(d)
        lo = max(0, i - LOOKBACK)
        w_dv = dvol[lo:i]                       # strictly BEFORE d
        w_px = close[lo:i]
        n = np.sum(~np.isnan(w_dv), axis=0)
        with np.errstate(all="ignore"):
            mdv = np.nanmedian(w_dv, axis=0)
            mpx = np.nanmedian(w_px, axis=0)
        ok = (n >= MIN_OBS) & (mdv >= MIN_MDV) & (mpx >= MIN_MPX)
        idx = np.flatnonzero(ok)
        out[d] = [[syms[j], float(mdv[j]), float(mpx[j])] for j in idx]
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / "screen.json.gz", "wt") as f:
        json.dump(out, f)
    union = sorted({s for v in out.values() for s, _, _ in v})
    (OUT / "screen_syms.json").write_text(json.dumps(union))
    szs = [len(v) for v in out.values()]
    print(f"screen: {len(study)} dates, per-day {min(szs)}..{max(szs)} "
          f"(mean {sum(szs)/len(szs):.0f}), union {len(union):,} symbols",
          flush=True)
    return out


def stage_halal():
    sys.path.insert(0, str(HERE))
    import halal2
    m = halal2.load()
    dates = gd_dates()
    with gzip.open(OUT / "screen.json.gz", "rt") as f:
        screen = json.load(f)
    udir = OUT / "universe"
    udir.mkdir(parents=True, exist_ok=True)
    stats = {}
    t0 = time.time()
    for k, d in enumerate(sorted(screen)):
        i = dates.index(d)
        pc = {r["T"]: r.get("c") for r in _load(dates[i - 1])}
        rows = screen[d]
        f_lab = f_pt = f_sh = f_pass = 0
        keep = []
        for sym, mdv, mpx in rows:
            p = pc.get(sym)
            if not p:
                continue
            if not (m.industry_clean(sym) and m.sector_clean(sym)):
                continue
            f_lab += 1
            if (ROOT / "data" / "pt_halal" / f"{sym}.json").exists():
                f_pt += 1
            if halal2.shares_asof_pt(sym, d):
                f_sh += 1
            if m.halal_pt(sym, d, p):
                f_pass += 1
                keep.append({"symbol": sym, "prev_close": round(float(p), 4),
                             "mdv": round(mdv, 1), "mpx": round(mpx, 4)})
        (udir / f"{d}.json").write_text(json.dumps(keep))
        stats[d] = {"screen": len(rows), "labelled": f_lab, "pt_halal": f_pt,
                    "shares": f_sh, "pass": f_pass}
        if (k + 1) % 50 == 0:
            print(f"  [{k+1}/{len(screen)}] {d} pass={f_pass} "
                  f"({time.time()-t0:.0f}s)", flush=True)
    (OUT / "universe_stats.json").write_text(json.dumps(
        {"rule": {"start": START, "end": END, "lookback": LOOKBACK,
                  "min_obs": MIN_OBS, "min_mdv": MIN_MDV, "min_mpx": MIN_MPX},
         "shares_cache_calls": halal2.stats(),
         "per_date": stats}, indent=1))
    ps = [v["pass"] for v in stats.values()]
    print(f"halal: {len(stats)} dates, PASS per day {min(ps)}..{max(ps)} "
          f"(mean {sum(ps)/len(ps):.1f}), total symbol-days {sum(ps):,}",
          flush=True)
    print("shares cache:", halal2.stats(), flush=True)


if __name__ == "__main__":
    st = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv \
        else "screen"
    if st == "screen":
        stage_screen()
    elif st == "halal":
        stage_halal()
    else:
        raise SystemExit(f"unknown stage {st}")
