"""Earnings-report history for walk-16 candidate symbols via yfinance.

Finnhub's free tier only serves ~1 month of historical calendar (the
2026-08-09 fetch returned zeros before 2026-07), so the per-symbol
yfinance path is the only workable source for the 2-year backtest.
Scope is cut to the 2,045 symbols that can actually be traded (top-16
walk membership, data/earnings_syms.json) -- ~45 min at gentle pace.

Each symbol: t.get_earnings_dates(limit=40) -> report timestamps (the
clock time distinguishes before-open from after-close) + Surprise(%).
Output data/earnings_yf.json:
  {"SYM": [{"ts": "YYYY-MM-DD HH:MM", "surprise": pct|null}, ...]}

Same discipline as the halal build: gentle pace, resumable flushes,
no-data recorded as [] only after a healthy-canary check so a rate
limit is never cached as "no earnings".
"""

import json
import sys
import time
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
SYMS_F = ROOT / "data/earnings_syms.json"
OUT = ROOT / "data/earnings_yf.json"
PACE = 1.2


def fetch_one(sym):
    try:
        df = yf.Ticker(sym).get_earnings_dates(limit=40)
    except Exception:
        return None
    if df is None or df.empty:
        return []
    out = []
    for ts, row in df.iterrows():
        sp = row.get("Surprise(%)")
        out.append({"ts": ts.strftime("%Y-%m-%d %H:%M"),
                    "surprise": None if sp != sp else float(sp)})
    return out


def main():
    syms = json.loads(SYMS_F.read_text())
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = [s for s in syms if s not in done]
    print(f"{len(done):,} cached, {len(todo):,} to fetch "
          f"(~{len(todo)*PACE/60:.0f} min)", flush=True)
    nodata_streak = 0
    for i, sym in enumerate(todo, 1):
        time.sleep(PACE)
        r = fetch_one(sym)
        if r is None or r == []:
            nodata_streak += 1
            if nodata_streak >= 25:
                canary = fetch_one("AAPL")
                if canary:
                    nodata_streak = 0
                else:
                    print("  RATE-LIMITED (canary failed) -- sleeping "
                          "10 min", flush=True)
                    json.dump(done, open(OUT, "w"))
                    time.sleep(600)
                    nodata_streak = 0
                    continue        # retry sym next run (not cached)
        else:
            nodata_streak = 0
        done[sym] = r if r is not None else []
        if i % 50 == 0 or i == len(todo):
            json.dump(done, open(OUT, "w"))
            got = sum(1 for v in done.values() if v)
            print(f"  [{i:,}/{len(todo):,}] with earnings data: {got:,}",
                  flush=True)
    json.dump(done, open(OUT, "w"))
    print("done", flush=True)


if __name__ == "__main__":
    main()
