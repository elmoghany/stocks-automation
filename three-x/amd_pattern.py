"""AMD's pattern before and after each earnings report, last 3 years. A description only, with no backtest (user order 2026-11-05).

D is the report date, after the close. For each report, working through the cycle:
  high before: highest close in the 30 trading days before D
  low before: lowest close between that high and D
  low after: lowest close in the 20 trading days after D
  high after: highest close after that low, up to the next report
Picking highs and lows after the fact makes any volatile stock look patterned, so the same measures are repeated on the same
number of fake dates, moved 3 to 9 weeks away from the reports. Only differences from those fake dates say something about earnings.
Writes results/amd_pattern.csv.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
raw = yf.download("AMD", start="2023-06-01", end="2026-11-06", auto_adjust=True, progress=False)
close = raw["Close"].squeeze().dropna()
close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
c, idx = close.values, close.index
dates = [d for d in pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"]) if pd.Timestamp("2023-11-05") <= d <= idx[-1]]
reports = sorted({int(idx.searchsorted(d)) for d in dates})


def cycle(p, next_p):
    a = max(p - 30, 0)
    hb = a + int(np.argmax(c[a:p + 1]))
    lb = hb + int(np.argmin(c[hb:p + 1]))
    row = {"report": idx[p].date(), "close_D": round(c[p], 2), "high_before_days": hb - p, "fall_into": c[lb] / c[hb] - 1, "low_before_days": lb - p, "bounce_into": c[p] / c[lb] - 1,
           "last_2d": c[p] / c[p - 2] - 1, "next_day": c[p + 1] / c[p] - 1 if p + 1 < len(c) else np.nan}
    end = min(p + 21, len(c))
    if p + 1 < end:
        la = p + 1 + int(np.argmin(c[p + 1:end]))
        row.update({"low_after_days": la - p, "drop_after": c[la] / c[p] - 1})
        if la + 1 < min(next_p + 1, len(c)):
            ha = la + int(np.argmax(c[la:min(next_p + 1, len(c))]))
            row.update({"high_after_days": ha - p, "rise_after": c[ha] / c[la] - 1})
    return row


rows = [cycle(p, reports[j + 1] if j + 1 < len(reports) else len(c) - 1) for j, p in enumerate(reports)]
ev = pd.DataFrame(rows)
ev.to_csv(RES / "amd_pattern.csv", index=False)
pd.set_option("display.width", 220, "display.max_columns", 20)
print(ev.to_string(index=False, float_format=lambda v: f"{v:+.2f}"))

measures = ["fall_into", "bounce_into", "last_2d", "next_day", "drop_after", "rise_after"]
print("\nmedian, range and direction across reports, against fake dates")
fake = []
for shift in (-45, -35, -25, -15, 15, 25, 35, 45):
    pts = [p + shift for p in reports if 31 <= p + shift < len(c) - 2]
    for j, p in enumerate(pts):
        fake.append(cycle(p, pts[j + 1] if j + 1 < len(pts) else len(c) - 1))
fake = pd.DataFrame(fake)
for m in measures:
    v, f = ev[m].dropna(), fake[m].dropna()
    print(f"{m:12s} real median {v.median():+.1%} (from {v.min():+.0%} to {v.max():+.0%}), up {int((v > 0).sum())} of {len(v)} | fake dates median {f.median():+.1%}, up {(f > 0).mean():.0%}")
for m in ("high_before_days", "low_before_days", "low_after_days", "high_after_days"):
    print(f"{m:18s} real median {ev[m].median():.0f} days | fake dates {fake[m].median():.0f} days")

path = {}
for j, p in enumerate(reports):
    path[str(idx[p].date())] = pd.Series({k: c[p + k] / c[p] - 1 for k in range(-30, 46) if 0 <= p + k < len(c)})
path = pd.DataFrame(path)
print("\nmedian path against the close on D")
for k in (-30, -20, -15, -10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 15, 20, 30, 40, 45):
    print(f"  day {k:+3d}: median {path.loc[k].median():+.1%}, reports {path.loc[k].notna().sum()}")

full = (ev.fall_into <= -.05) & (ev.bounce_into > 0) & (ev.drop_after <= -.05) & (ev.rise_after > 0)
real_rate = full[ev.drop_after.notna() & ev.rise_after.notna()].mean()
fake_full = (fake.fall_into <= -.05) & (fake.bounce_into > 0) & (fake.drop_after <= -.05) & (fake.rise_after > 0)
print(f"\nfull cycle (fell 5%+ into D, bounced into D, fell 5%+ after, then rose): {int(full.sum())} of {int((ev.drop_after.notna() & ev.rise_after.notna()).sum())} = {real_rate:.0%}; fake dates {fake_full[fake.drop_after.notna() & fake.rise_after.notna()].mean():.0%}")
