"""Backfill 1-minute bars for the W-pool (no-volume-filter discovery).

The W-experiments walk the top-8 by gain per day of the novol pool
(hist_n >= 50, same as load_by_day's default). 3,083 of those 3,549
symbol-days are already cached from the old pool; this fetches the
466 the old scanner's rvol filter hid (~1.6h at the key's 5 req/min).

Reuses fetch_m1 from penny_ax20_backfill.py so the CSV format is
byte-identical to the existing cache (UTC begins_at, EMPTY sentinel
for no-data days -- the sentinel matters: it distinguishes "Massive
has nothing" from "never fetched", so re-runs skip both).

Run with a deeper --walk N if the sim's walk ever exhausts 8.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location(
    "ax20b", ROOT / "plan" / "penny_ax20_backfill.py")
ax20b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ax20b)

M1 = ROOT / "data/massive/m1"


def main():
    walk = 8
    for i, a in enumerate(sys.argv):
        if a == "--walk" and i + 1 < len(sys.argv):
            walk = int(sys.argv[i + 1])
    byday = {}
    for lab in ("year", "y2025"):
        for c in json.loads(
                (ROOT / f"data/massive/gappers_novol_{lab}.json").read_text()):
            if c.get("hist_n", 99) >= 50:
                byday.setdefault(c["date"], []).append(c)
    todo = []
    for d, cs in sorted(byday.items()):
        cs.sort(key=lambda x: -x["gain_pct"])
        for c in cs[:walk]:
            f = M1 / f"{c['symbol']}_{d}.csv"
            if not f.exists():
                todo.append((c["symbol"], d))
    print(f"walk-{walk}: {len(todo):,} symbol-days to fetch "
          f"(~{len(todo)*12.5/60:.0f} min at 5 req/min)", flush=True)
    got = empty = 0
    for i, (sym, d) in enumerate(todo, 1):
        try:
            ax20b.fetch_m1(sym, d)
            if (M1 / f"{sym}_{d}.csv").read_text(
                    errors="ignore").startswith("EMPTY"):
                empty += 1
            else:
                got += 1
        except Exception as e:
            print(f"ERROR: {sym} {d} -- {e}", flush=True)
        if i % 25 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] fetched={got} empty={empty}",
                  flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
