"""SWING-EARNINGS: Polygon split calendar (execution dates) 2024-06 .. 2026-10.

gd files were fetched adjusted=true on different days, so a price series
can jump across a split.  Any trade whose [entry-60d, exit] window spans a
split execution date of its symbol is dropped by se_events (a rule that
looks only at the corporate-action calendar, never at returns).
Output data/research_oct/splits.json {sym: [execution_date, ...]}
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT.parent))
from shared import massive                                    # noqa: E402
from shared.win_cred import get_secret                        # noqa: E402

massive._TH_INTERVAL = 0.1
KEY = get_secret("MASSIVE_KEY")


def main():
    out = {}
    url = (f"{massive.BASE}/v3/reference/splits?execution_date.gte=2024-06-01"
           f"&execution_date.lte=2026-10-31&limit=1000&apiKey={KEY}")
    n = 0
    while url:
        d = massive._get(url)
        for r in d.get("results") or []:
            out.setdefault(r["ticker"], []).append(r["execution_date"])
            n += 1
        nxt = d.get("next_url")
        url = (nxt + f"&apiKey={KEY}") if nxt else None
    p = ROOT / "data" / "research_oct" / "se_splits.json"
    p.write_text(json.dumps(out))
    print(f"splits {n} for {len(out)} tickers")


if __name__ == "__main__":
    main()
