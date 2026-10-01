"""LEGACY-1: paired per-entry deltas vs base_next (fixed entries) + post-exit drift."""
import json
import numpy as np
D = json.load(open(r"C:\cornell\stocks-automation\day-trading\plan\pa_out\lm1_fixed.json"))
rng = np.random.default_rng(0)
for s in ("R4", "RND", "HF3"):
    O = D["out"][s]; b = O["base_next"]; dates = [m[0] for m in D["sets"][s]]
    print(f"\n## {s}")
    for v in ("base_close", "stop8", "stop3", "notrail_next", "nobear", "bear_min1", "bear_any", "tp3", "tp10", "red90", "t60", "vwap", "atr3", "lock3", "hold1500"):
        J = [j for j in range(len(b)) if b[j] and O[v][j]]
        d = 1e4 * np.array([O[v][j][0] - b[j][0] for j in J])
        # day-clustered bootstrap SE
        days = sorted(set(dates[j] for j in J)); ix = {dd: k for k, dd in enumerate(days)}
        tot = np.zeros(len(days)); cnt = np.zeros(len(days))
        for j, x in zip(J, d): tot[ix[dates[j]]] += x; cnt[ix[dates[j]]] += 1
        bs = []
        for _ in range(400):
            k = rng.integers(0, len(days), len(days)); bs.append(tot[k].sum() / cnt[k].sum())
        trim = np.sort(d)[5:-5].mean()
        print(f"  {v:13s} delta $/tkt {d.mean():+7.1f}  se {np.std(bs):5.1f}  trimmed(5/5) {trim:+6.1f}  better-share {np.mean(d>0):.2f}")
    # post-exit drift after a bearish exit: hold-to-15:00 minus the bearish exit
    J = [j for j in range(len(b)) if b[j] and b[j][1] == "bearish" and O["hold1500"][j]]
    dr = 1e4 * np.array([O["hold1500"][j][0] - b[j][0] for j in J])
    print(f"  post-bearish-exit drift to 15:00: n={len(J)} mean {dr.mean():+.1f} median {np.median(dr):+.1f} $/tkt (negative = exit was right)")
