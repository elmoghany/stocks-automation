"""OPEN-UNIVERSE (2026-09-17) step 2: the m1o 1-minute cache.

The minute subset is the top 600 names per date by prior-60-day median dollar
volume: 268,800 symbol-days over 448 dates -- but only 867 DISTINCT symbols,
because the top of the liquidity distribution barely turns over.  So this
backfill does NOT do one API call per symbol-day the way
plan/rl2/backfill_m1w.py does (that pattern costs 268,800 calls).  It walks
the RANGE endpoint per symbol in ~2-month chunks with next_url pagination:

    /v2/aggs/ticker/{SYM}/range/1/minute/{FROM}/{TO}?adjusted=true&limit=50000

~10,000 calls instead of 268,800, and the bytes that come back are identical.

STORAGE.  data/massive/m1o/{SYM}.npz, one file per symbol, resumable at symbol
granularity, holding the 04:00-20:00 ET 1-minute grid for EVERY study date the
symbol printed on:

    dates  (n,)  U10        the dates present, ascending
    o,h,l,c,v    (n, 960) float32, NaN (0 for v) where the minute had no print

The per-symbol layout is deliberate: plan/ou_table.py builds its feature/label
table by walking SYMBOLS, because every feature in the RL2/WIDE-NET block is a
function of one name's own tape, and the cross-sectional step happens later on
the table.  So the whole cache is read exactly once, sequentially.

CAUSALITY.  This file only fetches and stores; every date in the window is
stored for every symbol that has one, so nothing about WHICH rows exist can
encode an outcome.  Membership is decided in plan/ou_universe.py from prior-60-
session grouped-daily rows only.

Usage:
  python plan/ou_backfill.py [--workers 24] [--limit N] [--symbols A,B]
  MASSIVE_TH_INTERVAL=0.25 is the paid-tier pacing the mandate names.
"""
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT.parent))
import ou_lib as L                                            # noqa: E402
from shared import massive                                    # noqa: E402
from shared.win_cred import get_secret                        # noqa: E402

massive._TH_INTERVAL = float(os.environ.get("MASSIVE_TH_INTERVAL", "0.25"))
KEY = get_secret("MASSIVE_KEY")
ET = ZoneInfo("America/New_York")
CHUNK_DAYS = 62
RETRIES = 4
MIN_FREE_GB = 8
ERR_F = L.OUT / "m1o_errors.json"

_lock = threading.Lock()
_stats = {"sym": 0, "calls": 0, "bars": 0, "empty": 0, "fail": 0}
_errors = []


def chunks(dates):
    out, i = [], 0
    while i < len(dates):
        j = min(i + CHUNK_DAYS, len(dates))
        out.append((dates[i], dates[j - 1]))
        i = j
    return out


def fetch_range(sym, d0, d1):
    """All 1-minute bars in [d0, d1] as a list of raw Polygon rows."""
    url = (f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/minute/"
           f"{d0}/{d1}?adjusted=true&sort=asc&limit=50000&apiKey={KEY}")
    rows = []
    guard = 0
    while url and guard < 40:
        guard += 1
        d = massive._get(url)
        with _lock:
            _stats["calls"] += 1
        rows.extend(d.get("results") or [])
        nxt = d.get("next_url")
        url = (nxt + f"&apiKey={KEY}") if nxt else None
    return rows


_M0 = {}


def day_start_minutes(dates):
    """Epoch-minute of 04:00 ET on each date (DST resolved once per date).

    The 960-minute windows of consecutive dates are disjoint and ascending, so
    a bar's (date, slot) is a single searchsorted -- no per-bar datetime, which
    was the whole cost of this stage (~1M zoneinfo conversions per symbol).
    """
    key = (dates[0], dates[-1], len(dates))
    if key not in _M0:
        _M0[key] = np.array(
            [int(datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), 4, 0,
                          tzinfo=ET).timestamp()) // 60 for d in dates],
            dtype=np.int64)
    return _M0[key]


def grid(rows, dates):
    """raw rows -> (o,h,l,c,v) each (len(dates), 960) on the ET 04:00 grid."""
    D = len(dates)
    o = np.full((D, L.NMIN), np.nan, np.float32)
    h = np.full((D, L.NMIN), np.nan, np.float32)
    lo = np.full((D, L.NMIN), np.nan, np.float32)
    c = np.full((D, L.NMIN), np.nan, np.float32)
    v = np.zeros((D, L.NMIN), np.float32)
    if not rows:
        return o, h, lo, c, v, np.zeros(D, bool)
    n = len(rows)
    t = np.fromiter((r["t"] for r in rows), np.int64, n)
    ao = np.fromiter((r["o"] for r in rows), np.float64, n)
    ah = np.fromiter((r["h"] for r in rows), np.float64, n)
    al = np.fromiter((r["l"] for r in rows), np.float64, n)
    ac = np.fromiter((r["c"] for r in rows), np.float64, n)
    av = np.fromiter((r["v"] for r in rows), np.float64, n)
    m = t // 60000                                  # epoch minute of the bar
    m0 = day_start_minutes(dates)
    row = np.searchsorted(m0, m, side="right") - 1
    ok = row >= 0
    slot = np.where(ok, m - m0[np.clip(row, 0, D - 1)], -1)
    ok &= (slot >= 0) & (slot < L.NMIN)
    r_, m_ = row[ok], slot[ok]
    o[r_, m_] = ao[ok]
    h[r_, m_] = ah[ok]
    lo[r_, m_] = al[ok]
    c[r_, m_] = ac[ok]
    v[r_, m_] = av[ok]
    present = np.zeros(D, bool)
    present[np.unique(r_)] = True
    return o, h, lo, c, v, present


def one(sym, dates):
    f = L.M1O / f"{sym}.npz"
    if f.exists() and f.stat().st_size > 0:
        return "hit", 0
    rows = []
    for d0, d1 in chunks(dates):
        last = None
        for attempt in range(RETRIES):
            try:
                rows.extend(fetch_range(sym, d0, d1))
                last = None
                break
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
                if getattr(e, "code", None) in (401, 403):
                    break
                time.sleep(2 * (attempt + 1))
        if last:
            with _lock:
                _errors.append({"symbol": sym, "from": d0, "to": d1,
                                "err": last})
                _stats["fail"] += 1
            return "fail", 0
    o, h, lo, c, v, present = grid(rows, dates)
    if not present.any():
        np.savez_compressed(f, dates=np.array([], dtype="U10"),
                            o=o[:0], h=h[:0], l=lo[:0], c=c[:0], v=v[:0])
        return "empty", 0
    k = np.flatnonzero(present)
    tmp = f.with_name(f.name + f".{os.getpid()}.{threading.get_ident()}.part")
    np.savez_compressed(tmp, dates=np.array([dates[i] for i in k], dtype="U10"),
                        o=o[k], h=h[k], l=lo[k], c=c[k], v=v[k])
    os.replace(str(tmp) + ".npz", f)
    return "got", len(rows)


def main():
    workers, limit = 24, None
    argv = sys.argv[1:]
    if "--workers" in argv:
        workers = int(argv[argv.index("--workers") + 1])
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    dates = L.study_dates()
    pairs = json.loads((L.OUT / "minute_pairs.json").read_text())
    syms = sorted({s for s, _ in pairs})
    if "--symbols" in argv:
        syms = argv[argv.index("--symbols") + 1].split(",")
    L.M1O.mkdir(parents=True, exist_ok=True)
    for p in L.M1O.glob("*.part*"):
        p.unlink()
    todo = [s for s in syms
            if not ((L.M1O / f"{s}.npz").exists()
                    and (L.M1O / f"{s}.npz").stat().st_size > 0)]
    print(f"m1o: {len(pairs):,} symbol-days, {len(syms):,} symbols, "
          f"{len(dates)} dates; cached {len(syms)-len(todo):,}, "
          f"to fetch {len(todo):,} "
          f"(~{len(todo)*len(chunks(dates)):,} calls)", flush=True)
    if limit:
        todo = todo[:limit]
    import shutil
    if shutil.disk_usage(L.M1O).free / 1e9 < MIN_FREE_GB:
        raise SystemExit("ABORT: low disk")
    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.monotonic()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, s, dates): s for s in todo}
        for fu in as_completed(futs):
            try:
                r, nb = fu.result()
            except Exception as e:
                with _lock:
                    _errors.append({"symbol": futs[fu], "err": repr(e)})
                r, nb = "fail", 0
            with _lock:
                if r == "got":
                    _stats["sym"] += 1
                    _stats["bars"] += nb
                elif r in _stats:
                    _stats[r] += 1
                done += 1
                snap = dict(_stats)
            if done % 25 == 0 or done == len(todo):
                el = time.monotonic() - t0
                rate = done / el if el else 0
                nb_ = sum(p.stat().st_size for p in L.M1O.glob("*.npz"))
                print(f"  [{done:,}/{len(todo):,}] got={snap['sym']:,} "
                      f"empty={snap.get('empty',0):,} fail={snap['fail']:,} "
                      f"calls={snap['calls']:,} bars={snap['bars']:,} "
                      f"{nb_/1e9:.2f} GB  {rate*60:.1f} sym/min  eta "
                      f"{(len(todo)-done)/rate/60 if rate else 0:.0f}m",
                      flush=True)
    ERR_F.write_text(json.dumps(_errors[:5000], indent=1))
    nb = sum(p.stat().st_size for p in L.M1O.glob("*.npz"))
    print(f"DONE in {(time.monotonic()-t0)/60:.1f}m: {_stats}; "
          f"cache {nb/1e9:.2f} GB", flush=True)


if __name__ == "__main__":
    main()
