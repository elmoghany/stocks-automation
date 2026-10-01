"""LEGACY-1: report lm1_seq.json ($10k tickets, return-based)."""
import json, sys, collections
import numpy as np
D = json.load(open(rf"C:\cornell\stocks-automation\day-trading\plan\pa_out\lm1_{sys.argv[1] if len(sys.argv)>1 else 'seq'}.json"))
def net(r, b): return 1e4 * r - b * (2 + r)
def st(L, b=15):
    if not L: return None
    r = np.array([x[1] for x in L]); d = [x[0] for x in L]
    p = net(r, b); byd = collections.defaultdict(float); mon = collections.defaultdict(float)
    for di, pi in zip(d, p): byd[di] += pi; mon[di[:7]] += pi
    y1 = np.array([x < "2025-08-01" for x in d])
    return dict(n=len(r), g=1e4 * r.mean(), n15=p.mean(), n29=net(r, 28.75).mean(),
                y1=net(r[y1], b).mean(), y2=net(r[~y1], b).mean(), mo=p.sum() / max(len(mon), 1),
                mp=sum(v > 0 for v in mon.values()), nm=len(mon), exb=p.sum() - max(byd.values()),
                top5=np.sort(p)[-5:].sum() / max(p[p > 0].sum(), 1e-9))
IS = D["IS"]; OOS = D["OOS"]
vars_ = [k for k in IS if "|" not in k]
print("| exit (R4 frame, sequential) | n | tkt/day | gross $/tkt | net@15 | net@28.75 | Y1 net@15 | Y2 net@15 | $/mo @15 | months+ | ex-best-day $ | top5/gross-profit | RND net@15 mean+-sd | z | OOS n | OOS net@15 $/tkt |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for v in vars_:
    s = st(IS[v]); rn = [st(IS[k])["n15"] for k in IS if k.startswith(v + "|")]
    o = st(OOS.get(v, []))
    z = (s["n15"] - np.mean(rn)) / (np.std(rn) + 1e-9)
    print(f"| {v} | {s['n']} | {s['n']/D['IS_ndays']:.2f} | {s['g']:+.1f} | {s['n15']:+.1f} | {s['n29']:+.1f} | {s['y1']:+.1f} | {s['y2']:+.1f} | {s['mo']:+,.0f} | {s['mp']}/{s['nm']} | {s['exb']:+,.0f} | {s['top5']:.2f} | {np.mean(rn):+.1f}+-{np.std(rn):.1f} | {z:+.2f} | {o['n'] if o else 0} | {o['n15'] if o else float('nan'):+.1f} |")
# reasons for base_next and bear_min1
for v in ("base_next", "bear_min1"):
    if v not in IS: continue
    g = collections.defaultdict(list)
    for x in IS[v]: g[x[2]].append(x[1])
    print(v, {k: (len(a), round(100 * np.mean(a), 2)) for k, a in g.items()})
