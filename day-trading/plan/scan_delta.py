"""Build a run_scan dump from a BASE dump plus a small DELTA json, via
dump_from_delta.py (so every rule that script enforces still applies).

Written 2026-09-08 (Day 22): inline python spec-building inside a PowerShell
-c string broke on quote escaping, and a broken dump build silently skipped a
cycle's sweep. This moves the spec assembly into a file.

Usage:
    python plan/scan_delta.py BASE.json OUT.json DELTA.json

DELTA.json:
    {"changed": {"TK": [PCT_PERCENT, "LAST", "VOL"|"-"], ...},
     "new":     [["TK", PCT_PERCENT, "LAST", "VOL", "NAME"], ...],
     "gone":    ["TK", ...]}

Every ticker in BASE that is not in "gone" is carried with BASE values (or the
"changed" override). "new" rows must carry a NAME (dump_from_delta's rule).
"""
import json
import subprocess
import sys
from pathlib import Path


def main():
    base_p, out_p, delta_p = sys.argv[1:4]
    base = json.load(open(base_p, encoding="utf-8"))["data"]["result"]["results"]
    delta = json.load(open(delta_p, encoding="utf-8"))
    changed = delta.get("changed", {})
    gone = set(t.upper() for t in delta.get("gone", []))
    specs = []
    for r in base:
        tk = r["ticker"].upper()
        if tk in gone:
            continue
        c = r["columns"]
        if tk in changed:
            pct, last, vol = (list(changed[tk]) + ["-"])[:3]
            specs.append(f"{tk}:{pct}:{last}:{vol}")
        else:
            specs.append(f"{tk}:{float(c['% Change']) * 100!r}:{c['Last']}:-")
    for row in delta.get("new", []):
        tk, pct, last, vol, name = row
        specs.append(f"{tk}:{pct}:{last}:{vol}:{name}")
    here = Path(__file__).resolve().parent
    rc = subprocess.call([sys.executable, str(here / "dump_from_delta.py"), base_p, out_p] + specs)
    print(f"scan_delta: {len(specs)} specs, gone={sorted(gone) or 'none'}, rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
