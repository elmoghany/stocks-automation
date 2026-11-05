"""Every meaningful AMD fall in the last 3 years, including the one in progress, and which ones the earlier rules bought.

A fall runs from a closing high to the lowest close before the stock has rebounded by at least the same threshold.
Also shows the deepest fall visible at a Friday close, because earlier rules only looked on Fridays or at month-ends.
"""
import pandas as pd
import yfinance as yf

import amd_cycle as A

THRESHOLD = 0.15
raw = yf.download("AMD", start="2022-06-01", end="2026-11-06", auto_adjust=True, progress=False)
close = raw["Close"].squeeze().dropna()
close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
window = close[close.index >= A.FROM]
print("latest bars:", ", ".join(f"{d.date()} {v:.2f}" for d, v in window.tail(6).items()))
fridays = window.resample("W-FRI").last().dropna()

falls, high_i, low_i, falling = [], 0, 0, False
v = window.values
for i in range(1, len(v)):
    if not falling:
        if v[i] > v[high_i]:
            high_i = i
        elif v[i] <= v[high_i] * (1 - THRESHOLD):
            falling, low_i = True, i
    else:
        if v[i] < v[low_i]:
            low_i = i
        elif v[i] >= v[low_i] * (1 + THRESHOLD):
            falls.append((high_i, low_i))
            falling, high_i = False, i
if falling:
    falls.append((high_i, low_i))
else:
    now = v[-1] / v[high_i:].max() - 1
    print(f"not in a {THRESHOLD:.0%} fall now: {now:.1%} from the high of {window.index[high_i].date()}")

reports = pd.to_datetime(A.REPORTS)
rows = []
for a, b in falls:
    start, end = window.index[a], window.index[b]
    seen = fridays[(fridays.index >= start) & (fridays.index <= end + pd.Timedelta(days=7))]
    before = reports[reports <= end]
    rows.append({"high_date": start.date(), "high": round(v[a], 2), "low_date": end.date(), "low": round(v[b], 2), "fall": v[b] / v[a] - 1,
                 "weeks": round((b - a) / 5, 1), "deepest_friday": seen.min() / v[a] - 1, "rebound_after": window.iloc[b:].iloc[:64].max() / v[b] - 1,
                 "weeks_since_report": round((end - before[-1]).days / 7, 1) if len(before) else None})
table = pd.DataFrame(rows)
pd.set_option("display.width", 200, "display.max_columns", 20)
print(table.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
print(f"\nfalls of 15%+: {len(table)}; 20%+: {(table.fall <= -.20).sum()}; 25%+: {(table.fall <= -.25).sum()}")
print(f"reached 25% on a close but not at a Friday close: {((table.fall <= -.25) & (table.deepest_friday > -.25)).sum()}")

t = pd.read_csv(A.RES / "amd_cycle.csv")
print("\nearlier run 2 rules: changes in position over 3 years (a buy and a sale is 2)")
print(t[t.group.str.startswith("run2")].groupby("group").changes.describe()[["min", "50%", "max"]].to_string())
