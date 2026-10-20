"""PAPER-VS-BT: assemble paper vs backtest per day per book (R4, R15, RL)
from the pvb_* outputs and the paper ledgers. Prints the tables used in
research-oct/PAPER-VS-BACKTEST.md and writes data/pvb/summary.json.

    python plan/pvb_compare.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_lib as P                                          # noqa: E402

PV = P.DATA / "pvb"
PD = P.DATA / "paper_days"
DAYS = ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09",
        "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16",
        "2026-10-19"]
LOCKSTEP = {"2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"}


def n15(entry, exit_, sh, bps=15.0):
    return (exit_ - entry) * sh - (entry + exit_) * sh * bps / 1e4


def paper_r4():
    rows = []
    for d in DAYS:
        L = json.loads((PD / f"{d}.3book.json").read_text())
        grids = {t["sym"] + "@" + t.get("entry_time", ""): t.get("decision_min")
                 for t in L["trades"] if t["book"] == "r4"}
        dec = [t for t in L["trades"] if t["book"] == "r4"]
        if d == "2026-10-14":
            # crash 14:37, no EOD: rebuilt from full-day RH bars (data/pvb/rhx):
            # model entry 09:36 open 27.60, R4 exits -> 15:00 flatten at the
            # last print <= 15:00 (14:55 close 29.615); official exit unknown
            rows.append(dict(date=d, sym="QBTZ", grid="09:35", shares=362,
                             entry=27.58, exit=29.615, pnl=round(362 * (29.615 - 27.58), 2),
                             model_entry=27.60, model_exit=29.615,
                             model_pnl=round(362 * (29.615 - 27.60), 2),
                             reason="flatten (rebuilt)", cost_usd_vs_mid=None,
                             rebuilt=True))
            continue
        tl = (L.get("eod") or {}).get("r4", {}).get("trade_list", [])
        for k, t in enumerate(tl):
            g = dec[k].get("decision_min") if k < len(dec) else None
            rows.append(dict(date=d, sym=t["sym"], grid=g, shares=t["shares"],
                             entry=t["entry"], exit=t["exit"], pnl=t["pnl"],
                             model_entry=t.get("model_entry"),
                             model_exit=t.get("model_exit"),
                             model_pnl=t.get("model_pnl"),
                             reason=t.get("reason"),
                             cost_usd_vs_mid=t.get("cost_usd_vs_mid")))
    return rows


def bt_legs(res, d, k):
    return [(x["sym"], x["t_hhmm"], x.get("exit_min_hhmm"), x.get("reason"),
             x.get("net15"), x.get("entry"), x.get("exit"), x.get("shares"))
            for x in res.get(d, {}).get(k, [])]


def main():
    A = json.loads((PV / "r4_bt_rhx.json").read_text())
    B = json.loads((PV / "r4_bt_rhx_rthcoil.json").read_text())
    S = json.loads((PV / "r4_saved.json").read_text())
    pr = paper_r4()
    out = dict(r4=dict(days={}), rl={}, r15={})
    tot = dict(paper=0.0, paper_model=0.0, A_live=0.0, A_model=0.0,
               B_live=0.0, C_live_log=0.0, saved=0.0, A_noveto=0.0,
               policy_in_force_bt_conv=0.0)
    agree = dict(A_live=0, B_live=0, C_live_log=0, saved=0, A_model=0,
                 saved_lockstep=0)
    npaper = 0
    print("\n=== R4 per day ===")
    for d in DAYS:
        p = [x for x in pr if x["date"] == d]
        sv = [e for e in S[d]["events"] if e[1] in ("ENTER", "EXIT")]
        sv_legs, cur = [], None
        for e in sv:
            if e[1] == "ENTER":
                cur = dict(sym=e[2], grid=e[3])
            elif cur is not None:
                me, xp = e[6], e[4]
                sh = int(P.TICKET // me) if me else 0
                cur.update(exit=xp, entry=me, reason=e[3],
                           net15=round(n15(me, xp, sh), 2) if me else None)
                sv_legs.append(cur)
                cur = None
        row = dict(paper=p, A_live=bt_legs(A, d, "live"),
                   A_model=bt_legs(A, d, "model"),
                   A_noveto=bt_legs(A, d, "noveto"),
                   B_live=bt_legs(B, d, "live"),
                   C_live_log=bt_legs(B, d, "live_log"),
                   saved=sv_legs, lockstep=d in LOCKSTEP,
                   top8_A=A[d]["top8_compare"], top8_B=B[d]["top8_compare"])
        out["r4"]["days"][d] = row
        pp = sum(x["pnl"] for x in p)
        pm = sum((x["model_pnl"] or 0) for x in p)
        tot["paper"] += pp
        tot["paper_model"] += pm
        for k in ("A_live", "A_model", "B_live", "C_live_log", "A_noveto"):
            tot[k] += sum((x[4] or 0) for x in row[k])
        tot["saved"] += sum((x["net15"] or 0) for x in sv_legs) \
            if d not in LOCKSTEP else pm
        # the policy in force: live-track replay from 10-09; on the lockstep
        # days the paper's own (model) legs at the backtest convention
        # ($10k at the model entry, 15 bps/side)
        if d in LOCKSTEP:
            tot["policy_in_force_bt_conv"] += sum(
                n15(x["model_entry"], x["model_exit"],
                    int(P.TICKET // x["model_entry"])) for x in p)
        else:
            tot["policy_in_force_bt_conv"] += sum((x["net15"] or 0)
                                                  for x in sv_legs)
        for x in p:
            npaper += 1
            key = (x["sym"], x["grid"])
            for k in ("A_live", "B_live", "C_live_log", "A_model"):
                if any((y[0], y[1]) == key for y in row[k]):
                    agree[k] += 1
            # saved-input replay runs the CURRENT (live-track) policy; on the
            # lockstep days 10-05..10-08 it is a counterfactual, counted apart
            if any((y["sym"], y["grid"]) == key for y in sv_legs):
                agree["saved" if d not in LOCKSTEP else "saved_lockstep"] += 1
        print(d, "PAPER", [(x["sym"], x["grid"], round(x["pnl"], 2)) for x in p],
              round(pp, 2))
        for k in ("A_live", "B_live", "C_live_log", "A_model"):
            print("   ", k, [(y[0], y[1], y[2], y[3], y[4]) for y in row[k]],
                  round(sum((y[4] or 0) for y in row[k]), 2))
        print("    saved", [(y["sym"], y["grid"], y.get("reason"), y.get("net15"))
                            for y in sv_legs])
    tot = {k: round(v, 2) for k, v in tot.items()}
    out["r4"]["totals"] = tot
    out["r4"]["agree"] = dict(agree, paper_trades=npaper)
    # top-1 / top-8 agreement per grid
    import numpy as np
    for k in ("top8_A", "top8_B"):
        g = [c for d in DAYS for c in out["r4"]["days"][d][k]]
        out["r4"][k + "_stats"] = dict(
            grids=len(g), top1_same=sum(c["top1_same"] for c in g),
            overlap_mean=round(float(np.mean([c["overlap"] for c in g])), 2))
    # fill gap (official vs model, same shares)
    fg = [(x["pnl"] - x["model_pnl"]) for x in pr if x["model_pnl"] is not None]
    cm = [x["cost_usd_vs_mid"] for x in pr if x.get("cost_usd_vs_mid") is not None]
    bt_cost = [(x["entry"] + x["exit"]) * x["shares"] * 15 / 1e4 for x in pr]
    out["r4"]["fills"] = dict(
        official_minus_model_total=round(sum(fg), 2),
        official_minus_model_per_trade=round(sum(fg) / len(fg), 2),
        cost_vs_mid_per_trade=round(sum(cm) / len(cm), 2), n_cost=len(cm),
        backtest_cost_assumption_per_trade=round(sum(bt_cost) / len(bt_cost), 2))
    print("\nR4 totals", tot)
    print("R4 agree", out["r4"]["agree"])
    print("R4 top8", out["r4"]["top8_A_stats"], out["r4"]["top8_B_stats"])
    print("R4 fills", out["r4"]["fills"])
    # ---- RL
    rl = json.loads((PV / "rl_compare.json").read_text())
    paper_rl = {"2026-10-14": [("AMPX", "13:10", 1230, 8.13, 7.88, -307.50),
                               ("BB", "14:10", 1225, 8.16, 8.225,
                                round(1225 * (8.225 - 8.16), 2))],
                "2026-10-16": [("ABUS", "11:25", 2380, 4.20, 4.255, 130.90),
                               ("KOPN", "15:35", 3058, 3.27, 3.27, 0.0)]}
    rt = dict(paper=0.0, bars=0.0)
    for d in DAYS:
        p = paper_rl.get(d, [])
        b = rl[d]["bars_trades"]
        rt["paper"] += sum(x[5] for x in p)
        rt["bars"] += sum(x["net6"] for x in b)
        out["rl"][d] = dict(paper=p, bars=b, saved=rl[d]["saved_trades"],
                            br_min_bars=rl[d]["min_breadth_bars"],
                            br_min_live=rl[d]["min_breadth_live"],
                            br_absdiff_mean=rl[d]["breadth_absdiff_mean"])
    out["rl_totals"] = {k: round(v, 2) for k, v in rt.items()}
    print("\nRL totals", out["rl_totals"])
    out["r15"] = json.loads((PV / "r15_compare.json").read_text())
    f = PV / "r4_live_daily.json"
    if f.exists():
        out["r4_live_dist"] = json.loads(f.read_text()).get("summary")
        print("R4 live-policy 11-day windows", out["r4_live_dist"])
    (PV / "summary.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
