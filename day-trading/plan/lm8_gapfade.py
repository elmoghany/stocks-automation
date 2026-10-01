"""LEGACY-8: how robust is the GAP-OPEN fade (lm8_tod part B: names whose
09:30 bar already closes >= +10% lose ~-100..-200 bp to the close)?

Causal: selection uses only the 09:30 bar (close >= 1.10 x pc, >= $2) and
cum $vol through 09:30 (incl. premarket).  Entry = 09:31 OPEN (next printed
bar).  Returns are for a LONG; the fade is the negative of these.
Also: is there ANY clock window in which a gap-opener drifts UP (a long
entry for a cash account)?

    python plan/lm8_gapfade.py
"""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L  # noqa: E402

EX = [(10, 0), (10, 30), (11, 0), (12, 0), (13, 0), (14, 0), (15, 0), (15, 55)]
WIN = [((9, 31), (10, 0)), ((10, 0), (10, 30)), ((10, 30), (11, 0)), ((11, 0), (12, 0)),
       ((12, 0), (13, 0)), ((13, 0), (14, 0)), ((14, 0), (15, 0)), ((15, 0), (15, 55))]
BAD = {"2025-04-09", "2024-11-29", "2024-12-24", "2025-07-03", "2025-11-28", "2025-12-24"}


def summ(rows, key):
    v = [(x["date"], x[key]) for x in rows if np.isfinite(x[key])]
    r = np.array([b for _, b in v])
    by = defaultdict(list)
    for a, b in v:
        by[a].append(b)
    dm = np.array([np.mean(b) for b in by.values()])
    t = dm.mean() / (dm.std(ddof=1) / np.sqrt(len(dm)))
    y = lambda lo, hi: np.mean([b for a, b in v if lo <= a < hi]) * 1e4
    lo, hi = np.percentile(r, [1, 99])
    return (f"n={len(r):5d} mean={r.mean()*1e4:+7.1f} wins={np.clip(r,lo,hi).mean()*1e4:+7.1f} "
            f"med={np.median(r)*1e4:+7.1f} up={np.mean(r>0)*100:4.1f}% t-day={t:+6.2f} "
            f"Y1={y('2024','2025-08-01'):+7.1f} Y2={y('2025-08-01','2026-08-01'):+7.1f} "
            f"OOS={y('2026-08-01','2027'):+7.1f} dayfrac-neg={np.mean(dm<0)*100:4.1f}%")


def main():
    rows = []
    for date in L.panel_dates():
        if date in BAD:
            continue
        d = L.load_day(date)
        if d is None:
            continue
        m0 = L.M_OPEN
        ok = d.printed[:, m0] & (d.c[:, m0] >= 1.10 * d.pc) & (d.c[:, m0] >= L.MIN_PRICE)
        last = d.last
        for i in np.where(ok)[0]:
            if not d.printed[i, m0 + 1]:
                continue
            px = d.o[i, m0 + 1]
            rec = dict(date=date, dv=float(d.cumdv[i, m0]), gap=float(d.c[i, m0] / d.pc[i] - 1), px=px)
            for hh, mm in EX:
                rec[f"x{hh}{mm:02d}"] = last[i, L.mgrid(hh, mm)] / px - 1
            for (a, b), (c, e) in WIN:
                p0, p1 = last[i, L.mgrid(a, b)], last[i, L.mgrid(c, e)]
                rec[f"w{a}{b:02d}"] = p1 / p0 - 1 if a * 60 + b > 9 * 60 + 31 else p1 / px - 1
            rows.append(rec)
    tiers = [("ALL", lambda x: True), ("cum$vol>=2M", lambda x: x["dv"] >= 2e6),
             ("cum$vol>=10M", lambda x: x["dv"] >= 1e7),
             ("liq & gap 10-20%", lambda x: x["dv"] >= 2e6 and x["gap"] < 0.2),
             ("liq & gap 20-50%", lambda x: x["dv"] >= 2e6 and 0.2 <= x["gap"] < 0.5),
             ("liq & gap >=50%", lambda x: x["dv"] >= 2e6 and x["gap"] >= 0.5),
             ("liq & px>=10", lambda x: x["dv"] >= 2e6 and x["px"] >= 10)]
    print(f"gap-openers (09:30 close >= +10%), {len(rows)} name-days; LONG from 09:31 open (bp)")
    for nm, f in tiers:
        S = [x for x in rows if f(x)]
        print(f"\n-- {nm}")
        for hh, mm in EX:
            print(f"  09:31 -> {hh:02d}:{mm:02d}  " + summ(S, f"x{hh}{mm:02d}"))
        print("  clock windows (held since 09:31):")
        for (a, b), (c, e) in WIN:
            print(f"   {a:02d}:{b:02d}-{c:02d}:{e:02d}  " + summ(S, f"w{a}{b:02d}"))


if __name__ == "__main__":
    main()
