"""Merge agent-fetched Robinhood market caps into data/rh_fundamentals.json.

CONTEXT (2026-08-14): data/needs_mcap.json holds 5,930 symbols the halal
pre-screen refused because yfinance had no market cap ("absence of
evidence is never compliance"). The agent classified them against the
nasdaqtrader.com symbol directories -- 5,561 are exchange-flagged ETFs,
~330 more are notes/preferreds/debentures/CEFs/test issues, all of which
must STAY unverifiable -- and fetched RH fundamentals only for the ~34
plausible common stocks, writing what came back (plus every exclusion
and API error) to data/mcap_backfill_fetch.json.

This script merges the staged records into the rh_fundamentals cache
that day-trading.py::load_rh_fundamentals() reads. Guards, in the same
spirit as plan/update_rh_fundamentals.py:
  * refuses non-positive market caps (a stored 0 would make every halal
    ratio trivially pass -- the original SSP/RMCO/GTN bug);
  * refuses fund/trust industries (both RH spellings) so a closed-end
    fund's AUM can never masquerade as a company's market cap;
  * additive only -- asserts no existing entry is dropped.

Usage:  python plan/merge_needs_mcap_backfill.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "rh_fundamentals.json"
STAGE = ROOT / "data" / "mcap_backfill_fetch.json"

# RH uses both spellings ("Investment Trusts Or Mutual Funds" and
# "Investment Trusts/Mutual Funds") -- match either.
FUND_INDUSTRIES = {"investment trusts or mutual funds",
                   "investment trusts/mutual funds"}
KEYS = ("float", "shares_outstanding", "market_cap", "sector", "industry",
        "avg_volume_30d", "avg_volume_2wk", "fetched", "source")


def main():
    stage = json.loads(STAGE.read_text())
    recs = stage["records"]
    data = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    before = dict(data)

    added, updated, skipped = [], [], []
    for sym, r in sorted(recs.items()):
        sym = sym.upper()
        mcap = r.get("market_cap") or 0
        if mcap <= 0:
            skipped.append((sym, "non-positive market cap -- refusing"))
            continue
        if (r.get("industry") or "").strip().lower() in FUND_INDUSTRIES:
            skipped.append((sym, "fund/trust industry -- stays unverifiable"))
            continue
        cur = data.get(sym, {})
        (updated if sym in data else added).append(sym)
        cur.update({k: r.get(k) for k in KEYS})
        data[sym] = cur

    missing = set(before) - set(data)
    assert not missing, f"merge DROPPED existing entries: {sorted(missing)}"
    CACHE.write_text(json.dumps(data, indent=1))

    print(f"rh_fundamentals.json: {len(before)} -> {len(data)} entries")
    print(f"added   ({len(added)}): {', '.join(added)}")
    if updated:
        print(f"updated ({len(updated)}): {', '.join(updated)}")
    for sym, why in skipped:
        print(f"skipped {sym}: {why}")


if __name__ == "__main__":
    main()
