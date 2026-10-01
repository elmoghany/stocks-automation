"""LEGACY-9 step 7: robustness of the cheap / cheap_coil rankings."""
import json
from pathlib import Path
import numpy as np
P = Path(r"C:\cornell\stocks-automation\day-trading\plan")
D = json.load(open(P / "lm9_out/cheap_legs.json"))
S = json.load(open(P / "lm9_out/sim_legs.json"))["legs"]
D["R4_g8"] = S["R4_g8"]; D["R4_g10"] = S["R4_g10"]; D["R4_none"] = S["R4_gNone"]
D["RND_g10_seed0"] = S["RND0_g10"]
ndays_is = 444
for k, r in D.items():
    s = [x for x in r if x["date"] < "2026-08-01"]
    net = np.array([x["g"] - x["c_c"] for x in s])
    byday, bym = {}, {}
    for x, v in zip(s, net):
        byday[x["date"]] = byday.get(x["date"], 0) + v; bym[x["date"][:7]] = bym.get(x["date"][:7], 0) + v
    dv = np.array(list(byday.values()))
    srt = np.sort(net)[::-1]
    t = net.mean() / (net.std(ddof=1) / np.sqrt(len(net)))
    print(f"{k}: n {len(s)} ({len(s)/ndays_is:.2f}/day) net_c/tkt {net.mean():+.2f} t={t:+.2f} $/mo {net.sum()/(ndays_is/21):+,.0f} "
          f"ex-best-day {(net.sum()-dv.max())/(ndays_is/21):+,.0f} ex-top5 {srt[5:].sum()/(ndays_is/21):+,.0f} "
          f"months+ {sum(v>0 for v in bym.values())}/{len(bym)} gross/tkt {np.mean([x['g'] for x in s]):+.2f} top5 share {srt[:5].sum()/max(1,net.sum())*100:.0f}%")
