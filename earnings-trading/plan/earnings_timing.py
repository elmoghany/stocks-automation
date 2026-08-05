"""EARNINGS-TRADING entry-timing sweep (ET10/ET11).

User question (2026-08-05): if we buy BEFORE the earnings release, when
is the best time -- right before, or a few hours earlier?

For every halal-universe earnings event in the last year we take the
report day's HOURLY bars and simulate buying at each bar's open, with
two exits:
  ET10 (same-day, NO announcement risk): sell at that session's close,
       i.e. before a pm release -- pure pre-earnings run-up capture.
  ET11 (through the release): sell at the next session's open -- carries
       the announcement gap, so it is the timing-resolved version of the
       already-REJECTED buy-before-earnings probe; expect ~0 or worse.
pm (after-close) reporters: entries on the report day itself.
am (before-open) reporters: entries on the prior session (the last
hours before the release), ET10 exit = that session's close.
Report-timing (am/pm) comes from the yfinance earnings timestamp hour.
Buckets are the bar's ET start time (09:30 .. 15:30).
Window: Aug 2025..Jul 2026. Data: yfinance 1h bars (max ~730 days).
$15k notional per event, same as plan/earnings_trading.py.
"""

import importlib.util
import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
from plan.earnings_trading import UNIVERSE, WINDOW, BUDGET  # noqa: E402

CACHE = ROOT / "data/earnings_timing_events.json"


def build():
    halal = json.loads((ROOT / "data/earnings_halal.json").read_text())
    syms = [s for s in UNIVERSE if halal.get(s, {}).get("halal")]
    lo, hi = WINDOW
    rows = []
    for n, sym in enumerate(syms):
        try:
            t = yf.Ticker(sym)
            hd = t.history(period="2y", auto_adjust=True)
            hh = t.history(period="729d", interval="1h", auto_adjust=True)
            if hd.empty or hh.empty:
                continue
            hd.index = hd.index.tz_localize(None)
            ed = t.get_earnings_dates(limit=12)
            if ed is None or len(ed) == 0:
                continue
        except Exception as e:
            print(f"  {sym}: {e}", flush=True)
            continue
        didx = hd.index
        for ts in ed.index:
            d = ts.tz_localize(None).normalize()
            if not (lo <= str(d.date()) <= hi):
                continue
            timing = "pm" if ts.hour >= 15 else ("am" if ts.hour <= 9
                                                 else "mid")
            if timing == "mid":            # ambiguous -- skip
                continue
            if timing == "pm":             # entries on the report day
                entry_day = d if d in didx else None
                nxt = didx[didx > d]
            else:                          # am: entries on prior session
                prev = didx[didx < d]
                entry_day = prev[-1] if len(prev) else None
                nxt = didx[didx >= d]
            if entry_day is None or len(nxt) == 0:
                continue
            close_px = float(hd.loc[entry_day, "Close"])
            next_open = float(hd.loc[nxt[0], "Open"])
            bars = hh[(hh.index.year == entry_day.year)
                      & (hh.index.month == entry_day.month)
                      & (hh.index.day == entry_day.day)]
            for bts, bar in bars.iterrows():
                px = float(bar["Open"])
                if px <= 0:
                    continue
                rows.append(dict(
                    sym=sym, date=str(entry_day.date()), timing=timing,
                    hour=bts.strftime("%H:%M"),
                    pre=round((close_px / px - 1) * 100, 3),
                    thru=round((next_open / px - 1) * 100, 3)))
        if n % 20 == 0:
            print(f"  {n}/{len(syms)}", flush=True)
    CACHE.write_text(json.dumps(rows))
    print(f"saved {len(rows)} entry-points", flush=True)
    return rows


def stat(rets):
    n = len(rets)
    if not n:
        return "     -"
    win = 100 * sum(1 for r in rets if r > 0) / n
    avg = sum(rets) / n
    tot = sum(BUDGET * r / 100 for r in rets)
    return f"n={n:>3} win={win:4.1f}% avg={avg:+6.3f}% ${tot:+9,.0f}"


def report(rows):
    for field, label in (("pre", "ET10 sell at close BEFORE release"
                                 " (no announcement risk)"),
                         ("thru", "ET11 hold THROUGH release to next"
                                  " open (announcement gap risk)")):
        print(f"\n{label}  [{WINDOW[0]}..{WINDOW[1]}]")
        for timing in ("pm", "am"):
            print(f"  {timing} reporters "
                  f"({'report day' if timing == 'pm' else 'prior day'}"
                  f" entries):")
            buckets = defaultdict(list)
            for r in rows:
                if r["timing"] == timing:
                    buckets[r["hour"]].append(r[field])
            for hour in sorted(buckets):
                print(f"    {hour}  {stat(buckets[hour])}")


def main():
    if CACHE.exists() and "--refetch" not in sys.argv:
        rows = json.loads(CACHE.read_text())
    else:
        rows = build()
    report(rows)


if __name__ == "__main__":
    main()
