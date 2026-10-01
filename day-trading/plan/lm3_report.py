"""LEGACY-3 report: per-trigger / time-of-day / vs-random-entry tables from
plan/lm3_trig.py output. Every $ figure is normalised to a $10k ticket
(return on the leg's own notional x $10,000); net = gross - 2 x bps.
Usage: python plan/lm3_report.py IN.json"""
import json
import random
import statistics as st
import sys
from collections import defaultdict

d = json.load(open(sys.argv[1]))
NS = d["nseed"]
DAYS = len({x["date"] for x in d["dec"]})
Y1END = "2025-08-01"


def r10(leg):
    """$ at a $10k ticket, gross."""
    if not leg or not leg.get("notional"):
        return None
    return leg["pnl"] / leg["notional"] * 10_000


def fam(t):
    if t is None:
        return "?"
    if t == "ORB":
        return "ORB (new-high ratchet)"
    if t == "PMH-break":
        return "PMH stop-buy"
    return "pattern:" + t


def tod(ts):
    hm = ts[11:16]
    if hm < "09:45":
        return "a 09:30-09:45"
    if hm < "10:00":
        return "b 09:45-10:00"
    if hm < "10:30":
        return "c 10:00-10:30"
    if hm < "11:30":
        return "d 10:30-11:30"
    if hm < "13:00":
        return "e 11:30-13:00"
    return "f 13:00-14:30"


def boot_ci(v, n=2000, seed=7):
    if len(v) < 5:
        return (float("nan"), float("nan"))
    rr = random.Random(seed)
    ms = sorted(st.fmean(rr.choices(v, k=len(v))) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]


def row(name, v, yrs=None, extra=""):
    if not v:
        return f"| {name} | 0 | | | | | | | |"
    n = len(v)
    m = st.fmean(v)
    lo, hi = boot_ci(v)
    w = sum(1 for x in v if x > 0) / n
    ex5 = st.fmean(sorted(v)[:-5]) if n > 10 else float("nan")
    y = ""
    if yrs:
        a = [x for x, dd in yrs if dd < Y1END]
        b = [x for x, dd in yrs if dd >= Y1END]
        y = (f"{st.fmean(a):+.1f} / {st.fmean(b):+.1f}" if a and b
             else "-")
    return (f"| {name} | {n} | {w:.0%} | {m:+.1f} | [{lo:+.0f}, {hi:+.0f}]"
            f" | {m - 12:+.1f} | {m - 30:+.1f} | {ex5:+.1f} | {y} |{extra}")


HDR = ("| bucket | n | win | gross $/tkt@10k | 95% CI | net @6bps | "
       "net @15bps | ex-top-5 gross | Y1 / Y2 gross |\n"
       "|---|---:|---:|---:|---:|---:|---:|---:|---:|")

dec = d["dec"]
fired = [x for x in dec if x["real"]]
print(f"days {DAYS}, decisions {len(dec)}, real tickets {len(fired)} "
      f"({len(fired) / DAYS:.2f}/day), run tickets {len(d['tickets'])}")
print(f"identity: sum real pnl (actual budgets) "
      f"{sum(x['real']['pnl'] for x in fired):+,.0f} vs run "
      f"{sum(t['pnl'] for t in d['tickets']):+,.0f}")

print("\n## A. per trigger (real C37F tickets)\n")
print(HDR)
g = defaultdict(list)
for x in fired:
    g[fam(x["real"]["trig"])].append((r10(x["real"]), x["date"]))
print(row("ALL", [a for v in g.values() for a, _ in v],
          [p for v in g.values() for p in v]))
for k in sorted(g, key=lambda k: -len(g[k])):
    print(row(k, [a for a, _ in g[k]], g[k]))

print("\n## B. trigger family x entry time\n")
print(HDR)
g2 = defaultdict(list)
for x in fired:
    f = fam(x["real"]["trig"])
    f = f if not f.startswith("pattern") else "patterns (all)"
    g2[(f, tod(x["real"]["t"]))].append((r10(x["real"]), x["date"]))
for k in sorted(g2):
    print(row(f"{k[0]} @ {k[1][2:]}", [a for a, _ in g2[k]], g2[k]))
g3 = defaultdict(list)
for x in fired:
    g3[tod(x["real"]["t"])].append((r10(x["real"]), x["date"]))
for k in sorted(g3):
    print(row(f"ALL @ {k[2:]}", [a for a, _ in g3[k]], g3[k]))


def ctl_mean(x):
    vals = [r10(x["ctl"][f"r{s}"]) for s in range(NS)]
    vals = [v for v in vals if v is not None]
    return st.fmean(vals) if vals else None


print("\n## C. paired: trigger vs untriggered entry on the SAME decision\n")
print("Conditional on the trigger firing (control knows the name later "
      "fired -> control is favoured):\n")
print("| trigger | n | trigger $/tkt | imm (first bar) $/tkt | random<=30m "
      "$/tkt | trig - rnd | 95% CI | trig - imm |\n"
      "|---|---:|---:|---:|---:|---:|---:|---:|")
gp = defaultdict(list)
for x in fired:
    if not x["ctl"]:
        continue
    a, b, c = r10(x["real"]), r10(x["ctl"]["imm"]), ctl_mean(x)
    if a is None or b is None or c is None:
        continue
    f = fam(x["real"]["trig"])
    gp[f].append((a, b, c))
    gp["ALL"].append((a, b, c))
    if f.startswith("pattern"):
        gp["patterns (all)"].append((a, b, c))
for k in sorted(gp, key=lambda k: -len(gp[k])):
    v = gp[k]
    dd = [a - c for a, b, c in v]
    lo, hi = boot_ci(dd)
    print(f"| {k} | {len(v)} | {st.fmean(a for a, _, _ in v):+.1f} | "
          f"{st.fmean(b for _, b, _ in v):+.1f} | "
          f"{st.fmean(c for _, _, c in v):+.1f} | {st.fmean(dd):+.1f} | "
          f"[{lo:+.0f}, {hi:+.0f}] | "
          f"{st.fmean(a - b for a, b, _ in v):+.1f} |")

print("\nUnconditional (every decision the rotation made, lookahead-free):\n")
tot_r = [r10(x["real"]) for x in dec if x["real"]]
n_dec = len(dec)
rnd_all = [ctl_mean(x) for x in dec if x["ctl"]]
rnd_all = [v for v in rnd_all if v is not None]
imm_all = [r10(x["ctl"]["imm"]) for x in dec if x["ctl"]]
imm_all = [v for v in imm_all if v is not None]
print(f"- decisions {n_dec}; trigger fired on {len(tot_r)} "
      f"({len(tot_r) / n_dec:.0%}), $/ticket {st.fmean(tot_r):+.1f}, "
      f"$/decision {sum(tot_r) / n_dec:+.1f}")
print(f"- random<=30m filled on {len(rnd_all)} ({len(rnd_all) / n_dec:.0%})"
      f", $/ticket {st.fmean(rnd_all):+.1f}")
print(f"- immediate filled on {len(imm_all)} ({len(imm_all) / n_dec:.0%})"
      f", $/ticket {st.fmean(imm_all):+.1f}")
# no-fire decisions: what would entering have earned?
nf = [ctl_mean(x) for x in dec if not x["real"] and x["ctl"]]
nf = [v for v in nf if v is not None]
if nf:
    print(f"- decisions where the trigger NEVER fired: random entry would "
          f"have made {st.fmean(nf):+.1f}/tkt over {len(nf)} "
          f"(the trigger's 'skip' value)")

print("\n## D. trigger delay (minutes from arming to fill)\n")
print(HDR)
gd = defaultdict(list)
for x in fired:
    es = x["es"][:5]
    m0 = int(es[:2]) * 60 + int(es[3:5])
    t = x["real"]["t"][11:16]
    m1 = int(t[:2]) * 60 + int(t[3:5])
    dl = m1 - m0
    b = ("0-5" if dl <= 5 else "6-30" if dl <= 30 else "31-90" if dl <= 90
         else ">90")
    gd[b].append((r10(x["real"]), x["date"]))
for k in ["0-5", "6-30", "31-90", ">90"]:
    print(row(f"delay {k}", [a for a, _ in gd[k]], gd[k]))

print("\n## E. exit reason x trigger family (count, gross $/tkt)\n")
ge = defaultdict(list)
for x in fired:
    f = fam(x["real"]["trig"])
    f = f if not f.startswith("pattern") else "patterns"
    rsn = (x["real"]["reason"] or "?").split()[0]
    ge[(f, rsn)].append(r10(x["real"]))
for k in sorted(ge):
    print(f"- {k[0]} / {k[1]}: n={len(ge[k])} {st.fmean(ge[k]):+.1f}")

print("\n## F. how often is the trigger fill IDENTICAL to the immediate fill\n")
gi = defaultdict(lambda: [0, 0])
for x in fired:
    if not x["ctl"] or not x["ctl"]["imm"]:
        continue
    f = fam(x["real"]["trig"])
    same = (x["real"]["t"] == x["ctl"]["imm"]["t"]
            and abs(x["real"]["px"] - x["ctl"]["imm"]["px"]) < 1e-6)
    gi[f][0] += same
    gi[f][1] += 1
for k, (a, b) in sorted(gi.items(), key=lambda kv: -kv[1][1]):
    print(f"- {k}: {a}/{b} identical ({a / b:.0%})")
# months: tickets/day x 21
print(f"\ntickets/day (sampled days) {len(fired) / DAYS:.2f}")
