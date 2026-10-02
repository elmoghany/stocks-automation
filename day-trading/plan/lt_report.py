"""LEADS-TEST: tables for leads 1 (TC) and 2 (quiet rank) from lt_legs.json.
    python plan/lt_report.py > data/research_oct/lt_report.txt
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lt_lib as LL                                         # noqa: E402
import cp_lib as L                                          # noqa: E402

ROOT = LL.ROOT
D = json.loads((ROOT / "data/research_oct/lt_legs.json").read_text())
DATES = D["dates"]
LEGS = D["legs"]
TC = LL.tc_labels()
HAL = L.halal_set()
SPL = ("Y1", "Y2", "OOS", "ALL")


def nd_of(dates):
    nd = {sp: sum(1 for d in dates if LL.split_of(d) == sp) for sp in SPL[:3]}
    nd["ALL"] = len(dates)
    return nd


ND = nd_of(DATES)
TCD = [d for d in DATES if TC.get(d)]
NTD = [d for d in DATES if not TC.get(d)]
ND_TC, ND_NT = nd_of(TCD), nd_of(NTD)


def tot(legs, sp, k="n_c", days=None):
    return sum(x[k] for x in legs if (sp == "ALL" or LL.split_of(x["date"]) == sp)
               and (days is None or x["date"] in days))


def pct(v, arr):
    arr = np.asarray(arr)
    return 100.0 * (np.sum(arr < v) + 0.5 * np.sum(arr == v)) / len(arr)


def hdr():
    print("| line | split | n | gross $/tr | central $/tr | flat12 $/tr | tr/mo | "
          "$/mo central | $/mo flat12 | ex-top5 $/mo central |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")


def ctl_rows(prefix, nseeds, nd, days=None):
    """mean over seeds, as a summ-like dict per split, plus per-seed totals."""
    per = {sp: [] for sp in SPL}
    rows = {sp: dict(n=[], g=[], c=[], f12=[], ex5=[]) for sp in SPL}
    for s in range(nseeds):
        L_ = [x for x in LEGS[f"{prefix}_{s}"] if days is None or x["date"] in days]
        sm = LL.summ(L_, nd)
        for sp in SPL:
            per[sp].append(tot(L_, sp))
            if sm[sp].get("n"):
                for k in ("n", "g", "c", "f12"):
                    rows[sp][k].append(sm[sp][k])
                rows[sp]["ex5"].append(sm[sp]["ex5pm"])
    return per, rows


def print_line(name, legs, nd, ctl=None, days=None):
    L_ = [x for x in legs if days is None or x["date"] in days]
    s = LL.summ(L_, nd)
    for sp in SPL:
        row = LL.fmt_row(name, s, sp)
        if ctl is not None and s[sp].get("n"):
            row += f" pct {pct(tot(L_, sp), ctl[sp]):.0f}"
        print(row)
    return s


def ctl_print(name, prefix, nseeds, nd, days=None):
    per, rows = ctl_rows(prefix, nseeds, nd, days)
    for sp in SPL:
        r = rows[sp]
        if not r["n"]:
            continue
        months = max(nd[sp], 1) / 21
        print(f"| {name} (mean of {nseeds}) | {sp} | {np.mean(r['n']):.0f} | "
              f"{np.mean(r['g']):+.1f} | {np.mean(r['c']):+.1f} | {np.mean(r['f12']):+.1f} | "
              f"{np.mean(r['n'])/months:.1f} | {np.mean(per[sp])/months:+,.0f} "
              f"(sd {np.std(per[sp])/months:,.0f}) | | {np.mean(r['ex5']):+,.0f} |")
    return per


def main():
    print(f"sessions {ND}; TC days {ND_TC}; not-TC {ND_NT}")
    print("\n## A. Anchors and lead 2 (all days)\n")
    hdr()
    cR = ctl_print("RANDOM hyg+stack 09:35", "rand", 30, ND)
    cQ = ctl_print("RANDOM hyg+stack 09:50 gain<=40%", "randQ", 30, ND)
    cN = ctl_print("RANDOM no-hyg R4-exit 09:50 gain<=40%", "randN", 10, ND)
    print_line("R4 ref (coil, no hygiene, R4 exits, causal ties)", LEGS["r4ref"], ND)
    print_line("coil + hygiene + stack", LEGS["r4H"], ND, cR)
    print_line("LEAD2 quiet + hygiene + stack", LEGS["quiet"], ND, cQ)
    print_line("CTRL ret15-only + hygiene + stack", LEGS["ret15"], ND, cQ)
    print_line("quiet + hygiene + R4 exits", LEGS["quietH_r4x"], ND, cQ)
    print_line("quiet, no hygiene, stack exits", LEGS["quietS_nohyg"], ND)
    print_line("LEAD2 literal: quiet, no hygiene, R4 exits", LEGS["quietN"], ND, cN)
    print_line("CTRL ret15-only, no hygiene, R4 exits", LEGS["ret15N"], ND, cN)

    print("\n## B. Lead 1: TC regime (frozen LEGACY-10 label), TC days only\n")
    tcs, nts = set(TCD), set(NTD)
    hdr()
    pR = ctl_print("RANDOM hyg+stack, TC days", "rand", 30, ND_TC, tcs)
    pQ = ctl_print("RANDOM 09:50 hyg+stack, TC days", "randQ", 30, ND_TC, tcs)
    pN = ctl_print("RANDOM no-hyg R4-exit, TC days", "randN", 10, ND_TC, tcs)
    for nm, k, c in (("R4 ref", "r4ref", None), ("coil+hyg+stack", "r4H", pR),
                     ("quiet+hyg+stack", "quiet", pQ), ("quiet literal", "quietN", pN)):
        print_line(nm + " | TC only", LEGS[k], ND_TC, c, tcs)
    print("\n### TC minus not-TC, central $/trade (difference; random = mean & share of seeds > 0)\n")
    print("| line | Y1 TC / notTC | Y2 TC / notTC | OOS TC / notTC | ALL diff |")
    print("|---|---|---|---|---:|")

    def mean_c(legs, sp, days):
        v = [x["n_c"] for x in legs if x["date"] in days and (sp == "ALL" or LL.split_of(x["date"]) == sp)]
        return (np.mean(v) if v else np.nan), len(v)
    for nm, k in (("R4 ref", "r4ref"), ("coil+hyg+stack", "r4H"),
                  ("quiet+hyg+stack", "quiet"), ("quiet literal", "quietN")):
        cells = []
        for sp in ("Y1", "Y2", "OOS"):
            a, na = mean_c(LEGS[k], sp, tcs)
            b, nb = mean_c(LEGS[k], sp, nts)
            cells.append(f"{a:+.0f} (n{na}) / {b:+.0f} (n{nb})")
        a, _ = mean_c(LEGS[k], "ALL", tcs)
        b, _ = mean_c(LEGS[k], "ALL", nts)
        print(f"| {nm} | " + " | ".join(cells) + f" | {a-b:+.0f} |")
    for nm, pre, ns in (("RANDOM hyg+stack", "rand", 30), ("RANDOM 09:50 hyg+stack", "randQ", 30),
                        ("RANDOM no-hyg R4", "randN", 10)):
        cells, diffs = [], []
        for sp in ("Y1", "Y2", "OOS", "ALL"):
            ds = []
            for s in range(ns):
                a, _ = mean_c(LEGS[f"{pre}_{s}"], sp, tcs)
                b, _ = mean_c(LEGS[f"{pre}_{s}"], sp, nts)
                ds.append((a, b))
            ds = np.array(ds)
            if sp == "ALL":
                d = ds[:, 0] - ds[:, 1]
                diffs = d
            else:
                cells.append(f"{np.nanmean(ds[:,0]):+.0f} / {np.nanmean(ds[:,1]):+.0f}")
        print(f"| {nm} | " + " | ".join(cells) +
              f" | {np.nanmean(diffs):+.0f} ({np.mean(diffs > 0)*100:.0f}% seeds > 0) |")

    # random-day-subset null for TC on the strategy lines
    print("\n### TC-only vs random day subsets of the same size (central $ total, 2000 draws)\n")
    rng = np.random.default_rng(1)
    for nm, k in (("R4 ref", "r4ref"), ("coil+hyg+stack", "r4H"), ("quiet+hyg+stack", "quiet"),
                  ("quiet literal", "quietN"), ("random seed 0 hyg+stack", "rand_0")):
        byd = {}
        for x in LEGS[k]:
            byd[x["date"]] = byd.get(x["date"], 0) + x["n_c"]
        for sp in ("Y1", "Y2", "OOS", "ALL"):
            dd = [d for d in DATES if sp == "ALL" or LL.split_of(d) == sp]
            ntc = sum(1 for d in dd if TC.get(d))
            real = sum(byd.get(d, 0) for d in dd if TC.get(d))
            arr = np.array([sum(byd.get(d, 0) for d in rng.choice(dd, ntc, replace=False))
                            for _ in range(2000)])
            print(f"{nm:28s} {sp:4s} TC days {ntc:3d}: TC total {real:+9.0f}  null mean {arr.mean():+9.0f}  pct {pct(real, arr):5.1f}")

    print("\n## C. Halal-PASS-only lines (PRESENT-DAY list data/halal_list.json, 472 names; "
          "selection ignored halal; post-hoc filter only)\n")
    hdr()
    for nm, k in (("coil+hyg+stack", "r4H"), ("quiet+hyg+stack", "quiet"), ("quiet literal", "quietN"),
                  ("R4 ref", "r4ref")):
        print_line(nm + " | halal-PASS", [x for x in LEGS[k] if x["sym"] in HAL], ND)

    print("\n## D. Exit-reason mix and entry spread (diagnostic)\n")
    from collections import Counter
    for k in ("r4H", "quiet", "ret15", "rand_0", "randQ_0", "quietN"):
        L_ = LEGS[k]
        c = Counter(x["reason"].split()[0] for x in L_)
        print(k, len(L_), dict(c.most_common(6)), "median h_e", round(float(np.median([x["h_e"] for x in L_])), 1) if L_ else "",
              "mean notional", round(float(np.mean([x["notional"] for x in L_]))) if L_ else "")


if __name__ == "__main__":
    main()
