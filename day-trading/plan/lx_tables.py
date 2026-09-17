"""LIMIT-EXEC stage 2: the project's demonstrated-skill policies under
end-to-end limit execution, account-legal.

THE WALK (plan/uq_strat.py's rules, unchanged): ONE POSITION AT A TIME,
<= 7 tickets a day, $15,000 a ticket.  At each decision slot, if flat,
post limits on the top `post_k` names by score; whichever is hit FIRST
becomes the position and the rest are cancelled; the exit ladder starts at
fill + H; the account is busy until the position is out.

POLICIES (each with its own table, its own splits and its own controls)
  wn     WIDE-NET's walk-forward LightGBM (data/massive/wn/model_scores)
         and UNIVERSE-QUOTES' relabelled-for-the-fill refit
         (plan/uq_out/relabel_scores_*_s1.npy), held-out year, post_k 3,
         h30.  Controls: 30 random seeds, inverted, shuffled-label.
  rev    CLOSE-MOMENTUM's REV 15:30 -> 15:59 composite, k = 7 (the
         Y1-selected members, sign fixed on Y1), plan/cm_rev.build.
         Controls: 30 random, inverted, shuffled within day.
  veto   CATALYST-MINER's ANY_NEG_3d veto on the price-only h60 ranker,
         1/day at 09:35 (its headline), on the catalyst table.
         Controls: 30 random on the SAME vetoed universe, unvetoed.
  All four are first reproduced under MARKET fills through THIS walker
  (`--stage ident` asserts the wn market walk equals uq_strat.simulate_day
  ticket for ticket) and then run under the ladders.

Usage:
  python plan/lx_tables.py --stage ident [--days 12]
  python plan/lx_tables.py --stage wn   [--seeds 30] [--workers 2]
  python plan/lx_tables.py --stage rev  [--seeds 30]
  python plan/lx_tables.py --stage veto [--seeds 30]
"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import lx_engine as X                                         # noqa: E402
import lx_frame as F                                          # noqa: E402
import uq_fills as UF                                         # noqa: E402
import uq_econ as UE                                          # noqa: E402
from wn_lib import OUT as WNOUT, Table                        # noqa: E402

RTH = UF.RTH_DEC
UQOUT = HERE / "uq_out"
CMOUT = HERE.parent / "data" / "massive" / "cm"

# the ladders carried from the frame (stage 1) to the policies
LADDERS = {
    "mkt/mkt": (None, None),
    "bid-rest1-cancel/mkt": (F.E("rest", 1), None),
    "bid-rest3-cancel/mkt": (F.E("rest", 3), None),
    "bid-rest3-cancel/ask-rest3": (F.E("rest", 3), F.Xs("rest", 3)),
    "bid-rest3-mkt/tick3": (F.E("rest", 3, "market"), F.Xs("tick", 3)),
    "tick5-cancel/tick5": (F.E("tick", 5), F.Xs("tick", 5)),
    "tick5-mkt/tick5": (F.E("tick", 5, "market"), F.Xs("tick", 5)),
    "mkt/tick5": (None, F.Xs("tick", 5)),
}


# ------------------------------------------------------------- the walk
def walk_day(day, slots, post_k, hold, entry, exit_, max_tickets=7,
             exit_dec=None, tickets=None, exit_conv="open_next",
             flat_of=None, concurrent=False):
    """slots: list of (m_dec, [(sym, score, cap_shares), ...]) in time
    order.  Returns (records, attempts).  `concurrent=True` takes ALL of
    the top-k at one slot as separate tickets (CLOSE-MOMENTUM's k = 7 at
    15:30), otherwise one position at a time."""
    out, attempts = [], 0
    busy_until = -1
    tick_i = 0
    for m_dec, cands in slots:
        if len(out) >= max_tickets:
            break
        if not concurrent and m_dec + 1 < busy_until:
            continue
        cands = sorted(cands, key=lambda c: -c[1])[:post_k]
        best = None
        for rank, (sym, sc, cap) in enumerate(cands):
            si = day.sidx.get(sym)
            if si is None or not day.has_tape(si):
                continue
            attempts += 1
            tk = (tickets[min(tick_i if concurrent else len(out),
                              len(tickets) - 1)] if tickets else X.TICKET)
            flat_m = flat_of(day, si) if flat_of else int(day.flat_min[si])
            rec = X.ticket(day, si, m_dec, hold, entry, exit_, flat_m,
                           ticket_usd=tk, cap_shares=cap, exit_dec=exit_dec,
                           exit_conv=exit_conv)
            if rec is None:
                continue
            rec["rank"] = rank
            if concurrent:
                out.append(rec)
                tick_i += 1
                if len(out) >= max_tickets:
                    break
                continue
            key = (rec["entry"]["first_sec"], rank)
            if best is None or key < best[0]:
                best = (key, rec)
        if best is not None and not concurrent:
            rec = best[1]
            out.append(rec)
            busy_until = rec["m_out"] + 1
    return out, attempts


# ------------------------------------------------------- wn / cat tables
class WnProvider:
    """Rows of a wn-style table (wn or cat) grouped by date and slot."""

    def __init__(self, t, dec=RTH, h="h30"):
        self.t = t
        self.h = h
        self.dec_i = [UF.DEC_ET.index(x) for x in dec]
        self.di = {d: i for i, d in enumerate(t.dates)}
        self._feat = {}

    def volcap(self, date):
        if date not in self._feat:
            f = np.load(UF.FEAT / f"{date}.npz", allow_pickle=False)
            self._feat = {date: (f["volcap"].astype(float),
                                 [str(s) for s in f["syms"]])}
        return self._feat[date]

    def slots(self, date, score, mask=None):
        t = self.t
        base = (t.date_i == self.di[date]) & t.printed_m \
            & np.isin(t.dec_i, self.dec_i) & np.isfinite(score)
        if mask is not None:
            base &= mask
        rows = np.flatnonzero(base)
        vc, syms = self.volcap(date)
        sidx = {s: i for i, s in enumerate(syms)}
        by = {}
        for r in rows:
            ci = int(t.dec_i[r])
            ti = int(UF.DEC_T[ci])
            m_dec = int(UF.STEPS[ti])
            sym = t.syms[t.sym_i[r]]
            si = sidx.get(sym)
            cap = float(vc[ti, si]) if si is not None else np.nan
            by.setdefault(m_dec, []).append((sym, float(score[r]), cap))
        return sorted(by.items())


def _wn_worker(args):
    date, spec = args
    import lx_engine as XX
    try:
        day = XX.Day(date)
    except Exception as e:
        return date, None, str(e)
    t = Table(spec.get("table", str(Table.__init__.__defaults__[0])))
    prov = WnProvider(t, spec.get("dec", RTH), spec["h"])
    hold = UF.HORIZ[spec["h"]]
    scores = {k: np.load(v).astype(float) for k, v in spec["scores"].items()}
    fin = np.isfinite(scores[spec["ref"]])
    masks = {}
    if spec.get("veto_npz"):
        z = np.load(spec["veto_npz"])
        masks = {k: z[k] for k in z.files}
    res = {}
    for s in range(spec["seeds"]):
        rg = np.random.default_rng(1000 + s)
        scores[f"rand{s}"] = np.where(fin, rg.random(len(fin)), np.nan)
    for lad in spec["ladders"]:
        entry, exit_ = LADDERS[lad]
        for nm, sc in scores.items():
            for mk_name, mask in ([("", None)] + list(masks.items())):
                slots = prov.slots(date, sc, mask)
                recs, att = walk_day(day, slots, spec["post_k"], hold, entry,
                                     exit_, exit_conv="open_next")
                res[(lad, nm + ("|" + mk_name if mk_name else ""))] = (recs, att)
    return date, res, None


def _run(dates, worker, spec, workers, tag):
    acc, att = {}, {}
    t0 = time.monotonic()
    done = 0
    args = [(d, spec) for d in dates]
    it = Pool(workers).imap_unordered(worker, args, chunksize=2) \
        if workers > 1 else map(worker, args)
    for date, res, err in it:
        done += 1
        if err:
            print(f"  !! {date}: {err}", flush=True)
            continue
        for k, (recs, a) in res.items():
            acc.setdefault(k, []).extend(recs)
            att[k] = att.get(k, 0) + a
        if done % 25 == 0 or done == len(dates):
            print(f"  [{tag}] {done}/{len(dates)} days {(time.monotonic()-t0)/60:.1f} min",
                  flush=True)
    return acc, att


def _report(acc, att, ladders, names, seeds, ndays, tag, extra=None):
    rows = {}
    for lad in ladders:
        r = {}
        rnd = {k: [] for k in ("flat", "meas", "zero")}
        for s in range(seeds):
            rr = acc.get((lad, f"rand{s}"), [])
            for k in rnd:
                rnd[k].append(X.summarize(rr, ndays, k)["per_ticket"])
        r["random"] = {k: {"per_ticket_mean": round(float(np.mean(v)), 2),
                           "per_ticket_sd": round(float(np.std(v, ddof=1)), 2)
                           if seeds > 1 else 0.0,
                           "per_month_mean": round(float(np.mean(
                               [X.summarize(acc.get((lad, f"rand{s}"), []), ndays, k)["per_month"]
                                for s in range(seeds)])), 1)}
                       for k, v in rnd.items()}
        r["random"]["tickets_per_day"] = round(float(np.mean(
            [len(acc.get((lad, f"rand{s}"), [])) for s in range(seeds)]) / max(ndays, 1), 3)
        for nm in names:
            rr = acc.get((lad, nm), [])
            row = {k: X.summarize(rr, ndays, k) for k in ("flat", "meas", "zero")}
            row["fills"] = X.fill_stats(rr, att.get((lad, nm), 0))
            row["decomp"] = X.decomposition(rr)
            for k in ("flat", "meas"):
                v = np.array(rnd[k])
                row[k]["edge_vs_random"] = round(row[k]["per_ticket"] - float(v.mean()), 2)
                row[k]["percentile"] = round(100.0 * float(np.mean(v < row[k]["per_ticket"])), 1)
            r[nm] = row
        rows[lad] = r
    print(f"\n== {tag} ==")
    print(f"{'ladder':30s} {'policy':22s} {'n':>5} {'tk/d':>5} {'fill':>6} "
          f"{'flat$/tkt':>10} {'$/mo':>8} {'pct':>5} {'meas$/tkt':>10} {'zero':>8} {'mo+':>6}")
    for lad in ladders:
        r = rows[lad]
        rd = r["random"]
        print(f"{lad:30s} {'random x' + str(seeds):22s} {'':>5} {rd['tickets_per_day']:>5.2f} {'':>6} "
              f"{rd['flat']['per_ticket_mean']:>+10.2f} {rd['flat']['per_month_mean']:>+8.0f} {'':>5} "
              f"{rd['meas']['per_ticket_mean']:>+10.2f} {rd['zero']['per_ticket_mean']:>+8.2f}")
        for nm in names:
            v = r[nm]
            print(f"{'':30s} {nm:22s} {v['flat']['tickets']:>5} {v['flat']['tickets_per_day']:>5.2f} "
                  f"{v['fills']['fill_rate']:>6.3f} {v['flat']['per_ticket']:>+10.2f} "
                  f"{v['flat']['per_month']:>+8.0f} {v['flat']['percentile']:>5.0f} "
                  f"{v['meas']['per_ticket']:>+10.2f} {v['zero']['per_ticket']:>+8.2f} "
                  f"{v['flat']['months_pos']:>6}", flush=True)
    X.write_json(f"tables_{tag}.json", {"days": ndays, "seeds": seeds,
                                        "rows": rows, **(extra or {})})
    return rows


# ------------------------------------------------------------------- wn
def stage_wn(seeds=30, workers=2, ndays=None, ladders=None, post_k=3,
             tag="wn"):
    t = Table()
    days = UE.cached_days(t, 1)
    if ndays:
        days = days[:ndays]
    scores = {"model": str(WNOUT / "model_scores_h30_s0.npy"),
              "relabel": str(UQOUT / "relabel_scores_h30_o10_w1_x10_s1.npy"),
              "relabel_shuf": str(UQOUT / "relabel_scores_shuf_s1.npy"),
              "model_shuf": str(WNOUT / "model_scores_h30_s0_shuf.npy")}
    lx = X.OUT / "lx_relabel_scores_s1.npy"
    if lx.exists():
        scores["lx_refit"] = str(lx)
    # inverted copies
    inv = {}
    for k in ("model", "relabel") + (("lx_refit",) if lx.exists() else ()):
        p = X.OUT / f"_inv_{k}.npy"
        np.save(p, -np.load(scores[k]))
        inv[k + "_inv"] = str(p)
    scores.update(inv)
    ladders = ladders or list(LADDERS)
    spec = {"h": "h30", "scores": scores, "ref": "model", "seeds": seeds,
            "ladders": ladders, "post_k": post_k}
    print(f"[wn] {len(days)} OOS days, post_k {post_k}, {len(ladders)} ladders",
          flush=True)
    acc, att = _run(days, _wn_worker, spec, workers, tag)
    names = [k for k in scores if not k.startswith("rand")]
    return _report(acc, att, ladders, names, seeds, len(days), tag,
                   {"post_k": post_k, "split": 1})


def stage_ident(ndays=12):
    """The wn MARKET walk here == uq_strat.simulate_day(market=True)."""
    import uq_strat as US
    t = Table()
    sc = np.load(WNOUT / "model_scores_h30_s0.npy").astype(float)
    days = UE.cached_days(t, 1)[:ndays]
    prov = WnProvider(t)
    n_chk = n_bad = 0
    worst = 0.0
    for d in days:
        dt = UF.DayTape(d)
        rows = np.flatnonzero((t.date_i == prov.di[d]) & t.printed_m
                              & np.isin(t.dec_i, prov.dec_i) & np.isfinite(sc))
        a = US.simulate_day(t, dt, rows, sc, 10.0, 1, 3, "h30", market=True)
        day = X.Day(d)
        b, _ = walk_day(day, prov.slots(d, sc), 3, 30, None, None,
                        exit_conv="open_next")
        n_chk += 1
        if len(a) != len(b):
            n_bad += 1
            print(f"  {d}: {len(a)} vs {len(b)} tickets")
            continue
        for x, y in zip(a, b):
            dd = abs(x["pnl"] - y["pnl"]["flat"])
            worst = max(worst, dd)
            if x["sym"] != y["sym"] or dd > 0.05:
                n_bad += 1
                print(f"  {d}: {x['sym']} {x['pnl']:.2f} vs {y['sym']} "
                      f"{y['pnl']['flat']:.2f}")
    print(f"IDENT vs uq_strat market walk: {n_chk} days, {n_bad} mismatches, "
          f"worst ${worst:.4f}")
    X.write_json("tables_ident.json", {"days": n_chk, "mismatches": n_bad,
                                       "worst": worst})
    if n_bad:
        raise SystemExit("IDENTITY GATE FAILED")


# ----------------------------------------------------------------- rev
def _rev_worker(args):
    date, spec = args
    import lx_engine as XX
    import cm_lib as CL
    try:
        day = XX.Day(date)
    except Exception as e:
        return date, None, str(e)
    z = np.load(spec["rows_npz"])
    scores = dict(np.load(spec["scores_npz"]))
    dn = spec["date_num"][date]
    sel = np.flatnonzero((z["date_i"] == dn) & (z["dec_i"] == spec["dec_i"])
                         & z["printed_m"])
    syms = [str(s) for s in z["syms"]]
    m_dec = spec["m_dec"]
    flat_m = spec["flat_m"]
    vc = z["volcap"].astype(float)
    res = {}
    for s in range(spec["seeds"]):
        rg = np.random.default_rng(1000 + s)
        scores[f"rand{s}"] = rg.random(len(z["date_i"]))
    for lad in spec["ladders"]:
        entry, exit_ = LADDERS[lad]
        if exit_ is not None:
            exit_ = dict(exit_)
        for nm, sc in scores.items():
            ok = sel[np.isfinite(sc[sel])]
            cands = [(syms[z["sym_i"][r]], float(sc[r]), float(vc[r])) for r in ok]
            recs, att = walk_day(day, [(m_dec, cands)], 7, 0, entry, exit_,
                                 exit_dec=flat_m - spec["exit_wait"] - 1
                                 if exit_ is not None else flat_m,
                                 tickets=CL.TICKETS, exit_conv="close",
                                 flat_of=lambda d, si: flat_m, concurrent=True)
            res[(lad, nm)] = (recs, att)
    return date, res, None


def stage_rev(seeds=30, workers=2, ndays=None, ladders=None, tag="rev",
              dec="15:30", ex="15:59", exit_wait=3):
    import cm_lib as CL
    import cm_rev as CR
    import cm_single as CS
    t = CS.Table("wide")
    sc, members = CR.build(t, dec, ex)
    sc = np.where(np.isfinite(sc), sc, np.nan)
    rng = np.random.default_rng(7)
    shuf = CS._shuffle_day(t, rng) if hasattr(CS, "_shuffle_day") else None
    scores = {"rev": sc, "rev_inv": -sc}
    if shuf is not None:
        try:
            scores["rev_shuf"] = shuf if isinstance(shuf, np.ndarray) else None
        except Exception:
            pass
        if scores.get("rev_shuf") is None:
            scores.pop("rev_shuf", None)
    sp = X.OUT / "_rev_scores.npz"
    X.OUT.mkdir(parents=True, exist_ok=True)
    np.savez(sp, **scores)
    dates = list(t.dates)
    if ndays:
        dates = dates[:ndays]
    ladders = ladders or ["mkt/mkt", "bid-rest1-cancel/mkt",
                          "bid-rest3-mkt/tick3", "tick5-mkt/tick5", "mkt/tick5",
                          "bid-rest3-cancel/ask-rest3"]
    spec = {"rows_npz": str(CMOUT / "rows_wide.npz"), "scores_npz": str(sp),
            "date_num": {d: i for i, d in enumerate(t.dates)},
            "dec_i": t.didx[dec], "m_dec": int(t.m_dec[t.didx[dec]]),
            "flat_m": CL.idx(ex), "seeds": seeds, "ladders": ladders,
            "exit_wait": exit_wait}
    print(f"[rev] {len(dates)} days, {dec}->{ex} k7, members {members}",
          flush=True)
    acc, att = _run(dates, _rev_worker, spec, workers, tag)
    names = [k for k in scores]
    return _report(acc, att, ladders, names, seeds, len(dates), tag,
                   {"members": members, "dec": dec, "exit": ex,
                    "exit_wait": exit_wait})


# ---------------------------------------------------------------- veto
def stage_veto(seeds=30, workers=2, ndays=None, ladders=None, tag="veto",
               h="h60", seed=0):
    import cat_buckets as B
    import cat_lib as C
    import cat_model as CM
    t = CM.load("wide")
    fl = B.flags(t)
    veto = fl["8k_5.02_3d"] | fl["f4_sell_3d"] | fl["analyst_3d"] | fl["10q_18h"]
    vp = X.OUT / "_veto_masks.npz"
    X.OUT.mkdir(parents=True, exist_ok=True)
    np.savez(vp, ANY_NEG_3d=~veto)
    sc_f = C.OUT / f"scores_{h}_base_s{seed}.npy"
    sc = np.load(sc_f).astype(float)
    days = sorted({d for d in t.date_s[np.flatnonzero(np.isfinite(sc))]})
    days = [d for d in days if d in set(UE.cached_days(t, None))]
    if ndays:
        days = days[:ndays]
    inv = X.OUT / "_inv_cat.npy"
    np.save(inv, -sc)
    scores = {"base": str(sc_f), "base_inv": str(inv)}
    ladders = ladders or ["mkt/mkt", "bid-rest1-cancel/mkt",
                          "bid-rest3-mkt/tick3", "tick5-mkt/tick5",
                          "bid-rest3-cancel/ask-rest3"]
    spec = {"h": h, "scores": scores, "ref": "base", "seeds": seeds,
            "ladders": ladders, "post_k": 1, "dec": ["09:35"],
            "table": str(C.OUT / "table.npz"), "veto_npz": str(vp)}
    print(f"[veto] {len(days)} days, {h}, 1/day@09:35, veto ANY_NEG_3d "
          f"removes {int(veto.sum()):,} rows", flush=True)
    acc, att = _run(days, _wn_worker, spec, workers, tag)
    names = ["base", "base|ANY_NEG_3d", "base_inv", "base_inv|ANY_NEG_3d"]
    # random on the vetoed universe is the control that matters
    for lad in ladders:
        for s in range(seeds):
            acc[(lad, f"rand{s}")] = acc.pop((lad, f"rand{s}|ANY_NEG_3d"), [])
            att[(lad, f"rand{s}")] = att.pop((lad, f"rand{s}|ANY_NEG_3d"), 0)
    return _report(acc, att, ladders, names, seeds, len(days), tag,
                   {"h": h, "seed": seed, "random_universe": "vetoed"})


if __name__ == "__main__":
    a = sys.argv
    g = lambda f, d: (type(d)(a[a.index(f) + 1]) if f in a else d)  # noqa: E731
    st = g("--stage", "ident")
    lad = g("--ladders", "")
    lad = lad.split(",") if lad else None
    if st == "ident":
        stage_ident(g("--days", 12))
    elif st == "wn":
        stage_wn(g("--seeds", 30), g("--workers", 2), g("--days", 0) or None,
                 lad, g("--postk", 3), g("--tag", "wn"))
    elif st == "rev":
        stage_rev(g("--seeds", 30), g("--workers", 2), g("--days", 0) or None,
                  lad, g("--tag", "rev"), exit_wait=g("--xwait", 3))
    elif st == "veto":
        stage_veto(g("--seeds", 30), g("--workers", 2), g("--days", 0) or None,
                   lad, g("--tag", "veto"))
    else:
        raise SystemExit(st)
