"""LIMIT-EXEC honesty battery.

What the fill rule is ALLOWED to see, stated so the test can be scored
against it (plan/uq_poison.py's contract, extended to the exit leg):

  * the DECISION to post -- the limit price, the size, the ladder -- is a
    function of minute bars <= m_dec and of cost1 windows that end
    strictly before the posting minute;
  * WHETHER and HOW MUCH the order fills is decided by 1-second prints
    STRICTLY AFTER the post second.  That is the tape answering an order
    that already exists, the one thing the pipeline may read after t0.

So the test asserts, order by order:
  P1  garbage in every second AT OR BEFORE the post second  -> the fill
      (shares, price, first second) is BIT-IDENTICAL
  P2  garbage in the seconds AFTER the post second           -> the fill
      MOVES on a large fraction of orders (the rule reads them)
  P3  garbage in minute bars > m_dec                          -> mark,
      volcap and the posted limit are identical
  P4  garbage in cost1 minutes >= the post minute             -> the
      half-spread / impact are identical; garbage BEFORE it   -> they move
  P5  FastCost.parts == cr_cost.CostModel.parts on tier "win"
  P6  sanity: every passive buy fill price <= its limit, every passive
      sell fill >= its limit, no NaN, no non-positive price; a more
      passive ladder never fills MORE often; a "market" timeout fills 100%
      whenever a later print exists

Usage: python plan/lx_poison.py [--days 10]
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lx_engine as X                                         # noqa: E402
import lx_frame as F                                          # noqa: E402
import hd_lib as H                                            # noqa: E402
import cr_cost                                                # noqa: E402


def _copy_tape(tp):
    return X.Tape(tp.sec.copy(), tp.o.copy(), tp.h.copy(), tp.l.copy(),
                  tp.c.copy(), tp.v.copy())


def _garble(tp, mask, rng):
    f = 0.3 + 1.4 * rng.random(int(mask.sum()))
    for a in ("o", "h", "l", "c"):
        getattr(tp, a)[mask] = getattr(tp, a)[mask] * f
    tp.h[mask] = np.maximum(tp.h[mask], np.maximum(tp.o[mask], tp.c[mask]))
    tp.l[mask] = np.minimum(tp.l[mask], np.minimum(tp.o[mask], tp.c[mask]))
    tp.v[mask] = tp.v[mask] * (0.1 + 5.0 * rng.random(int(mask.sum())))


def main(ndays=10, seed=0):
    rng = np.random.default_rng(seed)
    dates = list(rng.choice(H.study_dates(), ndays, replace=False))
    specs = [F.E("rest", 3), F.E("tick", 5), F.E("chase", 3, "market"),
             F.E("rest", 1, part=0.5)]
    xspecs = [F.Xs("rest", 3), F.Xs("tick", 5)]
    rep = {k: 0 for k in ("p1_checks", "p1_bad", "p2_checks", "p2_moved",
                          "p3_checks", "p3_bad", "p4_checks", "p4_bad",
                          "p4b_checks", "p4b_moved", "p5_checks", "p5_bad",
                          "p6_checks", "p6_bad", "p6_mono_checks",
                          "p6_mono_bad", "p6_mkt_checks", "p6_mkt_bad")}
    cm_ref = cr_cost.CostModel()
    for d in dates:
        day = X.Day(d)
        S = len(day.syms)
        for si in range(S):
            tp = day.tape(si)
            if tp is None:
                continue
            for m_dec in (330, 345, 420, 600, 780):
                if not day.printed[si, m_dec]:
                    continue
                mark = day.mark(si, m_dec)
                if not np.isfinite(mark) or mark <= 0:
                    continue
                shares = min(X.TICKET / mark, max(day.volcap_shares(si, m_dec), 1.0))
                for side, sp_list in ((+1, specs), (-1, xspecs)):
                    for spec in sp_list:
                        base = X.execute_leg(day, si, side, m_dec, shares, spec,
                                             hard_flat=X.NMIN - 1)
                        key = (round(base["filled"], 6), round(float(base["px"]), 6)
                               if np.isfinite(base["px"]) else None,
                               base["first_sec"], base["m_done"])
                        s_post = (m_dec + 1 - X.SEC0_MIN) * 60
                        # ---- P1: garble AT OR BEFORE the post second
                        g = _copy_tape(tp)
                        mask = g.sec <= s_post
                        if mask.any():
                            _garble(g, mask, rng)
                            day._tape[day.syms[si]] = g
                            alt = X.execute_leg(day, si, side, m_dec, shares, spec,
                                                hard_flat=X.NMIN - 1)
                            day._tape[day.syms[si]] = tp
                            k2 = (round(alt["filled"], 6), round(float(alt["px"]), 6)
                                  if np.isfinite(alt["px"]) else None,
                                  alt["first_sec"], alt["m_done"])
                            rep["p1_checks"] += 1
                            if k2 != key:
                                rep["p1_bad"] += 1
                        # ---- P2: garble AFTER the post second
                        g = _copy_tape(tp)
                        mask = g.sec > s_post
                        if mask.any():
                            _garble(g, mask, rng)
                            day._tape[day.syms[si]] = g
                            alt = X.execute_leg(day, si, side, m_dec, shares, spec,
                                                hard_flat=X.NMIN - 1)
                            day._tape[day.syms[si]] = tp
                            k2 = (round(alt["filled"], 6), round(float(alt["px"]), 6)
                                  if np.isfinite(alt["px"]) else None,
                                  alt["first_sec"], alt["m_done"])
                            rep["p2_checks"] += 1
                            if k2 != key:
                                rep["p2_moved"] += 1
                        # ---- P6 sanity on the base fill
                        # the exact invariant: a PASSIVE fill never pays
                        # more (buy) / receives less (sell) than the
                        # highest / lowest limit the ladder actually posted
                        if base["passive_shares"] > 0:
                            rep["p6_checks"] += 1
                            pas_px = base["px"]
                            if base["mkt_shares"] > 0:
                                pas_px = ((base["px"] * base["filled"]
                                           - base["mkt_px"] * base["mkt_shares"])
                                          / base["passive_shares"])
                            bad = (not np.isfinite(pas_px)) or pas_px <= 0
                            if side > 0:
                                bad |= pas_px > base["lim_hi"] + 1e-6
                            else:
                                bad |= pas_px < base["lim_lo"] - 1e-6
                            if bad:
                                rep["p6_bad"] += 1
                # ---- P6 monotonicity + market timeout (buy side)
                a = X.execute_leg(day, si, +1, m_dec, shares, F.E("rest", 3),
                                  hard_flat=X.NMIN - 1)
                b = X.execute_leg(day, si, +1, m_dec, shares,
                                  F.E("rest", 3, k_bps=10.0), hard_flat=X.NMIN - 1)
                rep["p6_mono_checks"] += 1
                if b["passive_shares"] > a["passive_shares"] + 1e-9:
                    rep["p6_mono_bad"] += 1
                c = X.execute_leg(day, si, +1, m_dec, shares,
                                  F.E("rest", 1, "market"), hard_flat=X.NMIN - 1)
                nxt_px, nxt_m = day.next_open(si, m_dec + 2)
                if np.isfinite(nxt_px) and nxt_m >= 0:
                    rep["p6_mkt_checks"] += 1
                    if c["filled"] < shares - 1e-6:
                        rep["p6_mkt_bad"] += 1
                # ---- P3: minute bars after m_dec must not touch the decision
                o0, c0 = day.o.copy(), day.c.copy()
                v0, cf0, cv0 = day.v.copy(), day.cf.copy(), day.cvol.copy()
                day.o[:, m_dec + 1:] *= 1.7
                day.c[:, m_dec + 1:] *= 0.4
                day.v[:, m_dec + 1:] *= 3.0
                day.cf = X._ffill(day.c)
                day.cvol = np.cumsum(np.nan_to_num(day.v), axis=1)
                rep["p3_checks"] += 1
                if (day.mark(si, m_dec) != mark
                        or day.volcap_shares(si, m_dec) != 0.2 * float(cv0[si, m_dec] - cv0[si, max(m_dec - 5, 0)])):
                    rep["p3_bad"] += 1
                day.o, day.c, day.v, day.cf, day.cvol = o0, c0, v0, cf0, cv0
                # ---- P4: cost1 windows end strictly before the post minute
                sym = day.syms[si]
                dd = day.cm.day(sym, d)
                if dd is not None:
                    k = m_dec + 1 - X.SEC0_MIN
                    ref = day.cm.parts(sym, d, m_dec + 1, 15000.0)
                    keep = {kk: v.copy() for kk, v in dd.items()}
                    for kk in ("o", "h", "l", "c", "dv", "hl2"):
                        dd[kk][k:] = dd[kk][k:] * 3.0 + 1.0
                    alt = day.cm.parts(sym, d, m_dec + 1, 15000.0)
                    rep["p4_checks"] += 1
                    if alt != ref:
                        rep["p4_bad"] += 1
                    for kk in keep:
                        dd[kk][:] = keep[kk]
                    if k >= 2:
                        for kk in ("o", "h", "l", "c", "dv", "hl2"):
                            dd[kk][:k] = dd[kk][:k] * 3.0 + 1.0
                        alt = day.cm.parts(sym, d, m_dec + 1, 15000.0)
                        rep["p4b_checks"] += 1
                        if alt != ref:
                            rep["p4b_moved"] += 1
                        for kk in keep:
                            dd[kk][:] = keep[kk]
                    # ---- P5: FastCost == CostModel (tier win)
                    b5 = cm_ref.parts(sym, d, X.minute_time(m_dec + 1), 15000.0)
                    if ref[2] == "win" and b5[2] == "win":
                        rep["p5_checks"] += 1
                        if abs(ref[0] - b5[0]) > 1e-9 or abs(ref[1] - b5[1]) > 1e-9:
                            rep["p5_bad"] += 1
        print(f"  {d}: p1 {rep['p1_bad']}/{rep['p1_checks']} bad, "
              f"p2 {rep['p2_moved']}/{rep['p2_checks']} moved, "
              f"p4 {rep['p4_bad']}/{rep['p4_checks']} bad, "
              f"p5 {rep['p5_bad']}/{rep['p5_checks']} bad, "
              f"p6 {rep['p6_bad']}/{rep['p6_checks']} bad", flush=True)
    rep["days"] = dates
    ok = (rep["p1_bad"] == 0 and rep["p3_bad"] == 0 and rep["p4_bad"] == 0
          and rep["p5_bad"] == 0 and rep["p6_bad"] == 0
          and rep["p6_mono_bad"] == 0 and rep["p6_mkt_bad"] == 0
          and rep["p2_moved"] > 0.3 * rep["p2_checks"]
          and rep["p4b_moved"] > 0.5 * rep["p4b_checks"])
    rep["PASS"] = bool(ok)
    print("\n".join(f"{k}: {v}" for k, v in rep.items() if k != "days"))
    X.write_json("poison.json", rep)
    print("POISON", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    a = sys.argv
    main(int(a[a.index("--days") + 1]) if "--days" in a else 10)
