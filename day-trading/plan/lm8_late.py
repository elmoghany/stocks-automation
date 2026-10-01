"""LEGACY-8 follow-up: do LATE first-crossers (first RTH close >= +10%
after midday) drift up into the close?  lm8_tod.py part B found the
13:00-14:30 cross cohort at +67..+92 bp (liquid, winsorised) to 15:00+,
against -40 bp for every earlier cohort.  This stress-tests it.

Causal: at minute m the name's FIRST regular-session close >= k x
prev_close (>= $2) prints; nothing after m is used to select it.  Entry
= OPEN of the next printed bar (or of the bar after that, `lag=2`).
Exit = close of the 15:55 bar (grid 715) unless stated.  Liquidity =
cumulative RTH+PM dollar volume at the cross minute (known at m).

    python plan/lm8_late.py
"""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L  # noqa: E402

M1555 = L.mgrid(15, 55)
COH = [(L.mgrid(11, 0), L.mgrid(12, 0)), (L.mgrid(12, 0), L.mgrid(13, 0)),
       (L.mgrid(13, 0), L.mgrid(13, 30)), (L.mgrid(13, 30), L.mgrid(14, 0)),
       (L.mgrid(14, 0), L.mgrid(14, 31)), (L.mgrid(14, 31), L.mgrid(15, 15))]


def hm(m):
    t = m + 240
    return f"{t // 60:02d}:{t % 60:02d}"


def cross_k(d, k):
    thr = (k * d.pc)[:, None]
    arr = np.where(d.printed, d.c, -np.inf)
    ok = (arr >= thr) & (arr >= L.MIN_PRICE)
    ok[:, :L.M_OPEN] = False
    any_ = ok.any(axis=1)
    return np.where(any_, ok.argmax(axis=1), L.NMIN)


def nth_open_after(d, i, m, nth):
    pr = np.where(d.printed[i, m + 1:])[0]
    if len(pr) < nth:
        return np.nan, L.NMIN
    k = m + 1 + int(pr[nth - 1])
    return d.o[i, k], k


def stats(lab, rows, key="r"):
    if not rows:
        print(f"  {lab:<44} n=0")
        return
    r = np.array([x[key] for x in rows])
    days = defaultdict(list)
    for x in rows:
        days[x["date"]].append(x[key])
    dm = np.array([np.mean(v) for v in days.values()])
    t = dm.mean() / (dm.std(ddof=1) / np.sqrt(len(dm))) if len(dm) > 2 else np.nan
    srt = np.sort(r)[::-1]
    y1 = [x[key] for x in rows if x["date"] < "2025-08-01"]
    y2 = [x[key] for x in rows if "2025-08-01" <= x["date"] < "2026-08-01"]
    oos = [x[key] for x in rows if x["date"] >= "2026-08-01"]
    lo, hi = np.percentile(r, [1, 99])
    g = r.mean() * 1e4
    print(f"  {lab:<44} n={len(r):5d} days={len(dm):3d} gross={g:+7.1f} wins={np.clip(r,lo,hi).mean()*1e4:+7.1f} "
          f"med={np.median(r)*1e4:+6.1f} up={np.mean(r>0)*100:4.1f}% ex-top5={srt[5:].mean()*1e4 if len(r)>10 else np.nan:+7.1f} "
          f"t-day={t:+5.2f} Y1={np.mean(y1)*1e4 if y1 else np.nan:+7.1f}({len(y1)}) "
          f"Y2={np.mean(y2)*1e4 if y2 else np.nan:+7.1f}({len(y2)}) OOS={np.mean(oos)*1e4 if oos else np.nan:+7.1f}({len(oos)}) "
          f"net@12/15/18={g-24:+6.1f}/{g-30:+6.1f}/{g-36:+6.1f}")


def main():
    excl = set(sys.argv[1:])  # e.g. 2025-04-09 (tariff-pause 13:18 ET: 27% of the cohort)
    dates = [x for x in L.panel_dates() if x not in excl]
    print(f"excluded dates: {sorted(excl)}")
    R = []
    for di, date in enumerate(dates):
        d = L.load_day(date)
        if d is None:
            continue
        last = d.last
        cdv = d.cumdv
        cms = {k: cross_k(d, k) for k in (1.10, 1.15, 1.20)}
        cm10 = cms[1.10]
        for i in np.where((cm10 >= L.mgrid(11, 0)) & (cm10 < L.mgrid(15, 15)))[0]:
            m = int(cm10[i])
            px, em = nth_open_after(d, i, m, 1)
            px2, em2 = nth_open_after(d, i, m, 2)
            if not np.isfinite(px) or em > M1555 - 5:
                continue
            ex = last[i, M1555]
            rec = dict(date=date, sym=d.syms[i], cm=m, em=em, dv=float(cdv[i, m]),
                       gap=float(d.o[i, L.M_OPEN] / d.pc[i] - 1) if d.printed[i, L.M_OPEN] else np.nan,
                       r=ex / px - 1,
                       r2=(ex / px2 - 1) if np.isfinite(px2) and em2 < M1555 else np.nan,
                       r1559=last[i, 719] / px - 1,
                       r60=last[i, min(em + 60, 719)] / px - 1,
                       r30=last[i, min(em + 30, 719)] / px - 1,
                       # max level already printed today before the cross (RTH+PM) vs threshold
                       pmhi=float(np.nanmax(np.where(d.printed[i, :m], d.h[i, :m], np.nan)) / d.pc[i] - 1)
                       if d.printed[i, :m].any() else np.nan,
                       c15=bool(cms[1.15][i] <= m), c20=bool(cms[1.20][i] <= m))
            R.append(rec)
        if (di + 1) % 100 == 0:
            print(f"  ..{di+1}/{len(dates)}", flush=True)

    liq = [x for x in R if x["dv"] >= 2e6]
    print(f"\n=== first RTH close >= +10% (>= $2), entry next open, exit 15:55 close; "
          f"{len(R)} crossers 11:00-15:15, {len(liq)} liquid (cum $vol >= $2M)")
    for a, b in COH:
        stats(f"ALL cross {hm(a)}-{hm(b-1)}", [x for x in R if a <= x["cm"] < b])
    for a, b in COH:
        stats(f"LIQ cross {hm(a)}-{hm(b-1)}", [x for x in liq if a <= x["cm"] < b])
    W = [x for x in liq if L.mgrid(13, 0) <= x["cm"] < L.mgrid(14, 31)]
    print("\n=== the candidate: LIQ, first cross 13:00-14:30")
    stats("exit 15:55 (base)", W)
    stats("exit 15:59 close", W, "r1559")
    stats("exit entry+60m", W, "r60")
    stats("exit entry+30m", W, "r30")
    stats("entry one printed bar LATER (lag 2)", [x for x in W if np.isfinite(x["r2"])], "r2")
    for lo, hi, lab in ((2e6, 5e6, "$2-5M"), (5e6, 2e7, "$5-20M"), (2e7, 1e12, ">$20M")):
        stats(f"cum $vol {lab}", [x for x in W if lo <= x["dv"] < hi])
    stats("ALL-liquidity version (dv any)", [x for x in R if L.mgrid(13, 0) <= x["cm"] < L.mgrid(14, 31)])
    stats("dv >= $1M", [x for x in R if L.mgrid(13, 0) <= x["cm"] < L.mgrid(14, 31) and x["dv"] >= 1e6])
    stats("opened < +5% (true intraday breakout)", [x for x in W if x["gap"] < 0.05])
    stats("opened >= +5%", [x for x in W if x["gap"] >= 0.05])
    stats("prior high (incl PM) < +10% (never touched)", [x for x in W if x["pmhi"] < 0.10])
    stats("prior high >= +10% (re-cross on a close)", [x for x in W if x["pmhi"] >= 0.10])
    stats("cross bar also >= +15%", [x for x in W if x["c15"]])
    # one ticket a day: earliest qualifying liquid cross after 13:00
    first = {}
    for x in sorted(W, key=lambda z: (z["date"], z["cm"], -z["dv"])):
        first.setdefault(x["date"], x)
    F = list(first.values())
    stats("ONE/day: earliest liquid cross >= 13:00", F)
    top = {}
    for x in sorted(W, key=lambda z: (z["date"], -z["dv"])):
        top.setdefault(x["date"], x)
    stats("ONE/day: most liquid late crosser", list(top.values()))
    # monthly table for the one-a-day version, $ at $10k net 15 bps/side
    mon = defaultdict(float)
    for x in F:
        mon[x["date"][:7]] += x["r"] * 1e4 - 30
    print("  ONE/day monthly net@15 ($10k):", " ".join(f"{k}:{v:+.0f}" for k, v in sorted(mon.items())))
    print(f"  months positive {sum(v > 0 for v in mon.values())}/{len(mon)}, mean $/month {np.mean(list(mon.values())):+.0f}")
    # control: names ALREADY crossed before 13:00, liquid, bought at the SAME minute
    # as each late crosser of the day (matched entry minute) -> isolates 'fresh breakout'
    print("\n=== control: biggest-$vol ALREADY-crossed (before 11:00) liquid name, bought at the same minute")
    ctrl = []
    byday = defaultdict(list)
    for x in F:
        byday[x["date"]].append(x)
    for date, xs in byday.items():
        d = L.load_day(date)
        cm10 = cross_k(d, 1.10)
        last = d.last
        cdv = d.cumdv
        for x in xs:
            m = x["em"] - 1
            cand = [j for j in np.where(cm10 < L.mgrid(11, 0))[0] if cdv[j, m] >= 2e6 and d.syms[j] != x["sym"]]
            if not cand:
                continue
            j = max(cand, key=lambda j: cdv[j, m])
            px, em = nth_open_after(d, j, m, 1)
            if np.isfinite(px) and em < M1555:
                ctrl.append(dict(date=date, r=last[j, M1555] / px - 1))
    stats("control (already-crossed, same minute)", ctrl)


if __name__ == "__main__":
    main()
