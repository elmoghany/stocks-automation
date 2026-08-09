"""Historical earnings-report dates + surprises via Finnhub calendar.

WHY (2026-08-09, TWLO case study): the Aug-7 TWLO winner was an
earnings-gap -- Q2 beat reported Aug-6 AMC, +10% gap next morning,
6th straight beat. The Z4xx family tests whether earnings-day gappers
are systematically the good gappers. That needs, for every candidate
symbol-day, "did this company report in the prior 24h, and what is its
beat streak?" -- all knowable IN ADVANCE (report dates are scheduled,
past surprises are history), so fully causal.

Source: Finnhub /calendar/earnings (bulk: every symbol per date range).
Free tier is 60 calls/min -- monthly chunks for 2023-06..2026-08 is
~39 calls, i.e. ~1 minute. Range starts 2023-06 so beat STREAKS have
depth before the first backtest candidate (2024-10).

Output: data/earnings_dates.json
  {"SYM": [{"date": "YYYY-MM-DD", "hour": "amc|bmo|dmh",
            "beat": true|false|null}, ...]}  sorted by date
Loud failure on empty months that should have data; a month with zero
rows in earnings season is a fetch problem, not a fact.
"""

import json
import sys
import time
import urllib.request
from datetime import date as ddate
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))
from shared.win_cred import get_secret

KEY = get_secret("FINNHUB_KEY")
OUT = ROOT / "data/earnings_dates.json"
START = ddate(2023, 6, 1)
END = ddate(2026, 8, 31)


def month_edges():
    d = START
    while d <= END:
        nxt = ddate(d.year + (d.month == 12), d.month % 12 + 1, 1)
        yield d, min(END, ddate(nxt.year, nxt.month, 1))
        d = nxt


def main():
    per = {}
    n_rows = 0
    for a, b in month_edges():
        url = (f"https://finnhub.io/api/v1/calendar/earnings?from={a}"
               f"&to={b}&token={KEY}")
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    rows = json.load(r).get("earningsCalendar") or []
                break
            except Exception as e:
                if attempt == 4:
                    raise
                time.sleep(5 * (attempt + 1))
        if not rows:
            print(f"ERROR: {a}..{b} returned ZERO rows -- earnings months "
                  f"are never empty; treating as fetch failure", flush=True)
        for r in rows:
            sym = (r.get("symbol") or "").upper()
            dt = r.get("date") or ""
            if not sym or not dt:
                continue
            ea, ee = r.get("epsActual"), r.get("epsEstimate")
            beat = (float(ea) > float(ee)) if (
                ea is not None and ee is not None) else None
            per.setdefault(sym, []).append(
                {"date": dt, "hour": r.get("hour") or "", "beat": beat})
        n_rows += len(rows)
        print(f"  {a:%Y-%m}: {len(rows):,} reports", flush=True)
        time.sleep(1.1)                 # stay far under 60/min
    for sym in per:
        per[sym].sort(key=lambda x: x["date"])
    OUT.write_text(json.dumps(per))
    print(f"\n{n_rows:,} reports for {len(per):,} symbols -> {OUT.name}",
          flush=True)


if __name__ == "__main__":
    main()
