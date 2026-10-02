"""SWING-REVERSION long-history check data (pre-2024).

Universe: every ticker that was an S&P 500 member at any time between
2005-01-01 and 2024-09-30 (point-in-time intervals from
github.com/fja05680/sp500, sp500_ticker_start_end.csv). Daily OHLCV from
yfinance (auto_adjust=True: split+dividend adjusted). Delisted / acquired
names that Yahoo no longer serves are MISSING -> survivorship bias; the
missing fraction is recorded per year in long/coverage.json.
Output: data/research_oct/long/yf_daily.pkl (dict field -> DataFrame).
"""
import json
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research_oct" / "long"
mem = pd.read_csv(OUT / "sp500_ticker_start_end.csv")
mem["end_date"] = mem["end_date"].fillna("2099-01-01")
m = mem[(mem.start_date <= "2024-09-30") & (mem.end_date >= "2005-01-01")]
tick = sorted(set(m.ticker))
print("tickers", len(tick), flush=True)
yt = {t: t.replace(".", "-") for t in tick}
frames = {}
for i in range(0, len(tick), 80):
    chunk = tick[i:i + 80]
    df = yf.download([yt[t] for t in chunk] + (["SPY"] if i == 0 else []),
                     start="2003-06-01", end="2024-11-01", auto_adjust=True,
                     progress=False, threads=True, group_by="ticker")
    for t in chunk + (["SPY"] if i == 0 else []):
        k = yt.get(t, t)
        try:
            sub = df[k].dropna(how="all")
        except KeyError:
            continue
        if len(sub):
            frames[t] = sub
    print(i + len(chunk), "got", len(frames), flush=True)
fields = {}
for f in ("Open", "High", "Low", "Close", "Volume"):
    fields[f] = pd.DataFrame({t: v[f] for t, v in frames.items()})
pd.to_pickle(fields, OUT / "yf_daily.pkl")
missing = sorted(set(tick) - set(frames))
(OUT / "missing.json").write_text(json.dumps(missing))
print("DONE got", len(frames), "missing", len(missing), flush=True)
