"""Thin wrapper over scan_sweep.py for the headless session.

Lets the coordinator feed only the NON-FUND rows it already read out of a
run_scan response, as compact tuples, instead of re-serialising all 60 rows.
Fund rows are dropped by name upstream anyway, so passing them costs tokens
for no decision value; pass the dropped count through --funds so the ledger
still records it.

Usage:
  python plan/quick_sweep.py DATE HH:MM --funds N -- SYM:PCT:LAST:VOL:Name ...
    PCT is the RATIO exactly as RH returns it (0.1382 == +13.82%).
"""
import json, subprocess, sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent


def main():
    date, hhmm = sys.argv[1], sys.argv[2]
    rest = sys.argv[3:]
    funds = 0
    if "--funds" in rest:
        i = rest.index("--funds")
        funds = int(rest[i + 1])
        rest = rest[:i] + rest[i + 2:]
    if rest and rest[0] == "--":
        rest = rest[1:]

    rows = []
    for spec in rest:
        sym, pct, last, vol, name = spec.split(":", 4)
        rows.append({
            "ticker": sym.upper(), "instrument_type": "EQUITY",
            "columns": {"% Change": pct, "Last": last, "Name": name,
                        "Volume": vol, "Symbol": sym.upper()},
        })

    dump = DIR / "data" / "paper_days" / f"scan_{date}_{hhmm.replace(':', '')}.json"
    json.dump({"data": {"result": {"total_items": len(rows) + funds,
                                   "results": rows}}}, open(dump, "w"), indent=0)
    print(f"[funds dropped upstream by coordinator: {funds}]")
    subprocess.run([sys.executable, str(DIR / "plan" / "scan_sweep.py"),
                    str(dump), date, hhmm], check=True)


if __name__ == "__main__":
    main()
