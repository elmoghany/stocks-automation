"""Populate the Robinhood fundamentals cache that halal_check reads.

WHY THIS EXISTS (2026-08-07): the live session found SSP, RMCO and GTN
"passing" the halal screen on all-zero ratios. The cause was NOT missing
financial statements -- yfinance has those (SSP totalDebt $2.68B, cash
$83.7M, revenue $2.14B). The cause was a MISSING MARKET CAP: with
mcap = 0 every ratio divide-guards to 0.0 and every test trivially
passes. yfinance returns marketCap = None AND sharesOutstanding = None
for these names, so it cannot be recovered there.

Robinhood HAS the number -- the scanner returns a "Market cap" column
and get_equity_fundamentals carries it -- but only the agent can call
Robinhood. So the agent writes it here, and day-trading.py picks it up
via load_rh_fundamentals().

Usage (agent-driven, before screening a name):
    python plan/update_rh_fundamentals.py SYM MARKET_CAP [SECTOR] [INDUSTRY]
Refuses non-positive market caps rather than storing a value that would
re-create the original bug.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "rh_fundamentals.json"


def update(sym, mcap, sector=None, industry=None):
    try:
        mcap = float(mcap)
    except (TypeError, ValueError):
        return False, "ERROR: non-numeric market cap"
    if mcap <= 0:
        return False, ("ERROR: market cap must be positive -- storing 0 "
                       "would make every halal ratio trivially pass")
    data = {}
    if CACHE.exists():
        try:
            data = json.loads(CACHE.read_text())
        except Exception:
            data = {}
    rec = data.get(sym.upper(), {})
    rec["market_cap"] = mcap
    if sector:
        rec["sector"] = sector
    if industry:
        rec["industry"] = industry
    data[sym.upper()] = rec
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=1))
    return True, f"stored {sym.upper()} market_cap ${mcap:,.0f}"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    ok, msg = update(*sys.argv[1:5])
    print(msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
