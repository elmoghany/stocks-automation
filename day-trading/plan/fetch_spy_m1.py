"""SPY 1-minute bars, 2 years -- data for the video-strategy backtest.

The Riley Coleman study (video-studies/2026-08-09-*.md) trades S&P
futures reversals; our key has no futures, so SPY is the proxy. One
Massive/Polygon aggs call per trading day (free tier 5 req/min ->
~500 calls ~105 min). Resumable; EMPTY sentinel for holidays.
Output: data/spy_m1/SPY_YYYY-MM-DD.csv (same schema as data/massive/m1).
"""

import sys
import time
from datetime import date as ddate, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))
from shared import massive

OUT = ROOT / "data/spy_m1"
OUT.mkdir(parents=True, exist_ok=True)
START = ddate(2024, 8, 1)
END = ddate(2026, 7, 31)

days = []
d = START
while d <= END:
    if d.weekday() < 5:
        days.append(d)
    d += timedelta(days=1)
todo = [d for d in days if not (OUT / f"SPY_{d}.csv").exists()]
print(f"{len(days)} weekdays, {len(todo)} to fetch "
      f"(~{len(todo)*12.5/60:.0f} min)", flush=True)
got = empty = 0
for i, d in enumerate(todo, 1):
    try:
        df = massive.minute_bars("SPY", str(d))
    except Exception as e:
        print(f"ERROR {d}: {e}", flush=True)
        continue
    f = OUT / f"SPY_{d}.csv"
    if df is None or df.empty:
        f.write_text("EMPTY")
        empty += 1
    else:
        out = df.reset_index()
        out["begins_at"] = out["begins_at"].dt.tz_convert("UTC")
        out.to_csv(f, index=False)
        got += 1
    if i % 25 == 0 or i == len(todo):
        print(f"  [{i}/{len(todo)}] got={got} empty={empty}", flush=True)
print("done", flush=True)
