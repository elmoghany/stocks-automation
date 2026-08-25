"""Convert data/rh_bars/{SYM}_{DATE}.csv (UTC timestamps) into the
paper_watch BARS_JSON shape: {"date": D, "bars": [{"t": ISO_ET, ...}]}.

Usage: python plan/csv_to_watchjson.py SYM DATE OUT_PATH [SINCE_UTC_HHMM]

SINCE filters bars to begins_at >= that UTC clock time -- REQUIRED for a
position watch: passing the whole day lets pre-entry bars trip the
resting stop (found live 2026-08-25, CRML false EXIT on the 04:00 bar).
"""
import csv, json, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

ET = ZoneInfo("America/New_York")
DIR = Path(__file__).resolve().parent.parent / "data" / "rh_bars"

def main():
    sym, date, out = sys.argv[1:4]
    since = sys.argv[4] if len(sys.argv) > 4 else None   # UTC HH:MM
    rows = list(csv.DictReader(open(DIR / f"{sym}_{date}.csv")))
    bars = []
    for r in rows:
        ts = r.get("begins_at") or r.get("timestamp")
        if since and ts[11:16] < since:
            continue
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(ET)
        bars.append({"t": dt.isoformat(), "o": float(r["open"]), "h": float(r["high"]),
                     "l": float(r["low"]), "c": float(r["close"]), "v": int(float(r["volume"]))})
    json.dump({"date": date, "bars": bars}, open(out, "w"))
    print(f"{sym}: {len(bars)} bars -> {out} (last {bars[-1]['t']} c {bars[-1]['c']})" if bars else "EMPTY")

if __name__ == "__main__":
    main()
