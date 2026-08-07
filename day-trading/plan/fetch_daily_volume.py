"""Fetch daily volume history so rvol can use a 30-DAY baseline.

WHY (2026-08-07): the backtest selects candidates on FULL-DAY volume /
50-day average >= 5. Two problems, both real:
  1. NOT CAUSAL. Full-day volume is unknowable at 07:30 when we decide.
  2. WRONG LOOKBACK. The live Robinhood scanner uses 30 days, so the
     backtest and the live scan are not measuring the same thing. TWLO
     on 2026-08-06 finished at 2.05x on our 50-day measure -- BELOW the
     5x rule -- yet the live scan surfaced it and C35 traded it for
     +$1,266.58. Selection is currently inconsistent between the two.

This script builds the DENOMINATOR: a per-symbol daily volume table.
The numerator (cumulative volume as of a decision time) comes free from
the local 1-minute cache -- see build_vol_at_t.py.

COST NOTE, so nobody repeats the estimate wrong: shared/massive.py sets
_TH_INTERVAL = 12.5s, i.e. the Massive/Polygon key is FREE TIER at 5
requests/minute. Per-symbol intraday history for 3,916 symbols would be
13+ hours. grouped_daily returns EVERY US ticker for one date in ONE
call, so the whole 2-year daily table costs ~500 calls (~105 min).
That is why the 30-day baseline here is average FULL-DAY volume rather
than average volume-at-the-same-clock-time: the latter needs 30 sessions
of intraday bars per symbol, which the free tier cannot deliver in
reasonable time. Stated openly rather than silently approximated.

Resumable: already-cached dates are skipped, so it can be re-run.
"""

import json
import sys
from datetime import date as ddate, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))

OUT = ROOT / "data/massive/dailyvol"
START = ddate(2024, 9, 1)      # >=30 sessions before the first candidate
END = ddate(2026, 7, 31)       # last candidate date


def wanted_symbols():
    syms = set()
    for lab in ("year", "y2025"):
        f = ROOT / f"data/massive/gappers2_{lab}.json"
        if f.exists():
            for c in json.loads(f.read_text()):
                syms.add(c["symbol"].upper())
    if not syms:
        raise RuntimeError("ERROR: no candidate pool found -- refusing to "
                           "fetch a table with no target symbols")
    return syms


def main():
    from shared import massive
    OUT.mkdir(parents=True, exist_ok=True)
    syms = wanted_symbols()
    print(f"tracking {len(syms):,} symbols", flush=True)

    days = []
    d = START
    while d <= END:
        if d.weekday() < 5:                     # skip weekends, no API cost
            days.append(d)
        d += timedelta(days=1)
    todo = [d for d in days if not (OUT / f"{d}.json").exists()]
    print(f"{len(days):,} weekdays in range, {len(todo):,} still to fetch "
          f"(~{len(todo)*12.5/60:.0f} min at 5 req/min)", flush=True)

    for i, d in enumerate(todo, 1):
        try:
            rows = massive.grouped_daily(str(d))
        except Exception as e:
            print(f"ERROR: {d} fetch failed -- {e}", flush=True)
            continue
        # [] is a legitimate holiday result; cache it so we never re-ask.
        vol = {r["T"]: r["v"] for r in rows
               if r.get("T") in syms and r.get("v")}
        (OUT / f"{d}.json").write_text(json.dumps(vol))
        if i % 20 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] {d}  {len(vol):,} of our symbols "
                  f"traded ({len(rows):,} tickers total)", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
