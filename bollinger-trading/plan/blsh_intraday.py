"""BL-family (BL01-BL07): same-day BUY-LOW / SELL-HIGH on 5-year
uptrend halal names, with volume -- the bollinger-book philosophy as a
day-trading strategy, sized like E01 ($50k/event) for comparison.

Per symbol-day (halal S&P900+600 universe, price > $2):
  gate STRONG: as of the PRIOR close, 5y total return >= +100% AND
       close > 200-day SMA (computed rolling, point-in-time)
  gate VOLUME: prior-day 10-day volume-pressure (daily sv formula)
       and/or prior-day rvol vs 50d
  entry: resting limit at open x (1 - dip%); fills if the day's Low
       touches it (assumed fill AT the limit)
  exit: same-day close (honest), or "recovery target" = back at the
       open price (fills if High >= open after the dip; OHLC ordering
       is unknowable -- optimistic, reported as the upper bound)
Experiments:
  BL01 dip 2%, strong, sell close        BL02 dip 3%, strong, close
  BL03 dip 2%, strong, recovery target   BL04 = BL01 + pressure >= 0
  BL05 dip 2% on NOT-strong names (control -- trend gate must matter)
  BL06 ONE $50k slot/day: deepest dip among strong fills, sell close
       (apples-to-apples with E01's +$117,755/yr)
  BL07 = BL06 excluding earnings reaction days (is BL just E01?)
Window Aug 2025..Jul 2026. Data: yfinance 6y daily OHLCV, cached per
symbol in data/ohlcv6y/. Universes/halal from earnings-trading caches.
"""

import json
import sys
import time
import warnings
from collections import defaultdict
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
ET = REPO / "earnings-trading"
CACHE = ROOT / "data/ohlcv6y"
CACHE.mkdir(parents=True, exist_ok=True)
BUDGET = 50_000
WINDOW = ("2025-08-01", "2026-07-31")


def halal_universe():
    out = []
    for f in ("earnings_halal_big.json", "earnings_halal_600.json"):
        m = json.loads((ET / "data" / f).read_text())
        out += [s for s, v in m.items() if v]
    return sorted(set(out))


def earnings_days():
    days = set()
    for f in ("earnings_x2_events.json", "earnings_sc_events.json"):
        for e in json.loads((ET / "data" / f).read_text()):
            days.add((e["sym"], e["date"]))
    return days


def load_sym(sym):
    f = CACHE / f"{sym}.csv"
    if f.exists():
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
            return df if len(df) else None
        except Exception:
            return None
    try:
        df = yf.Ticker(sym).history(period="6y", auto_adjust=True)
        df.index = df.index.tz_localize(None)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
    except Exception:
        df = pd.DataFrame()
    df.to_csv(f)
    time.sleep(0.1)
    return df if len(df) else None


def prep(df):
    """Rolling point-in-time flags shifted so day t uses data < t."""
    c, v = df["Close"], df["Volume"]
    strong = ((c / c.shift(1250) - 1 >= 1.0)
              & (c > c.rolling(200).mean())).shift(1)
    h, l = df["High"], df["Low"]
    rng = (h - l)
    sv = v * (2 * (c - l) - rng) / rng.where(rng > 0)
    p10 = (sv.rolling(10).sum() / v.rolling(10).sum()).shift(1)
    rvol = (v / v.rolling(50).mean()).shift(1)
    return strong, p10, rvol


def main():
    syms = halal_universe()
    edays = earnings_days()
    lo, hi = WINDOW
    fills = []          # dict per fill
    for n, sym in enumerate(syms):
        df = load_sym(sym)
        if df is None or len(df) < 1300:
            continue
        strong, p10, rvol = prep(df)
        w = df[(df.index >= lo) & (df.index <= hi)]
        for d, row in w.iterrows():
            o, hi_, lo_, cl = (row["Open"], row["High"],
                               row["Low"], row["Close"])
            if o <= 2 or pd.isna(o):
                continue
            ds = str(d.date())
            for dip in (2, 3):
                limit = o * (1 - dip / 100)
                if lo_ <= limit:
                    fills.append(dict(
                        sym=sym, date=ds, dip=dip,
                        ret_close=(cl / limit - 1) * 100,
                        ret_tgt=((o / limit - 1) * 100
                                 if hi_ >= o else (cl / limit - 1) * 100),
                        strong=bool(strong.get(d) is True),
                        p10=(None if pd.isna(p10.get(d))
                             else float(p10.get(d))),
                        rvol=(None if pd.isna(rvol.get(d))
                              else float(rvol.get(d))),
                        edays=(sym, ds) in edays))
        if n % 25 == 0:
            print(f"  {n}/{len(syms)} ({len(fills)} fills)", flush=True)

    def stat(label, rets):
        n_ = len(rets)
        if not n_:
            print(f"{label}: n=0")
            return
        win = 100 * sum(1 for r in rets if r > 0) / n_
        avg = sum(rets) / n_
        tot = sum(BUDGET * r / 100 for r in rets)
        print(f"{label}  n={n_:>5} win={win:5.1f}% avg={avg:+6.3f}% "
              f"tot=${tot:+,.0f}")

    f2 = [f for f in fills if f["dip"] == 2]
    f3 = [f for f in fills if f["dip"] == 3]
    print(f"\nBL buy-low/sell-high  ${BUDGET:,}/event "
          f"[{WINDOW[0]}..{WINDOW[1]}]")
    stat("BL01 dip2 strong, close     ",
         [f["ret_close"] for f in f2 if f["strong"]])
    stat("BL02 dip3 strong, close     ",
         [f["ret_close"] for f in f3 if f["strong"]])
    stat("BL03 dip2 strong, recovery  ",
         [f["ret_tgt"] for f in f2 if f["strong"]])
    stat("BL04 dip2 strong+p10>=0     ",
         [f["ret_close"] for f in f2 if f["strong"]
          and f["p10"] is not None and f["p10"] >= 0])
    stat("BL05 dip2 NOT-strong control",
         [f["ret_close"] for f in f2 if not f["strong"]])
    by_day = defaultdict(list)
    for f in f2:
        if f["strong"]:
            by_day[f["date"]].append(f)
    # deepest dip = the fill whose limit sits lowest vs open is the
    # same 2% for all; rank instead by how far below the limit the
    # day's low went -- proxy: lowest ret_close day pick is post-hoc,
    # so rank by prior-day rvol (highest attention) instead
    slot = [max(v, key=lambda f: (f["rvol"] or 0))["ret_close"]
            for v in by_day.values()]
    stat("BL06 one-slot/day (top rvol)", slot)
    slot7 = [max([f for f in v if not f["edays"]] or v,
                 key=lambda f: (f["rvol"] or 0))["ret_close"]
             for v in by_day.values()]
    stat("BL07 slot excl earnings days", slot7)
    (ROOT / "data/blsh_results.json").write_text(json.dumps(dict(
        BL01=[round(f["ret_close"], 3) for f in f2 if f["strong"]],
        BL06=[round(r, 3) for r in slot])))


if __name__ == "__main__":
    main()
