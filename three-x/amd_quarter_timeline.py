"""One timeline of AMD: every earnings report, every swing, and each quarter's lowest and highest close.

Swings of 10% or more by close; Aug 2023, Oct 2023 and Oct 2024 use 5%, as in the quarter list. Closing prices, trading days.
Writes results/amd_quarter_timeline.csv and replaces the timeline section in AMD_QUARTERS.md.
"""
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

HERE = Path(__file__).parent
RES = HERE / "results"
raw = yf.download("AMD", start="2022-06-01", end="2026-11-06", auto_adjust=True, progress=False)
h, l, c = raw["High"].squeeze().dropna(), raw["Low"].squeeze().dropna(), raw["Close"].squeeze().dropna()
for s in (h, l, c):
    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
idx, v = c.index, c.values
reports = sorted({int(idx.searchsorted(d)) for d in pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"]) if pd.Timestamp("2023-07-15") <= d <= idx[-1]})
FINE = {"2023-08-01", "2023-10-31", "2024-10-29"}
d = c.diff()
rsi = 100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean() / (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean())
stoch = (100 * (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min())).rolling(3).mean()


def swings(a, b, size):
    points, hi, lo, way = [], a, a, 0
    for i in range(a + 1, b + 1):
        if v[i] > v[hi]:
            hi = i
        if v[i] < v[lo]:
            lo = i
        if way >= 0 and v[i] <= v[hi] * (1 - size):
            if hi != a:
                points.append(hi)
            way, lo = -1, i
        elif way <= 0 and v[i] >= v[lo] * (1 + size):
            if lo != a:
                points.append(lo)
            way, hi = 1, i
    return points


rows, previous = [], None
for j, r in enumerate(reports):
    end = reports[j + 1] if j + 1 < len(reports) else len(v) - 1
    is_last = j + 1 == len(reports)
    rows.append({"date": idx[r], "event": "EARNINGS", "close": v[r], "before": None, "after": None, "vs_report": None, "move": v[r] / previous - 1 if previous else None, "rsi": rsi.iloc[r], "stoch": stoch.iloc[r]})
    previous = v[r]
    span = range(r + 1, end + (1 if is_last else 0))
    lowest = min(range(r + 1, end + 1), key=lambda i: v[i]) if end > r else None
    highest = max(range(r + 1, end + 1), key=lambda i: v[i]) if end > r else None
    size = 0.05 if str(idx[r].date()) in FINE else 0.10
    points = set(swings(r, end, size))
    points |= {r + 1} if r + 1 <= end else set()
    points |= {i for i in (lowest, highest) if i is not None and i != end or is_last}
    if is_last:
        points.add(end)
    points.discard(end if not is_last else -1)
    for i in sorted(points):
        tag = "LOW" if i == lowest else "HIGH" if i == highest else "next day" if i == r + 1 else "swing"
        rows.append({"date": idx[i], "event": tag, "close": v[i], "before": None if is_last else end - i, "after": i - r, "vs_report": v[i] / v[r] - 1, "move": v[i] / previous - 1, "rsi": rsi.iloc[i], "stoch": stoch.iloc[i]})
        previous = v[i]
t = pd.DataFrame(rows)
t.to_csv(RES / "amd_quarter_timeline.csv", index=False)
lines = ["Date       Event      Close   Before/After  vs report   Move   RSI  Stoch"]
for r in t.itertuples():
    move = f"{r.move:+6.1%}" if pd.notna(r.move) else "      "
    if r.event == "EARNINGS":
        if len(lines) > 1:
            lines.append("")
        lines.append(f"{r.date.strftime('%b %d %y')}  EARNINGS {r.close:8.2f}                            {move}  {r.rsi:3.0f}   {r.stoch:3.0f}")
    else:
        before = "?" if pd.isna(r.before) else f"{int(r.before)}"
        lines.append(f"{r.date.strftime('%b %d %y')}  {r.event:<8} {r.close:8.2f}   {before + '/' + str(int(r.after)):>7}     {r.vs_report:+7.1%}  {move}  {r.rsi:3.0f}   {r.stoch:3.0f}")
text = "\n".join(lines)
print(text)
md = HERE / "AMD_QUARTERS.md"
s = md.read_text(encoding="utf-8")
a = s.index("## Timeline of each quarter")
b = s.index("Generated with `amd_quarter_paths.py`,", a)
section = ("## Timeline of each quarter\n\nEvery report, every swing, and each quarter's lowest (LOW) and highest (HIGH) close. Closing prices. Before/After is in trading days: days before the next report, then days after the last one. "
           "\"vs report\" is against the last report-day close, and \"Move\" is against the row above. Swings are 10% or more; Aug 2023, Oct 2023 and Oct 2024 use 5%. The last close may not be final.\n\n```\n" + text + "\n```\n\n")
md.write_text(s[:a] + section + s[b:], encoding="utf-8")
