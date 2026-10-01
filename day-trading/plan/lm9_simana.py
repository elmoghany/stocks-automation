"""LEGACY-9 step 4: summarise lm9_sim legs (R4 gated at $10k vs 30 seeds)."""
import json
from pathlib import Path
import numpy as np

P = Path(r"C:\cornell\stocks-automation\day-trading\plan")
D = json.load(open(P / "lm9_out/sim_legs.json"))
ds = D["dates"]; LG = D["legs"]
Y2, OOS = "2025-08-01", "2026-08-01"
per = {"Y1": [d for d in ds if d < Y2], "Y2": [d for d in ds if Y2 <= d < OOS], "OOS": [d for d in ds if d >= OOS]}
IS = per["Y1"] + per["Y2"]


def tot(rows, days, key):
    s = set(days)
    r = [x for x in rows if x["date"] in s]
    if key == "g":
        return sum(x["g"] for x in r), len(r)
    if key == "c":
        return sum(x["g"] - x["c_c"] for x in r), len(r)
    if key == "u":
        return sum(x["g"] - x["c_u"] for x in r), len(r)
    if key == "15":
        return sum(x["g"] - x["N"] * 15 * 2 / 1e4 for x in r), len(r)


def line(name, rows, rnd):
    t_g, n = tot(rows, IS, "g"); t_c, _ = tot(rows, IS, "c"); t_u, _ = tot(rows, IS, "u"); t_15, _ = tot(rows, IS, "15")
    mo = len(IS) / 21
    y = {k: tot(rows, v, "c") for k, v in per.items()}
    byday = {}
    for x in rows:
        if x["date"] < OOS:
            byday[x["date"]] = byday.get(x["date"], 0) + x["g"] - x["c_c"]
    leg = sorted([x["g"] - x["c_c"] for x in rows if x["date"] < OOS], reverse=True)
    rt = np.array([tot(r, IS, "c")[0] for r in rnd]) if rnd else None
    pct = (rt < t_c).mean() * 100 if rnd else np.nan
    z = (t_c - rt.mean()) / rt.std() if rnd else np.nan
    rg = np.mean([tot(r, IS, "g")[0] / max(1, tot(r, IS, "g")[1]) for r in rnd]) if rnd else np.nan
    cost_bps = np.mean([(x["c_c"]) / x["N"] * 1e4 / 2 for x in rows if x["date"] < OOS])
    he = np.mean([0.5 * x["h_e"] for x in rows if x["date"] < OOS])
    print(f"| {name} | {n} | {n/len(IS):.2f} | {t_g/n:+.2f} | {he:.1f} | {cost_bps:.1f} | {t_c/n:+.2f} | {t_u/n:+.2f} | {t_15/n:+.2f} | {t_c/mo:+,.0f} | "
          f"{y['Y1'][0]/(len(per['Y1'])/21):+,.0f} / {y['Y2'][0]/(len(per['Y2'])/21):+,.0f} | {y['OOS'][0]:+,.0f} ({y['OOS'][1]}) | "
          f"{(t_c-max(byday.values()))/mo:+,.0f} | {sum(leg[5:])/mo:+,.0f} | {rg:+.2f} | {pct:.0f} | {z:+.2f} |")


print("| config ($10k tickets) | n IS | tkt/day | gross $/tkt | mean entry half×0.5 bps | mean cost bps/side central | net $/tkt central | net $/tkt upper | net $/tkt @15 flat | $/mo central | Y1 / Y2 $/mo | OOS 22d net $ (n) | ex-best-day $/mo | ex-top5-legs $/mo | RND gross $/tkt (same gate) | pct vs RND (central) | z |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|")
for X in ("None", "8", "10", "12", "15", "20"):
    gx = X if X in ("None", "10") else None
    rnd = [LG[f"RND{k}_g{gx}"] for k in range(30)] if gx else None
    line(f"R4 gate h<={X}" if X != "None" else "R4 no gate", LG[f"R4_g{X}"], rnd)
for gx in ("None", "10"):
    r = [x for k in range(30) for x in LG[f"RND{k}_g{gx}"] if x["date"] < OOS]
    print(f"RND g{gx}: n/seed {len(r)/30:.0f}, gross/tkt {np.mean([x['g'] for x in r]):+.2f}, net central/tkt {np.mean([x['g']-x['c_c'] for x in r]):+.2f}")
# where did the gated names go? overlap with base
b = {(x["date"], x["sym"]) for x in LG["R4_gNone"]}
for X in ("10", "12"):
    g = LG[f"R4_g{X}"]
    same = [x for x in g if (x["date"], x["sym"]) in b]; new = [x for x in g if (x["date"], x["sym"]) not in b]
    print(f"gate {X}: kept-from-base {len(same)} net/tkt {np.mean([x['g']-x['c_c'] for x in same]):+.2f}; replacement legs {len(new)} net/tkt {np.mean([x['g']-x['c_c'] for x in new]):+.2f}")
# monthly sign for gate 10
for X in ("None", "10"):
    m = {}
    for x in LG[f"R4_g{X}"]:
        m[x["date"][:7]] = m.get(x["date"][:7], 0) + x["g"] - x["c_c"]
    print(X, "months+", sum(v > 0 for v in m.values()), "/", len(m), " ".join(f"{k[2:]}:{v:+.0f}" for k, v in sorted(m.items())))
