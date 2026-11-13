"""Shared data helpers for the Chronos-2 AMD tests. Backtest only; no orders."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
RES = HERE.parent / "results"
TRAIN_END = pd.Timestamp("2024-06-30")
FIRST_FC = pd.Timestamp("2024-07-01")
HORIZONS = (5, 10, 20)
H = 20

amd = pd.read_csv(RES / "amd_daily_2012_cache.csv", index_col=0, parse_dates=True)
peers = pd.read_csv(HERE / "peers.csv", index_col=0, parse_dates=True)
idx = amd.index
logc = np.log(amd.close)

earn = pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text())["AMD"])
earn = earn.sort_values()


def days_to_next_earn(dates, cap=90):
    """Calendar days from each date to the next AMD report date on/after it (capped). Report dates are public in advance."""
    e = earn.values
    out = []
    for d in pd.DatetimeIndex(dates):
        j = np.searchsorted(e, np.datetime64(d))
        out.append(min((e[j] - np.datetime64(d)).astype("timedelta64[D]").astype(int), cap) if j < len(e) else cap)
    return np.array(out, dtype="float32")


def future_dates(d, h=H):
    """The next h business days after d (Mon-Fri, holidays ignored; the model only sees them through a covariate)."""
    return pd.bdate_range(d + pd.Timedelta(days=1), periods=h)


def forecast_days():
    return idx[(idx >= FIRST_FC)]


def to_rows(variant, dates, q50):
    """q50: array [n_dates, H] of median log-price forecasts; returns rows with pred_ret per horizon."""
    rows = []
    for d, q in zip(dates, q50):
        c0 = logc.loc[d]
        for h in HORIZONS:
            rows.append((d.strftime("%Y-%m-%d"), variant, h, float(np.exp(q[h - 1] - c0) - 1)))
    return rows
