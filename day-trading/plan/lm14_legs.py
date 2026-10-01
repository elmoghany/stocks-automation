"""LEGACY-14: analysis-only pass over CHAMPION-REPLAY R4's saved legs
(plan/pa_out/cp_r4_legs.json). Questions: is the old re-entry ladder /
front-loading finding (entry #1 best, entries 1-3 = 73% of profit) still
true on the honest R4 ledger? Entry hour? Exit reasons? Everything is
re-expressed per $10k ticket (return% x $10k) with a per-side cost."""
import json
from collections import defaultdict
import numpy as np

P = r"C:\cornell\stocks-automation\day-trading\plan\pa_out\cp_r4_legs.json"
d = json.load(open(P))
legs = d["legs"]["R4"]
rnd = [d["legs"][f"RND{k}"] for k in range(30)]
Y2 = "2025-08-01"


def ret(x):
    return x["exit"] / x["entry"] - 1.0


def net10(x, bps):
    """$ on a $10k ticket at `bps` per side."""
    r = ret(x)
    return 10_000 * (r - bps / 1e4 * (2 + r))


def tag(L):
    by = defaultdict(list)
    for x in L:
        by[x["date"]].append(x)
    for dd, xs in by.items():
        xs.sort(key=lambda z: z["entry_min"])
        for k, x in enumerate(xs):
            x["k"] = k + 1
    return L


def row(name, xs, bps=(0, 12, 15, 18)):
    if not xs:
        return f"| {name} | 0 |"
    r = np.array([ret(x) for x in xs]) * 100
    outs = [np.mean([net10(x, b) for x in xs]) for b in bps]
    srt = sorted((net10(x, 15) for x in xs), reverse=True)
    ex5 = sum(srt[5:]) / max(len(srt) - 5, 1)
    y1 = [net10(x, 15) for x in xs if x["date"] < Y2]
    y2 = [net10(x, 15) for x in xs if x["date"] >= Y2]
    return (f"| {name} | {len(xs)} | {np.mean(r):+.2f}% | {np.median(r):+.2f}% | "
            + " | ".join(f"{o:+.1f}" for o in outs)
            + f" | {ex5:+.1f} | {np.mean(y1) if y1 else 0:+.1f} / {np.mean(y2) if y2 else 0:+.1f} |")


HDR = ("| slice | n | mean ret | median ret | $/tkt 0bps | 12 | 15 | 18 | "
       "15bps ex-top5 $/tkt | 15bps Y1 / Y2 $/tkt |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

tag(legs)
for L in rnd:
    tag(L)
print("R4 legs", len(legs), "days", d["ndays"])
print("\n## by entry number within day (R4)\n" + HDR)
print(row("all", legs))
for k in range(1, 8):
    print(row(f"entry #{k}", [x for x in legs if x["k"] == k]))
print("\n## same, random-pick control (30 seeds pooled)\n" + HDR)
allr = [x for L in rnd for x in L]
for k in range(1, 8):
    print(row(f"RND entry #{k}", [x for x in allr if x["k"] == k]))

print("\n## cumulative cap: keep only the first N entries/day (R4), $/month at 15bps\n")
months = sorted({x["date"][:7] for x in legs})
nm = 22
print("| cap N | tickets | $/tkt 15bps | $/month 15bps | $/month 0bps | ex-top5 $/month 15 |")
print("|---:|---:|---:|---:|---:|---:|")
for N in range(1, 8):
    xs = [x for x in legs if x["k"] <= N]
    v15 = [net10(x, 15) for x in xs]
    srt = sorted(v15, reverse=True)
    print(f"| {N} | {len(xs)} | {np.mean(v15):+.1f} | {sum(v15)/nm:+,.0f} | "
          f"{sum(net10(x,0) for x in xs)/nm:+,.0f} | {sum(srt[5:])/nm:+,.0f} |")

print("\n## by entry hour (R4)\n" + HDR)
for lo, hi, nmz in [(335, 360, "09:35-10:00"), (360, 390, "10:00-10:30"), (390, 450, "10:30-11:30"),
                    (450, 510, "11:30-12:30"), (510, 600, "12:30-14:00"), (600, 700, "14:00-14:30")]:
    print(row(nmz, [x for x in legs if lo <= x["entry_min"] < hi]))

print("\n## by exit reason (R4)\n" + HDR)
for rz in ["bearish", "trail", "flatten"]:
    print(row(rz, [x for x in legs if x["reason"].startswith(rz)]))

print("\n## does the previous leg's outcome predict the next? (R4, entries #2+)\n" + HDR)
by = defaultdict(list)
for x in legs:
    by[x["date"]].append(x)
aw, al = [], []
for dd, xs in by.items():
    xs.sort(key=lambda z: z["k"])
    for a, b in zip(xs, xs[1:]):
        (aw if ret(a) > 0 else al).append(b)
print(row("after a winning leg", aw))
print(row("after a losing leg", al))

# day-level: first-leg outcome vs rest of day
print("\n## stop-after-first-loss / stop-after-N-losses rule (R4), 15bps\n")
print("| rule | tickets | $/tkt | $/month | ex-top5 $/month |\n|---|---:|---:|---:|---:|")
for nl in (1, 2, 3, 99):
    keep = []
    for dd, xs in by.items():
        losses = 0
        for x in xs:
            keep.append(x)
            if ret(x) <= 0:
                losses += 1
            if losses >= nl:
                break
    v = sorted((net10(x, 15) for x in keep), reverse=True)
    print(f"| stop after {nl} losing legs | {len(keep)} | {np.mean(v):+.1f} | {sum(v)/nm:+,.0f} | {sum(v[5:])/nm:+,.0f} |")
