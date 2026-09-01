"""Seed a day's scan_state drop-lists from the prior session's verdicts.

Usage:  python plan/seed_scan_state.py PRIOR_DATE TODAY_DATE

A halal FAIL is never re-litigated (C37 protocol), so every prior FAIL --
same-day halal_fail, carried inherited_fail, and cannot_verify -- collapses
into today's inherited_fail. SPAC and fake-gap lists carry forward as-is.
Refuses to clobber an existing state file that already has candidates.
"""
import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent


def main():
    prior_date, today = sys.argv[1:3]
    d = DIR / "data" / "paper_days"
    pp = d / f"scan_state_{prior_date}.json"
    op = d / f"scan_state_{today}.json"

    if op.exists():
        cur = json.load(open(op))
        if cur.get("candidates"):
            print(f"ERROR: {op.name} already has "
                  f"{len(cur['candidates'])} candidates -- refusing to "
                  f"clobber a live state file")
            return 1

    prev = json.load(open(pp))
    inherited = sorted(set(prev.get("inherited_fail", []))
                       | set(prev.get("halal_fail", []))
                       | set(prev.get("cannot_verify", [])))
    state = {
        "candidates": {},
        "halal_fail": [],
        "fake_gap": sorted(set(prev.get("fake_gap", []))),
        "inherited_fail": inherited,
        "cannot_verify": [],
        "spac": sorted(set(prev.get("spac", []))),
        "_seed": f"seeded {today} from scan_state_{prior_date} "
                 f"(inherited_fail + halal_fail + cannot_verify)",
    }
    json.dump(state, open(op, "w"), indent=1)
    print(f"seeded inherited_fail={len(inherited)} "
          f"spac={len(state['spac'])} fake_gap={len(state['fake_gap'])} "
          f"-> {op.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
