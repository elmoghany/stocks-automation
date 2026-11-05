"""Choose AMD's second stock each January from earlier data only: high volume, then strongest growth.

Without this, testing a named partner like CEG or PLTR assumes we knew it would win. Price return stands
in for growth, because point-in-time revenue growth is not available here. Volume is 50-day average dollar
volume at the end of the prior year. Today's lists are used, so companies that later vanished are missing.

Two universes: the project's halal list ("auto_*"), and with the halal filter dropped at the user's request,
that list plus today's S&P 500 and Nasdaq-100 ("broad_*").

Writes results/growth_partner.json: {label: {year: ticker}}.
"""
import io
import json
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

HERE = Path(__file__).parent
HALAL = json.load(open(HERE.parent / "day-trading" / "data" / "halal_list.json", encoding="utf-8"))["symbols"]
RULES = {"vol30_12m": (30, 252), "vol100_12m": (100, 252), "vol30_6m": (30, 126)}
PAGES = {"https://en.wikipedia.org/wiki/List_of_S%26P_500_companies": "Symbol",
         "https://en.wikipedia.org/wiki/Nasdaq-100": "Ticker"}


def index_members():
    names = set()
    for url, column in PAGES.items():
        html = requests.get(url, headers={"User-Agent": "three-x-research/1.0"}, timeout=60).text
        for table in pd.read_html(io.StringIO(html)):
            if column in table.columns:
                names |= set(table[column].astype(str))
                break
    return {n for n in names if n.isascii() and "." not in n and n.isupper()}  # Vibe's loader has no share-class form


def choose(close, dollar, names, prefix, out):
    names = [n for n in names if n in close.columns and n != "AMD"]
    for label, (top_n, look) in RULES.items():
        key = f"{prefix}_{label}"
        out[key] = {}
        for year in range(2013, 2027):
            asof = close.index[close.index < f"{year}-01-01"][-1]
            liquid = dollar.loc[asof, names].dropna().nlargest(top_n).index
            ret = close[liquid].ffill().pct_change(look, fill_method=None).loc[asof].dropna()
            out[key][str(year)] = ret.idxmax()
        print(key, list(out[key].values()), flush=True)


members = index_members()
print("index members", len(members), flush=True)
universe = sorted(set(HALAL) | members | {"AMD"})
raw = yf.download(universe, start="2011-06-01", end="2026-11-04", auto_adjust=True, progress=False, threads=True)
close, volume = raw["Close"], raw["Volume"]
dollar = (close * volume).rolling(50).mean()
out = {}
choose(close, dollar, HALAL, "auto", out)
choose(close, dollar, universe, "broad", out)
(HERE / "results" / "growth_partner.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
