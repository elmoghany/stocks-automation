"""RL-SERIES v2 (2026-09-16): 1-minute bar backfill for the WIDE causal
universe -> data/massive/m1w/.

Input   plan/rl2/out/universe/{D}.json  (plan/rl2/universe.py --stage halal)
Output  data/massive/m1w/{SYM}_{D}.csv  04:00-20:00 ET, UTC timestamps,
        columns begins_at,Open,High,Low,Close,Volume -- byte-compatible
        with data/massive/m1, so either cache can be read by the same
        loader. A day Polygon has nothing for gets the 5-byte "EMPTY"
        sentinel, whose EXISTENCE still marks "already fetched".

Format, resumability, atomic writes, the EMPTY sentinel and the loud
permanent-failure file are all the pattern of plan/backfill_m1_full.py,
reused deliberately so the two caches cannot drift.

REUSE: ~40% of the wide universe's symbol-days already sit in
data/massive/m1 from the gapper campaigns. Those are HARD-LINKED (falling
back to a copy) rather than refetched -- the bytes are identical and the
API call is pure waste. `--no-reuse` disables it.

Usage:
  python plan/rl2/backfill_m1w.py [--workers 40] [--limit N] [--no-reuse]
"""
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT.parent))
from shared import massive                                    # noqa: E402

massive._TH_INTERVAL = float(os.environ.get("MASSIVE_TH_INTERVAL", "0.0"))

M1 = ROOT / "data" / "massive" / "m1"
M1W = ROOT / "data" / "massive" / "m1w"
UNI = HERE / "out" / "universe"
ERR_F = HERE / "out" / "m1w_errors.json"
MIN_FREE_GB = 8
RETRIES = 3

_lock = threading.Lock()
_stats = {"got": 0, "empty": 0, "link": 0, "fail": 0}
_errors = []


def pairs():
    out = []
    for f in sorted(UNI.glob("*.json")):
        d = f.stem
        for r in json.loads(f.read_text()):
            out.append((r["symbol"], d))
    return out


def free_gb():
    return shutil.disk_usage(M1W).free / 1e9


def fetch_one(sym, date, reuse=True):
    f = M1W / f"{sym}_{date}.csv"
    if reuse:
        src = M1 / f"{sym}_{date}.csv"
        if src.exists() and src.stat().st_size > 0:
            try:
                os.link(src, f)
            except OSError:
                shutil.copyfile(src, f)
            return "link"
    last_err = None
    for attempt in range(RETRIES):
        try:
            df = massive.minute_bars(sym, date)
            if df is None or df.empty:
                f.write_text("EMPTY")
                return "empty"
            out = df.reset_index()
            out["begins_at"] = out["begins_at"].dt.tz_convert("UTC")
            tmp = f.parent / f"{f.name}.{os.getpid()}.{threading.get_ident()}.part"
            out.to_csv(tmp, index=False)
            os.replace(tmp, f)
            return "got"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            if getattr(e, "code", None) in (401, 403):
                break
            time.sleep(2 * (attempt + 1))
    with _lock:
        _errors.append({"symbol": sym, "date": date, "err": last_err})
    return "fail"


def main():
    workers, limit, reuse = 40, None, True
    argv = sys.argv[1:]
    if "--workers" in argv:
        workers = int(argv[argv.index("--workers") + 1])
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    if "--no-reuse" in argv:
        reuse = False
    M1W.mkdir(parents=True, exist_ok=True)
    for p in M1W.glob("*.part"):
        p.unlink()
    pr = pairs()
    print(f"wide universe: {len(pr):,} symbol-days over "
          f"{len(set(d for _, d in pr)):,} dates, "
          f"{len(set(s for s, _ in pr)):,} distinct symbols", flush=True)
    todo = [(s, d) for s, d in pr
            if not ((M1W / f"{s}_{d}.csv").exists()
                    and (M1W / f"{s}_{d}.csv").stat().st_size > 0)]
    print(f"already cached: {len(pr)-len(todo):,}   to fetch: {len(todo):,}",
          flush=True)
    if limit:
        todo = todo[:limit]
    if free_gb() < MIN_FREE_GB:
        raise SystemExit(f"ABORT: only {free_gb():.1f} GB free")
    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.monotonic()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch_one, s, d, reuse) for s, d in todo]
        for fu in as_completed(futs):
            r = fu.result()
            with _lock:
                _stats[r] += 1
                done += 1
                snap = dict(_stats)
            if done % 2000 == 0 or done == len(todo):
                el = time.monotonic() - t0
                rate = done / el if el else 0
                print(f"  [{done:,}/{len(todo):,}] got={snap['got']:,} "
                      f"link={snap['link']:,} empty={snap['empty']:,} "
                      f"fail={snap['fail']:,} {rate:.1f}/s eta "
                      f"{(len(todo)-done)/rate/60 if rate else 0:.0f}m",
                      flush=True)
    ERR_F.write_text(json.dumps(_errors[:5000], indent=1))
    nb = sum(f.stat().st_size for f in M1W.glob("*.csv"))
    print(f"DONE in {(time.monotonic()-t0)/60:.1f}m: got={_stats['got']:,} "
          f"link={_stats['link']:,} empty={_stats['empty']:,} "
          f"fail={_stats['fail']:,}; cache {nb/1e9:.2f} GB", flush=True)


if __name__ == "__main__":
    main()
