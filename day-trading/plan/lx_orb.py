"""LIMIT-EXEC stage 3: C37's ORB ENTRY under end-to-end limit execution.

THE ENTRY.  The live rule's second trigger (day-trading.py `orb=True`,
DEFAULT_ORB_BARS = 5): the opening range is the first five regular-session
bars (09:30-09:34), and a name is bought on the first bar whose HIGH breaks
the range high.  The engine fills that as a stop-buy at max(OR high, open)
INSIDE the break bar; here, as everywhere in the honest line, the decision
is the COMPLETED break bar m and the incumbent market fill is the open of
m+1 -- and the limit ladders post at the start of m+1.

TWO UNIVERSES.  OPEN-UNIVERSE (data/massive/m1o) had no MANIFEST when
this ran, so the mandate's fallback applies:
  wide  the causal wide universe (plan/rl2/out/days, 191 halal PIT names,
        448 dates) -- the ORB instinct on names that are NOT gappers;
  pool  the gapper pool's symbol-days that carry BOTH a 1-second tape and
        an m1 bar file (plan/cr_out/pool_pairs.json, 45,404 symbol-days,
        median 91 a day): the pool the live rules actually trade.  NOTE
        the pool's membership is the retracted +10% screen (outcome-
        conditioned, MX-SERIES RETRACTION #2); the ORB break itself is
        causal, the pool is not, so the pool rows are an EXECUTION
        comparison (market vs limit on the same names), not an edge claim.

THE PICK among the day's fresh breakers, one position at a time, <= 7 a
day, hold 30, flat 15:00, entries cut at 14:30 (C37's entry_cutoff):
    rand      random among the names breaking on that minute (30 seeds)
    strength  the largest gain since the 09:30 open ("buy the runner")
    weak      the smallest
    fore      perfect foresight of the market path (ceiling)

Usage: python plan/lx_orb.py --universe wide|pool [--seeds 30] [--limit N]
"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import lx_engine as X                                         # noqa: E402
import lx_frame as F                                          # noqa: E402
import hd_lib as H                                            # noqa: E402

OR_LO, OR_HI = 330, 335          # 09:30..09:34 inclusive -> [330, 335)
CUTOFF = H.idx("14:30")
FLAT = H.idx("15:00")
HOLD = 30
M1 = ROOT / "data" / "massive" / "m1"
POOL = HERE / "cr_out" / "pool_pairs.json"

LADDERS = {
    "mkt/mkt": (None, None),
    "bid-rest3-cancel/mkt": (F.E("rest", 3), None),
    "bid-rest3-mkt/tick3": (F.E("rest", 3, "market"), F.Xs("tick", 3)),
    "tick5-mkt/tick5": (F.E("tick", 5, "market"), F.Xs("tick", 5)),
    "bid-rest3-cancel/ask-rest3": (F.E("rest", 3), F.Xs("rest", 3)),
}


def pool_by_date():
    p = json.loads(POOL.read_text())
    if isinstance(p, dict):
        p = p.get("pairs", list(p.values())[0])
    by = {}
    for s, d in p:
        if ((X.XDIR / f"{s}_{d}.json.gz").exists()
                and (M1 / f"{s}_{d}.csv").exists()):
            by.setdefault(d, []).append(s)
    return by


def pool_panel(date, syms):
    o, h, l, c, v, keep = [], [], [], [], [], []
    for s in syms:
        b = H.read_m1(M1 / f"{s}_{date}.csv", date)
        if b is None:
            continue
        keep.append(s)
        o.append(b[0]); h.append(b[1]); l.append(b[2]); c.append(b[3]); v.append(b[4])
    if not keep:
        return None
    return (keep, np.array(o), np.array(h), np.array(l), np.array(c), np.array(v))


def breakers(day):
    """{minute: [si, ...]} -- the FIRST bar whose high exceeds the 09:30-
    09:34 range high, per symbol; needs all five range bars printed."""
    S = len(day.syms)
    out = {}
    orh = np.full(S, np.nan)
    ok = day.printed[:, OR_LO:OR_HI].all(axis=1)
    orh[ok] = np.nanmax(day.h[:, OR_LO:OR_HI], axis=1)[ok]
    for si in range(S):
        if not ok[si] or not np.isfinite(orh[si]) or not day.has_tape(si):
            continue
        hh = day.h[si, OR_HI:CUTOFF]
        brk = np.flatnonzero(np.isfinite(hh) & (hh > orh[si]))
        if brk.size:
            m = int(OR_HI + brk[0])
            out.setdefault(m, []).append(si)
    return out


def run_day(day, bk, scorer, entry, exit_, rng=None, max_tickets=7):
    out, attempts = [], 0
    busy_until = -1
    for m in sorted(bk):
        if len(out) >= max_tickets:
            break
        if m + 1 < busy_until or m + 1 + HOLD > FLAT:
            continue
        idxs = np.array(bk[m], int)
        s = scorer(day, m, idxs, rng)
        si = int(idxs[int(np.argmax(s))])
        attempts += 1
        rec = X.ticket(day, si, m, HOLD, entry, exit_, FLAT)
        if rec is None:
            busy_until = m + 1 + (entry["wait"] if entry else 0)
            continue
        out.append(rec)
        busy_until = max(rec["m_out"], rec["exit"]["m_done"]) + 1
    return out, attempts


def sc_rand(day, m, idxs, rng):
    return rng.random(idxs.size)


def sc_strength(day, m, idxs, rng):
    r = day.cf[idxs, m] / day.o[idxs, OR_LO] - 1.0
    return np.where(np.isfinite(r), r, -np.inf)


def sc_weak(day, m, idxs, rng):
    r = sc_strength(day, m, idxs, rng)
    return np.where(np.isfinite(r), -r, -np.inf)


def sc_fore(day, m, idxs, rng):
    px_in = day.o[idxs, m + 1]
    px_out = day.cf[idxs, min(m + 1 + HOLD, X.NMIN - 1)]
    r = px_out / px_in - 1.0
    return np.where(np.isfinite(r), r, -np.inf)


PICKS = {"strength": sc_strength, "weak": sc_weak, "fore": sc_fore}


def _worker(args):
    date, uni, syms, seeds, ladders = args
    import lx_engine as XX
    try:
        if uni == "wide":
            day = XX.Day(date)
        else:
            pnl_ = pool_panel(date, syms)
            if pnl_ is None:
                return date, None, "no panel"
            day = XX.Day(date, panel=pnl_, cache_tag="_pool")
    except Exception as e:
        return date, None, str(e)
    bk = breakers(day)
    res = {"_n_breakers": sum(len(v) for v in bk.values()),
           "_n_syms": len(day.syms)}
    for lad in ladders:
        entry, exit_ = LADDERS[lad]
        for s in range(seeds):
            rng = np.random.default_rng(1000 + s)
            res[(lad, f"rand{s}")] = run_day(day, bk, sc_rand, entry, exit_, rng)
        for nm, sc in PICKS.items():
            res[(lad, nm)] = run_day(day, bk, sc, entry, exit_)
    return date, res, None


def main(uni="wide", seeds=30, limit=None, workers=1, ladders=None, stride=1):
    ladders = ladders or list(LADDERS)
    if uni == "wide":
        dates = H.study_dates()
        args = [(d, uni, None, seeds, ladders) for d in dates]
    else:
        by = pool_by_date()
        dates = sorted(by)
        args = [(d, uni, by[d], seeds, ladders) for d in dates]
    if stride > 1:
        args = args[::stride]
        dates = dates[::stride]
    if limit:
        args = args[:limit]
        dates = dates[:limit]
    print(f"[orb/{uni}] {len(args)} days, {len(ladders)} ladders, {seeds} seeds",
          flush=True)
    acc, att = {}, {}
    nb = ns = 0
    t0 = time.monotonic()
    it = Pool(workers).imap_unordered(_worker, args, chunksize=2) \
        if workers > 1 else map(_worker, args)
    done = 0
    for date, res, err in it:
        done += 1
        if err:
            print(f"  !! {date}: {err}", flush=True)
            continue
        nb += res.pop("_n_breakers")
        ns += res.pop("_n_syms")
        for k, (recs, a) in res.items():
            acc.setdefault(k, []).extend(recs)
            att[k] = att.get(k, 0) + a
        if done % 50 == 0 or done == len(args):
            print(f"  [orb/{uni}] {done}/{len(args)} {(time.monotonic()-t0)/60:.1f} min",
                  flush=True)
    nd = len(dates)
    rows = {}
    for lad in ladders:
        r = {}
        for key in ("flat", "meas", "zero"):
            pts = [X.summarize(acc.get((lad, f"rand{s}"), []), nd, key)
                   for s in range(seeds)]
            pt = np.array([p["per_ticket"] for p in pts])
            r[key] = {"random_per_ticket_mean": round(float(pt.mean()), 2),
                      "random_per_ticket_sd": round(float(pt.std(ddof=1)), 2)
                      if seeds > 1 else 0.0,
                      "random_per_month_mean": round(float(np.mean(
                          [p["per_month"] for p in pts])), 1)}
            for nm in PICKS:
                sm = X.summarize(acc.get((lad, nm), []), nd, key)
                sm["percentile"] = round(100.0 * float(np.mean(pt < sm["per_ticket"])), 1)
                sm["edge_vs_random"] = round(sm["per_ticket"] - float(pt.mean()), 2)
                r[key][nm] = sm
        allr = [x for s in range(seeds) for x in acc.get((lad, f"rand{s}"), [])]
        r["fills"] = X.fill_stats(allr, sum(att.get((lad, f"rand{s}"), 0)
                                            for s in range(seeds)))
        r["tickets_per_day"] = round(len(allr) / max(seeds * nd, 1), 3)
        r["decomp"] = X.decomposition(allr)
        mk = [x["mkt"]["pnl_flat"] for x in allr if x.get("mkt")]
        r["mkt_counterfactual_flat"] = round(float(np.mean(mk)), 2) if mk else None
        rows[lad] = r
    print(f"\n== ORB / {uni}: {nd} days, {nb/nd:.1f} breakers/day of {ns/nd:.1f} names ==")
    print(f"{'ladder':28s} {'tk/d':>5} {'fill':>6} {'rand flat':>10} {'meas':>8} {'zero':>8} "
          f"{'mktCF':>8} {'strength':>9} {'weak':>8} {'fore':>8} {'e:pi/mo':>12} {'x:pi/mo':>12}")
    for lad in ladders:
        r = rows[lad]
        d = r["decomp"]
        e, x = d.get("e", {}), d.get("x", {})
        fe = f"{e.get('pi_bps_mean', 0):+.1f}/{e.get('markout5_bps_mean', 0):+.1f}" if e.get("n") else "-"
        fx = f"{x.get('pi_bps_mean', 0):+.1f}/{x.get('markout5_bps_mean', 0):+.1f}" if x.get("n") else "-"
        print(f"{lad:28s} {r['tickets_per_day']:>5.2f} {r['fills']['fill_rate']:>6.3f} "
              f"{r['flat']['random_per_ticket_mean']:>+10.2f} {r['meas']['random_per_ticket_mean']:>+8.2f} "
              f"{r['zero']['random_per_ticket_mean']:>+8.2f} {(r['mkt_counterfactual_flat'] or 0):>+8.2f} "
              f"{r['flat']['strength']['per_ticket']:>+9.2f} {r['flat']['weak']['per_ticket']:>+8.2f} "
              f"{r['flat']['fore']['per_ticket']:>+8.1f} {fe:>12} {fx:>12}", flush=True)
    X.write_json(f"orb_{uni}.json", {"universe": uni, "days": nd, "seeds": seeds, "stride": stride,
                                     "breakers_per_day": nb / max(nd, 1),
                                     "names_per_day": ns / max(nd, 1),
                                     "rows": rows})


if __name__ == "__main__":
    a = sys.argv
    g = lambda f, d: (type(d)(a[a.index(f) + 1]) if f in a else d)  # noqa: E731
    lad = g("--ladders", "")
    main(g("--universe", "wide"), g("--seeds", 30), g("--limit", 0) or None,
         g("--workers", 1), lad.split(",") if lad else None, g("--stride", 1))
