"""Approximate point-in-time top-50 US names per January, from price x shares outstanding.

Candidates are large caps that were top-50-sized at some point since 2014, including names
that later fell back, so the list is not just today's winners. Names delisted through a
merger (for example CELG, MON, TWX) have no Yahoo data and are missing: a small survivorship
gap that is noted in the report.

Writes results/pit_top50.json: {year: {"all": [...], "halal": [...]}}.
"""
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

HERE = Path(__file__).parent
CANDIDATES = """AAPL MSFT GOOGL AMZN META NVDA AVGO TSLA BRK-B LLY WMT JPM V ORCL XOM MA NFLX JNJ COST ABBV PLTR HD PG BAC
UNH KO CVX GE CSCO AMD TMUS IBM WFC PM CRM ABT MS GS MCD AXP LIN INTC MU ISRG T RTX MRK PEP DIS UBER NOW QCOM TXN
VZ PFE C CMCSA BA MMM GILD AMGN BMY MDT HON UNP UPS CAT NKE SBUX LOW BLK SLB COP CVS TMO DHR ADBE PYPL ACN NEE LMT
SPGI TGT MO CL BKNG AMAT LRCX KLAC ADI PANW SHOP SNOW ABNB COIN APP CRWD GEV DELL ANET""".split()
HALAL = set(json.load(open(HERE.parent / "day-trading" / "data" / "halal_list.json", encoding="utf-8"))["symbols"])

prices, shares = {}, {}
for sym in CANDIDATES:
    t = yf.Ticker(sym)
    h = t.history(start="2013-06-01", auto_adjust=False)
    if h.empty:
        print("no price", sym)
        continue
    h.index = h.index.tz_localize(None)
    # Yahoo's Close is split-adjusted even with auto_adjust=False; undo that so price matches raw share counts.
    later_splits = h["Stock Splits"].replace(0, 1.0)[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
    prices[sym] = h["Close"] * later_splits
    try:
        s = t.get_shares_full(start="2013-06-01")
    except Exception as exc:
        print("no shares", sym, exc)
        continue
    if s is None or s.empty:
        print("no shares", sym)
        continue
    s.index = pd.DatetimeIndex(s.index).tz_localize(None)
    shares[sym] = s[~s.index.duplicated()].sort_index()

out, coverage = {}, {}
for year in range(2015, 2027):
    day = pd.Timestamp(f"{year}-01-01")
    caps = {}
    for sym, px in prices.items():
        p = px[:day]
        if p.empty or (day - p.index[-1]).days > 10 or sym not in shares:
            continue
        s = shares[sym][:day]
        if len(s):
            caps[sym] = float(p.iloc[-1]) * float(s.iloc[-1])
    ranked = sorted(caps, key=caps.get, reverse=True)[:50]
    out[year] = {"all": ranked, "halal": [s for s in ranked if s in HALAL]}
    coverage[year] = len(caps)
(HERE / "results" / "pit_top50.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("coverage", coverage)
for year in (2016, 2020, 2024, 2026):
    print(year, "halal", len(out[year]["halal"]), out[year]["halal"][:30], "AMD rank",
          out[year]["all"].index("AMD") + 1 if "AMD" in out[year]["all"] else None)
