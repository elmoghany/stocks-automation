"""LEGACY-5 part 2: minutes-since-cross vs random control, robustness,
R5 replication (R5 starts at 10:00 -> separates ordinal from clock).
Reads saved dumps + cp_feat cache only; shadow-rule evaluation."""
import json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(r"C:\cornell\stocks-automation\day-trading")
sys.path.insert(0, str(ROOT / "plan"))
import cp_feat as F  # noqa: E402
from lm5_seq import annotate, stat, fmt, HDR, months_pos, halves, bydate  # noqa: E402

M10 = 360
SCR = Path(r"C:/Users/MYPC~1/AppData/Local/Temp/claude/C--cornell-stocks-automation/20a29bc8-aa0d-497e-a600-4db3499b8240/scratchpad")


def attach(all_ann):
    by = defaultdict(list)
    for x in all_ann:
        by[x["date"]].append(x)
    for dt, xs in by.items():
        z = F.load(dt)
        if z is None:
            continue
        syms = {s: i for i, s in enumerate(z["syms"])}
        grid, el = z["grid"], z["elig_last"]
        first = np.where(el.any(axis=1), el.argmax(axis=1), -1)
        for x in xs:
            i = syms.get(x["sym"])
            if i is None or first[i] < 0:
                continue
            x["since"] = int(x["entry_min"] - grid[first[i]])
            x["at_open"] = bool(first[i] == 0)
            gi = int(np.searchsorted(grid, x["entry_min"] - 1, side="right") - 1)
            x["gain_now"] = float(z["gain_now"][i, max(gi, 0)])


def robust(xs, c=15, B=2000, seed=3):
    p = np.array([x["p"] for x in xs])
    if len(p) < 5:
        return "n<5"
    s = np.sort(p)
    rng = np.random.default_rng(seed)
    bs = [p[rng.integers(0, len(p), len(p))].mean() for _ in range(B)]
    return (f"median {np.median(p):+.0f}, ex-top-5 mean {s[:-5].mean():+.0f}, "
            f"ex-top-1% {s[:int(len(s)*0.99)].mean():+.0f}, boot95 gross [{np.percentile(bs,2.5):+.0f}, {np.percentile(bs,97.5):+.0f}]")


def block(name, legs, ndays, dates, P):
    main = annotate(legs[name])
    rnd = {k: annotate(v) for k, v in legs.items() if k.startswith("RND")}
    ns = len(rnd)
    rall = [x for v in rnd.values() for x in v]
    attach(main + rall)
    P(f"### {name}: {len(main)} legs, {ns} random seeds\n")
    P(HDR)
    for o, fn in (("#1", lambda x: x["ord"] == 1), ("#2", lambda x: x["ord"] == 2),
                  ("#3+", lambda x: x["ord"] >= 3)):
        P(fmt(f"{name} {o}", stat([x for x in main if fn(x)], ndays)))
        P(fmt(f"RND {o}", stat([x for x in rall if fn(x)], ndays * ns)))
    sb = (("since<=10", lambda x: x["since"] <= 10), ("10<since<=30", lambda x: 10 < x["since"] <= 30),
          ("30<since<=90", lambda x: 30 < x["since"] <= 90), ("since>90", lambda x: x["since"] > 90))
    for lab, fn in sb:
        P(fmt(f"{name} {lab}", stat([x for x in main if "since" in x and fn(x)], ndays)))
        P(fmt(f"RND {lab}", stat([x for x in rall if "since" in x and fn(x)], ndays * ns)))
    for lab, fn in (("#1 on scanner at 9:30", lambda x: x["ord"] == 1 and x.get("at_open")),
                    ("#1 crossed after 9:30", lambda x: x["ord"] == 1 and x.get("at_open") is False)):
        P(fmt(f"{name} {lab}", stat([x for x in main if fn(x)], ndays)))
        P(fmt(f"RND {lab}", stat([x for x in rall if fn(x)], ndays * ns)))
    P("")
    P("Robustness (gross $/10k):")
    for lab, fn in (("#1", lambda x: x["ord"] == 1), ("#2+", lambda x: x["ord"] >= 2),
                    ("since<=10", lambda x: x.get("since", -1) <= 10 and "since" in x),
                    ("since>10", lambda x: x.get("since", -1) > 10)):
        P(f"- {name} {lab}: {robust([x for x in main if fn(x)])}")
    P("")
    # shadow rules
    rules = {
        "ALL": lambda x: True,
        "skip #1": lambda x: x["ord"] >= 2,
        "skip since<=10": lambda x: x.get("since", 0) > 10,
        "skip #1 if on scanner at 9:30": lambda x: not (x["ord"] == 1 and x.get("at_open")),
        "skip since<=10 AND #1-at-open": lambda x: x.get("since", 0) > 10,
    }
    rules["#1 only if crossed after 9:30; later only since>10"] = (
        lambda x: (x["ord"] == 1 and x.get("at_open") is False) or (x["ord"] >= 2 and x.get("since", 0) > 10))
    P("| shadow rule | n | gross $/10k | net@15 $/10k | net@6 | gross $/mo | net@15 $/mo | months+ | H1/H2 net@15 | RND net@15 $/mo (mean) | RND seeds improved vs ALL |")
    P("|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|")
    rbase = {k: stat(v, ndays)["mo"] for k, v in rnd.items()}
    for rn, fn in rules.items():
        xs = [x for x in main if fn(x)]
        s = stat(xs, ndays)
        mp = months_pos(xs)
        h = halves(xs, dates)
        rm = []
        imp = 0
        for k, v in rnd.items():
            ys = [x for x in v if fn(x)]
            m = stat(ys, ndays).get("mo", 0.0)
            rm.append(m)
            imp += m > rbase[k]
        P(f"| {rn} | {s['n']} | {s['g']:+.1f} | {s['net']:+.1f} | {s['g']-12:+.1f} | {s['gmo']:+,.0f} | {s['mo']:+,.0f} "
          f"| {mp[0]}/{mp[1]} | {h[0]:+.0f} / {h[1]:+.0f} | {np.mean(rm):+,.0f} | {imp}/{len(rm)} |")
    P("")
    # selection edge vs random within the same since bucket and ordinal
    return main


def main():
    out = []
    P = out.append
    d = json.loads((ROOT / "plan/pa_out/cp_r4_legs.json").read_text())
    P("## R4 (coil rank, no stop, 09:35 start)\n")
    r4 = block("R4", d["legs"], d["ndays"], d["dates"], P)
    # within R4 #2+: since bucket by entry time, to separate clock vs since
    P("R4 #2+ by entry clock x since:\n")
    P(HDR)
    for a, b, lab in ((330, 360, "<10:00"), (360, 420, "10-11"), (420, 660, ">=11")):
        for sl, fn in (("since<=10", lambda x: x["since"] <= 10), ("since>10", lambda x: x["since"] > 10)):
            P(fmt(f"#2+ {lab} {sl}", stat([x for x in r4 if x["ord"] >= 2 and a <= x["entry_min"] < b and "since" in x and fn(x)], d["ndays"])))
    P("")
    # gain_now at entry for since<=10 vs >10 (is 'fresh' == 'extended'?)
    for sl, fn in (("since<=10", lambda x: x["since"] <= 10), ("since>10", lambda x: x["since"] > 10)):
        ys = [x for x in r4 if "since" in x and fn(x)]
        P(f"- R4 {sl}: median gain_now {np.median([x['gain_now'] for x in ys]):.3f}, median hold {np.median([x['hold'] for x in ys]):.0f} min, "
          f"share at_open {np.mean([x['at_open'] for x in ys]):.2f}")
    P("")
    d5 = json.loads((ROOT / "plan/crs_cp_r5_legs.json").read_text())
    P("## R5 (coil, start 10:00, stop -2%) -- clock-controlled replication\n")
    block("R5", d5["legs"], d5["ndays"], d5["dates"], P)
    txt = "\n".join(out)
    print(txt)
    (SCR / "lm5_out2.md").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
