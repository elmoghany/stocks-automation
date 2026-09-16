"""RL-SERIES (2026-09-16): what does the eligible set do on its own?

Descriptive only -- no policy, no selection, no ranking. At every decision
minute at which a name is ELIGIBLE (its regular-session +10% print has
already happened) and the next minute prints, buy one ticket at the next
bar's open and sell H minutes later at the next printing bar's open, paying
the same cost ladder the env pays. Average over every such (day, symbol,
minute). This is the unconditional net expectancy of the universe the RL
agent is allowed to trade; it bounds what any selection policy on top of it
can plausibly earn, and it is the number a null RL result should be read
against.

  python plan/rl/pool_profile.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import env as E                                             # noqa: E402

HORIZONS = (5, 15, 30, 60, 120, 240)
NOTIONAL = 15000.0


def profile(files, label):
    tot = defaultdict(lambda: [0, 0.0, 0.0])      # H -> [n, sum, sumsq]
    eod = [0, 0.0]
    for f in files:
        d = E.DayData(f)
        o = d.fill_o                                     # [T,S] open of m+1
        m = E.STEP_MINS
        ext = ((m < E.RTH_LO) | (m >= E.RTH_HI))
        buy_mult = 1.0 + (E.FEE_BPS + np.where(ext, E.EXT_BPS, 0.0)) / 1e4
        sell_mult = 1.0 - (E.FEE_BPS + np.where(ext, E.EXT_BPS, 0.0)) / 1e4
        ok0 = d.elig & d.printed_now & np.isfinite(o)
        for H in HORIZONS:
            k = H // E.STEP
            if k >= len(m):
                continue
            a = ok0[:-k]
            b = np.isfinite(o[k:])
            good = a & b
            if not good.any():
                continue
            px_in = o[:-k] * buy_mult[:-k, None]
            px_out = o[k:] * sell_mult[k:, None]
            sh = np.floor(NOTIONAL / np.maximum(px_in, 1e-9))
            cap = np.floor(np.maximum(d.volcap[:-k], 0.0))
            sh = np.minimum(sh, cap)
            pnl = sh * (px_out - px_in)
            v = pnl[good]
            v = v[np.isfinite(v)]
            tot[H][0] += len(v)
            tot[H][1] += float(v.sum())
            tot[H][2] += float((v * v).sum())
        # hold to the forced flatten
        fp = d.flat_px
        fm = d.flat_min
        fext = (fm < E.RTH_LO) | (fm >= E.RTH_HI)
        px_in = o * buy_mult[:, None]
        px_out = (fp * np.where(fext, 1.0 - (E.FEE_BPS + E.EXT_BPS) / 1e4,
                                1.0 - E.FEE_BPS / 1e4))[None, :]
        sh = np.minimum(np.floor(NOTIONAL / np.maximum(px_in, 1e-9)),
                        np.floor(np.maximum(d.volcap, 0.0)))
        pnl = sh * (px_out - px_in)
        v = pnl[ok0 & np.isfinite(px_out)]
        v = v[np.isfinite(v)]
        eod[0] += len(v)
        eod[1] += float(v.sum())
    out = {}
    for H in sorted(tot):
        n, s, s2 = tot[H]
        if not n:
            continue
        mu = s / n
        sd = (s2 / n - mu * mu) ** 0.5
        out[f"hold_{H}min"] = {"n": n, "mean_pnl_per_ticket": round(mu, 2),
                               "std": round(sd, 1),
                               "t_stat": round(mu / (sd / n ** 0.5), 2)}
    if eod[0]:
        out["hold_to_flatten"] = {"n": eod[0],
                                  "mean_pnl_per_ticket": round(eod[1] / eod[0], 2)}
    return {label: out}


def main():
    sp = E.split_files()
    out = {}
    for k in ("train", "val", "test", "extra"):
        if sp.get(k):
            out.update(profile(sp[k], k))
            print(k, json.dumps(out[k]), flush=True)
    p = E.OUT / "pool_profile.json"
    p.write_text(json.dumps(out, indent=1))
    print("wrote", p)


if __name__ == "__main__":
    main()
