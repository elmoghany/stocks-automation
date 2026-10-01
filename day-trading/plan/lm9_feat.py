"""LEGACY-9 (cost-aware selection), step 1: per-leg CAUSAL entry-cost
features for CHAMPION-REPLAY R4 + its 30 random seeds (pa_out/cp_r4_legs.json)
and the live C37F-hf3 / HOLD1-hf3 ledgers.

Every entry feature reads bars [em-30, em-1] of the cp_panel minute grid
(the fill minute em is excluded; em is the first print after the decision
minute, so nothing after the decision is used).  Exit-side half-spread is
computed too, but ONLY to price realised cost -- never as a selector.

Output: plan/lm9_out/feat.json   (gitignored like plan/*.json)
"""
import json, sys, time
from pathlib import Path
import numpy as np

P = Path(r"C:\cornell\stocks-automation\day-trading\plan")
ROOT = P.parent
sys.path.insert(0, str(P))
import cp_lib as L
import cp_cost as C

OUT = P / "lm9_out"
OUT.mkdir(exist_ok=True)


def half_at(day, i, m, win=30):
    a, b = max(0, m - win), m
    sel = day.printed[i, a:b]
    o = np.where(sel, day.o[i, a:b], np.nan)
    h = np.where(sel, day.h[i, a:b], np.nan)
    l = np.where(sel, day.l[i, a:b], np.nan)
    c = np.where(sel, day.c[i, a:b], np.nan)
    cs, ar = C._cs_ar(o, h, l, c)
    vals = [v for v in (cs, ar) if v is not None and np.isfinite(v)]
    hmax = max(max(vals) / 2.0, 1.0) if vals else 10.0
    hmin = max(min(vals) / 2.0, 1.0) if vals else 10.0
    return hmax, hmin, (cs if cs is not None else np.nan), (ar if ar is not None else np.nan), int(sel.sum())


def feats(day, i, em, xm):
    hmax, hmin, cs, ar, npr = half_at(day, i, em)
    cdv = day.cumdv
    dv30 = float(cdv[i, em - 1] - (cdv[i, em - 31] if em - 31 >= 0 else 0.0))
    dvday = float(cdv[i, em - 1])                      # since 04:00
    hx = half_at(day, i, xm)[0] if xm is not None else np.nan
    return dict(h_e=hmax, hmin_e=hmin, cs_e=cs, ar_e=ar, npr30=npr,
                dv30=dv30, dvday=dvday, h_x=hx)


def main():
    t0 = time.time()
    R4 = json.load(open(P / "pa_out/cp_r4_legs.json"))["legs"]
    jobs = {}       # date -> list of (book, idx, sym, em, xm)
    for book, legs in R4.items():
        for k, v in enumerate(legs):
            jobs.setdefault(v["date"], []).append((book, k, v["sym"], v["entry_min"], v["exit_min"]))
    led = {}
    for nm in ("C37F", "HOLD1"):
        led[nm] = json.load(open(ROOT / f"data/massive/rotation_trades_{nm}_hf3.json"))
        for k, v in enumerate(led[nm]):
            et = v["entry_time"][11:16]; xt = v["exit_time"][11:16]
            em = int(et[:2]) * 60 + int(et[3:]) - L.GRID_START
            xm = int(xt[:2]) * 60 + int(xt[3:]) - L.GRID_START
            xm = min(xm, L.NMIN - 1) if v["exit_time"][:10] == v["date"] else None
            jobs.setdefault(v["date"], []).append((nm, k, v["symbol"], em, xm))
    res = {b: {} for b in list(R4) + list(led)}
    miss = {}
    for n, date in enumerate(sorted(jobs)):
        day = L.load_day(date)
        if day is None:
            for j in jobs[date]:
                miss[j[0]] = miss.get(j[0], 0) + 1
            continue
        ix = {s: i for i, s in enumerate(day.syms)}
        for book, k, sym, em, xm in jobs[date]:
            i = ix.get(sym)
            if i is None or em is None or em < 1 or em >= L.NMIN:
                miss[book] = miss.get(book, 0) + 1
                continue
            res[book][k] = feats(day, i, em, xm)
        if (n + 1) % 100 == 0:
            print(n + 1, len(jobs), round(time.time() - t0), flush=True)
    out = {b: [res[b].get(k) for k in range(len(R4[b]) if b in R4 else len(led[b]))] for b in res}
    (OUT / "feat.json").write_text(json.dumps(out, default=float))
    print("done", round(time.time() - t0), "miss", miss)


if __name__ == "__main__":
    main()
