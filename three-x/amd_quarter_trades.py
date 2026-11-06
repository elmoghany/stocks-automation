"""AMD's quarter lows and highs as trades in date order: buy at a low, sell at the next high, with any earnings between them as rows.

Uses each quarter's lowest and highest close. Where two lows or two highs come in a row, the lower low or higher high is kept, so buys and sells
alternate. A buy may come before an earnings date (user's choice, 2026-11-05). Known only afterwards; not a rule. Closing prices, trading days.
Writes results/amd_quarter_trades.csv and replaces the trade section in AMD_QUARTERS.md.
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

events = []
for j, r in enumerate(reports):
    end = reports[j + 1] if j + 1 < len(reports) else len(v) - 1
    span = range(r + 1, end + 1)
    events += [(min(span, key=lambda i: v[i]), "low"), (max(span, key=lambda i: v[i]), "high")]
events = sorted(set(events))
chain = []
for i, kind in events:
    if chain and chain[-1][1] == kind:
        better = v[i] < v[chain[-1][0]] if kind == "low" else v[i] > v[chain[-1][0]]
        if better:
            chain[-1] = (i, kind)
    else:
        chain.append((i, kind))


def days(i):
    past = [r for r in reports if r < i]
    later = [r for r in reports if r >= i]
    return (i - past[-1] if past else None), (later[0] - i if later else None)


def row(i, label, gain="", held=""):
    a, b = days(i)
    return f"{idx[i].strftime('%b %d %y')}  {label:<8} {v[i]:8.2f}  {a if a is not None else '':>5}  {b if b is not None else '?':>6}  {gain:>7}  {held:>5}  {rsi[i]:3.0f}   {stoch[i]:3.0f}"


lines = ["Date       Event      Close  After  Before     Gain   Held  RSI  Stoch"]
rows, gains = [], []
report_iter = list(reports)
pos = 0
for k, (i, kind) in enumerate(chain):
    while pos < len(report_iter) and report_iter[pos] < i:
        lines.append(f"{idx[report_iter[pos]].strftime('%b %d %y')}  EARNINGS {v[report_iter[pos]]:8.2f}                                 {rsi[report_iter[pos]]:3.0f}   {stoch[report_iter[pos]]:3.0f}")
        pos += 1
    if kind == "low":
        if k:
            lines.append("")
        lines.append(row(i, "BUY"))
    elif k == 0:
        lines.append(row(i, "HIGH") + "   no buy before it")
    else:
        buy = chain[k - 1][0]
        gain = v[i] / v[buy] - 1
        gains.append(gain)
        lines.append(row(i, "SELL", f"{gain:+.1%}", str(i - buy)))
        rows.append({"buy": idx[buy].date(), "buy_close": v[buy], "sell": idx[i].date(), "sell_close": v[i], "gain": gain, "days_held": i - buy, "reports_inside": sum(buy < r < i for r in reports)})
if chain[-1][1] == "low":
    lines[-1] += "   lowest so far, not known to be the low"
while pos < len(report_iter):
    lines.append(f"{idx[report_iter[pos]].strftime('%b %d %y')}  EARNINGS {v[report_iter[pos]]:8.2f}")
    pos += 1
text = "\n".join(lines)
print(text)
t = pd.DataFrame(rows)
t.to_csv(RES / "amd_quarter_trades.csv", index=False)
print(f"\ntrades {len(t)}; compounded {np.prod(1 + t.gain):.1f}x; median gain {t.gain.median():+.0%}; median held {t.days_held.median():.0f} days, range {t.days_held.min()}-{t.days_held.max()}; with a report inside {(t.reports_inside > 0).sum()}")
md = HERE / "AMD_QUARTERS.md"
s = md.read_text(encoding="utf-8")
head = "## Lows and highs as trades"
a = s.index(head)
b = s.index("## Timeline of each quarter", a)
section = ("## Lows and highs as trades\n\nBuy at a quarter's low, sell at the next quarter high, with any earnings between them. Where two lows or two highs come in a row, the lower low or higher high is kept. Known only afterwards. Closing prices, trading days. "
           "After counts from the last report, Before counts to the next one, Gain is sell against buy, and Held is days between them.\n\n```\n" + text + "\n```\n\n")
md.write_text(s[:a] + section + s[b:], encoding="utf-8")
