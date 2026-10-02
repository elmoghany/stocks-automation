"""OVERNIGHT research step 2: top-N nightly portfolios on the gd universe.

Buy $100k/N each of the top-N names at the official close of D, sell at the
official open of D+1. Selectors use PRE features only unless tagged CLS.
Prints per split at 6 and 12 bps/side, with a 30-seed random-N control and
SPY close->open.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from on_lib import SPLITS, by_split, fmt, load, nightly, pick_top, split_of  # noqa: E402


def zs(u, f):
    g = u.groupby("date")[f]
    return (u[f] - g.transform("mean")) / g.transform("std")


def selectors(u):
    S = {
        "vol20_hi": u.vol20,
        "tug20_hi": u.tug20,
        "onmom20_hi": u.on_mom20,
        "onpos20_hi": u.on_pos20 + 1e-6 * u.on_mom20,
        "rev5_lo": -u.rev5,
        "pintra_lo": -u.pintra,
        "gap_lo": -u.gap,
        "vol+tug": zs(u, "vol20") + zs(u, "tug20"),
        "vol+rev5lo": zs(u, "vol20") - zs(u, "rev5"),
        "vol+tug+rev5lo": zs(u, "vol20") + zs(u, "tug20") - zs(u, "rev5"),
        "CLS:dret_lo": -u.dret,
        "CLS:vol+dretlo": zs(u, "vol20") - zs(u, "dret"),
    }
    return S


def main():
    u = load()
    Ns = [5, 10, 20, 50]
    bps_list = [6, 12]
    # SPY control
    spy = u.groupby("date").spy_on1.first().dropna()
    print("== SPY close->open ($100k)")
    for b in bps_list:
        r = by_split(spy, b)
        for k, v in r.items():
            print(f"  {b:2d}bps {k:4s} {fmt(v)}")
    print("== universe equal-weight (all names)")
    ew = u.groupby("date").oh1.mean()
    for b in bps_list:
        for k, v in by_split(ew, b).items():
            print(f"  {b:2d}bps {k:4s} {fmt(v)}")
    # random control
    rc = {}
    for n in Ns:
        sims = []
        for s in range(30):
            rng = np.random.default_rng(1000 + s)
            idx = pick_top(u, pd.Series(rng.random(len(u))), n, seed=s)
            sims.append(nightly(u, idx))
        rc[n] = sims
        g = pd.concat(sims, axis=1)
        sp = split_of(pd.Series(g.index, index=g.index))
        msg = " ".join(f"{k}:{(g[sp == k].mean() * 1e4).mean():.1f}bp[{(g[sp == k].mean() * 1e4).quantile(.1):.1f},{(g[sp == k].mean() * 1e4).quantile(.9):.1f}]"
                       for k in SPLITS)
        print(f"== random N={n} gross mean (p10,p90 across 30 seeds): {msg}")
    S = selectors(u)
    res = []
    for name, sc in S.items():
        for n in Ns:
            idx = pick_top(u, sc, n, seed=11)
            r = nightly(u, idx)
            sims = rc[n]
            sp = split_of(pd.Series(r.index, index=r.index))
            line = []
            for k in list(SPLITS) + ["ALL"]:
                m = sp == k if k != "ALL" else sp != ""
                gm = r[m].mean() * 1e4
                pct = np.mean([gm > s[split_of(pd.Series(s.index, index=s.index)) == k].mean() * 1e4
                               if k != "ALL" else gm > s.mean() * 1e4 for s in sims])
                st6 = by_split(r, 6)[k]
                line.append((k, gm, pct, st6["usd_month"], st6["exTop5_night"], st6["win"]))
                res.append({"sel": name, "N": n, "split": k, "gross_bp": gm, "rc_pct": pct,
                            **{f"{kk}_6": vv for kk, vv in st6.items()},
                            **{f"{kk}_12": vv for kk, vv in by_split(r, 12)[k].items()}})
            print(f"{name:16s} N={n:2d} " + " | ".join(
                f"{k} {gm:6.1f}bp p{pct*100:3.0f} ${um:7.0f}/mo@6 ex5 ${e5:6.1f}" for k, gm, pct, um, e5, w in line))
    pd.DataFrame(res).to_csv(sys.argv[1] if len(sys.argv) > 1 else
                             str(__import__("on_lib").OUT / "on_port.csv"), index=False)


if __name__ == "__main__":
    main()
