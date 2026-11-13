"""Download public daily peer prices (adjusted close) for fine-tuning data, cut at the train end 2024-06-30. Nothing after that enters.
Run with E:\\strategy-repos\\venvs\\vt\\Scripts\\python (has yfinance)."""
from pathlib import Path

import pandas as pd
import yfinance as yf

HERE = Path(__file__).parent
TICKERS = ["NVDA", "INTC", "QQQ", "SMH", "SOXX", "AVGO", "QCOM", "TXN", "MU", "AMAT", "LRCX", "KLAC", "MRVL", "ADI", "NXPI", "MCHP", "TSM", "ASML", "SPY", "AAPL", "MSFT", "CSCO", "ORCL", "IBM"]
CUT = "2024-06-30"
d = yf.download(TICKERS, start="2005-01-01", end="2024-07-01", auto_adjust=True, progress=False, group_by="ticker")
out = {}
for t in TICKERS:
    try:
        s = d[t]["Close"].dropna()
    except Exception as e:
        print("skip", t, e)
        continue
    s = s[s.index <= CUT]
    if len(s) > 500:
        out[t] = s
        print(t, len(s), s.index[0].date(), s.index[-1].date())
df = pd.DataFrame(out)
assert df.index.max() <= pd.Timestamp(CUT)
df.to_csv(HERE / "peers_close_to_2024-06-30.csv")
print(df.shape)
