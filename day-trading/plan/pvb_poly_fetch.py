"""PAPER-VS-BT: Polygon (Massive) minute bars for a queue of symbol-days,
via shared/massive.minute_bars (massive._get, default 12.5 s pacing: the key
is at 5 req/min). Writes m1-format CSVs (UTC begins_at, Open..Volume) to
data/pvb/poly/{SYM}_{DATE}.csv, "EMPTY" when Polygon has no bars. The queue
file (data/pvb/poly_queue.json, list of [sym, date]) is re-read after every
call, so items can be appended while it runs; it exits when the queue is
drained and stays drained for 60 s.

    python plan/pvb_poly_fetch.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shared import massive as M                               # noqa: E402

DT = ROOT / "day-trading" / "data" / "pvb"
OUT = DT / "poly"
Q = DT / "poly_queue.json"


def pending():
    q = json.loads(Q.read_text()) if Q.exists() else []
    seen, out = set(), []
    for s, d in q:
        if (s, d) in seen:
            continue
        seen.add((s, d))
        if not (OUT / f"{s}_{d}.csv").exists():
            out.append((s, d))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    idle = 0
    n = 0
    while True:
        p = pending()
        if not p:
            idle += 1
            if idle > 6:
                break
            time.sleep(10)
            continue
        idle = 0
        s, d = p[0]
        try:
            df = M.minute_bars(s, d)
        except Exception as e:                              # noqa: BLE001
            print(f"{s} {d} FAIL {str(e)[:80]}", flush=True)
            (OUT / f"{s}_{d}.csv").write_text("EMPTY,FAIL\n")
            continue
        f = OUT / f"{s}_{d}.csv"
        if df is None or df.empty:
            f.write_text("EMPTY\n")
        else:
            df = df.copy()
            df.index = df.index.tz_convert("UTC")
            df.to_csv(f, index_label="begins_at")
        n += 1
        print(f"{n} {s} {d} {0 if df is None else len(df)} left {len(p) - 1}",
              flush=True)
    print("drained", n)


if __name__ == "__main__":
    main()
