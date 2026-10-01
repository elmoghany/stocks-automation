"""LEGACY-1: base_next exit legs by reason with MFE/MAE (to exit and to 15:00)."""
import json, collections
import numpy as np
D = json.load(open(r"C:\cornell\stocks-automation\day-trading\plan\pa_out\lm1_fixed.json"))
for s in ("R4", "RND", "HF3"):
    res = D["out"][s]["base_next"]; mf = D["mfe"][s]
    g = collections.defaultdict(list)
    for j, x in enumerate(res):
        if x is None or mf[j] is None: continue
        k = x[1] if not x[1].startswith("trail") else x[1]
        g[k].append((x[0], x[2]) + tuple(mf[j]))
    allr = [v for L in g.values() for v in L]
    print(f"\n## {s} base_next n={len(allr)}  MFE-to-15:00 >=3%: {np.mean([v[4]>=.03 for v in allr]):.2f}  >=10%: {np.mean([v[4]>=.10 for v in allr]):.2f}")
    print("| reason | n | mean % | sum $10k | med hold | med MFE(to exit) | med MAE | MFE>=3% | MFE>=10% | med MFE to 15:00 | capture (mean r / mean MFE) |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k, L in sorted(g.items(), key=lambda kv: -len(kv[1])):
        a = np.array(L)
        print(f"| {k} | {len(a)} | {100*a[:,0].mean():+.2f} | {1e4*a[:,0].sum():+,.0f} | {np.median(a[:,1]):.0f} | {100*np.median(a[:,2]):+.2f} | {100*np.median(a[:,3]):+.2f} | {np.mean(a[:,2]>=.03):.2f} | {np.mean(a[:,2]>=.10):.2f} | {100*np.median(a[:,4]):+.2f} | {a[:,0].mean()/max(a[:,2].mean(),1e-9):.2f} |")
    # flatten losers that were up >=3% at some point
    fl = np.array(g.get("flatten", [[0]*6]))
    print(f"flatten legs: MFE>=3% then finished red: {np.mean((fl[:,2]>=.03)&(fl[:,0]<0)):.2f}")
