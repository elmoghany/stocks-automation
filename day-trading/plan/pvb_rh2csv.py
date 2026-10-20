"""PAPER-VS-BT helper: convert a spilled Robinhood get_equity_historicals
result (JSON {data:{results:[{symbol, bars:[...]}]}}) into per-symbol,
per-date CSVs in the rh_bars format (begins_at,open,high,low,close,volume,
UTC). Interpolated bars (synthesized gap fillers) are dropped, as the live
ingest does. Existing files are merged (union by minute, new rows win).

    python plan/pvb_rh2csv.py OUTDIR SPILL.txt [SPILL2.txt ...]
"""
import csv
import json
import sys
from pathlib import Path


def convert(spill, outdir):
    d = json.loads(Path(spill).read_text(encoding="utf-8"))
    res = (d.get("data") or d).get("results") or []
    n = 0
    for r in res:
        sym = r["symbol"]
        by_date = {}
        for b in r.get("bars") or []:
            if b.get("interpolated"):
                continue
            ts = b["begins_at"]
            by_date.setdefault(ts[:10], {})[ts] = (
                b["open_price"], b["high_price"], b["low_price"],
                b["close_price"], b.get("volume") or 0)
        for date, rows in by_date.items():
            f = outdir / f"{sym}_{date}.csv"
            old = {}
            if f.exists():
                with open(f, newline="") as fh:
                    rd = csv.reader(fh)
                    next(rd, None)
                    for row in rd:
                        if len(row) >= 6:
                            old[row[0]] = tuple(row[1:6])
            old.update(rows)
            with open(f, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["begins_at", "open", "high", "low", "close",
                            "volume"])
                for ts in sorted(old):
                    w.writerow([ts, *old[ts]])
            n += 1
    return n


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    tot = 0
    for s in sys.argv[2:]:
        k = convert(s, out)
        tot += k
        print(f"{Path(s).name}: {k} sym-day files")
    print("total", tot)
