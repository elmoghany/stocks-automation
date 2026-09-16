"""UNIVERSE+QUOTES (2026-09-16) -- constraint 2, stage 1: the execution tape.

THE PREMISE OF THE MANDATE DOES NOT HOLD ON THIS ACCOUNT, and that is the
first finding of this line. `/v3/quotes/{ticker}` and `/v3/trades/{ticker}`
both answer

    HTTP 403  {"status":"NOT_AUTHORIZED",
               "message":"You are not entitled to this data."}

as do `/v2/last/nbbo`, `/v2/last/trade` and `/v2/ticks/stocks/nbbo`. The
paid Starter tier carries aggregates and reference data, not the tick
feeds. Probed 2026-09-16; the probe is reproducible with `--probe`.

WHAT IS ENTITLED, AND WHY IT IS ENOUGH FOR THE FILL QUESTION
  `/v2/aggs/ticker/{sym}/range/1/second/{from_ms}/{to_ms}` returns 200 and
  goes back to at least 2024-10-22 (the first study date). A 1-second
  aggregate IS the trade tape, binned: its `l` is the MINIMUM TRADE PRICE
  in that second and its `n` is the transaction count. So the question the
  mandate actually asks --

      "a limit-buy posted at the decision minute is filled iff a trade
       prints at or below the limit within N minutes"

  -- is answered EXACTLY by min(l) over the seconds in the window. No tick
  feed is required for it; the 1-second low is the same number a tick scan
  would produce. What a 1-second bar CANNOT give is the NBBO, so the
  inside-spread half of the mandate needs a different instrument
  (plan/uq_fills.py: two published high-low spread estimators, validated
  against real Robinhood books pulled live).

WHY ONE CALL PER (SYMBOL, DAY) AND NOT ONE PER DECISION MINUTE
  The mandate says not to fetch full-day ticks for everything, and this
  does not: it fetches 09:30-16:05 ET of 1-second BARS, which is one HTTP
  call of ~2k-10k rows (~120 KB gzipped) per symbol-day. Keying the cache
  by decision minute instead would mean 9 calls for the same day and the
  same bytes. The cache is still addressable per decision minute through
  `window()`; it is simply stored once. Cost measured: 1.0-1.5 s/call,
  ~50 KB/symbol-day on disk.

CACHE   data/massive/trades/{SYM}_{DATE}.json.gz
          {"rows": [[t_ms, o, h, l, c, v, n], ...]}   ascending, adjusted
        A day Polygon has nothing for gets {"rows": []} -- "asked, tape
        silent" is distinguishable from "not fetched yet" by EXISTENCE,
        exactly the sentinel convention of plan/rl2/backfill_m1w.py.

Usage:
  python plan/uq_sec1.py --probe
  python plan/uq_sec1.py --pairs plan/uq_out/sec1_pairs.json [--workers 40]
  python plan/uq_sec1.py --universe        (all rl2 causal-universe pairs)
"""
import gzip
import json
import os
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT.parent))
from shared import massive                                    # noqa: E402

massive._TH_INTERVAL = float(os.environ.get("MASSIVE_TH_INTERVAL", "0.25"))

ET = ZoneInfo("America/New_York")
XDIR = ROOT / "data" / "massive" / "trades"
UNI = HERE / "rl2" / "out" / "universe"
OUT = HERE / "uq_out"
ERR_F = OUT / "sec1_errors.json"
MIN_FREE_GB = 8
RETRIES = 3

FROM_HM = (9, 30)
TO_HM = (16, 5)

_lock = threading.Lock()
_stats = {"got": 0, "empty": 0, "fail": 0}
_errors = []


def et_ms(date, hh, mm):
    y, mo, d = (int(x) for x in date.split("-"))
    return int(datetime(y, mo, d, hh, mm, tzinfo=ET).timestamp()) * 1000


def f_of(sym, date):
    return XDIR / f"{sym}_{date}.json.gz"


def have(sym, date):
    f = f_of(sym, date)
    return f.exists() and f.stat().st_size > 0


def load(sym, date):
    """[[t_ms,o,h,l,c,v,n], ...] or None if not cached."""
    f = f_of(sym, date)
    if not f.exists():
        return None
    try:
        with gzip.open(f, "rt") as h:
            return json.load(h)["rows"]
    except Exception:
        return None


def window(rows, t_lo_ms, t_hi_ms):
    """Rows with t in [t_lo, t_hi). Linear scan is fine: the caller holds
    the day once and slices it a handful of times."""
    return [r for r in rows if t_lo_ms <= r[0] < t_hi_ms]


def fetch_one(sym, date):
    f = f_of(sym, date)
    if have(sym, date):
        return "hit"
    a, b = et_ms(date, *FROM_HM), et_ms(date, *TO_HM)
    url = (f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/second/"
           f"{a}/{b}?limit=50000&sort=asc&adjusted=true"
           f"&apiKey={massive._key()}")
    last = None
    for attempt in range(RETRIES):
        try:
            d = massive._get(url)
            res = d.get("results") or []
            rows = [[r["t"], r.get("o"), r.get("h"), r.get("l"), r.get("c"),
                     r.get("v"), r.get("n")] for r in res]
            tmp = f.parent / f"{f.name}.{os.getpid()}.{threading.get_ident()}.part"
            with gzip.open(tmp, "wt") as h:
                json.dump({"rows": rows}, h, separators=(",", ":"))
            os.replace(tmp, f)
            return "got" if rows else "empty"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            if getattr(e, "code", None) in (401, 403):
                break
            time.sleep(2 * (attempt + 1))
    with _lock:
        _errors.append({"symbol": sym, "date": date, "err": last})
    return "fail"


def universe_pairs():
    out = []
    for f in sorted(UNI.glob("*.json")):
        d = f.stem
        for r in json.loads(f.read_text()):
            out.append([r["symbol"], d])
    return out


def probe():
    """Reproduce the entitlement finding."""
    import urllib.error
    import urllib.request
    k = massive._key()
    t0 = et_ms("2026-08-05", 9, 36) * 10**6
    tests = [
        ("/v3/quotes", f"https://api.polygon.io/v3/quotes/AAOI?"
                       f"timestamp.gte={t0-10**10}&timestamp.lte={t0+10**10}"
                       f"&limit=5&apiKey={k}"),
        ("/v3/trades", f"https://api.polygon.io/v3/trades/AAOI?"
                       f"timestamp.gte={t0}&timestamp.lte={t0+3*10**11}"
                       f"&limit=5&apiKey={k}"),
        ("/v2/last/nbbo", f"https://api.polygon.io/v2/last/nbbo/AAOI?apiKey={k}"),
        ("/v2/last/trade", f"https://api.polygon.io/v2/last/trade/AAOI?apiKey={k}"),
        ("/v2/ticks/nbbo", f"https://api.polygon.io/v2/ticks/stocks/nbbo/AAOI/"
                           f"2026-08-05?limit=2&apiKey={k}"),
        ("/v2/aggs 1-second", f"https://api.polygon.io/v2/aggs/ticker/AAOI/"
                              f"range/1/second/{et_ms('2026-08-05',9,30)}/"
                              f"{et_ms('2026-08-05',16,5)}?limit=50000"
                              f"&sort=asc&adjusted=true&apiKey={k}"),
        ("/v3/snapshot", f"https://api.polygon.io/v3/snapshot?ticker=AAOI"
                         f"&apiKey={k}"),
    ]
    rep = []
    for name, u in tests:
        try:
            with urllib.request.urlopen(u, timeout=40) as r:
                d = json.load(r)
            n = d.get("resultsCount")
            if n is None:
                n = len(d.get("results") or [])
            rep.append({"endpoint": name, "code": 200, "results": n})
        except urllib.error.HTTPError as e:
            rep.append({"endpoint": name, "code": e.code,
                        "body": e.read()[:200].decode("utf8", "replace")})
        except Exception as e:
            rep.append({"endpoint": name, "code": "ERR", "body": str(e)[:200]})
    print(json.dumps(rep, indent=1))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "entitlement_probe.json").write_text(json.dumps(rep, indent=1))


def main():
    argv = sys.argv[1:]
    if "--probe" in argv:
        probe()
        return
    XDIR.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for p in XDIR.glob("*.part"):
        p.unlink()
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv \
        else 40
    if "--pairs" in argv:
        pairs = json.loads(Path(argv[argv.index("--pairs") + 1]).read_text())
    else:
        pairs = universe_pairs()
    print(f"sec1 tape: {len(pairs):,} symbol-days, "
          f"{len(set(d for _, d in pairs)):,} dates", flush=True)
    todo = [(s, d) for s, d in pairs if not have(s, d)]
    print(f"already cached: {len(pairs)-len(todo):,}   to fetch: "
          f"{len(todo):,}", flush=True)
    if "--limit" in argv:
        todo = todo[:int(argv[argv.index("--limit") + 1])]
    if shutil.disk_usage(XDIR).free / 1e9 < MIN_FREE_GB:
        raise SystemExit("ABORT: low disk")
    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.monotonic()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch_one, s, d) for s, d in todo]
        for fu in as_completed(futs):
            r = fu.result()
            with _lock:
                _stats[r] = _stats.get(r, 0) + 1
                done += 1
                snap = dict(_stats)
            if done % 1000 == 0 or done == len(todo):
                el = time.monotonic() - t0
                rate = done / el if el else 0
                print(f"  [{done:,}/{len(todo):,}] {snap} {rate:.1f}/s "
                      f"eta {(len(todo)-done)/rate/60 if rate else 0:.0f}m",
                      flush=True)
    ERR_F.write_text(json.dumps(_errors[:5000], indent=1))
    nb = sum(f.stat().st_size for f in XDIR.glob("*.json.gz"))
    print(f"DONE in {(time.monotonic()-t0)/60:.1f}m: {_stats}; "
          f"cache {nb/1e9:.2f} GB", flush=True)


if __name__ == "__main__":
    main()
