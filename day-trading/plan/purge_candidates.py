"""Remove candidates from a day's scan_state that were never genuinely seen.

Usage:  python plan/purge_candidates.py DATE SYM [SYM ...]

Written 2026-09-01 (Day 20) after a cross-day filename collision. The dump
files were named scan_dump_{HHMM}.json with no date in them, so a sweep whose
delta-build had FAILED (and therefore wrote nothing) silently re-swept the
PREVIOUS session's file of the same name and injected four of yesterday's
symbols into today's crossed set as "NEW".

The crossed set is a LATCH -- anything in it stays eligible all day -- so a
phantom entry is not self-correcting: it would have sat there until 14:30 as
a tradeable candidate whose +10% cross never printed today. Purging is the
honest repair; the collision itself is fixed by date-scoping the filenames.
"""
import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent


def main():
    date, *syms = sys.argv[1:]
    syms = {s.upper() for s in syms}
    p = DIR / "data" / "paper_days" / f"scan_state_{date}.json"
    st = json.load(open(p))
    cands = st.get("candidates", {})

    missing = syms - set(cands)
    removed = {}
    for s in syms & set(cands):
        removed[s] = cands.pop(s)

    st["candidates"] = cands
    notes = st.setdefault("_purged", [])
    notes.append({"purged": sorted(removed),
                  "reason": "cross-day scan_dump filename collision -- "
                            "these never crossed +10% today"})
    json.dump(st, open(p, "w"), indent=1)

    print(f"purged {len(removed)} phantom candidates: {sorted(removed)}")
    if missing:
        print(f"NOTE: not present, nothing to purge: {sorted(missing)}")
    print(f"candidates now [{len(cands)}]: {sorted(cands)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
