"""CATALYST-MINER (2026-09-16): (a) bucket tables per catalyst class and
(c) the pre-registered simple rules, with matched controls.

No fitting anywhere in this file.  A bucket is a boolean over the
catalyst columns evaluated at the decision minute; the table reports the
mean net $/ticket, win rate, n and a t-stat for the bucket AND its
complement, at every decision time and horizon, split Y1 / Y2.

Rules are sets, so "the config" is: at each (date, decision) slot take
the qualifying names (tie-break = the most recent catalyst), at most k.
The matched control draws k random ELIGIBLE names on the same slots;
the mirror takes the complement set.  Percentiles are over 30 seeds.

Usage:  python plan/cat_buckets.py [--table wide|gap]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cat_lib as C                                           # noqa: E402
import cat_events as E                                        # noqa: E402
import cat_model as M                                         # noqa: E402
import wn_lib as L                                            # noqa: E402

HS = ["h30", "h60", "h120", "flat"]


def flags(t):
    """name -> boolean array over rows."""
    f = t.f
    out = {}
    for c in E.COUNT_CLASSES:
        for w in ("18h", "3d", "10d"):
            out[f"{c}_{w}"] = f(f"n_{c}_{w}") > 0
    out["earn_fresh"] = f("earn_fresh_ev") > 0
    out["earn_fresh_beat"] = (f("earn_fresh_ev") > 0) & (f("earn_surp_fresh_sign") > 0)
    out["earn_fresh_miss"] = (f("earn_fresh_ev") > 0) & (f("earn_surp_fresh_sign") < 0)
    out["earn_fresh_bigbeat"] = (f("earn_fresh_ev") > 0) & (f("earn_surp_fresh_pct") > 20)
    out["earn_fresh_bigmiss"] = (f("earn_fresh_ev") > 0) & (f("earn_surp_fresh_pct") < -20)
    out["earn_1to3d_beat"] = (f("days_since_earn") > 0.8) & (f("days_since_earn") <= 3) & (f("earn_surp_sign") > 0)
    out["earn_1to3d_miss"] = (f("days_since_earn") > 0.8) & (f("days_since_earn") <= 3) & (f("earn_surp_sign") < 0)
    out["dilution_30d"] = f("dilution_30d") > 0
    out["no_dilution_30d"] = f("dilution_30d") == 0
    out["insider_buy_30d"] = f("insider_buy_30d") > 0
    out["insider_sell_30d"] = f("insider_sell_30d") > 0
    out["f13d_30d"] = f("f13d_30d") > 0
    out["any_catalyst_18h"] = f("any_catalyst_18h") > 0
    out["quiet_10d"] = (f("n_news_all_10d") == 0) & (f("n_fil_all_10d") == 0)
    out["sent_pos_3d"] = f("sent_mean_3d") > 0.5
    out["sent_neg_3d"] = f("sent_mean_3d") < -0.5
    out["news_lt2h"] = f("hrs_since_news") < 2
    out["pr_lt18h"] = f("hrs_since_pr") < 18
    out["earn_upcoming_today_or_tmrw"] = (f("earn_rh") >= 0) & (f("earn_rh") <= 1)
    return out


def _stats(p):
    p = np.asarray(p, float)
    if p.size == 0:
        return {"n": 0, "mean": None, "win": None, "t": None}
    return {"n": int(p.size), "mean": round(float(p.mean()), 2),
            "win": round(float((p > 0).mean()), 3),
            "t": round(float(p.mean() / p.std(ddof=1) * np.sqrt(p.size)), 2)
            if p.size > 2 and p.std(ddof=1) > 0 else None}


def bucket_tables(t, out_name="buckets.json"):
    fl = flags(t)
    yr = np.array([m < M.Y1_END for m in t.month])
    res = []
    for name, b in fl.items():
        for dec in t.dec:
            base = t.mask(dec=dec)
            for h in HS:
                m = base & t.ok[h] if h in t.ok else base
                inb = m & b
                outb = m & ~b
                if inb.sum() < 30:
                    continue
                p, q = t.pnl[h][inb], t.pnl[h][outb]
                r = {"flag": name, "dec": dec, "h": h, "in": _stats(p), "out": _stats(q),
                     "in_y1": _stats(t.pnl[h][inb & yr]), "in_y2": _stats(t.pnl[h][inb & ~yr]),
                     "out_y1": _stats(t.pnl[h][outb & yr]), "out_y2": _stats(t.pnl[h][outb & ~yr])}
                r["delta"] = round(r["in"]["mean"] - r["out"]["mean"], 2) if r["out"]["mean"] is not None else None
                res.append(r)
    C.write_json(C.OUT / out_name, res)
    return res


# ------------------------------------------------------------ rules
def rules(t):
    f = t.f
    fresh_cat = (f("n_fda_18h") + f("n_contract_18h") + f("n_8k_1.01_18h") + f("n_pr_18h")) > 0
    nodil = (f("dilution_30d") == 0) & (f("n_offering_3d") == 0)
    beat = (f("earn_fresh_ev") > 0) & (f("earn_surp_fresh_sign") > 0)
    miss = (f("earn_fresh_ev") > 0) & (f("earn_surp_fresh_sign") < 0)
    green = f("ret_since_open") > 0
    R = {
        "R1 beat & green @09:35": (beat & green, ["09:35"], ["h60", "h120"], -f("hrs_since_earn")),
        "R1b beat & green @10:00": (beat & green, ["10:00"], ["h60", "h120"], -f("hrs_since_earn")),
        "R2 beat @09:35": (beat, ["09:35"], ["h60", "h120", "flat"], f("earn_surp_fresh_pct")),
        "R2b beat @10:00": (beat, ["10:00"], ["h60", "h120", "flat"], f("earn_surp_fresh_pct")),
        "R2c beat @13:00": (beat, ["13:00"], ["h60", "h120"], f("earn_surp_fresh_pct")),
        "R3 miss @10:30 (contrarian)": (miss, ["10:30"], ["h120", "flat"], -f("earn_surp_fresh_pct")),
        "R3b miss & red @09:35": (miss & ~green, ["09:35"], ["h60", "h120"], -f("earn_surp_fresh_pct")),
        "R4 fresh PR/contract/FDA/8-K1.01, no dilution @09:35": (fresh_cat & nodil, ["09:35"], ["h60", "h120"], -f("hrs_since_pr")),
        "R4b same & green": (fresh_cat & nodil & green, ["09:35"], ["h60", "h120"], -f("hrs_since_pr")),
        "R4c same @10:30": (fresh_cat & nodil, ["10:30"], ["h60", "h120"], -f("hrs_since_pr")),
        "R5 insider buy 30d, no dilution @09:35": ((f("insider_buy_30d") > 0) & nodil, ["09:35"], ["h120", "flat"], f("insider_buy_usd_30d")),
        "R6 offering/424B/3.02 in 3d @09:35 (expected NEGATIVE)": ((f("n_offering_3d") + f("n_424b_3d") + f("n_8k_3.02_3d")) > 0, ["09:35"], ["h60", "h120"], -f("hrs_since_fil")),
        "R7 8-K 2.02 in 18h & green @09:35": ((f("n_8k_2.02_18h") > 0) & green, ["09:35"], ["h60", "h120"], -f("hrs_since_fil")),
        "R8 SC 13D in 10d @09:35": (f("n_sc13d_10d") > 0, ["09:35"], ["h120", "flat"], -f("hrs_since_fil")),
        "R9 analyst headline 18h @09:35": (f("n_analyst_18h") > 0, ["09:35"], ["h60"], -f("hrs_since_news")),
        "R10 index-inclusion headline 10d @15:30": (f("n_index_10d") > 0, ["15:30"], ["h30"], -f("hrs_since_news")),
        "R11 M&A headline 18h @09:35": (f("n_mna_18h") > 0, ["09:35"], ["h60", "h120"], -f("hrs_since_news")),
        "R12 FDA headline 18h @09:35": (f("n_fda_18h") > 0, ["09:35"], ["h60", "h120"], -f("hrs_since_news")),
        "R13 no news/filing 10d (quiet) @09:35": ((f("n_news_all_10d") == 0) & (f("n_fil_all_10d") == 0), ["09:35"], ["h60"], f("rvol30")),
        "R14 positive sentiment 3d & green @09:35": ((f("sent_mean_3d") > 0.5) & green, ["09:35"], ["h60", "h120"], f("sent_mean_3d")),
    }
    return R


def eval_rule(t, sel, decs, h, tiebreak, k, nseed=30):
    m = t.mask(dec=decs, h=h)
    score = np.where(sel, tiebreak, np.nan).astype(np.float32)
    pnl, dates, take = L.single_pick(t, score, m & sel, h, k)
    ndays = len(set(t.date_s[np.flatnonzero(m)]))
    r = L.summarize(pnl, dates, ndays, "rule")
    r.update(M._years(pnl, dates))
    # slots actually taken
    slots = np.unique(t.date_i[take].astype(np.int64) * 64 + t.dec_i[take]) if take.size else np.zeros(0)
    key_all = t.date_i.astype(np.int64) * 64 + t.dec_i
    slot_mask = m & np.isin(key_all, slots)
    tots, exb, per = [], [], []
    for s in range(nseed):
        rng = np.random.default_rng(5000 + s)
        rs = rng.random(len(score)).astype(np.float32)
        p2, _, _ = L.single_pick(t, rs, slot_mask, h, k)
        tots.append(float(p2.sum())); exb.append(float(p2.sum() - p2.max()) if p2.size else 0.0)
        per.append(float(p2.mean()) if p2.size else 0.0)
    tots, exb, per = np.array(tots), np.array(exb), np.array(per)
    # mirror: complement set on the same slots, same tie-break direction flipped
    mir_score = np.where(~sel, -tiebreak, np.nan).astype(np.float32)
    p3, d3, _ = L.single_pick(t, mir_score, slot_mask & ~sel, h, k)
    r["random_per_tkt"] = round(float(per.mean()), 2)
    r["random_sd"] = round(float(per.std()), 2)
    r["pct_total"] = round(float((tots < r["total"]).mean() * 100), 1)
    r["pct_ex_best"] = round(float((exb < r["ex_best_total"]).mean() * 100), 1)
    r["mirror_per_tkt"] = round(float(p3.mean()), 2) if p3.size else None
    r["edge_vs_random"] = round(r["per_ticket"] - r["random_per_tkt"], 2)
    r["fires_days"] = int(len(set(dates)))
    return r


def run_rules(t):
    R = rules(t)
    out = []
    for name, (sel, decs, hs, tb) in R.items():
        for h in hs:
            for k in (1, 7):
                r = eval_rule(t, sel, decs, h, tb, k)
                r.update({"rule": name, "h": h, "k": k})
                out.append(r)
                print(f"  {name[:48]:48s} {h:5s} k={k} n={r['tickets']:5d} "
                      f"${r['per_ticket']:+8.2f}/tkt ${r['per_month']:+8.0f}/mo "
                      f"y1 {r['y1_per_tkt']} y2 {r['y2_per_tkt']} rand {r['random_per_tkt']:+.2f} "
                      f"pct {r['pct_total']:.0f} mirror {r['mirror_per_tkt']}", flush=True)
    C.write_json(C.OUT / "rules.json", out)
    return out


if __name__ == "__main__":
    a = sys.argv
    which = a[a.index("--table") + 1] if "--table" in a else "wide"
    t = M.load("wide")
    print("bucket tables ...", flush=True)
    res = bucket_tables(t)
    # print the strongest buckets (n>=100 both years, same sign both years)
    good = [r for r in res if r["in"]["n"] >= 100 and r["in_y1"]["n"] >= 30 and r["in_y2"]["n"] >= 30]
    good.sort(key=lambda r: -(r["in"]["mean"] or -1e9))
    print(f"{'flag':28s} {'dec':6s} {'h':5s} {'n':>6s} {'$/tkt':>8s} {'win':>6s} {'t':>6s} {'y1':>8s} {'y2':>8s} {'out':>8s}")
    for r in good[:25]:
        print(f"{r['flag']:28s} {r['dec']:6s} {r['h']:5s} {r['in']['n']:6d} {r['in']['mean']:8.2f} "
              f"{r['in']['win']:6.3f} {r['in']['t'] or 0:6.2f} {r['in_y1']['mean']:8.2f} {r['in_y2']['mean']:8.2f} {r['out']['mean']:8.2f}")
    print("... worst:")
    for r in good[-12:]:
        print(f"{r['flag']:28s} {r['dec']:6s} {r['h']:5s} {r['in']['n']:6d} {r['in']['mean']:8.2f} "
              f"{r['in']['win']:6.3f} {r['in']['t'] or 0:6.2f} {r['in_y1']['mean']:8.2f} {r['in_y2']['mean']:8.2f} {r['out']['mean']:8.2f}")
    print("rules ...", flush=True)
    run_rules(t)
