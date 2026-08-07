"""Does ONE premarket gate serve every stock class? (2026-08-07)

The share-ratio floor (premarket volume / 50-day average DAILY volume)
was calibrated on penny gappers, whose median is 1.75x. Large caps sit
near 0.01-0.05x, so the same floor rejected TWLO on a day it made
+$1,267. Before adopting a single dollar floor, test whether either
metric -- or a combination -- actually works across classes.

NOTE ON THE TWO METRICS: they are not redundant, and they are not the
same measure in different units.
  * pm_dollars (absolute) answers "is there enough liquidity to fill?"
  * pm_ratio (relative)   answers "is this stock unusually busy?"
  * dollar-normalising the ratio is ALGEBRAICALLY IDENTICAL to the share
    ratio (pm$/avg$ = pm_vol*px / (avg_vol*px)), so it adds nothing.
Scored on C35's realised per-day P&L, split by price band.
"""

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
M1 = ROOT / "data/massive/m1"
OPEN_MIN = 9 * 60 + 30
BANDS = [(0, 5, "$2-5"), (5, 20, "$5-20"), (20, 100, "$20-100"),
         (100, 1e9, "$100+")]


def band_of(px):
    for lo, hi, name in BANDS:
        if lo <= px < hi:
            return name
    return "?"


def main():
    pool = {}
    for lab in ("year", "y2025"):
        f = ROOT / f"data/massive/gappers2_{lab}.json"
        if f.exists():
            for c in json.loads(f.read_text()):
                if c.get("rvol") and c.get("volume"):
                    pool[(c["symbol"], c["date"])] = c
    pnl = {}
    for lab in ("year", "y2025"):
        f = ROOT / f"data/massive/s093_trades_{lab}.json"
        if f.exists():
            for d in json.loads(f.read_text()):
                pnl[(d["symbol"], d["date"])] = d["pnl"]

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
        rows.append(dict(
            sym=sym, date=date, px=c["prev_close"] or 0.0,
            band=band_of(c["prev_close"] or 0.0),
            ratio=pmv / avg50 if avg50 else 0.0, dollars=pmd,
            pnl=pnl.get((sym, date))))
    traded = [r for r in rows if r["pnl"] is not None]
    tot = sum(r["pnl"] for r in traded)
    print(f"{len(rows):,} candidate-days with premarket bars; "
          f"{len(traded):,} traded by C35 (${tot:+,.0f})\n")

    # ---- how the two metrics differ BY CLASS -------------------------
    print("MEDIAN PREMARKET FOOTPRINT BY PRICE BAND (traded days)")
    print(f"  {'band':<10}{'n':>5}{'med ratio':>12}{'med $':>14}"
          f"{'P&L':>13}")
    by = defaultdict(list)
    for r in traded:
        by[r["band"]].append(r)
    for _, _, name in BANDS:
        v = by.get(name, [])
        if not v:
            continue
        med_r = sorted(x["ratio"] for x in v)[len(v) // 2]
        med_d = sorted(x["dollars"] for x in v)[len(v) // 2]
        print(f"  {name:<10}{len(v):>5}{med_r:>12.3f}{med_d:>14,.0f}"
              f"{sum(x['pnl'] for x in v):>+13,.0f}")

    # ---- P&L retention: one global floor, each metric ----------------
    def retention(key, floors, fmt):
        print(f"\nGLOBAL FLOOR on {key}: P&L kept overall, and BY BAND")
        hdr = f"  {'floor':>12}{'kept':>8}{'%P&L':>7}"
        for _, _, nm in BANDS:
            hdr += f"{nm:>9}"
        print(hdr)
        for th in floors:
            keep = [r for r in traded if r[key] >= th]
            p = sum(r["pnl"] for r in keep)
            line = f"  {fmt(th):>12}{len(keep):>8}{100*p/tot:>6.0f}%"
            for _, _, nm in BANDS:
                v = by.get(nm, [])
                if not v:
                    line += f"{'-':>9}"
                    continue
                tb = sum(x["pnl"] for x in v)
                kb = sum(x["pnl"] for x in v if x[key] >= th)
                line += f"{(100*kb/tb if tb else 0):>8.0f}%"
            print(line)

    retention("ratio", [0.0, 0.01, 0.02, 0.05, 0.10, 0.25, 0.50, 1.00],
              lambda t: f"{t:.2f}x")
    retention("dollars", [0, 10_000, 25_000, 50_000, 100_000, 250_000,
                          1_000_000], lambda t: f"${t:,}")

    # ---- combined gate ----------------------------------------------
    print("\nCOMBINED (dollars AND ratio) -- % of total P&L kept")
    print(f"  {'$ floor':>12}" + "".join(f"{f'r>={r}':>10}"
                                         for r in (0.0, 0.005, 0.01, 0.02)))
    for d in (0, 25_000, 50_000, 100_000):
        line = f"  {f'${d:,}':>12}"
        for r in (0.0, 0.005, 0.01, 0.02):
            keep = [x for x in traded
                    if x["dollars"] >= d and x["ratio"] >= r]
            line += f"{100*sum(x['pnl'] for x in keep)/tot:>9.0f}%"
        print(line)


if __name__ == "__main__":
    main()
