"""CATALYST-MINER (2026-09-16): the catalyst block as a VETO on the
price-only ranker, and the closest-miss rule in detail.

The bucket tables put the largest |t| on the NEGATIVE side (officer
departures, insider sales, analyst chatter, fresh earnings held to the
close ...).  A long-only book cannot short those, but it can refuse
them.  This file takes the BASE (price-only) walk-forward scores, drops
every name a given flag marks, re-picks, and reports the delta against
the unvetoed pick and against a 30-seed random pick on the SAME vetoed
universe -- so a veto that merely shrinks the universe cannot look like
skill.

Usage: python plan/cat_veto.py [--h h60] [--seeds 0,1,2]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cat_lib as C                                           # noqa: E402
import cat_buckets as B                                       # noqa: E402
import cat_model as M                                         # noqa: E402
import wn_lib as L                                            # noqa: E402

VETOES = ["8k_5.02_3d", "f4_sell_3d", "analyst_3d", "earn_fresh", "10q_18h",
          "8k_7.01_18h", "dilution_30d", "offering_3d", "424b_3d", "legal_3d",
          "any_catalyst_18h", "news_lt2h", "sc13g_3d", "f144_3d", "earn_upcoming_today_or_tmrw"]


def run(h, seeds):
    t = M.load("wide")
    fl = B.flags(t)
    fl["ANY_NEG_3d"] = fl["8k_5.02_3d"] | fl["f4_sell_3d"] | fl["analyst_3d"] | fl["10q_18h"]
    out = []
    for seed in seeds:
        f = C.OUT / f"scores_{h}_base_s{seed}.npy"
        if not f.exists():
            continue
        sc = np.load(f)
        ndays = len({d for d in t.date_s[np.flatnonzero(np.isfinite(sc))]})
        for lab, dec, k in (("1/day@09:35", "09:35", 1), ("7/day@09:35", "09:35", 7),
                            ("1/slot all decs", None, 1)):
            base_m = t.mask(dec=dec, h=h) & np.isfinite(sc)
            p0, d0, _ = L.single_pick(t, sc, base_m, h, k)
            r0 = L.summarize(p0, d0, ndays, "none")
            for v in ["none"] + VETOES + ["ANY_NEG_3d"]:
                m = base_m if v == "none" else base_m & ~fl[v]
                p, d, take = L.single_pick(t, sc, m, h, k)
                r = L.summarize(p, d, ndays, v)
                r.update(M._years(p, d))
                rnd = []
                for s in range(30):
                    rr = np.random.default_rng(7000 + s).random(len(sc)).astype(np.float32)
                    pr, _, _ = L.single_pick(t, rr, m, h, k)
                    rnd.append(float(pr.mean()) if pr.size else 0.0)
                row = {"h": h, "seed": seed, "pick": lab, "veto": v,
                       "tickets": r["tickets"], "per_ticket": r["per_ticket"],
                       "per_month": r["per_month"], "months_pos": r["months_pos"],
                       "ex_best_total": r["ex_best_total"],
                       "y1_per_tkt": r["y1_per_tkt"], "y2_per_tkt": r["y2_per_tkt"],
                       "delta_vs_unvetoed": round(r["per_ticket"] - r0["per_ticket"], 2),
                       "random_on_vetoed_universe": round(float(np.mean(rnd)), 2),
                       "edge_vs_random": round(r["per_ticket"] - float(np.mean(rnd)), 2),
                       "removed_rows": int((base_m & ~m).sum())}
                out.append(row)
                print(f"  {h} s{seed} {lab:16s} veto={v:28s} n={row['tickets']:5d} "
                      f"${row['per_ticket']:+8.2f}/tkt ${row['per_month']:+8.0f}/mo "
                      f"d={row['delta_vs_unvetoed']:+7.2f} rand={row['random_on_vetoed_universe']:+7.2f} "
                      f"edge={row['edge_vs_random']:+7.2f} y1 {row['y1_per_tkt']} y2 {row['y2_per_tkt']}",
                      flush=True)
    prev = C.read_json(C.OUT / "veto.json", [])
    prev = [r for r in prev if r["h"] != h]
    C.write_json(C.OUT / "veto.json", prev + out)


def rule_detail():
    """The closest-miss rules, ticket by ticket, with ablations and
    tie-break variants.  Row indices are saved so plan/cat_cost.py can
    re-price the same tickets under the measured cost model."""
    t = M.load("wide")
    f = t.f
    fresh = f("earn_fresh_ev") > 0
    beat = fresh & (f("earn_surp_fresh_sign") > 0)
    green = f("ret_since_open") > 0
    rec = -f("hrs_since_earn")
    specs = [("R1 beat&green@09:35 h60", beat & green, "09:35", "h60"),
             ("R1b beat&green@10:00 h60", beat & green, "10:00", "h60"),
             ("R15 fresh&green@09:35 h60", fresh & green, "09:35", "h60"),
             ("R15 fresh&green@09:35 h120", fresh & green, "09:35", "h120"),
             ("R15b fresh&green@10:00 h60", fresh & green, "10:00", "h60")]
    names = {"R1": "R1 beat & green @09:35", "R1b": "R1b beat & green @10:00",
             "R15": "R15 fresh earnings & green @09:35",
             "R15b": "R15b fresh earnings & green @10:00"}
    rules_json = {(r["rule"], r["h"], r["k"]): r for r in C.read_json(C.OUT / "rules.json", [])}
    det = {}
    ndays_all = len(set(t.date_s))

    def pick(sel, dec, h, tie, k=1):
        m = t.mask(dec=dec, h=h) & sel
        sc = np.where(sel, tie, np.nan).astype(np.float32)
        return L.single_pick(t, sc, m, h, k)

    def summ(p2, d2, nm, keys):
        s2 = L.summarize(p2, d2, ndays_all, nm)
        s2.update(M._years(p2, d2))
        return {k: s2[k] for k in keys}

    K = ("tickets", "per_ticket", "per_month", "y1_per_tkt", "y2_per_tkt", "ex_best_total")
    for lab, sel, dec, h in specs:
        pnl, dates, take = pick(sel, dec, h, rec)
        m = t.mask(dec=dec, h=h) & sel
        rows = []
        for r, p in zip(take, pnl):
            rows.append({"date": t.dates[t.date_i[r]], "sym": t.syms[t.sym_i[r]],
                         "pnl": round(float(p), 2), "notional": round(float(t.notional[r]), 0),
                         "surp_pct": round(float(f("earn_surp_fresh_pct")[r]), 1),
                         "surp_sign": float(f("earn_surp_fresh_sign")[r]),
                         "ret_open_bp": round(float(f("ret_since_open")[r]) * 1e4, 1),
                         "gap_bp": round(float(f("gap_vs_prevclose")[r]) * 1e4, 1),
                         "hrs_since_earn": round(float(f("hrs_since_earn")[r]), 1),
                         "n_cands": int((m & (t.date_i == t.date_i[r])).sum())})
        s = L.summarize(pnl, dates, ndays_all, lab)
        s.update(M._years(pnl, dates))
        top = sorted(rows, key=lambda x: -x["pnl"])[:5]
        s["top5"] = top
        s["top5_share"] = round(sum(x["pnl"] for x in top) / s["total"], 3) if s["total"] else None
        s["median_ticket"] = round(float(np.median(pnl)), 2) if pnl.size else None
        s["syms_distinct"] = len({x["sym"] for x in rows})
        s["cands_mean"] = round(float(np.mean([x["n_cands"] for x in rows])), 2) if rows else None
        s["am_reports_share"] = round(float(np.mean([x["hrs_since_earn"] < 4 for x in rows])), 3) if rows else None
        s["rows"] = [int(x) for x in take]
        rj = rules_json.get((names[lab.split(" ")[0]], h, 1))
        if rj:
            for k in ("random_per_tkt", "random_sd", "pct_total", "pct_ex_best", "mirror_per_tkt"):
                s[k] = rj[k]
        tb = {"most recent report (default)": rec, "largest ret_open": f("ret_since_open"),
              "smallest ret_open": -f("ret_since_open"), "largest surprise": f("earn_surp_fresh_pct"),
              "largest rvol30": f("rvol30"), "largest gap": f("gap_vs_prevclose")}
        s["tiebreaks"] = {}
        for nm, tie in tb.items():
            p2, d2, _ = pick(sel, dec, h, tie)
            s["tiebreaks"][nm] = summ(p2, d2, nm, K)
        rnd = []
        for sd in range(30):
            rr = np.random.default_rng(9000 + sd).random(len(t.date_i)).astype(np.float32)
            p2, d2, _ = pick(sel, dec, h, rr)
            rnd.append(float(p2.mean()))
        s["tiebreaks"]["random among qualifiers (30 seeds)"] = {
            "per_ticket": round(float(np.mean(rnd)), 2), "sd": round(float(np.std(rnd)), 2)}
        abl = {"fresh only (any colour)": fresh, "beat only": beat, "fresh & red": fresh & ~green,
               "beat & green": beat & green,
               "miss & green": fresh & (f("earn_surp_fresh_sign") < 0) & green,
               "fresh & green, gap>0": fresh & green & (f("gap_vs_prevclose") > 0),
               "fresh & green, gap<=0": fresh & green & (f("gap_vs_prevclose") <= 0),
               "fresh & green, am report (<4h)": fresh & green & (f("hrs_since_earn") < 4),
               "fresh & green, pm report (>=4h)": fresh & green & (f("hrs_since_earn") >= 4),
               "fresh & green, no dilution 30d": fresh & green & (f("dilution_30d") == 0),
               "fresh & green, ret_open > 2%": fresh & green & (f("ret_since_open") > 0.02),
               "fresh & green, ret_open <= 2%": fresh & green & (f("ret_since_open") <= 0.02)}
        s["ablations"] = {}
        for nm, ss in abl.items():
            p2, d2, _ = pick(ss, dec, h, rec)
            s["ablations"][nm] = summ(p2, d2, nm, K)
        s["horizons"] = {}
        for h2 in ("h15", "h30", "h60", "h120", "flat"):
            p2, d2, _ = pick(sel, dec, h2, rec)
            s["horizons"][h2] = summ(p2, d2, h2, K + ("months_pos",))
        p2, d2, _ = pick(sel, dec, h, rec, 7)
        s["k7"] = summ(p2, d2, "k7", K)
        s["tickets_list"] = rows
        det[lab] = s
        print(lab, json.dumps({k: v for k, v in s.items()
                               if k not in ("tickets_list", "monthly", "rows", "top5")})[:1800], flush=True)
    C.write_json(C.OUT / "rule_detail.json", det)


if __name__ == "__main__":
    a = sys.argv
    if "--detail" in a:
        rule_detail()
    else:
        h = a[a.index("--h") + 1] if "--h" in a else "h60"
        seeds = [int(x) for x in (a[a.index("--seeds") + 1].split(",") if "--seeds" in a else ["0"])]
        run(h, seeds)
