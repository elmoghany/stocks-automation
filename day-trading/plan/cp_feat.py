"""CHAMPION-REPLAY: per-day CAUSAL feature grid, precomputed once.

Every ablation in this line re-ranks the same universe on the same
5-minute grid. Recomputing pressure/coil/VWAP per config is what made
the R- and V-campaigns cost hours per sweep. This computes the grid
once per date and stores it, exactly the trick `plan/feature_cache.py`
plays for the champion's own two keys, widened to the whole block.

IDENTITY IS THE CONTRACT: a value at grid minute m is computed from
bars with index <= m and from PRIOR sessions only. `--verify`
recomputes a random sample through cp_lib.Day.features (the slow,
obviously-causal path) and asserts equality.

Grid: every 5th minute from 09:30 to 15:00 inclusive (67 columns).

    python plan/cp_feat.py --build [--workers 8] [--days N]
    python plan/cp_feat.py --verify [--n 12]
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L                                          # noqa: E402
import cp_prior as P                                        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/massive/cp_feat"

STEP = 5
GRID = list(range(L.M_OPEN, L.M_1500 + 1, STEP))            # 330..660
KEYS = ["last", "gain_now", "coil", "hi_gain", "dvol_now", "bars_now",
        "vwap_dist", "pressure30", "pressure10", "orb_dist", "dens",
        "sigma1", "rvol_now", "vol5"]
STATIC = ["pc", "pm_dvol", "pm_high_gain", "gap_open", "gap7", "pm_bars",
          "dvol60", "prior_range", "nhist", "prevrange", "ret5", "shares",
          "gain_full", "rvol_pool"]


def _pressure_grid(d, nbars, min_vol=20_000.0):
    """(n, |GRID|) pressure over the last `nbars` PRINTED bars."""
    out = np.full((d.n, len(GRID)), np.nan)
    cumn, cumv, cumsv = d.cumn, d.cumv, d.cumsv
    for i in range(d.n):
        rown = cumn[i]
        for gi, m in enumerate(GRID):
            cn = rown[m]
            if cn < 3:
                continue
            j = int(np.searchsorted(rown[:m + 1], cn - nbars, side="right"))
            v0 = cumv[i, j - 1] if j > 0 else 0.0
            vol = cumv[i, m] - v0
            if vol < min_vol or vol <= 0:
                continue
            s0 = cumsv[i, j - 1] if j > 0 else 0.0
            out[i, gi] = (cumsv[i, m] - s0) / vol
    return out


def build_date(date):
    d = L.load_day(date)
    if d is None or d.n == 0:
        return None
    if not P.load(date):
        return None            # prior-session context not built yet
    ctx = P.context(d.syms, date)
    G = np.array(GRID)
    last = d.last[:, G]
    pc = d.pc[:, None]
    hi = d.runhigh[:, G]
    cdv, cv, cn = d.cumdv, d.cumv, d.cumn
    dv = cdv[:, G] - cdv[:, [L.M_OPEN - 1]]
    vv = cv[:, G] - cv[:, [L.M_OPEN - 1]]
    bars = (cn[:, G] - cn[:, [L.M_OPEN - 1]]).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        f = {}
        f["last"] = last
        f["gain_now"] = last / pc - 1.0
        f["coil"] = np.where(hi > 0, last / hi, np.nan)
        f["hi_gain"] = hi / pc - 1.0
        f["dvol_now"] = dv
        f["bars_now"] = bars
        f["vwap_dist"] = np.where(vv > 0, last / (dv / vv) - 1.0, np.nan)
        f["pressure30"] = _pressure_grid(d, 30)
        f["pressure10"] = _pressure_grid(d, 10)
        orbg = d.runhigh_from(L.M_OPEN)[:, np.minimum(G, L.M_OPEN + 4)]
        f["orb_dist"] = last / orbg - 1.0
        f["dens"] = bars / np.maximum(1.0, (G - L.M_OPEN + 1)[None, :])
        # trailing 5-minute share volume (the champion's sizing cap base)
        v5 = cv[:, G] - cv[:, np.maximum(G - 5, 0)]
        f["vol5"] = v5
        # 1-minute realised vol over the session so far, cumulative form
        lc = np.log(np.where(d.printed, d.c, np.nan))
        r = np.diff(lc, axis=1)
        r2 = np.nan_to_num(r) ** 2
        ok = (~np.isnan(r)).astype(float)
        cr2 = np.cumsum(r2, axis=1)
        cok = np.cumsum(ok, axis=1)
        gi = G - 1
        f["sigma1"] = np.sqrt(np.where(cok[:, gi] > 1,
                                       cr2[:, gi] / np.maximum(cok[:, gi], 1),
                                       np.nan))
        dvol60 = np.array([(ctx.get(s) or {}).get("dvol60") or np.nan
                           for s in d.syms], float)
        f["rvol_now"] = dv / dvol60[:, None]
        st = {}
        st["pc"] = d.pc
        st["pm_dvol"] = cdv[:, L.M_OPEN - 1]
        st["pm_high_gain"] = d.runhigh[:, L.M_OPEN - 1] / d.pc - 1.0
        st["gap_open"] = d.last[:, L.M_OPEN - 1] / d.pc - 1.0
        st["gap7"] = d.last[:, L.mgrid(7, 0)] / d.pc - 1.0
        st["pm_bars"] = cn[:, L.M_OPEN - 1].astype(float)
        st["dvol60"] = dvol60
        for k, src in (("prior_range", "range60"), ("nhist", "nhist"),
                       ("prevrange", "prevrange"), ("ret5", "ret5")):
            st[k] = np.array([
                (ctx.get(s) or {}).get(src)
                if (ctx.get(s) or {}).get(src) is not None else np.nan
                for s in d.syms], float)
        st["shares"] = np.array([(ctx.get(s) or {}).get("shares") or np.nan
                                 for s in d.syms], float)
        st["gain_full"] = d.gain_pct / 100.0       # HINDSIGHT, labels only
        st["rvol_pool"] = d.rvol                   # HINDSIGHT, labels only
    # eligibility grids (both conventions), and the deferred entry price
    elig_last = np.zeros((d.n, len(GRID)), bool)
    elig_high = np.zeros((d.n, len(GRID)), bool)
    for gi_, m in enumerate(GRID):
        elig_last[:, gi_] = d.crossed_by(m, "LAST")
        elig_high[:, gi_] = d.crossed_by(m, "HIGH")
    return dict(
        syms=np.array(d.syms), grid=G.astype(np.int32),
        **{k: f[k].astype(np.float32) for k in KEYS},
        **{k: np.asarray(st[k], np.float64) for k in STATIC},
        elig_last=elig_last, elig_high=elig_high)


def _one(date):
    f = OUT / f"{date}.npz"
    if f.exists():
        return (date, -1)
    d = build_date(date)
    if d is None:
        return (date, 0)
    tmp = OUT / f".{date}.tmp.npz"
    np.savez_compressed(tmp, **d)
    for k in range(20):
        try:
            os.replace(tmp, f)
            break
        except PermissionError:
            time.sleep(0.25 * (k + 1))
    return (date, len(d["syms"]))


def load(date):
    f = OUT / f"{date}.npz"
    if not f.exists():
        return None
    z = np.load(f, allow_pickle=False)
    return {k: z[k] for k in z.files}


def dates():
    return sorted(p.stem for p in OUT.glob("[0-9]*.npz"))


def verify(n=12):
    import random
    random.seed(5)
    ds = dates()
    random.shuffle(ds)
    worst = 0.0
    checks = 0
    for date in ds[:n]:
        F = load(date)
        d = L.load_day(date)
        ctx = P.context(d.syms, date)
        prior = {s: {"dvol60": (ctx.get(s) or {}).get("dvol60", np.nan),
                     "range60": (ctx.get(s) or {}).get("range60", np.nan),
                     "shares": (ctx.get(s) or {}).get("shares", np.nan)}
                 for s in d.syms}
        for gi in random.sample(range(len(GRID)), 4):
            m = GRID[gi]
            f = d.features(m, prior=prior)
            for k in ("gain_now", "coil", "vwap_dist", "pressure30",
                      "orb_dist", "dens"):
                a = np.asarray(F[k][:, gi], float)
                b = np.asarray(f[k if k != "last" else "px"], float)
                ok = np.isfinite(a) & np.isfinite(b)
                if ok.any():
                    denom = np.maximum(np.abs(b[ok]), 1e-6)
                    worst = max(worst, float(np.max(np.abs(a[ok] - b[ok])
                                                    / denom)))
                checks += int(ok.sum())
                assert (np.isfinite(a) == np.isfinite(b)).all(), (date, k, m)
    print(f"VERIFY cp_feat: {checks} checks, worst relative diff "
          f"{worst:.3e}")
    assert worst < 1e-5


def main():
    a = sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    if "--verify" in a:
        return verify(int(a[a.index("--n") + 1]) if "--n" in a else 12)
    ds = L.panel_dates()
    if "--days" in a:
        ds = ds[:int(a[a.index("--days") + 1])]
    w = int(a[a.index("--workers") + 1]) if "--workers" in a else 8
    from concurrent.futures import ProcessPoolExecutor
    done = 0
    with ProcessPoolExecutor(max_workers=w) as ex:
        for date, n in ex.map(_one, ds, chunksize=1):
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(ds)} {date} n={n}", flush=True)
    print(f"cp_feat: {len(dates())} dates")


if __name__ == "__main__":
    main()
