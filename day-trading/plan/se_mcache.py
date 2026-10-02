"""SWING-EARNINGS step 4a: day-1 minute bars from the EXISTING caches
(no API calls) -- data/massive/m1o/{SYM}.npz (960-slot 04:00 grid),
data/massive/m1w/{SYM}_{D}.csv and data/massive/m1/{SYM}_{D}.csv (UTC
begins_at).  Output shard data/research_oct/se_m1/part_cache.npz in the
se_minute format (3 x 390: o, c, v over 09:30..15:59 ET).
"""
import csv
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "data" / "research_oct"
MS = ROOT / "data" / "massive"
ET = ZoneInfo("America/New_York")


def from_csv(f):
    txt = f.read_text()
    if txt.startswith("EMPTY"):
        return None
    a = np.full((3, 390), np.nan, np.float32)
    for row in csv.DictReader(txt.splitlines()):
        t = datetime.fromisoformat(row["begins_at"]).astimezone(ET)
        k = t.hour * 60 + t.minute - 570
        if 0 <= k < 390:
            a[0, k], a[1, k], a[2, k] = float(row["Open"]), float(row["Close"]), float(row["Volume"])
    return a


def main():
    ev = json.loads((OUT / "se_events.json").read_text())
    want = sorted({(e["sym"], e["day1"]) for e in ev})
    have = set()
    for f in (OUT / "se_m1").glob("part_*.npz"):
        if f.name != "part_cache.npz":
            have |= set(np.load(f)["keys"].tolist())
    out, src = {}, {"m1o": 0, "m1w": 0, "m1": 0, "none": 0}
    by_sym = {}
    for s, d in want:
        if f"{s}|{d}" not in have:
            by_sym.setdefault(s, []).append(d)
    for n_, (s, ds) in enumerate(by_sym.items()):
        if n_ % 200 == 0:
            print("  sym", n_, len(by_sym), src, flush=True)
        z = None
        f = MS / "m1o" / f"{s}.npz"
        if f.exists():
            try:
                zz = np.load(f)
                dd = {d: i for i, d in enumerate(zz["dates"].tolist())}
                if any(d in dd for d in ds):
                    z = (dd, {k: zz[k][:, 330:720] for k in ("o", "c", "v")})
                else:
                    z = (dd, None)
            except Exception:                                 # noqa: BLE001
                z = None
        for d in ds:
            a = None
            if z is not None and z[1] is not None and d in z[0]:
                i = z[0][d]
                zz = z[1]
                a = np.stack([zz["o"][i], zz["c"][i], zz["v"][i]]).astype(np.float32)
                src["m1o"] += 1
            else:
                for cache in ("m1w", "m1"):
                    p = MS / cache / f"{s}_{d}.csv"
                    if p.exists():
                        a = from_csv(p)
                        if a is not None:
                            src[cache] += 1
                            break
            if a is None:
                src["none"] += 1
                continue
            out[f"{s}|{d}"] = a
    (OUT / "se_m1").mkdir(exist_ok=True)
    keys = list(out)
    np.savez_compressed(OUT / "se_m1" / "part_cache.npz", keys=np.array(keys),
                        a=np.stack([out[k] for k in keys]))
    miss = sorted(f"{s}|{d}" for s, ds in by_sym.items() for d in ds if f"{s}|{d}" not in out)
    (OUT / "se_m1_missing.json").write_text(json.dumps(miss))
    print("sources", src, "wanted", len(want), "already fetched", len(have))
    sp = {}
    for k in miss:
        d = k.split("|")[1]
        y = "Y1" if d <= "2025-07-31" else ("Y2" if d <= "2026-07-31" else "OOS")
        sp[y] = sp.get(y, 0) + 1
    print("missing by split", sp)


if __name__ == "__main__":
    main()
