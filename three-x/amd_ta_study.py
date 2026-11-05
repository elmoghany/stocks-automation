"""Which technical signals line up with AMD's real lows and highs in 2025-2026, and with the day-count rule's dates? No backtest.

Lows and highs are swings of 15% or more by close, known only afterwards. Each signal is split into separate episodes: firing again
within 5 trading days counts as the same episode. A hit is an episode that starts within 10 trading days of a real low (for buy
signals) or high (for sell signals). "Found" is the share of lows or highs with a hit. "Right" is the share of episodes that were hits.
"Chance" is how often an episode would be right on random dates, given how many lows or highs there are.

Writes results/amd_ta_study.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
FROM, NEAR = "2025-01-01", 10
raw = yf.download("AMD", start="2022-06-01", end="2026-11-06", auto_adjust=True, progress=False)
df = pd.DataFrame({k: raw[k].squeeze() for k in ("Open", "High", "Low", "Close", "Volume")}).dropna()
df.columns = [c.lower() for c in df.columns]
df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
c, h, l, v = df.close, df.high, df.low, df.volume


def rsi(s, n):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


sma = {n: c.rolling(n).mean() for n in (10, 20, 50, 100, 200)}
r14, r7 = rsi(c, 14), rsi(c, 7)
stoch = 100 * (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min())
macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
sig = macd.ewm(span=9, adjust=False).mean()
mid, sd = c.rolling(20).mean(), c.rolling(20).std()
up_band, dn_band = mid + 2 * sd, mid - 2 * sd
vol_ratio = v / v.rolling(50).mean().shift()


def cross_up(a, b):
    return (a > b) & (a.shift() <= b.shift())


buy = {f"new {n}-day low": l <= l.rolling(n).min() for n in (21, 42, 63, 126, 252)}
buy.update({f"RSI14 below {x}": r14 < x for x in (25, 30, 35, 40)})
buy.update({f"RSI7 below {x}": r7 < x for x in (20, 25, 30)})
buy.update({f"RSI14 back above {x}": cross_up(r14, pd.Series(x, index=c.index)) for x in (30, 35, 40)})
buy.update({f"Stochastic below {x}": stoch < x for x in (10, 20)})
buy["below lower Bollinger band"] = c < dn_band
buy["back above lower Bollinger band"] = cross_up(c, dn_band)
buy.update({f"{x}% below 50-day average": c <= sma[50] * (1 - x / 100) for x in (10, 15, 20)})
buy.update({f"{x}% below 20-day average": c <= sma[20] * (1 - x / 100) for x in (10, 15)})
buy.update({f"{x}% below 3-month high": c <= c.rolling(63).max() * (1 - x / 100) for x in (15, 20, 25, 30)})
buy.update({f"{a}-day average crosses above {b}-day": cross_up(sma[a], sma[b]) for a, b in ((10, 20), (10, 50), (20, 50), (50, 100), (50, 200))})
buy.update({f"close crosses above {n}-day average": cross_up(c, sma[n]) for n in (20, 50, 100, 200)})
buy["MACD crosses up"] = cross_up(macd, sig)
buy["MACD crosses up below zero"] = cross_up(macd, sig) & (macd < 0)
buy["down day on 1.5x volume"] = (c < c.shift()) & (vol_ratio >= 1.5)

sell = {f"new {n}-day high": h >= h.rolling(n).max() for n in (21, 42, 63, 126, 252)}
sell.update({f"RSI14 above {x}": r14 > x for x in (65, 70, 75, 80)})
sell.update({f"RSI7 above {x}": r7 > x for x in (75, 80, 85)})
sell.update({f"RSI14 back below {x}": cross_up(pd.Series(x, index=c.index), r14) for x in (65, 70, 75)})
sell.update({f"Stochastic above {x}": stoch > x for x in (80, 90)})
sell["above upper Bollinger band"] = c > up_band
sell["back below upper Bollinger band"] = cross_up(up_band, c)
sell.update({f"{x}% above 50-day average": c >= sma[50] * (1 + x / 100) for x in (15, 20, 25, 30)})
sell.update({f"{x}% above 20-day average": c >= sma[20] * (1 + x / 100) for x in (10, 15, 20)})
sell.update({f"{a}-day average crosses below {b}-day": cross_up(sma[b], sma[a]) for a, b in ((10, 20), (10, 50), (20, 50), (50, 100), (50, 200))})
sell.update({f"close crosses below {n}-day average": cross_up(sma[n], c) for n in (20, 50, 100, 200)})
sell["MACD crosses down"] = cross_up(sig, macd)
sell["MACD crosses down above zero"] = cross_up(sig, macd) & (macd > 0)
sell["up day on 1.5x volume"] = (c > c.shift()) & (vol_ratio >= 1.5)

window = c[c.index >= FROM]
values = window.values
lows, highs, hi, lo, way = [], [], 0, 0, 0
for i in range(1, len(values)):
    if values[i] > values[hi]:
        hi = i
    if values[i] < values[lo]:
        lo = i
    if way >= 0 and values[i] <= values[hi] * 0.85:
        highs.append(hi)
        way, lo = -1, i
    elif way <= 0 and values[i] >= values[lo] * 1.15:
        lows.append(lo)
        way, hi = 1, i
print("lows : " + ", ".join(f"{window.index[i].date()} {values[i]:.2f}" for i in lows))
print("highs: " + ", ".join(f"{window.index[i].date()} {values[i]:.2f}" for i in highs))
print(f"last close {values[-1]:.2f} on {window.index[-1].date()}")


def episodes(flag):
    on = np.nonzero(flag.reindex(window.index).fillna(False).values)[0]
    out = []
    for i in on:
        if not out or i - last > 5:
            out.append(i)
        last = i
    return np.array(out)


def rate(name, flag, targets):
    e = episodes(flag)
    if not len(e) or not len(targets):
        return {"signal": name, "episodes": len(e), "found": 0.0, "right": 0.0, "chance": 0.0, "days_on": float(flag.reindex(window.index).fillna(False).mean())}
    gaps = np.abs(e[:, None] - np.array(targets)[None, :])
    near_any = np.zeros(len(window), dtype=bool)
    for t in targets:
        near_any[max(0, t - NEAR):t + NEAR + 1] = True
    return {"signal": name, "episodes": len(e), "found": float((gaps.min(axis=0) <= NEAR).mean()), "right": float((gaps.min(axis=1) <= NEAR).mean()), "chance": float(near_any.mean()),
            "days_on": float(flag.reindex(window.index).fillna(False).mean())}


pd.set_option("display.width", 200, "display.max_rows", 80, "display.max_colwidth", 40)
tables = []
for side, signals, targets in (("BUY, against real lows", buy, lows), ("SELL, against real highs", sell, highs)):
    t = pd.DataFrame([rate(k, f, targets) for k, f in signals.items()])
    t["score"] = 2 * t.found * t.right / (t.found + t.right).replace(0, np.nan)
    t["side"] = side.split(",")[0]
    tables.append(t)
    print(f"\n{side}: {len(targets)} targets")
    print(t.sort_values("score", ascending=False).drop(columns="side").to_string(index=False, float_format=lambda x: f"{x:.2f}"))
pd.concat(tables).to_csv(RES / "amd_ta_study.csv", index=False)

trades = pd.read_csv(RES / "amd_grid_2024_trades.csv")
trades = trades[pd.to_datetime(trades.bought) >= "2025-05-01"]
reading = pd.DataFrame({"RSI14": r14, "RSI7": r7, "stoch": stoch, "vs20d": c / sma[20] - 1, "vs50d": c / sma[50] - 1, "vs200d": c / sma[200] - 1, "off_3m_high": c / c.rolling(63).max() - 1, "off_3m_low": c / c.rolling(63).min() - 1, "macd_up": (macd > sig).astype(int), "above_up_band": (c > up_band).astype(int)})
print("\nday-count rule's buy dates (previous close, the signal day):")
for x in trades.itertuples():
    d = c.index[c.index < pd.Timestamp(x.bought)][-1]
    print(f"  {d.date()} gain {x.gain:+.0%}  " + "  ".join(f"{k} {reading.loc[d, k]:.2f}" for k in reading.columns))
print("day-count rule's sell dates:")
for x in trades.itertuples():
    d = c.index[c.index < pd.Timestamp(x.sold)][-1]
    print(f"  {d.date()} gain {x.gain:+.0%}  " + "  ".join(f"{k} {reading.loc[d, k]:.2f}" for k in reading.columns))
print("\nreadings at real lows:")
for i in lows:
    d = window.index[i]
    print(f"  {d.date()} {values[i]:.2f}  " + "  ".join(f"{k} {reading.loc[d, k]:.2f}" for k in reading.columns))
print("readings at real highs:")
for i in highs:
    d = window.index[i]
    print(f"  {d.date()} {values[i]:.2f}  " + "  ".join(f"{k} {reading.loc[d, k]:.2f}" for k in reading.columns))
