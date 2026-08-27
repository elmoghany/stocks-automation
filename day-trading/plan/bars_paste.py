"""Append 1-min bars for SEVERAL symbols at once, read from stdin.

Usage:
    python plan/bars_paste.py <YYYY-MM-DD> [--stop SYM:LEVEL] [--after=UTC_ISO] < blob

Each stdin line:  SYM ts o h l c v      (whitespace separated, ts is UTC ISO)
Blank lines and lines starting with '#' are ignored.

Why this exists (Day 17, 2026-08-27): get_equity_historicals lands INLINE in the
agent's context rather than spilling, so a premarket sweep over 5 names at
1-minute granularity costs ~10k tokens per fetch. plan/append_bars.py takes one
symbol per process invocation, which multiplies the per-cycle overhead that the
Day-9 note already identified as the binding constraint. This takes every symbol
in one call, dedupes by timestamp, keeps time order, and reports per symbol:
bar count, last close, session high, and the trailing-10-completed-minute volume
that the 20% size cap needs -- so a ranking cycle does not need a second pass.

--stop SYM:LEVEL applies the intrabar resting-stop test (bar HIGH >= LEVEL for a
buy stop) and prints the first bar that would have filled, honouring --after so
pre-arm bars cannot falsely trip it.
"""
import csv
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "rh_bars"
HEADER = ["begins_at", "open", "high", "low", "close", "volume"]


def main():
    argv = sys.argv[1:]
    date = argv[0]
    stops, after = {}, ""
    for a in argv[1:]:
        if a.startswith("--after="):
            after = a.split("=", 1)[1]
        elif a == "--stop":
            continue
        elif ":" in a:
            s, lv = a.split(":", 1)
            stops[s.upper()] = float(lv)

    incoming = {}
    for raw in sys.stdin:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 7:
            print(f"ERROR: malformed line ({len(parts)} fields, want 7): {line[:80]}")
            continue
        sym, ts, o, h, lo, c, v = parts[0].upper(), *parts[1:]
        incoming.setdefault(sym, []).append([ts, o, h, lo, c, v])

    if not incoming:
        print("ERROR: no bars on stdin")
        return

    DIR.mkdir(parents=True, exist_ok=True)
    for sym, rows in sorted(incoming.items()):
        p = DIR / f"{sym}_{date}.csv"
        recs = {}
        if p.exists():
            with open(p, newline="") as f:
                for r in csv.DictReader(f):
                    recs[r["begins_at"]] = [r[k] for k in HEADER]
        added = 0
        for r in rows:
            if r[0] not in recs:
                added += 1
            recs[r[0]] = r
        ordered = [recs[k] for k in sorted(recs)]
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(HEADER)
            w.writerows(ordered)

        closes = [float(r[4]) for r in ordered]
        high = max(float(r[2]) for r in ordered)
        vols = [float(r[5]) for r in ordered]
        trail10 = sum(vols[-10:])
        print(f"{sym:<6} bars={len(ordered):<4} (+{added:<3}) last={closes[-1]:<10.4f} "
              f"high={high:<10.4f} trail10vol={trail10:,.0f} cap20%={trail10 * 0.2:,.0f}")

        if sym in stops:
            lv = stops[sym]
            hit = [r for r in ordered if float(r[2]) >= lv and (not after or r[0] > after)]
            if hit:
                print(f"  STOP {lv} WOULD FILL at {hit[0][0]} (bar high {hit[0][2]})")
            else:
                print(f"  stop {lv} not reached (max high {high:.4f})")


if __name__ == "__main__":
    main()
