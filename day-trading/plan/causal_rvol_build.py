"""Build + calibrate a CAUSAL 30-day rvol gate.

    rvol_at_T = (volume printed from 04:00 to T, on 5-minute buckets)
                / (average FULL-DAY volume over the prior 30 sessions)

Numerator  : build_vol_at_t.py, from the local 1-minute cache. Exact.
Denominator: data/massive/gd/ -- the raw grouped-daily cache the AX20
             discovery pass saved "so every future filter change costs
             zero API calls" (524 dates, 2024-08-05..2026-08-06, whole
             market). 30 sessions strictly BEFORE the candidate date.
             NOTE 2026-08-07: a fetch_daily_volume.py script spent an
             hour re-downloading a subset of this at 5 req/min before
             the existing cache was found. Deleted. CHECK data/ FIRST.

WHY 30 AND NOT 50: the live Robinhood scanner uses a 30-day RelVolume,
the backtest used 50. That mismatch is how TWLO reached the live session
on 2026-08-06 at a true 2.05x on our 50-day full-day measure -- below
the 5x rule the backtest requires -- and still got traded (+$1,266.58).
Backtest and live must measure the same thing.

WHY THE THRESHOLD CANNOT STAY 5: at 07:30 the median candidate has
printed 0.21% of its eventual day. A numerator that small against a
full-day denominator lands near 0.002-0.02, which is exactly where the
live premarket numbers sit (TWLO 0.0165). 5x is meaningless here; the
right floor has to be recalibrated, which is what this script does.

HONEST SCOPE LIMIT -- READ THIS BEFORE TRUSTING THE OUTPUT:
the candidate pool was DISCOVERED with the non-causal full-day
rvol >= 5 filter already applied (min rvol in the pool is exactly 5.00).
So this measures how much P&L a causal floor RETAINS among names the old
rule already liked. It CANNOT measure names the old rule rejected that a
causal gate would admit -- that needs a fresh 2-year discovery pass plus
1-minute bars for every new candidate, which the free-tier key (5
req/min) cannot deliver. The false-positive rate remains unmeasured.
"""

import gzip
import json
from collections import defaultdict
from datetime import date as ddate
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DV = ROOT / "data/massive/gd"
VAT = ROOT / "data/massive/vol_at_t.json"
OUT = ROOT / "data/massive/causal_rvol.json"
LOOKBACK = 30
MAX_GAP_DAYS = 10   # newest prior session must be this recent
TIMES = ["0700", "0730", "0800", "0830", "0900", "0930", "1000", "1030"]


def load_daily():
    """symbol -> [(date, volume)] sorted by date."""
    files = sorted(DV.glob("*.json.gz"))
    if not files:
        raise RuntimeError("ERROR: data/massive/gd cache missing")
    per = defaultdict(list)
    for f in files:
        d = f.name[:10]
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                rows = json.load(fh)
        except Exception:
            print(f"ERROR: unreadable gd cache {f.name} -- skipping")
            continue
        for r in rows:
            if r.get("T") and r.get("v"):
                per[r["T"]].append((d, float(r["v"])))
    for sym in per:
        per[sym].sort()
    return per, len(files)


def main():
    vat = json.loads(VAT.read_text())
    daily, ndates = load_daily()
    print(f"daily cache: {ndates:,} dates, {len(daily):,} symbols")
    print(f"volume-at-T: {len(vat):,} candidate-days\n")

    out, no_base, stale = {}, 0, 0
    for key, rec in vat.items():
        sym, date = key.split("|")
        hist = daily.get(sym)
        if not hist:
            no_base += 1
            continue
        prior = [(d, v) for d, v in hist if d < date][-LOOKBACK:]
        if len(prior) < LOOKBACK or sum(v for _, v in prior) <= 0:
            no_base += 1
            continue
        # STALENESS GUARD. With an incomplete daily cache the "prior 30
        # sessions" silently resolve to the last 30 dates that happen to
        # be cached -- which can be months stale -- producing a baseline
        # that looks fine and is worthless. Caught in smoke-testing on a
        # 43-date cache, where it reported a median full-day rvol of 310.
        # Refuse rather than approximate.
        gap = (ddate.fromisoformat(date)
               - ddate.fromisoformat(prior[-1][0])).days
        if gap > MAX_GAP_DAYS:
            stale += 1
            continue
        avg30 = sum(v for _, v in prior) / len(prior)
        r = {t: rec[t] / avg30 for t in TIMES}
        r["full"] = rec["full"] / avg30
        r["avg30"] = avg30
        r["_raw"] = {t: rec[t] for t in TIMES}
        out[key] = r
    OUT.write_text(json.dumps(out))
    print(f"built {len(out):,} symbol-days with a full {LOOKBACK}-session "
          f"baseline ({no_base:,} lacked one, {stale:,} rejected as STALE)")
    if stale > len(out):
        print("ERROR: more symbol-days rejected as stale than accepted -- "
              "the daily cache is INCOMPLETE. Any table below is not "
              "trustworthy. Finish plan/fetch_daily_volume.py first.")
    print()

    # ---- P&L join -----------------------------------------------------
    pnl = {}
    for lab in ("year", "y2025"):
        f = ROOT / f"data/massive/s093_trades_{lab}.json"
        if f.exists():
            for d in json.loads(f.read_text()):
                pnl[f"{d['symbol']}|{d['date']}"] = d["pnl"]
    traded = {k: v for k, v in pnl.items() if k in out}
    tot = sum(traded.values())
    print(f"C35 traded days with a causal measure: {len(traded):,} "
          f"(${tot:+,.0f})\n")

    print("DISTRIBUTION OF causal rvol BY DECISION TIME (traded days)")
    print(f"  {'T':>6}{'p10':>10}{'median':>10}{'p90':>10}"
          f"{'  vs 50d-fullday':>18}")
    for t in TIMES:
        v = sorted(out[k][t] for k in traded)
        if not v:
            continue
        q = lambda p: v[min(int(len(v) * p), len(v) - 1)]
        print(f"  {t[:2]}:{t[2:]:>2}{q(.10):>10.4f}{q(.50):>10.4f}"
              f"{q(.90):>10.4f}")
    vf = sorted(out[k]["full"] for k in traded)
    print(f"  {'full':>6}{vf[len(vf)//10]:>10.2f}{vf[len(vf)//2]:>10.2f}"
          f"{vf[int(len(vf)*.9)]:>10.2f}   <- 30d full-day, for reference")

    # ---- retention sweep ----------------------------------------------
    print("\nP&L RETAINED by a floor on causal rvol at each decision time")
    print("(share of C35's traded-day P&L that survives the gate)")
    floors = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.10, 0.25]
    hdr = f"  {'T':>6}" + "".join(f"{f:>8}" for f in floors)
    print(hdr)
    for t in TIMES:
        line = f"  {t[:2]}:{t[2:]:>2}"
        for fl in floors:
            keep = [v for k, v in traded.items() if out[k][t] >= fl]
            line += f"{100*sum(keep)/tot:>7.0f}%"
        print(line)

    print("\nCANDIDATE-DAYS ADMITTED (selectivity: lower = stricter)")
    print(hdr)
    for t in TIMES:
        line = f"  {t[:2]}:{t[2:]:>2}"
        for fl in floors:
            n = sum(1 for k in out if out[k][t] >= fl)
            line += f"{100*n/len(out):>7.0f}%"
        print(line)


if __name__ == "__main__":
    main()
