"""Signal library for Vibe-Trading's runner. sweep.py substitutes the PARAMS literal.

Every family decides from data up to and including the bar's close; Vibe's engine
shifts the signal one bar and fills at the next open. Long-only, weight <= 1 per
book: no margin, shorting or options (project hard rules).
"""
from typing import Dict

import numpy as np
import pandas as pd

PARAMS = {"family": "bh"}


def _rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _atr(df, n):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _latch(enter, leave):
    """Long from an enter bar until a leave bar; leave wins a tie."""
    out, on = [], False
    for e, x in zip(enter.fillna(False).values, leave.fillna(False).values):
        if x:
            on = False
        elif e:
            on = True
        out.append(1.0 if on else 0.0)
    return pd.Series(out, index=enter.index)


def _single(df, p):
    """Target exposure in [0, 1] for one stock."""
    f, c = p["family"], df["close"]
    if f == "bh":
        return pd.Series(1.0, index=c.index)
    if f == "sma_trend":
        return (c > c.rolling(p["n"]).mean()).astype(float)
    if f == "sma_cross":
        return (c.rolling(p["fast"]).mean() > c.rolling(p["slow"]).mean()).astype(float)
    if f == "donchian":
        return _latch(c > df["high"].shift().rolling(p["entry"]).max(),
                      c < df["low"].shift().rolling(p["exit"]).min())
    if f == "macd":
        m = c.ewm(span=p["fast"], adjust=False).mean() - c.ewm(span=p["slow"], adjust=False).mean()
        s = (m > m.ewm(span=p["signal"], adjust=False).mean()).astype(float)
        return s * (c > c.rolling(200).mean()).astype(float) if p.get("trend") else s
    if f == "rsi_pullback":
        trend = c > c.rolling(p.get("trend_n", 200)).mean()
        return _latch((_rsi(c, p["n"]) < p["th"]) & trend, c > c.rolling(p["exit_n"]).mean())
    if f == "bb_revert":
        mid, sd = c.rolling(p["n"]).mean(), c.rolling(p["n"]).std()
        enter = c < mid - p["k"] * sd
        if p.get("trend"):
            enter = enter & (c > c.rolling(200).mean())
        return _latch(enter, c > mid)
    if f == "atr_trail":
        enter = c > df["high"].shift().rolling(p["entry"]).max()
        atr = _atr(df, 20).values
        out, on, peak = [], False, 0.0
        for i, (ci, e) in enumerate(zip(c.values, enter.fillna(False).values)):
            if on:
                peak = max(peak, ci)
                if ci < peak - p["k"] * atr[i]:
                    on = False
            elif e:
                on, peak = True, ci
            out.append(1.0 if on else 0.0)
        return pd.Series(out, index=c.index)
    if f == "abs_mom":
        return (c.pct_change(p["n"]) > 0).astype(float)
    if f == "vol_target":
        vol = c.pct_change().rolling(20).std() * np.sqrt(252)
        w = (p["target"] / vol).clip(upper=1.0).fillna(0.0)
        return (w * (c > c.rolling(p["n"]).mean()).astype(float)).round(1)
    if f == "dip_buy":
        hi = c.rolling(252, min_periods=60).max()
        return _latch(c < hi * (1 - p["dd"]), c >= hi * (1 - p["exit_dd"]))
    if f == "gap_drift":
        # Earnings-style shock: gap up on heavy volume that holds into the close, then drift.
        gap = df["open"] / c.shift() - 1
        shock = (gap >= p["gap"]) & (c > df["open"]) & (df["volume"] > p["vol_mult"] * df["volume"].rolling(20).mean())
        out, on, age, stop = [], False, 0, 0.0
        for ci, lo, hit in zip(c.values, df["low"].values, shock.fillna(False).values):
            if hit:
                on, age, stop = True, 0, lo
            elif on:
                age += 1
                if age >= p["hold"] or ci < stop:
                    on = False
            out.append(1.0 if on else 0.0)
        return pd.Series(out, index=c.index)
    if f == "high_52w":
        return _latch(c >= c.rolling(252, min_periods=120).max() * (1 - p["near"]), c < c.rolling(p["exit_n"]).mean())
    if f == "squeeze":
        mid, sd = c.rolling(20).mean(), c.rolling(20).std()
        width = (4 * sd / mid)
        calm = width.rolling(120).rank(pct=True).shift() < p["pct"]
        return _latch(calm & (c > mid + 2 * sd), c < c.rolling(p["exit_n"]).mean())
    if f == "down_days":
        streak = (c < c.shift()).astype(int)
        for _ in range(p["days"] - 1):
            streak = streak * (c.shift(_ + 1) < c.shift(_ + 2)).astype(int)
        return _latch((streak > 0) & (c > c.rolling(200).mean()), c > c.shift())
    if f == "rs_leader":
        rel = c / df.attrs["bench"].reindex(c.index).ffill()
        return ((rel > rel.rolling(p["n"]).mean()) & (c > c.rolling(p["trend_n"]).mean())).astype(float)
    if f == "overnight":
        # Hourly bars: long from the last bar's open until the next morning's open.
        t = c.index.tz_localize(None) if c.index.tz is None else c.index.tz_convert("America/New_York").tz_localize(None)
        last_bar = pd.Series(t.date, index=c.index).shift(-2) != pd.Series(t.date, index=c.index)
        return last_bar.astype(float).where(pd.Series(t.date, index=c.index).shift(-1) == pd.Series(t.date, index=c.index), 0.0)
    if f == "external":
        # Dated decisions from an outside source (TradingAgents ratings), already mapped to weights.
        s = pd.Series({pd.Timestamp(k): float(v) for k, v in p["by_code"][df.attrs.get("code", "")].items()})
        return s.sort_index().reindex(c.index.tz_localize(None), method="ffill").fillna(0.0).set_axis(c.index)
    if f == "seasonal":
        return pd.Series(np.isin(c.index.month, p["months"]).astype(float), index=c.index)
    if f == "turn_of_month":
        idx = pd.Series(range(len(c)), index=c.index)
        ym = c.index.to_period("M")
        from_end = idx.groupby(ym).transform(lambda s: len(s) - 1 - (s - s.iloc[0]))
        from_start = idx.groupby(ym).transform(lambda s: s - s.iloc[0])
        return ((from_end < p["before"]) | (from_start < p["after"])).astype(float)
    raise ValueError(f)


def _rotate(data, codes, p):
    """Hold the stronger of the tradable names by n-day momentum.

    When neither has positive momentum: with p["cash"] go flat, otherwise keep the last pick.
    """
    closes = pd.concat([data[k]["close"].rename(k) for k in codes], axis=1).ffill()
    mom = closes.pct_change(p["n"])
    if p.get("vol_adj"):
        mom = mom / closes.pct_change().rolling(p["n"]).std()
    if p.get("trend_n"):
        mom = mom.where(closes > closes.rolling(p["trend_n"]).mean())
    best = mom.where(mom > 0).idxmax(axis=1)
    if p.get("cash"):
        best = best.fillna("")  # "" is flat; the ffill below must not bring the last pick back
    if p.get("every"):
        keep = pd.Series(range(len(best)), index=best.index) % p["every"] == 0
        best = best.where(keep).ffill()
    return {k: (best == k).astype(float) for k in codes}


def _topk(data, codes, p):
    """Hold the top k names of that year's eligible list by n-day momentum; rest in cash."""
    closes = pd.concat([data[k]["close"].rename(k) for k in codes], axis=1).ffill(limit=5)
    mom = closes.pct_change(p["n"])
    if p.get("vol_adj"):
        mom = mom / (closes.pct_change().rolling(p["n"]).std() * np.sqrt(p["n"]))
    if p.get("trend_n"):
        mom = mom.where(closes > closes.rolling(p["trend_n"]).mean())
    years = sorted(int(y) for y in p["elig"])
    elig = pd.DataFrame(False, index=closes.index, columns=closes.columns)
    for y in years:
        rows = closes.index.year <= y if y == years[0] else closes.index.year == y
        if len(years) == 1:
            rows = np.ones(len(closes), dtype=bool)
        cols = [k for k in p["elig"][str(y)] if k in elig.columns]
        elig.loc[rows, cols] = True
    mom = mom.where(elig).where(mom > 0)
    weights = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(p["n"], len(closes), p["every"]):
        best = mom.iloc[i].dropna().nlargest(p["k"]).index
        row = pd.Series(0.0, index=closes.columns)
        row[list(best)] = 1.0 / p["k"]
        weights.iloc[i] = row
    weights = weights.ffill().fillna(0.0)
    return {k: weights[k] for k in codes}


class SignalEngine:
    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        p = PARAMS
        codes = [k for k in data_map if k not in (p.get("regime_code"), p.get("bench_code"))]
        if p.get("bench_code"):
            for k in codes:
                data_map[k].attrs["bench"] = data_map[p["bench_code"]]["close"]
        if p["family"] == "rotate":
            sig = _rotate(data_map, codes, p)
        elif p["family"] == "topk":
            sig = _topk(data_map, codes, p)
        else:
            share = 1.0 / len(codes)
            for k in codes:
                data_map[k].attrs["code"] = k
            sig = {k: _single(data_map[k], p) * share for k in codes}
        if p.get("regime_code"):
            r = data_map[p["regime_code"]]["close"]
            on = (r > r.rolling(p["regime_n"]).mean()).astype(float)
            sig = {k: s * on.reindex(s.index).ffill().fillna(0.0) for k, s in sig.items()}
            sig[p["regime_code"]] = pd.Series(0.0, index=r.index)
        if p.get("bench_code"):
            sig[p["bench_code"]] = pd.Series(0.0, index=data_map[p["bench_code"]].index)
        return sig
