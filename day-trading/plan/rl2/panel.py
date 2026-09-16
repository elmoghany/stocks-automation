"""RL-SERIES v2 (2026-09-16): per-day minute tensors for the wide causal
universe.

INPUT   plan/rl2/out/universe/{D}.json    (causal membership, see universe.py)
        data/massive/m1w/{SYM}_{D}.csv    (1-min bars, UTC timestamps)
OUTPUT  plan/rl2/out/days/{D}.npz
          syms      (S,)     ticker strings, sorted
          prev_close(S,)     previous trading day's grouped-daily close
          o,h,l,c,v (S,960)  float32; NaN where the minute printed nothing
                             (v = 0). Minute grid is 04:00..19:59 ET,
                             index = ET minute-of-day - 240; the ET offset
                             is resolved once per day via zoneinfo, so DST
                             is handled.

Unlike v1 there is NO `onset` array and no eligibility gate inside the
day: membership was already decided by information complete before D
opened, so every name is visible for the whole session and premarket
entries are legal. Requirement (c) of the membership rule -- "had bars on
D" -- is enforced here: a symbol whose m1w file is the EMPTY sentinel, is
missing, or has no usable row on the grid is dropped and counted.
"""
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
M1W = ROOT / "data" / "massive" / "m1w"
M1 = ROOT / "data" / "massive" / "m1"
UNI = HERE / "out" / "universe"
DAYS = HERE / "out" / "days"
ET = ZoneInfo("America/New_York")

NMIN = 960
BASE_MIN = 4 * 60
RTH_LO = 9 * 60 + 30 - BASE_MIN       # 330  (09:30)
RTH_HI = 16 * 60 - BASE_MIN           # 720  (16:00)

_off = {}


def et_offset_min(date):
    if date not in _off:
        d = datetime.strptime(date, "%Y-%m-%d").replace(hour=12, tzinfo=ET)
        _off[date] = int(d.utcoffset().total_seconds() // 60)
    return _off[date]


def read_m1(sym, date):
    """(o,h,l,c,v) on the 960-slot ET grid, or None if no usable bar.

    Reads data/massive/m1w first, then data/massive/m1 (the gapper cache)
    so a run works even before the wide backfill has finished. Identical
    parsing to plan/rl/build_days.read_m1 -- UTC timestamps, a fixed
    per-day offset (the 04:00-20:00 ET window lies inside one UTC date),
    duplicate minutes keep the last row.
    """
    f = M1W / f"{sym}_{date}.csv"
    if not f.exists():
        f = M1 / f"{sym}_{date}.csv"
        if not f.exists():
            return None
    off = et_offset_min(date)
    o = np.full(NMIN, np.nan, np.float32)
    h = np.full(NMIN, np.nan, np.float32)
    lo = np.full(NMIN, np.nan, np.float32)
    c = np.full(NMIN, np.nan, np.float32)
    v = np.zeros(NMIN, np.float32)
    seen = False
    with open(f, newline="") as fh:
        rd = csv.reader(fh)
        hdr = next(rd, None)
        if hdr is None or (hdr and hdr[0].startswith("EMPTY")):
            return None
        for row in rd:
            if len(row) < 6:
                continue
            ts = row[0]
            if ts[:10] != date:
                continue
            try:
                k = int(ts[11:13]) * 60 + int(ts[14:16]) + off - BASE_MIN
            except ValueError:
                continue
            if not (0 <= k < NMIN):
                continue
            try:
                o[k] = float(row[1]); h[k] = float(row[2])
                lo[k] = float(row[3]); c[k] = float(row[4])
                v[k] = float(row[5])
            except ValueError:
                continue
            seen = True
    return (o, h, lo, c, v) if seen else None


def main():
    DAYS.mkdir(parents=True, exist_ok=True)
    files = sorted(UNI.glob("*.json"))
    st = {"dates": 0, "members": 0, "no_bars": 0, "written": 0, "empty": 0,
          "S": []}
    t0 = time.time()
    for i, f in enumerate(files):
        date = f.stem
        rows = json.loads(f.read_text())
        st["dates"] += 1
        st["members"] += len(rows)
        cand = []
        for r in sorted(rows, key=lambda r: r["symbol"]):
            b = read_m1(r["symbol"], date)
            if b is None:
                st["no_bars"] += 1
                continue
            cand.append((r["symbol"], float(r["prev_close"]), b))
        if not cand:
            st["empty"] += 1
            continue
        S = len(cand)
        st["S"].append(S)
        arr = {k: np.empty((S, NMIN), np.float32) for k in "ohlcv"}
        for j, (_s, _p, b) in enumerate(cand):
            for k, key in enumerate("ohlcv"):
                arr[key][j] = b[k]
        np.savez_compressed(
            DAYS / f"{date}.npz",
            syms=np.array([x[0] for x in cand]),
            prev_close=np.array([x[1] for x in cand], np.float32), **arr)
        st["written"] += 1
        if st["written"] % 50 == 0:
            el = time.time() - t0
            print(f"  [{i+1}/{len(files)}] {date} S={S} {el:.0f}s eta "
                  f"{el/(i+1)*(len(files)-i-1):.0f}s", flush=True)
    s = sorted(st.pop("S"))
    st.update(S_min=s[0], S_p50=s[len(s) // 2], S_p90=s[int(.9 * len(s))],
              S_max=s[-1], S_mean=round(sum(s) / len(s), 1))
    (HERE / "out" / "panel_stats.json").write_text(json.dumps(st, indent=1))
    print(json.dumps(st), flush=True)


if __name__ == "__main__":
    main()
