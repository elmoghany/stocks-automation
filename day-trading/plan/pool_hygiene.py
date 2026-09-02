"""POOL HYGIENE (2026-09-01) -- drop non-securities and split artifacts
from the rotation candidate pool.

AUDIT (read-only, 2026-09-01): the novol pool carries 287 rows whose
symbol is a NASDAQ test symbol (^Z[A-Z]ZZT$: ZVZZT, ZWZZT, ...) and 45
gain>=250% rows whose FIRST bar opens more than 3x the recorded
prev_close -- reverse-split / relisting artifacts, not moves (WW 156x,
DTC 120x, AIM 63x, WOLF 15x, CYCC 17x). A hold-to-flatten ticket on a
row like that books a fictitious gain against a stale prev_close.

Three filters, applied inside rotation_sim.day_candidates behind env
POOL_HYGIENE=1 (DEFAULT OFF so C37F reproduces -72,673 EXACT with it
off):
  1. symbol matches ^Z[A-Z]ZZT$                      -> drop (test symbol)
  2. first bar Open / prev_close outside [0.5, 2.0]  -> drop (split/relist)
  3. Massive reference type not in {CS, ADRC}        -> drop (ETF, warrant,
     unit, right, preferred, fund ...). Type is fetched once per symbol
     via shared.massive.ticker_details and cached in
     data/massive/ticker_types.json; a symbol the reference endpoint
     does not know is KEPT (unknown != non-equity) and cached as "?".

Every drop is logged with its ratio/type to
data/massive/pool_hygiene_dropped[_{ROTSHARD}].json (per-shard files so
parallel runs never clobber each other; merge with `--merge`).
"""

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))

TEST_RE = re.compile(r"^Z[A-Z]ZZT$")
RATIO_LO, RATIO_HI = 0.5, 2.0
KEEP_TYPES = {"CS", "ADRC"}
TYPES_F = ROOT / "data/massive/ticker_types.json"
_SHARD = os.environ.get("ROTSHARD", "")
DROP_F = ROOT / ("data/massive/pool_hygiene_dropped"
                 f"{'_' + _SHARD if _SHARD else ''}.json")

_types = None
_types_dirty = 0
_drops = []
_drop_keys = set()


def _load_types():
    global _types
    if _types is None:
        try:
            _types = json.loads(TYPES_F.read_text()) if TYPES_F.exists() \
                else {}
        except Exception:
            _types = {}
    return _types


def _save_types():
    """Merge-on-write: re-read siblings' additions, then atomic replace."""
    global _types_dirty
    cur = {}
    try:
        if TYPES_F.exists():
            cur = json.loads(TYPES_F.read_text())
    except Exception:
        cur = {}
    cur.update(_types)
    tmp = TYPES_F.with_name(f"{TYPES_F.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(cur, sort_keys=True))
    _replace_retry(tmp, TYPES_F)
    _types_dirty = 0


def _replace_retry(tmp, dst, tries=6):
    """Windows: os.replace fails with WinError 5 while a sibling process
    has `dst` open for reading. Retry briefly; on persistent failure
    drop the temp file and keep going -- the cache is an accelerator,
    losing one flush costs a refetch, never a wrong number."""
    for i in range(tries):
        try:
            os.replace(tmp, dst)
            return True
        except PermissionError:
            time.sleep(0.2 * (i + 1))
    try:
        tmp.unlink()
    except OSError:
        pass
    print(f"  hygiene: could not replace {dst.name} (busy); skipped",
          flush=True)
    return False


def ticker_type(sym, date=None):
    """Massive reference `type` for sym ("CS", "ADRC", "ETF", "WARRANT",
    ...); "?" when the reference endpoint has no row. Cached forever
    per symbol (type is a property of the listing, not of the day).
    A delisted symbol has no CURRENT row (404), so on a miss the as-of
    `date` is tried before giving up with "?"."""
    global _types_dirty
    t = _load_types()
    if sym in t:
        return t[sym]
    from shared import massive
    try:
        d = massive.ticker_details(sym)
        if not d and date:
            d = massive.ticker_details(sym, date)
        typ = (d.get("type") or "?") if d else "?"
    except Exception as e:                       # transport: do NOT cache
        print(f"  hygiene: type lookup failed {sym}: {e}", flush=True)
        return None
    t[sym] = typ
    _types_dirty += 1
    if _types_dirty >= 25:
        _save_types()
    return typ


def _log_drop(date, sym, why, **extra):
    k = (date, sym, why)
    if k in _drop_keys:
        return
    _drop_keys.add(k)
    _drops.append({"date": date, "symbol": sym, "why": why, **extra})
    if len(_drops) % 50 == 0:
        flush()


def flush():
    if _types_dirty:
        _save_types()
    if _drops:
        tmp = DROP_F.with_name(f"{DROP_F.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(_drops, indent=0))
        _replace_retry(tmp, DROP_F)


import atexit
atexit.register(flush)


def clean(cands, date):
    """Filter rotation_sim.day_candidates rows (dicts with "c", "df",
    "pc"). Returns the kept rows in the same order."""
    kept = []
    for r in cands:
        sym = r["c"]["symbol"]
        if TEST_RE.match(sym):
            _log_drop(date, sym, "test-symbol")
            continue
        pc = r.get("pc") or r["c"].get("prev_close") or 0
        df = r.get("df")
        if df is not None and len(df) and pc > 0:
            o = float(df["Open"].iloc[0])
            ratio = o / pc
            if not (RATIO_LO <= ratio <= RATIO_HI):
                _log_drop(date, sym, "first-open/prev_close",
                          ratio=round(ratio, 3), first_open=o, prev_close=pc,
                          first_bar=str(df.index[0]))
                continue
        typ = ticker_type(sym, date)
        if typ is not None and typ != "?" and typ not in KEEP_TYPES:
            _log_drop(date, sym, "type", type=typ)
            continue
        kept.append(r)
    return kept


def merge():
    """Merge every per-shard drop log into pool_hygiene_dropped.json."""
    base = ROOT / "data/massive/pool_hygiene_dropped.json"
    seen = {}
    for f in sorted((ROOT / "data/massive").glob(
            "pool_hygiene_dropped*.json")):
        try:
            for d in json.loads(f.read_text()):
                seen[(d["date"], d["symbol"], d["why"])] = d
        except Exception:
            pass
    rows = sorted(seen.values(), key=lambda d: (d["date"], d["symbol"]))
    base.write_text(json.dumps(rows, indent=0))
    from collections import Counter
    print(f"merged {len(rows)} drops -> {base.name}: "
          f"{dict(Counter(d['why'] for d in rows))}")
    return rows


if __name__ == "__main__":
    if "--merge" in sys.argv:
        merge()
    else:
        print(__doc__)
