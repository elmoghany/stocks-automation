"""Add symbols to a day's scan_state drop-list.

Written 2026-08-31 (Day 19). API HYGIENE #2: a halal FAIL is day-scoped and must
never re-enter the candidate pool. scan_sweep.py reads these lists but nothing
wrote to halal_fail during the session, so a name FAILed at 07:05 would keep
reappearing as a fresh candidate at 07:25.

Usage:
    python plan/state_fail.py <date> <list> SYM [SYM ...]
        <list> is one of: halal_fail | fake_gap | inherited_fail | cannot_verify | spac
"""
import json, sys
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "data" / "paper_days"
VALID = ("halal_fail", "fake_gap", "inherited_fail", "cannot_verify", "spac")


def main():
    date, lst, *syms = sys.argv[1:]
    if lst not in VALID:
        sys.exit(f"ERROR: list must be one of {VALID}")
    p = D / f"scan_state_{date}.json"
    st = json.load(open(p))
    added = []
    for s in (x.upper() for x in syms):
        if s not in st[lst]:
            st[lst].append(s)
            added.append(s)
    st[lst].sort()
    json.dump(st, open(p, "w"), indent=1)
    print(f"{lst}: added {added or 'nothing'} (now {len(st[lst])})")


if __name__ == "__main__":
    main()
