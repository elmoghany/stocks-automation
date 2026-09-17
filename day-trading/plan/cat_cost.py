"""CATALYST-MINER (2026-09-16): re-price the headline tickets under the
MEASURED cost model (plan/cr_cost.CostModel) next to the flat 10 bps.

COST-REBASE has NOT landed (no NOTES section, no index row as of this
run), so the flat 10 bps/side ladder stays the headline and this file
is the secondary reading the mandate asked for, using the module as it
stands: per-fill half-spread (max of HL2 / Corwin-Schultz / Abdi-
Ranaldo on trailing windows that end strictly before the fill minute)
plus a square-root impact term, floored at 1 bp, legacy 10 bps where
the 1-second tape is absent.

The table stores the NET return `tgt` (both legs at the flat ladder);
the gross return is recovered by inverting that ladder and re-charged at
the measured bps.  Exit minute = fill minute + H (or the forced flatten
for `flat`), the same convention the label uses; a horizon that runs
past 16:00 is treated as an extended-hours exit (60 bps) in BOTH ladders.

Usage: python plan/cat_cost.py   (reads model_results.json + scores_*.npy)
"""
import json
import sys
from datetime import time as dtime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cat_lib as C                                           # noqa: E402
import cat_model as M                                         # noqa: E402
import wn_lib as L                                            # noqa: E402
import cr_cost as CR                                          # noqa: E402

HMIN = {"h15": 15, "h30": 30, "h60": 60, "h120": 120}


def reprice(t, take, h, cm):
    """-> (flat_pnl, measured_pnl, mean_bps_in, mean_bps_out, tier mix)."""
    flat, meas = [], []
    bps_in, bps_out = [], []
    for r in take:
        sym, date = t.syms[t.sym_i[r]], t.dates[t.date_i[r]]
        dec = t.dec[t.dec_i[r]]
        hh, mm = (int(x) for x in dec.split(":"))
        m_in = hh * 60 + mm + 1
        m_out = m_in + HMIN.get(h, 10 ** 6)
        ext_in = not (570 <= m_in < 960)
        ext_out = not (570 <= m_out < 960)
        c_in0 = (10 + 50 * ext_in) / 1e4
        c_out0 = (10 + 50 * ext_out) / 1e4
        notion = float(t.notional[r])
        pnl0 = float(t.pnl[h][r])
        if notion <= 0:
            flat.append(pnl0); meas.append(pnl0); continue
        tgt = pnl0 / (notion * (1 + c_in0))
        g = (1 + tgt) * (1 + c_in0) / (1 - c_out0) - 1
        t_in = dtime(m_in // 60, m_in % 60)
        t_out = dtime(min(m_out, 959) // 60, min(m_out, 959) % 60) if not ext_out else dtime(16, 0)
        ci = cm.cost_bps(sym, date, t_in, notion) / 1e4
        co = cm.cost_bps(sym, date, t_out, notion) / 1e4 if not ext_out else max(
            cm.cost_bps(sym, date, dtime(15, 59), notion), 60.0) / 1e4
        net = (1 + g) * (1 - co) / (1 + ci) - 1
        flat.append(pnl0)
        meas.append(notion * (1 + ci) * net)
        bps_in.append(ci * 1e4); bps_out.append(co * 1e4)
    return (np.array(flat), np.array(meas),
            float(np.mean(bps_in)) if bps_in else None,
            float(np.mean(bps_out)) if bps_out else None)


def main():
    t = M.load("wide")
    res = C.read_json(C.OUT / "model_results.json", {"runs": []})
    cm = CR.CostModel()
    out = []
    for run in res["runs"]:
        if "SHUFFLED" in run["name"]:
            continue
        which, h, seed = run["name"].split("|")[:3]
        f = C.OUT / f"scores_{h}_{which}_{seed}.npy"
        if not f.exists():
            continue
        sc = np.load(f)
        for lab, dec, k in (("1/day@09:35", "09:35", 1), ("7/day@09:35", "09:35", 7),
                            ("1/day@13:00", "13:00", 1)):
            m = t.mask(dec=dec, h=h) & np.isfinite(sc)
            pnl, dates, take = L.single_pick(t, sc, m, h, k)
            ndays = len({d for d in t.date_s[np.flatnonzero(np.isfinite(sc))]})
            cm.reset()
            fl, me, bi, bo = reprice(t, take, h, cm)
            rep = cm.report()
            row = {"run": run["name"], "pick": lab, "tickets": int(len(take)),
                   "flat_per_tkt": round(float(fl.mean()), 2) if fl.size else None,
                   "measured_per_tkt": round(float(me.mean()), 2) if me.size else None,
                   "flat_per_month": round(float(fl.sum()) / max(ndays / 21, 1e-9), 2),
                   "measured_per_month": round(float(me.sum()) / max(ndays / 21, 1e-9), 2),
                   "mean_bps_in": round(bi, 2) if bi else None,
                   "mean_bps_out": round(bo, 2) if bo else None,
                   "tiers": rep.get("tiers"), "frac_gt_10bps": rep.get("frac_gt_10bps")}
            out.append(row)
            print(f"  {run['name']:22s} {lab:12s} n={row['tickets']:5d} flat ${row['flat_per_tkt']:+8.2f} "
                  f"measured ${row['measured_per_tkt']:+8.2f}/tkt  ${row['flat_per_month']:+8.0f} -> "
                  f"${row['measured_per_month']:+8.0f}/mo  bps in/out {row['mean_bps_in']}/{row['mean_bps_out']} "
                  f"tiers {row['tiers']}", flush=True)
    C.write_json(C.OUT / "cost_reprice.json", out)


if __name__ == "__main__":
    main()
