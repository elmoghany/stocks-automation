"""COST-REBASE: does the measured cost model track reality?

Three independent validations, none of which the model was fitted to.

  V1  THE LIVE BOOK.  data/liquidity_truth.json holds 176 REAL inside
      books logged by the live paper sessions (bid/ask read off the
      Robinhood book at a known ET minute, 9 days, 35 symbol-days).
      That is the only true NBBO this project owns. The 1-second tape
      for those symbol-days was fetched for BOTH sessions
      (data/massive/trades_pm = 04:00-09:30, data/massive/trades =
      09:30-16:05) and the model's estimate at the same minute --
      computed causally, from bars strictly before it -- is compared to
      the logged spread. Reported as median signed error, median
      absolute error, correlation, and the fraction where the model is
      WIDER than the real book (the conservative direction).

  V2  THE UNIVERSE-QUOTES ESTIMATORS.  Part 5 of universe-quotes-audit
      published six estimator medians on the wide universe. The model's
      spread is compared against all six on the same universe, so the
      rebase can be read next to the number that motivated it.

  V3  WHAT PRICE WAS AVAILABLE.  UNIVERSE-QUOTES' limit-fill results
      are the ground truth for "what could you actually get". This test
      asks the tape the same question the fill engine asks: at a
      decision minute with mark P (the last printed close AT OR BEFORE
      the minute), how far below P does the next second of tape print?
      Bucketed by the model's PREDICTED half-spread, the median
      |first print - mark| should rise with it roughly one-for-one if
      the estimate is a spread and not noise. Slope and per-bucket
      medians are reported.

Also reports the COST DISTRIBUTION the rebase actually applies -- the
fraction of fills above 10 bps, by universe -- which is the guardrail
against a one-directional change.

Usage:
  python plan/cr_validate.py --stage live
  python plan/cr_validate.py --stage tape [--days 60]
  python plan/cr_validate.py --stage all
"""
import gzip
import json
import sys
from datetime import time as dtime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import cr_cost as CC                                        # noqa: E402

PMDIR = ROOT / "data" / "massive" / "trades_pm"
OUT = HERE / "cr_out"


def _rows(d, sym, date):
    f = d / f"{sym}_{date}.json.gz"
    if not f.exists():
        return None
    try:
        with gzip.open(f, "rt") as h:
            return json.load(h)["rows"]
    except Exception:
        return None


class _Est:
    """A standalone spread estimate on an arbitrary session window --
    used only by the validators, which need premarket (04:00) as well
    as the regular session (09:30) that CostModel caches."""

    def __init__(self, rows, date, base_hm, nmin, spread_mode="max"):
        st = CC._stats_from_rows(rows, date, base_hm=base_hm, nmin=nmin)
        self.st = st
        self.base = base_hm[0] * 60 + base_hm[1]
        self.nmin = nmin
        self.mode = spread_mode

    def idx(self, t):
        m = t.hour * 60 + t.minute - self.base
        return m if 0 <= m < self.nmin else -1

    def spread_bps(self, t):
        """max(HL2, CS, AR) over trailing windows ending BEFORE t."""
        m = self.idx(t)
        if m < 0:
            return None, {}
        s = self.st
        a = max(0, m - CC.SPREAD_WIN)
        w = s["hl2"][a:m]
        w = w[np.isfinite(w)]
        hl = float(np.median(w)) if len(w) >= CC.MIN_MIN_HL2 else None
        if hl is None:
            a2 = max(0, m - CC.WIDE_WIN)
            w = s["hl2"][a2:m]
            w = w[np.isfinite(w)]
            hl = float(np.median(w)) if len(w) >= CC.MIN_MIN_HL2 else None
        b0 = max(0, m - CC.CSAR_WIN)
        cs = CC.cs_bps(s["o"], s["h"], s["l"], b0, m)
        ar = CC.ar_bps(s["h"], s["l"], s["c"], b0, m)
        rl = CC.roll_bps(s["c"], b0, m)
        vals = [v for v in (hl, cs, ar) if v is not None]
        if not vals:
            return None, dict(hl2=hl, cs=cs, ar=ar, roll=rl)
        return max(vals), dict(hl2=hl, cs=cs, ar=ar, roll=rl)


# ======================================================================
# V1 -- the live book
# ======================================================================

_VETO_W = ("veto", "skip", "untradeable", "blew", "collapsed", "wide",
           "deteriorated", "flapped")
_PASS_W = ("pass", "clean", "armed", "tightest", "entered", "filled",
           "nearly tradeable", "one tick")


def _ctx_group(o):
    """TRADEABLE vs VETOED, read off the live ledger's own note.

    This split is the whole point of V1. The live sessions logged a
    book either because they were about to trade it (`PASS + ENTERED`,
    `ARMED stop-buy`, `clean book`, `tightest of day`) or because they
    REFUSED it on the 0.5% spread cap (`veto SPREAD ...`). A cost model
    used inside a backtest only ever has to price the FIRST population;
    the second is what the live veto exists to keep out. Reporting one
    number over both would hide that."""
    c = (o.get("context") or "").lower()
    if any(w in c for w in _VETO_W):
        return "vetoed"
    if any(w in c for w in _PASS_W):
        return "tradeable"
    return "other"


def stage_live():
    obs = json.loads((ROOT / "data" / "liquidity_truth.json")
                     .read_text())["observations"]
    rows = []
    cache = {}
    for o in obs:
        if o.get("bid") is None or o.get("ask") is None:
            continue
        sym, date = o["symbol"], o["date"]
        hh, mm = (int(x) for x in o["time_et"].split(":")[:2])
        t = dtime(hh, mm)
        pre = t < dtime(9, 30)
        key = (sym, date, pre)
        if key not in cache:
            if pre:
                r = _rows(PMDIR, sym, date)
                cache[key] = _Est(r, date, (4, 0), 330) if r else None
            else:
                r = _rows(CC.XDIR, sym, date)
                cache[key] = _Est(r, date, (9, 30), CC.NMIN) if r else None
        est = cache[key]
        if est is None:
            continue
        sp, parts = est.spread_bps(t)
        real = 1e4 * (o["ask"] - o["bid"]) / ((o["ask"] + o["bid"]) / 2.0)
        rows.append(dict(sym=sym, date=date, t=o["time_et"],
                         phase=o["phase"], prec=o["time_precision"],
                         ctx=o.get("context", ""), grp=_ctx_group(o),
                         real_bps=real, est_bps=sp, **parts))
    got = [r for r in rows if r["est_bps"] is not None]
    rep = {"n_obs_with_book": len(rows), "n_estimable": len(got)}
    if got:
        e = np.array([r["est_bps"] for r in got])
        a = np.array([r["real_bps"] for r in got])
        rep.update(
            median_real_bps=float(np.median(a)),
            median_est_bps=float(np.median(e)),
            median_signed_err_bps=float(np.median(e - a)),
            median_abs_err_bps=float(np.median(np.abs(e - a))),
            median_ratio=float(np.median(e / np.maximum(a, 1e-9))),
            spearman=_spearman(e, a),
            pearson=float(np.corrcoef(e, a)[0, 1]) if len(e) > 2 else None,
            frac_model_wider=float((e >= a).mean()))
        for ph in ("premarket", "postopen"):
            s = [r for r in got if r["phase"] == ph]
            if s:
                ee = np.array([r["est_bps"] for r in s])
                aa = np.array([r["real_bps"] for r in s])
                rep[f"{ph}_n"] = len(s)
                rep[f"{ph}_median_real"] = float(np.median(aa))
                rep[f"{ph}_median_est"] = float(np.median(ee))
                rep[f"{ph}_median_abs_err"] = float(
                    np.median(np.abs(ee - aa)))
                rep[f"{ph}_frac_wider"] = float((ee >= aa).mean())
        for g in ("tradeable", "vetoed", "other"):
            s = [r for r in got if r["grp"] == g]
            if s:
                ee = np.array([r["est_bps"] for r in s])
                aa = np.array([r["real_bps"] for r in s])
                rep[f"grp_{g}"] = dict(
                    n=len(s), median_real=float(np.median(aa)),
                    median_est=float(np.median(ee)),
                    median_ratio=float(np.median(ee / np.maximum(aa, 1e-9))),
                    median_abs_err=float(np.median(np.abs(ee - aa))),
                    frac_wider=float((ee >= aa).mean()),
                    n_postopen=int(sum(1 for r in s
                                       if r["phase"] == "postopen")))
        s = [r for r in got if r["prec"] == "exact"]
        if s:
            ee = np.array([r["est_bps"] for r in s])
            aa = np.array([r["real_bps"] for r in s])
            rep["exact_n"] = len(s)
            rep["exact_median_abs_err"] = float(np.median(np.abs(ee - aa)))
            rep["exact_median_ratio"] = float(
                np.median(ee / np.maximum(aa, 1e-9)))
    OUT.mkdir(exist_ok=True)
    (OUT / "validate_live.json").write_text(
        json.dumps({"report": rep, "rows": got}, indent=1))
    print(json.dumps(rep, indent=1))
    return rep


def _spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if len(a) < 3:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


# ======================================================================
# V2 / V3 -- the tape
# ======================================================================

def _uni_pairs(ndays):
    UNI = HERE / "rl2" / "out" / "universe"
    fs = sorted(UNI.glob("*.json"))
    step = max(1, len(fs) // ndays)
    out = []
    for f in fs[::step][:ndays]:
        d = f.stem
        for r in json.loads(f.read_text()):
            out.append((r["symbol"], d))
    return out


def stage_tape(ndays=60, per_day=40, seed=0):
    rng = np.random.default_rng(seed)
    pairs = _uni_pairs(ndays)
    by = {}
    for s, d in pairs:
        by.setdefault(d, []).append(s)
    ests = {"hl2": [], "cs": [], "ar": [], "roll": [], "model": []}
    v3 = []            # (pred_half_bps, |first print - mark| bps)
    costs = []
    cm = CC.CostModel()
    for d, syms in sorted(by.items()):
        pick = list(syms)
        rng.shuffle(pick)
        for sym in pick[:per_day]:
            r = _rows(CC.XDIR, sym, d)
            if not r:
                continue
            est = _Est(r, d, (9, 30), CC.NMIN)
            st = est.st
            # one decision minute per RTH hour
            for m in (35, 60, 95, 140, 185, 230, 275, 320):
                t = dtime((CC.MIN_M + m) // 60, (CC.MIN_M + m) % 60)
                sp, parts = est.spread_bps(t)
                for k in ("hl2", "cs", "ar", "roll"):
                    if parts.get(k) is not None:
                        ests[k].append(parts[k])
                if sp is not None:
                    ests["model"].append(sp)
                costs.append(cm.cost_bps(sym, d, t, 15000.0))
                # V3: mark = last printed close <= m-1 ; first print at m
                prev = st["c"][:m]
                prev = prev[prev > 0]
                if sp is None or not len(prev) or st["o"][m] <= 0:
                    continue
                mark = float(prev[-1])
                first = float(st["o"][m])
                v3.append((sp / 2.0, 1e4 * abs(first - mark) / mark))
    rep = {"n_days": len(by), "n_points": len(ests["model"])}
    for k, v in ests.items():
        if v:
            a = np.array(v)
            rep[k] = dict(n=len(a), median=float(np.median(a)),
                          mean=float(a.mean()),
                          p75=float(np.percentile(a, 75)),
                          p90=float(np.percentile(a, 90)))
    if costs:
        c = np.array(costs)
        rep["cost_bps_per_side_15k"] = dict(
            n=len(c), median=float(np.median(c)), mean=float(c.mean()),
            p25=float(np.percentile(c, 25)),
            p75=float(np.percentile(c, 75)),
            p90=float(np.percentile(c, 90)),
            frac_gt_10=float((c > 10).mean()),
            frac_gt_20=float((c > 20).mean()))
        rep["cost_tally"] = cm.report()
    if v3:
        a = np.array(v3)
        qs = np.quantile(a[:, 0], np.linspace(0, 1, 11))
        bucket = []
        for i in range(10):
            m = (a[:, 0] >= qs[i]) & (a[:, 0] <= qs[i + 1])
            if m.sum() >= 20:
                bucket.append(dict(
                    pred_half_bps=float(np.median(a[m, 0])),
                    obs_move_bps=float(np.median(a[m, 1])),
                    n=int(m.sum())))
        rep["v3_buckets"] = bucket
        if len(bucket) >= 3:
            x = np.array([b["pred_half_bps"] for b in bucket])
            y = np.array([b["obs_move_bps"] for b in bucket])
            A = np.vstack([x, np.ones_like(x)]).T
            sl, ic = np.linalg.lstsq(A, y, rcond=None)[0]
            rep["v3_slope"] = float(sl)
            rep["v3_intercept_bps"] = float(ic)
            rep["v3_r"] = float(np.corrcoef(x, y)[0, 1])
    OUT.mkdir(exist_ok=True)
    (OUT / "validate_tape.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    return rep


def main():
    a = sys.argv[1:]
    st = a[a.index("--stage") + 1] if "--stage" in a else "all"
    nd = int(a[a.index("--days") + 1]) if "--days" in a else 60
    if st in ("live", "all"):
        print("== V1 live book ==")
        stage_live()
    if st in ("tape", "all"):
        print("== V2/V3 tape ==")
        stage_tape(nd)


if __name__ == "__main__":
    main()
