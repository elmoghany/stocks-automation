"""UNIVERSE+QUOTES (2026-09-16) -- constraint 2, stage 3: the economics of
a limit entry, measured on the real tape.

Everything here re-prices tickets the wide-net study already booked. It
never re-fits a model: `data/massive/wn/model_scores_h30_s0.npy` is the
walk-forward score written by plan/wn_model.py (fitted month by month on
rows strictly before each test month) and it is read, not rebuilt. Only
the FILL changes.

THE LADDER
  offset k bps below `mark(m)` -- the last printed close at or before the
  decision minute, which is what a trader can actually see at t0:
     k = 0    ... post AT the last print (roughly the mid when the spread
                  straddles it; the "limit at mid" leg of the mandate)
     k = s/2  ... post at the ESTIMATED BID, per-row, from the high-low
                  spread estimators of plan/uq_fills.py (the "limit at the
                  bid" leg; the NBBO itself is not entitled on this
                  account -- see plan/uq_sec1.py)
     k in {5,10,15,20,30,50} ... a fixed ladder, so the shape of the
                  fill-rate / edge trade-off is visible rather than
                  assumed at one point.
  N in {1, 3, 5} minutes of resting time. Unfilled = no trade = $0, and
  the ticket is spent.

WHAT MOVES AND WHAT DOES NOT
  * entry price: L instead of the open of minute m+1
  * entry cost: `passive_bps` instead of 10 bps (a resting limit does not
    pay the spread; it may still pay a fee -- reported at 0 / 2 / 5)
  * holding clock: starts at the FILL minute, so a late fill exits late
  * exit: unchanged in shape (open of the first printed minute at or
    after fill+H), cost `exit_bps`, default the incumbent 10 bps
  * eligibility, candidate set, notional cap, the $15,000 ticket and the
    model score: all unchanged

Usage:
  python plan/uq_econ.py --stage grid     [--days N] [--h h30]
  python plan/uq_econ.py --stage controls [--seeds 30]
  python plan/uq_econ.py --stage need
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uq_fills as uf                                         # noqa: E402
import uq_sec1                                                # noqa: E402
from wn_lib import OUT as WNOUT, Table, summarize             # noqa: E402

OUT = HERE / "uq_out"
RTH = uf.RTH_DEC
OFFSETS = [0.0, 5.0, 10.0, 15.0, 20.0, 30.0, 50.0]
NWAIT = [1, 3, 5]
PASSIVE = [0.0, 2.0, 5.0]


# ------------------------------------------------------------ fill scans
def fill_scan(day, sym, me, maxmin=5):
    """(ts, running-min-low, open) over [t0, t0+maxmin), improvements only.

    The running-min array is strictly decreasing, so the first second at
    which a limit L would be hit is one searchsorted away -- for EVERY L
    at once. The OPEN of that second is carried alongside because it is
    what decides the fill PRICE (see `fill_at`).
    """
    rows = day.tape(sym)
    if not rows:
        return None
    lo = day.ms_of_min(me)
    hi = lo + maxmin * 60_000
    ts, rm, op, cur = [], [], [], float("inf")
    for r in rows:
        t = r[0]
        if t < lo:
            continue
        if t >= hi:
            break
        lw = r[3]
        if lw is None:
            continue
        if lw < cur:
            cur = lw
            ts.append(t)
            rm.append(cur)
            op.append(r[1] if r[1] is not None else lw)
    if not ts:
        return None
    return (np.asarray(ts, np.int64), np.asarray(rm, float),
            np.asarray(op, float))


def fill_ms(scan, L):
    """First timestamp whose running-min low is <= L, or None."""
    if scan is None:
        return None
    ts, rm = scan[0], scan[1]
    i = int(np.searchsorted(-rm, -L, side="left"))
    return int(ts[i]) if i < len(ts) else None


def fill_at(scan, L):
    """(timestamp, FILL PRICE) for a buy limit at L, or (None, None).

    THE FILL PRICE IS NOT ALWAYS L, and getting this wrong is the single
    biggest way a limit backtest lies to itself. An exchange fills a buy
    limit at the BETTER of the limit and the market:

      * the filling second OPENED ABOVE L -- price came down to us during
        that second, our order was resting at L, we get L;
      * the filling second OPENED AT OR BELOW L -- the market was already
        there when we posted, so the order was marketable on arrival and
        we get the market, not our (worse) limit.

    min(L, open of the filling second) is exactly those two cases. The
    first version of this module filled at L unconditionally, and because
    `mark(m)` is the last printed close -- which can be STALE by minutes
    on a thin name -- that charged the stale price for a marketable order
    and made the limit entry look WORSE than a market order at a zero
    offset. The symptom was a NEGATIVE price-improvement column (`pxImp`)
    at offset 0, which is arithmetically impossible for a real limit
    order, and that is what exposed it.
    """
    if scan is None:
        return None, None
    ts, rm, op = scan
    i = int(np.searchsorted(-rm, -L, side="left"))
    if i >= len(ts):
        return None, None
    o = float(op[i])
    return int(ts[i]), (min(L, o) if np.isfinite(o) and o > 0 else L)


def price_ticket(day, ti, si, h, L, fill_t_ms, passive_bps, exit_bps,
                 cap_mult=1.0, fill_px=None):
    """$ P&L of a filled limit ticket.

    `L` is the POSTED limit; it sizes the ticket (notional = min($15,000,
    volcap * L), a quantity knowable at t0). `fill_px` is what the order
    actually paid -- min(L, market) per `fill_at` -- and defaults to L."""
    mf = int((fill_t_ms - day.t0_04) // 60_000)
    fp = float(L if fill_px is None else fill_px)
    cap = day.volcap[ti, si] * cap_mult
    notion = min(uf.TICKET, cap * L)
    if not np.isfinite(notion):
        return None
    ex_px, ex_m = day.exit_leg(si, mf, uf.HORIZ[h])
    if not np.isfinite(ex_px) or ex_m < mf:
        return None
    ent_c = float(uf.cost_frac(mf, passive_bps))
    ex_c = float(uf.cost_frac(ex_m, exit_bps))
    r = (ex_px * (1 - ex_c)) / (fp * (1 + ent_c)) - 1
    return {"pnl": notion * (1 + ent_c) * r, "notional": notion,
            "fill_min": mf, "fill_px": fp,
            "capped": bool(cap * L < uf.TICKET)}


# ------------------------------------------------------------ row engine
def price_rows(t, rows, h, offsets=OFFSETS, nwait=NWAIT,
               passive_bps=0.0, exit_bps=uf.FEE_BPS, cap_mult=1.0,
               spread_offset=True, verbose=True, through=0.0):
    """Price every row under the baseline and the whole limit ladder.

    Returns dict with arrays aligned to `rows`:
      base   $ (the wide-net table's own number)
      lim[(k, N)]  $ ; filled[(k, N)] bool
      sbid   the per-row estimated half-spread in bps (k = s/2 leg)
    """
    by_date = {}
    for i, r in enumerate(rows):
        by_date.setdefault(t.date_s[r], []).append(i)
    n = len(rows)
    base = np.zeros(n)
    keys = [(k, N) for k in offsets for N in nwait]
    lim = {k: np.zeros(n) for k in keys}
    fil = {k: np.zeros(n, bool) for k in keys}
    cap = {k: np.zeros(n, bool) for k in keys}
    sbid = np.full(n, np.nan)
    sobs = np.full(n, np.nan)
    slim = {N: np.zeros(n) for N in nwait}
    sfil = {N: np.zeros(n, bool) for N in nwait}
    notn = np.zeros(n)
    pximp = {k: np.full(n, np.nan) for k in keys}
    gross = {k: np.full(n, np.nan) for k in keys}
    bgross = np.full(n, np.nan)
    have_tape = np.zeros(n, bool)
    dates = sorted(by_date)
    for di, date in enumerate(dates):
        day = uf.DayTape(date)
        for i in by_date[date]:
            r = rows[i]
            sym = t.syms[t.sym_i[r]]
            si = day.sidx.get(sym)
            if si is None:
                continue
            ti = int(uf.DEC_T[t.dec_i[r]])
            base[i] = float(t.pnl[h][r])
            me = min(int(uf.STEPS[ti]) + 1, uf.NMIN - 1)
            # GROSS (cost-free) baseline return, so the decomposition can
            # separate "cost saved" from "adverse selection".
            if day.printed[si, me]:
                bo = float(day.o[si, me])
                bx, bm = day.exit_leg(si, me, uf.HORIZ[h])
                if np.isfinite(bo) and bo > 0 and np.isfinite(bx)                         and bm >= me:
                    bgross[i] = (bx / bo - 1.0) * 1e4
            if not uq_sec1.have(sym, date):
                continue
            have_tape[i] = True
            scan = fill_scan(day, sym, me, max(nwait))
            ref = day.mark[ti, si]
            if not np.isfinite(ref) or ref <= 0:
                continue
            if spread_offset:
                est = uf.spread_at(day, si, ti)
                ob, _nb = uf.obs_spread_sec(day, sym, ti)
            else:
                est, ob = {"ar": np.nan}, np.nan     # skip: pure cost
            sobs[i] = ob
            # The limit "at the bid" uses the OBSERVED intra-second range
            # when the tape offers one and falls back to the Abdi-Ranaldo
            # estimator otherwise; both are halved, because the bid is
            # half a spread below the mid.
            half = (ob / 2.0 if np.isfinite(ob)
                    else (est["ar"] / 2.0 if np.isfinite(est["ar"])
                          else np.nan))
            sbid[i] = half
            for k in offsets:
                L = float(ref) * (1 - k / 1e4)
                # `through` = how far BELOW the limit the tape must print
                # before the fill is believed. 0 = a touch fills (front of
                # queue); 0.01 = a full cent through (the book at L had to
                # be cleared first). The queue-position sensitivity.
                ft, fpx = fill_at(scan, L - through)
                if ft is None:
                    continue
                fpx = min(L, fpx)
                wait = ft - day.ms_of_min(me)
                for N in nwait:
                    if wait >= N * 60_000:
                        continue
                    pt = price_ticket(day, ti, si, h, L, ft, passive_bps,
                                      exit_bps, cap_mult, fill_px=fpx)
                    if pt is None:
                        continue
                    lim[(k, N)][i] = pt["pnl"]
                    fil[(k, N)][i] = True
                    cap[(k, N)][i] = pt["capped"]
                    gx, gm = day.exit_leg(si, pt["fill_min"], uf.HORIZ[h])
                    if np.isfinite(gx) and gm >= pt["fill_min"]:
                        gross[(k, N)][i] = (gx / pt["fill_px"] - 1.0) * 1e4
                    if day.printed[si, me]:
                        pximp[(k, N)][i] = (float(day.o[si, me])
                                            / pt["fill_px"] - 1.0) * 1e4
                    if k == 0.0:
                        notn[i] = pt["notional"]
            if spread_offset and np.isfinite(half) and half > 0:
                L = float(ref) * (1 - half / 1e4)
                ft, fpx = fill_at(scan, L - through)
                fpx = None if ft is None else min(L, fpx)
                if ft is not None:
                    wait = ft - day.ms_of_min(me)
                    for N in nwait:
                        if wait >= N * 60_000:
                            continue
                        pt = price_ticket(day, ti, si, h, L, ft, passive_bps,
                                          exit_bps, cap_mult, fill_px=fpx)
                        if pt is None:
                            continue
                        slim[N][i] = pt["pnl"]
                        sfil[N][i] = True
        if verbose and (di + 1) % 25 == 0:
            print(f"  ..{di+1}/{len(dates)} days", flush=True)
    return {"base": base, "lim": lim, "filled": fil, "capped": cap,
            "sbid": sbid, "sobs": sobs, "slim": slim, "sfil": sfil,
            "notional": notn, "have_tape": have_tape,
            "pximp": pximp, "gross": gross, "bgross": bgross}


# ---------------------------------------------------------------- stages
def model_rows(t, h="h30", topk=1, dec=RTH, split=1, score=None):
    if score is None:
        score = np.load(WNOUT / f"model_scores_{h}_s0.npy").astype(float)
    m = t.mask(split=split, dec=dec, h=h) & np.isfinite(score)
    from wn_lib import single_pick
    _p, _d, take = single_pick(t, score, m, h=h, topk=topk)
    return take, score


def stage_grid(h="h30", ndays=None, topk=1, dec=None, exit_bps=uf.FEE_BPS):
    t = Table()
    dec = dec or ["09:35"]
    take, _sc = model_rows(t, h, topk, dec)
    if ndays:
        keep = sorted({t.date_s[r] for r in take})[:ndays]
        take = np.array([r for r in take if t.date_s[r] in set(keep)])
    print(f"grid: {len(take):,} model picks, "
          f"{len({t.date_s[r] for r in take})} days, dec={dec}, topk={topk}",
          flush=True)
    res = price_rows(t, take, h, exit_bps=exit_bps)
    ht = res["have_tape"]
    nd = len({t.date_s[r] for r in take[ht]})
    dts = np.array([t.date_s[r] for r in take])[ht]
    rep = {"h": h, "dec": dec, "topk": topk, "exit_bps": exit_bps,
           "picks": int(len(take)), "with_tape": int(ht.sum()),
           "days": nd,
           "baseline": summarize(res["base"][ht], dts, nd, "market m+1 open")}
    rows = []
    for k in OFFSETS:
        for N in NWAIT:
            f = res["filled"][(k, N)][ht]
            p = res["lim"][(k, N)][ht]
            s = summarize(p, dts, nd, f"limit -{k:.0f}bps / {N}m")
            rows.append({"offset_bps": k, "wait_min": N,
                         "fill_rate": round(float(f.mean()), 4),
                         "per_ticket_all": s["per_ticket"],
                         "per_ticket_filled": round(
                             float(p[f].mean()) if f.any() else 0.0, 2),
                         "per_month": s["per_month"],
                         "months_pos": s["months_pos"],
                         "total": s["total"],
                         "cap_binds": round(float(
                             res["capped"][(k, N)][ht][f].mean())
                             if f.any() else 0.0, 4)})
    rep["ladder"] = rows
    sb = res["sbid"][ht]
    rep["est_half_spread_bps"] = {
        "n": int(np.isfinite(sb).sum()),
        "p25": round(float(np.nanpercentile(sb, 25)), 2),
        "p50": round(float(np.nanpercentile(sb, 50)), 2),
        "p75": round(float(np.nanpercentile(sb, 75)), 2)}
    srows = []
    for N in NWAIT:
        f = res["sfil"][N][ht]
        p = res["slim"][N][ht]
        s = summarize(p, dts, nd, f"limit at est. bid / {N}m")
        srows.append({"wait_min": N, "fill_rate": round(float(f.mean()), 4),
                      "per_ticket_all": s["per_ticket"],
                      "per_month": s["per_month"],
                      "months_pos": s["months_pos"]})
    rep["at_est_bid"] = srows
    print(json.dumps({k: v for k, v in rep.items()
                      if k != "ladder"}, indent=1, default=str))
    print(f"\n{'off':>5} {'N':>2} {'fill':>6} {'$/tkt':>9} "
          f"{'$/tkt|fill':>11} {'$/mo':>9} {'mo+':>6} {'cap%':>6}")
    for r in rows:
        print(f"{r['offset_bps']:>5.0f} {r['wait_min']:>2} "
              f"{r['fill_rate']:>6.3f} {r['per_ticket_all']:>9.2f} "
              f"{r['per_ticket_filled']:>11.2f} {r['per_month']:>9.0f} "
              f"{r['months_pos']:>6} {r['cap_binds']:>6.3f}")
    tag = f"{h}_top{topk}_{'-'.join(x.replace(':','') for x in dec)}"
    (OUT / f"econ_grid_{tag}.json").write_text(
        json.dumps(rep, indent=1, default=str))
    return rep


def cached_days(t, split=None, need=0.9):
    """Dates whose 1-second tape is (nearly) complete in the cache."""
    out = []
    for i, d in enumerate(t.dates):
        if split is not None:
            s = 0 if d < "2025-08-01" else (1 if d < "2026-08-01" else 2)
            if s != split:
                continue
        syms = sorted({t.syms[t.sym_i[j]] for j in
                       np.flatnonzero((t.date_i == i) & t.printed_m)})
        if not syms:
            continue
        have = sum(uq_sec1.have(x, d) for x in syms)
        if have >= need * len(syms):
            out.append(d)
    return out


def stage_uncond(h="h30", ndays=None, dec=None, exit_bps=uf.FEE_BPS,
                 sample=None, seed=0, through=0.0, cap_mult=1.0,
                 passive_bps=0.0):
    """Unconditional expectancy per $15,000 ticket under the limit ladder
    -- the direct analogue of widenet-audit Part 2.1, which measured the
    market-fill toll at -$15..-$31 in the regular session."""
    t = Table()
    dec = dec or RTH
    days = cached_days(t, None)
    if ndays:
        days = days[:ndays]
    dset = {d: i for i, d in enumerate(t.dates)}
    di = [dset[d] for d in days]
    dec_i = [uf.DEC_ET.index(x) for x in dec]
    rows = np.flatnonzero(t.printed_m & np.isin(t.date_i, di)
                          & np.isin(t.dec_i, dec_i))
    rng = np.random.default_rng(seed)
    if sample and len(rows) > sample:
        rows = np.sort(rng.choice(rows, sample, replace=False))
    print(f"uncond: {len(rows):,} eligible tickets over {len(days)} "
          f"tape-complete days, dec={dec}", flush=True)
    res = price_rows(t, rows, h, exit_bps=exit_bps, through=through,
                     cap_mult=cap_mult, passive_bps=passive_bps)
    ht = res["have_tape"]
    dts = np.array([t.date_s[r] for r in rows])[ht]
    nd = len(set(dts))
    rep = {"h": h, "dec": dec, "exit_bps": exit_bps, "days": nd,
           "cap_mult": cap_mult, "passive_bps": passive_bps,
           "tickets": int(ht.sum()),
           "baseline": summarize(res["base"][ht], dts, nd, "market m+1")}
    out = []
    for k in OFFSETS:
        for N in NWAIT:
            f = res["filled"][(k, N)][ht]
            p = res["lim"][(k, N)][ht]
            gk = res["gross"][(k, N)][ht]
            pk = res["pximp"][(k, N)][ht]
            bg = res["bgross"][ht]
            out.append({"offset_bps": k, "wait_min": N,
                        "fill_rate": round(float(f.mean()), 4),
                        "per_ticket_all": round(float(p.mean()), 2),
                        "per_ticket_filled": round(
                            float(p[f].mean()) if f.any() else 0.0, 2),
                        "cap_binds": round(float(
                            res["capped"][(k, N)][ht][f].mean())
                            if f.any() else 0.0, 4),
                        # decomposition, all in bps of notional
                        "px_improve_bps": round(float(np.nanmean(pk[f]))
                                                if f.any() else 0.0, 2),
                        "gross_ret_filled_bps": round(
                            float(np.nanmean(gk[f])) if f.any() else 0.0, 2),
                        "gross_ret_base_all_bps": round(
                            float(np.nanmean(bg)), 2),
                        "gross_ret_base_on_filled_bps": round(
                            float(np.nanmean(bg[f])) if f.any() else 0.0, 2)})
    rep["ladder"] = out
    ob = res["sobs"][ht]
    rep["obs_spread_bps"] = {
        "n": int(np.isfinite(ob).sum()),
        "p10": round(float(np.nanpercentile(ob, 10)), 2),
        "p25": round(float(np.nanpercentile(ob, 25)), 2),
        "p50": round(float(np.nanpercentile(ob, 50)), 2),
        "p75": round(float(np.nanpercentile(ob, 75)), 2),
        "p90": round(float(np.nanpercentile(ob, 90)), 2),
        "mean": round(float(np.nanmean(ob)), 2)}
    rep["through_cents"] = through
    sb = res["sbid"][ht]
    rep["est_half_spread_bps"] = {
        "n": int(np.isfinite(sb).sum()),
        "p10": round(float(np.nanpercentile(sb, 10)), 2),
        "p25": round(float(np.nanpercentile(sb, 25)), 2),
        "p50": round(float(np.nanpercentile(sb, 50)), 2),
        "p75": round(float(np.nanpercentile(sb, 75)), 2),
        "p90": round(float(np.nanpercentile(sb, 90)), 2)}
    rep["at_est_bid"] = [
        {"wait_min": N,
         "fill_rate": round(float(res["sfil"][N][ht].mean()), 4),
         "per_ticket_all": round(float(res["slim"][N][ht].mean()), 2),
         "per_ticket_filled": round(float(
             res["slim"][N][ht][res["sfil"][N][ht]].mean())
             if res["sfil"][N][ht].any() else 0.0, 2)}
        for N in NWAIT]
    print(f"baseline (market fill at m+1 open): "
          f"${rep['baseline']['per_ticket']:.2f}/ticket on "
          f"{rep['tickets']:,} tickets")
    print(f"OBSERVED full spread bps (1-s range, n>=2): "
          f"{rep['obs_spread_bps']}")
    print(f"half-spread used for the at-bid leg: "
          f"{rep['est_half_spread_bps']}")
    print()
    print(f"{'off':>5} {'N':>2} {'fill':>6} {'$/tkt(all)':>11} "
          f"{'$/tkt(fill)':>12} {'pxImp':>7} {'grFill':>8} {'grBaseSel':>10} "
          f"{'cap%':>6}")
    for r in out:
        print(f"{r['offset_bps']:>5.0f} {r['wait_min']:>2} "
              f"{r['fill_rate']:>6.3f} {r['per_ticket_all']:>11.2f} "
              f"{r['per_ticket_filled']:>12.2f} {r['px_improve_bps']:>7.1f} "
              f"{r['gross_ret_filled_bps']:>8.1f} "
              f"{r['gross_ret_base_on_filled_bps']:>10.1f} "
              f"{r['cap_binds']:>6.3f}")
    print(f"gross fwd return, ALL eligible (baseline entry): "
          f"{out[0]['gross_ret_base_all_bps']:.1f} bps")
    print("at estimated bid:", json.dumps(rep["at_est_bid"]))
    (OUT / f"econ_uncond_{h}_x{exit_bps:.0f}_c{cap_mult:.2f}"
           f"_p{passive_bps:.0f}_t{through:.2f}.json").write_text(
        json.dumps(rep, indent=1, default=str))
    return rep


if __name__ == "__main__":
    a = sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    st = a[a.index("--stage") + 1] if "--stage" in a else "grid"
    h = a[a.index("--h") + 1] if "--h" in a else "h30"
    nd = int(a[a.index("--days") + 1]) if "--days" in a else None
    tk = int(a[a.index("--topk") + 1]) if "--topk" in a else 1
    dc = a[a.index("--dec") + 1].split(",") if "--dec" in a else None
    xb = float(a[a.index("--exit") + 1]) if "--exit" in a else uf.FEE_BPS
    sm = int(a[a.index("--sample") + 1]) if "--sample" in a else None
    th = float(a[a.index("--through") + 1]) if "--through" in a else 0.0
    if st == "grid":
        stage_grid(h, nd, tk, dc, xb)
    elif st == "uncond":
        cm = float(a[a.index("--capmult") + 1]) if "--capmult" in a else 1.0
        pb = float(a[a.index("--passive") + 1]) if "--passive" in a else 0.0
        stage_uncond(h, nd, dc, xb, sm, through=th, cap_mult=cm,
                     passive_bps=pb)
    else:
        raise SystemExit(f"unknown stage {st}")
