"""Build the broad earnings-trading universe: S&P 500 + S&P 400 midcap
+ Nasdaq-100 tickers scraped from Wikipedia (cached to
data/universe_big.json; --refetch to rebuild). Dots -> dashes for
yfinance (BRK.B -> BRK-B). The >$2 price gate is applied later at event
build time from actual bars."""

import json
import sys
import urllib.request
from io import StringIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/universe_big.json"
PAGES = [
    ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
     "Symbol"),
    ("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
     "Symbol"),
    ("https://en.wikipedia.org/wiki/Nasdaq-100", "Symbol"),
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent":
                                 "Mozilla/5.0 (research script)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def build():
    syms = set()
    for url, col in PAGES:
        try:
            tables = pd.read_html(StringIO(fetch(url)))
        except Exception as e:
            print(f"  {url}: {e}")
            continue
        got = 0
        for tb in tables:
            if col in tb.columns:
                vals = [str(v).strip().replace(".", "-")
                        for v in tb[col].dropna()]
                vals = [v for v in vals if v.isascii() and 1 <= len(v) <= 6
                        and v.upper() == v and not v.isdigit()]
                if len(vals) >= 90:          # the real constituents table
                    syms.update(vals)
                    got = len(vals)
                    break
        print(f"  {url.rsplit('/', 1)[-1]}: {got}")
    out = sorted(syms)
    OUT.write_text(json.dumps(out))
    print(f"universe: {len(out)} symbols -> {OUT.name}")
    return out


def load():
    if OUT.exists() and "--refetch" not in sys.argv:
        return json.loads(OUT.read_text())
    return build()


if __name__ == "__main__":
    load()
