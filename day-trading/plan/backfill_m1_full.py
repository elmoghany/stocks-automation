"""W-campaign Phase 0.1: FULL-BREADTH minute-bar backfill.

Fetches 1-minute bars for EVERY (symbol, date) in the union of
gappers_novol_year.json + gappers_novol_y2025.json with hist_n >= 50
-- the whole candidate universe, not a gain-ranked slice. This is the
fix for the manifest's `bar-coverage-by-full-day-gain` bias: until now
bars existed only for ~17 of ~213 candidates/day, and that subset was
selected by FULL-DAY gain, i.e. with hindsight.

Requires the PAID Polygon tier (no hard rate limit). The module-level
throttle in shared.massive is neutralized IN THIS PROCESS ONLY; every
other consumer keeps the conservative 12.5s pacing.

Format contract: byte-identical to the existing cache. The CSV writer
is the same pandas pipeline as penny_ax20_backfill.fetch_m1 (UTC
begins_at index col, columns Open,High,Low,Close,Volume); days where
Massive has nothing get the "EMPTY" sentinel the loaders recognize
(bars_for/get treat a file starting with "EMPTY" as no-data; its
EXISTENCE still marks "already fetched" for resumability).

Resumable: existing non-empty files are skipped (both real bars and
EMPTY sentinels). Writes are atomic (tmp + os.replace) so a killed run
never leaves a half-written CSV that a loader would misparse.

Permanent failures land LOUDLY in data/massive/backfill_errors.json.

Usage: python plan/backfill_m1_full.py [--workers N] [--limit N]
"""

import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))
from shared import massive

# Paid tier (verified 2026-08-20: 8 calls in 5.4s, zero 429s). This
# process only -- the module default stays 12.5s for everyone else.
massive._TH_INTERVAL = 0.0

M1 = ROOT / "data/massive/m1"
ERR_F = ROOT / "data/massive/backfill_errors.json"
MIN_FREE_GB = 10
RETRIES = 3

_lock = threading.Lock()
_stats = {"got": 0, "empty": 0, "fail": 0}
_errors = []


def universe():
    """Union of (symbol, date) over both novol pools, hist_n >= 50."""
    pairs = set()
    for lab in ("year", "y2025"):
        g = json.loads(
            (ROOT / f"data/massive/gappers_novol_{lab}.json").read_text())
        for c in g:
            if c.get("hist_n", 99) >= 50:
                pairs.add((c["symbol"], c["date"]))
    return sorted(pairs)


def free_gb():
    return shutil.disk_usage(M1).free / 1e9


def fetch_one(sym, date):
    f = M1 / f"{sym}_{date}.csv"
    last_err = None
    for attempt in range(RETRIES):
        try:
            df = massive.minute_bars(sym, date)
            if df is None or df.empty:
                f.write_text("EMPTY")
                return "empty"
            out = df.reset_index()
            out["begins_at"] = out["begins_at"].dt.tz_convert("UTC")
            tmp = f.parent / (f.name + ".part")
            out.to_csv(tmp, index=False)
            os.replace(tmp, f)
            return "got"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            code = getattr(e, "code", None)
            if code in (401, 403):
                break                     # entitlement -- retrying is noise
            time.sleep(2 * (attempt + 1))
    with _lock:
        _errors.append({"symbol": sym, "date": date, "err": last_err})
    print(f"  !! PERMANENT FAIL {sym} {date}: {last_err}", flush=True)
    return "fail"


def main():
    workers, limit = 40, None
    argv = sys.argv[1:]
    if "--workers" in argv:
        workers = int(argv[argv.index("--workers") + 1])
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])

    pairs = universe()
    print(f"universe: {len(pairs):,} symbol-days (hist_n>=50, union of "
          f"gappers_novol_year + gappers_novol_y2025)", flush=True)
    bad = [s for s, _ in pairs
           if not all(ch.isalnum() or ch in ".-" for ch in s)]
    if bad:
        print(f"  {len(bad)} path-unsafe symbols skipped: "
              f"{sorted(set(bad))[:10]}", flush=True)
        pairs = [(s, d) for s, d in pairs
                 if all(ch.isalnum() or ch in ".-" for ch in s)]

    # resumability: an existing non-empty file (bars OR the 5-byte
    # EMPTY sentinel) means "already fetched"; zero-byte files are
    # corrupt interrupted writes and get refetched.
    for p in M1.glob("*.part"):
        p.unlink()
    todo = [(s, d) for s, d in pairs
            if not ((M1 / f"{s}_{d}.csv").exists()
                    and (M1 / f"{s}_{d}.csv").stat().st_size > 0)]
    print(f"already cached: {len(pairs) - len(todo):,}   "
          f"to fetch: {len(todo):,}", flush=True)
    if limit:
        todo = todo[:limit]
        print(f"--limit {limit}: fetching first {len(todo):,}", flush=True)

    if free_gb() < MIN_FREE_GB:
        print(f"ABORT: only {free_gb():.1f} GB free (< {MIN_FREE_GB} GB). "
              f"Clear disk before the ~3 GB backfill.", flush=True)
        sys.exit(1)
    print(f"disk: {free_gb():.1f} GB free -- ok. {workers} workers.",
          flush=True)

    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.monotonic()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_one, s, d): (s, d) for s, d in todo}
        for fu in as_completed(futs):
            r = fu.result()
            with _lock:
                _stats[r] += 1
                done += 1
                snap = dict(_stats)
            if done % 500 == 0 or done == len(todo):
                el = time.monotonic() - t0
                rate = done / el if el else 0
                eta = (len(todo) - done) / rate / 60 if rate else 0
                print(f"  [{done:,}/{len(todo):,}] got={snap['got']:,} "
                      f"empty={snap['empty']:,} fail={snap['fail']:,} "
                      f"{rate:.1f}/s eta {eta:.0f}m", flush=True)
                with _lock:
                    ERR_F.write_text(json.dumps(_errors, indent=1))
            if done % 5000 == 0 and free_gb() < MIN_FREE_GB:
                print(f"ABORT MID-RUN: disk fell below {MIN_FREE_GB} GB "
                      f"free. Resumable -- rerun after clearing space.",
                      flush=True)
                for f2 in futs:
                    f2.cancel()
                break
    ERR_F.write_text(json.dumps(_errors, indent=1))
    el = time.monotonic() - t0
    print(f"DONE in {el/60:.1f}m: got={_stats['got']:,} "
          f"empty={_stats['empty']:,} fail={_stats['fail']:,} "
          f"(errors -> {ERR_F.name})", flush=True)


if __name__ == "__main__":
    main()
