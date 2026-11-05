"""For each year, the 30 highest dollar-volume stocks at the end of the prior year, from earlier data only.

Used by the ladder's "pick the second stock when selling" addition. Universe is the project's halal list plus
today's S&P 500 and Nasdaq-100, so companies that later vanished are missing. Writes results/growth_pool.json.
"""
import io
import json
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

HERE = Path(__file__).parent
HALAL = json.load(open(HERE.parent / "day-trading" / "data" / "halal_list.json", encoding="utf-8"))["symbols"]
PAGES = {"https://en.wikipedia.org/wiki/List_of_S%26P_500_companies": "Symbol",
         "https://en.wikipedia.org/wiki/Nasdaq-100": "Ticker"}

names = set(HALAL)
for url, column in PAGES.items():
    html = requests.get(url, headers={"User-Agent": "three-x-research/1.0"}, timeout=60).text
    for table in pd.read_html(io.StringIO(html)):
        if column in table.columns:
            names |= set(table[column].astype(str))
            break
names = sorted(n for n in names if n.isascii() and "." not in n and n.isupper() and n != "AMD")
raw = yf.download(names, start="2011-06-01", end="2026-11-04", auto_adjust=True, progress=False, threads=True)
dollar = (raw["Close"] * raw["Volume"]).rolling(50).mean()
out = {}
for year in range(2013, 2027):
    asof = dollar.index[dollar.index < f"{year}-01-01"][-1]
    out[str(year)] = sorted(dollar.loc[asof].dropna().nlargest(30).index)
(HERE / "results" / "growth_pool.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("tickers in total", len({n for v in out.values() for n in v}))
