"""Append 1-min bars to data/rh_bars/{SYM}_{DATE}.csv from compact CLI args,
then report stop-trigger state for the paper resting order.

Usage:
    python plan/append_bars.py SYM DATE STOP ts:o:h:l:c:v [ts:o:h:l:c:v ...]

Each bar spec: ISO-ts:open:high:low:close:volume (ts may contain colons --
split from the RIGHT, 5 splits). Dedupes by timestamp, keeps time order.
Prints any bar whose HIGH >= STOP (intrabar fill signal) and the last close.
STOP=0 disables the fill check.
"""
import csv, sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "rh_bars"

def main():
    sym, date, stop, *specs = sys.argv[1:]
    after = ""
    if specs and specs[0].startswith("--after="):
        after = specs[0].split("=", 1)[1]
        specs = specs[1:]
    stop = float(stop)
    p = DIR / f"{sym}_{date}.csv"
    recs = {}
    if p.exists():
        for ln in p.read_text().splitlines()[1:]:
            if ln.strip():
                recs[ln.split(",")[0]] = ln
    n_new = 0
    for spec in specs:
        parts = spec.rsplit(":", 5)
        if len(parts) != 6:
            print(f"ERROR: bad bar spec {spec!r}")
            continue
        ts, o, h, l, c, v = parts
        if ts not in recs:
            n_new += 1
        recs[ts] = f"{ts},{o},{h},{l},{c},{int(float(v))}"
    with open(p, "w", newline="") as f:
        f.write("begins_at,open,high,low,close,volume\n")
        for ts in sorted(recs):
            f.write(recs[ts] + "\n")
    rows = [recs[ts].split(",") for ts in sorted(recs)]
    print(f"{sym}: {len(rows)} bars (+{n_new} new); last {rows[-1][0]} close {rows[-1][4]}")
    if stop > 0:
        hits = [r for r in rows if float(r[2]) >= stop and (not after or r[0] >= after)]
        if hits:
            first = hits[0]
            print(f"STOP-HIT: first bar with high>={stop}: {first[0]} high {first[2]} (fill at stop {stop})")
        else:
            eligible = [float(r[2]) for r in rows if (not after or r[0] >= after)]
            print(f"no stop hit post-arm (max high {max(eligible) if eligible else 0})")

if __name__ == "__main__":
    main()
