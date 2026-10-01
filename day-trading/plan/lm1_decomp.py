"""LEGACY-1 (exits): decompose saved honest ledgers by exit reason / hold.
Reads only saved dumps. Per-leg return r = exit/entry - 1, rescaled to a
$10k ticket; net at b bps/side = 10k*(r) - 10k*b/1e4*(2+r)."""
import json, collections, numpy as np
B = r"C:\cornell\stocks-automation\day-trading"
def net(r, b): return 1e4 * r - 1e4 * b / 1e4 * (2 + r)
def rep(name, rows):
    # rows: (reason, r, hold_min, extra)
    print(f"\n== {name}: n={len(rows)}")
    r = np.array([x[1] for x in rows])
    print(f"  all: gross$/tkt10k {1e4*r.mean():+.1f}  net15 {np.mean([net(v,15) for v in r]):+.1f}  win {np.mean(r>0):.3f}")
    g = collections.defaultdict(list)
    for x in rows: g[x[0]].append(x)
    for k, L in sorted(g.items(), key=lambda kv: -len(kv[1])):
        rr = np.array([x[1] for x in L]); h = np.array([x[2] for x in L])
        print(f"  {k:22s} n={len(L):5d} mean%={100*rr.mean():+6.2f} sum$10k={1e4*rr.sum():+9.0f} med%={100*np.median(rr):+5.2f} win={np.mean(rr>0):.2f} holdmed={np.median(h):5.0f}")
    hb = [(0,5),(5,15),(15,30),(30,60),(60,120),(120,999)]
    for a, b_ in hb:
        L = [x for x in rows if a <= x[2] < b_]
        if L:
            rr = np.array([x[1] for x in L])
            print(f"  hold[{a},{b_}) n={len(L):5d} mean%={100*rr.mean():+6.2f} sum$10k={1e4*rr.sum():+9.0f}")
def rs(reason):
    s = reason.split()[0]
    if s == "trail": return reason
    return s
# R4 legs (cp_sim)
d = json.load(open(B + r"\plan\pa_out\cp_r4_legs.json"))
rows = [(rs(x["reason"]), x["exit"] / x["entry"] - 1, x["exit_min"] - x["entry_min"], x) for x in d["legs"]["R4"]]
rep("R4 coil+no stop (cp_sim)", rows)
rnd = []
for k in range(30): rnd += [(rs(x["reason"]), x["exit"] / x["entry"] - 1, x["exit_min"] - x["entry_min"], x) for x in d["legs"][f"RND{k}"]]
rep("RND0-29 pooled (same exits, random pick)", rnd)
# C37F hf3
import datetime as dt
h = json.load(open(B + r"\data\massive\rotation_trades_C37F_hf3.json"))
print("labels", collections.Counter(x["label"] for x in h))
def mins(s): return int(s[11:13]) * 60 + int(s[14:16])
rows = [(rs(x["reason"]), x["exit"] / x["entry"] - 1, mins(x["exit_time"]) - mins(x["entry_time"]), x) for x in h]
rep("C37F-hf3", rows)
# MFE give-back on hf3: peak_pct vs realised
pk = np.array([x["peak_pct"] for x in h]); rr = np.array([100 * (x["exit"] / x["entry"] - 1) for x in h])
print("\nhf3 MFE(peak_pct) quantiles", np.percentile(pk, [10, 25, 50, 75, 90]).round(2), " realised", np.percentile(rr, [10, 25, 50, 75, 90]).round(2))
for a, b_ in [(-99, 0.5), (0.5, 2), (2, 5), (5, 10), (10, 20), (20, 999)]:
    m = (pk >= a) & (pk < b_)
    if m.sum(): print(f"  MFE[{a},{b_}) n={m.sum():4d} mean realised%={rr[m].mean():+6.2f} givebackpp={(pk[m]-rr[m]).mean():5.2f}")
