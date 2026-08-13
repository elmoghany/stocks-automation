"""Ingest an MCP get_equity_historicals tool-result dump into data/rh_bars/{SYM}_{DATE}.csv

Usage:
    python plan/rh_bars_ingest.py <dump.json> <YYYY-MM-DD> SYM SYM ...

Asserts the returned symbol set equals the requested set (get_equity_historicals
silently truncates at 10 symbols -- API HYGIENE defect #1). Skips interpolated
bars. Merges with any bars already cached for the day.
"""
import json, sys, os
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent
OUT = DIR / "data" / "rh_bars"


def main():
    dump, date, *req = sys.argv[1:]
    req_set = {s.upper() for s in req}
    raw = json.load(open(dump, encoding="utf-8"))
    res = raw.get("data", raw).get("results", [])

    got = {}
    for entry in res:
        sym = (entry.get("symbol") or entry.get("Symbol") or "").upper()
        rows = entry.get("historicals") or entry.get("bars") or entry.get("data") or []
        if sym:
            got[sym] = rows

    missing = req_set - set(got)
    extra = set(got) - req_set
    if missing:
        print(f"ERROR: get_equity_historicals TRUNCATED -- missing {sorted(missing)}")
    if extra:
        print(f"ERROR: unexpected symbols returned {sorted(extra)}")

    OUT.mkdir(parents=True, exist_ok=True)
    for sym, rows in sorted(got.items()):
        recs = {}
        p = OUT / f"{sym}_{date}.csv"
        if p.exists():
            for ln in p.read_text().splitlines()[1:]:
                if ln.strip():
                    recs[ln.split(",")[0]] = ln
        n_new = n_interp = 0
        for b in rows:
            if b.get("interpolated"):
                n_interp += 1
                continue
            t = b.get("begins_at") or b.get("timestamp")
            if not t or not t.startswith(date):
                continue
            ln = "%s,%s,%s,%s,%s,%s" % (
                t, b.get("open_price", b.get("open")), b.get("high_price", b.get("high")),
                b.get("low_price", b.get("low")), b.get("close_price", b.get("close")),
                int(float(b.get("volume", 0))))
            if t not in recs:
                n_new += 1
            recs[t] = ln
        with open(p, "w") as f:
            f.write("begins_at,open,high,low,close,volume\n")
            for t in sorted(recs):
                f.write(recs[t] + "\n")
        print(f"  {sym:6} {len(recs):4} bars total (+{n_new} new, {n_interp} interpolated skipped)")

    print("OK" if not missing and not extra else "SYMBOL-SET MISMATCH -- see ERROR above")


if __name__ == "__main__":
    main()
