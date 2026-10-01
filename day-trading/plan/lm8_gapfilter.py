"""LEGACY-8: price the rule "never buy a GAP-OPENER (09:30 bar close >= +10%)
before 11:00" on the HONEST ledgers (C37F-hf3, HOLD1-hf3, cp R4, cp RND x30).

Tag is causal (09:30 bar).  Dropping legs approximates the rule (the real
engine would rotate the freed ticket into another name) -- the kept-leg
$/ticket is what the filtered book would earn on the legs it still takes.

    python plan/lm8_gapfilter.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L  # noqa: E402
from lm8_tod import legs_c37, legs_cp, row  # noqa: E402

M1100 = L.mgrid(11, 0)


def main():
    sets = {"C37F-hf3": legs_c37("C37F"), "HOLD1-hf3": legs_c37("HOLD1"),
            "R4": legs_cp("R4"), "RND x30": legs_cp("RND")}
    need = defaultdict(set)
    for lg in sets.values():
        for x in lg:
            need[x["date"]].add(x["sym"])
    tag = {}
    for date, syms in need.items():
        d = L.load_day(date)
        if d is None:
            continue
        idx = {s: i for i, s in enumerate(d.syms)}
        for s in syms:
            i = idx.get(s)
            if i is None or not d.printed[i, L.M_OPEN]:
                continue
            tag[(date, s)] = (float(d.c[i, L.M_OPEN] / d.pc[i] - 1), float(d.cumdv[i, L.M_OPEN]))
    for nm, lg in sets.items():
        lg = [dict(x, gap=tag.get((x["date"], x["sym"]), (np.nan, 0))[0]) for x in lg]
        known = [x for x in lg if np.isfinite(x["gap"])]
        print(f"\n=== {nm}: {len(lg)} legs, gap tag known for {len(known)}")
        go = lambda x: x["gap"] >= 0.10
        early = lambda x: x["em"] < M1100
        row("ALL", [x["r"] for x in lg], [x["date"] for x in lg])
        for lab, f in (("gap-opener, entry <11:00", lambda x: go(x) and early(x)),
                       ("gap-opener, entry >=11:00", lambda x: go(x) and not early(x)),
                       ("intraday crosser, <11:00", lambda x: (not go(x)) and early(x)),
                       ("intraday crosser, >=11:00", lambda x: (not go(x)) and not early(x)),
                       ("gap-opener >=+20%, <11:00", lambda x: x["gap"] >= 0.2 and early(x)),
                       ("KEEP (rule applied)", lambda x: not (go(x) and early(x))),
                       ("KEEP strict (no gap-openers)", lambda x: not go(x))):
            s = [x for x in known if f(x)]
            row(lab, [x["r"] for x in s], [x["date"] for x in s])


if __name__ == "__main__":
    main()
