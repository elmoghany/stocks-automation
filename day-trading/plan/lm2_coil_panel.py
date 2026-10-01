"""LEGACY-2 (coil as an order): build a causal candidate panel.

For every session in the CHAMPION-REPLAY causal universe (cp_feat grid),
every 5-minute decision minute t in [09:35, 14:30], every name on the
live scanner at t (elig_last: printed close >= +10% vs prior close,
last >= $2) with 07:00 gap <= 35%:
  * features at t (read from the causal cp_feat grid, values dated <= t)
  * entry = OPEN of the next printed bar after t (RS_DEFER convention)
  * forward outcomes from that fill: last printed close at em+15/30/60
    and at 15:00 (clamped to 15:00), max high / min low to 15:00
  * on a sub-grid of decision minutes, the R4 exit stack (trail
    20/10/40 pressure-modulated + bearish engulfing, no stop, 15:00
    flatten) via cp_sim._walk_exit -- gap-through fills.
Nothing after t enters a feature; outcomes are labels only.

    python plan/lm2_coil_panel.py   -> plan/lm2_out/panel.npz
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402
import cp_sim as S                                          # noqa: E402

OUT = Path(__file__).resolve().parent / "lm2_out"
OUT.mkdir(exist_ok=True)
T0, T1 = L.mgrid(9, 35), L.mgrid(14, 30)
R4_SUB = {L.mgrid(9, 35), L.mgrid(9, 40), L.mgrid(9, 45), L.mgrid(9, 50),
          L.mgrid(10, 0), L.mgrid(10, 15), L.mgrid(10, 30), L.mgrid(11, 0),
          L.mgrid(11, 30), L.mgrid(12, 0), L.mgrid(13, 0), L.mgrid(14, 0)}
FK = ["coil", "gain_now", "hi_gain", "last", "dvol_now", "rvol_now",
      "sigma1", "vwap_dist", "orb_dist", "pressure30", "dens"]
SK = ["gap7", "gap_open", "pm_high_gain", "pm_dvol", "dvol60", "pc"]


def main():
    dates = F.dates() if hasattr(F, "dates") else L.panel_dates()
    cfg = S.default_cfg(rank="coil", stop_pct=None)
    rows = {k: [] for k in
            ["di", "t", "i", "ncand", "first", "coil_m5", "coil_m15",
             "gain_m15", "em", "entry", "r15", "r30", "r60", "r1500",
             "mfe", "mae", "r4", "r4_min"] + FK + SK}
    chunks = {k: [] for k in rows}
    t0 = time.time()
    for di, date in enumerate(dates):
        for k in rows:
            if rows[k]:
                chunks[k].append(np.asarray(rows[k], np.float32 if k not in ("di", "t", "i", "em") else np.int32))
                rows[k] = []
        Fd = F.load(date) if hasattr(F, "load") else None
        if Fd is None:
            continue
        day = L.load_day(date)
        if day is None:
            continue
        grid = list(Fd["grid"])
        gidx = {m: j for j, m in enumerate(grid)}
        elig = Fd["elig_last"]
        g7 = Fd["gap7"]
        okgap = ~(np.isfinite(g7) & (g7 > 0.35))
        last = day.last
        seen = np.zeros(day.n, bool)
        # prefix max high / min low from the right for MFE/MAE to 15:00
        for t in range(T0, T1 + 1, 5):
            gi = gidx[t]
            cand = np.where(elig[:, gi] & okgap)[0]
            newmask = ~seen[cand]
            seen[cand] = True
            nc = len(cand)
            for k, i in enumerate(cand):
                em = S._next_print(day, i, t + 1)
                if em is None or em > L.M_1500 - 1:
                    continue
                px = float(day.o[i, em])
                if not np.isfinite(px) or px < 2.0:
                    continue

                def at(m):
                    return float(last[i, min(m, L.M_1500)]) / px - 1.0
                hh = day.h[i, em:L.M_1500 + 1]
                ll = day.l[i, em:L.M_1500 + 1]
                rows["di"].append(di); rows["t"].append(t)
                rows["i"].append(i); rows["ncand"].append(nc)
                rows["first"].append(bool(newmask[k]))
                rows["coil_m5"].append(Fd["coil"][i, gi - 1])
                rows["coil_m15"].append(Fd["coil"][i, gi - 3])
                rows["gain_m15"].append(Fd["gain_now"][i, gi - 3])
                rows["em"].append(em); rows["entry"].append(px)
                rows["r15"].append(at(em + 15)); rows["r30"].append(at(em + 30))
                rows["r60"].append(at(em + 60)); rows["r1500"].append(at(L.M_1500))
                rows["mfe"].append(np.nanmax(hh) / px - 1.0)
                rows["mae"].append(np.nanmin(ll) / px - 1.0)
                if t in R4_SUB:
                    xm, xp, _ = S._walk_exit(day, Fd, i, em, px, cfg)
                    rows["r4"].append(np.nan if xp is None else xp / px - 1.0)
                    rows["r4_min"].append(-1 if xm is None else xm)
                else:
                    rows["r4"].append(np.nan); rows["r4_min"].append(-1)
                for f in FK:
                    rows[f].append(Fd[f][i, gi])
                for f in SK:
                    rows[f].append(Fd[f][i])
        if di % 25 == 0:
            print(f"{di}/{len(dates)} {date} rows={sum(len(c) for c in chunks['di'])} "
                  f"{time.time() - t0:.0f}s", flush=True)
    for k in rows:
        if rows[k]:
            chunks[k].append(np.asarray(rows[k], np.float32 if k not in ("di", "t", "i", "em") else np.int32))
    np.savez_compressed(OUT / "panel.npz", dates=np.array(dates),
                        **{k: np.concatenate(v) for k, v in chunks.items()})
    print("done", sum(len(c) for c in chunks["di"]), f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
