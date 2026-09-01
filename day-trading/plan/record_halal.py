"""Record the day's halal verdicts into scan_state_{date}.json.

Usage:
    python plan/record_halal.py DATE fail SYM [SYM ...]
    python plan/record_halal.py DATE cannot_verify SYM [SYM ...]
    python plan/record_halal.py DATE fake_gap SYM [SYM ...]
    python plan/record_halal.py DATE show

A FAIL written here is inherited by every later sweep of the same day
(API HYGIENE #2: a FAIL must never re-enter the candidate pool), and by
tomorrow's session via seed_scan_state.py.
"""
import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent
BUCKETS = {"fail": "halal_fail", "cannot_verify": "cannot_verify",
           "fake_gap": "fake_gap", "spac": "spac"}


def main():
    date, action, *syms = sys.argv[1:]
    p = DIR / "data" / "paper_days" / f"scan_state_{date}.json"
    st = json.load(open(p))

    if action == "show":
        for k in ("halal_fail", "cannot_verify", "fake_gap", "spac",
                  "inherited_fail"):
            v = st.get(k, [])
            print(f"{k:<16} [{len(v)}] {','.join(v)}")
        print(f"candidates       [{len(st.get('candidates', {}))}]")
        return 0

    key = BUCKETS.get(action)
    if not key:
        print(f"ERROR: unknown bucket '{action}' -- "
              f"use one of {sorted(BUCKETS)} or 'show'")
        return 1

    before = set(st.get(key, []))
    after = sorted(before | {s.upper() for s in syms})
    st[key] = after
    json.dump(st, open(p, "w"), indent=1)
    added = sorted(set(after) - before)
    print(f"{key}: +{len(added)} {added} -> now {len(after)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
