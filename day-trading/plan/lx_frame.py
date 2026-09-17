"""LIMIT-EXEC stage 1: the zero-information frame under end-to-end limit
execution.

THE FRAME is plan/hd_foresight.py's, unchanged: causal wide universe
(plan/rl2/out/days), one position at a time, <= 7 tickets a day, $15,000 a
ticket, 20%-of-trailing-5-minute-volume cap, decisions every minute from
09:30, everything flat by 15:00, hold H minutes.  Its zero-information
baseline is -$28.6 per ticket at the flat 10 bps a side and ~$0 at zero
cost -- i.e. the toll and nothing else.

IDENTITY FIRST.  `--stage ident` runs the incumbent market ticket (entry at
the open of m+1, exit at the close of m+1+H, 10 bps a side) through THIS
module's ticket code and asserts it reproduces hd_foresight.run_day seed
for seed, ticket for ticket.  Only then are the ladders believed.

THEN THE LADDERS.  The same random pick (30 seeds), the same schedule, the
same cap -- only the FILL changes:
    entry  rest at the estimated bid / at the last print, cancel or go
           marketable after N minutes; tick up toward the ask; chase
    exit   rest at the estimated ask, tick down toward the bid over M
           minutes, marketable at the end; and always marketable at the
           15:00 flatten
Every ticket carries its P&L under the flat, measured and zero cost
conventions and its own market counterfactual, so the change from -$28.6
can be decomposed into fee saved, price improvement, adverse selection and
the tickets that were never taken.

CONTROLS.  Perfect-foresight and anti-foresight pickers under the same
ladders (the ceiling must stay monotone and the engine must still make
money when information is present), and the poison test in
plan/lx_poison.py.

Usage:
  python plan/lx_frame.py --stage ident  [--limit N]
  python plan/lx_frame.py --stage ladder [--seeds 30] [--limit N] [--workers 2]
"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lx_engine as X                                         # noqa: E402
import hd_lib as H                                            # noqa: E402

START_K = H.idx("09:30")
FLAT_K = H.idx("15:00")
MAX_TICKETS = 7
HOLD = 30

# ------------------------------------------------------------ ladder specs
E_MKT = None
X_MKT = None


def E(mode, wait, on_timeout="cancel", part=1.0, k_bps=0.0, through=0.0,
      range_share=True):
    return dict(mode=mode, wait=wait, on_timeout=on_timeout, part=part,
                k_bps=k_bps, through=through, range_share=range_share)


def Xs(mode, wait, part=1.0, k_bps=0.0, through=0.0, range_share=True):
    return dict(mode=mode, wait=wait, on_timeout="market", part=part,
                k_bps=k_bps, through=through, range_share=range_share)


# name -> (entry spec, exit spec).  Stage A isolates the ENTRY (market
# exit), stage B isolates the EXIT (market entry), stage C is end-to-end.
CONFIGS = {
    "mkt/mkt": (E_MKT, X_MKT),
    # ---- A: entry ladders, incumbent market exit
    "bid-rest1-cancel/mkt": (E("rest", 1), X_MKT),
    "bid-rest3-cancel/mkt": (E("rest", 3), X_MKT),
    "bid-rest5-cancel/mkt": (E("rest", 5), X_MKT),
    "bid-rest10-cancel/mkt": (E("rest", 10), X_MKT),
    "bid-rest1-mkt/mkt": (E("rest", 1, "market"), X_MKT),
    "bid-rest3-mkt/mkt": (E("rest", 3, "market"), X_MKT),
    "bid-rest5-mkt/mkt": (E("rest", 5, "market"), X_MKT),
    "mid-rest1-cancel/mkt": (E("mid", 1), X_MKT),
    "mid-rest3-cancel/mkt": (E("mid", 3), X_MKT),
    "tick3-cancel/mkt": (E("tick", 3), X_MKT),
    "tick5-cancel/mkt": (E("tick", 5), X_MKT),
    "tick10-cancel/mkt": (E("tick", 10), X_MKT),
    "tick3-mkt/mkt": (E("tick", 3, "market"), X_MKT),
    "tick5-mkt/mkt": (E("tick", 5, "market"), X_MKT),
    "chase3-cancel/mkt": (E("chase", 3), X_MKT),
    "chase5-cancel/mkt": (E("chase", 5), X_MKT),
    "chase5-mkt/mkt": (E("chase", 5, "market"), X_MKT),
    # ---- B: exit ladders, incumbent market entry
    "mkt/ask-rest1": (E_MKT, Xs("rest", 1)),
    "mkt/ask-rest3": (E_MKT, Xs("rest", 3)),
    "mkt/ask-rest5": (E_MKT, Xs("rest", 5)),
    "mkt/tick3": (E_MKT, Xs("tick", 3)),
    "mkt/tick5": (E_MKT, Xs("tick", 5)),
    "mkt/tick10": (E_MKT, Xs("tick", 10)),
    "mkt/chase5": (E_MKT, Xs("chase", 5)),
    # ---- C: end-to-end
    "bid-rest1-cancel/ask-rest1": (E("rest", 1), Xs("rest", 1)),
    "bid-rest3-cancel/ask-rest3": (E("rest", 3), Xs("rest", 3)),
    "bid-rest5-cancel/ask-rest5": (E("rest", 5), Xs("rest", 5)),
    "bid-rest3-mkt/tick3": (E("rest", 3, "market"), Xs("tick", 3)),
    "tick3-cancel/tick3": (E("tick", 3), Xs("tick", 3)),
    "tick5-cancel/tick5": (E("tick", 5), Xs("tick", 5)),
    "tick5-mkt/tick5": (E("tick", 5, "market"), Xs("tick", 5)),
    "chase5-cancel/chase5": (E("chase", 5), Xs("chase", 5)),
    "mid-rest3-cancel/tick5": (E("mid", 3), Xs("tick", 5)),
    # ---- sensitivities on the headline end-to-end shape
    "bid-rest3-cancel/ask-rest3|part0.5": (E("rest", 3, part=0.5), Xs("rest", 3, part=0.5)),
    "bid-rest3-cancel/ask-rest3|through1c": (E("rest", 3, through=0.01), Xs("rest", 3, through=0.01)),
    "bid-rest3-cancel/ask-rest3|touch": (E("rest", 3, part=1e12, range_share=False),
                                         Xs("rest", 3, part=1e12, range_share=False)),
    "bid+5-rest3-cancel/ask+5-rest3": (E("rest", 3, k_bps=5.0), Xs("rest", 3, k_bps=5.0)),
}


# ------------------------------------------------------------- one day
def run_day(day, hold, scorer, entry, exit_, rng=None, max_tickets=MAX_TICKETS,
            flat=FLAT_K, hd_identity=False):
    """One position at a time.  Returns (records, attempts)."""
    out = []
    attempts = 0
    m = START_K
    S = len(day.syms)
    while len(out) < max_tickets:
        mf = m + 1
        if hd_identity:
            mx = mf + hold
            if mx > flat:
                break
            avail = (day.printed[:, m] & np.isfinite(day.o[:, mf])
                     & (day.o[:, mf] > 0) & np.isfinite(day.cf[:, mx])
                     & (day.cf[:, mx] > 0))
        else:
            if mf + hold > flat:
                break
            avail = day.printed[:, m].copy()
            for si in np.flatnonzero(avail):
                if not day.has_tape(si):
                    avail[si] = False
        if not avail.any():
            m += 1
            continue
        idxs = np.flatnonzero(avail)
        s = scorer(day, m, mf, hold, idxs, rng)
        si = int(idxs[int(np.argmax(s))])
        attempts += 1
        if hd_identity:
            # hd_foresight sizes on the FILL open and exits at cf[mf+hold]
            px_in = float(day.o[si, mf])
            cap = day.volcap_shares(si, m)
            sh = X.TICKET / px_in
            if np.isfinite(cap) and cap > 0:
                sh = min(sh, cap)
            if sh * px_in < X.MIN_NOTIONAL:
                m = mf
                continue
            px_out = float(day.cf[si, mf + hold])
            cfi = X.FEE_BPS / 1e4
            pnl = sh * px_out * (1 - cfi) - sh * px_in * (1 + cfi)
            out.append({"date": day.date, "sym": day.syms[si], "m_dec": m,
                        "pnl": {"flat": float(pnl), "flat_all": float(pnl),
                                "zero": float(sh * (px_out - px_in)),
                                "meas": np.nan},
                        "notional": sh * px_in, "e_passive_frac": 0.0,
                        "x_passive_frac": 0.0, "dec": {},
                        "cost_bps": {"e_flat": 10, "x_flat": 10,
                                     "e_meas": np.nan, "x_meas": np.nan}})
            m = mf + hold
            continue
        rec = X.ticket(day, si, m, hold, entry, exit_, flat)
        if rec is None:
            # attempt spent; the account was busy for the entry window
            m = mf + (entry["wait"] if entry else 0)
            continue
        out.append(rec)
        m = max(rec["m_out"], mf)
        if rec["exit"]["m_done"] >= 0:
            m = max(m, rec["exit"]["m_done"])
    return out, attempts


def sc_random(day, m, mf, hold, idxs, rng):
    return rng.random(idxs.size)


def sc_foresight(day, m, mf, hold, idxs, rng):
    """Perfect knowledge of the MARKET path: the forward return from the
    open of m+1 to the close of m+1+H.  Under a limit ladder this is the
    information a perfect forecaster would act on; the fill is still
    decided by the tape."""
    px_in = day.o[idxs, mf]
    px_out = day.cf[idxs, min(mf + hold, X.NMIN - 1)]
    r = px_out / px_in - 1.0
    return np.where(np.isfinite(r), r, -np.inf)


def sc_anti(day, m, mf, hold, idxs, rng):
    r = sc_foresight(day, m, mf, hold, idxs, rng)
    return np.where(np.isfinite(r), -r, -np.inf)


# ------------------------------------------------------------ the passes
def _day_worker(args):
    date, names, seeds, hold, with_fore, ident = args
    import lx_engine as XX
    try:
        day = XX.Day(date)
    except Exception as e:
        return date, None, str(e)
    res = {}
    for nm in names:
        entry, exit_ = CONFIGS[nm]
        for s in range(seeds):
            rng = np.random.default_rng(1000 + s)
            recs, att = run_day(day, hold, sc_random, entry, exit_, rng=rng,
                                hd_identity=ident)
            res[(nm, f"rand{s}")] = (recs, att)
        if with_fore:
            recs, att = run_day(day, hold, sc_foresight, entry, exit_)
            res[(nm, "fore")] = (recs, att)
            recs, att = run_day(day, hold, sc_anti, entry, exit_)
            res[(nm, "anti")] = (recs, att)
    return date, res, None


def run_pass(dates, names, seeds, hold=HOLD, with_fore=False, workers=2,
             ident=False, tag=""):
    args = [(d, names, seeds, hold, with_fore, ident) for d in dates]
    acc = {}
    att = {}
    t0 = time.monotonic()
    done = 0
    it = Pool(workers).imap_unordered(_day_worker, args, chunksize=4) \
        if workers > 1 else map(_day_worker, args)
    for date, res, err in it:
        done += 1
        if err:
            print(f"  !! {date}: {err}", flush=True)
            continue
        for k, (recs, a) in res.items():
            acc.setdefault(k, []).extend(recs)
            att[k] = att.get(k, 0) + a
        if done % 50 == 0 or done == len(dates):
            el = time.monotonic() - t0
            print(f"  [{tag}] {done}/{len(dates)} days  {el/60:.1f} min",
                  flush=True)
    return acc, att


def _agg(acc, att, names, seeds, ndays, with_fore):
    rows = {}
    for nm in names:
        r = {"config": nm}
        for key in ("flat", "meas", "zero"):
            pts = [X.summarize(acc.get((nm, f"rand{s}"), []), ndays, key)
                   for s in range(seeds)]
            pt = np.array([p["per_ticket"] for p in pts])
            pm = np.array([p["per_month"] for p in pts])
            r[key] = {"per_ticket_mean": round(float(np.nanmean(pt)), 2),
                      "per_ticket_sd": round(float(np.nanstd(pt, ddof=1)), 2)
                      if seeds > 1 else 0.0,
                      "per_month_mean": round(float(np.nanmean(pm)), 1),
                      "months_pos": pts[0]["months_pos"],
                      "ex_best": pts[0]["ex_best"],
                      "aug2026": pts[0]["aug2026"]}
        allrecs = [x for s in range(seeds) for x in acc.get((nm, f"rand{s}"), [])]
        tot_att = sum(att.get((nm, f"rand{s}"), 0) for s in range(seeds))
        r["fills"] = X.fill_stats(allrecs, tot_att)
        r["tickets_per_day"] = round(len(allrecs) / max(seeds * ndays, 1), 3)
        r["decomp"] = X.decomposition(allrecs)
        # market counterfactual on the SAME names/decisions
        mk = [x["mkt"]["pnl_flat"] for x in allrecs if x.get("mkt")]
        r["mkt_counterfactual_flat"] = round(float(np.mean(mk)), 2) if mk else None
        r["mkt_counterfactual_zero"] = round(float(np.mean(
            [x["mkt"]["pnl_zero"] for x in allrecs if x.get("mkt")])), 2) if mk else None
        if with_fore:
            for lab in ("fore", "anti"):
                rr = acc.get((nm, lab), [])
                r[lab] = {k: X.summarize(rr, ndays, k)["per_ticket"]
                          for k in ("flat", "meas", "zero")}
                r[lab]["tickets_per_day"] = round(len(rr) / max(ndays, 1), 2)
        rows[nm] = r
    return rows


def stage_ident(limit=None, seeds=30):
    import hd_foresight as HF
    dates = H.study_dates()
    if limit:
        dates = dates[:limit]
    n_chk = n_bad = 0
    worst = 0.0
    for d in dates:
        P = HF.day_panel(d)
        if P is None:
            continue
        day = X.Day(d)
        for s in range(seeds):
            a = HF.run_day(P, HOLD, HF.sc_random,
                           rng=np.random.default_rng(1000 + s))
            b, _ = run_day(day, HOLD, sc_random, None, None,
                           rng=np.random.default_rng(1000 + s),
                           hd_identity=True)
            bb = [r["pnl"]["flat"] for r in b]
            n_chk += 1
            if len(a) != len(bb):
                n_bad += 1
                continue
            dd = max([abs(x - y) for x, y in zip(a, bb)] + [0.0])
            worst = max(worst, dd)
            if dd > 0.05:
                n_bad += 1
        for nm, sc_a, sc_b in (("fore", HF.sc_foresight, sc_foresight),
                               ("anti", HF.sc_antiforesight, sc_anti)):
            a = HF.run_day(P, HOLD, sc_a)
            b, _ = run_day(day, HOLD, sc_b, None, None, hd_identity=True)
            bb = [r["pnl"]["flat"] for r in b]
            n_chk += 1
            if len(a) != len(bb) or max([abs(x - y) for x, y in zip(a, bb)] + [0.0]) > 0.05:
                n_bad += 1
    rep = {"days": len(dates), "checks": n_chk, "mismatches": n_bad,
           "worst_abs_diff": worst}
    print(f"IDENT vs hd_foresight: {n_chk} day-policy checks over "
          f"{len(dates)} days, {n_bad} mismatches, worst ${worst:.4f}")
    X.write_json("frame_ident.json", rep)
    if n_bad:
        raise SystemExit("IDENTITY GATE FAILED")


def stage_ladder(seeds=30, limit=None, workers=2, names=None, hold=HOLD,
                 with_fore=True, tag="ladder"):
    dates = H.study_dates()
    if limit:
        dates = dates[:limit]
    names = names or list(CONFIGS)
    print(f"[{tag}] {len(dates)} days, {len(names)} configs, {seeds} seeds, "
          f"hold {hold}", flush=True)
    acc, att = run_pass(dates, names, seeds, hold, with_fore, workers, tag=tag)
    rows = _agg(acc, att, names, seeds, len(dates), with_fore)
    print(f"\n{'config':40s} {'fill':>6} {'tk/d':>5} {'flat $/tkt':>11} "
          f"{'meas':>8} {'zero':>8} {'mktCF':>8} {'e:pi/mo':>12} {'x:pi/mo':>12}"
          f" {'fore':>8} {'anti':>8}")
    for nm in names:
        r = rows[nm]
        d = r["decomp"]
        e = d.get("e", {})
        x = d.get("x", {})
        fe = f"{e.get('pi_bps_mean', 0):+.1f}/{e.get('markout5_bps_mean', 0):+.1f}" if e.get("n") else "-"
        fx = f"{x.get('pi_bps_mean', 0):+.1f}/{x.get('markout5_bps_mean', 0):+.1f}" if x.get("n") else "-"
        print(f"{nm:40s} {r['fills']['fill_rate']:>6.3f} {r['tickets_per_day']:>5.2f} "
              f"{r['flat']['per_ticket_mean']:>+8.2f}±{r['flat']['per_ticket_sd']:<3.1f} "
              f"{r['meas']['per_ticket_mean']:>+8.2f} {r['zero']['per_ticket_mean']:>+8.2f} "
              f"{(r['mkt_counterfactual_flat'] or 0):>+8.2f} {fe:>12} {fx:>12}"
              f" {r.get('fore', {}).get('flat', 0):>+8.1f} {r.get('anti', {}).get('flat', 0):>+8.1f}",
              flush=True)
    X.write_json(f"frame_{tag}_h{hold}.json",
                 {"days": len(dates), "seeds": seeds, "hold": hold,
                  "configs": {nm: {"entry": CONFIGS[nm][0], "exit": CONFIGS[nm][1]}
                              for nm in names},
                  "rows": rows})
    return rows


if __name__ == "__main__":
    a = sys.argv
    g = lambda f, d: (type(d)(a[a.index(f) + 1]) if f in a else d)  # noqa: E731
    st = g("--stage", "ident")
    if st == "ident":
        stage_ident(limit=g("--limit", 0) or None, seeds=g("--seeds", 30))
    elif st == "ladder":
        nm = g("--names", "")
        stage_ladder(seeds=g("--seeds", 30), limit=g("--limit", 0) or None,
                     workers=g("--workers", 2),
                     names=nm.split(",") if nm else None,
                     hold=g("--hold", HOLD), with_fore=not ("--nofore" in a),
                     tag=g("--tag", "ladder"))
    else:
        raise SystemExit(st)
