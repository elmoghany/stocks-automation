"""LEGACY-9 step 5: does the gate help the random frame in every year / seed?"""
import json
from pathlib import Path
import numpy as np
P = Path(r"C:\cornell\stocks-automation\day-trading\plan")
LG = json.load(open(P / "lm9_out/sim_legs.json"))["legs"]
per = {"Y1": ("0", "2025-08-01"), "Y2": ("2025-08-01", "2026-08-01"), "OOS": ("2026-08-01", "9")}
for p, (a, b) in per.items():
    for g in ("None", "10"):
        r = [x for k in range(30) for x in LG[f"RND{k}_g{g}"] if a <= x["date"] < b]
        print(p, g, "n/seed", round(len(r) / 30), "gross", round(np.mean([x["g"] for x in r]), 2), "net_c", round(np.mean([x["g"] - x["c_c"] for x in r]), 2),
              "net@15", round(np.mean([x["g"] - x["N"] * 30e-4 for x in r]), 2))
d = []
for k in range(30):
    a = [x for x in LG[f"RND{k}_gNone"] if x["date"] < "2026-08-01"]; b = [x for x in LG[f"RND{k}_g10"] if x["date"] < "2026-08-01"]
    d.append((np.mean([x["g"] - x["c_c"] for x in b]) - np.mean([x["g"] - x["c_c"] for x in a]), np.mean([x["g"] for x in b]) - np.mean([x["g"] for x in a])))
d = np.array(d); print("per-seed net gain/tkt: mean %.2f min %.2f max %.2f ; gross gain mean %.2f min %.2f, seeds improved %d/30" % (d[:, 0].mean(), d[:, 0].min(), d[:, 0].max(), d[:, 1].mean(), d[:, 1].min(), (d[:, 0] > 0).sum()))
# ungated random legs bucketed by h_e: gross by bucket, year split
r = [x for k in range(30) for x in LG[f"RND{k}_gNone"] if x["date"] < "2026-08-01"]
for lo, hi in ((0, 5), (5, 10), (10, 20), (20, 40), (40, 1e9)):
    s = [x for x in r if lo <= x["h_e"] < hi]
    y1 = [x["g"] for x in s if x["date"] < "2025-08-01"]; y2 = [x["g"] for x in s if x["date"] >= "2025-08-01"]
    print(f"h_e {lo}-{hi}: share {len(s)/len(r)*100:.0f}% gross Y1 {np.mean(y1):+.2f} Y2 {np.mean(y2):+.2f} net_c {np.mean([x['g']-x['c_c'] for x in s]):+.2f} median px {np.median([x['N'] for x in s]):.0f}N")
