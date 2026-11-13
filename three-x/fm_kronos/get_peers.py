"""Download public daily peer prices (adjusted) for Kronos fine-tuning. Public data only."""
import sys
from pathlib import Path
import pandas as pd
import yfinance as yf

OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)
PEERS = ["NVDA", "INTC", "QCOM", "AVGO", "MU", "TXN", "AMAT", "LRCX", "KLAC", "ADI", "MCHP", "NXPI", "ON", "SWKS", "QQQ", "SMH"]
for t in PEERS:
    df = yf.download(t, start="2012-01-01", end="2026-11-12", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
    df.index.name = "Date"
    df.to_csv(OUT / f"{t}.csv")
    print(t, len(df), df.index[0].date(), df.index[-1].date(), flush=True)
