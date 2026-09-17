"""COST-REBASE: re-run the best row of every line under MEASURED costs.

Every leg reuses the original harness by import. Nothing is rewritten.
Where a harness's PATH is provably cost-independent the ledger is
re-priced exactly (and the proof is run); where it is not, the harness
is re-run with the engine's flag-gated cost model switched on.

  wn   WIDE-NET LightGBM single-ticket + top-k (3,5,7,10) at every RTH
       slot, with the 30-seed random controls, the inverted control and
       the aug2026 stub -- all of it through plan/wn_oos.py's own
       `pick` / `random_null` / `summarize`, on a Table whose `pnl` has
       been swapped for the measured one. Also a REFIT: the walk-forward
       LightGBM re-trained on the measured label, because a cost change
       changes the label the model learns.
  uq   UNIVERSE-QUOTES' rank-for-the-fill limit policy, through
       plan/uq_relabel.py / uq_strat.py with `uq_fills.cost_frac`
       wrapped so a per-(symbol, minute) cost reaches `price_ticket`.
  rl2  RL-SCOUT v2 approach-4 seed-0 rule + its controls, re-priced.
  vs2  VS2's W8RSd, re-run through the engine flag.
  rot  C37F-hf2 / HOLD1-hf2 and their random controls -- long; driven
       from the command line, see --stage rot.

Usage:
  python plan/cr_rerun.py --stage wn
  python plan/cr_rerun.py --stage rl2
  python plan/cr_rerun.py --stage uq
  python plan/cr_rerun.py --stage vs2 [--days N]
  python plan/cr_rerun.py --stage rot --cfg C37F,HOLD1 --shard crm
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT.parent))

import cr_cost as CC                                        # noqa: E402
import cr_engine as CE                                      # noqa: E402
import cr_table as CT                                       # noqa: E402

OUT = HERE / "cr_out"
WN = ROOT / "data" / "massive" / "wn"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


# ======================================================================
# wn -- wide net
# ======================================================================

def _priced(h="h30"):
    z = dict(np.load(CT.path_of(h), allow_pickle=False))
    f = OUT / f"priced_{h}.npz"
    if not f.exists():
        raise SystemExit(f"run: python plan/cr_table.py --price --h {h}")
    p = dict(np.load(f, allow_pickle=False))
    return z, p


def stage_wn(h="h30", refit=True):
    WL = _load("wn_lib", HERE / "wn_lib.py")
    WO = _load("wn_oos", HERE / "wn_oos.py")
    z, p = _priced(h)
    rep = {"h": h, "legs": []}

    def table(kind):
        t = WL.Table()
        if kind != "flat10":
            t.pnl[h] = p[f"pnl_{kind}"].astype(np.float64)
        return t

    for kind in ("flat10", "measured", "spreadonly", "imp03"):
        t = table(kind)
        for f in sorted(WN.glob("model_scores_h30_s0.npy")):
            sc0 = np.load(f).astype(np.float64)
            m = t.mask(split=None, dec=WO.RTH, h=h) & np.isfinite(sc0)
            sc = np.where(m, sc0, -np.inf)
            oos = np.isin(t.split, 1)
            first = t.dec_i == t.dec.index("09:35")
            rows = WO.pick(t, m & oos & first, sc, per="day")
            res = WO.score_rows(t, rows, h, 1, f"{f.stem}:{kind}")
            elig = t.mask(split=1, dec=["09:35"], h=h)
            nul = WO.random_null(t, elig, h, 1, rows)
            inv = WO.pick(t, m & oos & first,
                          np.where(m, -sc0, -np.inf), per="day")
            a = WO.pick(t, m & np.isin(t.split, 2) & first, sc, per="day")
            res.update(cost=kind, topk=1, per="day",
                       random_mean=nul["per_ticket_mean"],
                       random_sd=nul["per_ticket_sd"],
                       percentile=WO.pctile(res["per_ticket"], nul["_vals"]),
                       inverted=round(float(t.pnl[h][inv].mean()), 2)
                       if inv.size else None,
                       aug2026_tickets=int(a.size),
                       aug2026_total=round(float(t.pnl[h][a].sum()), 2)
                       if a.size else 0.0)
            rep["legs"].append(res)
            for k in (3, 5, 7, 10):
                rk = WO.pick(t, m & oos, sc, topk=k, per="slot")
                b = WO.score_rows(t, rk, h, 1, f"top{k}_allslots:{kind}")
                nb = WO.random_null(t, t.mask(split=1, dec=WO.RTH, h=h),
                                    h, 1, rk, topk=k, n=WO.NRAND_K)
                ak = WO.pick(t, m & np.isin(t.split, 2), sc, topk=k,
                             per="slot")
                b.update(cost=kind, topk=k, per="slot",
                         random_mean=nb["per_ticket_mean"],
                         percentile=WO.pctile(b["per_ticket"], nb["_vals"]),
                         aug2026_tickets=int(ak.size),
                         aug2026_total=round(float(t.pnl[h][ak].sum()), 2)
                         if ak.size else 0.0)
                rep["legs"].append(b)

    # ---- REFIT: the model re-trained on the measured label -----------
    if refit:
        WM = _load("wn_model", HERE / "wn_model.py")
        tm = table("measured")
        WM.Table = lambda *a, **k: tm
        t0 = time.monotonic()
        WM.stage_wf(h, 0, shuffle=False, tag="_crmeas")
        print(f"refit {(time.monotonic()-t0)/60:.1f}m", flush=True)
        sc0 = np.load(WN / f"model_scores_{h}_s0_crmeas.npy"
                      ).astype(np.float64)
        t = tm
        m = t.mask(split=None, dec=WO.RTH, h=h) & np.isfinite(sc0)
        sc = np.where(m, sc0, -np.inf)
        oos = np.isin(t.split, 1)
        first = t.dec_i == t.dec.index("09:35")
        rows = WO.pick(t, m & oos & first, sc, per="day")
        res = WO.score_rows(t, rows, h, 1, "refit_on_measured")
        nul = WO.random_null(t, t.mask(split=1, dec=["09:35"], h=h),
                             h, 1, rows)
        res.update(cost="measured_refit", topk=1, per="day",
                   random_mean=nul["per_ticket_mean"],
                   percentile=WO.pctile(res["per_ticket"], nul["_vals"]))
        rep["legs"].append(res)
        for k in (3, 5, 7):
            rk = WO.pick(t, m & oos, sc, topk=k, per="slot")
            b = WO.score_rows(t, rk, h, 1, f"refit_top{k}")
            nb = WO.random_null(t, t.mask(split=1, dec=WO.RTH, h=h), h, 1,
                                rk, topk=k, n=WO.NRAND_K)
            b.update(cost="measured_refit", topk=k, per="slot",
                     random_mean=nb["per_ticket_mean"],
                     percentile=WO.pctile(b["per_ticket"], nb["_vals"]))
            rep["legs"].append(b)

    OUT.mkdir(exist_ok=True)
    (OUT / "rerun_wn.json").write_text(json.dumps(rep, indent=1, default=str))
    _print_legs(rep["legs"])
    return rep


def _print_legs(legs):
    print(f"{'label':>42} {'cost':>14} {'k':>3} {'tkt':>6} {'$/tkt':>8} "
          f"{'$/mo':>9} {'mo+':>7} {'rand':>8} {'pct':>5} {'ex-best':>10}")
    for b in legs:
        print(f"{str(b['label'])[:42]:>42} {b.get('cost',''):>14} "
              f"{b.get('topk',1):>3} {b['tickets']:>6} "
              f"{b['per_ticket']:>8.2f} {b['per_month']:>9.0f} "
              f"{b['months_pos']:>7} {b.get('random_mean',0):>8.2f} "
              f"{b.get('percentile',0):>5.1f} {b['ex_best_total']:>10,.0f}")


# ======================================================================
# rl2 -- re-price the ledger (path is cost-independent; proved)
# ======================================================================

def stage_rl2(seeds=30):
    """RL-SCOUT v2, approach 4, seed 0 -- its published rule, re-priced.

    The rl2 harness's PATH is cost-independent (exits compare mark /
    px_in on RAW fill prices, sizing is notional/px, the $500 minimum
    tests sh*px), so the ledger `sim.run_day` returns can be re-priced
    exactly. `assert_path_cost_free` proves the premise by re-running
    with the fee tripled and asserting every entry and exit minute and
    price is unchanged.
    """
    r2 = HERE / "rl2"
    sys.path.insert(0, str(r2))
    FT = _load("features", r2 / "features.py")
    SM = _load("sim", r2 / "sim.py")
    RL = _load("rules", r2 / "rules.py")
    TR_END, TE_END = "2025-08-01", "2026-08-07"      # rules.py:182
    dates = sorted((r2 / "out" / "feat").glob("*.npz"))
    hold = [SM.Day(p_) for p_ in dates if TR_END <= p_.stem < TE_END]
    print(f"held-out days: {len(hold)}", flush=True)
    chk, bad = CE.assert_path_cost_free(SM, hold, n=8)
    print(f"path-cost-free proof: {chk} legs, {bad} moved", flush=True)

    best = json.loads((r2 / "results" / "rules_holdout_s0.json").read_text())
    rd = best["rule"]
    tests = [(FT.FEATURE_NAMES.index(n), 1 if op == ">" else -1, float(v))
             for n, op, v in rd["tests"]]
    cand = RL.Cand(tests, tuple(rd["window"]),
                   (rd["exit"][0], rd["exit"][1]) if len(rd["exit"]) > 1
                   else (rd["exit"][0],))
    cm = CC.CostModel(ext_floor_bps=60.0)    # the 10 fee + 50 ext ladder
    rep = {"rule": rd, "path_checks": chk, "path_moved": bad, "legs": [],
           "published_heldout": best["heldout"]}

    tr = RL.evaluate(cand, hold)
    variants = [("flat10", dict(flat_bps=10.0)),
                ("measured", dict()),
                ("spreadonly", dict(cm=CC.CostModel(
                    ext_floor_bps=60.0, impact_coef=0.0,
                    enable_impact=False)))]
    for name, kw in variants:
        c = kw.pop("cm", cm)
        pr = CE.reprice(tr, c, **kw)
        rep["legs"].append(_sum_rl2(pr, len(hold), f"rules_s0:{name}"))

    # 30-seed random control, matched to the rule's ticket RATE, through
    # plan/rl2/honesty.py's own machinery (imported, not reimplemented)
    HO = _load("honesty", r2 / "honesty.py")
    rate = len(tr) / max(len(hold), 1)
    p_entry = rate / (SM.T * 1.0)
    for name, kw in [("flat10", dict(flat_bps=10.0)), ("measured", dict()),
                     ("spreadonly", dict(cm=CC.CostModel(
                         ext_floor_bps=60.0, impact_coef=0.0,
                         enable_impact=False)))]:
        c = kw.pop("cm", cm)
        vals = []
        for s_ in range(seeds):
            trs = []
            for d in hold:
                rng = np.random.default_rng(10_000 + s_)
                sc = rng.random((SM.T, d.S))
                trs += SM.run_day(d, sc, cand.exit,
                                  min_score=1.0 - p_entry,
                                  max_new_per_step=2)[0]
            pr = CE.reprice(trs, c, **kw)
            vals.append(_sum_rl2(pr, len(hold), f"random:{name}", s_))
        pt = np.array([v["per_ticket"] for v in vals])
        pm = np.array([v["per_month"] for v in vals])
        row = {"label": f"random{seeds}:{name}", "cost": name,
               "tickets": int(np.mean([v["tickets"] for v in vals])),
               "per_ticket": round(float(pt.mean()), 2),
               "per_ticket_sd": round(float(pt.std(ddof=1)), 2),
               "per_month": round(float(pm.mean()), 2),
               "months_pos": "-", "ex_best_total": 0.0,
               "_vals": [float(x) for x in pt]}
        rep["legs"].append(row)
        b = [x for x in rep["legs"] if x["label"] == f"rules_s0:{name}"][0]
        b["cost"] = name
        b["random_mean"] = row["per_ticket"]
        b["percentile"] = round(float(100.0 * np.mean(
            np.array(row["_vals"]) < b["per_ticket"])), 1)

    (OUT / "rerun_rl2.json").write_text(json.dumps(rep, indent=1,
                                                   default=str))
    _print_legs([x for x in rep["legs"] if "_vals" not in x])
    for x in rep["legs"]:
        if "_vals" in x:
            print(f"{x['label']:>28} {x['per_ticket']:>8.2f} "
                  f"+/- {x['per_ticket_sd']:.2f}  ${x['per_month']:,.0f}/mo")
    return rep


def _sum_rl2(tr, ndays, label, seed=None):
    if not tr:
        return {"label": label, "tickets": 0, "per_ticket": 0.0,
                "per_month": 0.0, "months_pos": "0/0", "total": 0.0,
                "ex_best_total": 0.0, "seed": seed}
    p = np.array([x["pnl"] for x in tr])
    d = [x["date"] for x in tr]
    by = {}
    for dd, pp in zip(d, p):
        by[dd[:7]] = by.get(dd[:7], 0.0) + pp
    mv = np.array([by[m] for m in sorted(by)])
    return {"label": label, "seed": seed, "tickets": int(p.size),
            "total": round(float(p.sum()), 2),
            "per_ticket": round(float(p.mean()), 2),
            "per_month": round(float(p.sum()) / max(ndays / 21.0, 1e-9), 2),
            "months_pos": f"{int((mv>0).sum())}/{len(mv)}",
            "ex_best_total": round(float(p.sum() - p.max()), 2),
            "sharpe": 0.0,
            "mean_c_in_bps": round(float(np.mean(
                [x["c_in_bps"] for x in tr])), 2),
            "mean_c_out_bps": round(float(np.mean(
                [x["c_out_bps"] for x in tr])), 2)}


# ======================================================================
# uq -- UNIVERSE-QUOTES' rank-for-the-fill limit policy
# ======================================================================

ENTRY_SENT = -12345.0       # sentinels: see patch_uq
EXIT_SENT = -54321.0


def patch_uq(UE, UF, cm):
    """Route `uq_econ.price_ticket`'s two cost legs through the measured
    model WITHOUT rewriting price_ticket.

    price_ticket calls `uf.cost_frac(mf, passive_bps)` for the entry and
    `uf.cost_frac(ex_m, exit_bps)` for the exit, and neither call sees a
    symbol. So price_ticket is wrapped to publish (day, si) and to pass
    two sentinel `bps` values through; the wrapped `cost_frac`
    recognises them and returns the measured number for the right leg.
    Any other caller of cost_frac (the identity gate, uq_fills.limit)
    reaches the ORIGINAL function unchanged.

    `passive_bps <= 0` is UNIVERSE-QUOTES' own flag for a resting limit
    that someone else crossed to (uq_strat.py:89 vs :102); that leg is
    charged impact only, the market leg pays the half-spread too."""
    orig_pt = UE.price_ticket
    orig_cf = UF.cost_frac
    ctx = {"day": None, "si": None, "passive": True}

    def price_ticket(day, ti, si, h, L, fill_t_ms, passive_bps, exit_bps,
                     cap_mult=1.0, fill_px=None):
        ctx["day"], ctx["si"] = day, si
        ctx["passive"] = bool(passive_bps is not None
                              and float(passive_bps) <= 1e-9)
        return orig_pt(day, ti, si, h, L, fill_t_ms, ENTRY_SENT, EXIT_SENT,
                       cap_mult=cap_mult, fill_px=fill_px)

    def cost_frac(minute, bps=UF.FEE_BPS):
        try:
            scalar = float(bps)
        except Exception:
            return orig_cf(minute, bps)
        if scalar not in (ENTRY_SENT, EXIT_SENT):
            return orig_cf(minute, bps)
        day, si = ctx["day"], ctx["si"]
        if day is None:
            return orig_cf(minute, UF.FEE_BPS)
        sym = day.syms[si]
        t = CT._clock(int(np.asarray(minute).reshape(-1)[0]))
        passive = ctx["passive"] and scalar == ENTRY_SENT
        return cm.cost_bps(sym, day.date, t, 15000.0,
                           passive=passive) / 1e4

    UE.price_ticket = price_ticket
    UF.cost_frac = cost_frac
    return orig_pt, orig_cf



def _redirect_uq_out(*mods):
    """OWN-FILES-ONLY GUARD. uq_relabel.stage_eval writes its report to
    `uq_relabel.OUT / relabel_eval_...json`, which is UNIVERSE-QUOTES'
    published artifact. The first --stage uq run of this line overwrote
    it (restored from git the same session, byte-exact). Every module
    this line drives now has its OUT pointed at plan/cr_out, so a
    COST-REBASE run cannot write into plan/uq_out at all."""
    OUT.mkdir(exist_ok=True)
    for m in mods:
        if m is not None and hasattr(m, "OUT"):
            m.OUT = OUT

def stage_uq(h="h30", offset=10.0, wait=1, post_k=3, split=1, seeds=30):
    UF = _load("uq_fills", HERE / "uq_fills.py")
    UE = _load("uq_econ", HERE / "uq_econ.py")
    UR = _load("uq_relabel", HERE / "uq_relabel.py")
    US = _load("uq_strat", HERE / "uq_strat.py")
    _redirect_uq_out(UF, UE, UR, US, _load("uq_label", HERE / "uq_label.py"))
    rep = {}
    print("--- flat10 (reproduces the published row) ---", flush=True)
    rep["flat10"] = UR.stage_eval(h, offset, wait, UF.FEE_BPS, split,
                                  seeds, post_k)
    cm = CC.CostModel(ext_floor_bps=60.0)
    patch_uq(UE, UF, cm)
    # uq_relabel imported uq_econ/uq_fills by name; rebind those too
    UR.UE, UR.UF = UE, UF
    US = sys.modules.get("uq_strat")
    if US is not None:
        US.UE, US.UF = UE, UF
    print("--- measured ---", flush=True)
    rep["measured"] = UR.stage_eval(h, offset, wait, UF.FEE_BPS, split,
                                    seeds, post_k)
    rep["cost_tally"] = cm.report()
    (OUT / "rerun_uq.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep["cost_tally"], indent=1))
    return rep


def stage_uqrefit(h="h30", offset=10.0, wait=1, post_k=3, split=1,
                  seeds=30):
    """The UQ leg, made symmetric with the wide-net leg: rebuild the
    limit-fill LABEL under measured costs, refit the ranker on it, and
    evaluate. Every artifact is redirected into plan/cr_out so not one
    byte of plan/uq_out is overwritten -- uq_label.path and
    uq_relabel.score_path are monkeypatched, the modules are not
    edited."""
    UF = _load("uq_fills", HERE / "uq_fills.py")
    UE = _load("uq_econ", HERE / "uq_econ.py")
    UL = _load("uq_label", HERE / "uq_label.py")
    UR = _load("uq_relabel", HERE / "uq_relabel.py")
    UL.UE, UL.UF = UE, UF
    UR.UE, UR.UF, UR.UL = UE, UF, UL
    _redirect_uq_out(UF, UE, UL, UR, _load("uq_strat", HERE / "uq_strat.py"))
    cm = CC.CostModel(ext_floor_bps=60.0)
    patch_uq(UE, UF, cm)
    US = sys.modules.get("uq_strat")
    if US is not None:
        US.UE, US.UF = UE, UF
    OUT.mkdir(exist_ok=True)
    UL.path = lambda *a, **k: OUT / "limlabel_measured_h30_o10_w1.npz"
    UR.score_path = lambda h_, o_, w_, x_, sp_: (
        OUT / f"relabel_scores_measured_s{sp_}.npy")
    lab = UL.path()
    if not lab.exists():
        UL.build(h, offset, wait, UF.FEE_BPS)
    if not UR.score_path(h, offset, wait, UF.FEE_BPS, 1).exists():
        UR.stage_scores(h, offset, wait, UF.FEE_BPS)
    rep = UR.stage_eval(h, offset, wait, UF.FEE_BPS, split, seeds, post_k)
    (OUT / "rerun_uq_refit.json").write_text(
        json.dumps({"report": rep, "cost_tally": cm.report()}, indent=1,
                   default=str))
    return rep


# ======================================================================
# need -- the break-even information coefficient under measured costs
# ======================================================================

def stage_need(h="h30"):
    WL = _load("wn_lib", HERE / "wn_lib.py")
    WN_ = _load("wn_need", HERE / "wn_need.py")
    z, p = _priced(h)
    rep = {"h": h, "target": WN_.TARGET, "curves": {}}
    KINDS = ("flat10", "measured", "spreadonly", "imp03")
    for kind in KINDS:
        t = WL.Table()
        if kind != "flat10":
            t.pnl[h] = p[f"pnl_{kind}"].astype(np.float64)
        # 1 ticket a day among any RTH slot, and top-k per slot
        c_any = WN_.curve(t, WN_.RTH, h, ks=(1, 3, 7), split=1)
        rep["curves"][kind] = {
            str(k): v for k, v in c_any.items()}
        rep[f"needed_rho_{kind}"] = {
            str(k): WN_.needed_rho(v) for k, v in c_any.items()}
    (OUT / "rerun_need.json").write_text(json.dumps(rep, indent=1,
                                                    default=str))
    for kind in KINDS:
        print(kind, json.dumps(rep[f"needed_rho_{kind}"]))
        for k, rows in rep["curves"][kind].items():
            print(f"  k={k}: " + "  ".join(
                f"rho{r['rho']}={r['per_month']:+,.0f}" for r in rows))
    return rep


# ======================================================================
# vs2 -- W8RSd through the engine flag
# ======================================================================

def stage_vs2(cfgs=("W8RSd",), shard="crm", days=None):
    os.environ["VS2W_SHARD"] = shard
    VW = _load("vs2_wide", HERE / "vs2_wide.py")
    ec = CE.EngineCost(cm=CC.CostModel(ext_floor_bps=10.0))
    CE.patch_vs2(VW, ec)
    VW.main(list(cfgs), days)
    print(json.dumps(ec.cm.report(), indent=1))
    (OUT / f"rerun_vs2_{shard}.json").write_text(
        json.dumps({"cfgs": list(cfgs), "shard": shard,
                    "cost_tally": ec.cm.report()}, indent=1))


# ======================================================================
# rot -- the rotation anchors under the engine flag
# ======================================================================

def stage_rot(cfg_ids, extra_cfgs=None):
    RS = _load("rotation_sim", HERE / "rotation_sim.py")
    if extra_cfgs:
        for new, base, over in extra_cfgs:
            RS.CFGS[new] = dict(RS.CFGS[base], **over)
    ec = CE.EngineCost(cm=CC.CostModel(ext_floor_bps=10.0))
    CE.patch_rotation(RS, ec)
    RS.run_many(list(cfg_ids))
    rep = ec.cm.report()
    print(json.dumps(rep, indent=1))
    (OUT / f"rerun_rot_{os.environ.get('ROTSHARD','x')}.json").write_text(
        json.dumps({"cfgs": list(cfg_ids), "cost_tally": rep}, indent=1))


def main():
    a = sys.argv[1:]
    st = a[a.index("--stage") + 1] if "--stage" in a else "wn"
    if st == "wn":
        stage_wn(refit="--norefit" not in a)
    elif st == "rl2":
        stage_rl2()
    elif st == "uq":
        pk = int(a[a.index("--postk") + 1]) if "--postk" in a else 3
        stage_uq(post_k=pk)
    elif st == "uqrefit":
        pk = int(a[a.index("--postk") + 1]) if "--postk" in a else 3
        stage_uqrefit(post_k=pk)
    elif st == "need":
        stage_need()
    elif st == "vs2":
        d = int(a[a.index("--days") + 1]) if "--days" in a else None
        cf = (a[a.index("--cfg") + 1].split(",") if "--cfg" in a
              else ["W8RSd"])
        stage_vs2(cf, os.environ.get("VS2W_SHARD", "crm"), d)
    elif st == "rot":
        cf = a[a.index("--cfg") + 1].split(",") if "--cfg" in a \
            else ["C37F", "HOLD1"]
        extra = []
        for c in list(cf):
            if c.endswith("-R"):
                extra.append((c, c[:-2], dict(
                    rand=True, desc="CONTROL random pick")))
        stage_rot(cf, extra)
    else:
        raise SystemExit(f"unknown stage {st}")


if __name__ == "__main__":
    main()
