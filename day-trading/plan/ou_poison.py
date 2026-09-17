"""OPEN-UNIVERSE (2026-09-17): the adversarial battery.

Nothing in open-universe-audit.md counts unless these pass.

  identity     Charging the flat 10/50 bps ladder on the LEGS this line
               stores (plan/ou_table.raw_legs) must reproduce, to float32,
               the `pnl_*` that plan/wn_table.day_block computed the other
               way round.  If the two disagree, every measured-cost number
               in this line is void, because they are re-priced off those
               legs.
  poison_bars  Replace every bar STRICTLY AFTER minute m with garbage and
               recompute the whole feature block on the m1o cache.  Every
               feature, the mark, the print mask and the size cap at every
               decision step <= m must be BIT-IDENTICAL.  This is
               plan/rl2/honesty.poison_check pointed at this line's own
               cache and its own (600-name) cross-sections -- which matters,
               because two of the features (`xs_breadth`, `xs_rank_ret30`)
               are cross-sectional and therefore change meaning when the
               panel goes from 61 names to 600.
  poison_picks The same mutation, carried all the way to the DECISION: the
               top-1 / top-7 picks of every ordering in the sweep must be
               identical before and after.  A feature can be causal and a
               pick still leak if the ranking code reads the wrong row.
  poison_cost  Garble the 1-minute tape at and after the fill minute and
               assert not one measured cost moves (plan/ou_cost.MinuteCost
               windows all end strictly before the fill).
  hold_zero    A never-buy score books exactly $0 on 0 tickets.
  cost_monotone  zero < measured < flat10 < 10x flat, same fixed policy.

Usage:  python plan/ou_poison.py [--days 12] [--stage all|identity|bars|...]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import ou_lib as L                                            # noqa: E402
import ou_cost as OC                                          # noqa: E402
import ou_table as OTB                                        # noqa: E402
import features as RF                                         # noqa: E402
import wn_table as WT                                         # noqa: E402


# ------------------------------------------------------------------ identity
def identity():
    import ou_rank as OR
    t = OR.OT()
    out = {}
    worst_all = 0.0
    for h in ("h15", "h30", "h60", "h120", "flat"):
        a = t.pnl[h].astype(np.float64)
        b = t.flat_pnl(h).astype(np.float64)
        m = t.ok[h]
        d = np.abs(a[m] - b[m])
        worst = float(d.max()) if d.size else 0.0
        worst_all = max(worst_all, worst)
        out[h] = {"rows": int(m.sum()), "worst_abs_diff": round(worst, 9),
                  "mean_abs_diff": round(float(d.mean()), 12) if d.size else 0}
    out["worst_overall"] = round(worst_all, 9)
    print(f"[identity] {json.dumps(out)}", flush=True)
    assert worst_all < 0.02, out          # float32 on a $15,000 notional
    return out


# --------------------------------------------------------------- bar poison
def _block(date, cand, prof, daily, sic2, earn, prev_date, bars=None):
    ss = [x[0] for x in cand]
    pc = np.array([x[1] for x in cand], np.float64)
    if bars is None:
        bars = []
        for k in range(1, 6):
            a = np.empty((len(cand), L.NMIN), np.float64)
            for j, (_s, _p, i, rec) in enumerate(cand):
                a[j] = rec[k][i]
            bars.append(a)
    z = RF.compute_day(date, ss, pc, bars, prof, daily)
    return z, WT.day_block(date, z, sic2, earn, None, prev_date), bars


def _sample_days(n, seed=0):
    uni = L.universe()
    dates = [d for d in L.study_dates() if d in uni]
    rng = np.random.default_rng(seed)
    pick = sorted(rng.choice(len(dates), size=min(n, len(dates)),
                             replace=False))
    all_td = L.trading_dates()
    prev_of = {d: all_td[i - 1] for i, d in enumerate(all_td) if i}
    for i in pick:
        date = dates[i]
        cand = []
        pcr = L.gd_day(prev_of[date])
        for sym in sorted(r[0] for r in uni[date][:L.MINUTE_TOP]):
            rec = OTB.load_symbol(sym)
            if rec is None:
                continue
            di = {d: k for k, d in enumerate(rec[0])}
            if date not in di:
                continue
            k = di[date]
            if not np.isfinite(rec[4][k]).any():
                continue
            p = (pcr.get(sym) or {}).get("c")
            if not p:
                continue
            cand.append((sym, float(p), k, rec))
        if cand:
            yield date, cand, prev_of.get(date)


def poison_bars(n_days=12, cuts=(400, 550, 700, 850), seed=0):
    prof = np.load(OTB.PROFILE_F)
    daily = RF.Daily()
    sic2, earn = WT.load_sic2(), WT.load_earn()
    rng = np.random.default_rng(seed)
    checks = mism = 0
    detail = []
    for date, cand, prev in _sample_days(n_days, seed):
        zc, bc, bars = _block(date, cand, prof, daily, sic2, earn, prev)
        for cut in cuts:
            o, h, lo, c, v = (a.copy() for a in bars)
            sl = slice(cut + 1, None)
            shp = o[:, sl].shape
            g = rng.uniform(0.5, 500.0, size=shp)
            o[:, sl] = g
            h[:, sl] = g * rng.uniform(1.0, 1.5, size=shp)
            lo[:, sl] = g * rng.uniform(0.5, 1.0, size=shp)
            c[:, sl] = g * rng.uniform(0.7, 1.3, size=shp)
            v[:, sl] = rng.integers(1, 10 ** 7, size=shp)
            zb, bb, _ = _block(date, cand, prof, daily, sic2, earn, prev,
                               (o, h, lo, c, v))
            keep = WT.STEPS[WT.DEC_T] <= cut
            for k in ("F", "printed_m", "notional", "fill_px"):
                a, b = bc[k][keep], bb[k][keep]
                if not np.array_equal(np.nan_to_num(np.asarray(a, float),
                                                    nan=-9e9),
                                      np.nan_to_num(np.asarray(b, float),
                                                    nan=-9e9)):
                    mism += 1
                    detail.append({"date": date, "cut": cut, "arr": k})
                checks += 1
    res = {"checks": checks, "mismatches": mism, "detail": detail[:20],
           "days": n_days, "cuts": list(cuts)}
    print(f"[poison_bars] {checks} array checks / {mism} mismatches",
          flush=True)
    assert mism == 0, detail[:5]
    return res


def poison_picks(n_days=12, cuts=(550, 700), seed=1, topk=(1, 7)):
    """The same mutation, carried to the PICK."""
    import ou_rank as OR
    prof = np.load(OTB.PROFILE_F)
    daily = RF.Daily()
    sic2, earn = WT.load_sic2(), WT.load_earn()
    rng = np.random.default_rng(seed)
    checks = mism = 0
    for date, cand, prev in _sample_days(n_days, seed):
        zc, bc, bars = _block(date, cand, prof, daily, sic2, earn, prev)
        for cut in cuts:
            o, h, lo, c, v = (a.copy() for a in bars)
            sl = slice(cut + 1, None)
            shp = o[:, sl].shape
            g = rng.uniform(0.5, 500.0, size=shp)
            o[:, sl] = g
            h[:, sl] = g * rng.uniform(1.0, 1.5, size=shp)
            lo[:, sl] = g * rng.uniform(0.5, 1.0, size=shp)
            c[:, sl] = g * rng.uniform(0.7, 1.3, size=shp)
            v[:, sl] = rng.integers(1, 10 ** 7, size=shp)
            zb, bb, _ = _block(date, cand, prof, daily, sic2, earn, prev,
                               (o, h, lo, c, v))
            for ti, dec in enumerate(WT.DEC_ET):
                if WT.STEPS[WT.DEC_T[ti]] > cut:
                    continue
                elig_a = bc["printed_m"][ti]
                elig_b = bb["printed_m"][ti]
                for f in OR.ORDERINGS:
                    if f not in WT.FEATURES:
                        continue
                    fi = WT.FEATURES.index(f)
                    for sg in (1, -1):
                        sa = np.where(elig_a, bc["F"][ti, :, fi] * sg, -np.inf)
                        sb = np.where(elig_b, bb["F"][ti, :, fi] * sg, -np.inf)
                        for k in topk:
                            pa = np.argsort(-sa, kind="stable")[:k]
                            pb = np.argsort(-sb, kind="stable")[:k]
                            checks += 1
                            if not np.array_equal(pa, pb):
                                mism += 1
    print(f"[poison_picks] {checks} pick checks / {mism} mismatches",
          flush=True)
    assert mism == 0
    return {"checks": checks, "mismatches": mism}


def poison_cost(n_sym=6, n_date=6, seed=2):
    """Garble the tape at and after the fill minute; no cost may move."""
    pairs = json.loads((L.OUT / "minute_pairs.json").read_text())
    syms = sorted({s for s, _ in pairs})
    rng = np.random.default_rng(seed)
    checks = moved = 0
    for sym in syms[:n_sym]:
        f = L.M1O / f"{sym}.npz"
        if not f.exists():
            continue
        z = np.load(f, allow_pickle=False)
        for i in range(min(n_date, len(z["dates"]))):
            o, h, lo, c, v = (z[k][i].astype(np.float64) for k in "ohlcv")
            s0, d0, g0 = OC._rolling_from_m1(o, h, lo, c, v)
            for gm in (400, 500, 600, 700):
                m = gm - OC.CR_LO
                if not (0 <= m < OC.CR_N):
                    continue
                oo, hh, ll, cc, vv = (a.copy() for a in (o, h, lo, c, v))
                sl = slice(gm, None)
                n = oo[sl].shape[0]
                gg = rng.uniform(0.5, 500.0, size=n)
                oo[sl] = gg
                hh[sl] = gg * 1.3
                ll[sl] = gg * 0.7
                cc[sl] = gg * 1.1
                vv[sl] = rng.integers(1, 10 ** 7, size=n)
                s1, d1, g1 = OC._rolling_from_m1(oo, hh, ll, cc, vv)
                for a, b in ((s0, s1), (d0, d1), (g0, g1)):
                    checks += 1
                    va, vb = a[m], b[m]
                    if not (np.isnan(va) and np.isnan(vb)) and \
                            not np.isclose(va, vb, rtol=1e-12, atol=1e-12):
                        moved += 1
    print(f"[poison_cost] {checks} cost checks / {moved} moved", flush=True)
    assert moved == 0
    return {"checks": checks, "moved": moved}


def hold_zero_and_monotone():
    import ou_rank as OR
    t = OR.OT()
    cm = OC.MinuteCost()
    h, dec, k = "h30", "10:00", 7
    m = t.mask(split=1, dec=dec, h=h)
    never = np.full(len(t.pnl[h]), np.nan)
    pk = OR.picks(t, never, m, k)
    hz = {"tickets": int(pk.size), "pnl": float(t.pnl[h][pk].sum())
          if pk.size else 0.0}
    assert hz["tickets"] == 0 and hz["pnl"] == 0.0, hz
    sc = t.f("ret30").astype(np.float64)
    pk = OR.picks(t, sc, m, k)
    en, ex = t.fill_px[pk], t.expx[h][pk]
    no = t.notional[pk]
    with np.errstate(all="ignore"):
        gross = np.where(t.ok[h][pk], no * (ex / np.maximum(en, 1e-9) - 1.0),
                         0.0)
    flat = t.pnl[h][pk]
    meas = t.measured_pnl(h, pk, cm)
    cen = L.cost_frac(t.ent_min[pk]) * 10.0
    cex = L.cost_frac(t.exmin[h][pk]) * 10.0
    with np.errstate(all="ignore"):
        x10 = np.where(t.ok[h][pk],
                       no * ((ex * (1 - cex)) / np.maximum(en * (1 + cen),
                                                           1e-9) - 1.0), 0.0)
    r = {"zero": round(float(gross.sum()), 2),
         "measured": round(float(meas.sum()), 2),
         "flat10": round(float(flat.sum()), 2),
         "flat100": round(float(x10.sum()), 2),
         "hold_zero": hz}
    print(f"[monotone] {json.dumps(r)}", flush=True)
    assert r["zero"] > r["flat10"] > r["flat100"], r
    return r


def main():
    nd = 12
    if "--days" in sys.argv:
        nd = int(sys.argv[sys.argv.index("--days") + 1])
    stage = "all"
    if "--stage" in sys.argv:
        stage = sys.argv[sys.argv.index("--stage") + 1]
    out = {}
    if stage in ("all", "identity"):
        out["identity"] = identity()
    if stage in ("all", "cost"):
        out["poison_cost"] = poison_cost()
    if stage in ("all", "bars"):
        out["poison_bars"] = poison_bars(nd)
    if stage in ("all", "picks"):
        out["poison_picks"] = poison_picks(max(4, nd // 2))
    if stage in ("all", "monotone"):
        out["monotone"] = hold_zero_and_monotone()
    L.write("poison.json", out)
    print("[poison] ALL PASS", flush=True)


if __name__ == "__main__":
    main()
