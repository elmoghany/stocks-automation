"""Pattern study before any backtest: what AMD did right after each report since 2013, and how often a fast run like Nov 2026 happened.

The November 2026 case: report Nov 3 after the close, a fall to $404 on Nov 5, then +45% in five sessions. The five paper books wait for fixed
dates or dips, so they sat in cash. This looks at every report since 2013 for the same shape: how far it fell after the report, how fast it
came back, and how far it ran. It also lists every fast run (+25% within 10 sessions) and how near each was to a report. Prints only.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).parent
END = "2026-11-13"

raw = yf.download("AMD", start="2012-06-01", end=END, auto_adjust=True, progress=False)
f = pd.DataFrame({k.lower(): raw[k].squeeze() for k in ("Open", "High", "Low", "Close", "Volume")}).dropna()
f.index = pd.DatetimeIndex(f.index).tz_localize(None).normalize()
c, idx, n = f.close.values, f.index, len(f)
reports = [d for d in pd.to_datetime(json.loads((HERE / "results" / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"]) if pd.Timestamp("2013-01-01") <= d <= idx[-1]]

rows = []
for d in reports:
    r = int(idx.searchsorted(d))
    if r + 1 >= n:
        continue
    base = c[r]
    w5 = c[r + 1:min(r + 6, n)]
    low_i = r + 1 + int(np.argmin(w5))
    low = c[low_i]
    after = c[low_i:min(low_i + 21, n)]
    peak_i = low_i + int(np.argmax(after))
    rows.append({
        "report": d.date(), "close": round(base, 2), "day1": c[r + 1] / base - 1, "low5": low / base - 1, "low_day": low_i - r,
        "run20": c[peak_i] / low - 1, "run_days": peak_i - low_i,
        "after20": c[min(r + 20, n - 1)] / base - 1, "after60": c[min(r + 60, n - 1)] / base - 1 if r + 60 < n else np.nan,
    })
t = pd.DataFrame(rows)
pct = lambda v: "" if pd.isna(v) else f"{v:+.0%}"
show = t.copy()
for col in ("day1", "low5", "run20", "after20", "after60"):
    show[col] = show[col].map(pct)
pd.set_option("display.width", 200, "display.max_rows", 100)
print("Each report: day1 = next close vs report-day close; low5 = lowest close in 5 days after; run20 = best rise from that low within 20 days")
print(show.to_string(index=False))

print(f"\n{len(t)} reports. Runs from the post-report low:")
for lim in (0.15, 0.25, 0.40):
    hit = t[t.run20 >= lim]
    print(f"  +{lim:.0%} or more within 20 days: {len(hit)} of {len(t)} ({len(hit) / len(t):.0%}); median days {hit.run_days.median():.0f}")
for name, part in (("fell 5%+ in 5 days", t[t.low5 <= -0.05]), ("fell less", t[t.low5 > -0.05])):
    print(f"  {name}: {len(part)}, run +15% or more {(part.run20 >= 0.15).mean():.0%}, median run {part.run20.median():+.0%}")
for name, part in (("since Aug 2023", t[pd.to_datetime(t.report) >= "2023-08-01"]), ("2013 to Jul 2023", t[pd.to_datetime(t.report) < "2023-08-01"])):
    print(f"  {name}: {len(part)} reports, run +15% or more {(part.run20 >= 0.15).mean():.0%}, median run {part.run20.median():+.0%}")

print("\nEvery fast run since 2013: close up 25%+ within 10 sessions from a 10-day low (first day of each, 20 days apart)")
runs, last = [], -99
for i in range(10, n - 1):
    lo_i = i - 9 + int(np.argmin(c[i - 9:i + 1]))
    if c[i] / c[lo_i] - 1 >= 0.25 and i - last > 20:
        rep = [int(idx.searchsorted(d)) for d in reports]
        gap = min((lo_i - r for r in rep if r <= lo_i), default=999)
        fwd = c[min(i + 20, n - 1)] / c[i] - 1
        runs.append({"low_date": idx[lo_i].date(), "hit_date": idx[i].date(), "rise": c[i] / c[lo_i] - 1, "days_from_report": gap, "next20": fwd})
        last = i
r = pd.DataFrame(runs)
near = r[r.days_from_report <= 10]
print(r.assign(rise=r.rise.map(pct), next20=r.next20.map(pct)).to_string(index=False))
print(f"\n{len(r)} fast runs; {len(near)} began within 10 sessions after a report. After the run was already +25%, the next 20 sessions: median {r.next20.median():+.0%}, up in {(r.next20 > 0).mean():.0%}")
