"""PESSIMISM-AUDIT: half-spread under each spread_mode of cr_cost (max of
three = the production choice) on the cr_out/_decomp sample design."""
import sys, json
from datetime import time as dtime
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cr_cost as CC
fs = sorted(CC.CDIR.glob("*.npz")); sel = fs[::max(1, len(fs)//600)][:600]
MINS = [5, 10, 20, 35, 60, 90, 120, 180, 240, 300, 350]
res = {}
for mode in ("max", "med", "cs", "hl2"):
    cm = CC.CostModel(spread_mode=mode, impact_coef=0.0)
    H = []; Mm = []
    for f in sel:
        s, d = f.name[:-4].split("_", 1)
        for m in MINS:
            t = dtime((CC.MIN_M+m)//60, (CC.MIN_M+m) % 60)
            h, i, tier = cm.parts(s, d, t, 15000.0)
            H.append(h); Mm.append(m)
    H = np.array(H); Mm = np.array(Mm)
    res[mode] = dict(median=round(float(np.median(H)), 3), mean=round(float(H.mean()), 3),
                     mean_0930_1030=round(float(H[Mm < 60].mean()), 3),
                     median_0930_1030=round(float(np.median(H[Mm < 60])), 3))
print(json.dumps(res, indent=1))
json.dump(res, open(HERE/"pa_out"/"spread_modes.json", "w"), indent=1)
