"""RL-SERIES v2 (2026-09-16): de-campaigned point-in-time shares backfill.

See plan/rl2/halal2.py for WHY. In one line: under nearest-earlier
semantics, `data/pt_shares` makes a symbol halal-EVALUABLE only after some
earlier (future-conditioned) campaign happened to query it, so the halal
universe silently collapses back onto "names that recently gapped". This
fetches `weighted_shares_outstanding` as of a FIXED MONTHLY ANCHOR GRID
for every symbol that survives the causal liquidity screen and carries a
sector/industry label, so membership depends on the screen and nothing
else.

  anchors   the first calendar day of each month from ANCHOR_FROM to
            ANCHOR_TO. A date D reads the most recent anchor <= D, i.e.
            at most ~31 days stale and never future.
  cache     plan/rl2/cache/shares/{SYM}_{YYYY-MM-DD}.json, a bare JSON
            number (or null for "Polygon has no row / no field"), the
            same format `penny_ax11b_massive.shares_asof` writes. Private
            directory: a concurrently-running halal job cannot be
            disturbed by this and vice versa.
  failures  a transport failure ({} from api()) is NEVER cached -- it
            would become a permanent silent FAIL. Only a real answer
            (including a 404) is written.

Resumable: an existing file is skipped. Usage:
  python plan/rl2/backfill_shares.py [--workers N] [--limit N]
"""
import json
import os
import sys
import threading
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(HERE))
from shared import massive                                    # noqa: E402

massive._TH_INTERVAL = float(os.environ.get("MASSIVE_TH_INTERVAL", "0.0"))

CACHE = HERE / "cache" / "shares"
ERR_F = HERE / "out" / "shares_errors.json"
ANCHOR_FROM = (2024, 8)
ANCHOR_TO = (2026, 9)

_lock = threading.Lock()
_stats = {"got": 0, "null": 0, "fail": 0}
_errors = []


def anchors():
    out = []
    y, mth = ANCHOR_FROM
    while (y, mth) <= ANCHOR_TO:
        out.append(date(y, mth, 1).isoformat())
        mth += 1
        if mth == 13:
            y, mth = y + 1, 1
    return out


def candidates():
    """Screen-surviving symbols that carry a sector/industry label.

    The label screen (`industry_clean` + `sector_clean`) is present-day
    and static, so running it here only avoids paying for share counts
    that the gate would refuse anyway -- it does not change any verdict.
    """
    import halal2
    m = halal2.load()
    syms = json.loads((HERE / "out" / "screen_syms.json").read_text())
    keep = [s for s in syms if m.industry_clean(s) and m.sector_clean(s)]
    return keep


def fetch_one(sym, d):
    f = CACHE / f"{sym}_{d}.json"
    if f.exists():
        return "skip"
    url = (f"https://api.polygon.io/v3/reference/tickers/{sym}"
           f"?date={d}&apiKey={massive._key()}")
    for attempt in range(3):
        try:
            r = massive._get(url)
        except Exception as e:
            code = getattr(e, "code", None)
            if code == 404:
                r = {"results": None}      # a real answer: no row that day
            else:
                if attempt == 2:
                    with _lock:
                        _errors.append({"symbol": sym, "date": d,
                                        "err": f"{type(e).__name__}: {e}"})
                    return "fail"
                time.sleep(1.5 * (attempt + 1))
                continue
        res = r.get("results") or {}
        sh = res.get("weighted_shares_outstanding") or \
            res.get("share_class_shares_outstanding")
        tmp = f.with_name(f"{f.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(sh))
        os.replace(tmp, f)
        return "got" if sh else "null"
    return "fail"


def main():
    workers = 40
    limit = None
    argv = sys.argv[1:]
    if "--workers" in argv:
        workers = int(argv[argv.index("--workers") + 1])
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    CACHE.mkdir(parents=True, exist_ok=True)
    for p in CACHE.glob("*.tmp"):
        p.unlink()
    syms = candidates()
    an = anchors()
    print(f"candidates: {len(syms):,} symbols x {len(an)} monthly anchors "
          f"= {len(syms)*len(an):,} lookups", flush=True)
    todo = [(s, d) for s in syms for d in an
            if not (CACHE / f"{s}_{d}.json").exists()]
    print(f"already cached: {len(syms)*len(an)-len(todo):,}   "
          f"to fetch: {len(todo):,}", flush=True)
    if limit:
        todo = todo[:limit]
    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.monotonic()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch_one, s, d) for s, d in todo]
        for fu in as_completed(futs):
            r = fu.result()
            with _lock:
                if r in _stats:
                    _stats[r] += 1
                done += 1
                snap = dict(_stats)
            if done % 2000 == 0 or done == len(todo):
                el = time.monotonic() - t0
                rate = done / el if el else 0
                print(f"  [{done:,}/{len(todo):,}] got={snap['got']:,} "
                      f"null={snap['null']:,} fail={snap['fail']:,} "
                      f"{rate:.1f}/s eta "
                      f"{(len(todo)-done)/rate/60 if rate else 0:.0f}m",
                      flush=True)
    ERR_F.parent.mkdir(parents=True, exist_ok=True)
    ERR_F.write_text(json.dumps(_errors[:2000], indent=1))
    print(f"DONE in {(time.monotonic()-t0)/60:.1f}m: got={_stats['got']:,} "
          f"null={_stats['null']:,} fail={_stats['fail']:,}", flush=True)


if __name__ == "__main__":
    main()
