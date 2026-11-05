"""Past earnings dates for every second stock the ladder can hold, and the days fear was fading on the VIX.

Dates come from Yahoo through yfinance. Names Yahoo has no dates for are listed and simply get no earnings rule.
Writes results/earnings_dates.json {ticker: [dates]} and results/vix_close.json {date: close}.
"""
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

RES = Path(__file__).parent / "results"
labels = json.loads((RES / "growth_partner.json").read_text(encoding="utf-8"))
names = sorted({n for by_year in labels.values() for n in by_year.values()} | {"AMD"})
out, missing = {}, []
for name in names:
    try:
        table = yf.Ticker(name).get_earnings_dates(limit=70)
    except Exception as exc:  # Yahoo fails per ticker; one failure must not stop the rest
        print(name, "failed", repr(exc)[:100], flush=True)
        table = None
    if table is None or table.empty:
        missing.append(name)
        continue
    days = pd.DatetimeIndex(table.index).tz_localize(None).normalize()
    days = sorted({d.strftime("%Y-%m-%d") for d in days if d <= pd.Timestamp("2026-11-04")})
    out[name] = days
    print(name, len(days), days[0], days[-1], flush=True)
print("missing", missing)
(RES / "earnings_dates.json").write_text(json.dumps(out, indent=0), encoding="utf-8")
vix = yf.download("^VIX", start="2012-01-01", end="2026-11-04", auto_adjust=True, progress=False)["Close"].squeeze().dropna()
(RES / "vix_close.json").write_text(json.dumps({d.strftime("%Y-%m-%d"): round(float(v), 2) for d, v in vix.items()}), encoding="utf-8")
print("vix bars", len(vix), vix.index[0].date(), vix.index[-1].date())
