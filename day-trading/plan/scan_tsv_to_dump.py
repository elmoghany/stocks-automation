"""Convert a compact TSV transcription of a run_scan response into the dump JSON
that plan/scan_sweep.py expects.

Written 2026-08-31 (Day 19). The run_scan MCP response arrives INLINE when it is
small enough not to spill to a file, so there is no dump on disk to feed the
sweep. Rather than hand-parse 90 rows in conversation (the exact "ranking by
hand" failure mode the rank command exists to prevent), transcribe the rows into
a TSV once and let the mechanical path own everything downstream.

TSV columns, tab-separated, one row per scan result, no header:
    TICKER  NAME  PCT_CHANGE_RATIO  LAST  VOLUME

PCT_CHANGE_RATIO is the RAW ratio exactly as the scanner returns it (0.1358 =
+13.58%); scan_sweep.py multiplies by 100 itself.

Usage:
    python plan/scan_tsv_to_dump.py <in.tsv> <out.json>
"""
import json, sys
from pathlib import Path


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    rows = []
    for ln, raw in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) != 5:
            sys.exit(f"ERROR: line {ln} has {len(parts)} fields, expected 5: {raw!r}")
        sym, name, pct, last, vol = (p.strip() for p in parts)
        float(pct); float(last)  # fail loudly on a bad transcription
        rows.append({
            "ticker": sym.upper(),
            "instrument_type": "EQUITY",
            "columns": {
                "Symbol": sym.upper(), "Name": name,
                "% Change": pct, "Last": last, "Volume": vol,
            },
        })
    json.dump({"data": {"result": {"results": rows, "total_items": len(rows)}}},
              open(dst, "w"), indent=1)
    print(f"wrote {dst} with {len(rows)} rows")


if __name__ == "__main__":
    main()
