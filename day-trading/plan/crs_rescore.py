"""COST-RESCORE (2026-10-01, part of PESSIMISM-AUDIT): every line's best
config and its random control, re-priced from saved dumps on a flat
per-side cost grid 0,2,3,4,6,8,10,12 bps (+50 bps on any extended-hours
leg, as each harness charges it), plus the break-even cost.

Sources (all GROSS recovered by undoing the harness's own convention):
  WIDE-NET single/top3/5/7, CATALYST R15, CHAMPION R4, LIMIT-EXEC, OPEN-
    UNIVERSE: PESSIMISM-AUDIT's plan/pa_rescore.py line functions,
    imported (summ patched to add months-positive); wn/cat tables are
    inverted exactly (pnl = N(1+c0)tgt), R4 from pa_out/cp_r4_legs.json,
    lx/ou linear between their stored zero-cost and flat-10 rows.
  CLOSE-MOMENTUM REV|15:30->15:59|k7: cm_single.run once per ranking at the
    incumbent fee; each trade carries gross = sh*(px_out-px_in) and the
    path is cost-free, so net(b) = gross - sh*(px_in+px_out)*b (identity
    at b=10 asserted per trade).
  CHAMPION R5: plan/crs_cp.py dump.  RL-SCOUT v2: plan/crs_rl2.py dump.
  UNIVERSE-QUOTES: plan/crs_uq.py dump.  VS2 W8RSd: plan/crs_vs2.py dump.
  C37F-hf3 / HOLD1-hf3: data/massive/rotation_trades_*_hf3.json ledgers
    (C37F carries 0 bps, HOLD1 10 bps: fill = entry/(1+slip_old)); path
    frozen (C37F stop/trail levels are struck off entry -- cost-rebase
    route B bounds that); no 30-seed full-period control exists.

    python plan/crs_rescore.py [--only wn,cat,...]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import pa_rescore as PA  # noqa: E402

GRID = [0.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0]
Y1_END, Y2_END = PA.Y1_END, PA.Y2_END
OUTF = HERE / "crs_rescore.json"
_summ0 = PA.summ


def summ(pnl, dates, ndays):
    s = _summ0(pnl, dates, ndays)
    if len(pnl):
        by = {}
        for d, p in zip(dates, pnl):
            by[str(d)[:7]] = by.get(str(d)[:7], 0.0) + float(p)
        s["months_pos"] = f"{sum(v > 0 for v in by.values())}/{len(by)}"
    return s


PA.summ = summ
pct = PA.pct


def lab(b):
    return f"{b:g}"


# ------------------------------------------------------------ generic legs
def score(name, rule, rand, d_all, method, b_list=GRID, rule_mask=None):
    """rule: (fn(b)->pnl array, dates); rand: list of (fn, dates)."""
    d_all = sorted(d_all)
    nd = len(d_all)
    res = {}
    for b in b_list:
        p = rule[0](b)
        ds = np.asarray(rule[1])
        s = summ(p, ds, nd)
        s.update(PA.years(p, ds, d_all))
        # halves of the line's own calendar (the only split a held-out-
        # year-only line has); per-month on each half's own sessions
        mid = d_all[len(d_all) // 2]
        for nm_, k_ in (("half1", ds < mid), ("half2", ds >= mid)):
            nh = sum((d < mid) == (nm_ == "half1") for d in d_all)
            s[nm_] = {"per_ticket": round(float(p[k_].mean()), 2) if k_.any() else None,
                      "per_month": round(float(p[k_].sum()) / (nh / 21.0), 1),
                      "from": d_all[0] if nm_ == "half1" else mid}
        if rand:
            rt, rx, rp = [], [], []
            for fn, rds in rand:
                q = fn(b)
                qs = _summ0(q, np.asarray(rds), nd)
                rt.append(qs.get("total", 0.0))
                rx.append(qs.get("ex_best_day", 0.0))
                rp.append(qs.get("per_ticket", 0.0))
            s.update(random_per_ticket=round(float(np.mean(rp)), 2),
                     random_sd=round(float(np.std(rp, ddof=1)), 2),
                     random_n=len(rand),
                     random_tickets_per_day=round(float(np.mean(
                         [len(r[1]) for r in rand])) / nd, 3),
                     pct_vs_random=pct(s["total"], rt),
                     pct_per_ticket_vs_random=pct(s["per_ticket"], rp),
                     pct_ex_best_vs_random=pct(s["ex_best_day"], rx))
        res[lab(b)] = s
    res["method"] = method
    return {name: res}


def flat_pricer(legs, gross_key, notion_fn, ext_fn=None):
    g = np.array([x[gross_key] for x in legs], float)
    nn = np.array([notion_fn(x) for x in legs], float)       # entry+exit notional
    if ext_fn is None:
        ex = np.zeros_like(g)
    else:
        ex = np.array([ext_fn(x) for x in legs], float)       # $ notional on ext legs
    return lambda b: g - nn * b / 1e4 - ex * 50.0 / 1e4


# ------------------------------------------------------------- the lines
def line_cp_r5():
    z = json.loads((HERE / "crs_cp_r5_legs.json").read_text())
    pub = json.loads((ROOT / "data/massive/cp/recomb.json").read_text())
    L = z["legs"]
    mk = lambda lg: (flat_pricer(lg, "gross", lambda x: (x["entry"] + x["exit"]) * x["shares"]),  # noqa: E731
                     [x["date"] for x in lg])
    ident = {"R5_flat_total_rerun": round(sum(x["net_flat"] for x in L["R5"]), 2),
             "R5_flat_total_published": round(pub["R5 coil + start 10:00 + stop -2%"]["total_flat"], 2),
             "R5_n": [len(L["R5"]), pub["R5 coil + start 10:00 + stop -2%"]["n"]],
             "rnd_flat_totals_match": all(abs(sum(x["net_flat"] for x in L[f"RND{k}"])
                                              - pub[f"RND{k}"]["total_flat"]) < 0.01 for k in range(30)),
             "net_flat_vs_10bps_reprice_maxdiff": round(float(np.max(np.abs(
                 mk(L["R5"])[0](10.0) - np.array([x["net_flat"] for x in L["R5"]])))), 4)}
    r = score("CHAMPION-REPLAY R5", mk(L["R5"]), [mk(L[f"RND{k}"]) for k in range(30)],
              z["dates"], "exact: crs_cp.py re-run, no cost callable, gross per leg; "
              "b on entry+exit notional; random = R5 frame 30 seeds (cp_run.recomb)")
    r["CHAMPION-REPLAY R5"]["identity"] = ident
    return r


def line_cm():
    import cm_lib as Lb
    import cm_single as S
    import cm_rev as RV
    t = S.Table("wide")
    Lb.FEE_BPS = 10.0
    sc, _m = RV.build(t, "15:30", "15:59")
    runs = {"RULE": S.run(t, sc, "15:59", ["15:30"], topk=7)}
    for k in range(30):
        runs[f"RND{k}"] = S.run(t, np.random.default_rng(90_000 + k).random(len(t.px_in)),
                                "15:59", ["15:30"], topk=7)
    bad = 0
    for tr in runs.values():
        for x in tr:
            ext = (x["m_in"] < 330 or x["m_in"] >= 720 or x["m_out"] < 330 or x["m_out"] > 720)   # k = ET min - 240
            exp = x["gross"] - x["sh"] * (x["px_in"] + x["px_out"]) * 1e-3
            bad += int(ext or abs(exp - x["pnl"]) > 1e-6)
    mk = lambda tr: (flat_pricer(tr, "gross", lambda x: x["sh"] * (x["px_in"] + x["px_out"])),  # noqa: E731
                     [x["date"] for x in tr])
    r = score("CLOSE-MOMENTUM REV 15:30->15:59 k7", mk(runs["RULE"]),
              [mk(runs[f"RND{k}"]) for k in range(30)], list(t.dates),
              "exact: cm_single.run once per ranking (composite built at 10 bps, "
              "IC selection cost-invariant); gross re-priced; random = 30 seeds 90000+k "
              "as cm_controls")
    r["CLOSE-MOMENTUM REV 15:30->15:59 k7"]["identity"] = {
        "trades_failing_10bps_identity_or_ext": bad,
        "trades": sum(len(v) for v in runs.values())}
    return r


def line_rl2():
    z = json.loads((HERE / "crs_rl2_legs.json").read_text())
    L = z["legs"]
    mk = lambda lg: (flat_pricer(  # noqa: E731
        [dict(x, g=x["sh"] * (x["px_out"] - x["px_in"])) for x in lg], "g",
        lambda x: x["sh"] * (x["px_in"] + x["px_out"]),
        lambda x: x["sh"] * (x["px_in"] * x["ext_in"] + x["px_out"] * x["ext_out"])),
        [x["date"] for x in lg])
    rf = mk(L["RULE"])[0](10.0)
    ident = {"tickets": len(L["RULE"]), "published_tickets": z["published"]["tickets"],
             "total_10bps": round(float(rf.sum()), 2),
             "published_total": z["published"]["total"],
             "ext_in_legs": int(sum(x["ext_in"] for x in L["RULE"])),
             "ext_out_legs": int(sum(x["ext_out"] for x in L["RULE"]))}
    dates = sorted({x["date"] for x in L["RULE"]} | set(z["dates"]))
    r = score("RL-SCOUT v2 approach-4 seed 0", mk(L["RULE"]),
              [mk(L[f"RND{k}"]) for k in range(30)], z["dates"],
              "exact: crs_rl2.py dump (path cost-free, cr_engine proof); b both sides, "
              "+50 on ext legs; held-out year only (2025-08-01..2026-08-06); random = "
              "cr_rerun.stage_rl2's 30 seeds (NOT rate-matched: ~7 tkts/day vs 1.2)")
    r["RL-SCOUT v2 approach-4 seed 0"]["identity"] = ident
    _ = dates
    return r


def line_uq():
    z = json.loads((HERE / "crs_uq_legs.json").read_text())
    L = z["legs"]

    def mk(lg):
        N = np.array([x["N"] for x in lg]); F = np.array([x["F"] for x in lg])
        X = np.array([x["X"] for x in lg])
        ei = np.array([x["ext_in"] for x in lg], float); eo = np.array([x["ext_out"] for x in lg], float)
        pas = np.array([x["passive"] for x in lg], float)

        def fn(b):
            ec = ((1 - pas) * b + 50 * ei) / 1e4
            xc = (b + 50 * eo) / 1e4
            return N * (X / F * (1 - xc) - (1 + ec))
        return fn, [x["date"] for x in lg]
    m = L["MODEL"]
    ident = {"tickets": len(m), "per_ticket_10bps": round(float(np.mean(mk(m)[0](10.0))), 3),
             "per_ticket_harness": round(float(np.mean([x["pnl"] for x in m])), 3),
             "maxdiff": round(float(np.max(np.abs(mk(m)[0](10.0) - np.array([x["pnl"] for x in m])))), 6),
             "passive_frac": round(float(np.mean([x["passive"] for x in m])), 3),
             "ext_legs": int(sum(x["ext_in"] or x["ext_out"] for x in m))}
    r = score("UNIVERSE-QUOTES rank-for-the-fill (limit, h30)", mk(m),
              [mk(L[f"RND{k}"]) for k in range(30)], z["dates"],
              "exact: crs_uq.py dump through uq_strat.run_many; passive limit entry "
              "pays 0, exit pays b (+50 ext); held-out year; random = 30 seeds 2000+s")
    inv = score("x", mk(L["INVERTED"]), [], z["dates"], "", b_list=[0.0, 10.0])["x"]
    r["UNIVERSE-QUOTES rank-for-the-fill (limit, h30)"]["identity"] = ident
    r["UNIVERSE-QUOTES rank-for-the-fill (limit, h30)"]["inverted"] = {
        k: inv[k]["per_ticket"] for k in ("0", "10")}
    return r


def line_vs2():
    legs, dates = {}, None
    for tg in ("a", "b", "c"):
        z = json.loads((HERE / f"crs_vs2_legs_{tg}.json").read_text())
        legs.update(z["legs"])
        dates = z["dates"]
    slip = 10.0 / 1e4

    def mk(lg):
        lg = [x for x in lg if x.get("shares") and x.get("exit")]
        for x in lg:
            x["fill"] = x["entry"] / (1 + slip)
            x["g"] = (x["exit"] - x["fill"]) * x["shares"]
            assert "09:3" <= x["entry_time"][11:16] and x["exit_time"][11:16] <= "16:00"
        return (flat_pricer(lg, "g", lambda x: (x["fill"] + x["exit"]) * x["shares"]),
                [x["date"] for x in lg])
    rule = legs["W8RSd"]
    tk = len({(x["date"], x["ticket"]) for x in rule})
    ident = {"legs": len(rule), "tickets": tk,
             "total_10bps": round(float(mk(rule)[0](10.0).sum()), 2),
             "total_harness": round(sum(x["pnl"] for x in rule), 2)}
    r = score("VS2 W8RSd", mk(rule), [mk(legs[f"RND{k}"]) for k in range(30)
                                      if f"RND{k}" in legs], dates,
              "exact: crs_vs2.py re-run at 10 bps with legs dumped (hold-to-flatten, "
              "no exit level depends on cost); fill = entry/1.001; random = NEW 30-seed "
              "gate-matched control (rs_rand: same market-red gate & minutes, random name)")
    r["VS2 W8RSd"]["identity"] = ident
    return r


def line_rot():
    out = {}
    cal = json.loads((HERE / "crs_cp_r5_legs.json").read_text())["dates"]
    ctl = json.loads((HERE / "cr_out/rot_subsample_d40_control.json").read_text())
    for cfg, slip_old in (("C37F", 0.0), ("HOLD1", 10.0)):
        lg = json.loads((ROOT / f"data/massive/rotation_trades_{cfg}_hf3.json").read_text())
        lg = [x for x in lg if x.get("shares") and x.get("exit")]
        for x in lg:
            x["fill"] = x["entry"] / (1 + slip_old / 1e4)
            x["g"] = (x["exit"] - x["fill"]) * x["shares"]
            assert x["entry_time"][11:16] >= "09:30" and x["exit_time"][11:16] <= "16:00"
        d_all = [d for d in cal if min(x["date"] for x in lg) <= d <= max(x["date"] for x in lg)]
        fn = flat_pricer(lg, "g", lambda x: (x["fill"] + x["exit"]) * x["shares"])
        rep = float(np.sum(fn(slip_old)))
        nm = f"{cfg}-hf3"
        r = score(nm, (fn, [x["date"] for x in lg]), [], d_all,
                  f"ledger re-price (path frozen); legacy slip {slip_old:g} bps undone; "
                  "no full-period 30-seed control exists")
        r[nm]["identity"] = {"total_at_legacy_slip": round(rep, 2),
                             "ledger_pnl_sum": round(sum(x["pnl"] for x in lg), 2)}
        # the only control: cost-rebase 4.7, 10 seeds x 40 days (flat = harness slip)
        rows = [x for x in ctl["rows"] if x["cfg"] == f"{cfg}-R" and x["cost"] == "flat"]
        if rows:
            r[nm]["control_40d_flat_per_ticket"] = {
                lb: round(float(np.mean([x["pnl_per_ticket"] for x in rows if x["label"] == lb])), 1)
                for lb in sorted({x["label"] for x in rows})}
        out.update(r)
    return out


def breakeven(res):
    """b* where total, Y1, Y2 cross zero (linear in b: net = G - K b)."""
    def be(v0, v10):
        if v0 is None or v10 is None:
            return None
        if v0 <= 0:
            return 0.0 if v0 == 0 else -1.0       # negative even at zero cost
        k = (v0 - v10) / 10.0
        return round(v0 / k, 2) if k > 0 else 99.0
    for nm, r in res.items():
        a, c = r.get("0"), r.get("10")
        if not isinstance(a, dict) or not isinstance(c, dict):
            continue
        tot0 = a.get("total", a.get("per_month")); tot10 = c.get("total", c.get("per_month"))
        y = lambda s, k: (s.get(k) or {}).get("per_month") if isinstance(s.get(k), dict) else None  # noqa: E731
        r["breakeven_bps"] = {"all": be(tot0, tot10), "y1": be(y(a, "y1"), y(c, "y1")),
                              "y2": be(y(a, "y2"), y(c, "y2"))}
        if "oos_h1_per_ticket" in a:
            r["breakeven_bps"]["oos_h1"] = be(a["oos_h1_per_ticket"], c["oos_h1_per_ticket"])
            r["breakeven_bps"]["oos_h2"] = be(a["oos_h2_per_ticket"], c["oos_h2_per_ticket"])
        if "random_per_ticket" in a:
            # cost at which the rule's $/ticket edge over its control equals the
            # cost difference: edge is ~cost-invariant when notionals match
            r["edge_vs_random_per_ticket"] = {lab(b): round(r[lab(b)]["per_ticket"] - r[lab(b)]["random_per_ticket"], 2)
                                              for b in GRID if isinstance(r.get(lab(b)), dict)
                                              and "random_per_ticket" in r[lab(b)]}


def line_wn_day():
    """Account-legal top-k: k names at the 09:35 decision, one ticket each
    (pa_rescore's top-k is per SLOT = 27-63 tickets/day, over the
    $100k/day cap). Same exact Recost inversion; random = 30 seeds in the
    same (date, 09:35) slots."""
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
    nd = t.ndays(1)
    elig = t.mask(split=1, dec=["09:35"], h=h)
    d_oos = np.array([d for d in t.dates if Y1_END <= d < Y2_END])
    half = d_oos[len(d_oos) // 2]
    res = {}
    for k in (3, 5, 7):
        rows = W.pick(t, m & oos & first, sc, topk=k, per="day")
        nm = f"WIDE-NET model top{k} @09:35 (account-legal)"
        res[nm] = {}
        for b in GRID:
            rc.set(b)
            p = t.pnl[h]
            s = summ(p[rows], t.date_s[rows], nd)
            ds = t.date_s[rows]
            s["oos_h1_per_ticket"] = round(float(p[rows][ds < half].mean()), 2)
            s["oos_h2_per_ticket"] = round(float(p[rows][ds >= half].mean()), 2)
            nul = W.random_null(t, elig, h, 1, rows, topk=k, n=30)
            s.update(random_per_ticket=nul["per_ticket_mean"], random_sd=nul["per_ticket_sd"],
                     random_n=nul["n_seeds"], pct_vs_random=pct(s["per_ticket"], nul["_vals"]))
            res[nm][lab(b)] = s
        res[nm]["method"] = ("exact Recost of wn table pnl_h30; top-k by model_scores_h30_s0 "
                             "at 09:35 only (per='day'); OOS year; 30-seed slot-matched random")
    rc.restore()
    return res


LINES = {
    "wnday": line_wn_day,
    "wn": lambda: PA.line_widenet(GRID),
    "cat": lambda: PA.line_catalyst(GRID),
    "cp4": lambda: PA.line_champion(GRID),
    "cp5": line_cp_r5,
    "cm": line_cm,
    "lx": lambda: PA.line_limitexec(GRID),
    "ou": lambda: PA.line_openuni(GRID),
    "uq": line_uq,
    "vs2": line_vs2,
    "rl2": line_rl2,
    "rot": line_rot,
}


def main():
    a = sys.argv
    only = a[a.index("--only") + 1].split(",") if "--only" in a else list(LINES)
    allres = json.loads(OUTF.read_text()) if OUTF.exists() else {}
    for k in only:
        print(f"== {k}", flush=True)
        try:
            r = LINES[k]()
        except Exception as e:                          # report, keep going
            import traceback
            traceback.print_exc()
            print(f"!! {k} failed: {e}", flush=True)
            continue
        breakeven(r)
        allres.update(r)
        OUTF.write_text(json.dumps(allres, indent=1, default=float))
    print("-> crs_rescore.json")


if __name__ == "__main__":
    main()
