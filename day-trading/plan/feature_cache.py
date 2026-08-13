"""Feature cache -- compute the ranking inputs once, not once per config.

WHY: every rotation config re-derives the SAME per-(symbol, date, time)
features. The B-series recomputed coil and 30-bar pressure identically
across 10 configs; the V-series did it 9 more times. That is vectorbt's
actual lesson for a path-dependent strategy: we cannot vectorise the
simulation (rotation, one-position, trail state are all path-dependent),
but the FEATURE layer underneath it is pure and shared.

Cache key: SYM|YYYY-MM-DD -> {"HHMM": [last, high, coil, pressure]}
Pressure is null when the 30-bar window is below the 20k-share trust
floor -- callers must keep treating null as "untrusted", never as 0.

CAUSALITY: features at HHMM use bars with index.time <= HHMM only, the
same slice rank_at takes. Built through CausalView so the boundary is
enforced rather than assumed.

IDENTITY IS THE WHOLE CONTRACT. A cache that changes a single ranking
changes the champion. `--verify` re-computes live and compares every
value; rotation_sim only reads the cache when FEATCACHE=1.

    python plan/feature_cache.py --build  [--label y2025] [--days N]
    python plan/feature_cache.py --verify [--label y2025] [--days N]
"""

import gzip
import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
CACHE = ROOT / "data/massive/featcache"
CACHE.mkdir(parents=True, exist_ok=True)

_spec = importlib.util.spec_from_file_location("causal", ROOT / "plan/causal.py")
causal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(causal)

SCAN_STEP = 5
START = dtime(7, 0)
END = dtime(14, 30)


def steps():
    m = START.hour * 60 + START.minute
    last = END.hour * 60 + END.minute
    while m <= last:
        yield dtime(m // 60, m % 60)
        m += SCAN_STEP


def _key(t):
    return f"{t.hour:02d}{t.minute:02d}"


def build_day(dt_mod, cands, date):
    """cands: rotation_sim day_candidates() output for one date."""
    out = {}
    for r in cands:
        sym = r["c"]["symbol"]
        cv = causal.CausalView(r["df"], sym, date)
        per = {}
        for t in steps():
            w = cv.upto(t)
            if len(w) < 3:
                continue
            last = float(w["Close"].iloc[-1])
            hi = float(w["High"].max())
            coil = (last / hi) if hi > 0 else 0.0
            prs = None
            if len(w) >= 5:
                prs = dt_mod.Candles(w).pressure(len(w) - 1, 30, 20_000)
            per[_key(t)] = [last, hi, coil,
                            (None if prs is None else float(prs))]
        if per:
            out[sym] = per
    return out


def path_for(date):
    return CACHE / f"{date}.json.gz"


def save(date, data):
    with gzip.open(path_for(date), "wt", encoding="utf-8") as f:
        json.dump(data, f)


def load(date):
    p = path_for(date)
    if not p.exists():
        return None
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: feature cache {p.name} unreadable ({e}) -- "
              f"falling back to live computation for this date")
        return None


def _harness():
    spec = importlib.util.spec_from_file_location(
        "rs", ROOT / "plan/rotation_sim.py")
    rs = importlib.util.module_from_spec(spec)
    sys.modules["rs"] = rs
    spec.loader.exec_module(rs)
    return rs


def main():
    argv = sys.argv[1:]
    label = "y2025"
    if "--label" in argv:
        label = argv[argv.index("--label") + 1]
    maxd = None
    if "--days" in argv:
        maxd = int(argv[argv.index("--days") + 1])
    verify = "--verify" in argv

    rs = _harness()
    byday = rs.px.load_by_day(label, 50, "novol")
    items = sorted(byday.items())
    if maxd:
        items = items[:maxd]

    built = checked = mism = 0
    for n, (date, cs) in enumerate(items, 1):
        cands = rs.day_candidates(cs, date, {})
        if not cands:
            continue
        fresh = build_day(rs.dt, cands, date)
        if verify:
            cached = load(date)
            if cached is None:
                print(f"  {date}: NO CACHE (build first)")
                continue
            for sym, per in fresh.items():
                for k, v in per.items():
                    got = cached.get(sym, {}).get(k)
                    checked += 1
                    if got is None or len(got) != 4 or any(
                            (a is None) != (b is None) or
                            (a is not None and abs(a - b) > 1e-9)
                            for a, b in zip(v, got)):
                        mism += 1
                        if mism <= 5:
                            print(f"  MISMATCH {date} {sym} {k}: "
                                  f"live={v} cached={got}")
        else:
            save(date, fresh)
            built += 1
        if n % 50 == 0:
            print(f"  ..{label} {n}/{len(items)}", flush=True)

    if verify:
        print(f"\nverified {checked:,} cached feature rows -> {mism} "
              f"mismatches")
        print("PASS: cache is identical to live computation" if mism == 0
              else "*** FAIL: cache would change the champion ***")
        sys.exit(1 if mism else 0)
    tot = sum(f.stat().st_size for f in CACHE.glob("*.json.gz"))
    print(f"\nbuilt {built} dates -> {CACHE} ({tot/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
