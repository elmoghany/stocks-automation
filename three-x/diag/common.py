"""Shared helpers for the AMD diagnosis scripts. Research only: reads prices, never places orders, never writes outside diag/.

Fill convention (same as every earlier AMD study): a decision is made at a close, the trade fills at the NEXT open, 5 bp per side.
pos[i] = 1 means "decided at the close of day i to be in AMD during day i+1".
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ROOT = HERE.parent
DATA = HERE / "data"
OUT = HERE / "out"
RES = ROOT / "results"
COST = 0.0005
RECENT_START = pd.Timestamp("2023-08-01")
EARLY_START = pd.Timestamp("2013-01-02")
sys.path.insert(0, str(ROOT))


def load_amd():
    """Adjusted daily bars 2012 to 2026-11-11 from the study cache (same file every earlier script used)."""
    f = pd.read_csv(RES / "amd_daily_2012_cache.csv", index_col=0, parse_dates=True)
    f.index = pd.DatetimeIndex(f.index).normalize()
    return f


def load_etf(code):
    """QQQ or SMH daily bars from yfinance, cached once in diag/data so reruns do not change."""
    path = DATA / f"{code}.csv"
    if not path.exists():
        import yfinance as yf
        raw = yf.download(code, start="2012-01-01", end="2026-11-13", auto_adjust=True, progress=False)
        out = pd.DataFrame({k.lower(): raw[k].squeeze() for k in ("Open", "High", "Low", "Close", "Volume")}).dropna()
        out.index = pd.DatetimeIndex(out.index).tz_localize(None).normalize()
        out.to_csv(path)
    f = pd.read_csv(path, index_col=0, parse_dates=True)
    return f


def report_dates():
    return pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"])


def windows(idx, last=None):
    """(name, lo, hi) bar ranges: lo is the first day held, hi is one past the last day. recent = Aug 2023 on, early = 2013 to Jul 2023."""
    n = len(idx) if last is None else last
    i_recent = int(idx.searchsorted(RECENT_START))
    i_early = int(idx.searchsorted(EARLY_START))
    return {"recent": (i_recent, n), "early": (i_early, i_recent)}


def factors(pos, o, c, lo, hi, cost=COST):
    """Daily growth factors for days lo..hi-1. Flat before lo. pos decided at close t-1 is held during day t."""
    n = len(c)
    pos = np.asarray(pos, dtype=float)
    now = np.zeros(n)           # held during day t
    now[1:] = pos[:-1]
    before = np.zeros(n)        # held during day t-1
    before[1:] = now[:-1]
    before[lo] = 0.0            # start of window: flat
    d = np.ones(n)
    both = (now == 1) & (before == 1)
    buy = (now == 1) & (before == 0)
    sell = (now == 0) & (before == 1)
    prev_c = np.r_[np.nan, c[:-1]]
    d[both] = (c / prev_c)[both]
    d[buy] = (c / o * (1 - cost))[buy]          # bought at the open, 5 bp worse
    d[sell] = (o / prev_c * (1 - cost))[sell]   # sold at the open, 5 bp worse
    out = np.ones(n)
    out[lo:hi] = d[lo:hi]
    return out


def curve(pos, o, c, lo, hi, cost=COST):
    """Cumulative value (1.0 = start) after each close lo..hi-1."""
    return np.cumprod(factors(pos, o, c, lo, hi, cost)[lo:hi])


def mult(pos, o, c, lo, hi, cost=COST):
    return float(np.prod(factors(pos, o, c, lo, hi, cost)[lo:hi]))


def hold_mult(o, c, lo, hi, cost=COST):
    """Bought at the first open (5 bp worse), marked at the last close."""
    return float(c[hi - 1] / o[lo] * (1 - cost))


def max_dd(eq):
    eq = np.asarray(eq)
    return float(np.min(eq / np.maximum.accumulate(eq) - 1))


def trades_from_pos(pos, lo, hi):
    """List of (decision_bar_in, decision_bar_out or None) from a daily position array."""
    p = np.asarray(pos)[lo:hi]
    prev = 0.0
    out, start = [], None
    for k, v in enumerate(p):
        if v == 1 and prev == 0:
            start = lo + k
        elif v == 0 and prev == 1:
            out.append((start, lo + k))
            start = None
        prev = v
    if start is not None:
        out.append((start, None))
    return out
