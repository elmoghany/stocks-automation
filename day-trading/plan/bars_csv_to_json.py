"""Convert a cached data/rh_bars/{SYM}_{DATE}.csv into the bars JSON that
paper_watch.py expects.

Usage:  python plan/bars_csv_to_json.py SYM DATE OUT.json

Written on Paper Day 9. The session agent already keeps
data/rh_bars/{SYM}_{DATE}.csv current via plan/rh_bars_ingest.py (which
asserts the API returned every symbol it was asked for and drops
interpolated bars). paper_watch wants the same bars as
{"date":..., "bars":[{"t": ISO8601_ET, "o","h","l","c","v"}]}, so this
just re-shapes the authoritative cache rather than introducing a second,
unchecked path to the same data.
"""
import csv
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

DIR = Path(__file__).resolve().parent.parent
ET = timezone(timedelta(hours=-4))          # EDT; session is 2026-08-14


def main():
    sym, date, out = sys.argv[1].upper(), sys.argv[2], sys.argv[3]
    src = DIR / "data" / "rh_bars" / f"{sym}_{date}.csv"
    bars = []
    with open(src, newline="") as f:
        for r in csv.DictReader(f):
            t = datetime.fromisoformat(
                r["begins_at"].replace("Z", "+00:00")).astimezone(ET)
            bars.append({"t": t.isoformat(), "o": float(r["open"]),
                         "h": float(r["high"]), "l": float(r["low"]),
                         "c": float(r["close"]), "v": float(r["volume"])})
    bars.sort(key=lambda b: b["t"])
    Path(out).write_text(json.dumps({"date": date, "bars": bars}))
    print(f"{sym}: {len(bars)} bars -> {out}"
          + (f"  last {bars[-1]['t'][11:16]} c={bars[-1]['c']}" if bars else ""))


if __name__ == "__main__":
    main()
