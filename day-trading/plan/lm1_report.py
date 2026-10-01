"""LEGACY-1: summarize lm1_fixed.json. $ per $10k ticket; net at b bps/side."""
import json, sys, collections
import numpy as np
B = r"C:\cornell\stocks-automation\day-trading"
D = json.load(open(B + r"\plan\pa_out\lm1_fixed.json"))
def net(r, b): return 1e4 * r - b * (2 + r)
MONTHS = 22.0
def row(s, v, keep=None):
    meta = D["sets"][s]; res = D["out"][s][v]
    J = [j for j, x in enumerate(res) if x is not None and (keep is None or keep[j])]
    r = np.array([res[j][0] for j in J]); dts = [meta[j][0] for j in J]
    y1 = np.array([d < "2025-08-01" for d in dts])
    pnl = 1e4 * r
    mon = collections.defaultdict(float)
    for d, p in zip(dts, net(r, 15)): mon[d[:7]] += p
    top5 = np.sort(pnl)[-5:].sum()
    return dict(n=len(r), g=pnl.mean(), n12=net(r, 12).mean(), n15=net(r, 15).mean(),
                n29=net(r, 28.75).mean(), y1=pnl[y1].mean(), y2=pnl[~y1].mean(),
                win=(r > 0).mean(), mpos=sum(v > 0 for v in mon.values()), nm=len(mon),
                ex5=(pnl.sum() - top5) / len(r), med=np.median(pnl),
                mo15=net(r, 15).sum() / MONTHS)
sel = sys.argv[1:] or list(D["out"]["R4"].keys())
# common keep: entries valid under every variant (so rows are same-entry)
for s in ("R4", "RND", "HF3"):
    keep = [all(D["out"][s][v][j] is not None for v in D["out"][s] if "1200" not in v) for j in range(len(D["sets"][s]))]
    print(f"\n### {s}  (n common={sum(keep)}, miss={D['miss'].get(s,0)})")
    print("| exit | n | gross $/tkt | net@12 | net@15 | net@28.75 | Y1 gross | Y2 gross | win | median | ex-top5 gross | months+ @15 | $/mo @15 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for v in sel:
        x = row(s, v, keep)
        print(f"| {v} | {x['n']} | {x['g']:+.1f} | {x['n12']:+.1f} | {x['n15']:+.1f} | {x['n29']:+.1f} | {x['y1']:+.1f} | {x['y2']:+.1f} | {x['win']:.2f} | {x['med']:+.1f} | {x['ex5']:+.1f} | {x['mpos']}/{x['nm']} | {x['mo15']:+,.0f} |")
