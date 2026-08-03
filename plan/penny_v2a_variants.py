"""Second-generation sweep from the NEW base (V2a = $2-16, NO float limit,
7-noon window). One change per variant.

Top-3 performers from the last sweep and their variants:
  V2a base ($2-16, no-float, 7-noon)   A1 window 7-11AM
                                       A2 top-2 gappers/day
                                       A3 stop 8%
  V3a base ($2-16, no-float, 7-4PM)    B1 no NEW entries after noon
                                       B2 window 7-2PM
                                       B3 top-2 gappers/day
  V6b base (no-ceil, no-float, 7-noon) C1 top-2 gappers/day
                                       C2 ceiling $30
                                       C3 no NEW entries after 11AM
Price-cap variants (4th set, from V2a): ceiling $14 / $12 / $10.

All: $15k/position, 10% bar-volume cap, trail 20 / stop 5 (unless varied),
halal + upward sectors + up>=10% + rvol>=5x.
"""

import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "penny-stocks.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

sys.path.insert(0, str(ROOT / "plan"))
_espec = importlib.util.spec_from_file_location(
    "exp", ROOT / "plan" / "penny_expand_test.py")
exp = importlib.util.module_from_spec(_espec)
_espec.loader.exec_module(exp)

_e2 = importlib.util.spec_from_file_location(
    "exp2", ROOT / "plan" / "penny_expand2.py")
exp2 = importlib.util.module_from_spec(_e2)
_e2.loader.exec_module(exp2)

CACHE = ROOT / "data" / "backtest60"
BUDGET = 15_000.0

band_raw = json.loads((CACHE / "gappers_ytd.json").read_text())
noceil_raw = json.loads((CACHE / "gappers_ytd_noceil.json").read_text())
POOL_BAND = exp2.filter_no_float(band_raw)
POOL_NOCEIL = exp2.filter_no_float(noceil_raw)


def pick(pool, top_n):
    by_day = {}
    for c in pool:
        by_day.setdefault(c["date"], []).append(c)
    return {d: sorted(cs, key=lambda x: -x["gain_pct"])[:top_n]
            for d, cs in by_day.items()}


def run(name, pool, end_t, price_max, top_n=1, stop=5,
        entry_cutoff=None):
    days = []
    total = 0.0
    saved = ps.PRICE_MAX
    ps.PRICE_MAX = price_max
    try:
        for date, cands in sorted(pick(pool, top_n).items()):
            day_pnl = 0.0
            traded = False
            for c in cands:
                df = exp.get_full_df(c["symbol"], date)
                if df is None:
                    continue
                w = df[(df.index.time >= dtime(7, 0))
                       & (df.index.time < end_t)]
                if len(w) < 8:
                    continue
                tr = ps.simulate_trades(w, verbose=False, buy_set=None,
                                        vol_confirm=False, trail_pct=20,
                                        stop_pct=stop,
                                        prev_close=c["prev_close"],
                                        budget=BUDGET, orb=True,
                                        max_vol_frac=0.10,
                                        entry_cutoff=entry_cutoff)
                day_pnl += sum(t["pnl"] for t in tr)
                traded = traded or bool(tr)
            if traded:
                days.append(day_pnl)
            total += day_pnl
    finally:
        ps.PRICE_MAX = saved
    n = len(days)
    wins = sum(1 for d in days if d > 0)
    big = sum(1 for d in days if d >= 1000)
    print(f"{name:<38} {n:>4} {total:>+11.2f} {total / n if n else 0:>+9.2f} "
          f"{wins:>3}/{n:<3} {big:>4} {min(days) if days else 0:>+9.2f}",
          flush=True)


def main():
    print(f"{'VARIANT (one change from base)':<38} {'days':>4} "
          f"{'total':>11} {'avg/day':>9} {'win':>7} {'>=1k':>4} {'worst':>9}")
    print("-" * 92)
    run("V2a BASE $2-16 nofloat 7-noon", POOL_BAND, dtime(12, 0), 16.0)
    run("A1  -> window 7-11AM", POOL_BAND, dtime(11, 0), 16.0)
    run("A2  -> top-2 gappers/day", POOL_BAND, dtime(12, 0), 16.0, top_n=2)
    run("A3  -> stop 8%", POOL_BAND, dtime(12, 0), 16.0, stop=8)
    print("-" * 92)
    run("V3a BASE $2-16 nofloat 7-4PM", POOL_BAND, dtime(16, 0), 16.0)
    run("B1  -> no new entries after noon", POOL_BAND, dtime(16, 0), 16.0,
        entry_cutoff=dtime(12, 0))
    run("B2  -> window 7-2PM", POOL_BAND, dtime(14, 0), 16.0)
    run("B3  -> top-2 gappers/day", POOL_BAND, dtime(16, 0), 16.0, top_n=2)
    print("-" * 92)
    run("V6b BASE noceil nofloat 7-noon", POOL_NOCEIL, dtime(12, 0), 1e9)
    run("C1  -> top-2 gappers/day", POOL_NOCEIL, dtime(12, 0), 1e9, top_n=2)
    run("C2  -> ceiling $30", POOL_NOCEIL, dtime(12, 0), 30.0)
    run("C3  -> no new entries after 11AM", POOL_NOCEIL, dtime(12, 0), 1e9,
        entry_cutoff=dtime(11, 0))
    print("-" * 92)
    run("CAP14 -> V2a with ceiling $14", POOL_BAND, dtime(12, 0), 14.0)
    run("CAP12 -> V2a with ceiling $12", POOL_BAND, dtime(12, 0), 12.0)
    run("CAP10 -> V2a with ceiling $10", POOL_BAND, dtime(12, 0), 10.0)


if __name__ == "__main__":
    main()
