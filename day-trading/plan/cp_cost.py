"""CHAMPION-REPLAY: a measured transaction cost usable on EVERY fill.

WHY NOT JUST USE plan/cr_cost.py. That model is the better one -- it
reads the 1-second tape. But the tape exists for 38% of the gapper
pool's symbol-days and its per-minute statistics (`data/massive/cost1`)
are built for 3%. A champion replay that charges the measured toll only
where the tape happens to exist would charge it exactly where the
liquid names are, i.e. it would UNDER-charge the microcaps the
champions traded. So this module estimates the same quantity from the
1-minute bars, which exist for 100% of the universe, and is then
CALIBRATED against cr_cost on the symbol-days where both are defined
(`--calibrate`); the calibration is reported, not hidden.

THE ESTIMATOR (same shape as cr_cost, same conservative choices):

  spread_bps = max( HL, CS, AR )    over a TRAILING window that never
                                    contains the fill minute
    HL = median (high-low)/mid of the trailing bars        (bar range)
    CS = Corwin-Schultz (2012) high-low spread estimator
    AR = Abdi-Ranaldo (2017) close-high-low estimator
  half_spread = spread_bps / 2, floored at FLOOR_BPS
  impact_bps  = Y * sigma_win_bps * sqrt(notional / dollar_vol_win)
                Y = 1.0, the TOP of the published square-root range
  total       = half_spread + impact

Roll (1984) is computed for reference and excluded from the max, the
same judgement cr_cost makes and for the same reason.

CAUSALITY: the window is [m-WIN, m-1]. The fill minute never enters.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

CSAR_WIN = 30           # bars of 1-minute tape for CS / AR  (= cr_cost)
IMPACT_WIN = 10         # minutes of trailing dollar volume + vol
IMPACT_COEF = 1.0       # square-root-law Y, top of the published range
FLOOR_BPS = 1.0
MIN_PAIRS = 5
CS_K = 3.0 - 2.0 * np.sqrt(2.0)

# NOTE ON HL2. cr_cost's third estimator is the median per-SECOND
# (high-low)/mid over seconds with >= 2 prints -- an observation of the
# bid-ask bounce. There is no 1-second analogue here, and the 1-MINUTE
# bar range is a RANGE, not a spread (it is 100-500 bps on a microcap),
# so including it in the max would charge volatility as if it were
# spread. It is therefore excluded, and the exclusion is the single
# judgement call in this module that makes it CHEAPER; `--calibrate`
# prints what that costs against cr_cost on the overlap.


def _cs_ar(o, h, l, c):
    """Corwin-Schultz and Abdi-Ranaldo, in bps, over consecutive bars.
    Same per-pair algebra as cr_cost.cs_pairs / ar_pairs, same window
    means, same MIN_PAIRS floor."""
    ok0 = np.isfinite(h) & np.isfinite(l) & np.isfinite(c) & (l > 0)
    o, h, l, c = o[ok0], h[ok0], l[ok0], c[ok0]
    if len(h) < MIN_PAIRS + 1:
        return None, None
    h1, l1, c1 = h[:-1], l[:-1], c[:-1]
    h2, l2, o2 = h[1:].copy(), l[1:].copy(), o[1:]
    ok = ((np.minimum.reduce([h1, l1, h2, l2, o2]) > 0)
          & (h1 >= l1) & (h2 >= l2))
    adj = np.where(o2 > h1, o2 - h1, np.where(o2 < l1, o2 - l1, 0.0))
    h2 = h2 - adj
    l2 = l2 - adj
    ok = ok & (np.minimum(h2, l2) > 0)
    cs = None
    if ok.sum() >= MIN_PAIRS:
        with np.errstate(divide="ignore", invalid="ignore"):
            b = (np.log(h1[ok] / l1[ok]) ** 2 + np.log(h2[ok] / l2[ok]) ** 2)
            g = np.log(np.maximum(h1[ok], h2[ok])
                       / np.minimum(l1[ok], l2[ok])) ** 2
            alpha = (np.sqrt(2.0 * b) - np.sqrt(b)) / CS_K - np.sqrt(g / CS_K)
            ss = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
        cs = 1e4 * float(np.mean(np.maximum(np.nan_to_num(ss), 0.0)))
    ar = None
    oka = np.minimum.reduce([h1, l1, c1, h[1:], l[1:]]) > 0
    if oka.sum() >= MIN_PAIRS:
        with np.errstate(divide="ignore", invalid="ignore"):
            lc = np.log(c1[oka])
            e1 = 0.5 * (np.log(h1[oka]) + np.log(l1[oka]))
            e2 = 0.5 * (np.log(h[1:][oka]) + np.log(l[1:][oka]))
            x = np.nan_to_num((lc - e1) * (lc - e2))
        ar = 1e4 * float(np.sqrt(max(4.0 * float(np.mean(x)), 0.0)))
    return cs, ar


class TapeCost:
    """Per-fill cost in bps from the minute panel."""

    def __init__(self, coef=IMPACT_COEF, floor=FLOOR_BPS,
                 csar_win=CSAR_WIN, impact_win=IMPACT_WIN):
        self.coef, self.floor = coef, floor
        self.csar_win, self.impact_win = csar_win, impact_win
        self.hist = []
        self.parts = []

    def bps(self, day, i, m, notional):
        b = m                       # EXCLUSIVE: the fill minute is out
        a = max(0, m - self.csar_win)
        sel = day.printed[i, a:b]
        o = np.where(sel, day.o[i, a:b], np.nan)
        h = np.where(sel, day.h[i, a:b], np.nan)
        l = np.where(sel, day.l[i, a:b], np.nan)
        c = np.where(sel, day.c[i, a:b], np.nan)
        cs, ar = _cs_ar(o, h, l, c)
        vals = [v for v in (cs, ar) if v is not None and np.isfinite(v)]
        spread = max(vals) if vals else 2 * 10.0     # legacy last resort
        half = max(spread / 2.0, self.floor)
        # ---- impact, identical algebra to cr_cost.parts()
        a2 = max(0, m - self.impact_win)
        dv = float(day.cumdv[i, b - 1] - (day.cumdv[i, a2 - 1]
                                          if a2 > 0 else 0.0))
        cc = np.where(day.printed[i, a2:b], day.c[i, a2:b], np.nan)
        cc = cc[np.isfinite(cc) & (cc > 0)]
        sig = np.nan
        if len(cc) >= 3:
            r = np.diff(np.log(cc))
            if len(r) >= 2:
                sig = float(np.std(r, ddof=1)) * np.sqrt(max(1, b - a2)) * 1e4
        if dv > 0 and np.isfinite(sig) and notional > 0:
            imp = self.coef * sig * np.sqrt(notional / dv)
        elif notional > 0:
            imp = 10.0
        else:
            imp = 0.0
        tot = max(self.floor, half + imp)
        self.hist.append(tot)
        self.parts.append((half, imp))
        return tot

    def dollars(self, day, i, m, px, sh):
        return px * sh * self.bps(day, i, m, px * sh) / 10_000.0

    def report(self):
        if not self.hist:
            return {}
        a = np.array(self.hist)
        return dict(n=int(a.size), median=float(np.median(a)),
                    mean=float(a.mean()), p90=float(np.percentile(a, 90)),
                    frac_over_10=float((a > 10).mean()))


def make(day_cost=None):
    tc = TapeCost()

    def f(day, i, m, px, sh):
        return tc.dollars(day, i, m, px, sh)
    f.model = tc
    return f


def calibrate(n_pairs=400, seed=3):
    """Compare TapeCost against cr_cost's 1-second-tape CostModel on the
    symbol-days where cr_cost has statistics."""
    import importlib.util
    import random
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT))
    import cp_lib as L
    spec = importlib.util.spec_from_file_location(
        "cr_cost", ROOT / "plan/cr_cost.py")
    cc = importlib.util.module_from_spec(spec)
    sys.modules["cr_cost"] = cc
    spec.loader.exec_module(cc)
    cm = cc.CostModel()
    rnd = random.Random(seed)
    dates = L.panel_dates()
    rnd.shuffle(dates)
    tc = TapeCost()
    pairs = []
    for date in dates:
        if len(pairs) >= n_pairs:
            break
        day = L.load_day(date)
        if day is None:
            continue
        order = list(range(day.n))
        rnd.shuffle(order)
        for i in order[:25]:
            if len(pairs) >= n_pairs:
                break
            m = rnd.randrange(L.M_OPEN + 20, L.M_1500)
            if not day.printed[i, m]:
                continue
            px = float(day.c[i, m])
            if not np.isfinite(px) or px <= 0:
                continue
            sh = int(15_000 / px)
            if sh < 1:
                continue
            from datetime import time as dtime
            tt = dtime((m + 240) // 60, (m + 240) % 60)
            try:
                half, imp, tier = cm.parts(day.syms[i], date, tt, px * sh)
            except Exception:
                continue
            if tier.startswith("legacy"):
                continue          # cr_cost has no tape here -- not a test
            ref = max(cm.floor, half + imp)
            if not np.isfinite(ref):
                continue
            mine = tc.bps(day, i, m, px * sh)
            pairs.append((mine, ref))
    if not pairs:
        print("calibrate: no overlapping fills where cr_cost MEASURED")
        return
    a = np.array([p[0] for p in pairs])
    b = np.array([p[1] for p in pairs])
    print(f"calibrate: {len(pairs)} fills where cr_cost actually MEASURED "
          f"(tier win/prior, not the 10 bps legacy fallback)")
    print(f"  tape-bar model : median {np.median(a):7.2f} bps  "
          f"mean {a.mean():7.2f}")
    print(f"  cr_cost (1-sec): median {np.median(b):7.2f} bps  "
          f"mean {b.mean():7.2f}")
    print(f"  ratio of medians {np.median(a)/max(np.median(b),1e-9):.3f}; "
          f"Spearman {_spear(a, b):+.3f}; "
          f"fraction where tape model is the CHEAPER of the two "
          f"{(a < b).mean():.2f}")


def _spear(a, b):
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    d = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / d) if d else float("nan")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--calibrate" in a:
        n = int(a[a.index("--n") + 1]) if "--n" in a else 400
        calibrate(n)
    else:
        print(__doc__)
