"""One-parameter-at-a-time sensitivity sweep from the trail20 baseline.

Baseline (the new penny default): all bullish patterns, no volume gate,
trail 20% from peak, hard stop -5%, one gapper/day (biggest gain among the
rule-passing candidates), $1000/trade, 7-10 AM ET, same-day flatten.
HELD FIXED per user: halal gate, up>=10% (at entry and day selection).

Each variant changes exactly ONE thing. Day set and data identical across
variants (except the day-selection variants, noted). Uses cached discovery
results (data/backtest60/) + Robinhood 5-min CSVs (data/rh_bars/) +
yfinance 5-min for the rest, cached locally on first run.
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
IDIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Qualifying candidates (already discovered + rule-filtered)
# ---------------------------------------------------------------------------
gappers = json.loads((CACHE / "gapper_days.json").read_text())
verdicts = json.loads((CACHE / "symbol_rules.json").read_text())
passing = [g for g in gappers
           if (v := verdicts.get(g["symbol"], {})).get("float_ok")
           and v.get("sector_ok") and v.get("halal_ok")]


def pick_days(min_rvol=5.0, top_n=1):
    """day -> top-N candidates by gain, among those with rvol >= min_rvol."""
    by_day = {}
    for c in passing:
        if c["rvol"] < min_rvol:
            continue
        by_day.setdefault(c["date"], []).append(c)
    return {d: sorted(cs, key=lambda x: -x["gain_pct"])[:top_n]
            for d, cs in by_day.items()}


def get_day_df(sym, date):
    """Intraday 5-min window bars: RH CSV first, else cached yf, else fetch."""
    rh = ROOT / f"data/rh_bars/{sym}_{date}.csv"
    src = rh if rh.exists() else (IDIR / f"{sym}_{date}.csv")
    if not src.exists():
        import yfinance as yf
        d0 = datetime.strptime(date, "%Y-%m-%d")
        df = yf.Ticker(sym).history(
            start=date, end=(d0 + timedelta(days=1)).strftime("%Y-%m-%d"),
            interval="5m", prepost=True)
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


def run_variant(name, sim_kwargs=None, patch=None, min_rvol=5.0, top_n=1):
    """Total P&L across the period for one parameter variant."""
    saved = {}
    for k, v in (patch or {}).items():
        saved[k] = getattr(ps, k)
        setattr(ps, k, v)
    base = dict(verbose=False, buy_set=None, vol_confirm=False,
                trail_pct=20, stop_pct=5)
    base.update(sim_kwargs or {})
    total = 0.0
    n = 0
    days = 0
    try:
        for date, cands in sorted(pick_days(min_rvol, top_n).items()):
            for c in cands:
                df = get_day_df(c["symbol"], date)
                if df is None:
                    continue
                trades = ps.simulate_trades(df, prev_close=c["prev_close"],
                                            **base)
                total += sum(t["pnl"] for t in trades)
                n += len(trades)
                days += 1
    finally:
        for k, v in saved.items():
            setattr(ps, k, v)
    return name, total, n, days


VARIANTS = [
    ("BASELINE trail20/stop5/allpat", None, None, 5.0, 1),
    ("trail 10%", {"trail_pct": 10}, None, 5.0, 1),
    ("trail 15%", {"trail_pct": 15}, None, 5.0, 1),
    ("trail 25%", {"trail_pct": 25}, None, 5.0, 1),
    ("trail 30%", {"trail_pct": 30}, None, 5.0, 1),
    ("stop 3%", {"stop_pct": 3}, None, 5.0, 1),
    ("stop 8%", {"stop_pct": 8}, None, 5.0, 1),
    ("stop 10%", {"stop_pct": 10}, None, 5.0, 1),
    ("entry hammer_family", {"buy_set": ps.BUY_SETS["hammer_family"]}, None, 5.0, 1),
    ("entry strong_reversal", {"buy_set": ps.BUY_SETS["strong_reversal"]}, None, 5.0, 1),
    ("entry multi_candle", {"buy_set": ps.BUY_SETS["multi_candle"]}, None, 5.0, 1),
    ("vol confirm ON", {"vol_confirm": True}, None, 5.0, 1),
    ("max 1 trade/day", {"max_trades": 1}, None, 5.0, 1),
    ("max 2 trades/day", {"max_trades": 2}, None, 5.0, 1),
    ("max 3 trades/day", {"max_trades": 3}, None, 5.0, 1),
    ("surge 1% (easier arm)", None, {"SURGE_PCT": 1.0}, 5.0, 1),
    ("surge 3% (stricter arm)", None, {"SURGE_PCT": 3.0}, 5.0, 1),
    ("surge 5% (strictest arm)", None, {"SURGE_PCT": 5.0}, 5.0, 1),
    ("dip 2c (quicker entry)", None, {"DIP_MIN_CENTS": 0.02}, 5.0, 1),
    ("dip 10c (deeper dip)", None, {"DIP_MIN_CENTS": 0.10}, 5.0, 1),
    ("dip 20c (deepest dip)", None, {"DIP_MIN_CENTS": 0.20}, 5.0, 1),
    ("band ceiling $20", None, {"PRICE_MAX": 20.0}, 5.0, 1),
    ("band ceiling $30", None, {"PRICE_MAX": 30.0}, 5.0, 1),
    ("rvol >= 8x (fewer days)", None, None, 8.0, 1),
    ("rvol >= 15x (A+ days only)", None, None, 15.0, 1),
    ("trade top-2 gappers/day", None, None, 5.0, 2),
]


def main():
    print(f"{len(passing)} rule-passing stock-days feed the sweep\n")
    rows = []
    for name, kw, patch, rvol, topn in VARIANTS:
        name, total, n, days = run_variant(name, kw, patch, rvol, topn)
        rows.append((total, name, n, days))
        print(f"  {name:<28} {days:>3} day-sims {n:>3} trades "
              f"${total:>+10.2f}", flush=True)

    rows.sort(reverse=True)
    base_total = next(t for t, nm, *_ in rows if nm.startswith("BASELINE"))
    print(f"\n{'=' * 66}")
    print(f"{'VARIANT':<30} {'trades':>6} {'P&L':>11} {'vs base':>10}")
    print("-" * 66)
    for total, name, n, days in rows:
        print(f"{name:<30} {n:>6} {total:>+11.2f} {total - base_total:>+10.2f}")


if __name__ == "__main__":
    main()
