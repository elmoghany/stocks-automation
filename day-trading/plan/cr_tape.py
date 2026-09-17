"""COST-REBASE: extend the 1-second execution tape to the GAPPER pool.

plan/uq_sec1.py built `data/massive/trades/{SYM}_{DATE}.json.gz` for the
27,209 symbol-days of the causal WIDE universe. The gapper pool that
C37F / HOLD1 / the VS2 gapper configs trade on barely overlaps it
(4.5%), so a measured cost model cannot price those lines without
extending the cache. Same endpoint, same paid tier, resumable.

This module IMPORTS uq_sec1 and reuses its `fetch_one` verbatim; the
only thing it changes is that it does NOT delete other processes'
`*.part` files on startup (uq_sec1.main does, which makes a second
concurrent process kill the first), so several shards can run at once.
It also carries a PREMARKET mode for the liquidity-truth calibration,
which needs 07:00-09:30 where uq_sec1 only ever fetched 09:30-16:05.

Usage:
  python plan/cr_tape.py --pairs FILE [--workers 120] [--shard i/n]
  python plan/cr_tape.py --pm --pairs FILE     # 04:00-09:30 -> trades_pm
  python plan/cr_tape.py --plan                # what is still missing
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT.parent))

_spec = importlib.util.spec_from_file_location("uq_sec1", HERE / "uq_sec1.py")
S1 = importlib.util.module_from_spec(_spec)
sys.modules["uq_sec1"] = S1
_spec.loader.exec_module(S1)

OUT = HERE / "cr_out"
PMDIR = ROOT / "data" / "massive" / "trades_pm"


def run(pairs, workers=120, pm=False):
    if pm:
        # premarket window, separate cache dir -- never mixes with the
        # RTH tape uq_sec1 owns.
        S1.XDIR = PMDIR
        S1.FROM_HM = (4, 0)
        S1.TO_HM = (9, 30)
    S1.XDIR.mkdir(parents=True, exist_ok=True)
    todo = [(s, d) for s, d in pairs if not S1.have(s, d)]
    print(f"cr_tape: {len(pairs):,} pairs, {len(todo):,} to fetch "
          f"-> {S1.XDIR}", flush=True)
    if not todo:
        return
    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0 = time.monotonic()
    stats, done = {}, 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(S1.fetch_one, s, d) for s, d in todo]
        for fu in as_completed(futs):
            r = fu.result()
            stats[r] = stats.get(r, 0) + 1
            done += 1
            if done % 2000 == 0 or done == len(todo):
                el = time.monotonic() - t0
                rate = done / el if el else 0
                print(f"  [{done:,}/{len(todo):,}] {stats} {rate:.1f}/s "
                      f"eta {(len(todo)-done)/rate/60 if rate else 0:.0f}m",
                      flush=True)
    print(f"DONE {(time.monotonic()-t0)/60:.1f}m {stats}", flush=True)


def main():
    a = sys.argv[1:]
    pm = "--pm" in a
    workers = int(a[a.index("--workers") + 1]) if "--workers" in a else 120
    pairs = json.loads(Path(a[a.index("--pairs") + 1]).read_text())
    pairs = [tuple(p) for p in pairs]
    if "--shard" in a:
        i, n = (int(x) for x in a[a.index("--shard") + 1].split("/"))
        pairs = pairs[i::n]
    run(pairs, workers, pm)


if __name__ == "__main__":
    main()
