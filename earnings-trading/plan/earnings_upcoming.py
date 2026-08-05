"""EARNINGS-TRADING live helper: list upcoming earnings (next N days,
default 7) for the halal universe, with each name's historical reaction
stats so the morning-after trade can be planned the night before.

For each upcoming reporter it prints, from data/earnings_rx_events.json
(built by plan/earnings_trading.py):
  n events, % of gaps >= +3%, mean same-day open->close return after a
  gap-up >= +3%, mean after a gap-down <= -3%, and last-event reaction.
Usage: python plan/earnings_upcoming.py [--days N]
Halal gate: data/earnings_halal.json (refresh via earnings_trading.py).
"""

import json
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

import yfinance as yf

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
from plan.earnings_trading import UNIVERSE  # noqa: E402

DAYS = (int(sys.argv[sys.argv.index("--days") + 1])
        if "--days" in sys.argv else 7)


def main():
    halal = json.loads((ROOT / "data/earnings_halal.json").read_text())
    events = json.loads((ROOT / "data/earnings_rx_events.json").read_text())
    syms = [s for s in UNIVERSE if halal.get(s, {}).get("halal")]
    today, horizon = date.today(), date.today() + timedelta(days=DAYS)
    rows = []
    for n, sym in enumerate(syms):
        try:
            ed = yf.Ticker(sym).get_earnings_dates(limit=8)
            if ed is None or len(ed) == 0:
                continue
            future = sorted(d.date() for d in ed.index.tz_localize(None)
                            if today <= d.date() <= horizon)
        except Exception:
            continue
        if not future:
            continue
        evs = events.get(sym, [])
        ups = [e["day"] for e in evs if e["gap"] >= 3]
        downs = [e["day"] for e in evs if e["gap"] <= -3]
        rows.append(dict(
            sym=sym, when=str(future[0]), n=len(evs),
            up_rate=round(100 * len(ups) / len(evs), 0) if evs else None,
            up_day=round(sum(ups) / len(ups), 2) if ups else None,
            dn_day=round(sum(downs) / len(downs), 2) if downs else None,
            last=evs[-1]["day"] if evs else None))
        if n % 25 == 0:
            print(f"  ...{n}/{len(syms)}", flush=True)
    rows.sort(key=lambda r: r["when"])
    print(f"\nhalal names reporting {today} .. {horizon}:")
    print(f"{'sym':<6} {'date':<11} {'nEv':>4} {'gap>=3%':>8} "
          f"{'avg day% after +gap':>20} {'after -gap':>11} {'lastRx%':>8}")
    for r in rows:
        print(f"{r['sym']:<6} {r['when']:<11} {r['n']:>4} "
              f"{(str(r['up_rate']) + '%') if r['up_rate'] is not None else '-':>8} "
              f"{r['up_day'] if r['up_day'] is not None else '-':>20} "
              f"{r['dn_day'] if r['dn_day'] is not None else '-':>11} "
              f"{r['last'] if r['last'] is not None else '-':>8}")
    if not rows:
        print("  (none found in window)")


if __name__ == "__main__":
    main()
