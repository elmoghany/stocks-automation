"""UNIVERSE+QUOTES (2026-09-16) -- constraint 2, stage 4: a sequential,
account-legal strategy simulator under LIMIT entries, with its controls.

THE ACCOUNT RULES ARE PART OF THE SIMULATOR, not a footnote (MEMORY.md,
cash-account ticket rules): ONE POSITION AT A TIME, at most 7 tickets a
day, $15,000 a ticket, $100,000 of same-day notional. The wide-net study's
breadth tables broke all three (17.8 tickets/day = $267k), which is one of
the reasons its only >$7k/month row was not executable. Here the day is
walked forward in time and a new position can only be opened once the
previous one is out.

THE DAY, EXACTLY
  For each regular-session decision slot in order (09:35 09:45 10:00 10:30
  11:00 12:00 13:00 14:00 15:00):
    * if a position is still open, skip the slot;
    * otherwise rank the causally-eligible names by the walk-forward model
      score and POST a buy limit at L = mark(m)*(1-k/10000) on the top
      `post_k` of them;
    * whichever of those posted limits is hit FIRST by a print within N
      minutes becomes the position; the rest are cancelled. (Posting k and
      taking the first fill is what a real operator does; taking ALL fills
      would break the one-position rule.)
    * the position exits at the open of the first printed minute at or
      after fill+H, paying `exit_bps`; the account is busy until then.
    * stop after `max_tickets` fills.

CONTROLS, all of them under the IDENTICAL fill rule, slot order, account
rules and costs -- only the ranking changes:
    random   `seeds` independent uniform rankings
    inverted -score
    shuffled the walk-forward model refitted on labels permuted within
             each train day (data/massive/wn/model_scores_h30_s0_shuf.npy,
             written by plan/wn_model.py --shuffle)

Usage:
  python plan/uq_strat.py --stage run [--offset 10] [--wait 1] [--postk 3]
                          [--h h30] [--split 1] [--seeds 30]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uq_econ as UE                                          # noqa: E402
import uq_fills as UF                                         # noqa: E402
import uq_sec1                                                # noqa: E402
from wn_lib import OUT as WNOUT, Table, summarize             # noqa: E402

OUT = HERE / "uq_out"
RTH = UF.RTH_DEC


def simulate_day(t, day, rows, score, offset, wait, post_k, h,
                 exit_bps=UF.FEE_BPS, passive_bps=0.0, max_tickets=7,
                 max_notional=100_000.0, market=False):
    """One day, one ranking. Returns the list of tickets taken."""
    by_slot = {}
    for r in rows:
        by_slot.setdefault(int(t.dec_i[r]), []).append(r)
    out = []
    busy_until = -1
    notional_used = 0.0
    for dec in RTH:
        ci = UF.DEC_ET.index(dec)
        cand = by_slot.get(ci)
        if not cand:
            continue
        ti = int(UF.DEC_T[ci])
        me = min(int(UF.STEPS[ti]) + 1, UF.NMIN - 1)
        if me < busy_until:
            continue
        if len(out) >= max_tickets or notional_used >= max_notional:
            break
        cand = sorted(cand, key=lambda r: -score[r])[:post_k]
        best = None
        for rank, r in enumerate(cand):
            sym = t.syms[t.sym_i[r]]
            si = day.sidx.get(sym)
            if si is None:
                continue
            if market:
                if not day.printed[si, me]:
                    continue
                L = float(day.o[si, me])
                ft = day.ms_of_min(me)
                pb = UF.FEE_BPS
            else:
                if not uq_sec1.have(sym, day.date):
                    continue
                ref = day.mark[ti, si]
                if not np.isfinite(ref) or ref <= 0:
                    continue
                L = float(ref) * (1 - offset / 1e4)
                scan = UE.fill_scan(day, sym, me, wait)
                ft, fpx = UE.fill_at(scan, L)
                if ft is None or ft - day.ms_of_min(me) >= wait * 60_000:
                    continue
                fpx = min(L, fpx)
                pb = passive_bps
            if best is None or ft < best[0] or (ft == best[0]
                                                and rank < best[1]):
                best = (ft, rank, si, sym, L, pb, (L if market else fpx))
        if best is None:
            continue
        ft, _rank, si, sym, L, pb, fpx = best
        pt = UE.price_ticket(day, ti, si, h, L, ft, pb, exit_bps,
                             fill_px=fpx)
        if pt is None or pt["notional"] < UF.MIN_NOTIONAL:
            continue
        _ex, ex_m = day.exit_leg(si, pt["fill_min"], UF.HORIZ[h])
        busy_until = ex_m + 1
        notional_used += pt["notional"]
        out.append({"date": day.date, "dec": dec, "sym": sym,
                    "pnl": pt["pnl"], "notional": pt["notional"],
                    "fill_min": pt["fill_min"], "exit_min": int(ex_m),
                    "capped": pt["capped"]})
    return out


def run_policy(t, dates, score, **kw):
    """Walk every date once. Returns (tickets, per-date row index cache)."""
    tickets = []
    di = {d: i for i, d in enumerate(t.dates)}
    dec_i = [UF.DEC_ET.index(x) for x in RTH]
    for d in dates:
        rows = np.flatnonzero((t.date_i == di[d]) & t.printed_m
                              & np.isin(t.dec_i, dec_i)
                              & np.isfinite(score))
        if rows.size == 0:
            continue
        day = UF.DayTape(d)
        tickets += simulate_day(t, day, rows, score, **kw)
    return tickets


def _summ(tk, ndays, label):
    p = np.array([x["pnl"] for x in tk], float) if tk else np.zeros(0)
    ds = np.array([x["date"] for x in tk]) if tk else np.zeros(0, "U10")
    s = summarize(p, ds, ndays, label)
    s["tickets_per_day"] = round(len(tk) / max(ndays, 1), 3)
    s["mean_notional"] = round(float(np.mean([x["notional"] for x in tk]))
                               if tk else 0.0, 1)
    s["cap_binds"] = round(float(np.mean([x["capped"] for x in tk]))
                           if tk else 0.0, 4)
    return s


def stage_run(h="h30", split=1, offset=10.0, wait=1, post_k=3, seeds=30,
              exit_bps=UF.FEE_BPS, passive_bps=0.0, ndays=None,
              max_tickets=7, tag=""):
    t = Table()
    sc = np.load(WNOUT / f"model_scores_{h}_s0.npy").astype(float)
    days = UE.cached_days(t, split)
    if ndays:
        days = days[:ndays]
    if not days:
        raise SystemExit("no tape-complete day in this split yet")
    kw = dict(offset=offset, wait=wait, post_k=post_k, h=h,
              exit_bps=exit_bps, passive_bps=passive_bps,
              max_tickets=max_tickets)
    nd = len(days)
    print(f"strategy: {nd} tape-complete days in split {split}, "
          f"offset {offset} bps, wait {wait}m, post_k {post_k}, "
          f"exit {exit_bps} bps", flush=True)
    rep = {"h": h, "split": split, "offset_bps": offset, "wait_min": wait,
           "post_k": post_k, "exit_bps": exit_bps,
           "passive_bps": passive_bps, "days": nd,
           "first": days[0], "last": days[-1]}
    main = run_policy(t, days, sc, **kw)
    rep["model_limit"] = _summ(main, nd, "model, limit entry")
    mk = run_policy(t, days, sc, market=True, **kw)
    rep["model_market"] = _summ(mk, nd, "model, market entry (incumbent)")
    inv = run_policy(t, days, -sc, **kw)
    rep["inverted"] = _summ(inv, nd, "inverted score, limit entry")
    shf = WNOUT / f"model_scores_{h}_s0_shuf.npy"
    if shf.exists():
        s2 = np.load(shf).astype(float)
        rep["shuffled"] = _summ(run_policy(t, days, s2, **kw), nd,
                                "shuffled-label model, limit entry")
    rnd = []
    fin = np.isfinite(sc)
    for s in range(seeds):
        rg = np.random.default_rng(1000 + s)
        r = np.where(fin, rg.random(len(sc)), np.nan)
        rnd.append(_summ(run_policy(t, days, r, **kw), nd, f"random {s}"))
        if (s + 1) % 5 == 0:
            print(f"  ..random seed {s+1}/{seeds}", flush=True)
    pm = np.array([x["per_month"] for x in rnd])
    pt = np.array([x["per_ticket"] for x in rnd])
    rep["random"] = {
        "seeds": seeds,
        "per_ticket_mean": round(float(pt.mean()), 2),
        "per_ticket_sd": round(float(pt.std(ddof=1)), 2),
        "per_month_mean": round(float(pm.mean()), 1),
        "per_month_sd": round(float(pm.std(ddof=1)), 1),
        "tickets_per_day_mean": round(float(np.mean(
            [x["tickets_per_day"] for x in rnd])), 3)}
    rep["percentile_vs_random_per_month"] = round(
        100.0 * float(np.mean(pm < rep["model_limit"]["per_month"])), 1)
    rep["percentile_vs_random_per_ticket"] = round(
        100.0 * float(np.mean(pt < rep["model_limit"]["per_ticket"])), 1)
    OUT.mkdir(parents=True, exist_ok=True)
    nm = (f"strat_{h}_s{split}_o{offset:.0f}_w{wait}_k{post_k}"
          f"_x{exit_bps:.0f}{tag}.json")
    (OUT / nm).write_text(json.dumps({**rep, "tickets": main[:3000]},
                                     indent=1, default=str))
    for k in ("model_limit", "model_market", "inverted", "shuffled"):
        if k in rep:
            v = rep[k]
            print(f"{k:>16}: {v['tickets']:>5} tkts "
                  f"({v['tickets_per_day']:.2f}/day) "
                  f"${v['per_ticket']:>8.2f}/tkt  ${v['per_month']:>9.0f}/mo "
                  f"mo+ {v['months_pos']}  dd {v['max_dd']:.0f}")
    print(f"{'random':>16}: {rep['random']}")
    print(f"percentile vs random: per-month "
          f"{rep['percentile_vs_random_per_month']}, per-ticket "
          f"{rep['percentile_vs_random_per_ticket']}")
    print(f"-> {nm}")
    return rep


if __name__ == "__main__":
    a = sys.argv
    g = lambda f, d: (type(d)(a[a.index(f) + 1]) if f in a else d)  # noqa: E731
    stage_run(h=g("--h", "h30"), split=g("--split", 1),
              offset=g("--offset", 10.0), wait=g("--wait", 1),
              post_k=g("--postk", 3), seeds=g("--seeds", 30),
              exit_bps=g("--exit", UF.FEE_BPS),
              passive_bps=g("--passive", 0.0),
              ndays=g("--days", 0) or None,
              max_tickets=g("--maxtkt", 7), tag=g("--tag", ""))
