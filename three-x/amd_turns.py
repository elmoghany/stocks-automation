"""Study AMD's major lows and highs over the last 3 years: what was true at each one, including earnings timing.

A swing counts once the close has reversed by the threshold (zigzag). That is only known afterwards, so this is a study of
hindsight, not a trading rule. "Perfect" is the multiple from buying every low and selling every high: a ceiling.
The percentile columns compare a turn's reading with every day in the window, so 5 means lower than 95% of days.

Writes results/amd_turns.csv.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
FROM, END = "2023-11-06", "2026-11-05"


def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def zigzag(c, threshold):
    """Swing lows and highs of close c, each confirmed by a reversal of at least threshold."""
    turns, high_i, low_i, going = [], 0, 0, 0
    v = c.values
    for i in range(1, len(v)):
        if v[i] > v[high_i]:
            high_i = i
        if v[i] < v[low_i]:
            low_i = i
        if going >= 0 and v[i] <= v[high_i] * (1 - threshold):
            turns.append((high_i, "high"))
            going, low_i = -1, i
        elif going <= 0 and v[i] >= v[low_i] * (1 + threshold):
            turns.append((low_i, "low"))
            going, high_i = 1, i
    return turns


raw = yf.download(["AMD", "QQQ", "SMH"], start="2022-06-01", end=END, auto_adjust=True, progress=False)
raw.index = pd.DatetimeIndex(raw.index).tz_localize(None).normalize()
amd, vol = raw["Close"]["AMD"].dropna(), raw["Volume"]["AMD"].dropna()
qqq, smh = raw["Close"]["QQQ"].reindex(amd.index).ffill(), raw["Close"]["SMH"].reindex(amd.index).ffill()
vix = pd.Series(json.loads((RES / "vix_close.json").read_text(encoding="utf-8")))
vix.index = pd.to_datetime(vix.index)
reports = pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"])
idx = amd.index
report_pos = np.array(sorted({int(idx.searchsorted(d)) for d in reports if idx[0] <= d <= idx[-1]}))

week = amd.resample("W-FRI").last().dropna()
features = pd.DataFrame({
    "vs_200d": amd / amd.rolling(200).mean() - 1,
    "vs_50d": amd / amd.rolling(50).mean() - 1,
    "off_1y_high": amd / amd.rolling(252, min_periods=120).max() - 1,
    "ret_3m": amd.pct_change(63),
    "rsi_14d": rsi(amd, 14),
    "rsi_14w": rsi(week, 14).reindex(idx, method="ffill"),
    "volume_vs_50d": vol / vol.rolling(50).mean(),
    "qqq_vs_200d": qqq / qqq.rolling(200).mean() - 1,
    "qqq_off_high": qqq / qqq.rolling(252, min_periods=120).max() - 1,
    "amd_vs_smh_3m": amd.pct_change(63) - smh.pct_change(63),
    "vix": vix.reindex(idx, method="ffill"),
})
days_to_next = pd.Series(np.nan, index=idx)
days_since = pd.Series(np.nan, index=idx)
for i in range(len(idx)):
    later, earlier = report_pos[report_pos >= i], report_pos[report_pos < i]
    days_to_next.iloc[i] = later[0] - i if len(later) else np.nan
    days_since.iloc[i] = i - earlier[-1] if len(earlier) else np.nan
features["weeks_to_report"] = days_to_next / 5
features["weeks_since_report"] = days_since / 5

window = amd[amd.index >= FROM]
held = window.iloc[-1] / window.iloc[0]
print(f"AMD held {window.index[0].date()} to {window.index[-1].date()}: {held:.2f}x. Reports in window: {sum(1 for r in reports if pd.Timestamp(FROM) <= r <= idx[-1])}")
all_rows = []
for threshold in (0.20, 0.30, 0.40):
    turns = zigzag(window, threshold)
    v = window.values
    lows_highs = [(i, kind) for i, kind in turns]
    money, entry = 1.0, None
    for i, kind in lows_highs:
        if kind == "low":
            entry = v[i]
        elif entry is not None:
            money, entry = money * v[i] / entry, None
    if entry is not None:
        money *= v[-1] / entry
    gaps = np.diff([i for i, _ in lows_highs]) / 21
    print(f"\n--- swings of {threshold:.0%} or more: {len(lows_highs)} turns, one every {gaps.mean():.1f} months; perfect buy-low sell-high {money:.1f}x; stock held {held:.2f}x")
    rows = []
    for j, (i, kind) in enumerate(lows_highs):
        d = window.index[i]
        row = {"threshold": threshold, "date": d.date(), "turn": kind, "close": round(v[i], 2)}
        row["move_from_prior"] = v[i] / v[lows_highs[j - 1][0]] - 1 if j else np.nan
        row.update(features.loc[d].to_dict())
        rows.append(row)
    table = pd.DataFrame(rows)
    all_rows.append(table)
    pd.set_option("display.width", 240, "display.max_columns", 30, "display.max_rows", 100)
    print(table.drop(columns=["threshold", "amd_vs_smh_3m", "qqq_vs_200d"]).to_string(index=False, float_format=lambda x: f"{x:.2f}"))

study = pd.concat(all_rows)
study.to_csv(RES / "amd_turns.csv", index=False)
in_window = features[features.index >= FROM]
names = [c for c in features.columns]
base = study[study.threshold == 0.30]
print("\n--- 30% swings: median reading at lows and highs, against all days, and how low or high that sits (percentile of all days)")
rows = []
for name in names:
    day = in_window[name].dropna()
    lo, hi = base[base.turn == "low"][name].astype(float), base[base.turn == "high"][name].astype(float)
    rows.append({"reading": name, "all_days": day.median(), "at_lows": lo.median(), "lows_pct": (day < lo.median()).mean() * 100, "lows_min": lo.min(), "lows_max": lo.max(),
                 "at_highs": hi.median(), "highs_pct": (day < hi.median()).mean() * 100, "highs_min": hi.min(), "highs_max": hi.max()})
print(pd.DataFrame(rows).to_string(index=False, float_format=lambda x: f"{x:.2f}"))

print("\n--- when turns fall in the earnings cycle (weeks to the next report; a quarter is about 13 weeks)")
for threshold in (0.20, 0.30, 0.40):
    part = study[study.threshold == threshold]
    for kind in ("low", "high"):
        w = part[part.turn == kind].weeks_since_report.astype(float)
        buckets = pd.cut(w, [0, 2, 4, 8, 11, 14]).value_counts().sort_index()
        print(f"{threshold:.0%} {kind}s, weeks since the last report: " + ", ".join(f"{a.left}-{a.right}: {b}" for a, b in buckets.items()))
