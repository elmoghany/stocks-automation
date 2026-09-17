"""HARNESS-DIAGNOSTIC, supplementary: what does the LIVE RULE's own instinct
-- "buy the name that is already running" -- pay inside a CAUSAL universe?

The live benchmark (C37F-hf2, -$55/ticket) is WORSE than this frame's
zero-information baseline (-$28.6/ticket, plan/hd_foresight.py).  That gap is
not the harness and it is not the toll: it is the selection rule.  The +10%
gapper pool cannot be used to measure it, because membership in that pool is
conditioned on the day's own regular-session high (EXPERIMENTS-INDEX.md,
"MX-SERIES RETRACTION #2").  So the same instinct is measured here on the
CAUSAL wide universe, where membership was fixed before the open:

    mom      buy the name most extended above its own session open
    rev      buy the name least extended (the mirror)
    vwap_hi  buy the name furthest above VWAP
    vwap_lo  buy the name furthest below VWAP
    rvol     buy the name with the highest relative volume
    random   buy anything

Same engine as the foresight ladder: one position at a time, 7 tickets a day,
$15,000 each, 20%-of-trailing-volume cap, flat 10 bps a side, flat by 15:00.

Usage:  python plan/hd_intraday.py [--hold 30] [--seeds 30]
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_lib as H                                            # noqa: E402
import hd_foresight as FS                                     # noqa: E402


def day_panel(date):
    p = H.npz_panel(date)
    if p is None:
        return None
    syms, o, h, l, c, v = p[0], p[1], p[2], p[3], p[4], p[5]
    cf = H.ffill(c)
    printed = ~np.isnan(c)
    cvol = np.cumsum(np.nan_to_num(v), axis=1)
    cdv = np.cumsum(np.nan_to_num(c) * np.nan_to_num(v), axis=1)
    # session-open reference, guarded: a name whose first regular-session bar
    # has not printed by m has no open yet (plan/cm_lib.Panel.open_ref)
    S = len(syms)
    ao = printed[:, H.RTH_LO:]
    has = ao.any(axis=1)
    first = np.where(has, H.RTH_LO + np.argmax(ao, axis=1), -1)
    ar = np.arange(S)
    op = np.where(first >= 0, o[ar, np.maximum(first, 0)], np.nan)
    opc = np.where(first >= 0, c[ar, np.maximum(first, 0)], np.nan)
    open_px = np.where(np.isfinite(op), op, opc)
    f32 = lambda a: np.asarray(a, np.float32)                  # noqa: E731
    return {"date": date, "syms": syms, "o": f32(o), "c": f32(c),
            "cf": f32(cf), "printed": printed, "cvol": f32(cvol),
            "cdv": f32(cdv), "open_px": f32(open_px), "open_min": first,
            "S": S}


def _openref(P, m, idxs):
    ok = (P["open_min"][idxs] >= 0) & (P["open_min"][idxs] <= m)
    return np.where(ok, P["open_px"][idxs], np.nan)


def sc_mom(P, m, mf, mx, idxs, rng):
    with np.errstate(all="ignore"):
        r = P["cf"][idxs, m] / np.maximum(_openref(P, m, idxs), 1e-9) - 1.0
    return np.nan_to_num(r, nan=-1e9)


def sc_rev(P, m, mf, mx, idxs, rng):
    return -sc_mom(P, m, mf, mx, idxs, rng)


def _vwap(P, m, idxs):
    with np.errstate(all="ignore"):
        b = P["cvol"][idxs, m]
        return np.where(b > 0, P["cdv"][idxs, m] / np.maximum(b, 1e-9), np.nan)


def sc_vwap_hi(P, m, mf, mx, idxs, rng):
    with np.errstate(all="ignore"):
        r = P["cf"][idxs, m] / np.maximum(_vwap(P, m, idxs), 1e-9) - 1.0
    return np.nan_to_num(r, nan=-1e9)


def sc_vwap_lo(P, m, mf, mx, idxs, rng):
    return -sc_vwap_hi(P, m, mf, mx, idxs, rng)


def sc_rvol(P, m, mf, mx, idxs, rng):
    return np.nan_to_num(P["cvol"][idxs, m], nan=-1e9)


def sc_rvol_lo(P, m, mf, mx, idxs, rng):
    return -sc_rvol(P, m, mf, mx, idxs, rng)


SCORERS = {"mom": sc_mom, "rev": sc_rev, "vwap_hi": sc_vwap_hi,
           "vwap_lo": sc_vwap_lo, "rvol_hi": sc_rvol, "rvol_lo": sc_rvol_lo}


def main():
    hold = 30
    seeds = 30
    for i, a in enumerate(sys.argv):
        if a == "--hold":
            hold = int(sys.argv[i + 1])
        if a == "--seeds":
            seeds = int(sys.argv[i + 1])
    dates = H.study_dates()
    panels = [p for p in (day_panel(d) for d in dates) if p is not None]
    print(f"[intra] {len(panels)} panels, hold={hold}m", flush=True)

    res = {"hold": hold, "rows": {}}
    for nm, sc in SCORERS.items():
        pd_ = {P["date"]: FS.run_day(P, hold, sc) for P in panels}
        s = FS.summarize(pd_, nm)
        pd0 = {P["date"]: FS.run_day(P, hold, sc, cost_bps=0.0)
               for P in panels}
        s["per_ticket_nocost"] = FS.summarize(pd0, nm + "0c")["per_ticket"]
        res["rows"][nm] = s
    pts, pts0 = [], []
    for k in range(seeds):
        rng = np.random.default_rng(2000 + k)
        pd_ = {P["date"]: FS.run_day(P, hold, FS.sc_random, rng=rng)
               for P in panels}
        pts.append(FS.summarize(pd_, "r")["per_ticket"])
        rng = np.random.default_rng(2000 + k)
        pd0 = {P["date"]: FS.run_day(P, hold, FS.sc_random, cost_bps=0.0,
                                     rng=rng) for P in panels}
        pts0.append(FS.summarize(pd0, "r")["per_ticket"])
    res["random"] = {"seeds": seeds,
                     "per_ticket_mean": round(float(np.mean(pts)), 2),
                     "per_ticket_sd": round(float(np.std(pts, ddof=1)), 2),
                     "per_ticket_nocost_mean": round(float(np.mean(pts0)), 2),
                     "per_month_at7": round(float(np.mean(pts))
                                            * H.TICKETS_PER_MONTH, 2)}
    rm, rs = res["random"]["per_ticket_mean"], res["random"]["per_ticket_sd"]
    print(f"[intra] {'policy':10s} {'$/tkt':>9s} {'$/tkt@0bps':>11s} "
          f"{'$/mo@7':>11s} {'edge vs rand':>13s} {'z':>6s}", flush=True)
    for nm, s in res["rows"].items():
        e = s["per_ticket"] - rm
        print(f"[intra] {nm:10s} {s['per_ticket']:9.2f} "
              f"{s['per_ticket_nocost']:11.2f} {s['per_month_at7']:11,.0f} "
              f"{e:13.2f} {e/max(rs,1e-9):6.2f}", flush=True)
    print(f"[intra] {'random':10s} {rm:9.2f} "
          f"{res['random']['per_ticket_nocost_mean']:11.2f} "
          f"{res['random']['per_month_at7']:11,.0f}", flush=True)
    H.write(f"intraday_h{hold}.json", res)


if __name__ == "__main__":
    main()
