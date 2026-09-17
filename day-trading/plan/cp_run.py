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


def dates():
    return F.dates()


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
    ds = ds or dates()[:80]
    print("### hold-is-zero (enter and exit in the same minute, no cost)")
    cfg = S.default_cfg(stop_pct=None, trail_pct=None, bearish_exit=False,
                        time_stop=0)
    legs = S.run(ds[:25], cfg, cost=None)
    same = [x for x in legs if x["exit_min"] == x["entry_min"]]
    bad = [x for x in same if abs(x["gross"]) > 1e-9]
    print(f"  {len(legs)} legs, {len(same)} same-minute, "
          f"{len(bad)} with non-zero gross")

    print("### poison: corrupt every bar strictly after the FILL bar")
    T = L.mgrid(10, 0)
    base = S.default_cfg(t_start=T, cutoff=T + 1, ntickets=1)
    ref, got_all = {}, {}
    for d in ds[:60]:
        Fd, day = F.load(d), L.load_day(d)
        if Fd is None or day is None:
            continue
        ref[d] = [(lg["sym"], lg["entry_min"], round(lg["entry"], 6))
                  for lg in S.run_day(day, Fd, base, None)]
    rng = np.random.default_rng(1)
    for d in ref:
        Fd, day = F.load(d), L.load_day(d)
        for a in ("o", "h", "l", "c"):
            arr = getattr(day, a)
            arr[:, T + 2:] = arr[:, T + 2:] * (
                1 + rng.normal(0, 5.0, arr[:, T + 2:].shape))
        day._ffill = day._runhi = day._cumv = None
        day._cumdv = day._cumsv = day._cumn = None
        day._orb = None
        got_all[d] = [(lg["sym"], lg["entry_min"], round(lg["entry"], 6))
                      for lg in S.run_day(day, Fd, base, None)]
    nchk = sum(len(v) for v in ref.values())
    moved = sum(1 for d in ref if got_all[d] != ref[d])
    print(f"  {nchk} picks over {len(ref)} days; days whose pick or entry "
          f"price moved: {moved}")

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
    ds = dates()
    overs = {"CHAMP": {}, "INV": dict(invert=True)}
    for k in range(nseed):
        overs[f"R{k}"] = dict(rank="none", rand=True, seed=k)
    res = run_batch(ds, overs)
    s = res["CHAMP"]
    print(f"\n## Controls ({len(ds)} sessions, {nseed} random seeds)\n")
    print(HEAD)
    print(_fmt("CHAMPION-MIMIC", s))
    print(_fmt("CONTROL inverted champion key", res["INV"]))
    tots = np.array([res[f"R{k}"]["total_flat"] for k in range(nseed)])
    pts = np.array([res[f"R{k}"]["flat_tkt"] for k in range(nseed)])
    exb = np.array([res[f"R{k}"]["ex_best"] for k in range(nseed)])
    print(f"| CONTROL random pick, {nseed} seeds (mean) | | | | "
          f"{pts.mean():+.2f} +- {pts.std(ddof=1):.2f} | | "
          f"{tots.mean()/max(s['months'],1):+,.0f} | | "
          f"{exb.mean():+,.0f} |")
    print(f"\n- percentile of the champion-mimic against the random "
          f"control, total: **{(tots < s['total_flat']).mean()*100:.1f}th**; "
          f"ex-best: **{(exb < s['ex_best']).mean()*100:.1f}th**")
    print(f"- edge over random: **{s['flat_tkt']-pts.mean():+.2f}/ticket** "
          f"(z = {(s['flat_tkt']-pts.mean())/max(pts.std(ddof=1),1e-9):+.2f})")
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


def main():
    a = sys.argv[1:]
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
    if not a:
        print(__doc__)


if __name__ == "__main__":
    main()
