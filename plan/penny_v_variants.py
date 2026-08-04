"""Three one-change variants each of V2, V3, V6 (9 variants + 3 bases).

Bases:
  V2 = band $2-16, float<=16M, window 7-noon
  V3 = band $2-16, float<=16M, window 7-16 (full day)
  V6 = no ceiling, no float, window 7-16

Variants (exactly ONE change from the base):
  V2a no float limit          V3a no float limit          V6a restore $16 ceiling
  V2b window 7-13 (1PM)       V3b trail 25%               V6b window 7-noon
  V2c trail 25%               V3c no NEW entries after    V6c trail 25%
                                  noon (exits run to 4PM)

All: $15k/position, 10% bar-volume cap, one top gapper/day, halal +
upward sectors + up>=10% + rvol>=5x always on. Same real-data day sets.
"""

import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

sys.path.insert(0, str(ROOT / "plan"))
_espec = importlib.util.spec_from_file_location(
    "exp", ROOT / "plan" / "penny_expand_test.py")
exp = importlib.util.module_from_spec(_espec)
_espec.loader.exec_module(exp)
ytd = exp.ytd

_e2 = importlib.util.spec_from_file_location(
    "exp2", ROOT / "plan" / "penny_expand2.py")
exp2 = importlib.util.module_from_spec(_e2)
_e2.loader.exec_module(exp2)

CACHE = ROOT / "data" / "backtest60"
BUDGET = 15_000.0

band_raw = json.loads((CACHE / "gappers_ytd.json").read_text())
noceil_raw = json.loads((CACHE / "gappers_ytd_noceil.json").read_text())

POOLS = {
    "band_float": ytd.filter_symbols(band_raw),
    "band_nofloat": exp2.filter_no_float(band_raw),
    "noceil_nofloat": exp2.filter_no_float(noceil_raw),
    "noceil_float": ytd.filter_symbols(noceil_raw),
}


def run(name, pool, end_t, price_max, trail=20, entry_cutoff=None):
    days = []
    total = 0.0
    saved = ps.PRICE_MAX
    ps.PRICE_MAX = price_max
    try:
        for date, c in sorted(exp.day_pick(POOLS[pool]).items()):
            df = exp.get_full_df(c["symbol"], date)
            if df is None:
                continue
            w = df[(df.index.time >= dtime(7, 0)) & (df.index.time < end_t)]
            if len(w) < 8:
                continue
            tr = ps.simulate_trades(w, verbose=False, buy_set=None,
                                    vol_confirm=False, trail_pct=trail,
                                    stop_pct=5, prev_close=c["prev_close"],
                                    budget=BUDGET, orb=True,
                                    max_vol_frac=0.10,
                                    entry_cutoff=entry_cutoff)
            pnl = sum(t["pnl"] for t in tr)
            if tr:
                days.append(pnl)
            total += pnl
    finally:
        ps.PRICE_MAX = saved
    n = len(days)
    wins = sum(1 for d in days if d > 0)
    big = sum(1 for d in days if d >= 1000)
    print(f"{name:<36} {n:>4} {total:>+11.2f} {total / n if n else 0:>+9.2f} "
          f"{wins:>3}/{n:<3} {big:>4} {min(days) if days else 0:>+9.2f}",
          flush=True)
    return total


def main():
    print(f"{'VARIANT (one change from base)':<36} {'days':>4} "
          f"{'total':>11} {'avg/day':>9} {'win':>7} {'>=1k':>4} {'worst':>9}")
    print("-" * 88)
    run("V2  base: $2-16 float 7-noon", "band_float", dtime(12, 0), 16.0)
    run("V2a  -> no float limit", "band_nofloat", dtime(12, 0), 16.0)
    run("V2b  -> window 7-1PM", "band_float", dtime(13, 0), 16.0)
    run("V2c  -> trail 25%", "band_float", dtime(12, 0), 16.0, trail=25)
    print("-" * 88)
    run("V3  base: $2-16 float 7-4PM", "band_float", dtime(16, 0), 16.0)
    run("V3a  -> no float limit", "band_nofloat", dtime(16, 0), 16.0)
    run("V3b  -> trail 25%", "band_float", dtime(16, 0), 16.0, trail=25)
    run("V3c  -> no new entries after noon", "band_float", dtime(16, 0), 16.0,
        entry_cutoff=dtime(12, 0))
    print("-" * 88)
    run("V6  base: no-ceil no-float 7-4PM", "noceil_nofloat", dtime(16, 0), 1e9)
    run("V6a  -> restore $16 ceiling", "band_nofloat", dtime(16, 0), 16.0)
    run("V6b  -> window 7-noon", "noceil_nofloat", dtime(12, 0), 1e9)
    run("V6c  -> trail 25%", "noceil_nofloat", dtime(16, 0), 1e9, trail=25)


if __name__ == "__main__":
    main()
