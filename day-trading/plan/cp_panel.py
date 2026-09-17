"""CHAMPION-REPLAY: compact minute panel cache over the gapper pool.

WHY. `data/massive/m1` holds 113,817 one-day CSVs. Reading them with
pandas costs ~45 ms each (85 minutes for one full pass), which makes
every question in this line unaffordable to ask twice. This builds a
per-DATE npz holding the same numbers on a fixed 04:00-16:00 ET minute
grid, so a full-window pass costs seconds instead of an hour.

WHAT IS IN IT (per date):
  syms      (n,)      symbol strings, pool order
  pc        (n,)      prev_close from the novol pool record
  o,h,l,c   (n, 720)  float32, NaN where no bar printed that minute
  v         (n, 720)  float32 share volume, 0 where no bar
  gain_pct  (n,)      the pool's full-day gain (HINDSIGHT - never used
                      for decisions, kept only to reproduce the biased
                      pool cut and to label the champion's tail months)
  hist_n, rvol, rvol30, gdopen, gdhigh, gdclose, gdvol  (n,)

Grid index m = minutes since 04:00 ET, 0..719 (04:00 -> 15:59).

CAUSALITY. The panel is raw tape, nothing derived. Every consumer must
slice it themselves; nothing here knows about a decision time.

    python plan/cp_panel.py --build [--days N] [--workers K]
    python plan/cp_panel.py --verify [--n 40]
"""

import gzip
import json
import os
import sys
from datetime import date as ddate, datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
M1 = ROOT / "data/massive/m1"
# m1c holds the bars this line fetched for the pool's LISTING-AGE hole
# (plan/cp_fetch.py --job A: the 8,042 candidate symbol-days the
# full-breadth backfill skipped because hist_n < 50). Reading it here is
# what puts recent listings into every causal universe downstream.
M1C = ROOT / "data/massive/m1c"
OUT = ROOT / "data/massive/cp_panel"
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

GRID_START = 4 * 60          # 04:00 ET
NMIN = 720                   # 04:00 .. 15:59


def pool_records(labels=("y2025", "year")):
    """The novol pool: gd regular-session high >= +10%, no rvol filter.

    NOTE this is the OUTCOME-CONDITIONED membership set (the day's own
    regular-session high). It is used here only as a COVERAGE list --
    which symbol-days have bars on disk. Every causal universe in this
    line is re-derived from the bars themselves."""
    recs = {}
    for lab in labels:
        f = ROOT / f"data/massive/gappers_novol_{lab}.json"
        if not f.exists():
            continue
        for r in json.loads(f.read_text()):
            recs.setdefault(r["date"], []).append(r)
    return recs


def _et_offset_minutes(date_str):
    """UTC->ET offset in minutes for 12:00 local on that date."""
    d = ddate.fromisoformat(date_str)
    loc = datetime(d.year, d.month, d.day, 12, 0, tzinfo=ET)
    return int(loc.utcoffset().total_seconds() // 60)


def build_date(date_str, recs):
    """Read every pool CSV for one date onto the fixed grid."""
    off = _et_offset_minutes(date_str)        # -240 (EDT) or -300 (EST)
    syms, pcs, meta = [], [], []
    rows_o, rows_h, rows_l, rows_c, rows_v = [], [], [], [], []
    for r in recs:
        sym = r["symbol"]
        f = M1 / f"{sym}_{date_str}.csv"
        if not f.exists():
            f = M1C / f"{sym}_{date_str}.csv"
            if not f.exists():
                continue
        try:
            raw = f.read_text(errors="ignore")
        except Exception:
            continue
        if raw.startswith("EMPTY") or "\n" not in raw:
            continue
        lines = raw.splitlines()
        if len(lines) < 2:
            continue
        o = np.full(NMIN, np.nan, np.float32)
        h = np.full(NMIN, np.nan, np.float32)
        lo = np.full(NMIN, np.nan, np.float32)
        c = np.full(NMIN, np.nan, np.float32)
        v = np.zeros(NMIN, np.float32)
        got = 0
        for ln in lines[1:]:
            # begins_at,Open,High,Low,Close,Volume
            # "2025-07-31 08:05:00+00:00,1.56,..."
            try:
                ts, rest = ln.split(",", 1)
                hh = int(ts[11:13]); mm = int(ts[14:16])
                # the file's timestamps are UTC (+00:00) in every row
                m = hh * 60 + mm + off
                if m < GRID_START or m >= GRID_START + NMIN:
                    continue
                i = m - GRID_START
                a, b, cc, d, e = rest.split(",")
                o[i] = float(a); h[i] = float(b); lo[i] = float(cc)
                c[i] = float(d); v[i] = float(e)
                got += 1
            except Exception:
                continue
        if not got:
            continue
        syms.append(sym)
        pcs.append(float(r.get("prev_close") or 0.0))
        meta.append((float(r.get("gain_pct") or 0.0),
                     float(r.get("hist_n") or 0.0),
                     float(r.get("rvol") or 0.0),
                     float(r.get("rvol30") or 0.0),
                     float(r.get("open") or 0.0),
                     float(r.get("high") or 0.0),
                     float(r.get("close") or 0.0),
                     float(r.get("volume") or 0.0)))
        rows_o.append(o); rows_h.append(h); rows_l.append(lo)
        rows_c.append(c); rows_v.append(v)
    if not syms:
        return None
    M = np.array(meta, np.float64)
    return dict(
        syms=np.array(syms), pc=np.array(pcs, np.float64),
        o=np.vstack(rows_o), h=np.vstack(rows_h), l=np.vstack(rows_l),
        c=np.vstack(rows_c), v=np.vstack(rows_v),
        gain_pct=M[:, 0], hist_n=M[:, 1], rvol=M[:, 2], rvol30=M[:, 3],
        gdopen=M[:, 4], gdhigh=M[:, 5], gdclose=M[:, 6], gdvol=M[:, 7])


def _one(args):
    date_str, recs = args
    f = OUT / f"{date_str}.npz"
    if f.exists():
        return (date_str, -1)
    d = build_date(date_str, recs)
    if d is None:
        return (date_str, 0)
    tmp = OUT / f".{date_str}.tmp.npz"
    np.savez_compressed(tmp, **d)
    # Windows occasionally holds the handle a beat longer than numpy does
    # (indexer/AV); retry rather than lose the whole batch.
    import time as _t
    for k in range(20):
        try:
            os.replace(tmp, f)
            break
        except PermissionError:
            _t.sleep(0.25 * (k + 1))
    else:
        return (date_str, -2)
    return (date_str, len(d["syms"]))


def load(date_str):
    f = OUT / f"{date_str}.npz"
    if not f.exists():
        return None
    z = np.load(f, allow_pickle=False)
    return {k: z[k] for k in z.files}


def dates():
    return sorted(p.stem for p in OUT.glob("*.npz"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    argv = sys.argv[1:]
    if "--verify" in argv:
        return verify(int(_arg(argv, "--n", 40)))
    recs = pool_records()
    ds = sorted(recs)
    nd = _arg(argv, "--days", None)
    if nd:
        ds = ds[:int(nd)]
    workers = int(_arg(argv, "--workers", 10))
    todo = [(d, recs[d]) for d in ds]
    from concurrent.futures import ProcessPoolExecutor
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for date_str, n in ex.map(_one, todo, chunksize=1):
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(todo)} {date_str} n={n}", flush=True)
    print(f"panel: {len(list(OUT.glob('*.npz')))} dates", flush=True)


def _arg(argv, flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default


def verify(n):
    """Re-read n random CSVs with pandas and compare to the panel."""
    import random
    import pandas as pd
    random.seed(11)
    ds = dates()
    random.shuffle(ds)
    checks = 0
    worst = 0.0
    for date_str in ds[:max(4, n // 8)]:
        P = load(date_str)
        idx = list(range(len(P["syms"])))
        random.shuffle(idx)
        for i in idx[:8]:
            sym = str(P["syms"][i])
            src = M1 / f"{sym}_{date_str}.csv"
            if not src.exists():
                src = M1C / f"{sym}_{date_str}.csv"
            df = pd.read_csv(src, index_col=0, parse_dates=True)
            df.index = df.index.tz_convert(ET)
            for ts, row in df.iterrows():
                m = ts.hour * 60 + ts.minute - GRID_START
                if m < 0 or m >= NMIN:
                    continue
                for k, col in (("o", "Open"), ("h", "High"),
                               ("l", "Low"), ("c", "Close")):
                    a = float(P[k][i, m]); b = float(row[col])
                    if b:
                        worst = max(worst, abs(a - b) / abs(b))
                    checks += 1
    print(f"VERIFY panel: {checks} cell checks, worst relative "
          f"difference {worst:.3e}")
    assert worst < 1e-6, "panel does not reproduce the CSVs"


if __name__ == "__main__":
    main()
