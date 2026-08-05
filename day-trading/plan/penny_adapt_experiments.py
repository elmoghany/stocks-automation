"""Adaptation experiments: make the strategy earn in EVERY regime.

User thesis: there is no "cold year" -- news and hot sectors always exist;
if returns drop, the strategy must adapt. Each experiment is ONE change
from the live default (C1 top-1 x $15k + calm-gap, 7-noon), run on BOTH
years from cached Massive 1-min bars.

  E0 baseline      live default
  E1 dyn-sectors   upward-sector list recomputed AS-OF each month
                   (sector ETF 1y>0 AND >200SMA at month start)
  E3 adaptive-gap  calm-gap threshold = median of trailing 20 top-pick
                   7AM gaps (clamped 10..40%) instead of fixed 20%
  E5 eq-throttle   rolling 5-day P&L < -$3k -> half size until >= 0
  E7 day2-cont     if yesterday's pick made >= +$2k and today opens calm,
                   trade it again when today has no calm fresh gapper
  E9 two-shot      if the day's trades ended red before 9AM, take ONE
                   re-pick from the next calm candidate (same $15k)
"""

import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)
ps.SURGE_WINDOW_MIN = 50
ps.PRICE_MAX = float("inf")

M1 = ROOT / "data" / "massive" / "m1"
VER = json.loads((ROOT / "data/backtest60/rules_ytd.json").read_text())

GROUPS = {
    "XLK": ["technology", "software", "semiconductor",
            "artificial intelligence"],
    "XLV": ["health", "biotech", "pharmaceutical", "drug", "medical"],
    "XLI": ["industrial", "machinery", "engineering", "construction",
            "transport", "trucking", "railroads"],
    "XLE": ["energy", "oil", "gas", "solar", "renewable", "petroleum"],
    "XLB": ["materials", "chemical", "mining", "gold", "silver", "steel",
            "copper"],
    "XLP": ["consumer defensive", "food", "beverage", "household",
            "grocery", "discount stores", "packaged foods"],
    "XLRE": ["real estate", "reit"],
    "XLY": ["consumer cyclical", "retail", "apparel", "auto", "restaurant",
            "leisure", "travel"],
    "XLC": ["communication", "media", "telecom", "entertainment",
            "advertising"],
    "XLU": ["utilities", "utility"],
}
ALL_WORDS = [w for ws in GROUPS.values() for w in ws]
STATIC_UP = (GROUPS["XLK"] + GROUPS["XLV"] + GROUPS["XLI"] + GROUPS["XLE"]
             + GROUPS["XLB"] + GROUPS["XLP"] + GROUPS["XLRE"])


def month_up_words():
    """Per-month allowed keyword list from ETF trends AS-OF month start."""
    cache = ROOT / "data/massive/sector_months.json"
    if cache.exists():
        return json.loads(cache.read_text())
    import yfinance as yf
    out = {}
    hist = {etf: yf.Ticker(etf).history(period="3y")["Close"]
            for etf in GROUPS}
    months = (["2024-%02d" % m for m in range(10, 13)]
              + ["2025-%02d" % m for m in range(1, 13)]
              + ["2026-%02d" % m for m in range(1, 8)])
    for m in months:
        asof = pd.Timestamp(m + "-01")
        words = []
        for etf, ws in GROUPS.items():
            h = hist[etf]
            hh = h[h.index.tz_localize(None) < asof]
            if len(hh) < 210:
                continue
            ret1y = hh.iloc[-1] / hh.iloc[-252] - 1 if len(hh) >= 252 else \
                hh.iloc[-1] / hh.iloc[0] - 1
            sma200 = hh.rolling(200).mean().iloc[-1]
            if ret1y > 0 and hh.iloc[-1] > sma200:
                words += ws
        out[m] = words
    cache.write_text(json.dumps(out))
    return out


def get(sym, date):
    f = M1 / f"{sym}_{date}.csv"
    if not f.exists() or f.read_text(errors="ignore").startswith("EMPTY"):
        return None
    df = pd.read_csv(f)
    df["begins_at"] = (pd.to_datetime(df["begins_at"], utc=True)
                       .dt.tz_convert(ps.ET))
    return df.set_index("begins_at").sort_index()


def load_days(label, sector_words=None, monthly_words=None):
    gap = json.loads(
        (ROOT / f"data/massive/gappers_{label}.json").read_text())
    by_day = {}
    for c in gap:
        v = VER.get(c["symbol"], {})
        if not v.get("halal_ok"):
            continue
        sec = v.get("sector_raw", "").lower()
        if monthly_words is not None:
            words = monthly_words.get(c["date"][:7], [])
        else:
            words = sector_words
        if not any(w in sec for w in words):
            continue
        by_day.setdefault(c["date"], []).append(c)
    return by_day


def g7_of(c, w):
    return ((float(w["Open"].iloc[0]) / c["prev_close"] - 1) * 100
            if c["prev_close"] else 999)


def sim(c, w, budget):
    tr = ps.simulate_trades(w, verbose=False, buy_set=None,
                            vol_confirm=False, trail_pct=20, stop_pct=5,
                            prev_close=c["prev_close"], budget=budget,
                            orb=True, orb_bars=15, max_vol_frac=0.10,
                            vol_frac_window=5)
    return tr


def run(label, mode, monthly_words=None):
    by_day = load_days(label,
                       sector_words=None if mode == "E1" else STATIC_UP,
                       monthly_words=monthly_words if mode == "E1" else None)
    days = []
    monthly = {}
    recent_g7 = []
    rolling = []
    budget_scale = 1.0
    prev_day_info = None   # (symbol, day_pnl)
    for date, cs in sorted(by_day.items()):
        ranked = sorted(cs, key=lambda x: -x["gain_pct"])
        thresh = 20.0
        if mode == "E3" and len(recent_g7) >= 5:
            thresh = min(40.0, max(10.0, sorted(recent_g7[-20:])[
                len(recent_g7[-20:]) // 2]))
        picked = None
        backup = None
        for c in ranked[:4]:
            df = get(c["symbol"], date)
            if df is None:
                continue
            w = df[(df.index.time >= dtime(7, 0))
                   & (df.index.time < dtime(12, 0))]
            if len(w) < 20:
                continue
            g = g7_of(c, w)
            if ranked and c is ranked[0]:
                recent_g7.append(g)
            if g <= thresh:
                if picked is None:
                    picked = (c, w)
                elif backup is None:
                    backup = (c, w)
        # E7: day-2 continuation as fallback
        if picked is None and mode == "E7" and prev_day_info \
                and prev_day_info[1] >= 2000:
            sym = prev_day_info[0]
            df = get(sym, date)
            if df is not None:
                w = df[(df.index.time >= dtime(7, 0))
                       & (df.index.time < dtime(12, 0))]
                if len(w) >= 20:
                    pc = float(w["Open"].iloc[0]) / 1.0
                    fake = {"symbol": sym, "prev_close": None,
                            "gain_pct": 0}
                    picked = (fake, w)
        if picked is None:
            prev_day_info = None
            continue
        c, w = picked
        budget = 15000 * (budget_scale if mode == "E5" else 1.0)
        tr = sim(c, w, budget)
        dp = sum(x["pnl"] for x in tr)
        # E9: two-shot -- if red and done before 9AM, one re-pick
        if mode == "E9" and tr and dp < 0 and backup is not None:
            last_exit = max(t["exit_time"] for t in tr)
            if last_exit.time() < dtime(9, 0):
                c2, w2 = backup
                w2b = w2[w2.index.time >= dtime(9, 0)]
                if len(w2b) >= 10:
                    tr2 = sim(c2, w2b, budget)
                    dp += sum(x["pnl"] for x in tr2)
                    tr = tr + tr2
        if not tr:
            prev_day_info = None
            continue
        days.append(dp)
        m = date[:7]
        monthly.setdefault(m, []).append(dp)
        prev_day_info = (c.get("symbol"), dp)
        if mode == "E5":
            rolling.append(dp)
            r5 = sum(rolling[-5:])
            budget_scale = 0.5 if r5 < -3000 else 1.0
    negm = sum(1 for v in monthly.values() if sum(v) < 0)
    tot = sum(days)
    return (tot, len(days), tot / len(days) if days else 0, negm,
            len(monthly))


def main():
    mw = month_up_words()
    print(f"{'EXPERIMENT':<16} {'year':<6} {'days':>5} {'total':>12} "
          f"{'avg/day':>9} {'neg-months':>11}")
    for mode, name in [("E0", "E0 baseline"), ("E1", "E1 dyn-sectors"),
                       ("E3", "E3 adaptive-gap"), ("E5", "E5 eq-throttle"),
                       ("E7", "E7 day2-cont"), ("E9", "E9 two-shot")]:
        for label, yr in [("year", "Y1"), ("y2025", "Y2")]:
            tot, n, avg, negm, nm = run(label, mode,
                                        monthly_words=mw)
            print(f"{name:<16} {yr:<6} {n:>5} {tot:>+12,.0f} {avg:>+9,.0f} "
                  f"{negm:>7}/{nm:<3}", flush=True)


if __name__ == "__main__":
    main()
