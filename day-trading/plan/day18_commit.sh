#!/bin/sh
# Stage ONLY this session's own files. Never `git add -A`, never a bare
# directory -- 2026-08-28 staged day-trading/data/paper_days/ and swept in a
# parallel campaign session's untracked files (undone in the next commit).
#
# git add is ATOMIC: one missing path aborts the whole batch and stages
# nothing. So every path is existence-checked and added individually.
# data/rh_bars is gitignored -- never staged.
#
# Usage: sh plan/day18_commit.sh "commit message"
set -e
cd /c/cornell/stocks-automation
D=day-trading

for f in \
  "$D/data/paper_days/2026-08-28.json" \
  "$D/data/paper_days/2026-08-28.md" \
  "$D/data/paper_days/scan_state_2026-08-28.json" \
  "$D/plan/quick_sweep.py" \
  "$D/plan/day18_commit.sh" \
  "$D/NOTES-DAYTRADING.md" \
  "$D"/data/paper_days/scan_2026-08-28_*.json \
  "$D"/data/paper_days/scan_2026-08-28_*.py
do
  [ -e "$f" ] && git add -- "$f"
done

git commit -q -m "$1"
git push -q origin main
git log --oneline -1
