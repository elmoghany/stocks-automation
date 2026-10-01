"""LEGACY-12 part 2: candidate causal filters from the bucket tables, applied
post hoc to R4 (and the same filter to each of its 30 random seeds, and to
C37F-hf3).  $10k tickets.  Cost: per-leg evidence cost (upper) and 0.65x it
(central, mean ~18.7 bps/side), plus flat 15 bps/side.  Month-block bootstrap
of the R4 kept-vs-dropped difference.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lm12_buckets as B  # noqa: E402

TK, Y1 = 10_000.0, "2025-08-01"

r4, ndays = B.load_r4()
hf3 = B.load_hf3()
allsets = dict(r4)
allsets["HF3"] = hf3
keys = sorted({(r["date"], r["sym"]) for rows in allsets.values() for r in rows})
cache = {(s, d): B.feats(s, d, None) for d, s in keys}
for rows in allsets.values():
    for r in rows:
        r["f"] = dict(cache[(r["sym"], r["date"])], price=r["entry"])

pool = [r for k, rows in r4.items() for r in rows]
cm = defaultdict(list)
for r in pool:
    cm[B.bucket("dvol60", r["f"]["dvol60"])].append(r["bps"])
cmd = {k: float(np.mean(v)) for k, v in cm.items()}
for r in hf3:
    r["bps"] = cmd.get(B.bucket("dvol60", r["f"]["dvol60"]), 28.75)

dv = lambda r: r["f"]["dvol60"] or 0
rv = lambda r: r["f"]["rvol1"]
px = lambda r: r["f"]["price"]
FILT = {
    "ALL": lambda r: True,
    "drop dvol60 $1-5M": lambda r: not (1e6 <= dv(r) < 5e6),
    "drop rvol1<0.5 or >5": lambda r: rv(r) is None or 0.5 <= rv(r) <= 5,
    "drop both": lambda r: not (1e6 <= dv(r) < 5e6) and (rv(r) is None or 0.5 <= rv(r) <= 5),
    "price $5-10 only": lambda r: 5 <= px(r) < 10,
    "price $2-10 only": lambda r: 2 <= px(r) < 10,
    "drop price $10-50": lambda r: not (10 <= px(r) < 50),
    "dvol60 < $1M only": lambda r: dv(r) < 1e6,
}


def stat(rows, cf):
    if not rows:
        return {}
    g = np.array([r["ret"] * TK for r in rows])
    out = {"n": len(rows), "gross": g.mean()}
    for lab, f in cf.items():
        n = g - 2 * TK * np.array([f(r) for r in rows]) / 1e4
        y1 = np.array([r["date"] < Y1 for r in rows])
        mo = defaultdict(float)
        for r, x in zip(rows, n):
            mo[r["date"][:7]] += x
        out[lab] = dict(net=n.mean(), y1=n[y1].mean() if y1.any() else np.nan,
                        y2=n[~y1].mean() if (~y1).any() else np.nan,
                        per_mo=n.sum() / (ndays / 21.0),
                        mo_pos=f"{sum(v > 0 for v in mo.values())}/{len(mo)}")
    out["gy1"] = g[np.array([r['date'] < Y1 for r in rows])].mean()
    out["gy2"] = g[np.array([r['date'] >= Y1 for r in rows])].mean()
    return out


CF = {"central": lambda r: 0.65 * r["bps"], "evid": lambda r: r["bps"], "flat15": lambda r: 15.0}
rnd_keys = [k for k in r4 if k.startswith("RND")]
res = {}
rng = np.random.default_rng(0)
for name, f in FILT.items():
    R = stat([r for r in r4["R4"] if f(r)], CF)
    rs = [stat([r for r in r4[k] if f(r)], {"central": CF["central"]}) for k in rnd_keys]
    rnd_g = np.array([s["gross"] for s in rs])
    rnd_c = np.array([s["central"]["net"] for s in rs])
    H = stat([r for r in hf3 if f(r)], {"central": CF["central"]})
    # month-block bootstrap: kept-minus-dropped gross difference in R4
    kept = [r for r in r4["R4"] if f(r)]
    drop = [r for r in r4["R4"] if not f(r)]
    boot = None
    if drop and name != "ALL":
        months = sorted({r["date"][:7] for r in r4["R4"]})
        bk = defaultdict(list); bd = defaultdict(list)
        for r in kept: bk[r["date"][:7]].append(r["ret"] * TK)
        for r in drop: bd[r["date"][:7]].append(r["ret"] * TK)
        diffs = []
        for _ in range(2000):
            ms = rng.choice(months, len(months))
            a = [x for m in ms for x in bk[m]]; b = [x for m in ms for x in bd[m]]
            if a and b:
                diffs.append(np.mean(a) - np.mean(b))
        boot = (float(np.mean(np.array(diffs) > 0)), float(np.percentile(diffs, 5)), float(np.percentile(diffs, 95)))
    res[name] = dict(R4=R, rnd_gross=(rnd_g.mean(), rnd_g.std()), rnd_central=(rnd_c.mean(), rnd_c.std()),
                     z_central=(R["central"]["net"] - rnd_c.mean()) / rnd_c.std(), HF3=H, boot_kept_gt_drop=boot)
    c, e, fl = R["central"], R["evid"], R["flat15"]
    print(f"\n### {name}: R4 n={R['n']} ({R['n']/ndays:.2f}/day) gross {R['gross']:+.1f} (Y1 {R['gy1']:+.1f} / Y2 {R['gy2']:+.1f})")
    for lab, x in (("central", c), ("evid", e), ("flat15", fl)):
        print(f"   net@{lab:8s} {x['net']:+7.1f}/tkt  Y1 {x['y1']:+7.1f}  Y2 {x['y2']:+7.1f}  ${x['per_mo']:+8.0f}/mo  months+ {x['mo_pos']}")
    print(f"   RND same filter: gross {rnd_g.mean():+.1f}±{rnd_g.std():.1f}, central {rnd_c.mean():+.1f}±{rnd_c.std():.1f}; R4 z(central) {res[name]['z_central']:+.2f}")
    print(f"   HF3 same filter: n={H.get('n')} gross {H.get('gross', np.nan):+.1f} (Y1 {H.get('gy1', np.nan):+.1f} / Y2 {H.get('gy2', np.nan):+.1f}) central {H['central']['net'] if H else np.nan:+.1f}")
    if boot:
        print(f"   bootstrap P(kept>dropped gross) {boot[0]:.3f}, diff 90% CI [{boot[1]:+.0f}, {boot[2]:+.0f}]")
(Path(__file__).parent / "lm12_filters_out.json").write_text(json.dumps(res, indent=1, default=float))
