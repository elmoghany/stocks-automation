"""LEGACY-5: ticket sequence / rotation analysis on the HONEST R4 dump.

Reads ONLY saved dumps (plan/pa_out/cp_r4_legs.json = R4 coil+no-stop and
its 30 random-pick seeds in the same frame; crs_cp_r5_legs.json; the
cp_feat cache for the cross minute).  No re-simulation, no fetching.

Every rule evaluated here is a SHADOW rule: the engine's sequence is left
untouched (paper-trade the skipped tickets), and only the live P&L of the
kept tickets is counted.  That makes "drop leg k from the dump" an exact,
causal evaluation -- the kept legs' timing does not change.
"""
import json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(r"C:\cornell\stocks-automation\day-trading")
sys.path.insert(0, str(ROOT / "plan"))
import cp_feat as F  # noqa: E402

OPEN, M10 = 330, 360
COSTS = (0, 6, 12, 15, 18)


def p10(l):
    return l["gross"] / (l["entry"] * l["shares"]) * 10_000.0


def load_r4():
    d = json.loads((ROOT / "plan/pa_out/cp_r4_legs.json").read_text())
    return d["ndays"], d["dates"], d["legs"]


def bydate(legs):
    g = defaultdict(list)
    for l in legs:
        g[l["date"]].append(l)
    for v in g.values():
        v.sort(key=lambda x: x["entry_min"])
    return g


def annotate(legs):
    """ordinal, prior result, day-so-far, entry bucket."""
    out = []
    for dt, L in bydate(legs).items():
        cum = 0.0
        for k, l in enumerate(L):
            x = dict(l)
            x["ord"] = k + 1
            x["p"] = p10(l)
            x["prev"] = None if k == 0 else (L[k - 1]["gross"] > 0)
            x["first_win"] = L[0]["gross"] > 0
            x["cum_before"] = cum
            x["hold"] = l["exit_min"] - l["entry_min"]
            x["nday"] = len(L)
            cum += x["p"]
            out.append(x)
    return out


def stat(xs, ndays, c=15):
    if not xs:
        return dict(n=0)
    p = np.array([x["p"] for x in xs])
    net = p - 2 * c
    return dict(n=len(p), g=p.mean(), net=net.mean(), win=(p > 0).mean() * 100,
                med=np.median(p), mo=net.sum() / ndays * 21,
                gmo=p.sum() / ndays * 21)


def fmt(name, s):
    if not s.get("n"):
        return f"| {name} | 0 | | | | | |"
    return (f"| {name} | {s['n']} | {s['g']:+.1f} | {s['net']:+.1f} | {s['win']:.0f}% "
            f"| {s['gmo']:+,.0f} | {s['mo']:+,.0f} |")


HDR = ("| slice | n | gross $/10k | net@15 $/10k | win | gross $/mo | net@15 $/mo |\n"
       "|---|---:|---:|---:|---:|---:|---:|")


def rules(ann):
    """Shadow rules -> list of kept legs."""
    R = {}
    R["ALL (R4 as is)"] = ann
    R["skip ticket #1 (shadow it)"] = [x for x in ann if x["ord"] >= 2]
    R["only ticket #1"] = [x for x in ann if x["ord"] == 1]
    R["shadow until 10:00 (keep entries >=10:00)"] = [x for x in ann if x["entry_min"] >= M10]
    R["keep entries <10:00 only"] = [x for x in ann if x["entry_min"] < M10]
    R["skip #1 only if it enters <10:00"] = [x for x in ann if not (x["ord"] == 1 and x["entry_min"] < M10)]
    R["live only after #1 WON"] = [x for x in ann if x["ord"] >= 2 and x["first_win"]]
    R["live only after #1 LOST"] = [x for x in ann if x["ord"] >= 2 and not x["first_win"]]
    R["after prev WIN (ord>=2)"] = [x for x in ann if x["prev"] is True]
    R["after prev LOSS (ord>=2)"] = [x for x in ann if x["prev"] is False]
    return R


def months_pos(xs, c=15):
    m = defaultdict(float)
    for x in xs:
        m[x["date"][:7]] += x["p"] - 2 * c
    v = np.array(list(m.values()))
    return int((v > 0).sum()), len(v)


def halves(xs, dates, c=15):
    mid = dates[len(dates) // 2]
    a = [x["p"] - 2 * c for x in xs if x["date"] < mid]
    b = [x["p"] - 2 * c for x in xs if x["date"] >= mid]
    return (np.mean(a) if a else np.nan, np.mean(b) if b else np.nan)


def boot_diff(xs_all_days, keep_fn, dates, c=15, B=2000, seed=1):
    """Day-block bootstrap of the $/day difference kept - dropped."""
    rng = np.random.default_rng(seed)
    g = bydate(xs_all_days)
    per = np.array([sum(x["p"] - 2 * c for x in g.get(d, []) if not keep_fn(x)) for d in dates])
    # per-day $ of the DROPPED legs; rule improves if dropped sum < 0
    bs = [per[rng.integers(0, len(per), len(per))].mean() for _ in range(B)]
    return per.mean() * 21, np.percentile(bs, 2.5) * 21, np.percentile(bs, 97.5) * 21


def cross_info(ann):
    """Minutes since the name first appeared on the LAST scanner grid,
    and causal features at the decision grid point (<= entry_min-1)."""
    by = defaultdict(list)
    for x in ann:
        by[x["date"]].append(x)
    for dt, xs in by.items():
        z = F.load(dt)
        if z is None:
            continue
        syms = {s: i for i, s in enumerate(z["syms"])}
        grid = z["grid"]
        el = z["elig_last"]
        nel = el.sum(axis=0)
        for x in xs:
            i = syms.get(x["sym"])
            gi = int(np.searchsorted(grid, x["entry_min"] - 1, side="right") - 1)
            if i is None or gi < 0:
                continue
            row = el[i]
            first = int(np.argmax(row)) if row.any() else None
            x["since_cross"] = None if first is None else int(x["entry_min"] - grid[first])
            x["cross_at_open"] = first == 0
            x["gain_now"] = float(z["gain_now"][i, gi])
            x["coil"] = float(z["coil"][i, gi])
            x["n_elig"] = int(nel[gi])
            x["gap_open"] = float(z["gap_open"][i])


def main():
    ndays, dates, legs = load_r4()
    out = []
    P = out.append
    r4 = annotate(legs["R4"])
    rnd = {k: annotate(v) for k, v in legs.items() if k.startswith("RND")}
    nseed = len(rnd)
    rnd_all = [x for v in rnd.values() for x in v]

    P(f"R4 legs {len(r4)} over {ndays} days; random seeds {nseed}\n")
    P("## A. By ticket ordinal (R4 vs random pick, same frame)\n")
    P(HDR)
    for o in (1, 2, 3, 4, 5):
        sel = (lambda x, o=o: x["ord"] == o) if o < 5 else (lambda x: x["ord"] >= 5)
        lab = f"#{o}" if o < 5 else "#5+"
        P(fmt(f"R4 {lab}", stat([x for x in r4 if sel(x)], ndays)))
        P(fmt(f"RND {lab} (per seed)", stat([x for x in rnd_all if sel(x)], ndays * nseed)))
    P("")

    P("## B. Entry time x ordinal (R4)\n")
    P(HDR)
    bins = [(330, 345), (345, 360), (360, 390), (390, 420), (420, 480), (480, 660)]
    for a, b in bins:
        lab = f"{(a+240)//60}:{(a+240)%60:02d}-{(b+240)//60}:{(b+240)%60:02d}"
        P(fmt(f"R4 #1 {lab}", stat([x for x in r4 if x["ord"] == 1 and a <= x["entry_min"] < b], ndays)))
        P(fmt(f"R4 #2+ {lab}", stat([x for x in r4 if x["ord"] >= 2 and a <= x["entry_min"] < b], ndays)))
        P(fmt(f"RND all {lab} (per seed)", stat([x for x in rnd_all if a <= x["entry_min"] < b], ndays * nseed)))
    P("")

    P("## C. Prior-trade outcome (R4, ord>=2)\n")
    P(HDR)
    for lab, fn in (("prev WIN", lambda x: x["prev"] is True),
                    ("prev LOSS", lambda x: x["prev"] is False),
                    ("#1 won, any later", lambda x: x["ord"] >= 2 and x["first_win"]),
                    ("#1 lost, any later", lambda x: x["ord"] >= 2 and not x["first_win"]),
                    ("day-so-far >0", lambda x: x["ord"] >= 2 and x["cum_before"] > 0),
                    ("day-so-far <=0", lambda x: x["ord"] >= 2 and x["cum_before"] <= 0)):
        P(fmt("R4 " + lab, stat([x for x in r4 if fn(x)], ndays)))
        P(fmt("RND " + lab, stat([x for x in rnd_all if fn(x)], ndays * nseed)))
    P("")

    P("## D. Hold time / exit reason of #1 vs #2+ (R4)\n")
    for o, fn in (("#1", lambda x: x["ord"] == 1), ("#2+", lambda x: x["ord"] >= 2)):
        xs = [x for x in r4 if fn(x)]
        reas = defaultdict(list)
        for x in xs:
            reas[x["reason"].split()[0]].append(x["p"])
        P(f"- {o}: median entry {np.median([x['entry_min'] for x in xs])+240:.0f} min-of-day, "
          f"median hold {np.median([x['hold'] for x in xs]):.0f} min; reasons: "
          + ", ".join(f"{k} n={len(v)} {np.mean(v):+.0f}" for k, v in sorted(reas.items(), key=lambda t: -len(t[1]))))
    P("")

    P("## E. Shadow rules (R4 sequence untouched; skipped legs paper-traded)\n")
    P("| rule | n | gross $/10k | net@15 $/10k | net@6 | net@12 | net@18 | gross $/mo | net@15 $/mo | months+ @15 | H1/H2 net@15 $/10k |")
    P("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for name, xs in rules(r4).items():
        s = stat(xs, ndays)
        mp = months_pos(xs)
        h = halves(xs, dates)
        P(f"| {name} | {s['n']} | {s['g']:+.1f} | {s['net']:+.1f} | {s['g']-12:+.1f} | {s['g']-24:+.1f} | {s['g']-36:+.1f} "
          f"| {s['gmo']:+,.0f} | {s['mo']:+,.0f} | {mp[0]}/{mp[1]} | {h[0]:+.1f} / {h[1]:+.1f} |")
    P("")
    P("### Same shadow rules applied to the 30 random-pick seeds (mean over seeds)\n")
    P("| rule | n/seed | gross $/10k | net@15 $/mo | seeds where rule's net $/mo > ALL's |")
    P("|---|---:|---:|---:|---:|")
    allmo = []
    acc = defaultdict(list)
    for k, v in rnd.items():
        for name, xs in rules(v).items():
            s = stat(xs, ndays)
            acc[name].append((s.get("n", 0), s.get("g", np.nan), s.get("mo", 0.0)))
    base = [t[2] for t in acc["ALL (R4 as is)"]]
    for name, lst in acc.items():
        a = np.array(lst, float)
        better = sum(1 for j, t in enumerate(lst) if t[2] > base[j])
        P(f"| {name.replace('R4 as is','random as is')} | {a[:,0].mean():.0f} | {np.nanmean(a[:,1]):+.1f} | {a[:,2].mean():+,.0f} | {better}/{len(lst)} |")
    P("")

    P("### Day-block bootstrap: $/month of the DROPPED legs (net@15) -- rule helps iff CI < 0\n")
    for name, fn in (("skip #1", lambda x: x["ord"] >= 2),
                     ("shadow until 10:00", lambda x: x["entry_min"] >= M10),
                     ("skip #1 if <10:00", lambda x: not (x["ord"] == 1 and x["entry_min"] < M10))):
        m, lo, hi = boot_diff(r4, fn, dates)
        P(f"- {name}: dropped legs {m:+,.0f} $/mo, 95% CI [{lo:+,.0f}, {hi:+,.0f}]")
    P("")

    # F. minutes since cross / causal features
    cross_info(r4)
    xs = [x for x in r4 if x.get("since_cross") is not None]
    P(f"## F. Minutes since the name first hit the scanner grid (R4, n={len(xs)})\n")
    P(HDR)
    for a, b, lab in ((-1, 1, "crossed at/before open (gi=0) & entry<10:00"),):
        pass
    for lab, fn in (("since<=10", lambda x: x["since_cross"] <= 10),
                    ("10<since<=30", lambda x: 10 < x["since_cross"] <= 30),
                    ("30<since<=90", lambda x: 30 < x["since_cross"] <= 90),
                    ("since>90", lambda x: x["since_cross"] > 90),
                    ("on scanner at 9:30 (gapper)", lambda x: x["cross_at_open"]),
                    ("crossed intraday (after 9:30)", lambda x: not x["cross_at_open"])):
        P(fmt("R4 " + lab, stat([x for x in xs if fn(x)], ndays)))
        P(fmt("R4 #1 " + lab, stat([x for x in xs if x["ord"] == 1 and fn(x)], ndays)))
        P(fmt("R4 #2+ " + lab, stat([x for x in xs if x["ord"] >= 2 and fn(x)], ndays)))
    P("")
    P("## G. Causal feature means at decision, #1 vs #2+ (R4)\n")
    for lab, fn in (("#1", lambda x: x["ord"] == 1), ("#2+", lambda x: x["ord"] >= 2)):
        ys = [x for x in xs if fn(x)]
        P(f"- {lab}: gain_now med {np.nanmedian([x['gain_now'] for x in ys]):.3f}, coil med {np.nanmedian([x['coil'] for x in ys]):.3f}, "
          f"n_elig med {np.median([x['n_elig'] for x in ys]):.0f}, gap_open med {np.nanmedian([x['gap_open'] for x in ys]):.3f}, "
          f"since_cross med {np.median([x['since_cross'] for x in ys]):.0f}")
    P("")
    # #1 split by gain_now and n_elig terciles
    P("### #1 ticket split by causal features (R4)\n")
    P(HDR)
    one = [x for x in xs if x["ord"] == 1]
    for key in ("gain_now", "n_elig", "since_cross", "gap_open"):
        v = np.array([x[key] for x in one], float)
        q = np.nanpercentile(v, [33.3, 66.7])
        for lab, fn in (("lo", lambda t: t <= q[0]), ("mid", lambda t: q[0] < t <= q[1]), ("hi", lambda t: t > q[1])):
            P(fmt(f"#1 {key} {lab} ({q[0]:.2f}/{q[1]:.2f})", stat([x for x in one if fn(x[key])], ndays)))
    P("")
    # 2+ by entry hour for R4 vs RND -> isolates selection vs time
    print("\n".join(out))
    Path(r"C:/Users/MYPC~1/AppData/Local/Temp/claude/C--cornell-stocks-automation/20a29bc8-aa0d-497e-a600-4db3499b8240/scratchpad/lm5_out.md").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
