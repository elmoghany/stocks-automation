"""LEGACY-12 part 4: (a) a causal LIQUIDITY FLOOR on R4 / 30 random seeds /
C37F-hf3, full mean, ex-R4-top-5 and winsorised; (b) right-tail frequency
(leg >= +25% / +50% of ticket) and left-tail by dvol60 bucket and year.
"""
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
cm = defaultdict(list)
for k, v in r4.items():
    for r in v:
        cm[B.bucket("dvol60", r["f"]["dvol60"])].append(r["bps"])
cmd = {k: float(np.mean(v)) for k, v in cm.items()}
for r in hf3:
    r["bps"] = cmd.get(B.bucket("dvol60", r["f"]["dvol60"]), 28.75)
top5 = set(id(r) for r in sorted(r4["R4"], key=lambda r: -r["ret"])[:5])
g_all = np.array([r["ret"] * TK for r in r4["R4"]])
print(f"R4 gross total per $10k {g_all.sum():+.0f}; top-5 legs {sum(r['ret']*TK for r in r4['R4'] if id(r) in top5):+.0f}; "
      f"ex-top5 mean {np.mean([r['ret']*TK for r in r4['R4'] if id(r) not in top5]):+.2f}/tkt")
rk = [k for k in r4 if k.startswith("RND")]
dv = lambda r: r["f"]["dvol60"] or 0
pdv = lambda r: r["f"]["pdv"] or 0
RULES = {
    "dvol60>=5M": lambda r: dv(r) >= 5e6,
    "dvol60>=20M": lambda r: dv(r) >= 20e6,
    "dvol60>=20M & pdv>=5M": lambda r: dv(r) >= 20e6 and pdv(r) >= 5e6,
    "dvol60<1M (thin)": lambda r: dv(r) < 1e6,
}


def st(rows, ex5=False, flat=None):
    rows = [r for r in rows if not (ex5 and id(r) in top5)]
    if not rows:
        return None
    g = np.array([r["ret"] * TK for r in rows])
    b = np.array([flat if flat is not None else 0.65 * r["bps"] for r in rows])
    n = g - 2 * TK * b / 1e4
    y1 = np.array([r["date"] < Y1 for r in rows])
    return dict(n=len(rows), g=g.mean(), gy1=g[y1].mean() if y1.any() else np.nan,
                gy2=g[~y1].mean() if (~y1).any() else np.nan, net=n.mean(),
                ny1=n[y1].mean() if y1.any() else np.nan, ny2=n[~y1].mean() if (~y1).any() else np.nan,
                mo=n.sum() / (ndays / 21), bps=b.mean())


for name, f in RULES.items():
    print(f"\n### {name}")
    for lab, rows, kw in (("R4", r4["R4"], {}), ("R4 ex-top5", r4["R4"], {"ex5": True}),
                          ("R4 @6bps", r4["R4"], {"flat": 6.0}), ("HF3", hf3, {}), ("HF3 @6bps", hf3, {"flat": 6.0})):
        s = st([r for r in rows if f(r)], **kw)
        if s:
            print(f"  {lab:11s} n={s['n']:4d} ({s['n']/ndays:.2f}/d) gross {s['g']:+7.1f} (Y1 {s['gy1']:+7.1f} Y2 {s['gy2']:+7.1f})"
                  f" net@{s['bps']:.1f}bps {s['net']:+7.1f} (Y1 {s['ny1']:+7.1f} Y2 {s['ny2']:+7.1f}) ${s['mo']:+6.0f}/mo")
    for flat in (None, 6.0):
        ss = [st([r for r in r4[k] if f(r)], flat=flat) for k in rk]
        ss = [s for s in ss if s]
        a = lambda key: np.array([s[key] for s in ss])
        print(f"  RND30 {'@6bps' if flat else '@cent'} n/seed={a('n').mean():.0f} ({a('n').mean()/ndays:.2f}/d) gross {a('g').mean():+6.1f}±{a('g').std():.1f}"
              f" (Y1 {np.nanmean(a('gy1')):+6.1f} Y2 {np.nanmean(a('gy2')):+6.1f}) net {a('net').mean():+6.1f}±{a('net').std():.1f}"
              f" (Y1 {np.nanmean(a('ny1')):+6.1f} Y2 {np.nanmean(a('ny2')):+6.1f}) bps {a('bps').mean():.1f}")

print("\n### tail frequency by dvol60 bucket (per 1000 legs): >=+50%, >=+25%, <=-15% ; Y1/Y2")
for b in sorted({B.bucket("dvol60", r["f"]["dvol60"]) for r in r4["R4"]}):
    for lab, rows in (("R4", r4["R4"]), ("RND", [r for k in rk for r in r4[k]]), ("HF3", hf3)):
        sel = [r for r in rows if B.bucket("dvol60", r["f"]["dvol60"]) == b]
        out = []
        for yy in (True, False):
            s = [r["ret"] for r in sel if (r["date"] < Y1) == yy]
            if s:
                s = np.array(s)
                out.append(f"{(s >= .5).mean()*1e3:5.1f} {(s >= .25).mean()*1e3:5.1f} {(s <= -.15).mean()*1e3:5.1f}")
        print(f"  {b:>14} {lab:4s} n={len(sel):6d}  Y1[{out[0] if out else ''}]  Y2[{out[1] if len(out) > 1 else ''}]")
