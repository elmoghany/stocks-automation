"""CHAMPION-REPLAY: resumable minute-bar fetcher for the two coverage
holes the existing `data/massive/m1` cache still has.

HOLE A -- LISTING AGE. `plan/backfill_m1_full.py` fetched the union of
the two novol pools **with hist_n >= 50**, i.e. it silently dropped
every candidate with fewer than 50 prior grouped-daily sessions. Those
are recent listings -- precisely the names that print the +100% days
the champions' P&L is made of. 8.2k symbol-days, and the cut is a
COVERAGE cut, so it biases the pool the same way the full-day-gain cut
did before it was fixed.

HOLE B -- PREMARKET-ONLY CROSSERS. Pool membership is the grouped-daily
REGULAR-SESSION high >= +10%. A name whose PREMARKET last crosses +10%
and whose regular session never does is invisible to the pool and has
no bars anywhere on disk. The live scanner sees it. Every premarket
entry the C31..C37 family ever made was therefore drawn from a set
conditioned on the rest of the day. This job fetches the whole
scannable market on SAMPLED dates so the size and the economics of that
missing set can be measured instead of assumed.

Format contract: byte-identical to data/massive/m1 (UTC `begins_at`
index column, Open,High,Low,Close,Volume; "EMPTY" sentinel for
no-data). Files land in data/massive/m1c/ so nothing already published
can be perturbed. Atomic writes, resumable, permanent failures logged.

    python plan/cp_fetch.py --job A [--workers 32] [--limit N]
    python plan/cp_fetch.py --job B [--ndates 24] [--workers 32]
    python plan/cp_fetch.py --plan B --ndates 24      (count only)
"""

import gzip
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared import massive                                   # noqa: E402
import cp_prior as P                                         # noqa: E402

massive._TH_INTERVAL = 0.0            # paid tier, this process only

M1 = ROOT / "data/massive/m1"
M1C = ROOT / "data/massive/m1c"
ERR_F = ROOT / "data/massive/cp_fetch_errors.json"
RETRIES = 3
MIN_PREV_CLOSE = 1.82                 # a +10% cross must print >= $2
MIN_DVOL60 = 100_000.0                # prior-60-session median $ volume

_lock = threading.Lock()
_stats = {"got": 0, "empty": 0, "fail": 0}
_errors = []


def clean_ticker(sym):
    """penny_ax20_discover.clean_ticker, reproduced (same rule)."""
    if not sym or not sym.isalpha() or not sym.isupper():
        return False
    if len(sym) == 5 and sym.endswith(("W", "U", "R")):
        return False
    return len(sym) <= 5


_INDEX = {}


def _index(base):
    """One scandir per directory instead of a stat per symbol.

    On a loaded disk the per-symbol `Path.exists()` sweep over ~12k
    tickers x 12 dates costs minutes of pure IO wait; the listing costs
    one pass. Call `refresh_index()` after fetching more files."""
    key = str(base)
    if key not in _INDEX:
        s = set()
        try:
            with os.scandir(base) as it:
                for e in it:
                    if e.name.endswith(".csv"):
                        s.add(e.name[:-4])
        except FileNotFoundError:
            pass
        _INDEX[key] = s
    return _INDEX[key]


def refresh_index():
    _INDEX.clear()


def have(sym, date):
    k = f"{sym}_{date}"
    return k in _index(M1) or k in _index(M1C)


def job_a(labels=("year", "y2025", "aug2026")):
    """Pool symbol-days no backfill ever fetched.

    Two causes: listing age (`hist_n < 50`, which the 2026-08-21
    full-breadth backfill excluded) and the aug-2026 out-of-sample
    block, which that backfill predates entirely."""
    pairs = set()
    for lab in labels:
        f = ROOT / f"data/massive/gappers_novol_{lab}.json"
        if not f.exists():
            continue
        for c in json.loads(f.read_text()):
            pairs.add((c["symbol"], c["date"]))
    return sorted(p for p in pairs
                  if clean_ticker(p[0]) and not have(*p))


def sample_dates(n):
    """Evenly spaced trading dates across the whole study window."""
    ds = sorted(p.stem for p in (ROOT / "data/massive/cp_panel")
                .glob("[0-9]*.npz"))
    if not ds:
        ds = sorted(p.name.split(".")[0]
                    for p in (ROOT / "data/massive/gd").glob("*.json.gz"))
    step = max(1, len(ds) // n)
    return [ds[i] for i in range(0, len(ds), step)][:n]


def job_b(ndates):
    """Whole scannable market on sampled dates, minus what we have."""
    out = []
    for date in sample_dates(ndates):
        pr = P.load(date)
        if not pr:
            print(f"  {date}: no prior context, skipped", flush=True)
            continue
        rows = P.gd_rows(date)
        n = 0
        for r in rows:
            s = r.get("T")
            if not clean_ticker(s):
                continue
            e = pr.get(s)
            if not e:
                continue
            if (e.get("prevclose") or 0) < MIN_PREV_CLOSE:
                continue
            if (e.get("dvol60") or 0) < MIN_DVOL60:
                continue
            if (r.get("v") or 0) <= 0:
                continue
            if have(s, date):
                continue
            out.append((s, date))
            n += 1
        print(f"  {date}: {n} to fetch", flush=True)
    return out


def job_b_done_dates():
    """(symbol, date) pairs already fetched into m1c for a job-B date.

    A date counts as CENSUS-COMPLETE once its whole candidate list has
    been attempted; cp_premkt re-derives the list and checks presence,
    so this only has to report which dates were touched at all."""
    seen = set()
    for p in M1C.glob("*_*.csv"):
        sym, _, date = p.stem.rpartition("_")
        seen.add((sym, date))
    return seen


def fetch_one(args):
    sym, date = args
    f = M1C / f"{sym}_{date}.csv"
    last_err = None
    for attempt in range(RETRIES):
        try:
            df = massive.minute_bars(sym, date)
            if df is None or df.empty:
                f.write_text("EMPTY")
                with _lock:
                    _stats["empty"] += 1
                return "empty"
            out = df.reset_index()
            out["begins_at"] = out["begins_at"].dt.tz_convert("UTC")
            tmp = f.parent / (f.name + ".part")
            out.to_csv(tmp, index=False)
            for k in range(10):
                try:
                    os.replace(tmp, f)
                    break
                except PermissionError:
                    time.sleep(0.2 * (k + 1))
            with _lock:
                _stats["got"] += 1
            return "got"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            if getattr(e, "code", None) in (401, 403):
                break
            time.sleep(1.5 * (attempt + 1))
    with _lock:
        _stats["fail"] += 1
        _errors.append({"symbol": sym, "date": date, "err": last_err})
    return "fail"


def main():
    a = sys.argv[1:]

    def arg(flag, d=None):
        return a[a.index(flag) + 1] if flag in a else d
    job = (arg("--job") or arg("--plan") or "A").upper()
    ndates = int(arg("--ndates", 24))
    pairs = job_a() if job == "A" else job_b(ndates)
    print(f"job {job}: {len(pairs):,} symbol-days to fetch", flush=True)
    if "--plan" in a:
        return
    lim = arg("--limit")
    if lim:
        pairs = pairs[:int(lim)]
    M1C.mkdir(parents=True, exist_ok=True)
    workers = int(arg("--workers", 32))
    from concurrent.futures import ThreadPoolExecutor
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for _ in ex.map(fetch_one, pairs):
            done += 1
            if done % 500 == 0:
                el = time.time() - t0
                print(f"  {done}/{len(pairs)} {done/el:.1f}/s "
                      f"eta {(len(pairs)-done)/max(done/el,.01)/60:.0f}m "
                      f"{_stats}", flush=True)
    ERR_F.write_text(json.dumps(_errors))
    print(f"done {_stats} in {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
