"""Download public daily closes for peers/covariates (2012 to 2026-11-12) with yfinance into peers.csv (adjusted close)."""
from pathlib import Path
import pandas as pd
import yfinance as yf

OUT = Path(__file__).parent / "peers.csv"
tick = ["NVDA", "INTC", "QQQ", "SMH", "MU", "AVGO", "TXN", "QCOM", "SOXX", "SPY", "TSM", "AMAT"]
d = yf.download(tick, start="2012-01-01", end="2026-11-14", auto_adjust=True, progress=False)
close = d["Close"].copy()
close.index = pd.to_datetime(close.index).tz_localize(None)
close.to_csv(OUT)
print(close.shape, close.index.min(), close.index.max())
print(close.isna().sum())
