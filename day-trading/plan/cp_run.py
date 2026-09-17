"""CHAMPION-REPLAY parts 2-5: the champion's components, re-measured on
the causal live-scannable universe, with controls.

    python plan/cp_run.py --selftest    gates: hold-is-zero, poison,
                                        foresight ladder, cost monotone
    python plan/cp_run.py --universe    part 3: what the causal universe
                                        looks like against the pool file
    python plan/cp_run.py --ablate      part 4: component ablation
    python plan/cp_run.py --controls    30-seed random + inverted
    python plan/cp_run.py --model       part 2: the detector's picks,
                                        traded (needs cp_detect's scores)
    python plan/cp_run.py --halal       part 5: post-hoc halal
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402
import cp_sim as S                                          # noqa: E402
import cp_cost as C                                         # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/massive/cp"

HEAD = ("| config | tickets | tkt/day | gross $/tkt | flat10 $/tkt | "
        "measured $/tkt | $/month (flat10) | months + | ex-best |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|")


# The aug-2026 block (2026-08-03 .. 2026-09-01) lies entirely after the
# last in-sample session, so one date cut separates in-sample from
# out-of-sample. Nothing is fitted in this file, but the mandate asks
# for an aug-2026 sign check on every line, and a config chosen by
# looking at the 444-session table has been chosen with that table.
OOS_FROM = "2026-08-01"


def dates(oos=False):
    return [d for d in F.dates() if (d >= OOS_FROM) == oos]


def _fmt(name, s):
    if not s.get("n"):
        return f"| {name} | 0 | | | | | | | |"
    return (f"| {name} | {s['n']} | {s['tkts_per_day']:.2f} | "
            f"{s['gross_tkt']:+.2f} | {s['flat_tkt']:+.2f} | "
            f"{s['meas_tkt']:+.2f} | "
            f"{s['total_flat']/max(s['months'],1):+,.0f} | "
            f"{s['months_pos']}/{s['months']} | {s['ex_best']:+,.0f} |")


def run_batch(ds, overs, progress=True):
    """{name: cfg-overrides} -> {name: summary}, one pass over the tape.

    Every job sees the SAME panel objects, so no config can influence
    another; the only thing that differs is the config dict."""
    jobs, costs = {}, {}
    for k, over in overs.items():
        over = dict(over)
        sc = over.pop("_scores", None)
        cst = C.TapeCost()
        costs[k] = cst

        def f(day, i, m, px, sh, _c=cst):
            return _c.dollars(day, i, m, px, sh)
        jobs[k] = (S.default_cfg(**over), f, sc)
    legs = S.run_many(ds, jobs, progress=progress)
    out = {}
    for k in overs:
        s = S.summarize(legs[k], len(ds))
        s["cost_report"] = costs[k].report()
        s["_legs"] = legs[k]
        out[k] = s
    return out


def _strip(res):
    return {k: {kk: vv for kk, vv in v.items() if kk != "_legs"}
            for k, v in res.items()}


# ---------------------------------------------------------------------
# gates
# ---------------------------------------------------------------------
def selftest(ds=None):
    """The gates. Each one is a statement about the ENGINE, not a result.

    1. FILL CONVENTION -- every leg fills strictly AFTER its decision
       minute, at the OPEN of a bar that actually printed, and every
       sell price lies inside that bar's [Low, High].
    2. ACCOUNTING -- reported gross equals (exit - entry) x shares to
       the cent, and the flat toll equals 10 bps of both notionals.
    3. POISON (the causality gate) -- corrupt every bar STRICTLY AFTER a
       decision minute and recompute the whole feature block at that
       minute. A single changed value would mean a feature reads the
       future. NOTE the earlier form of this test also poisoned the FILL
       bar, which legitimately moves the entry price (the fill happens
       after the decision by construction), so it was testing the wrong
       thing; this form tests the decision layer, which is the layer
       that has to be causal.
    4. FORESIGHT LADDER + ANTI-FORESIGHT MIRROR.
    5. COST MONOTONE in the square-root-impact coefficient."""
    ds = ds or dates()[:80]

    print("### fill convention + accounting")
    legs = S.run(ds[:60], S.default_cfg(), cost=None)
    bad_fill = bad_acc = bad_bar = 0
    for d in {x["date"] for x in legs}:
        day = L.load_day(d)
        idx = {s: i for i, s in enumerate(day.syms)}
        for x in [z for z in legs if z["date"] == d]:
            i = idx[x["sym"]]
            if not day.printed[i, x["entry_min"]]:
                bad_bar += 1
            elif abs(float(day.o[i, x["entry_min"]]) - x["entry"]) > 1e-6:
                bad_fill += 1
            lo = float(day.l[i, x["exit_min"]])
            hi = float(day.h[i, x["exit_min"]])
            if not (lo - 1e-6 <= x["exit"] <= hi + 1e-6):
                bad_bar += 1
            g = (x["exit"] - x["entry"]) * x["shares"]
            if abs(g - x["gross"]) > 1e-6:
                bad_acc += 1
            t = (x["entry"] + x["exit"]) * x["shares"] * 10.0 / 1e4
            if abs((x["gross"] - t) - x["net_flat"]) > 1e-6:
                bad_acc += 1
    print(f"  {len(legs)} legs: entry not at the fill bar's open "
          f"{bad_fill}, price outside the bar {bad_bar}, "
          f"accounting mismatches {bad_acc}")

    print("### poison: corrupt every bar AFTER the decision minute and "
          "recompute the feature block")
    keys = ("gain_now", "coil", "hi_gain", "pm_dvol", "pm_high_gain",
            "gap_open", "dvol_now", "bars_now", "vwap_dist", "pressure30",
            "pressure10", "orb_dist", "dens", "sigma1")
    rng = np.random.default_rng(1)
    nchk = moved = 0
    for d in ds[:40]:
        day = L.load_day(d)
        if day is None:
            continue
        for T in (L.mgrid(9, 35), L.mgrid(11, 0), L.mgrid(13, 30)):
            ref = day.features(T)
            elig0 = day.crossed_by(T, "LAST")
            day2 = L.load_day(d)
            for a in ("o", "h", "l", "c", "v"):
                arr = getattr(day2, a)
                arr[:, T + 1:] = np.abs(arr[:, T + 1:] * (
                    1 + rng.normal(0, 5.0, arr[:, T + 1:].shape))) + 1.0
            got = day2.features(T)
            elig1 = day2.crossed_by(T, "LAST")
            if not np.array_equal(elig0, elig1):
                moved += 1
            for k in keys:
                x, y = np.asarray(ref[k], float), np.asarray(got[k], float)
                nchk += x.size
                if not np.allclose(x, y, rtol=1e-9, atol=1e-9,
                                   equal_nan=True):
                    moved += 1
    print(f"  {nchk} feature values over {len(ds[:40])} days x 3 decision "
          f"minutes; values or eligibility masks that moved: {moved}")

    print("### foresight ladder (60-minute forward return as the rank)")
    sc_f, sc_a = {}, {}
    for d in ds:
        Fd, day = F.load(d), L.load_day(d)
        if Fd is None or day is None:
            continue
        G = Fd["grid"]
        b = day.last[:, G]
        fwd = np.full(b.shape, np.nan)
        for gi, m in enumerate(G):
            fwd[:, gi] = day.last[:, min(m + 60, L.M_1500)] / b[:, gi] - 1.0
        sc_f[d] = np.nan_to_num(fwd, nan=-9.9)
        sc_a[d] = -sc_f[d]
    res = run_batch(ds, {"foresight": dict(rank="model", _scores=sc_f),
                         "anti-foresight": dict(rank="model", _scores=sc_a),
                         "champion-mimic": {}}, progress=False)
    print(HEAD)
    for k in ("foresight", "anti-foresight", "champion-mimic"):
        print(_fmt(k, res[k]))

    print("### cost monotone in the impact coefficient")
    for coef in (0.0, 0.3, 1.0, 2.0):
        cst = C.TapeCost(coef=coef)

        def f(day, i, m, px, sh, _c=cst):
            return _c.dollars(day, i, m, px, sh)
        legs = S.run(ds, S.default_cfg(), cost=f)
        s = S.summarize(legs, len(ds))
        r = cst.report()
        print(f"  Y={coef:.1f}: measured {s['meas_tkt']:+9.2f}/tkt, "
              f"median {r.get('median', 0):.1f} bps/side")


# ---------------------------------------------------------------------
# part 3: the universe
# ---------------------------------------------------------------------
def universe():
    ds = dates()
    pool, poolall = {}, {}
    for lab in ("year", "y2025"):
        f = ROOT / f"data/massive/gappers_novol_{lab}.json"
        if f.exists():
            for r in json.loads(f.read_text()):
                poolall.setdefault(r["date"], set()).add(r["symbol"])
                if r.get("hist_n", 99) >= 50:
                    pool.setdefault(r["date"], set()).add(r["symbol"])
    times = [(9, 35), (10, 0), (11, 0), (12, 0), (14, 0), (15, 0)]
    rows = {t: [] for t in times}
    rowsH = {t: [] for t in times}
    poolsz, poolsz50, crossers, panel_n = [], [], [], []
    for d in ds:
        Fd = F.load(d)
        if Fd is None:
            continue
        gp = {m: i for i, m in enumerate(Fd["grid"])}
        for t in times:
            gi = gp[L.mgrid(*t)]
            rows[t].append(int(Fd["elig_last"][:, gi].sum()))
            rowsH[t].append(int(Fd["elig_high"][:, gi].sum()))
        poolsz.append(len(poolall.get(d, ())))
        poolsz50.append(len(pool.get(d, ())))
        crossers.append(int(Fd["elig_last"][:, -1].sum()))
        panel_n.append(len(Fd["syms"]))
    print(f"\n## The causal live-scannable universe ({len(ds)} sessions)\n")
    print("| as of | on the scanner, LAST rule (Robinhood's own) | "
          "HIGH rule (rotation_sim's RS_CROSS) |")
    print("|---|---:|---:|")
    for t in times:
        print(f"| {t[0]:02d}:{t[1]:02d} | {np.mean(rows[t]):.1f} | "
              f"{np.mean(rowsH[t]):.1f} |")
    print(f"\n- grouped-daily pool records per day: "
          f"**{np.mean(poolsz):.1f}** (of which "
          f"{np.mean(poolsz50):.1f} have `hist_n >= 50`, the only ones the "
          f"2026-08-21 backfill fetched)")
    print(f"- symbol-days with bars in this line's panel: "
          f"**{np.mean(panel_n):.1f}/day**")
    print(f"- names that appear on the LIVE scanner at some point in the "
          f"regular session: **{np.mean(crossers):.1f}/day** "
          f"({np.mean(crossers)/max(np.mean(poolsz), 1)*100:.0f}% of the "
          f"pool file; the remainder touch +10% only on a WICK, so the "
          f"HIGH rule sees them and the LAST rule does not)")


# ---------------------------------------------------------------------
# part 4: ablation
# ---------------------------------------------------------------------
ABL = [
    ("CHAMPION-MIMIC (coil/pressure, stop+trail+bearish, rotation)", {}),
    ("-- ranking", None),
    ("rank: least-extended crosser (gain_asc)", dict(rank="gain_asc")),
    ("rank: coil only", dict(rank="coil")),
    ("rank: pressure only", dict(rank="pressure")),
    ("rank: furthest below VWAP", dict(rank="vwap_lo")),
    ("rank: highest relative volume", dict(rank="rvol_hi")),
    ("rank: none (first eligible)", dict(rank="none")),
    ("CONTROL rank INVERTED (champion key flipped)", dict(invert=True)),
    ("-- entry trigger", None),
    ("trigger: opening-range break", dict(trigger="orb")),
    ("trigger: premarket-high break", dict(trigger="pmh")),
    ("-- exits", None),
    ("no bearish-pattern exit", dict(bearish_exit=False)),
    ("no trail", dict(trail_pct=None)),
    ("no -8% stop", dict(stop_pct=None)),
    ("flatten at 15:00 only (no exits at all)",
     dict(stop_pct=None, trail_pct=None, bearish_exit=False)),
    ("fixed 20% trail, no pressure modulation",
     dict(trail_lo=0.20, trail_hi=0.20)),
    ("time stop at 30 minutes", dict(time_stop=30)),
    ("time stop at 60 minutes", dict(time_stop=60)),
    ("stop at -4% instead of -8%", dict(stop_pct=0.04)),
    ("stop at -2%", dict(stop_pct=0.02)),
    ("stop at -12%", dict(stop_pct=0.12)),
    ("tighter trail (10% base)", dict(trail_pct=0.10)),
    ("-- structure", None),
    ("no rotation (ticket returns to the same name)", dict(rotate=False)),
    ("entry window closes 12:00", dict(cutoff=L.mgrid(12, 0))),
    ("entry window opens 10:00", dict(t_start=L.mgrid(10, 0))),
    ("HIGH-rule universe (rotation_sim's RS_CROSS)", dict(universe="HIGH")),
    ("one ticket a day", dict(ntickets=1)),
]


def ablate():
    ds = dates()
    overs = {n: dict(o) for n, o in ABL if o is not None}
    res = run_batch(ds, overs)
    print(f"\n## Component ablation on the causal universe "
          f"({len(ds)} sessions)\n")
    print(HEAD)
    for n, o in ABL:
        if o is None:
            print(f"| **{n[3:]}** | | | | | | | | |")
        else:
            print(_fmt(n, res[n]))
    (OUT / "ablate.json").write_text(json.dumps(_strip(res), indent=1,
                                                default=float))


def controls(nseed=30):
    """The two rows the ablation actually pointed at, each against a
    30-seed random control IN ITS OWN FRAME.

    A random control only means something if the only thing randomised
    is the PICK: same entry window, same stop, same trail, same exits,
    same ticket schedule. R5's control (in --recomb) was run this way
    and R5 failed it; these are the two rows that did not."""
    ds = dates()
    FRAMES = {
        "R1 coil rank only": (dict(rank="coil"), dict(rank="none",
                                                      rand=True)),
        "R4 coil + no stop": (dict(rank="coil", stop_pct=None),
                              dict(rank="none", rand=True, stop_pct=None)),
        "CHAMPION-MIMIC": ({}, dict(rank="none", rand=True)),
    }
    overs = {}
    for name, (cfg, rctl) in FRAMES.items():
        overs[name] = dict(cfg)
        overs[f"{name} | INVERTED"] = dict(cfg, invert=True)
        for k in range(nseed):
            overs[f"{name} | RND{k}"] = dict(rctl, seed=k)
    res = run_batch(ds, overs)
    print("\n## Controls: %d random seeds in each row's own frame "
          "(%d sessions)\n" % (nseed, len(ds)))
    print(HEAD)
    lines = []
    for name in FRAMES:
        print(_fmt(name, res[name]))
        print(_fmt(f"{name} -- CONTROL inverted", res[f"{name} | INVERTED"]))
        tots = np.array([res[f"{name} | RND{k}"]["total_flat"]
                         for k in range(nseed)])
        pts = np.array([res[f"{name} | RND{k}"]["flat_tkt"]
                        for k in range(nseed)])
        exb = np.array([res[f"{name} | RND{k}"]["ex_best"]
                        for k in range(nseed)])
        mo = max(res[name]["months"], 1)
        print(f"| {name} -- CONTROL random, {nseed} seeds (mean) | | | | "
              f"{pts.mean():+.2f} +- {pts.std(ddof=1):.2f} | | "
              f"{tots.mean()/mo:+,.0f} | | {exb.mean():+,.0f} |")
        lines.append((name,
                      float((tots < res[name]["total_flat"]).mean() * 100),
                      float((exb < res[name]["ex_best"]).mean() * 100),
                      res[name]["flat_tkt"] - pts.mean(),
                      (res[name]["flat_tkt"] - pts.mean())
                      / max(pts.std(ddof=1), 1e-9)))
    print("\n| row | percentile, total | percentile, ex-best | "
          "edge over random $/tkt | z |")
    print("|---|---:|---:|---:|---:|")
    for n, pt, pe, ed, z in lines:
        print(f"| {n} | {pt:.1f}th | {pe:.1f}th | {ed:+.2f} | {z:+.2f} |")
    (OUT / "controls.json").write_text(json.dumps(_strip(res), indent=1,
                                                  default=float))


# ---------------------------------------------------------------------
# part 2: the detector's picks, traded
# ---------------------------------------------------------------------
def model_scores(path=None):
    """cp_detect's walk-forward scores as per-date (name x grid) arrays.

    A score exists only at the decision minutes the model scored; every
    other grid column is -inf, so the engine can never trade off a
    minute the model never saw."""
    import cp_scan
    z = np.load(path or (OUT / "scores.npz"), allow_pickle=False)
    sc, date, sym, tt = z["score"], z["date"], z["sym"], z["tt"]
    names = [str(x) for x in cp_scan.load()["dates"]]
    per = {}
    for k in range(len(sc)):
        per.setdefault(int(date[k]), []).append(
            (str(sym[k]), int(tt[k]), float(sc[k])))
    out = {}
    for di, rws in per.items():
        d = names[di]
        Fd = F.load(d)
        if Fd is None:
            continue
        gp = {m: i for i, m in enumerate(Fd["grid"])}
        si = {str(s): i for i, s in enumerate(Fd["syms"])}
        g = np.full((len(Fd["syms"]), len(Fd["grid"])), -np.inf)
        for s, t, v in rws:
            i = si.get(s)
            m = gp.get(L.mgrid(t // 100, t % 100))
            if i is not None and m is not None and np.isfinite(v):
                g[i, m] = v
        out[d] = g
    return out


def oracle_scores(kind="gain_full"):
    """CONTROL, NOT A STRATEGY: rank by a fact only the close knows.

    `gain_full` is the pool record's full-day gain, i.e. the single
    binary-ish fact the whole of Part 2 is trying to predict. Ranking on
    it measures the CEILING of 'detect the champion's kind of day' --
    what the champion's own machinery would earn if the detector were
    perfect. Nothing that uses this is reported as an honest result."""
    out = {}
    for d in dates():
        Fd = F.load(d)
        if Fd is None:
            continue
        v = np.asarray(Fd[kind], float)
        out[d] = np.repeat(np.nan_to_num(v, nan=-9.9)[:, None],
                           len(Fd["grid"]), axis=1)
    return out


def model():
    sc = model_scores()
    ds = [d for d in dates() if d in sc]
    slot = dict(t_start=L.mgrid(9, 35), cutoff=L.mgrid(10, 5))
    overs = {
        "model pick 09:35, champion exits":
            dict(rank="model", _scores=sc, **slot),
        "model pick 09:35, flatten 15:00":
            dict(rank="model", _scores=sc, stop_pct=None, trail_pct=None,
                 bearish_exit=False, **slot),
        "CONTROL same slot, random pick, champion exits":
            dict(rank="none", rand=True, seed=11, **slot),
        "CONTROL same slot, champion ranking":
            dict(**slot),
        "model, full day (rotation to 14:30)":
            dict(rank="model", _scores=sc),
        "CEILING (not a strategy): perfect day-type oracle, full day":
            dict(rank="model", _scores=oracle_scores()),
        "CEILING: perfect day-type oracle, 09:35 slot only":
            dict(rank="model", _scores=oracle_scores(), **slot),
    }
    res = run_batch(ds, overs)
    print(f"\n## The detector's picks, traded ({len(ds)} scored sessions)\n")
    print(HEAD)
    for n in overs:
        print(_fmt(n, res[n]))
    (OUT / "model.json").write_text(json.dumps(_strip(res), indent=1,
                                               default=float))


# ---------------------------------------------------------------------
# part 5: post-hoc halal
# ---------------------------------------------------------------------
def halal():
    hal = L.halal_set()
    new = L.halal_set("NEW")
    ds = dates()
    overs = {"no screen (this line's mandate)": {},
             "halal_list.json applied at decision time": dict(halal=hal),
             "halal_list.NEW.json applied": dict(halal=new)}
    res = run_batch(ds, overs)
    print(f"\n## Post-hoc halal ({len(hal)} PASS names in "
          f"halal_list.json, {len(new)} in halal_list.NEW.json)\n")
    print(HEAD)
    for n in overs:
        print(_fmt(n, res[n]))
    legs = res["no screen (this line's mandate)"]["_legs"]
    keep = [x for x in legs if x["sym"] in hal]
    kn = [x["net_flat"] for x in keep] or [0.0]
    print(f"\n- of {len(legs)} legs taken with no screen, "
          f"**{len(keep)} ({len(keep)/max(len(legs),1)*100:.1f}%)** are on a "
          f"halal-PASS name; those legs are worth "
          f"**{sum(kn):+,.0f}** at flat 10 bps "
          f"(**{np.mean(kn):+.2f}/ticket**) against "
          f"**{sum(x['net_flat'] for x in legs):+,.0f}** for the whole book.")
    (OUT / "halal.json").write_text(json.dumps(_strip(res), indent=1,
                                               default=float))


RECOMB = {
    "CHAMPION-MIMIC (reference)": {},
    "R1 coil rank only": dict(rank="coil"),
    "R2 coil + start 10:00": dict(rank="coil", t_start=L.mgrid(10, 0)),
    "R3 coil + stop -2%": dict(rank="coil", stop_pct=0.02),
    "R4 coil + no stop": dict(rank="coil", stop_pct=None),
    "R5 coil + start 10:00 + stop -2%":
        dict(rank="coil", t_start=L.mgrid(10, 0), stop_pct=0.02),
    "R6 coil + start 10:00 + no stop":
        dict(rank="coil", t_start=L.mgrid(10, 0), stop_pct=None),
    "R7 R5 + tighter trail (10%)":
        dict(rank="coil", t_start=L.mgrid(10, 0), stop_pct=0.02,
             trail_pct=0.10),
    "R8 R5 without the bearish exit":
        dict(rank="coil", t_start=L.mgrid(10, 0), stop_pct=0.02,
             bearish_exit=False),
    "CONTROL R5 with the coil rank INVERTED":
        dict(rank="coil", t_start=L.mgrid(10, 0), stop_pct=0.02,
             invert=True),
    "CONTROL R5 with a random pick":
        dict(rank="none", rand=True, seed=17, t_start=L.mgrid(10, 0),
             stop_pct=0.02),
}


def recomb(nseed=30):
    """The best causal recombination the ablation points at, with the
    controls that decide whether it is a finding or a search artefact.

    This IS an in-sample maximum over the ablation grid and is labelled
    as one; the 30-seed random control, the inverted mirror and the
    aug-2026 block are what make it readable."""
    ds = dates()
    overs = dict(RECOMB)
    best = dict(rank="coil", t_start=L.mgrid(10, 0), stop_pct=0.02)
    for k in range(nseed):
        overs[f"RND{k}"] = dict(best, rank="none", rand=True, seed=k)
    res = run_batch(ds, overs)
    print(f"\n## Best causal recombination ({len(ds)} sessions)\n")
    print(HEAD)
    for n in RECOMB:
        print(_fmt(n, res[n]))
    tots = np.array([res[f"RND{k}"]["total_flat"] for k in range(nseed)])
    pts = np.array([res[f"RND{k}"]["flat_tkt"] for k in range(nseed)])
    exb = np.array([res[f"RND{k}"]["ex_best"] for k in range(nseed)])
    r5 = res["R5 coil + start 10:00 + stop -2%"]
    print(f"| CONTROL random pick in R5's frame, {nseed} seeds (mean) | | | | "
          f"{pts.mean():+.2f} +- {pts.std(ddof=1):.2f} | | "
          f"{tots.mean()/max(r5['months'],1):+,.0f} | | {exb.mean():+,.0f} |")
    print(f"\n- R5 percentile vs the 30-seed control: total "
          f"**{(tots < r5['total_flat']).mean()*100:.1f}th**, ex-best "
          f"**{(exb < r5['ex_best']).mean()*100:.1f}th**")
    print(f"- R5 edge over random: **{r5['flat_tkt']-pts.mean():+.2f}"
          f"/ticket** (z = "
          f"{(r5['flat_tkt']-pts.mean())/max(pts.std(ddof=1),1e-9):+.2f})")
    (OUT / "recomb.json").write_text(json.dumps(_strip(res), indent=1,
                                                default=float))


def oos():
    ds = dates(oos=True)
    overs = {"CHAMPION-MIMIC": {},
             "R1 coil rank only": dict(rank="coil"),
             "R5 coil + start 10:00 + stop -2%":
                 dict(rank="coil", t_start=L.mgrid(10, 0), stop_pct=0.02),
             "CONTROL R5 inverted":
                 dict(rank="coil", t_start=L.mgrid(10, 0), stop_pct=0.02,
                      invert=True),
             "CONTROL random pick": dict(rank="none", rand=True, seed=3)}
    res = run_batch(ds, overs)
    print(f"\n## Out of sample: aug-2026 block ({len(ds)} sessions)\n")
    print(HEAD)
    for n in overs:
        print(_fmt(n, res[n]))
    (OUT / "oos.json").write_text(json.dumps(_strip(res), indent=1,
                                             default=float))


def main():
    a = sys.argv[1:]
    if "--oos" in a:
        oos()
    if "--selftest" in a:
        selftest()
    if "--universe" in a:
        universe()
    if "--ablate" in a:
        ablate()
    if "--controls" in a:
        controls()
    if "--model" in a:
        model()
    if "--halal" in a:
        halal()
    if "--recomb" in a:
        recomb()
    if not a:
        print(__doc__)


if __name__ == "__main__":
    main()
