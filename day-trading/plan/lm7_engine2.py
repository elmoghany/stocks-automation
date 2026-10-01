"""LEGACY-7: robustness of the in-engine low-participation veto on R4
(rvol_now = session $vol so far / prior-60d avg daily $vol, read at the
decision grid point; veto when < th).  Threshold grid, per-month and
per-day deltas vs R4, ex-best-day, day-block bootstrap of the delta."""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lm7_engine as E7                                     # noqa: E402  (patches load_day path below)

S, L, R = E7.S, E7.L, E7.R


def _w(day, Fd, i, t, gi, budget, cfg, cost):
    th = cfg.get("rv_th")
    if th is not None:
        j = int(np.where(Fd["syms"] == day.syms[i])[0][0])
        rv = float(Fd["rvol_now"][j, gi])
        if np.isfinite(rv) and rv < th:
            return None
        if cfg.get("k502") and E7.vetoed("k502", day, Fd, i, t, gi):
            return None
    return E7._orig(day, Fd, i, t, gi, budget, cfg, cost)


S._try_ticket = _w
_ld = L.load_day


def ld(date):
    d = _ld(date)
    if d is not None:
        d.date = date
    return d


L.load_day = ld


def g10(x):
    return x["gross"] * 10_000.0 / (x["entry"] * x["shares"])


def main():
    ds = R.dates()
    base = S.default_cfg(rank="coil", stop_pct=None)
    jobs = {"R4": (base, None, None)}
    for th in (0.03, 0.05, 0.07, 0.10, 0.15, 0.20):
        jobs[f"rv{th}"] = (dict(base, rv_th=th), None, None)
    jobs["rv0.07+k502"] = (dict(base, rv_th=0.07, k502=True), None, None)
    # same veto, same rule, on the inverted ranking and the random ranking
    # (does the veto help ANY ordering, i.e. is it about the names, not R4?)
    for s in range(10):
        rb = S.default_cfg(rank="none", rand=True, stop_pct=None, seed=s)
        jobs[f"RND{s}"] = (rb, None, None)
        jobs[f"RND{s}+rv"] = (dict(rb, rv_th=0.07), None, None)
    legs = S.run_many(ds, jobs, progress=False)
    nd = len(ds)
    day = {k: defaultdict(float) for k in legs}
    for k, Ls in legs.items():
        for x in Ls:
            day[k][x["date"]] += g10(x)
    base_d = np.array([day["R4"][d] for d in ds])
    for k in legs:
        if k.startswith("RND"):
            continue
        g = np.array([g10(x) for x in legs[k]])
        dd = np.array([day[k][d] for d in ds]) - base_d
        y1 = np.array([d < "2025-08-01" for d in ds])
        best = np.argmax(np.array([day[k][d] for d in ds]))
        tot = g.sum()
        exbest = tot - day[k][ds[best]]
        # day-block bootstrap of the delta total
        rng = np.random.default_rng(0)
        bs = np.array([dd[rng.integers(0, nd, nd)].sum() for _ in range(2000)])
        mon = defaultdict(float)
        for d, v in zip(ds, dd):
            mon[d[:7]] += v
        print(f"{k:12s} n{len(g):4d} ${g.mean():+7.2f}/tkt net15 ${g.mean()-30:+7.2f} tot {tot:+8.0f} ex-best {exbest:+8.0f} | "
              f"delta {dd.sum():+7.0f} (Y1 {dd[y1].sum():+6.0f} Y2 {dd[~y1].sum():+6.0f}) boot P(delta>0) {(bs > 0).mean():.2f} "
              f"| days changed {(dd != 0).sum()} | months + {sum(v > 0 for v in mon.values())}/- {sum(v < 0 for v in mon.values())}"
              f" | top-3 day deltas {np.round(np.sort(dd)[-3:]).tolist()} bottom-3 {np.round(np.sort(dd)[:3]).tolist()}")
    print("\nveto applied to RANDOM ordering (10 seeds): $/tkt base -> vetoed")
    dl = []
    for s in range(10):
        a = np.array([g10(x) for x in legs[f"RND{s}"]])
        b = np.array([g10(x) for x in legs[f"RND{s}+rv"]])
        dl.append(b.sum() - a.sum())
        print(f"  seed {s}: {a.mean():+7.2f} (n{len(a)}) -> {b.mean():+7.2f} (n{len(b)}) delta tot {b.sum()-a.sum():+8.0f}")
    print(f"  mean delta {np.mean(dl):+.0f}, positive {sum(d > 0 for d in dl)}/10")


if __name__ == "__main__":
    main()
