"""LEADS-TEST adversarial audit of the positive-looking rows (light).
    python plan/lt_audit.py"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lt_lib as LL
D = json.loads((LL.ROOT / "data/research_oct/lt_legs.json").read_text())
LEGS, DATES = D["legs"], D["dates"]
TC = LL.tc_labels()
rng = np.random.default_rng(0)


def daytot(legs, dates, k="n_c"):
    b = {d: 0.0 for d in dates}
    for x in legs:
        if x["date"] in b:
            b[x["date"]] += x[k]
    return np.array([b[d] for d in dates])


def boot(v, n=4000):
    m = [rng.choice(v, len(v)).mean() for _ in range(n)]
    return np.percentile(m, [5, 95])


for name in ("quietN", "r4ref", "quiet", "ret15"):
    L = LEGS[name]
    for sp in ("Y1", "Y2", "OOS"):
        ds = [d for d in DATES if LL.split_of(d) == sp]
        for lab, sub in (("all", ds), ("TC", [d for d in ds if TC.get(d)]), ("notTC", [d for d in ds if not TC.get(d)])):
            v = daytot(L, sub)
            legs = [x["n_c"] for x in L if x["date"] in set(sub)]
            if not legs:
                continue
            srt = np.sort(legs)
            top5 = srt[-5:].sum()
            t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 2 and v.std() > 0 else np.nan
            lo, hi = boot(v)
            print(f"{name:7s} {sp:3s} {lab:5s} days {len(sub):3d} legs {len(legs):4d} $/day {v.mean():+7.1f} t {t:+5.2f} "
                  f"90%CI/day [{lo:+.0f},{hi:+.0f}] total {sum(legs):+8.0f} top5 {top5:+7.0f} ex5 {sum(legs)-top5:+8.0f}")
# TC-minus-notTC day bootstrap for R4 ref and quietN (in-sample Y1+Y2), per-leg means
for name in ("r4ref", "quietN", "quiet", "r4H"):
    L = [x for x in LEGS[name] if LL.split_of(x["date"]) != "OOS"]
    tcl = [x for x in L if TC.get(x["date"])]
    ntl = [x for x in L if not TC.get(x["date"])]
    bd = {}
    for x in L:
        bd.setdefault(x["date"], []).append(x["n_c"])
    tcd = [d for d in bd if TC.get(d)]
    ntd = [d for d in bd if not TC.get(d)]
    diffs = []
    for _ in range(3000):
        a = np.concatenate([bd[d] for d in rng.choice(tcd, len(tcd))])
        b = np.concatenate([bd[d] for d in rng.choice(ntd, len(ntd))])
        diffs.append(a.mean() - b.mean())
    print(f"{name} in-sample TC-minus-notTC $/tr {np.mean([x['n_c'] for x in tcl]) - np.mean([x['n_c'] for x in ntl]):+.1f} "
          f"90% CI [{np.percentile(diffs,5):+.0f},{np.percentile(diffs,95):+.0f}] P(<=0) {np.mean(np.array(diffs)<=0):.3f}")
# quietN concentration and thinness
q = LEGS["quietN"]
srt = sorted(q, key=lambda x: -x["n_c"])
print("quietN top 8:", [(x["date"], x["sym"], round(x["n_c"]), round(x["notional"]), round(x["h_e"], 1)) for x in srt[:8]])
for lab, f in (("h_e<=10", lambda x: x["h_e"] <= 10), ("h_e>10", lambda x: x["h_e"] > 10),
               ("notional>=9.5k", lambda x: x["notional"] >= 9500), ("notional<9.5k", lambda x: x["notional"] < 9500)):
    s = [x for x in q if f(x)]
    for sp in ("Y1", "Y2", "OOS"):
        v = [x["n_c"] for x in s if LL.split_of(x["date"]) == sp]
        print(f"quietN {lab:15s} {sp} n {len(v):4d} central $/tr {np.mean(v) if v else float('nan'):+7.1f} median {np.median(v) if v else float('nan'):+6.1f}")
