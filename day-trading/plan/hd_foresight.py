"""HARNESS-DIAGNOSTIC control 4: the foresight ladder, and the zero-
information baseline it is measured against.

Two numbers come out of this file and they answer different halves of the
question.

  ZERO-INFORMATION BASELINE.  Run the frame with a RANDOM pick at every
  decision.  Whatever that returns is what the frame costs before any skill
  is applied.  If it equals (universe intraday drift x notional) minus the
  toll, the harness is adding nothing of its own and hypothesis (A) is dead
  on this axis.  If it is far below that, the harness is leaking money
  somewhere and (A) is alive.

  FORESIGHT LADDER.  Replace the random pick with PERFECT knowledge of the
  next H minutes and nothing else -- same universe, same schedule, same
  ticket ladder, same volume cap, same toll.  The result is the ceiling: the
  most that H minutes of same-day, long-only information can be worth in this
  frame.  The $7,500/month target can then be stated as a FRACTION of perfect
  information, which is the honest way to say how hard the target is.

FRAME (the user's account rules, from memory/cash-account-ticket-rules)
  one position at a time, up to 7 tickets a day, $15,000 a ticket, flat
  10 bps a side inside 09:30-16:00, 20%-of-trailing-5-minute-volume size cap,
  everything flat by 15:00.  Entry is the OPEN of the bar after the decision
  bar; exit is the CLOSE of the bar H minutes later.  Availability is read
  off the decision bar, never off the fill bar.

Usage:  python plan/hd_foresight.py [--seeds 30] [--limit N]
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_lib as H                                            # noqa: E402

START_K = H.idx("09:30")      # first decision bar -> fill at the 09:31 open
FLAT_K = H.idx("15:00")       # everything is out by here
MAX_TICKETS = 7
VOLCAP_FRAC = 0.20
VOLCAP_WIN = 5
MIN_NOTIONAL = 500.0
HORIZONS = (5, 10, 30, 60)


def day_panel(date):
    p = H.npz_panel(date)
    if p is None:
        return None
    syms, o, h, l, c, v = p[0], p[1], p[2], p[3], p[4], p[5]
    cf = H.ffill(c)
    cvol = np.cumsum(np.nan_to_num(v), axis=1)
    printed = ~np.isnan(c)
    f32 = lambda a: np.asarray(a, np.float32)                  # noqa: E731
    return {"date": date, "syms": syms, "o": f32(o), "c": f32(c),
            "cf": f32(cf), "printed": printed, "cvol": f32(cvol),
            "S": len(syms)}


def run_day(P, hold, scorer, cost_bps=H.FEE_BPS, rng=None, ticket=H.TICKET,
            max_tickets=MAX_TICKETS):
    """One position at a time; returns a list of $ P&L per ticket."""
    o, cf, printed, cvol = P["o"], P["cf"], P["printed"], P["cvol"]
    out = []
    m = START_K
    while len(out) < max_tickets:
        mf = m + 1
        mx = mf + hold
        if mx > FLAT_K:
            break
        avail = printed[:, m] & np.isfinite(o[:, mf]) & (o[:, mf] > 0) \
            & np.isfinite(cf[:, mx]) & (cf[:, mx] > 0)
        if not avail.any():
            m += 1
            continue
        idxs = np.flatnonzero(avail)
        s = scorer(P, m, mf, mx, idxs, rng)
        i = int(idxs[int(np.argmax(s))])
        px_in = float(o[i, mf])
        px_out = float(cf[i, mx])
        lo = max(m - VOLCAP_WIN, 0)
        cap = VOLCAP_FRAC * float(cvol[i, m] - cvol[i, lo])
        sh = ticket / px_in
        if np.isfinite(cap) and cap > 0:
            sh = min(sh, cap)
        if sh * px_in < MIN_NOTIONAL:
            m = mf
            continue
        cfi = cost_bps / 1e4
        pnl = sh * px_out * (1.0 - cfi) - sh * px_in * (1.0 + cfi)
        out.append(float(pnl))
        m = mx                     # flat again at the exit bar
    return out


def sc_foresight(P, m, mf, mx, idxs, rng):
    return P["cf"][idxs, mx] / P["o"][idxs, mf] - 1.0


def sc_antiforesight(P, m, mf, mx, idxs, rng):
    return -(P["cf"][idxs, mx] / P["o"][idxs, mf] - 1.0)


def sc_random(P, m, mf, mx, idxs, rng):
    return rng.random(idxs.size)


def summarize(per_day, label):
    tot = float(sum(sum(v) for v in per_day.values()))
    tks = [x for v in per_day.values() for x in v]
    nd = len(per_day)
    if not tks:
        return {"label": label, "tickets": 0}
    pt = tot / len(tks)
    tpd = len(tks) / nd
    ser = np.array([sum(per_day[d]) for d in sorted(per_day)])
    eq = np.cumsum(ser)
    return {"label": label, "days": nd, "tickets": len(tks),
            "tickets_per_day": round(tpd, 2),
            "per_ticket": round(pt, 2),
            "per_day": round(tot / nd, 2),
            "total": round(tot, 2),
            "per_month_at7": round(pt * H.TICKETS_PER_MONTH, 2),
            "per_month_actual": round(tot / nd * H.DAYS_PER_MONTH, 2),
            "win_rate": round(float(np.mean([x > 0 for x in tks])), 4),
            "max_dd": round(float(np.min(eq - np.maximum.accumulate(eq))), 2)}


def main():
    seeds = 30
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--seeds":
            seeds = int(sys.argv[i + 1])
        if a == "--limit":
            limit = int(sys.argv[i + 1])
    dates = H.study_dates()
    if limit:
        dates = dates[:limit]
    print(f"[fore] loading {len(dates)} panels", flush=True)
    panels = []
    for d in dates:
        P = day_panel(d)
        if P is not None:
            panels.append(P)
    print(f"[fore] {len(panels)} panels, median S="
          f"{int(np.median([p['S'] for p in panels]))}", flush=True)

    res = {"n_days": len(panels), "rows": {}}
    for hold in HORIZONS:
        row = {}
        for nm, sc, cb in (("foresight", sc_foresight, H.FEE_BPS),
                           ("foresight_nocost", sc_foresight, 0.0),
                           ("antiforesight", sc_antiforesight, H.FEE_BPS)):
            pd_ = {P["date"]: run_day(P, hold, sc, cost_bps=cb)
                   for P in panels}
            row[nm] = summarize(pd_, f"h{hold}/{nm}")
        # random control, `seeds` independent draws
        rnd, rnd0 = [], []
        for s in range(seeds):
            rng = np.random.default_rng(1000 + s)
            pd_ = {P["date"]: run_day(P, hold, sc_random, rng=rng)
                   for P in panels}
            rnd.append(summarize(pd_, f"h{hold}/rand{s}"))
            rng = np.random.default_rng(1000 + s)
            pd0 = {P["date"]: run_day(P, hold, sc_random, cost_bps=0.0,
                                      rng=rng) for P in panels}
            rnd0.append(summarize(pd0, f"h{hold}/rand0c{s}"))
        pt = np.array([r["per_ticket"] for r in rnd])
        pt0 = np.array([r["per_ticket"] for r in rnd0])
        row["random"] = {"seeds": seeds,
                         "per_ticket_mean": round(float(pt.mean()), 2),
                         "per_ticket_sd": round(float(pt.std(ddof=1)), 2),
                         "per_month_at7": round(float(pt.mean())
                                                * H.TICKETS_PER_MONTH, 2),
                         "tickets_per_day": rnd[0]["tickets_per_day"]}
        row["random_nocost"] = {"seeds": seeds,
                                "per_ticket_mean": round(float(pt0.mean()), 2),
                                "per_ticket_sd": round(float(pt0.std(ddof=1)),
                                                       2),
                                "per_month_at7": round(float(pt0.mean())
                                                       * H.TICKETS_PER_MONTH,
                                                       2)}
        res["rows"][f"h{hold}"] = row
        f = row["foresight"]
        print(f"[fore] h={hold:3d}  foresight ${f['per_ticket']:+8.2f}/tkt "
              f"({f['tickets_per_day']:.2f} tkt/day, ${f['per_month_at7']:+10,.0f}/mo@7)"
              f"  nocost ${row['foresight_nocost']['per_ticket']:+8.2f}"
              f"  random ${row['random']['per_ticket_mean']:+7.2f}"
              f" +/- {row['random']['per_ticket_sd']:.2f}"
              f"  random@0bps ${row['random_nocost']['per_ticket_mean']:+7.2f}"
              f"  anti ${row['antiforesight']['per_ticket']:+8.2f}", flush=True)
        print(f"        target share: $7,500/mo is "
              f"{100*H.TARGET_PER_MONTH/max(f['per_month_at7'],1e-9):.2f}% "
              f"of perfect {hold}-minute information", flush=True)

    H.write("foresight.json", res)
    print("[fore] wrote foresight.json", flush=True)


if __name__ == "__main__":
    main()
