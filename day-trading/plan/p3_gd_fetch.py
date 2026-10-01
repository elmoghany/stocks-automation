"""PAPER-3BOOK: top up data/massive/gd (Polygon grouped-daily) through
YESTERDAY, so plan/p3_universe.py's 60-session liquidity screen is current.
Needed only for the monthly universe refresh. Today's file is not
available until after the close (403), so it is never requested.

    python plan/p3_gd_fetch.py            # fills every missing weekday
"""
import gzip
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shared import massive as M                               # noqa: E402

GD = ROOT / "day-trading" / "data" / "massive" / "gd"


def main():
    have = sorted(p.name[:10] for p in GD.glob("*.json.gz"))
    d = date.fromisoformat(have[-1]) + timedelta(days=1)
    end = date.today() - timedelta(days=1)
    n = 0
    while d <= end:
        if d.weekday() < 5:
            f = GD / f"{d}.json.gz"
            if not f.exists():
                try:
                    r = M.grouped_daily(str(d))
                except Exception as e:                          # noqa: BLE001
                    print(f"{d}: FAILED {e}", flush=True)
                    d += timedelta(days=1)
                    continue
                with gzip.open(f, "wt") as fh:
                    json.dump(r, fh)
                n += 1
                print(f"{d}: {len(r)} rows", flush=True)
        d += timedelta(days=1)
    print(f"gd top-up: {n} new files; last = {sorted(GD.glob('*.json.gz'))[-1].name}")


if __name__ == "__main__":
    main()
