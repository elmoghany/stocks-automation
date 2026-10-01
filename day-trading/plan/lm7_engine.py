"""LEGACY-7: the candidate vetoes INSIDE the R4 engine (cp_sim, honest
RS_DEFER fills), so a vetoed name is REPLACED by the next ranked name /
next decision, exactly as live -- plus a matched-rate random-veto control.

Veto is evaluated at the decision minute t (grid index gi) on name i:
  rvtn  : rvol_now[i,gi] / fixed U-shape expected-volume fraction < 0.5
  am    : Amihud over bars [t-29, t] > 2.5e5 bps per $1M
  or    : rvtn OR am
  rv07  : raw rvol_now < 0.07
  neg3d : CATALYST-MINER composite (8-K 5.02 | Form-4 sale | analyst in 3d, 10-Q in 18h)
  k502  : 8-K item 5.02 in 3d
  rndK  : drop each (name, decision) with prob p = the 'or' veto rate (seeded hash)
Only cp_sim._try_ticket is wrapped (monkeypatch in this process; no file edits).
"""
import json
import sys
import time
import zlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cp_run as R                                          # noqa: E402
import cat_events as E                                      # noqa: E402
from lm7_feat import amihud                                 # noqa: E402

S = R.S
L = S.L
ET = ZoneInfo("America/New_York")
FN = E.feature_names()
IX = {k: FN.index(k) for k in ("n_8k_5.02_3d", "n_f4_sell_3d", "n_analyst_3d", "n_10q_18h")}
CNT = {}


def frac(mod):
    mod = max(1.0, mod)
    return min(1.0, 0.10 * (mod / 5.0) ** 0.5) if mod <= 60 else min(1.0, 0.35 + 0.65 * (mod - 60) / 330)


def cat_row(day, sym, t):
    hh, mi = divmod(t + L.GRID_START, 60)
    y, mo, d = (int(x) for x in day.date.split("-"))
    ts = datetime(y, mo, d, hh, mi, tzinfo=ET).timestamp()
    return E.features_for(sym, np.array([ts]))[0]


def vetoed(kind, day, Fd, i, t, gi):
    sym = day.syms[i]
    if kind.startswith("rnd"):
        seed, p = kind[3:].split("_")
        h = zlib.crc32(f"{seed}|{day.date}|{sym}|{t}".encode()) / 2 ** 32
        return h < float(p)
    j = int(np.where(Fd["syms"] == sym)[0][0])
    rv = float(Fd["rvol_now"][j, gi])
    if kind in ("rvtn", "or"):
        if np.isfinite(rv) and rv / frac(t - L.M_OPEN) < 0.5:
            return True
    if kind in ("am", "or"):
        if amihud(day, i, t + 1) > 2.5e5:
            return True
    if kind == "rv07":
        return np.isfinite(rv) and rv < 0.07
    if kind in ("neg3d", "k502"):
        x = cat_row(day, sym, t)
        if kind == "k502":
            return x[IX["n_8k_5.02_3d"]] > 0
        return any(x[v] > 0 for v in IX.values())
    return False


_orig = S._try_ticket


def _wrapped(day, Fd, i, t, gi, budget, cfg, cost):
    kind = cfg.get("veto")
    if kind:
        c = CNT.setdefault(kind, [0, 0])
        c[0] += 1
        if vetoed(kind, day, Fd, i, t, gi):
            c[1] += 1
            return None
    return _orig(day, Fd, i, t, gi, budget, cfg, cost)


S._try_ticket = _wrapped


def summ(L_):
    g = np.array([x["gross"] * 10_000.0 / (x["entry"] * x["shares"]) for x in L_])
    y1 = np.array([x["date"] < "2025-08-01" for x in L_])
    return dict(n=len(g), n1=int(y1.sum()), n2=int((~y1).sum()), mean=g.mean(),
                m1=g[y1].mean(), m2=g[~y1].mean(), tot=g.sum(), tot1=g[y1].sum(), tot2=g[~y1].sum())


def main():
    t0 = time.time()
    ds = R.dates()
    # need day.date inside the wrapper
    if not hasattr(L.Day, "date"):
        _ld = L.load_day

        def ld(date):
            d = _ld(date)
            if d is not None:
                d.date = date
            return d
        L.load_day = ld
    base = S.default_cfg(rank="coil", stop_pct=None)
    jobs = {"R4": (base, None, None)}
    for k in ("rvtn", "am", "or", "rv07", "neg3d", "k502"):
        jobs[k] = (dict(base, veto=k), None, None)
    legs = S.run_many(ds, jobs, progress=False)
    p = CNT["or"][1] / CNT["or"][0]
    print("attempt-level veto rates:", {k: (v[1], v[0], round(v[1] / v[0], 3)) for k, v in CNT.items()}, flush=True)
    jobs2 = {f"rnd{s}": (dict(base, veto=f"rnd{s}_{p:.4f}"), None, None) for s in range(20)}
    legs.update(S.run_many(ds, jobs2, progress=False))
    out = {k: summ(v) for k, v in legs.items()}
    nd = len(ds)
    for k, s in out.items():
        print(f"{k:8s} n{s['n']:4d} ({s['n']/nd:.2f}/d) mean {s['mean']:+7.2f} Y1 {s['m1']:+7.2f} (n{s['n1']}) "
              f"Y2 {s['m2']:+7.2f} (n{s['n2']}) tot {s['tot']:+8.0f} Y1 {s['tot1']:+8.0f} Y2 {s['tot2']:+8.0f}")
    rnd = np.array([out[f"rnd{s}"]["tot"] for s in range(20)])
    rnd2 = np.array([out[f"rnd{s}"]["tot2"] for s in range(20)])
    for k in ("rvtn", "am", "or", "rv07", "neg3d", "k502"):
        print(f"{k}: tot vs R4 {out[k]['tot'] - out['R4']['tot']:+.0f}; pct vs random-veto(or-rate) "
              f"{(rnd < out[k]['tot']).mean()*100:.0f}th (rand mean {rnd.mean():+.0f} sd {rnd.std():.0f}); "
              f"Y2 pct {(rnd2 < out[k]['tot2']).mean()*100:.0f}th")
    # cost: net at 15 bps/side = gross - $30 per $10k ticket
    for k in ("R4", "or", "rvtn", "am"):
        s = out[k]
        print(f"{k} net@15bps/side: ${s['mean']-30:+.2f}/tkt, ${(s['mean']-30)*s['n']/nd*21:+.0f}/mo; "
              f"Y1 ${s['m1']-30:+.2f}/tkt Y2 ${s['m2']-30:+.2f}/tkt")
    json.dump({k: {kk: float(vv) for kk, vv in v.items()} for k, v in out.items()},
              open(Path(sys.argv[1]) if len(sys.argv) > 1 else
                   Path(r"C:/Users/MYPC~1/AppData/Local/Temp/claude/C--cornell-stocks-automation/"
                        r"20a29bc8-aa0d-497e-a600-4db3499b8240/scratchpad/lm7_engine.json"), "w"))
    print("secs", round(time.time() - t0))


if __name__ == "__main__":
    main()
