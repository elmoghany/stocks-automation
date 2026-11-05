"""Each AMD quarter as a trade: earnings, then the best buy, then the best sell after it. Known only afterwards; not a rule.

A quarter runs from the day after a report through the next report day. The pair is the largest rise from a close to a later close in
that span, so the sell always follows the buy. Closing prices, trading days. Writes results/amd_quarter_best_trades.csv and a section in AMD_QUARTERS.md.
"""
import json
from pathlib import Path

import numpy as np
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
d = c.diff()
rsi = (100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean() / (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean())).values
stoch = ((100 * (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min())).rolling(3).mean()).values
rows, lines = [], ["Date       Event      Close   After  Before  vs report   Gain   RSI  Stoch"]
gains = []
for j, r in enumerate(reports):
    last = j + 1 == len(reports)
    end = len(v) - 1 if last else reports[j + 1]
    lines.append(f"{idx[r].strftime('%b %d %y')}  EARNINGS {v[r]:8.2f}                                  {rsi[r]:3.0f}   {stoch[r]:3.0f}")
    if last:
        low = min(range(r + 1, end + 1), key=lambda i: v[i])
        lines.append(f"{idx[low].strftime('%b %d %y')}  BUY      {v[low]:8.2f}   {low - r:4d}       ?   {v[low] / v[r] - 1:+7.1%}          {rsi[low]:3.0f}   {stoch[low]:3.0f}   lowest so far, not known to be the low")
        rows.append({"report": idx[r].date(), "buy": idx[low].date(), "buy_close": v[low], "sell": None, "sell_close": None, "gain": None})
        continue
    best = max(((v[y] / v[x] - 1, x, y) for x in range(r + 1, end) for y in range(x + 1, end + 1)))
    gain, x, y = best
    gains.append(gain)
    lines.append(f"{idx[x].strftime('%b %d %y')}  BUY      {v[x]:8.2f}   {x - r:4d}    {end - x:4d}   {v[x] / v[r] - 1:+7.1%}          {rsi[x]:3.0f}   {stoch[x]:3.0f}")
    lines.append(f"{idx[y].strftime('%b %d %y')}  SELL     {v[y]:8.2f}   {y - r:4d}    {end - y:4d}   {v[y] / v[r] - 1:+7.1%}  {gain:+6.1%}  {rsi[y]:3.0f}   {stoch[y]:3.0f}")
    lines.append("")
    rows.append({"report": idx[r].date(), "buy": idx[x].date(), "buy_close": v[x], "buy_after": x - r, "buy_before": end - x, "sell": idx[y].date(), "sell_close": v[y], "sell_after": y - r, "sell_before": end - y, "gain": gain, "days_held": y - x})
text = "\n".join(lines)
print(text)
t = pd.DataFrame(rows)
t.to_csv(RES / "amd_quarter_best_trades.csv", index=False)
done = t.dropna(subset=["gain"])
print(f"\nquarters {len(done)}; gain median {done.gain.median():+.0%}, range {done.gain.min():+.0%} to {done.gain.max():+.0%}; 25%+ in {(done.gain >= .25).sum()}; 20%+ in {(done.gain >= .20).sum()}")
print(f"buy day median {done.buy_after.median():.0f}, range {done.buy_after.min():.0f}-{done.buy_after.max():.0f}; sell day median {done.sell_after.median():.0f}, range {done.sell_after.min():.0f}-{done.sell_after.max():.0f}; held median {done.days_held.median():.0f} days, range {done.days_held.min():.0f}-{done.days_held.max():.0f}")
print(f"all trades compounded: {np.prod(1 + np.array(gains)):.1f}x")
md = HERE / "AMD_QUARTERS.md"
s = md.read_text(encoding="utf-8")
head = "## Each quarter as a trade"
section = (head + "\n\nEarnings, then the best buy, then the best sell after it in that quarter, known only afterwards. Closing prices, trading days. After counts from the report, Before counts to the next report, vs report is against the report-day close, and Gain is sell against buy.\n\n```\n" + text + "\n```\n\n")
if head in s:
    a = s.index(head)
    b = s.index("## Timeline of each quarter", a)
    s = s[:a] + section + s[b:]
else:
    a = s.index("## Timeline of each quarter")
    s = s[:a] + section + s[a:]
md.write_text(s, encoding="utf-8")
