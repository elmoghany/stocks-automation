"""PAPER-3BOOK (2026-10-01): the live WIDE universe for the RL book (and R15).

Rebuilds RL-SERIES v2's pre-registered membership rule (plan/rl2/universe.py)
for ONE live date D, so the live book trades the same kind of universe the
rule was found on:

  (b) over the PRIOR 60 trading sessions (grouped-daily rows with date < D,
      >= 40 printed): median dollar volume >= $2,000,000 and median close
      >= $3.00                                   (data/massive/gd/*.json.gz)
  (a) industry/sector clean + halal-PASS point-in-time at D
      (plan/rl2/halal2.py: HALAL_STRICT=1 PT_FILED=1, network removed)
  -- (c) "printed a bar on D" is a live fact: a name that never trades
      simply never qualifies (the rule needs bar m printed).

The halal-PASS gate here is PART of the universe definition the rule was
searched on; it is not a live selection gate (PAPER-3BOOK ignores halal for
selection and only TAGS trades). Capped at 200 names (most liquid first).

Trading dates are recomputed from the gd files themselves (empty holiday
files skipped); plan/rl2/out/trading_dates.json is a stale cache and is NOT
used.

    python plan/p3_universe.py --build --asof 2026-10-02
      -> data/paper/universe_wide.json  {asof, rule, symbols, prev_close, ...}
Monthly refresh = rerun with a new --asof (keeps the saved scan_id field).
"""
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import p3_lib as P                                           # noqa: E402

GD = P.MASSIVE / "gd"
OUT = P.DATA / "paper" / "universe_wide.json"
LOOKBACK, MIN_OBS, MIN_MDV, MIN_MPX, CAP = 60, 40, 2_000_000.0, 3.0, 200


def trading_dates():
    out = []
    for p in sorted(GD.glob("*.json.gz")):
        with gzip.open(p, "rt") as f:
            if len(f.read(20)) > 3:
                out.append(p.name[:-8])
    return out


def _load(d):
    return json.loads(gzip.open(GD / f"{d}.json.gz", "rt").read())


def screen(asof):
    """Rule (b) for date `asof` from the 60 sessions strictly before it."""
    dates = [d for d in trading_dates() if d < asof][-LOOKBACK:]
    if len(dates) < LOOKBACK:
        raise SystemExit(f"only {len(dates)} gd sessions before {asof}")
    dv, px = {}, {}
    for d in dates:
        for x in _load(d):
            s, c, v = x.get("T"), x.get("c"), x.get("v")
            if not s or c is None or v is None:
                continue
            if not all(ch.isalnum() or ch in ".-" for ch in s):
                continue
            dv.setdefault(s, []).append(c * v)
            px.setdefault(s, []).append(c)
    rows = []
    for s, a in dv.items():
        if len(a) < MIN_OBS:
            continue
        mdv, mpx = float(np.median(a)), float(np.median(px[s]))
        if mdv >= MIN_MDV and mpx >= MIN_MPX:
            rows.append((s, mdv, mpx))
    prev = {x["T"]: x.get("c") for x in _load(dates[-1])}
    return rows, prev, dates


def build(asof):
    t0 = time.time()
    rows, prev, dates = screen(asof)
    import halal2
    m = halal2.load()
    f_lab = 0
    keep = []
    for sym, mdv, mpx in rows:
        p = prev.get(sym)
        if not p:
            continue
        if not (m.industry_clean(sym) and m.sector_clean(sym)):
            continue
        f_lab += 1
        try:
            ok = m.halal_pt(sym, asof, p)
        except Exception:                             # noqa: BLE001
            ok = False
        if ok:
            keep.append({"symbol": sym, "prev_close": round(float(p), 4),
                         "mdv": round(mdv, 1), "mpx": round(mpx, 4)})
    keep.sort(key=lambda r: -r["mdv"])
    keep = keep[:CAP]
    syms = sorted(r["symbol"] for r in keep)
    old = P.read_json(OUT, {}) or {}
    out = {"asof": asof, "built": P.now_et().isoformat(timespec="seconds"),
           "method": "rl2 membership rule rebuilt for asof (screen + "
                     "industry/sector clean + halal_pt PIT)",
           "rule": {"lookback": LOOKBACK, "min_obs": MIN_OBS,
                    "min_mdv": MIN_MDV, "min_mpx": MIN_MPX, "cap": CAP,
                    "gd_window": [dates[0], dates[-1]]},
           "funnel": {"screen": len(rows), "labelled": f_lab,
                      "pass": len(keep)},
           "symbols": syms,
           "prev_close": {r["symbol"]: r["prev_close"] for r in keep},
           "mdv": {r["symbol"]: r["mdv"] for r in keep},
           "scan_id": old.get("scan_id"), "scan_symbols": old.get("scan_symbols"),
           "secs": round(time.time() - t0, 1)}
    if old.get("scan_symbols") and sorted(old["scan_symbols"]) != syms:
        out["scan_stale"] = ("universe changed since the scan was saved -- an "
                             "interactive session must re-save the scan's "
                             "ANY_OF list (create_scan with scan_id)")
    P.write_atomic(OUT, out)
    print(json.dumps({k: out[k] for k in ("asof", "funnel", "rule", "secs")}))
    print(f"wrote {OUT} ({len(syms)} names)")
    return out


def load():
    return P.read_json(OUT, {}) or {}


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--build" in a:
        build(a[a.index("--asof") + 1] if "--asof" in a
              else P.now_et().date().isoformat())
    else:
        print(__doc__)
