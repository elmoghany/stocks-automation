"""LEADS-TEST: honest gapper engine with the hygiene stack (copy-and-modify of
cp_sim's run_day; cp_sim itself is NOT edited and is imported only for its
helpers: _next_print, _pressure_at, _prev_print, _bearish, _sell_fill).

Frame (cp_sim post-retraction): live scanner universe (LAST: an RTH close
>= 1.10 x prev close, last >= $2), 5-minute grid, decision at grid minute t
fills at the OPEN of the next printed bar after t (RS_DEFER), gap-through
sells, one position at a time, <= 7 tickets/day, $10k tickets capped at 20%
of trailing 5-minute volume, rotation, flat by 15:00.

CAUSAL TIE-BREAK (the LEGACY-2 leak fix): every rank is
    np.lexsort((u_seeded, -volume_so_far, key))
i.e. key first, then share volume 04:00..t (desc), then a seeded uniform.
Pool/file order is never used; `selftest()` checks this by shuffling the
panel's row order and asserting identical legs.

HYGIENE STACK (cfg hyg=True), applied to candidates at decision minute t:
  * pool hygiene: type in {CS, ADRC} (or unknown), not a test symbol,
    first printed bar open / prev close in [0.5, 2.0]
  * spread: max(CS, AR)/2 over the 30 bars [t-29, t] <= 10 bps
  * liquidity: dvol60 >= $5M
  * range: sigma1 at t defined and <= 0.017
  * no premarket entries (t >= 09:35 by construction)
EXITS:
  exit="stack": no fixed stop; +5% target = first CLOSE >= 1.05 x entry,
      sold at the NEXT printed bar's open; 10% trail from the highest high
      since entry (level from bars BEFORE the current one, fill min(level,
      open) clamped); bearish engulfing only when close >= 1.01 x entry,
      sold at the NEXT printed bar's open; flatten at the last bar <= 15:00.
  exit="r4": cp_sim's R4 exits (20% trail, 10%/40% by pressure, bearish
      while close > entry) with the bearish fill moved to the next open
      (the live R4 config).
COSTS (per side, bps): central = 0.5*half + 4.4 before 10:30 else 3.1
  (LEGACY-9), half = max(CS,AR)/2 on the 30 bars before the fill minute;
  stress = flat 12.
All $ are per $10k ticket: 1e4 x leg return (LEGACY-10 convention).
"""
import json
import sys
import zlib
from pathlib import Path

import numpy as np

P = Path(__file__).resolve().parent
ROOT = P.parent
sys.path.insert(0, str(P))
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402
import cp_sim as S                                          # noqa: E402
import cp_cost as C                                         # noqa: E402

VOL_CAP = 0.20
TKT = 10_000.0
M1030 = L.mgrid(10, 30)
_TYPES = None


def types():
    global _TYPES
    if _TYPES is None:
        f = ROOT / "data/massive/ticker_types.json"
        _TYPES = json.loads(f.read_text()) if f.exists() else {}
    return _TYPES


def cfg(**o):
    c = dict(rank="coil", t_start=L.mgrid(9, 35), cutoff=L.mgrid(14, 30),
             exit_end=L.M_1500, step=5, seed=0, hyg=True, exit="stack",
             gain_max=None, ntickets=7, gap7=True, universe="LAST",
             spread_max=10.0, dvol_min=5e6, sig_max=0.017, tc=None)
    c.update(o)
    return c


def half_at(day, i, m, win=30):
    """max(CS, AR)/2 (bps) on printed bars [m-win, m-1]; 10 when unknown
    (lm9_feat.half_at, verbatim logic)."""
    a, b = max(0, m - win), m
    sel = day.printed[i, a:b]
    o = np.where(sel, day.o[i, a:b], np.nan)
    h = np.where(sel, day.h[i, a:b], np.nan)
    lo = np.where(sel, day.l[i, a:b], np.nan)
    c = np.where(sel, day.c[i, a:b], np.nan)
    cs, ar = C._cs_ar(o, h, lo, c)
    vals = [v for v in (cs, ar) if v is not None and np.isfinite(v)]
    return max(max(vals) / 2.0, 1.0) if vals else 10.0


class DayCtx:
    """Per-date cached causal quantities shared by every config."""

    def __init__(self, date, day, Fd):
        self.date, self.day, self.Fd = date, day, Fd
        self.grid = list(Fd["grid"])
        self.gidx = {m: k for k, m in enumerate(self.grid)}
        n = day.n
        T = types()
        ok = np.ones(n, bool)
        for i, s in enumerate(day.syms):
            t = T.get(s)
            if isinstance(t, str) and t not in ("CS", "ADRC", "?"):
                ok[i] = False
            if s.startswith("Z") and s.endswith("ZZT"):
                ok[i] = False
            row = np.where(day.printed[i])[0]
            if len(row) and day.pc[i] > 0:
                r = day.o[i, row[0]] / day.pc[i]
                if not (0.5 <= r <= 2.0):
                    ok[i] = False
        self.pool_ok = ok
        self._half = {}

    def half(self, i, m_end):
        """spread estimate on bars [m_end-29, m_end] (i.e. <= m_end)."""
        k = (i, m_end)
        if k not in self._half:
            self._half[k] = half_at(self.day, i, m_end + 1)
        return self._half[k]


def rank_order(ctx, gi, t, cand, c, rng):
    day, Fd = ctx.day, ctx.Fd
    volsofar = day.cumv[cand, t]
    u = np.array([zlib.crc32(f"{c['seed']}|{ctx.date}|{t}|{day.syms[i]}"
                             .encode()) for i in cand], float)
    r = c["rank"]
    if r == "rand":
        return cand[np.argsort(u, kind="stable")]
    coil = np.nan_to_num(Fd["coil"][cand, gi].astype(float), nan=0.0)
    if r == "coil":
        key = -np.round(coil, 6)
    elif r in ("quiet", "ret15"):
        last = day.last
        r15 = last[cand, t] / last[cand, max(t - 15, 0)] - 1.0
        r15 = np.where(np.isfinite(r15), r15, 0.0)
        pr15 = _pct(r15)
        if r == "quiet":
            key = -(_pct(coil) - pr15)
        else:
            key = pr15
        key = np.round(key, 9)
    else:
        raise ValueError(r)
    return cand[np.lexsort((u, -volsofar, key))]


def _pct(x):
    """average-tie percentile rank in [0,1]."""
    n = len(x)
    if n <= 1:
        return np.zeros(n)
    o = np.argsort(x, kind="mergesort")
    rk = np.empty(n)
    rk[o] = np.arange(n)
    # average ties
    xs = x[o]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[j + 1] == xs[i]:
            j += 1
        if j > i:
            rk[o[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return rk / (n - 1)


def run_day(ctx, c):
    day, Fd = ctx.day, ctx.Fd
    elig = Fd["elig_last" if c["universe"] == "LAST" else "elig_high"]
    g7 = Fd["gap7"]
    legs = []
    rng = np.random.default_rng([c["seed"], int(ctx.date.replace("-", ""))])
    t, ti, last_exit = c["t_start"], 0, -1
    while ti < c["ntickets"] and t < c["cutoff"]:
        if t not in ctx.gidx:
            t += 1
            continue
        gi = ctx.gidx[t]
        cand = np.where(elig[:, gi])[0]
        if c["gain_max"] is not None and len(cand):
            gn = Fd["gain_now"][cand, gi]
            cand = cand[np.isfinite(gn) & (gn <= c["gain_max"])]
        if len(cand) == 0:
            t += c["step"]
            continue
        order = rank_order(ctx, gi, t, cand, c, rng)
        if c["hyg"]:
            keep = []
            for i in order:
                i = int(i)
                if not ctx.pool_ok[i]:
                    continue
                dv = Fd["dvol60"][i]
                if not (np.isfinite(dv) and dv >= c["dvol_min"]):
                    continue
                sg = Fd["sigma1"][i, gi]
                if not (np.isfinite(sg) and sg <= c["sig_max"]):
                    continue
                if ctx.half(i, t) > c["spread_max"]:
                    continue
                keep.append(i)
                if len(keep) >= 8:
                    break
            order = np.array(keep, int)
        leg = None
        for k, i in enumerate(order[:8]):
            i = int(i)
            if c["gap7"]:
                lim = 0.35 if k == 0 else 0.20
                if np.isfinite(g7[i]) and g7[i] > lim:
                    continue
            leg = try_ticket(ctx, i, t, c)
            if leg is not None:
                break
        if leg is None:
            t += c["step"]
            continue
        leg["ticket"] = ti
        leg["dec"] = t
        legs.append(leg)
        ti += 1
        t = max(t + c["step"], leg["exit_min"] + 1)
    return legs


def try_ticket(ctx, i, t, c):
    day = ctx.day
    em = S._next_print(day, i, t + 1, limit=5)
    if em is None:
        return None
    px = float(day.o[i, em])
    if not np.isfinite(px) or px < 2.0:
        return None
    v5 = float(day.cumv[i, em - 1] - day.cumv[i, max(em - 6, 0)])
    sh = int(min(TKT / px, VOL_CAP * v5))
    if sh < 1:
        return None
    if c["exit"] == "stack":
        xm, xp, why = walk_stack(day, i, em, px, c["exit_end"])
    else:
        cc = S.default_cfg(stop_pct=None, exit_end=c["exit_end"])
        xm, xp, why = walk_r4(day, Fd_dummy, i, em, px, cc)
    if xp is None:
        return None
    ret = xp / px - 1.0
    he = ctx.half(i, em - 1)
    hx = ctx.half(i, xm - 1)
    cen = (0.5 * he + (4.4 if em < M1030 else 3.1)) * px + \
          (0.5 * hx + (4.4 if xm < M1030 else 3.1)) * xp
    cen_ret = cen / px / 1e4
    return dict(sym=day.syms[i], i=i, entry_min=em, entry=px, exit_min=xm,
                exit=xp, reason=why, shares=sh, ret=ret,
                g=1e4 * ret, n_c=1e4 * (ret - cen_ret),
                n_12=1e4 * (ret - 12e-4 * (1 + xp / px)),
                h_e=he, notional=sh * px)


Fd_dummy = None


def walk_stack(day, i, em, entry, end):
    peak = float(day.h[i, em])
    pending = None
    tgt = entry * 1.05
    for m in range(em + 1, end + 1):
        if not day.printed[i, m]:
            continue
        o, h, lo, cl = (float(day.o[i, m]), float(day.h[i, m]),
                        float(day.l[i, m]), float(day.c[i, m]))
        if pending is not None:
            return m, o, pending
        lvl = peak * 0.90
        if lo <= lvl:
            return m, float(min(max(min(lvl, o), lo), h)), "trail10"
        peak = max(peak, h)
        if cl >= tgt:
            pending = "target5"
            continue
        if cl >= entry * 1.01 and S._bearish(day, i, m):
            pending = "bearish"
            continue
    m = end
    while m > em and not day.printed[i, m]:
        m -= 1
    if m <= em:
        return None, None, None
    return m, float(day.c[i, m]), ("flatten" if pending is None else pending + "@flat")


def walk_r4(day, Fd, i, em, entry, cfg):
    peak = entry
    pending = None
    for m in range(em + 1, cfg["exit_end"] + 1):
        if not day.printed[i, m]:
            continue
        lo, hi, cl, o = (float(day.l[i, m]), float(day.h[i, m]),
                         float(day.c[i, m]), float(day.o[i, m]))
        if pending:
            return m, o, "bearish"
        peak = max(peak, hi)
        tw = cfg["trail_pct"]
        p10 = S._pressure_at(day, i, m, 10)
        if p10 is not None:
            if p10 <= -cfg["trail_thr"]:
                tw = cfg["trail_lo"]
            elif p10 >= cfg["trail_thr"]:
                tw = cfg["trail_hi"]
        lvl = peak * (1 - tw)
        if lo <= lvl < peak:
            return m, S._sell_fill(day, i, m, lvl), f"trail {tw:.2f}"
        if cl > entry and S._bearish(day, i, m):
            pending = True
    m = cfg["exit_end"]
    while m > em and not day.printed[i, m]:
        m -= 1
    if m <= em:
        return None, None, None
    return m, float(day.c[i, m]), "flatten"


def run_many(dates, jobs, progress=False, perm=False):
    """jobs: {name: cfg}. Returns {name: [legs]}; each date loaded once.
    perm=True shuffles the panel row order (tie-break leak test)."""
    out = {k: [] for k in jobs}
    for n, date in enumerate(dates):
        Fd = F.load(date)
        day = L.load_day(date) if Fd is not None else None
        if day is None:
            continue
        if perm:
            Fd, day = _permute(date, Fd, day)
        ctx = DayCtx(date, day, Fd)
        for k, c in jobs.items():
            if c.get("tc") is not None and not c["tc"].get(date, False):
                continue
            for leg in run_day(ctx, c):
                leg["date"] = date
                leg.pop("i", None)
                out[k].append(leg)
        if progress and (n + 1) % 50 == 0:
            print(f"  {n+1}/{len(dates)}", flush=True)
    return out


def _permute(date, Fd, day):
    n = day.n
    p = np.random.default_rng(int(date.replace("-", "")) + 7).permutation(n)
    Fd = {k: (v[p] if isinstance(v, np.ndarray) and v.ndim >= 1
              and v.shape[0] == n and k != "grid" else v)
          for k, v in Fd.items()}
    for k in ("o", "h", "l", "c", "v", "pc", "printed"):
        setattr(day, k, getattr(day, k)[p])
    day.syms = [day.syms[j] for j in p]
    for k in ("gain_pct", "hist_n", "rvol", "rvol30", "gdopen", "gdhigh",
              "gdclose", "gdvol"):
        if getattr(day, k, None) is not None:
            setattr(day, k, getattr(day, k)[p])
    day._ffill = day._runhi = day._cumv = day._cumdv = None
    day._cumsv = day._cumn = None
    return Fd, day
