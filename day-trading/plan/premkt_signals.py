"""CAN WE QUALIFY CANDIDATES IN EXTENDED HOURS? (2026-08-07)

The projected-rvol gate failed because it compared premarket volume to
a MARKET-WIDE profile whose premarket share is wildly skewed (mean
5.1%, median 0.1%). That is the wrong yardstick.

Better idea: premarket volume is not small in ABSOLUTE terms on the
names we want. A stock that trades 300k shares before 09:30 when its
whole normal DAY is 800k is screaming, and every input for that
statement is available at 07:00.

Signals tested (all causal, all computable pre-open):
  pm_vs_avg50  premarket volume / 50-day average DAILY volume
  pm_dollars   premarket dollar volume (absolute)
  pm_x_gap     pm_vs_avg50 x the 7AM gap %
  pm_share     premarket volume / that day's eventual volume  (NOT
               causal -- included only as an upper bound on how much
               signal premarket volume could ever carry)
Scored against the gate the backtest actually uses (full-day rvol >= 5)
on every cached candidate-day, and -- more importantly -- against the
DAY'S REALISED P&L from the C35 trade record, because the question is
not "does it predict rvol" but "does it find the days that pay".
"""

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
M1 = ROOT / "data/massive/m1"
OPEN_MIN = 9 * 60 + 30


def load_pool():
    out = {}
    for lab in ("year", "y2025"):
        f = ROOT / f"data/massive/gappers2_{lab}.json"
        if f.exists():
            for c in json.loads(f.read_text()):
                if c.get("rvol") and c.get("volume"):
                    out[(c["symbol"], c["date"])] = c
    return out


def load_pnl():
    """day -> realised P&L from the C35 trade record."""
    out = {}
    for lab in ("year", "y2025"):
        f = ROOT / f"data/massive/s093_trades_{lab}.json"
        if f.exists():
            for d in json.loads(f.read_text()):
                out[(d["symbol"], d["date"])] = d["pnl"]
    return out


def main():
    pool, pnl = load_pool(), load_pnl()
    rows = []
    for f in M1.glob("*.csv"):
        sym, date = f.stem.rsplit("_", 1)
        c = pool.get((sym, date))
        if not c:
            continue
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
        except Exception:
            continue
        if len(df) < 30 or df.index.tz is None:
            continue
        df.index = df.index.tz_convert("America/New_York")
        mins = df.index.hour * 60 + df.index.minute
        pm = df[mins < OPEN_MIN]
        if not len(pm):
            continue
        pmv = float(pm["Volume"].sum())
        pmd = float((pm["Volume"] * pm["Close"]).sum())
        avg50 = c["volume"] / c["rvol"]
        gap = ((float(pm["Close"].iloc[-1]) / c["prev_close"] - 1) * 100
               if c.get("prev_close") else 0.0)
        rows.append(dict(
            sym=sym, date=date, true_rvol=c["rvol"], pnl=pnl.get((sym, date)),
            pm_vs_avg50=pmv / avg50 if avg50 else 0.0,
            pm_dollars=pmd,
            pm_x_gap=(pmv / avg50 if avg50 else 0.0) * max(gap, 0.0),
            pm_share=pmv / c["volume"] if c["volume"] else 0.0))
    print(f"candidate-days with premarket bars: {len(rows):,}")
    traded = [r for r in rows if r["pnl"] is not None]
    print(f"of which C35 actually traded: {len(traded):,} "
          f"(total ${sum(r['pnl'] for r in traded):+,.0f})")

    print("\nPREMARKET SIGNAL DISTRIBUTION (all candidate-days)")
    for k in ("pm_vs_avg50", "pm_dollars", "pm_share"):
        v = sorted(r[k] for r in rows)
        q = lambda p: v[int(len(v) * p)]
        print(f"  {k:<13} p10 {q(.10):>12,.2f}  median {q(.50):>12,.2f}  "
              f"p90 {q(.90):>12,.2f}")

    # Does a premarket threshold select the PROFITABLE days?
    print("\nIF WE GATE ON pm_vs_avg50 (premarket volume as a multiple of a "
          "normal FULL day):")
    print(f"  {'threshold':>10}{'days kept':>11}{'% of days':>11}"
          f"{'P&L kept':>14}{'% of P&L':>10}{'$/day':>10}")
    tot_pnl = sum(r["pnl"] for r in traded)
    for th in (0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 1.00):
        keep = [r for r in traded if r["pm_vs_avg50"] >= th]
        if not keep:
            continue
        p = sum(r["pnl"] for r in keep)
        print(f"  {th:>10.2f}{len(keep):>11,}{100*len(keep)/len(traded):>10.0f}%"
              f"{p:>+14,.0f}{100*p/tot_pnl:>9.0f}%{p/len(keep):>10,.0f}")

    print("\nSAME, gating on premarket DOLLAR volume:")
    print(f"  {'threshold':>12}{'days kept':>11}{'% of days':>11}"
          f"{'P&L kept':>14}{'% of P&L':>10}{'$/day':>10}")
    for th in (50_000, 100_000, 250_000, 500_000, 1_000_000, 2_500_000):
        keep = [r for r in traded if r["pm_dollars"] >= th]
        if not keep:
            continue
        p = sum(r["pnl"] for r in keep)
        print(f"  ${th:>11,}{len(keep):>11,}"
              f"{100*len(keep)/len(traded):>10.0f}%"
              f"{p:>+14,.0f}{100*p/tot_pnl:>9.0f}%{p/len(keep):>10,.0f}")

    (ROOT / "data/massive/premkt_signals.json").write_text(json.dumps(
        [{k: v for k, v in r.items()} for r in rows]))


if __name__ == "__main__":
    main()
