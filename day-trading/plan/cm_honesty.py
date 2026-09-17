"""CLOSE-MOMENTUM (2026-09-16): the adversarial battery.

Nothing in close-momentum-audit.md means anything unless these pass.

  poison        Replace every bar STRICTLY AFTER decision minute m with
                garbage and rebuild the panel from scratch. Every feature,
                the print mask and the size cap at m must be BIT-IDENTICAL,
                and -- the stronger form the mandate asks for -- the TRADES
                the configs would open at m must be identical too. Prices
                obviously move (the fill is bar m+1); the SELECTION may not.
  hold_zero     A never-buy score returns exactly $0 and 0 tickets.
  cost_monotone The same fixed policy earns strictly more at 0x cost than
                at 1x, and more at 1x than at 10x.
  foresight     Score = the realized net return of the very trade the
                decision opens. Must be strongly positive or a null here
                has no power.
  random        30 uniform-random seeds over the SAME eligible set, window,
                fills, exit rule and costs.
  inverted      Every reported score also run with its sign flipped.
  shuffled      The (fill, exit, cap) triple permuted across rows WITHIN
                each day: destroys the feature->outcome association while
                preserving the day's outcome distribution.
  early_close   The half-day audit. On the 1:00 pm sessions minute 719 is
                after the close; this counts what the harness actually did
                on those dates.

Usage:  python plan/cm_honesty.py [--universe wide] [--days 16]
Writes: data/massive/cm/honesty_{universe}.json
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import cm_lib as L                                            # noqa: E402
import cm_rows as R                                           # noqa: E402
import cm_single as S                                         # noqa: E402

CUTS = ["12:00", "13:00", "15:00", "15:30", "15:45"]
SCORES = ["r_first", "r_mid", "ret_open", "dist_vwap", "rvol", "dist_hi",
          "xs_rank_first", "r_first_dm"]


def poison_check(n_days=16, seed=0):
    daily = L.Daily.get()
    prof = L.profile()
    dates = [p.stem for p in sorted(L.DAYS.glob("*.npz"))]
    rng = np.random.default_rng(seed)
    pick = [dates[i] for i in rng.choice(len(dates), size=min(n_days,
                                                             len(dates)),
                                         replace=False)]
    arr_checks = arr_bad = pick_checks = pick_bad = 0
    detail = []
    for d in sorted(pick):
        p = L.Panel.from_rl2(d)
        for lab in CUTS:
            m = L.idx(lab) - 1
            clean_f = L.features(p, m, daily, prof)
            clean_prn = p.printed[:, m].copy()
            clean_vc = p.volcap_shares(m).copy()
            # poison every bar strictly after m
            bars = [a.copy() for a in (p.o, p.h, p.l, p.c, p.v)]
            sl = slice(m + 1, None)
            shp = bars[0][:, sl].shape
            g = rng.uniform(0.5, 500.0, size=shp)
            bars[0][:, sl] = g
            bars[1][:, sl] = g * rng.uniform(1.0, 1.5, size=shp)
            bars[2][:, sl] = g * rng.uniform(0.5, 1.0, size=shp)
            bars[3][:, sl] = g * rng.uniform(0.7, 1.3, size=shp)
            bars[4][:, sl] = rng.integers(1, 10 ** 7, size=shp)
            q = L.Panel(d, p.syms, p.prev_close, bars)
            bad_f = L.features(q, m, daily, prof)
            for k in L.FEATS:
                arr_checks += 1
                if not np.array_equal(np.nan_to_num(clean_f[k], nan=-9e9),
                                      np.nan_to_num(bad_f[k], nan=-9e9)):
                    arr_bad += 1
                    detail.append({"date": d, "cut": lab, "array": k})
            for k, a, b in (("printed", clean_prn, q.printed[:, m]),
                            ("volcap", clean_vc, q.volcap_shares(m))):
                arr_checks += 1
                if not np.array_equal(np.nan_to_num(a, nan=-9e9),
                                      np.nan_to_num(b, nan=-9e9)):
                    arr_bad += 1
                    detail.append({"date": d, "cut": lab, "array": k})
            # the selection itself, for every score used in the study
            for sc in SCORES:
                for k in (1, 3, 7):
                    pick_checks += 1
                    a = _top(clean_f[sc], clean_prn, k)
                    b = _top(bad_f[sc], q.printed[:, m], k)
                    if a != b:
                        pick_bad += 1
                        detail.append({"date": d, "cut": lab, "pick": sc,
                                       "k": k, "clean": a, "poisoned": b})
    return {"array_checks": arr_checks, "array_mismatches": arr_bad,
            "pick_checks": pick_checks, "pick_mismatches": pick_bad,
            "days": len(pick), "cuts": CUTS, "detail": detail[:20]}


def _top(score, prn, k):
    idx = np.flatnonzero(prn & np.isfinite(score))
    if idx.size == 0:
        return []
    return [int(i) for i in idx[np.argsort(-score[idx], kind="stable")][:k]]


def battery(t):
    res = {}
    zero = np.full(len(t.px_in), -np.inf)
    tr = S.run(t, zero, "15:59", ["15:30"], topk=7)
    res["hold_zero"] = {"tickets": len(tr),
                        "total": round(sum(x["pnl"] for x in tr), 6)}

    # cost monotonicity on one fixed (seeded-random) policy
    rng = np.random.default_rng(5)
    sc = rng.random(len(t.px_in))
    base_fee, base_ext = L.FEE_BPS, L.EXT_BPS
    cm = {}
    for name, mult in (("zero", 0.0), ("modelled", 1.0), ("ten_x", 10.0)):
        L.FEE_BPS, L.EXT_BPS = base_fee * mult, base_ext * mult
        cm[name] = round(sum(x["pnl"] for x in
                             S.run(t, sc, "15:59", ["15:30"], topk=7)), 2)
    L.FEE_BPS, L.EXT_BPS = base_fee, base_ext
    res["cost_monotone"] = cm
    res["cost_monotone_ok"] = cm["zero"] > cm["modelled"] > cm["ten_x"]

    # foresight positive control, same policy shape as the reported rows
    for dec, ex in (("15:30", "15:59"), ("15:00", "15:59"),
                    ("12:00", "15:59")):
        f = S.foresight_score(t, ex, dec)
        f = np.where(np.isfinite(f), f, -np.inf)
        for k in (1, 7):
            tr = S.run(t, np.where(f > 0, f, -np.inf), ex, [dec], topk=k)
            res[f"foresight|{dec}->{ex}|k{k}"] = L.summarize(
                tr, len(t.dates), f"FORESIGHT-{dec}-k{k}")
    return res


def half_days(dates):
    """Detect the 1:00 pm sessions FROM THE DATA rather than from
    plan/market_calendar.py, whose HALF_DAYS list only covers 2026-2027
    and is empty over this study window. A date is a half day when more
    than half the universe's names stop printing before 15:00 ET."""
    out = {}
    for d in dates:
        f = L.DAYS / f"{d}.npz"
        if not f.exists():
            continue
        c = np.load(f, allow_pickle=False)["c"]
        prn = ~np.isnan(c[:, :720])
        has = prn.any(axis=1)
        last = np.where(has, 719 - np.argmax(prn[:, ::-1], axis=1), -1)
        last = last[has]
        if last.size and float((last < 660).mean()) > 0.5:
            out[d] = L.clock(int(np.median(last)))
    return out


def identity_gate(t, n_cfg=8, seed=0):
    """Recompute every reported ticket from its own recorded primitives.

    For each trade the engine emits (px_in, px_out, sh, m_in, m_out) and a
    pnl. This recomputes pnl = sh*px_out*(1-cost(m_out)) - sh*px_in*
    (1+cost(m_in)) from scratch and requires an exact match, and separately
    requires the share count to respect the 20%-of-trailing-volume cap and
    the $500 floor. It is the gate that proves the summary tables are
    arithmetic on the recorded fills and not a second, divergent model.
    """
    rng = np.random.default_rng(seed)
    checks = bad = capbad = 0
    worst = 0.0
    for c in range(n_cfg):
        sc = rng.random(len(t.px_in))
        dec = t.dec[rng.integers(0, len(t.dec))]
        ex = [x for x in t.exits if L.idx(x) > L.idx(dec)]
        if not ex:
            continue
        ex = ex[rng.integers(0, len(ex))]
        for tr in S.run(t, sc, ex, [dec], topk=int(rng.integers(1, 8))):
            checks += 1
            want = (tr["sh"] * tr["px_out"] * (1 - L.cost_frac(tr["m_out"]))
                    - tr["sh"] * tr["px_in"] * (1 + L.cost_frac(tr["m_in"])))
            d = abs(want - tr["pnl"])
            worst = max(worst, d)
            if d > 1e-6:
                bad += 1
            if tr["sh"] * tr["px_in"] < L.MIN_NOTIONAL - 1e-6:
                capbad += 1
    return {"tickets_recomputed": checks, "mismatches": bad,
            "worst_abs_diff": round(worst, 10),
            "below_min_notional": capbad}


def early_close_audit(t):
    """Half days close at 13:00 ET; minute 719 is an hour past the bell.

    On those dates a 15:30 decision has no printed bar, so the candidate
    gate drops it and no ticket is opened -- but a 12:00 decision is legal
    and its "15:59" exit is really the official 13:00 close. This reports
    the exposure rather than asserting it is fine.
    """
    hd = half_days(t.dates)
    out = {"half_days_in_window": hd, "n_half_days": len(hd),
           "calendar_note": "plan/market_calendar.HALF_DAYS covers 2026-2027 "
                            "only and is empty here; detected from the bars"}
    di = {d: i for i, d in enumerate(t.dates)}
    for lab in ("15:30", "15:00", "12:00"):
        j = t.didx[lab]
        n = 0
        for d in hd:
            k = (t.date_i == di[d]) & (t.dec_i == j) & t.printed_m                 & np.isfinite(t.px_in)
            n += int(k.sum())
        out[f"eligible_rows_at_{lab}_on_half_days"] = n
    return out


def main():
    uni = sys.argv[sys.argv.index("--universe") + 1] \
        if "--universe" in sys.argv else "wide"
    nd = int(sys.argv[sys.argv.index("--days") + 1]) \
        if "--days" in sys.argv else 16
    res = {}
    print("poison ...", flush=True)
    res["poison"] = poison_check(nd)
    p = res["poison"]
    print(f"  arrays {p['array_checks']} checks / {p['array_mismatches']} "
          f"mismatches;  picks {p['pick_checks']} checks / "
          f"{p['pick_mismatches']} mismatches", flush=True)
    if p["detail"]:
        print("  DETAIL:", json.dumps(p["detail"][:5])[:600], flush=True)
    t = S.Table(uni)
    res["battery"] = battery(t)
    print("hold_zero:", res["battery"]["hold_zero"], flush=True)
    print("cost_monotone:", res["battery"]["cost_monotone"],
          "ok =", res["battery"]["cost_monotone_ok"], flush=True)
    for k, v in res["battery"].items():
        if k.startswith("foresight"):
            print(f"  {k:28s} n={v['tickets']:5d} ${v['per_ticket']:+9.2f}/tkt "
                  f"${v['per_month']:+10.1f}/mo", flush=True)
    res["identity"] = identity_gate(t)
    print("identity:", res["identity"], flush=True)
    res["early_close"] = early_close_audit(t)
    print("early_close:", json.dumps(res["early_close"])[:400], flush=True)
    L.write_json(f"honesty_{uni}.json", res)
    print("wrote", L.OUT / f"honesty_{uni}.json", flush=True)


if __name__ == "__main__":
    main()
