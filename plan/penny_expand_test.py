"""Expansion tests at $15k/position: price ceiling and the 10 AM rule.

Variants (all: halal + float<=16M + upward sectors + up>=10% + rvol>=5x,
ORB+dip entries, trail 20% / stop 5%, 10% bar-volume liquidity cap,
one top gapper per day, $15,000 per position):

  V0 baseline     band $2-16, window 7:00-10:00  (reference)
  V1 no ceiling   band $2+,   window 7:00-10:00
  V2 noon window  band $2-16, window 7:00-12:00
  V3 full day     band $2-16, window 7:00-16:00
  V4 both         band $2+,   window 7:00-16:00

Discovery for V1/V4 re-scans the market without the $16 ceiling.
Windows beyond 10:00 use freshly cached FULL-session 5-min bars
(the original intraday cache was pre-filtered to 7-10 AM).
"""

import importlib.util
import json
import sys
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "penny-stocks.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

sys.path.insert(0, str(ROOT / "plan"))
_yspec = importlib.util.spec_from_file_location(
    "ytd", ROOT / "plan" / "penny_backtest_ytd.py")
ytd = importlib.util.module_from_spec(_yspec)
_yspec.loader.exec_module(ytd)

CACHE = ROOT / "data" / "backtest60"
FDIR = CACHE / "intraday_full"
FDIR.mkdir(exist_ok=True)

BUDGET = 15_000.0
VOL_FRAC = 0.10
MIN_GAIN = 10.0
MIN_RVOL = 5.0
BATCH = 400


def discover_noceil():
    """Gapper days with NO price ceiling (only the $2 floor reachable)."""
    cache_f = CACHE / "gappers_ytd_noceil.json"
    if cache_f.exists():
        return json.loads(cache_f.read_text())
    import yfinance as yf
    universe = json.loads((CACHE / "universe.json").read_text())
    found = []
    for i in range(0, len(universe), BATCH):
        batch = universe[i:i + BATCH]
        print(f"  noceil batch {i // BATCH + 1}/{(len(universe) - 1) // BATCH + 1}",
              flush=True)
        try:
            data = yf.download(batch, period="13mo", interval="1d",
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
            if len(df) < 60:
                continue
            close = df["Close"].values
            high = df["High"].values
            vol = df["Volume"].values
            dates = df.index
            for k in range(51, len(df)):
                if str(dates[k].date()) < "2026-01-01":
                    continue
                prev = close[k - 1]
                if prev <= 0:
                    continue
                if (high[k] / prev - 1) * 100 < MIN_GAIN:
                    continue
                if high[k] < 2.0:
                    continue
                av = vol[k - 50:k].mean()
                if av <= 0 or vol[k] < MIN_RVOL * av:
                    continue
                found.append({"symbol": sym, "date": str(dates[k].date()),
                              "gain_pct": round((high[k] / prev - 1) * 100, 1),
                              "prev_close": round(float(prev), 4),
                              "rvol": round(float(vol[k] / av), 1)})
    cache_f.write_text(json.dumps(found))
    return found


def get_full_df(sym, date):
    src = FDIR / f"{sym}_{date}.csv"
    if not src.exists():
        import yfinance as yf
        d0 = datetime.strptime(date, "%Y-%m-%d")
        try:
            df = yf.Ticker(sym).history(
                start=date, end=(d0 + timedelta(days=1)).strftime("%Y-%m-%d"),
                interval="5m", prepost=True)
        except Exception:
            df = pd.DataFrame()
        if df.empty:
            src.write_text("EMPTY")
            return None
        df.index = df.index.tz_convert(ps.ET)
        out = pd.DataFrame({"begins_at": df.index.tz_convert("UTC"),
                            "open": df["Open"], "high": df["High"],
                            "low": df["Low"], "close": df["Close"],
                            "volume": df["Volume"]})
        out.to_csv(src, index=False)
    txt = src.read_text()
    if txt.startswith("EMPTY"):
        return None
    df = pd.read_csv(src)
    df["begins_at"] = (pd.to_datetime(df["begins_at"], utc=True)
                       .dt.tz_convert(ps.ET))
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    return df.set_index("begins_at").sort_index()


def day_pick(cands):
    by_day = {}
    for c in cands:
        if (c["date"] not in by_day
                or c["gain_pct"] > by_day[c["date"]]["gain_pct"]):
            by_day[c["date"]] = c
    return by_day


def run_variant(name, cands, end_t, price_max):
    saved = ps.PRICE_MAX
    ps.PRICE_MAX = price_max
    total = 0.0
    days = []
    try:
        for date, c in sorted(day_pick(cands).items()):
            df = get_full_df(c["symbol"], date)
            if df is None:
                continue
            w = df[(df.index.time >= dtime(7, 0)) & (df.index.time < end_t)]
            if len(w) < 8:
                continue
            tr = ps.simulate_trades(w, verbose=False, buy_set=None,
                                    vol_confirm=False, trail_pct=20,
                                    stop_pct=5, prev_close=c["prev_close"],
                                    budget=BUDGET, orb=True,
                                    max_vol_frac=VOL_FRAC)
            pnl = sum(t["pnl"] for t in tr)
            if tr:
                days.append(pnl)
            total += pnl
    finally:
        ps.PRICE_MAX = saved
    n = len(days)
    wins = sum(1 for d in days if d > 0)
    big = sum(1 for d in days if d >= 1000)
    print(f"{name:<28} {n:>6} {total:>+12.2f} {total / n if n else 0:>+10.2f} "
          f"{wins:>5}/{n:<5} {big:>6} {min(days) if days else 0:>+10.2f}",
          flush=True)


def main():
    band_cands = ytd.filter_symbols(
        json.loads((CACHE / "gappers_ytd.json").read_text()))
    print("Discovering no-ceiling gappers (if not cached)...")
    noceil_raw = discover_noceil()
    print(f"  {len(noceil_raw)} no-ceiling stock-days; filtering...")
    noceil_cands = ytd.filter_symbols(noceil_raw)
    print(f"  {len(noceil_cands)} survive rules "
          f"({len({c['symbol'] for c in noceil_cands})} symbols)\n")

    print(f"$15,000/position, 10% bar-volume cap, one top gapper/day\n")
    print(f"{'VARIANT':<28} {'days':>6} {'total P&L':>12} {'avg $/day':>10} "
          f"{'win/day':>11} {'>=+$1k':>6} {'worst':>10}")
    print("-" * 92)
    run_variant("V0 band $2-16, 7-10AM", band_cands, dtime(10, 0), 16.0)
    run_variant("V1 NO CEILING, 7-10AM", noceil_cands, dtime(10, 0), 1e9)
    run_variant("V2 band $2-16, 7-12", band_cands, dtime(12, 0), 16.0)
    run_variant("V3 band $2-16, 7-16 full", band_cands, dtime(16, 0), 16.0)
    run_variant("V4 NO CEILING, 7-16 full", noceil_cands, dtime(16, 0), 1e9)


if __name__ == "__main__":
    main()
