"""A wide search for AMD signals that are right at least 75% of the time (user's bar, 2026-11-05). No backtest.

Hundreds of signals, alone and in pairs: lookback extremes, distance from averages, oscillators, candles, divergences, volume, retracements,
VWAP, sector and market context, VIX, earnings timing, volatility and time since the last turn. Past data only in every signal.
Searched on 2025-2026. 2024 played no part and is the check. Each signal counts once per episode (5 trading days apart).

"Works" (the trade goes right first, within 63 trading days; unresolved cases left out):
  wide: buy +15% before -15%; sell -15% before +15%.
  tight: buy +10% before -5%; sell -10% before +5%. This rewards buying near a low or selling near a high.
Because so many pairs are tried, the same search on data rotated by a random shift shows how many pass by luck.

Writes results/amd_ta_brainstorm.csv.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
BAR, MIN_N, MIN_N_CHECK = 0.75, 5, 3
ERAS = {"main": ("2025-01-01", "2026-11-06"), "check": ("2024-01-01", "2024-12-31")}
raw = yf.download(["AMD", "QQQ", "SMH"], start="2022-01-01", end="2026-11-06", auto_adjust=True, progress=False)
raw.index = pd.DatetimeIndex(raw.index).tz_localize(None).normalize()
o, h, l, c, v = [raw[k]["AMD"].dropna() for k in ("Open", "High", "Low", "Close", "Volume")]
idx = c.index
qqq, smh = raw["Close"]["QQQ"].reindex(idx).ffill(), raw["Close"]["SMH"].reindex(idx).ffill()
vix = pd.Series(json.loads((RES / "vix_close.json").read_text(encoding="utf-8")))
vix.index = pd.to_datetime(vix.index)
vix = vix.reindex(idx, method="ffill")
report_days = sorted({int(idx.searchsorted(d)) for d in pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"]) if idx[0] <= d <= idx[-1]})


def rsi(s, n):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def atr(n):
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def cross_up(a, b):
    return (a > b) & (a.shift() <= (b.shift() if isinstance(b, pd.Series) else b))


def cross_dn(a, b):
    return (a < b) & (a.shift() >= (b.shift() if isinstance(b, pd.Series) else b))


def stoch(n):
    return 100 * (c - l.rolling(n).min()) / (h.rolling(n).max() - l.rolling(n).min())


LOOKS = (5, 10, 15, 21, 30, 42, 63, 90, 126, 189, 252)
AVGS = (5, 10, 20, 30, 50, 100, 150, 200)
buy, sell, state = {}, {}, {}
sma = {n: c.rolling(n).mean() for n in AVGS}
ema = {n: c.ewm(span=n, adjust=False).mean() for n in AVGS}
rets = c.pct_change(fill_method=None)

for n in LOOKS:  # extremes and time since them
    buy[f"new {n}d low"] = l <= l.rolling(n).min()
    sell[f"new {n}d high"] = h >= h.rolling(n).max()
for n in (21, 42, 63, 126, 252):
    top, bottom = c.rolling(n).max(), c.rolling(n).min()
    for x in (10, 12.5, 15, 17.5, 20, 22.5, 25, 30, 35, 40, 50):
        buy[f"{x}% below {n}d high"] = c <= top * (1 - x / 100)
    for x in (20, 30, 40, 50, 75, 100, 150):
        sell[f"{x}% above {n}d low"] = c >= bottom * (1 + x / 100)
    since_high = c.rolling(n).apply(lambda w: len(w) - 1 - np.argmax(w), raw=True)
    since_low = c.rolling(n).apply(lambda w: len(w) - 1 - np.argmin(w), raw=True)
    for d in (10, 20, 30, 40):
        if d < n:
            buy[f"{d}+ days since {n}d high"] = since_high >= d
            sell[f"{d}+ days since {n}d low"] = since_low >= d
for n in AVGS:  # distance from averages, in percent and in ATRs
    for x in (5, 7.5, 10, 12.5, 15, 17.5, 20, 25, 30):
        buy[f"{x}% below {n}d avg"] = c <= sma[n] * (1 - x / 100)
        sell[f"{x}% above {n}d avg"] = c >= sma[n] * (1 + x / 100)
    buy[f"close back above {n}d avg"] = cross_up(c, sma[n])
    sell[f"close back below {n}d avg"] = cross_dn(c, sma[n])
    buy[f"close back above {n}d EMA"] = cross_up(c, ema[n])
    sell[f"close back below {n}d EMA"] = cross_dn(c, ema[n])
    state[f"above {n}d avg"] = c > sma[n]
    state[f"below {n}d avg"] = c < sma[n]
    state[f"{n}d avg rising"] = sma[n] > sma[n].shift(5)
    state[f"{n}d avg falling"] = sma[n] < sma[n].shift(5)
    a14 = atr(14)
    for x in (2, 3, 4, 5, 6):
        buy[f"{x} ATR below {n}d avg"] = (c - sma[n]) / a14 <= -x
        sell[f"{x} ATR above {n}d avg"] = (c - sma[n]) / a14 >= x
for a, b in ((5, 10), (5, 20), (10, 20), (10, 30), (10, 50), (20, 50), (30, 100), (50, 100), (50, 150), (50, 200), (100, 200)):
    buy[f"{a}d avg crosses above {b}d"] = cross_up(sma[a], sma[b])
    sell[f"{a}d avg crosses below {b}d"] = cross_dn(sma[a], sma[b])
    buy[f"{a}d EMA crosses above {b}d"] = cross_up(ema[a], ema[b])
    sell[f"{a}d EMA crosses below {b}d"] = cross_dn(ema[a], ema[b])
for n in (20, 50, 100):
    z = (c - c.rolling(n).mean()) / c.rolling(n).std()
    for x in (1.5, 2, 2.5, 3):
        buy[f"z {n}d below -{x}"] = z <= -x
        sell[f"z {n}d above {x}"] = z >= x
for n in (2, 3, 5, 7, 9, 14, 21, 28):  # RSI
    r = rsi(c, n)
    for x in (5, 10, 15, 20, 25, 30, 35, 40, 45):
        if x >= 20 or n <= 5:
            buy[f"RSI{n} below {x}"] = r < x
            sell[f"RSI{n} above {100 - x}"] = r > 100 - x
    for x in (20, 25, 30, 35, 40, 45):
        buy[f"RSI{n} back above {x}"] = cross_up(r, x)
        sell[f"RSI{n} back below {100 - x}"] = cross_dn(r, 100 - x)
weekly = c.resample("W-FRI").last().dropna()
for n in (5, 9, 14):
    r = rsi(weekly, n).shift(1).reindex(idx, method="ffill")  # the last finished week only
    for x in (30, 35, 40, 45, 50):
        buy[f"weekly RSI{n} below {x}"] = r < x
        sell[f"weekly RSI{n} above {100 - x}"] = r > 100 - x
for n in (5, 9, 14, 21):  # stochastic
    k = stoch(n)
    d = k.rolling(3).mean()
    for x in (5, 10, 20, 30):
        buy[f"stoch{n} below {x}"] = d < x
        sell[f"stoch{n} above {100 - x}"] = d > 100 - x
    buy[f"stoch{n} K over D below 20"] = cross_up(k, d) & (d < 20)
    sell[f"stoch{n} K under D above 80"] = cross_dn(k, d) & (d > 80)
    buy[f"stoch{n} back above 20"] = cross_up(d, 20)
    sell[f"stoch{n} back below 80"] = cross_dn(d, 80)
r14 = rsi(c, 14)
srsi = 100 * (r14 - r14.rolling(14).min()) / (r14.rolling(14).max() - r14.rolling(14).min())
for x in (5, 10, 20):
    buy[f"stochRSI below {x}"] = srsi < x
    sell[f"stochRSI above {100 - x}"] = srsi > 100 - x
tp = (h + l + c) / 3
for n in (14, 20, 40):
    cci = (tp - tp.rolling(n).mean()) / (0.015 * tp.rolling(n).apply(lambda w: np.abs(w - w.mean()).mean(), raw=True))
    for x in (100, 150, 200, 250):
        buy[f"CCI{n} below -{x}"] = cci < -x
        sell[f"CCI{n} above {x}"] = cci > x
    buy[f"CCI{n} back above -100"] = cross_up(cci, -100)
    sell[f"CCI{n} back below 100"] = cross_dn(cci, 100)
for n in (1, 2, 3, 5, 10, 21, 42, 63, 126):  # size of the recent move
    roc = c.pct_change(n, fill_method=None) * 100
    for x in (5, 7.5, 10, 12.5, 15, 20, 25, 30, 40, 50):
        if x <= 7 * n ** 0.5 + 5:
            buy[f"down {x}% in {n}d"] = roc <= -x
            sell[f"up {x}% in {n}d"] = roc >= x
down_run, up_run = (c < c.shift()).astype(int), (c > c.shift()).astype(int)
down_run = down_run.groupby((down_run == 0).cumsum()).cumsum()
up_run = up_run.groupby((up_run == 0).cumsum()).cumsum()
for x in (3, 4, 5, 6, 7):
    buy[f"{x}+ down days in a row"] = down_run >= x
    sell[f"{x}+ up days in a row"] = up_run >= x
for n, k in ((20, 2), (20, 2.5), (20, 3), (50, 2), (50, 2.5)):  # bands
    mid, sd = c.rolling(n).mean(), c.rolling(n).std()
    buy[f"below Bollinger {n}/{k}"] = c < mid - k * sd
    sell[f"above Bollinger {n}/{k}"] = c > mid + k * sd
    buy[f"back above Bollinger {n}/{k}"] = cross_up(c, mid - k * sd)
    sell[f"back below Bollinger {n}/{k}"] = cross_dn(c, mid + k * sd)
for n, k in ((20, 1.5), (20, 2), (20, 3), (50, 3)):
    ec, ar = c.ewm(span=n, adjust=False).mean(), atr(n)
    buy[f"below Keltner {n}/{k}"] = c < ec - k * ar
    sell[f"above Keltner {n}/{k}"] = c > ec + k * ar
macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
sig = macd.ewm(span=9, adjust=False).mean()
hist = macd - sig
buy["MACD crosses up"], sell["MACD crosses down"] = cross_up(macd, sig), cross_dn(macd, sig)
buy["MACD crosses up below zero"] = cross_up(macd, sig) & (macd < 0)
sell["MACD crosses down above zero"] = cross_dn(macd, sig) & (macd > 0)
buy["MACD histogram turns up below zero"] = (hist > hist.shift()) & (hist.shift() <= hist.shift(2)) & (hist < 0)
sell["MACD histogram turns down above zero"] = (hist < hist.shift()) & (hist.shift() >= hist.shift(2)) & (hist > 0)
rng = (h - l).replace(0, np.nan)
body = (c - o).abs()
lower, upper = pd.concat([o, c], axis=1).min(axis=1) - l, h - pd.concat([o, c], axis=1).max(axis=1)
vr = v / v.rolling(50).mean().shift()
buy["hammer"] = (lower >= 2 * body) & (upper <= body) & (c - l >= 0.6 * rng)
sell["shooting star"] = (upper >= 2 * body) & (lower <= body) & (h - c >= 0.6 * rng)
buy["bullish engulfing"] = (c > o) & (c.shift() < o.shift()) & (c >= o.shift()) & (o <= c.shift())
sell["bearish engulfing"] = (c < o) & (c.shift() > o.shift()) & (c <= o.shift()) & (o >= c.shift())
buy["closes in top quarter after a new 21d low"] = (l <= l.rolling(21).min()) & (c - l >= 0.75 * rng)
sell["closes in bottom quarter after a new 21d high"] = (h >= h.rolling(21).max()) & (h - c >= 0.75 * rng)
buy["key reversal up"] = (l < l.shift()) & (c > c.shift()) & (l <= l.rolling(21).min())
sell["key reversal down"] = (h > h.shift()) & (c < c.shift()) & (h >= h.rolling(21).max())
buy["gap down that closes up"] = (o < c.shift() * 0.98) & (c > o)
sell["gap up that closes down"] = (o > c.shift() * 1.02) & (c < o)
buy["inside day after a 21d low"] = (h < h.shift()) & (l > l.shift()) & (l.shift() <= l.rolling(21).min().shift())
sell["inside day after a 21d high"] = (h < h.shift()) & (l > l.shift()) & (h.shift() >= h.rolling(21).max().shift())
for x in (1.25, 1.5, 2, 3):  # volume
    buy[f"down day on {x}x volume"] = (c < c.shift()) & (vr >= x)
    sell[f"up day on {x}x volume"] = (c > c.shift()) & (vr >= x)
    buy[f"long lower wick on {x}x volume"] = (lower >= 0.5 * rng) & (vr >= x)
    sell[f"long upper wick on {x}x volume"] = (upper >= 0.5 * rng) & (vr >= x)
obv = (np.sign(c.diff()).fillna(0) * v).cumsum()
for n in (21, 42, 63):
    buy[f"OBV new {n}d low"] = obv <= obv.rolling(n).min()
    sell[f"OBV new {n}d high"] = obv >= obv.rolling(n).max()
    # divergence: price at a new extreme, but the oscillator is not
    buy[f"RSI divergence on new {n}d low"] = (l <= l.rolling(n).min()) & (r14 > r14.rolling(n).min() + 3)
    sell[f"RSI divergence on new {n}d high"] = (h >= h.rolling(n).max()) & (r14 < r14.rolling(n).max() - 3)
    buy[f"MACD divergence on new {n}d low"] = (l <= l.rolling(n).min()) & (hist > hist.rolling(n).min())
    sell[f"MACD divergence on new {n}d high"] = (h >= h.rolling(n).max()) & (hist < hist.rolling(n).max())
    buy[f"OBV divergence on new {n}d low"] = (l <= l.rolling(n).min()) & (obv > obv.rolling(n).min())
    sell[f"OBV divergence on new {n}d high"] = (h >= h.rolling(n).max()) & (obv < obv.rolling(n).max())
mfi_raw = tp * v
pos_flow = mfi_raw.where(tp > tp.shift(), 0).rolling(14).sum()
neg_flow = mfi_raw.where(tp < tp.shift(), 0).rolling(14).sum()
mfi = 100 - 100 / (1 + pos_flow / neg_flow)
for x in (10, 20, 30, 40):
    buy[f"MFI below {x}"] = mfi < x
    sell[f"MFI above {100 - x}"] = mfi > 100 - x
up_move, dn_move = h.diff(), -l.diff()
plus = up_move.where((up_move > dn_move) & (up_move > 0), 0.0).ewm(alpha=1 / 14, adjust=False).mean() / atr(14) * 100
minus = dn_move.where((dn_move > up_move) & (dn_move > 0), 0.0).ewm(alpha=1 / 14, adjust=False).mean() / atr(14) * 100
adx = ((plus - minus).abs() / (plus + minus) * 100).ewm(alpha=1 / 14, adjust=False).mean()
for x in (25, 30, 35, 40):
    buy[f"-DI above {x}"] = minus > x
    sell[f"+DI above {x}"] = plus > x
    state[f"ADX above {x}"] = adx > x
buy["+DI crosses above -DI"], sell["-DI crosses above +DI"] = cross_up(plus, minus), cross_up(minus, plus)
for n in (14, 25):
    aroon_up = h.rolling(n + 1).apply(lambda w: 100 * np.argmax(w) / n, raw=True)
    aroon_dn = l.rolling(n + 1).apply(lambda w: 100 * np.argmin(w) / n, raw=True)
    buy[f"Aroon{n} crosses up"], sell[f"Aroon{n} crosses down"] = cross_up(aroon_up, aroon_dn), cross_dn(aroon_up, aroon_dn)
ha_close = (o + h + l + c) / 4
ha_open = ((o + c) / 2).copy()
for i in range(1, len(ha_open)):
    ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2
buy["Heikin-Ashi turns up"] = (ha_close > ha_open) & (ha_close.shift() <= ha_open.shift())
sell["Heikin-Ashi turns down"] = (ha_close < ha_open) & (ha_close.shift() >= ha_open.shift())
for mult in (2, 3, 4):  # Supertrend
    mid, a = (h + l) / 2, atr(10)
    upper_band, lower_band = (mid + mult * a).values.copy(), (mid - mult * a).values.copy()
    trend = np.ones(len(c))
    cv = c.values
    for i in range(1, len(cv)):
        if cv[i - 1] <= upper_band[i - 1]:
            upper_band[i] = min(upper_band[i], upper_band[i - 1])
        if cv[i - 1] >= lower_band[i - 1]:
            lower_band[i] = max(lower_band[i], lower_band[i - 1])
        trend[i] = 1 if cv[i] > upper_band[i - 1] else -1 if cv[i] < lower_band[i - 1] else trend[i - 1]
    tr = pd.Series(trend, index=idx)
    buy[f"Supertrend {mult} turns up"], sell[f"Supertrend {mult} turns down"] = (tr > 0) & (tr.shift() < 0), (tr < 0) & (tr.shift() > 0)
# retracements of the last confirmed swing, using only swings already confirmed at the time
for swing in (0.15, 0.25):
    last_low, last_high, hi, lo, way = np.nan, np.nan, 0, 0, 0
    lows, highs = np.full(len(c), np.nan), np.full(len(c), np.nan)
    cv = c.values
    for i in range(1, len(cv)):
        if cv[i] > cv[hi]:
            hi = i
        if cv[i] < cv[lo]:
            lo = i
        if way >= 0 and cv[i] <= cv[hi] * (1 - swing):
            last_high, way, lo = cv[hi], -1, i
        elif way <= 0 and cv[i] >= cv[lo] * (1 + swing):
            last_low, way, hi = cv[lo], 1, i
        lows[i], highs[i] = last_low, last_high
    lo_s, hi_s = pd.Series(lows, index=idx), pd.Series(highs, index=idx)
    top = pd.concat([hi_s, c.rolling(63).max()], axis=1).max(axis=1)
    bottom = pd.concat([lo_s, c.rolling(63).min()], axis=1).min(axis=1)
    for f in (38.2, 50, 61.8, 78.6, 100):
        buy[f"retraced {f}% of a {int(swing * 100)}% swing"] = c <= top - (top - lo_s) * f / 100
        sell[f"rebounded {f}% of a {int(swing * 100)}% swing"] = c >= bottom + (hi_s - bottom) * f / 100
    buy[f"tested the last {int(swing * 100)}% swing low within 5%"] = (c <= lo_s * 1.05) & (c >= lo_s * 0.95)
    buy[f"higher low above the last {int(swing * 100)}% swing low"] = (c.rolling(5).min() > lo_s * 1.02) & (c.rolling(5).min() < lo_s * 1.15) & (c > c.shift())
    sell[f"tested the last {int(swing * 100)}% swing high within 5%"] = (c >= hi_s * 0.95) & (c <= hi_s * 1.05)
    sell[f"lower high below the last {int(swing * 100)}% swing high"] = (c.rolling(5).max() < hi_s * 0.98) & (c.rolling(5).max() > hi_s * 0.85) & (c < c.shift())
# VWAP anchored at the last report
anchor = pd.Series(np.nan, index=idx)
anchor.iloc[report_days] = range(len(report_days))
anchor = anchor.ffill()
pv = (tp * v).groupby(anchor).cumsum()
vv = v.groupby(anchor).cumsum()
vwap = pv / vv
for x in (0, 5, 10, 15):
    buy[f"{x}% below VWAP from the last report"] = c <= vwap * (1 - x / 100)
    sell[f"{x}% above VWAP from the last report"] = c >= vwap * (1 + x / 100)
# sector, market, fear
for name, other in (("SMH", smh), ("QQQ", qqq)):
    ratio = c / other
    for n in (21, 42, 63, 126):
        buy[f"AMD/{name} new {n}d low"] = ratio <= ratio.rolling(n).min()
        sell[f"AMD/{name} new {n}d high"] = ratio >= ratio.rolling(n).max()
    for n in (21, 63):
        gap = c.pct_change(n, fill_method=None) - other.pct_change(n, fill_method=None)
        for x in (10, 20, 30, 50):
            buy[f"AMD trails {name} by {x}% over {n}d"] = gap <= -x / 100
            sell[f"AMD leads {name} by {x}% over {n}d"] = gap >= x / 100
    for x in (3, 5, 7.5, 10, 15, 20):
        state[f"{name} {x}%+ below its 1y high"] = other <= other.rolling(252).max() * (1 - x / 100)
        state[f"{name} within {x}% of its 1y high"] = other >= other.rolling(252).max() * (1 - x / 100)
    other_rsi = rsi(other, 14)
    for x in (30, 35, 40, 45):
        state[f"{name} RSI below {x}"] = other_rsi < x
        state[f"{name} RSI above {100 - x}"] = other_rsi > 100 - x
    for n in (50, 100, 200):
        state[f"{name} above {n}d avg"] = other > other.rolling(n).mean()
        state[f"{name} below {n}d avg"] = other < other.rolling(n).mean()
for x in (15, 18, 20, 22, 25, 30, 35, 40):
    state[f"VIX above {x}"] = vix > x
    state[f"VIX below {x}"] = vix < x
    buy[f"VIX back below {x}"] = cross_dn(vix, x)
    sell[f"VIX back above {x}"] = cross_up(vix, x)
for x in (15, 25, 40):
    buy[f"VIX up {x}% in 5d"] = vix >= vix.shift(5) * (1 + x / 100)
    sell[f"VIX down {x}% in 5d"] = vix <= vix.shift(5) * (1 - x / 100)
# earnings timing
days_since, days_to = pd.Series(np.nan, index=idx), pd.Series(np.nan, index=idx)
reports = np.array(report_days)
for i in range(len(idx)):
    past, later = reports[reports < i], reports[reports >= i]
    days_since.iloc[i] = i - past[-1] if len(past) else np.nan
    days_to.iloc[i] = later[0] - i if len(later) else 63 - (days_since.iloc[i] if len(past) else 0)
for a, b in ((1, 5), (6, 10), (11, 15), (16, 20), (21, 30), (31, 40), (41, 50), (51, 65)):
    state[f"days {a}-{b} after a report"] = (days_since >= a) & (days_since <= b)
for a, b in ((0, 3), (4, 7), (8, 12), (13, 20), (21, 30)):
    state[f"{a}-{b} days before a report"] = (days_to >= a) & (days_to <= b)
reaction = pd.Series(np.nan, index=idx)
for r in report_days:
    if r + 1 < len(c):
        reaction.iloc[r + 1:] = c.iloc[r + 1] / c.iloc[r] - 1
for x in (0, 5, 10):
    state[f"last report's next day down {x}%+"] = reaction <= -x / 100
    state[f"last report's next day up {x}%+"] = reaction >= x / 100
# volatility
vol10 = rets.rolling(10).std() * np.sqrt(252)
vol63 = rets.rolling(63).std() * np.sqrt(252)
for x in (40, 60, 80, 100):
    state[f"10d volatility above {x}%"] = vol10 > x / 100
    state[f"10d volatility below {x}%"] = vol10 < x / 100
state["10d volatility above 63d"] = vol10 > vol63
state["10d volatility below 63d"] = vol10 < vol63
width = 4 * c.rolling(20).std() / c.rolling(20).mean()
state["Bollinger width in its top fifth"] = width.rolling(126).rank(pct=True) >= 0.8
state["Bollinger width in its bottom fifth"] = width.rolling(126).rank(pct=True) <= 0.2
for side in (buy, sell):
    side.update({f"[{k}]": f for k, f in state.items()})  # states only count in a pair; marked with brackets
print(f"signals: buy {len(buy)}, sell {len(sell)}", flush=True)

closes = c.values
n_all = len(closes)


def outcome(up, down, side):
    """+1 if the trade goes right first, 0 if wrong first, nan if neither within 63 bars."""
    out = np.full(n_all, np.nan)
    for i in range(n_all):
        win, lose = (1 + up, 1 - down) if side == "buy" else (1 - up, 1 + down)
        base = closes[i]
        for x in closes[i + 1:i + 64]:
            if (side == "buy" and x >= base * win) or (side == "sell" and x <= base * win):
                out[i] = 1.0
                break
            if (side == "buy" and x <= base * lose) or (side == "sell" and x >= base * lose):
                out[i] = 0.0
                break
    return out


masks = {era: (idx >= a) & (idx <= b) for era, (a, b) in ERAS.items()}
outcomes = {side: {"wide": outcome(0.15, 0.15, side), "tight": outcome(0.10, 0.05, side)} for side in ("buy", "sell")}
for side in outcomes:
    for era, m in masks.items():
        print(f"{side} on any day, {era}: wide {np.nanmean(outcomes[side]['wide'][m]):.0%}, tight {np.nanmean(outcomes[side]['tight'][m]):.0%}", flush=True)


def starts_of(arr):
    on = np.nonzero(arr)[0]
    if not len(on):
        return on
    keep = np.append(True, np.diff(on) > 5)
    return on[keep]


def score_arrays(side, table, wide, tight, shift=0):
    """All singles and pairs, on the main era. Returns the ones passing on either measure."""
    m = masks["main"]
    w, t = np.roll(wide, shift), np.roll(tight, shift)
    names = list(table)
    arr = {k: table[k].reindex(idx).fillna(False).values.astype(bool) & m for k in names}
    candidates = [(k,) for k in names if not k.startswith("[")]
    trig = [k for k in names if not k.startswith("[") and arr[k].sum() >= 3]
    for i, a in enumerate(trig):
        for b in names:
            if b != a and (b.startswith("[") or names.index(b) > names.index(a)) and arr[b].sum() >= 3:
                candidates.append((a, b))
    out = []
    for combo in candidates:
        flag = arr[combo[0]] if len(combo) == 1 else arr[combo[0]] & arr[combo[1]]
        s = starts_of(flag)
        if len(s) < MIN_N:
            continue
        rw, rt = w[s], t[s]
        rw, rt = rw[np.isfinite(rw)], rt[np.isfinite(rt)]
        if len(rw) >= MIN_N - 1 and rw.mean() >= BAR or len(rt) >= MIN_N - 1 and rt.mean() >= BAR:
            out.append((combo, len(s), rw.mean() if len(rw) else np.nan, len(rw), rt.mean() if len(rt) else np.nan, len(rt)))
    return out, len(candidates)


def check(combo, table, side):
    m = masks["check"]
    flag = table[combo[0]].reindex(idx).fillna(False).values.astype(bool) & m
    if len(combo) == 2:
        flag = flag & table[combo[1]].reindex(idx).fillna(False).values.astype(bool)
    s = starts_of(flag)
    w, t = outcomes[side]["wide"][s], outcomes[side]["tight"][s]
    w, t = w[np.isfinite(w)], t[np.isfinite(t)]
    return len(s), (w.mean() if len(w) else np.nan), len(w), (t.mean() if len(t) else np.nan), len(t)


def main():
    rows = []
    rng_gen = np.random.default_rng(3)
    pd.set_option("display.width", 220, "display.max_columns", 20, "display.max_rows", 80, "display.max_colwidth", 70)
    for side, table in (("buy", buy), ("sell", sell)):
        found, tested = score_arrays(side, table, outcomes[side]["wide"], outcomes[side]["tight"])
        lucky = []
        for _ in range(5):
            shift = int(rng_gen.integers(40, n_all - 40))
            lucky.append(len(score_arrays(side, table, outcomes[side]["wide"], outcomes[side]["tight"], shift)[0]))
        print(f"\n{side}: tested {tested} singles and pairs; pass on real data {len(found)}; pass on rotated data {lucky}", flush=True)
        for combo, n, rw, nw, rt, nt in found:
            cn, cw, cnw, ct, cnt = check(combo, table, side)
            rows.append({"side": side, "signal": " + ".join(combo), "size": len(combo), "n": n, "wide": rw, "wide_n": nw, "tight": rt, "tight_n": nt, "n_2024": cn, "wide_2024": cw, "wide_n_2024": cnw, "tight_2024": ct, "tight_n_2024": cnt})
    t = pd.DataFrame(rows)
    t.to_csv(RES / "amd_ta_brainstorm.csv", index=False)
    show = ["signal", "n", "wide", "wide_n", "tight", "tight_n", "n_2024", "wide_2024", "wide_n_2024", "tight_2024", "tight_n_2024"]
    fmt = lambda x: f"{x:.2f}"
    for side in ("buy", "sell"):
        part = t[t.side == side]
        if part.empty:
            print(f"\n{side}: nothing passed")
            continue
        print(f"\n=== {side}: passed on 2025-26 {len(part)}; singles {(part['size'] == 1).sum()}")
        print("singles, most signals first")
        print(part[part["size"] == 1].sort_values(["n", "wide"], ascending=False).head(15)[show].to_string(index=False, float_format=fmt))
        for label, col, nn in (("wide", "wide", "wide_n"), ("tight", "tight", "tight_n")):
            held = part[(part[col] >= BAR) & (part[f"{col}_2024"] >= BAR) & (part[f"{nn}_2024"] >= MIN_N_CHECK)]
            print(f"\nalso at 75%+ on {label} in 2024 with at least {MIN_N_CHECK} resolved: {len(held)} (singles {(held['size'] == 1).sum()})")
            print(held.sort_values(["n", nn], ascending=False).head(15)[show].to_string(index=False, float_format=fmt))


if __name__ == "__main__":
    main()
