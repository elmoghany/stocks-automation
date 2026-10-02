"""OVERNIGHT research step 3: holding 1-5 sessions for a fixed selector, top-N.

Cohort entered at close D, exited at the open of D+k. k cohorts overlap, so
each cohort gets CAP/k (loose: proceeds reusable on the sale day) or
CAP/(k+1) (strict settled cash: a sale at the D+k open settles D+k+1, so the
cash re-enters one session later). Cost = 2 sides per cohort.
Usage: python plan/on_hold.py SELECTOR  (a key of on_port.selectors)
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from on_lib import CAP, SPLITS, load, pick_top, split_of  # noqa: E402
from on_port import selectors  # noqa: E402


def main():
    sel = sys.argv[1]
    u = load()
    sc = selectors(u)[sel]
    for n in (5, 10, 20, 50):
        idx = pick_top(u, sc, n, seed=11)
        p = u.loc[idx]
        rnd = []
        for k in range(1, 6):
            r = p.groupby("date")[f"oh{k}"].mean().dropna()
            sp = split_of(pd.Series(r.index, index=r.index))
            line = []
            for b in (6, 12):
                for mode, cap in (("loose", CAP / k), ("strict", CAP / (k + 1))):
                    usd = (r - 2 * b / 1e4) * cap
                    cells = []
                    for s in list(SPLITS) + ["ALL"]:
                        m = (sp == s) if s != "ALL" else (sp != "")
                        x = usd[m]
                        cum = x.cumsum()
                        cells.append(f"{s} ${x.sum() / (len(x) / 21):6.0f}/mo dd${(cum - cum.cummax()).min():7.0f}")
                    line.append(f"  {b:2d}bps {mode:6s} " + " | ".join(cells))
            print(f"{sel} N={n} hold={k}: gross/cohort {r.mean() * 1e4:6.1f}bp "
                  f"(per-session {r.mean() * 1e4 / k:5.1f}bp)")
            print("\n".join(line))
            rnd.append(r)


if __name__ == "__main__":
    main()
