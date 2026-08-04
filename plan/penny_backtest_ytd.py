"""YTD backtest (Jan 1 2026 -> today) with EXPANDED upward-trending sectors.

Sectors included (1y return > 0 AND price > 200-SMA, checked 2026-08-02 via
sector ETFs): Technology, Healthcare, Industrials, Energy, Basic Materials,
Consumer Defensive, Real Estate. Excluded (below 200-SMA): Consumer
Cyclical, Communication Services, Utilities. Financials/haram industries are
killed by the halal gate regardless.

Strategy: the penny default -- all bullish patterns, trail 20%, stop 5%,
one top gapper/day, 7-10 AM window, same-day flatten, halal + float<=16M +
up>=10% + rvol>=5x + band $2-16 at entry. COMPOUNDING from $1000 on Jan 1.

Data reality: intraday 5-min bars exist only from ~May 5 (Robinhood) /
~Jun 4 (yfinance). Jan-Apr qualifying days are discovered from daily data
but cannot be intraday-simulated -- they are counted and the final answer
extrapolates them from the simulated days' average daily return (clearly
labeled as an estimate).
"""

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

CACHE = ROOT / "data" / "backtest60"
IDIR = CACHE / "intraday"
IDIR.mkdir(parents=True, exist_ok=True)

START_DATE = "2026-01-01"
MIN_GAIN = 10.0
MIN_RVOL = 5.0
BATCH = 400

# upward-trending sector keyword map (matched vs yfinance sector/industry)
UPWARD_SECTOR_WORDS = [
    # Technology
    "technology", "software", "semiconductor", "artificial intelligence",
    # Healthcare
    "health", "biotech", "pharmaceutical", "drug", "medical",
    # Industrials (defense/aerospace still killed by halal industry screen)
    "industrial", "machinery", "engineering", "construction", "transport",
    "trucking", "railroads",
    # Energy
    "energy", "oil", "gas", "solar", "renewable", "petroleum",
    # Basic Materials
    "materials", "chemical", "mining", "gold", "silver", "steel", "copper",
    # Consumer Defensive (alcohol/tobacco killed by halal screen)
    "consumer defensive", "food", "beverage", "household", "grocery",
    "discount stores", "packaged foods",
    # Real Estate (debt-heavy REITs killed by halal ratios)
    "real estate", "reit",
]


def discover():
    cache_f = CACHE / "gappers_ytd.json"
    if cache_f.exists():
        return json.loads(cache_f.read_text())
    import yfinance as yf
    universe = json.loads((CACHE / "universe.json").read_text())
    found = []
    for i in range(0, len(universe), BATCH):
        batch = universe[i:i + BATCH]
        print(f"  daily batch {i // BATCH + 1}/{(len(universe) - 1) // BATCH + 1}",
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
            low = df["Low"].values
            vol = df["Volume"].values
            dates = df.index
            for k in range(51, len(df)):
                if str(dates[k].date()) < START_DATE:
                    continue
                prev = close[k - 1]
                if prev <= 0:
                    continue
                if (high[k] / prev - 1) * 100 < MIN_GAIN:
                    continue
                if not (high[k] >= 2.0 and low[k] <= 16.0):
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


def filter_symbols(cands):
    """float + halal + UPWARD-sector filters; reuses old verdicts."""
    cache_f = CACHE / "rules_ytd.json"
    verdicts = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    old = json.loads((CACHE / "symbol_rules.json").read_text()) \
        if (CACHE / "symbol_rules.json").exists() else {}
    import yfinance as yf

    syms = sorted({c["symbol"] for c in cands})
    print(f"  {len(syms)} unique symbols to verify", flush=True)
    for n, sym in enumerate(syms):
        if sym in verdicts:
            continue
        v = {"float_ok": None, "halal_ok": None, "sector_raw": "",
             "reason": ""}
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            v["sector_raw"] = (f"{info.get('sector', '')} / "
                               f"{info.get('industry', '')}")
            flt = info.get("floatShares")
            ov = old.get(sym, {})
            v["float_ok"] = ov.get("float_ok") if ov.get("float_ok") is not None \
                else ((flt is None) or (flt <= ps.MAX_FLOAT))
            sector_ok = any(w in v["sector_raw"].lower()
                            for w in UPWARD_SECTOR_WORDS)
            if v["float_ok"] and sector_ok:
                if ov.get("halal_ok") is not None:
                    v["halal_ok"] = ov["halal_ok"]
                else:
                    h = ps.halal_check(sym, t, info.get("marketCap"))
                    v["halal_ok"] = h["halal"]
                    if not h["halal"]:
                        v["reason"] = h["fail_reason"]
        except Exception as e:
            v["reason"] = f"error: {e}"
        verdicts[sym] = v
        if n % 25 == 0:
            cache_f.write_text(json.dumps(verdicts))
            print(f"  ..{n}/{len(syms)}", flush=True)
    cache_f.write_text(json.dumps(verdicts))

    out = []
    for c in cands:
        v = verdicts.get(c["symbol"], {})
        sector_ok = any(w in v.get("sector_raw", "").lower()
                        for w in UPWARD_SECTOR_WORDS)
        if v.get("float_ok") and sector_ok and v.get("halal_ok"):
            out.append(c)
    return out


def get_day_df(sym, date):
    rh = ROOT / f"data/rh_bars/{sym}_{date}.csv"
    src = rh if rh.exists() else (IDIR / f"{sym}_{date}.csv")
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
        w = df[(df.index.time >= ps.NEWS_START) & (df.index.time < ps.NEWS_END)]
        out = pd.DataFrame({"begins_at": w.index.tz_convert("UTC"),
                            "open": w["Open"], "high": w["High"],
                            "low": w["Low"], "close": w["Close"],
                            "volume": w["Volume"]})
        out.to_csv(src, index=False)
    txt = src.read_text()
    if txt.startswith("EMPTY"):
        return None
    df = pd.read_csv(src)
    df["begins_at"] = (pd.to_datetime(df["begins_at"], utc=True)
                       .dt.tz_convert(ps.ET))
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    df = df.set_index("begins_at").sort_index()
    w = df[(df.index.time >= ps.NEWS_START) & (df.index.time < ps.NEWS_END)]
    return w if len(w) >= 8 else None


def main():
    print("Stage 1: discovering YTD gapper days (Jan 1 -> today)...")
    cands = discover()
    print(f"  {len(cands)} qualifying stock-days "
          f"({len({c['symbol'] for c in cands})} symbols)")

    print("Stage 2: float / halal / UPWARD-sector filters...")
    final = filter_symbols(cands)
    print(f"  {len(final)} stock-days survive "
          f"({len({c['symbol'] for c in final})} symbols)")

    by_day = {}
    for c in final:
        if (c["date"] not in by_day
                or c["gain_pct"] > by_day[c["date"]]["gain_pct"]):
            by_day[c["date"]] = c

    print(f"\nStage 3: chronological COMPOUNDING sim from $1000, "
          f"{len(by_day)} qualifying days...\n")
    capital = 1000.0
    day_rets = []
    no_data = []
    for date in sorted(by_day):
        c = by_day[date]
        df = get_day_df(c["symbol"], date)
        if df is None:
            no_data.append((date, c["symbol"], c["gain_pct"]))
            continue
        trades = ps.simulate_trades(df, verbose=False, buy_set=None,
                                    vol_confirm=False, trail_pct=20,
                                    stop_pct=5, prev_close=c["prev_close"],
                                    budget=capital, compound=True)
        pnl = sum(t["pnl"] for t in trades)
        if trades:
            day_rets.append(pnl / capital)
        capital += pnl
        print(f"{date}  {c['symbol']:<6} +{c['gain_pct']:>6.1f}%  "
              f"{len(trades)}t  ${pnl:>+9.2f}  capital ${capital:>10,.2f}",
              flush=True)

    sim_days = len(day_rets)
    avg_ret = (sum(day_rets) / sim_days) if sim_days else 0
    est = capital
    for _ in no_data:
        est *= (1 + avg_ret)

    print(f"\n{'=' * 70}")
    print(f"  YTD RESULT (expanded upward sectors, compounding from $1000)")
    print(f"{'=' * 70}")
    print(f"  Qualifying days: {len(by_day)}  | simulated: with-trades "
          f"{sim_days}, no-intraday-data {len(no_data)} (mostly Jan-Apr)")
    print(f"  SIMULATED capital (real data days): ${capital:,.2f} "
          f"({(capital / 1000 - 1) * 100:+.1f}%)")
    print(f"  Avg daily return on traded days: {avg_ret * 100:+.2f}%")
    print(f"  EXTRAPOLATED incl. no-data days:  ${est:,.2f} "
          f"({(est / 1000 - 1) * 100:+.1f}%)  [ESTIMATE]")
    print(f"\n  No-data days (not simulated): "
          f"{[f'{d} {s} +{g}%' for d, s, g in no_data[:12]]}"
          f"{' ...' if len(no_data) > 12 else ''}")
    (CACHE / "ytd_results.json").write_text(json.dumps(
        {"capital": capital, "est": est, "no_data": no_data,
         "days": len(by_day)}, default=str))


if __name__ == "__main__":
    main()
