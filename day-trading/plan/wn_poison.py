"""WIDE-NET (2026-09-16): the poison test, run on THIS study's own pipeline
and at the level the mandate specifies -- the PICKS, not just the features.

For a sampled day and a sampled decision time t (minute m), every 1-minute
bar strictly after m is replaced with uniform garbage (prices 0.5-500,
volumes up to 10^7).  The whole causal block is recomputed through
plan/rl2/features.compute_day and then through plan/wn_table.day_block --
the same two functions the real table was built with -- and the test
asserts:

  1. every one of the 30 wide-net feature columns at every decision time
     <= m is BIT-IDENTICAL,
  2. `printed` and `notional` at those times are identical,
  3. the pattern's TOP-1 PICK at time m is the same ticker,

for every pattern in data/massive/wn/rules_search.json plus the model
score's feature inputs.  A single mismatch means a feature can see the
future and every dollar in the audit is void.

`fill_o`, `pnl` and `ok` are DELIBERATELY excluded: they price the fill at
minute m+1 and are the label, not the state.  A poisoned run must change
them -- if it did not, the label would not be reading the future it is
supposed to read, and the test asserts that too (a sanity direction check).

Usage: python plan/wn_poison.py [--days 12]
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))

import features as FT                                   # noqa: E402
import wn_table as WT                                   # noqa: E402
from wn_lib import Table, write_json                    # noqa: E402
from wn_rules import RTH, apply_rule                    # noqa: E402

DAYS = HERE / "rl2" / "out" / "days"


def top1(F, live, fidx, rule, sd, syms, ti):
    """The rule's top-1 pick at decision index ti from a feature block."""
    m = live[ti].copy()
    sc = np.zeros(len(syms))
    k = 0
    for cond in rule:
        if cond.startswith("dec=="):
            if WT.DEC_ET[ti] != cond[5:]:
                return None
            continue
        if cond.startswith("sic2=="):
            m &= F[ti, :, fidx["sic2"]].astype(int) == int(cond[6:])
            continue
        if "<=" in cond:
            f, v = cond.split("<="); sgn = -1.0
        else:
            f, v = cond.split(">"); sgn = +1.0
        x = F[ti, :, fidx[f]].astype(np.float64)
        m &= (x <= float(v)) if sgn < 0 else (x > float(v))
        sc += sgn * (x - float(v)) / sd[f]
        k += 1
    if not m.any():
        return "<no match>"
    sc = np.where(m, sc / max(k, 1), -np.inf)
    return syms[int(np.argmax(sc))]


def main(ndays=12, seed=7):
    t = Table()
    sd = {f: float(np.std(t.F[t.split == 0, t.fidx[f]].astype(np.float64)))
          or 1.0 for f in t.feat}
    rules = [r["rule"] for r in
             json.loads((WT.OUT / "rules_search.json").read_text())]
    rules = [list(x) for x in {tuple(r) for r in rules}]

    prof = FT.fit_profile()
    daily = FT.Daily()
    sic2, earn = WT.load_sic2(), WT.load_earn()
    files = sorted(DAYS.glob("*.npz"))
    rng = np.random.default_rng(seed)
    pick = [files[i] for i in
            rng.choice(len(files), min(ndays, len(files)), replace=False)]

    cuts = [WT.DEC_ET.index(x) for x in ("09:35", "10:30", "13:00", "15:00")]
    checks = mism = pickchecks = pickmism = 0
    labelmoved = 0
    detail = []
    for p in pick:
        date = p.stem
        syms, pc, bars = FT.load_raw(p)
        clean = WT.day_block(date, FT.compute_day(date, syms, pc, bars, prof,
                                                  daily), sic2, earn)
        for ci in cuts:
            m = int(WT.STEPS[WT.DEC_T[ci]])
            o, h, lo, c, v = (a.copy() for a in bars)
            sl = slice(m + 1, None)
            shp = o[:, sl].shape
            g = rng.uniform(0.5, 500.0, size=shp)
            o[:, sl] = g
            h[:, sl] = g * rng.uniform(1.0, 1.5, size=shp)
            lo[:, sl] = g * rng.uniform(0.5, 1.0, size=shp)
            c[:, sl] = g * rng.uniform(0.7, 1.3, size=shp)
            v[:, sl] = rng.integers(1, 10 ** 7, size=shp)
            bad = WT.day_block(date, FT.compute_day(
                date, syms, pc, (o, h, lo, c, v), prof, daily), sic2, earn)
            keep = WT.STEPS[WT.DEC_T] <= m
            for k in ("F", "printed", "notional"):
                a = np.nan_to_num(clean[k][keep], nan=-9e9)
                b = np.nan_to_num(bad[k][keep], nan=-9e9)
                checks += 1
                if not np.array_equal(a, b):
                    mism += 1
                    detail.append({"date": date, "cut": WT.DEC_ET[ci],
                                   "array": k,
                                   "n_diff": int((a != b).sum())})
            # the label MUST move (it prices minute m+1 onward)
            if not np.array_equal(np.nan_to_num(clean["pnl"][ci]),
                                  np.nan_to_num(bad["pnl"][ci])):
                labelmoved += 1
            for r in rules:
                aa = top1(clean["F"], clean["printed"], t.fidx, r, sd,
                          clean["syms"], ci)
                bb = top1(bad["F"], bad["printed"], t.fidx, r, sd,
                          bad["syms"], ci)
                if aa is None:
                    continue
                pickchecks += 1
                if aa != bb:
                    pickmism += 1
                    detail.append({"date": date, "cut": WT.DEC_ET[ci],
                                   "rule": r, "clean": aa, "poisoned": bb})
        print(f"  {date}: {checks} array checks, {pickchecks} pick checks, "
              f"{mism + pickmism} mismatches", flush=True)

    res = {"days": len(pick), "cuts": [WT.DEC_ET[c] for c in cuts],
           "array_checks": checks, "array_mismatches": mism,
           "pick_checks": pickchecks, "pick_mismatches": pickmism,
           "label_moved_of": len(pick) * len(cuts),
           "label_moved": labelmoved,
           "rules_tested": len(rules), "detail": detail[:20],
           "PASS": bool(mism == 0 and pickmism == 0
                        and labelmoved == len(pick) * len(cuts))}
    write_json("poison.json", res)
    print(json.dumps({k: v for k, v in res.items() if k != "detail"}, indent=1))


if __name__ == "__main__":
    a = sys.argv
    main(int(a[a.index("--days") + 1]) if "--days" in a else 12)
