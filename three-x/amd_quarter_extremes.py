"""The lowest and highest close of each AMD earnings quarter: days from the report, % moves and indicator readings on those days.

A quarter runs from the day after a report through the next report day. Closing prices. Known only afterwards, so this describes
the past and is not a rule. Writes results/amd_quarter_extremes.csv.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
raw = yf.download(["AMD", "QQQ", "SMH"], start="2022-06-01", end="2026-11-06", auto_adjust=True, progress=False)
raw.index = pd.DatetimeIndex(raw.index).tz_localize(None).normalize()
o, h, l, c, v = [raw[k]["AMD"].dropna() for k in ("Open", "High", "Low", "Close", "Volume")]
qqq, smh = raw["Close"]["QQQ"].reindex(c.index).ffill(), raw["Close"]["SMH"].reindex(c.index).ffill()
vix = pd.Series(json.loads((RES / "vix_close.json").read_text(encoding="utf-8")))
vix.index = pd.to_datetime(vix.index)
vix = vix.reindex(c.index, method="ffill")
idx = c.index
reports = sorted({int(idx.searchsorted(d)) for d in pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"]) if pd.Timestamp("2023-07-15") <= d <= idx[-1]})


def rsi(s, n):
    d = s.diff()
    return 100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean() / (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean())


stoch = (100 * (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min())).rolling(3).mean()
macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
reading = pd.DataFrame({"rsi14": rsi(c, 14), "stoch": stoch, "vs20d": c / c.rolling(20).mean() - 1, "vs50d": c / c.rolling(50).mean() - 1, "vs200d": c / c.rolling(200).mean() - 1, "off_1y_high": c / c.rolling(252, min_periods=120).max() - 1,
                        "off_3m_high": c / c.rolling(63).max() - 1, "volume": v / v.rolling(50).mean().shift(), "macd_above": macd > macd.ewm(span=9, adjust=False).mean(), "vix": vix, "qqq_above_100d": qqq > qqq.rolling(100).mean(), "smh_off_high": smh / smh.rolling(252, min_periods=120).max() - 1})
rows = []
for j, r in enumerate(reports):
    end = reports[j + 1] if j + 1 < len(reports) else len(c) - 1
    if end <= r:
        continue
    span = c.iloc[r + 1:end + 1]
    lo, hi = span.idxmin(), span.idxmax()
    base = c.iloc[r]
    for kind, day in (("low", lo), ("high", hi)):
        pos = idx.get_loc(day)
        rows.append({"report": idx[r].date(), "report_close": round(base, 2), "kind": kind, "date": day.date(), "close": round(c.loc[day], 2), "days_after": pos - r, "days_before_next": end - pos if j + 1 < len(reports) else np.nan, "vs_report": c.loc[day] / base - 1, **reading.loc[day].to_dict(),
                     "order": "low first" if lo < hi else "high first", "complete": j + 1 < len(reports), "quarter_days": end - r, "low_to_high": c.loc[hi] / c.loc[lo] - 1})
t = pd.DataFrame(rows)
t.to_csv(RES / "amd_quarter_extremes.csv", index=False)
pd.set_option("display.width", 240, "display.max_columns", 30, "display.max_rows", 60)
print(t.drop(columns=["report_close", "complete", "off_3m_high"]).to_string(index=False, float_format=lambda x: f"{x:.2f}"))
done = t[t.complete]
for kind in ("low", "high"):
    part = done[done.kind == kind]
    print(f"\n{kind}: {len(part)} quarters; days after report median {part.days_after.median():.0f} (range {part.days_after.min()}-{part.days_after.max()}); days before next median {part.days_before_next.median():.0f}; vs report median {part.vs_report.median():+.1%} (range {part.vs_report.min():+.1%} to {part.vs_report.max():+.1%})")
    print(f"  RSI median {part.rsi14.median():.0f} ({part.rsi14.min():.0f}-{part.rsi14.max():.0f}); stoch {part.stoch.median():.0f} ({part.stoch.min():.0f}-{part.stoch.max():.0f}); vs50d {part.vs50d.median():+.1%} ({part.vs50d.min():+.1%} to {part.vs50d.max():+.1%}); volume {part.volume.median():.2f}; MACD above signal {int(part.macd_above.sum())}; QQQ above 100d {int(part.qqq_above_100d.sum())}")
    print(f"  first third (days 1-21) {(part.days_after <= 21).sum()}, middle (22-42) {((part.days_after > 21) & (part.days_after <= 42)).sum()}, last (43+) {(part.days_after > 42).sum()}")
print("\norder:", done[done.kind == "low"].order.value_counts().to_dict())
print("low to high median", f"{done[done.kind == 'low'].low_to_high.median():+.0%}")
