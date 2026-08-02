"""60-day market-wide backtest of the full penny-stock methodology.

Stages:
  1. Universe: all NASDAQ/NYSE common stocks (nasdaqtrader symbol files),
     minus ETFs/warrants/units/rights.
  2. Daily discovery (yfinance bulk daily data): for each of the last 60
     trading days find stocks with: band $2-16 reachable that day, day high
     >= +10% over prev close, volume >= 5x trailing 50-day average.
  3. Rule filters on the survivors (current snapshots -- approximation):
     float <= 16M, hot sector, HALAL (loans/deposits/combined/haram-revenue
     + industry screen). News rule is NOT backtestable -> skipped (noted).
  4. Intraday sim on each qualifying stock-day: yfinance 5-minute bars
     (prepost) restricted to 7-10 AM ET, one gapper per day (highest gain),
     $1000 per trade, same-day flatten. Two configs:
       A. calibrated default: hammer_family + vol confirm + strong_if_profit
       B. trail 20% + all bullish patterns (the "ride the runner" config)

Honest limitations (also printed): float/halal/sector use TODAY's values
(survivorship approximation); 5-min bars are coarser than the 1-min bars the
patterns were calibrated on; yfinance premarket volume is 0 so volume
confirmation auto-passes premarket; news rule skipped.
"""

import importlib.util
import io
import json
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# import penny-stocks.py (hyphenated filename)
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "penny-stocks.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

CACHE = ROOT / "data" / "backtest60"
CACHE.mkdir(parents=True, exist_ok=True)

DAYS_BACK = 60
MIN_GAIN = 10.0
MIN_RVOL = 5.0
BATCH = 400


def get_universe() -> list[str]:
    """All US-listed common stocks from nasdaqtrader symbol directories."""
    cache_f = CACHE / "universe.json"
    if cache_f.exists():
        return json.loads(cache_f.read_text())
    syms = []
    for url, sym_col, skip_col in [
        ("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
         "Symbol", "ETF"),
        ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
         "ACT Symbol", "ETF"),
    ]:
        with urllib.request.urlopen(url, timeout=30) as r:
            txt = r.read().decode("utf-8", errors="replace")
        df = pd.read_csv(io.StringIO(txt), sep="|")
        df = df[df[sym_col].notna()]
        name_col = [c for c in df.columns if "Name" in c][0]
        bad_words = ("Warrant", "Right", "Unit", " Units", "Preferred",
                     "Depositary", "Notes ", "%")
        for _, row in df.iterrows():
            s = str(row[sym_col]).strip()
            nm = str(row.get(name_col, ""))
            if (not s or not s.isalpha() or len(s) > 5
                    or str(row.get(skip_col, "N")) == "Y"
                    or str(row.get("Test Issue", "N")) == "Y"
                    or any(w in nm for w in bad_words)):
                continue
            syms.append(s)
    syms = sorted(set(syms))
    cache_f.write_text(json.dumps(syms))
    return syms


def discover_gapper_days(symbols: list[str]) -> list[dict]:
    """Bulk daily data -> qualifying (symbol, date) stock-days."""
    cache_f = CACHE / "gapper_days.json"
    if cache_f.exists():
        return json.loads(cache_f.read_text())

    import yfinance as yf
    found = []
    for i in range(0, len(symbols), BATCH):
        batch = symbols[i:i + BATCH]
        print(f"  daily batch {i // BATCH + 1}/{(len(symbols) - 1) // BATCH + 1} "
              f"({len(batch)} syms)...", flush=True)
        try:
            data = yf.download(batch, period="7mo", interval="1d",
                               group_by="ticker", threads=True,
                               progress=False, auto_adjust=True)
        except Exception as e:
            print(f"    batch failed: {e}")
            continue
        for sym in batch:
            try:
                df = data[sym].dropna(subset=["Close"])
            except Exception:
                continue
            if len(df) < 55:
                continue
            close = df["Close"].values
            high = df["High"].values
            low = df["Low"].values
            vol = df["Volume"].values
            dates = df.index
            n = len(df)
            start_i = max(51, n - DAYS_BACK)
            for k in range(start_i, n):
                prev = close[k - 1]
                if prev <= 0:
                    continue
                gain = (high[k] / prev - 1) * 100
                if gain < MIN_GAIN:
                    continue
                if not (high[k] >= 2.0 and low[k] <= 16.0):
                    continue
                av = vol[k - 50:k].mean()
                if av <= 0 or vol[k] < MIN_RVOL * av:
                    continue
                found.append({"symbol": sym,
                              "date": str(dates[k].date()),
                              "gain_pct": round(gain, 1),
                              "prev_close": round(float(prev), 4),
                              "rvol": round(float(vol[k] / av), 1)})
    cache_f.write_text(json.dumps(found))
    return found


def filter_rules(cands: list[dict]) -> list[dict]:
    """Float <= 16M, hot sector, halal -- current snapshots, cached."""
    cache_f = CACHE / "symbol_rules.json"
    verdicts = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    import yfinance as yf

    syms = sorted({c["symbol"] for c in cands})
    for sym in syms:
        if sym in verdicts:
            continue
        v = {"float_ok": None, "sector_ok": None, "halal_ok": None,
             "reason": ""}
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            flt = info.get("floatShares")
            v["float_ok"] = (flt is None) or (flt <= ps.MAX_FLOAT)
            if flt is not None and flt > ps.MAX_FLOAT:
                v["reason"] = f"float {flt / 1e6:.0f}M"
            sector = f"{info.get('sector', '')} / {info.get('industry', '')}"
            v["sector_ok"] = any(s in sector.lower() for s in ps.HOT_SECTORS)
            if not v["sector_ok"]:
                v["reason"] = f"sector: {sector[:40]}"
            if v["float_ok"] and v["sector_ok"]:
                h = ps.halal_check(sym, t, info.get("marketCap"))
                v["halal_ok"] = h["halal"]
                if not h["halal"]:
                    v["reason"] = f"NOT HALAL: {h['fail_reason']}"
        except Exception as e:
            v["reason"] = f"error: {e}"
        verdicts[sym] = v
        cache_f.write_text(json.dumps(verdicts))
        print(f"  {sym}: float_ok={v['float_ok']} sector_ok={v['sector_ok']} "
              f"halal_ok={v['halal_ok']} {v['reason']}", flush=True)

    out = []
    for c in cands:
        v = verdicts.get(c["symbol"], {})
        if v.get("float_ok") and v.get("sector_ok") and v.get("halal_ok"):
            out.append(c)
    return out


def simulate_day(sym: str, date: str, prev_close: float):
    """7-10 AM sim on yfinance 5-min prepost bars for one day."""
    import yfinance as yf
    d0 = datetime.strptime(date, "%Y-%m-%d")
    t = yf.Ticker(sym)
    df = t.history(start=d0.strftime("%Y-%m-%d"),
                   end=(d0 + timedelta(days=1)).strftime("%Y-%m-%d"),
                   interval="5m", prepost=True)
    if df.empty:
        return None
    df.index = df.index.tz_convert(ps.ET)
    w = df[(df.index.time >= ps.NEWS_START) & (df.index.time < ps.NEWS_END)]
    if len(w) < 8:
        return None
    res = {}
    res["A_default"] = ps.simulate_trades(w, verbose=False,
                                          prev_close=prev_close)
    res["B_trail20"] = ps.simulate_trades(w, verbose=False, buy_set=None,
                                          vol_confirm=False, trail_pct=20,
                                          stop_pct=5, prev_close=prev_close)
    return res


def main():
    print("Stage 1: universe...")
    universe = get_universe()
    print(f"  {len(universe)} common stocks")

    print("Stage 2: discovering gapper days (60d, +10%, 5x rvol, band)...")
    cands = discover_gapper_days(universe)
    print(f"  {len(cands)} qualifying stock-days "
          f"({len({c['symbol'] for c in cands})} unique symbols)")

    print("Stage 3: float / hot-sector / HALAL filters...")
    final = filter_rules(cands)
    print(f"  {len(final)} stock-days survive all rules "
          f"({len({c['symbol'] for c in final})} symbols)")

    # one gapper per day: highest day gain
    by_day = {}
    for c in final:
        if c["date"] not in by_day or c["gain_pct"] > by_day[c["date"]]["gain_pct"]:
            by_day[c["date"]] = c

    print(f"\nStage 4: simulating {len(by_day)} trading days "
          f"(one gapper/day, $1000/trade, 7-10 AM, 5-min bars)...\n")
    rows = []
    tot = {"A_default": 0.0, "B_trail20": 0.0}
    ntr = {"A_default": 0, "B_trail20": 0}
    for date in sorted(by_day):
        c = by_day[date]
        res = simulate_day(c["symbol"], date, c["prev_close"])
        if res is None:
            print(f"{date}  {c['symbol']:<6} +{c['gain_pct']}%  (no intraday data)")
            continue
        pa = sum(t["pnl"] for t in res["A_default"])
        pb = sum(t["pnl"] for t in res["B_trail20"])
        tot["A_default"] += pa
        tot["B_trail20"] += pb
        ntr["A_default"] += len(res["A_default"])
        ntr["B_trail20"] += len(res["B_trail20"])
        rows.append((date, c["symbol"], c["gain_pct"], c["rvol"],
                     len(res["A_default"]), pa, len(res["B_trail20"]), pb))
        print(f"{date}  {c['symbol']:<6} +{c['gain_pct']:>6.1f}%  rvol {c['rvol']:>5.1f}x"
              f"  | A: {len(res['A_default'])}t ${pa:>+8.2f}"
              f"  | B(trail20): {len(res['B_trail20'])}t ${pb:>+8.2f}")

    print(f"\n{'=' * 72}")
    print(f"  60-DAY RESULTS -- full methodology, $1000/trade, halal-only")
    print(f"{'=' * 72}")
    print(f"  Qualifying gapper days traded: {len(rows)}")
    print(f"  A calibrated default : {ntr['A_default']:>3} trades  "
          f"P&L ${tot['A_default']:>+10.2f}  ({tot['A_default'] / 10:+.1f}% on $1000)")
    print(f"  B trail20 all-pattern: {ntr['B_trail20']:>3} trades  "
          f"P&L ${tot['B_trail20']:>+10.2f}  ({tot['B_trail20'] / 10:+.1f}% on $1000)")
    print(f"\n  Limitations: float/sector/halal are TODAY'S snapshots; news rule")
    print(f"  skipped (not backtestable); 5-min bars (calibrated on 1-min);")
    print(f"  yfinance premarket volume=0 so vol-confirm auto-passes premarket.")

    (CACHE / "results.json").write_text(json.dumps(rows, default=str))


if __name__ == "__main__":
    main()
