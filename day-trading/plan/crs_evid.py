"""COST-RESCORE: price each config's OWN fills at PESSIMISM-AUDIT's
evidence-based per-side cost (pa_rescore.Evid: cr_cost measured half-spread
with no sqrt impact, floor 1 bps, + 4.4 bps impact before 10:30 else 3.1),
because a ranker can select names whose spread differs from the universe
mean (COST-REBASE 4.2). Rule fills only (the lookup runs ~13 fills/s); the
random control is read at a FLAT b equal to the rule's own mean EVID bps
(score() at that b, exact), so the percentile is approximate where the
control's fills are cheaper or dearer than the rule's.
Writes plan/crs_evid.json.   python plan/crs_evid.py [--only uq,rl2,...]"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import crs_rescore as C  # noqa: E402
PA = C.PA
OUTF = HERE / "crs_evid.json"


def hm(s):
    return int(s[11:13]) * 60 + int(s[14:16])


def finish(name, net, dates, d_all, bps_pairs, rand=None, extra=None):
    net = np.asarray(net, float)
    beff = round(float(np.mean([(a + b) / 2 for a, b in bps_pairs])), 2)
    d_all = sorted(d_all)
    s = C.summ(net, np.asarray(dates), len(d_all))
    s.update(PA.years(net, np.asarray(dates), d_all))
    mid = d_all[len(d_all) // 2]
    ds = np.asarray(dates)
    for nm_, k_ in (("half1", ds < mid), ("half2", ds >= mid)):
        nh = sum((d < mid) == (nm_ == "half1") for d in d_all)
        s[nm_] = {"per_ticket": round(float(net[k_].mean()), 2) if k_.any() else None,
                  "per_month": round(float(net[k_].sum()) / (nh / 21.0), 1)}
    s["evid_bps_mean"] = beff
    s["evid_bps_median"] = round(float(np.median([(a + b) / 2 for a, b in bps_pairs])), 2)
    s["evid_entry_mean"] = round(float(np.mean([a for a, _ in bps_pairs])), 2)
    s["evid_exit_mean"] = round(float(np.mean([b for _, b in bps_pairs])), 2)
    if rand:
        fl = C.score("x", (lambda b: net, dates), rand, d_all, "", b_list=[beff])["x"][C.lab(beff)]
        rt = []
        for fn, rds in rand:
            rt.append(float(np.sum(fn(beff))))
        s["random_per_ticket_at_flat_beff"] = fl["random_per_ticket"]
        s["pct_vs_random_at_flat_beff"] = C.pct(float(net.sum()), rt)
        s["pct_per_ticket_vs_random_at_flat_beff"] = fl["pct_per_ticket_vs_random"]
    if extra:
        s.update(extra)
    return {name: s}


def ev_uq():
    z = json.loads((HERE / "crs_uq_legs.json").read_text())
    L = z["legs"]
    ev = PA.Evid()
    net, pairs = [], []
    for x in L["MODEL"]:
        mi = 240 + int(x["fill_min"])            # uq minute grid starts 04:00
        mo = 240 + int(x["exit_min"])
        ce = 0.0 if x["passive"] else ev.side(x["sym"], x["date"], mi, x["N"])
        cx = ev.side(x["sym"], x["date"], mo, x["N"] * x["X"] / x["F"])
        ce += 50 * x["ext_in"]
        cx += 50 * x["ext_out"]
        net.append(x["N"] * (x["X"] / x["F"] * (1 - cx / 1e4) - (1 + ce / 1e4)))
        pairs.append((ce, cx))
    # control at the same flat EXIT cost (entries passive in both)
    rnd = []
    for k in range(30):
        lg = L[f"RND{k}"]
        N = np.array([x["N"] for x in lg]); F = np.array([x["F"] for x in lg]); X = np.array([x["X"] for x in lg])
        rnd.append((lambda b, N=N, F=F, X=X: N * (X / F * (1 - 2 * b / 1e4) - 1), [x["date"] for x in lg]))
    return finish("UNIVERSE-QUOTES rank-for-the-fill (limit, h30)", net,
                  [x["date"] for x in L["MODEL"]], z["dates"], pairs, rnd,
                  {"note": "entry passive = 0 bps; evid_bps_mean averages the 0 entry with the exit; "
                           "control priced at exit-only flat 2*beff"})


def ev_rl2():
    z = json.loads((HERE / "crs_rl2_legs.json").read_text())
    L = z["legs"]
    ev = PA.Evid()
    net, pairs = [], []
    for x in L["RULE"]:
        ce = ev.side(x["sym"], x["date"], 240 + x["m_in"], x["sh"] * x["px_in"]) + 50 * x["ext_in"]
        cx = ev.side(x["sym"], x["date"], 240 + x["m_out"], x["sh"] * x["px_out"]) + 50 * x["ext_out"]
        net.append(x["sh"] * x["px_out"] * (1 - cx / 1e4) - x["sh"] * x["px_in"] * (1 + ce / 1e4))
        pairs.append((ce, cx))
    rnd = []
    for k in range(30):
        lg = [dict(x, g=x["sh"] * (x["px_out"] - x["px_in"])) for x in L[f"RND{k}"]]
        rnd.append((C.flat_pricer(lg, "g", lambda x: x["sh"] * (x["px_in"] + x["px_out"]),
                                  lambda x: x["sh"] * (x["px_in"] * x["ext_in"] + x["px_out"] * x["ext_out"])),
                    [x["date"] for x in lg]))
    return finish("RL-SCOUT v2 approach-4 seed 0", net, [x["date"] for x in L["RULE"]],
                  z["dates"], pairs, rnd, {"note": "evid includes +50 on the 82 extended-hours exits"})


def ev_vs2():
    legs, dates = {}, None
    for tg in ("a", "b", "c"):
        z = json.loads((HERE / f"crs_vs2_legs_{tg}.json").read_text())
        legs.update(z["legs"]); dates = z["dates"]
    ev = PA.Evid()
    net, pairs = [], []
    lg = [x for x in legs["W8RSd"] if x.get("shares") and x.get("exit")]
    for x in lg:
        fill = x["entry"] / 1.001
        ce = ev.side(x["symbol"], x["date"], hm(x["entry_time"]), fill * x["shares"])
        cx = ev.side(x["symbol"], x["date"], hm(x["exit_time"]), x["exit"] * x["shares"])
        net.append(x["exit"] * x["shares"] * (1 - cx / 1e4) - fill * x["shares"] * (1 + ce / 1e4))
        pairs.append((ce, cx))
    rnd = []
    for k in range(30):
        r = [dict(x, fill=x["entry"] / 1.001) for x in legs.get(f"RND{k}", []) if x.get("shares") and x.get("exit")]
        for x in r:
            x["g"] = (x["exit"] - x["fill"]) * x["shares"]
        rnd.append((C.flat_pricer(r, "g", lambda x: (x["fill"] + x["exit"]) * x["shares"]), [x["date"] for x in r]))
    return finish("VS2 W8RSd", net, [x["date"] for x in lg], dates, pairs, rnd)


def ev_cm():
    import cm_lib as Lb
    import cm_single as S
    import cm_rev as RV
    t = S.Table("wide")
    Lb.FEE_BPS = 10.0
    sc, _m = RV.build(t, "15:30", "15:59")
    tr = S.run(t, sc, "15:59", ["15:30"], topk=7)
    ev = PA.Evid()
    net, pairs = [], []
    for x in tr:
        ce = ev.side(x["sym"], x["date"], 240 + x["m_in"], x["sh"] * x["px_in"])   # cm k = ET min - 240
        cx = ev.side(x["sym"], x["date"], 240 + x["m_out"], x["sh"] * x["px_out"])
        net.append(x["gross"] - x["sh"] * x["px_in"] * ce / 1e4 - x["sh"] * x["px_out"] * cx / 1e4)
        pairs.append((ce, cx))
    rnd = []
    for k in range(30):
        r = S.run(t, np.random.default_rng(90_000 + k).random(len(t.px_in)), "15:59", ["15:30"], topk=7)
        rnd.append((C.flat_pricer(r, "gross", lambda x: x["sh"] * (x["px_in"] + x["px_out"])),
                    [x["date"] for x in r]))
    return finish("CLOSE-MOMENTUM REV 15:30->15:59 k7", net, [x["date"] for x in tr],
                  list(t.dates), pairs, rnd)


def _wn_rows(t, rows, h, hmin, rc):
    mask = np.zeros(len(t.date_i), bool)
    mask[rows] = True
    rc.build_evid(h, hmin, mask)
    rc.set("EVID")
    net = t.pnl[h][rows].copy()
    pairs = list(zip(rc.ce[h][rows], rc.cx[h][rows]))
    rc.restore()
    return net, pairs


def ev_wn():
    import wn_oos as W
    from wn_rules import RTH
    t = W.Table()
    h = "h30"
    rc = PA.Recost(t, [h], RTH)
    sc0 = np.load(W.OUT / "model_scores_h30_s0.npy").astype(np.float64)
    m = t.mask(split=None, dec=RTH, h=h) & np.isfinite(sc0)
    sc = np.where(m, sc0, -np.inf)
    oos = np.isin(t.split, 1)
    first = t.dec_i == t.dec.index("09:35")
    elig = t.mask(split=1, dec=["09:35"], h=h)
    d_oos = sorted({t.date_s[i] for i in np.flatnonzero(elig)})
    out = {}
    for k, nm in ((1, "WIDE-NET model single"), (3, "WIDE-NET model top3 @09:35 (account-legal)"),
                  (7, "WIDE-NET model top7 @09:35 (account-legal)")):
        rows = W.pick(t, m & oos & first, sc, topk=k, per="day")
        net, pairs = _wn_rows(t, rows, h, 30, rc)
        rnd = []
        for s_ in range(30):
            rng = np.random.default_rng(10_000 + s_)
            rr = W.pick(t, elig, rng.random(len(t.date_i)), topk=k, per="slot",
                        slots=W.slots_of(t, rows))
            R, live = rc.R[h]
            N = rc.N[rr]; Rr = R[rr]
            rnd.append((lambda b, N=N, Rr=Rr: N * Rr * (1 - b / 1e4) - N * (1 + b / 1e4), list(t.date_s[rr])))
        out.update(finish(nm, net, list(t.date_s[rows]), d_oos, pairs, rnd))
    return out


def ev_cat():
    import cat_model as M
    import cat_buckets as CB
    import wn_lib as WL
    from wn_rules import RTH
    t = M.load("wide")
    h = "h60"
    rc = PA.Recost(t, [h], RTH)
    sel, decs, _hs, tb = CB.rules(t)["R15 fresh earnings & green @09:35"]
    m = t.mask(dec=decs, h=h)
    score = np.where(sel, tb, np.nan).astype(np.float32)
    _p, dates, take = WL.single_pick(t, score, m & sel, h, 1)
    take = np.asarray(take)
    net, pairs = _wn_rows(t, take, h, 60, rc)
    d_all = sorted(set(t.date_s[np.flatnonzero(m)]))
    return finish("CATALYST-MINER R15 h60", net, list(dates), d_all, pairs, None,
                  {"note": "control not re-priced at EVID (30-seed slot-matched control is "
                           "-$35.57/tkt at flat 10; see grid)"})


LINES = {"uq": ev_uq, "rl2": ev_rl2, "vs2": ev_vs2, "cm": ev_cm, "wn": ev_wn, "cat": ev_cat}


def main():
    a = sys.argv
    only = a[a.index("--only") + 1].split(",") if "--only" in a else list(LINES)
    res = json.loads(OUTF.read_text()) if OUTF.exists() else {}
    for k in only:
        print("==", k, flush=True)
        try:
            res.update(LINES[k]())
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("!!", k, e, flush=True)
            continue
        OUTF.write_text(json.dumps(res, indent=1, default=float))
    for n, s in res.items():
        print(f"{n[:44]:<44} evid {s['evid_bps_mean']:>6} (med {s['evid_bps_median']}) "
              f"$/tkt {s['per_ticket']:+8.2f} $/mo {s['per_month']:+9.1f} "
              f"pct {s.get('pct_vs_random_at_flat_beff')}")


if __name__ == "__main__":
    main()
