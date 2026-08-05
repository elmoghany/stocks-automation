"""Position-size scaling test: what does it take to average +$1,000/day?

Runs the current penny default (dip-reversal + ORB, trail 20%, stop 5%,
all patterns) over the YTD simulated day set at position sizes $1k-$30k,
top-1 and top-2 gappers per day, WITH a liquidity cap: shares per entry
limited to 10% of the entry bar's printed volume (fills beyond that are
fantasy in 0.5-16M float names). Reports avg $/qualifying-day, days over
+$1,000, and how much the liquidity cap bit at each size.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

sys.path.insert(0, str(ROOT / "plan"))
_yspec = importlib.util.spec_from_file_location(
    "ytd", ROOT / "plan" / "penny_backtest_ytd.py")
ytd = importlib.util.module_from_spec(_yspec)
_yspec.loader.exec_module(ytd)

CACHE = ROOT / "data" / "backtest60"
gappers = json.loads((CACHE / "gappers_ytd.json").read_text())
final = ytd.filter_symbols(gappers)

by_day = {}
for c in final:
    by_day.setdefault(c["date"], []).append(c)
for d in by_day:
    by_day[d] = sorted(by_day[d], key=lambda x: -x["gain_pct"])

VOL_FRAC = 0.10   # max 10% of the entry bar's volume

SIZES = [1_000, 5_000, 10_000, 15_000, 20_000, 30_000]


def run(size, top_n):
    total = 0.0
    days = []
    for date in sorted(by_day):
        day_pnl = 0.0
        traded = False
        for c in by_day[date][:top_n]:
            df = ytd.get_day_df(c["symbol"], date)
            if df is None:
                continue
            tr = ps.simulate_trades(df, verbose=False, buy_set=None,
                                    vol_confirm=False, trail_pct=20,
                                    stop_pct=5, prev_close=c["prev_close"],
                                    budget=size, orb=True,
                                    max_vol_frac=VOL_FRAC)
            day_pnl += sum(t["pnl"] for t in tr)
            traded = traded or bool(tr)
        if traded:
            days.append(day_pnl)
        total += day_pnl
    return total, days


def main():
    print(f"Liquidity cap: shares <= {VOL_FRAC:.0%} of entry-bar volume\n")
    print(f"{'size/trade':>10} {'top-N':>5} {'total P&L':>11} {'traded days':>11} "
          f"{'avg $/day':>10} {'days>=+$1k':>10} {'worst day':>10}")
    print("-" * 66)
    for top_n in (1, 2):
        for size in SIZES:
            total, days = run(size, top_n)
            n = len(days)
            avg = total / n if n else 0
            big = sum(1 for d in days if d >= 1000)
            worst = min(days) if days else 0
            print(f"{size:>10,} {top_n:>5} {total:>+11.2f} {n:>11} "
                  f"{avg:>+10.2f} {big:>10} {worst:>+10.2f}", flush=True)


if __name__ == "__main__":
    main()
