"""LEGACY-13 step 8: per-seed $/month of the random-pick frame, with and
without a range gate (post hoc, no resequencing), at flat 12 bps and at a
range-tiered cost (6 / 12 / 18 bps a side for low / mid / high sigma)."""
import json, numpy as np
X = json.load(open(__file__.replace("lm13_seeds.py", "lm13_rnd_legs.json")))
months = len({x["date"][:7] for x in X})
def cost_bps(s, tier):
    if not tier: return 12.0
    if not np.isfinite(s): return 18.0
    return 6.0 if s <= .0086 else (12.0 if s <= .0170 else 18.0)
rows = {}
for lab, keep in {"all": lambda s: True,
                  "skip thin+Q5 (sig nan or >0.0242)": lambda s: np.isfinite(s) and s <= .0242,
                  "skip thin+hi tercile (>0.0170)": lambda s: np.isfinite(s) and s <= .0170,
                  "lo tercile only (<=0.0086)": lambda s: np.isfinite(s) and s <= .0086,
                  "CTRL hi tercile only (>0.0170)": lambda s: np.isfinite(s) and s > .0170}.items():
    for tier in (False, True):
        per = []; per10 = []; nt = []
        for sd in range(10):
            L = [x for x in X if x["seed"] == sd and keep(x["sigma1"])]
            pnl = sum(x["notional"] * (x["ret"] - 2 * cost_bps(x["sigma1"], tier) / 1e4) for x in L)
            p10 = sum(1e4 * (x["ret"] - 2 * cost_bps(x["sigma1"], tier) / 1e4) for x in L)
            per.append(pnl / months); per10.append(p10 / months); nt.append(len(L))
        per, per10 = np.array(per), np.array(per10)
        print(f"{lab:36s} cost={'tiered' if tier else 'flat12'}  tkts/seed {np.mean(nt):6.0f}  "
              f"$/mo actual-notional mean {per.mean():+7.0f} sd {per.std(ddof=1):5.0f} | "
              f"$/mo at full $10k {per10.mean():+7.0f} sd {per10.std(ddof=1):5.0f} "
              f"| $/tkt@10k {per10.mean()*months/np.mean(nt):+6.1f}")
