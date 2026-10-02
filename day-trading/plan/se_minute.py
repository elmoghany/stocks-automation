"""SWING-EARNINGS step 4: day-1 regular-session 1-minute bars per event.

/v2/aggs/ticker/{sym}/range/1/minute/{day1}/{day1}?adjusted=true -> grid of
390 slots (09:30..15:59 ET); o, c, v float32, NaN where no print.
Shards: data/research_oct/m1/part_XXX.npz  (keys = "SYM|YYYY-MM-DD").
Resumable.  Paid tier: 8 threads, 0.03 s between request starts.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT.parent))
from shared import massive                                    # noqa: E402

massive._TH_INTERVAL = 1.0
OUT = ROOT / "data" / "research_oct"
M1 = OUT / "se_m1"
ET = ZoneInfo("America/New_York")


def fetch(sym, day):
    d = massive._get(f"{massive.BASE}/v2/aggs/ticker/{sym}/range/1/minute/{day}/{day}"
                     f"?adjusted=true&sort=asc&limit=50000&apiKey={massive._key()}")
    a = np.full((3, 390), np.nan, np.float32)
    for r in d.get("results") or []:
        t = datetime.fromtimestamp(r["t"] / 1000, ET)
        k = t.hour * 60 + t.minute - 570
        if 0 <= k < 390:
            a[0, k], a[1, k], a[2, k] = r["o"], r["c"], r["v"]
    return f"{sym}|{day}", a


def done_keys():
    s = set()
    for f in M1.glob("part_*.npz"):
        s |= set(np.load(f)["keys"].tolist())
    return s


def flush(buf):
    k = len(list(M1.glob("part_*.npz")))
    keys = list(buf)
    np.savez_compressed(M1 / f"part_{k:03d}.npz", keys=np.array(keys),
                        a=np.stack([buf[x] for x in keys]))


def main():
    M1.mkdir(parents=True, exist_ok=True)
    ev = json.loads((OUT / "se_events.json").read_text())
    have = done_keys()
    todo = sorted({(e["sym"], e["day1"]) for e in ev} - {tuple(k.split("|")) for k in have},
                  key=lambda x: (x[1], x[0]), reverse=True)   # newest (OOS) first
    if len(sys.argv) > 1:          # restrict to a key list (e.g. se_top600_missing.json)
        want = {tuple(k.split("|")) for k in json.loads(Path(sys.argv[1]).read_text())}
        todo = [x for x in todo if x in want]
    print(f"events {len(ev)}; cached {len(have)}; todo {len(todo)}", flush=True)
    buf, n = {}, 0
    with ThreadPoolExecutor(2) as ex:
        futs = [ex.submit(fetch, s, d) for s, d in todo]
        for fu in as_completed(futs):
            try:
                k, a = fu.result()
            except Exception as e:                            # noqa: BLE001
                print("ERR", str(e)[:120], flush=True)
                continue
            buf[k] = a
            n += 1
            if len(buf) >= 50:
                flush(buf)
                buf = {}
                print(f"  {n}/{len(todo)}", flush=True)
    if buf:
        flush(buf)
    print("DONE", n, flush=True)


if __name__ == "__main__":
    main()
