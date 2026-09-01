"""Build the day's ticker-name registry from every dump already written.

Usage:  python plan/seed_name_registry.py DATE

Names are immutable per ticker, so once a session has seen a ticker it never
needs to be told the name again -- but dump_from_delta only reads the single
base dump it is handed. This walks every scan_dump_{DATE}_*.json and unions
them into data/paper_days/ticker_names.json, which dump_from_delta then reads
and keeps updated.
"""
import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "paper_days"


def main():
    date = sys.argv[1]
    reg_p = DIR / "ticker_names.json"
    registry = {}
    if reg_p.exists():
        registry = json.load(open(reg_p, encoding="utf-8"))

    added = 0
    for p in sorted(DIR.glob(f"scan_dump_{date}_*.json")):
        raw = json.load(open(p, encoding="utf-8"))
        for r in raw["data"]["result"]["results"]:
            tk = r["ticker"].upper()
            nm = (r.get("columns") or {}).get("Name")
            if not nm:
                continue
            if tk not in registry:
                added += 1
            registry[tk] = {"name": nm,
                            "type": r.get("instrument_type", "EQUITY")}

    json.dump(registry, open(reg_p, "w"), indent=0, sort_keys=True)
    print(f"registry now holds {len(registry)} tickers (+{added} new) "
          f"-> {reg_p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
