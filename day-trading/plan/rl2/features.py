"""RL-SERIES v2 (2026-09-16): causal features + tradeable targets.

INPUT   plan/rl2/out/days/{D}.npz     (plan/rl2/panel.py)
        data/massive/gd/*.json.gz     (daily history, dates < D only)
OUTPUT  plan/rl2/out/feat/{D}.npz

CAUSALITY CONTRACT
  Every feature at decision step t (minute m = STEPS[t]) is a function of
  bars with grid index <= m and of grouped-daily rows with date < D. No
  feature touches bar m+1, and `poison_check` in plan/rl2/honesty.py
  proves it mechanically by replacing every bar after m with garbage and
  asserting the feature block is bit-identical.

  The one quantity built from the future is `tgt` -- the realized net
  return of the trade a decision at t would open. It is the LABEL. It is
  written into a separate array, never into F, and the model is never
  given it (except deliberately, in the foresight positive control).

  The intraday volume profile used by the relative-volume feature is
  fitted on TRAIN DATES ONLY (< PROFILE_END) and frozen, so a test day's
  own shape never informs its own feature.

ARRAYS
  syms (S,)  prev_close (S,)  steps (T,)
  F      (T,S,NF) float32   causal features, NaN-free
  mark   (T,S)              last printed close at or before m
  printed(T,S) bool         bar m itself printed (the tradeability mask)
  fill_o (T,S)              OPEN of bar m+1 -- the fill price; NaN if the
                            minute did not print, which makes the order
                            impossible. FUTURE at decision time: used to
                            price a fill, never to decide one.
  volcap (T,S)              0.20 * volume over the trailing STEP minutes
  flat_px(S,) flat_min(S,)  forced-flatten reference (last printed bar)
  tgt    (T,S,H) float32    net return per $1 of an entry at t exited
                            after HORIZONS[h] minutes (see `_targets`)
  tgt_ok (T,S,H) bool       that trade was actually openable+closable
"""
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GD = ROOT / "data" / "massive" / "gd"
DAYS = HERE / "out" / "days"
FEAT = HERE / "out" / "feat"

NMIN = 960
RTH_LO = 330          # 09:30 ET
RTH_HI = 720          # 16:00 ET
STEP = 5
FIRST_STEP, LAST_STEP = 0, NMIN - 5           # 04:00 .. 19:55
STEPS = np.arange(FIRST_STEP, LAST_STEP + 1, STEP)
T = len(STEPS)

FEE_BPS = 10.0
EXT_BPS = 50.0
HORIZONS = [15, 30, 60, 120, 10 ** 6]          # 10**6 = hold to flatten
NH = len(HORIZONS)

PROFILE_END = "2025-08-01"     # volume profile fitted on dates STRICTLY <
PRIOR_D = 20                   # prior trading days for the daily stats

FEATURE_NAMES = [
    "gap_vs_prevclose", "ret_since_open", "dist_vwap_day", "dist_vwap30",
    "ret5", "ret15", "ret30", "ret60",
    "rvol_profile", "log_dv5", "dv_burst", "rvol30", "bar_range5",
    "print_density30", "print_density5", "amihud30",
    "tod", "min_to_1600", "is_ext", "log_price",
    "prev_day_ret", "log_mdv20", "dist_hi", "dist_lo",
    "xs_breadth", "xs_rank_ret30",
]
NF = len(FEATURE_NAMES)


# ------------------------------------------------------------------ daily
class Daily:
    """Prior-day statistics from grouped daily, dates STRICTLY < D."""

    def __init__(self):
        sys.path.insert(0, str(HERE))
        import universe as UV
        self.dates = UV.gd_dates()          # TRADING dates only (no holidays)
        self.didx = {d: i for i, d in enumerate(self.dates)}
        syms = set()
        rows = []
        for d in self.dates:
            r = json.loads(gzip.open(GD / f"{d}.json.gz", "rt").read())
            rows.append({x["T"]: (x.get("c"), x.get("v")) for x in r})
            syms.update(rows[-1])
        self.syms = sorted(syms)
        self.sidx = {s: i for i, s in enumerate(self.syms)}
        n, m = len(self.dates), len(self.syms)
        self.close = np.full((n, m), np.nan, np.float32)
        self.vol = np.full((n, m), np.nan, np.float32)
        for i, r in enumerate(rows):
            for s, (c, v) in r.items():
                j = self.sidx[s]
                if c is not None:
                    self.close[i, j] = c
                if v is not None:
                    self.vol[i, j] = v

    def stats(self, date, syms):
        """(prev_day_ret, median daily volume, median daily $ volume) over
        the PRIOR_D grouped-daily rows strictly before `date`."""
        i = self.didx[date]
        lo = max(0, i - PRIOR_D)
        j = np.array([self.sidx.get(s, -1) for s in syms])
        ok = j >= 0
        jj = np.where(ok, j, 0)
        wv = self.vol[lo:i][:, jj]
        wc = self.close[lo:i][:, jj]
        with np.errstate(all="ignore"):
            mv = np.nanmedian(wv, axis=0)
            mdv = np.nanmedian(wv * wc, axis=0)
            c1 = self.close[i - 1, jj] if i >= 1 else np.full(len(jj), np.nan)
            c2 = self.close[i - 2, jj] if i >= 2 else np.full(len(jj), np.nan)
            pr = np.log(np.maximum(c1, 1e-9) / np.maximum(c2, 1e-9))
        bad = ~ok
        for a in (mv, mdv, pr):
            a[bad] = np.nan
        return (np.nan_to_num(pr, nan=0.0),
                np.nan_to_num(mv, nan=0.0),
                np.nan_to_num(mdv, nan=0.0))


# ------------------------------------------------------------ small utils
def ffill_rows(a):
    idx = np.where(~np.isnan(a), np.arange(a.shape[1])[None, :], 0)
    np.maximum.accumulate(idx, axis=1, out=idx)
    return a[np.arange(a.shape[0])[:, None], idx]


def next_printed(printed):
    """nxt[i,k] = smallest j >= k with printed[i,j], else NMIN (sentinel)."""
    S, N = printed.shape
    nxt = np.full((S, N + 1), N, np.int32)
    for k in range(N - 1, -1, -1):
        nxt[:, k] = np.where(printed[:, k], k, nxt[:, k + 1])
    return nxt[:, :N]


def cost_frac(minute):
    """One side's cost as a fraction: 10 bps always, +50 bps outside RTH."""
    ext = (minute < RTH_LO) | (minute >= RTH_HI)
    return (FEE_BPS + EXT_BPS * ext) / 1e4


# ------------------------------------------------------------------ build
def load_raw(path):
    z = np.load(path, allow_pickle=False)
    return ([str(s) for s in z["syms"]], z["prev_close"].astype(np.float64),
            [z[k].astype(np.float64) for k in "ohlcv"])


def compute_day(date, syms, pc, bars, profile, daily):
    """The whole causal feature/label block for one day, as a dict.

    Separated from the writer so plan/rl2/honesty.py can call it on a
    POISONED copy of the bars and compare arrays element-wise.
    """
    o, h, lo, c, v = bars
    S = len(syms)
    M = STEPS

    printed = ~np.isnan(c)
    cf = ffill_rows(c)
    first_ok = np.isnan(cf)
    cf = np.where(first_ok, np.nan, cf)
    hf = np.fmax.accumulate(np.where(np.isnan(h), -np.inf, h), axis=1)
    lf = np.fmin.accumulate(np.where(np.isnan(lo), np.inf, lo), axis=1)
    dv = np.nan_to_num(c) * v
    cdv, cvol, cprint = (np.cumsum(x, axis=1) for x in
                         (dv, v, printed.astype(np.float64)))
    lr = np.zeros_like(cf)
    lr[:, 1:] = np.log(np.maximum(cf[:, 1:], 1e-9) /
                       np.maximum(cf[:, :-1], 1e-9))
    lr = np.nan_to_num(lr)
    clr, clr2, calr = (np.cumsum(x, axis=1) for x in (lr, lr * lr, np.abs(lr)))
    rng = np.where(printed, np.log(np.maximum(np.nan_to_num(h, nan=1.0), 1e-9) /
                                   np.maximum(np.nan_to_num(lo, nan=1.0), 1e-9)),
                   0.0)
    crng = np.cumsum(rng, axis=1)

    def win(cum, w):
        a = cum[:, M]
        lo_i = M - w
        b = np.where(lo_i >= 0, cum[:, np.maximum(lo_i, 0)], 0.0)
        return (a - b).T                                     # [T,S]

    mark = cf[:, M].T.copy()
    prn = printed[:, M].T.copy()
    nxt1 = np.minimum(M + 1, NMIN - 1)
    fill_o = o[:, nxt1].T.copy()
    fill_o = np.where(printed[:, nxt1].T, fill_o, np.nan)
    volcap = 0.20 * win(cvol, STEP)

    # forced flatten: the day's last printed bar per symbol
    any_p = printed.any(axis=1)
    last = np.where(any_p, NMIN - 1 - np.argmax(printed[:, ::-1], axis=1), -1)
    flat_min = last.astype(np.int32)
    flat_px = np.where(last >= 0, c[np.arange(S), np.maximum(last, 0)], np.nan)

    # ---- features
    with np.errstate(divide="ignore", invalid="ignore"):
        F = np.zeros((T, S, NF), np.float64)
        pcb = pc[None, :]
        F[:, :, 0] = np.log(np.maximum(mark, 1e-9) / np.maximum(pcb, 1e-9))
        # first printed close at/after 09:30 -- the session open reference
        op = np.where(M[:, None] >= RTH_LO,
                      cf[:, RTH_LO][None, :], cf[:, 0][None, :])
        F[:, :, 1] = np.log(np.maximum(mark, 1e-9) / np.maximum(op, 1e-9))
        dvday, vday = cdv[:, M].T, cvol[:, M].T
        vwapd = dvday / np.maximum(vday, 1.0)
        F[:, :, 2] = np.where(vday > 0, np.log(np.maximum(mark, 1e-9) /
                                               np.maximum(vwapd, 1e-9)), 0.0)
        dv30, vv30 = win(cdv, 30), win(cvol, 30)
        vwap30 = dv30 / np.maximum(vv30, 1.0)
        F[:, :, 3] = np.where(vv30 > 0, np.log(np.maximum(mark, 1e-9) /
                                               np.maximum(vwap30, 1e-9)), 0.0)
        for jj, w in enumerate((5, 15, 30, 60), start=4):
            prev = cf[:, np.maximum(M - w, 0)].T
            F[:, :, jj] = np.log(np.maximum(mark, 1e-9) /
                                 np.maximum(prev, 1e-9))
        # relative volume vs the name's own prior-20d size x a FROZEN,
        # train-only intraday shape
        prev_ret, mvol, mdv20 = daily.stats(date, syms)
        exp_v = mvol[None, :] * profile[M][:, None]
        F[:, :, 8] = np.log1p(vday) - np.log1p(np.maximum(exp_v, 1.0))
        dv5 = win(cdv, STEP)
        F[:, :, 9] = np.log1p(dv5)
        el = np.maximum(M[:, None] + 1, 1).astype(np.float64)
        F[:, :, 10] = np.log((dv5 / STEP + 1.0) / (dvday / el + 1.0))
        m30, m230 = win(clr, 30) / 30.0, win(clr2, 30) / 30.0
        F[:, :, 11] = np.sqrt(np.maximum(m230 - m30 * m30, 0.0))
        n5 = np.maximum(win(cprint, STEP), 1.0)
        F[:, :, 12] = win(crng, STEP) / n5
        F[:, :, 13] = win(cprint, 30) / 30.0
        F[:, :, 14] = win(cprint, STEP) / STEP
        F[:, :, 15] = np.log1p(win(calr, 30) / np.maximum(dv30, 1.0) * 1e6)
        F[:, :, 16] = (M[:, None] / float(NMIN)) * np.ones((1, S))
        F[:, :, 17] = ((RTH_HI - M)[:, None] / 60.0) * np.ones((1, S))
        F[:, :, 18] = (((M < RTH_LO) | (M >= RTH_HI))[:, None]
                       * np.ones((1, S))).astype(np.float64)
        F[:, :, 19] = np.log(np.maximum(mark, 1e-9))
        F[:, :, 20] = prev_ret[None, :] * np.ones((T, 1))
        F[:, :, 21] = np.log1p(mdv20)[None, :] * np.ones((T, 1))
        F[:, :, 22] = np.log(np.maximum(mark, 1e-9) /
                             np.maximum(hf[:, M].T, 1e-9))
        F[:, :, 23] = np.log(np.maximum(mark, 1e-9) /
                             np.maximum(lf[:, M].T, 1e-9))
        r1 = np.where(prn, F[:, :, 1], np.nan)
        with np.errstate(all="ignore"):
            br = np.nanmean(r1, axis=1)
        br = np.nan_to_num(br)
        F[:, :, 24] = br[:, None] * np.ones((1, S))
        r30 = np.where(prn, F[:, :, 6], np.nan)
        rk = np.argsort(np.argsort(np.nan_to_num(r30, nan=-1e9), axis=1),
                        axis=1).astype(np.float64)
        F[:, :, 25] = rk / max(S - 1, 1)
    F = np.nan_to_num(F, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    tgt, tgt_ok = _targets(o, printed, flat_min, flat_px)
    return dict(syms=np.array(syms), prev_close=pc.astype(np.float32),
                steps=STEPS.astype(np.int32), F=F,
                mark=mark.astype(np.float32), printed=prn,
                fill_o=fill_o.astype(np.float32),
                volcap=volcap.astype(np.float32),
                flat_px=flat_px.astype(np.float32), flat_min=flat_min,
                tgt=tgt, tgt_ok=tgt_ok)


def build_day(path, profile, daily):
    date = Path(path).stem
    syms, pc, bars = load_raw(path)
    d = compute_day(date, syms, pc, bars, profile, daily)
    np.savez_compressed(FEAT / f"{date}.npz", **d)
    return len(syms)


def _targets(o, printed, flat_min, flat_px):
    """Net return per $1 of: buy at the OPEN of minute m+1, sell at the
    open of the first printed minute at or after m+1+H, or -- if that
    would fall past the day's last print -- at the forced-flatten price.
    Both legs pay 10 bps, plus 50 bps each if outside 09:30-16:00.

    This is exactly the trade plan/rl2/sim.py executes for a fixed-horizon
    exit, so the model's label and the simulator's P&L cannot disagree.
    """
    S = o.shape[0]
    nxt = next_printed(printed)
    M = STEPS
    ent_m = np.minimum(M + 1, NMIN - 1)                       # [T]
    ent_ok = printed[:, ent_m].T                              # [T,S]
    ent_px = np.where(ent_ok, o[:, ent_m].T, np.nan)
    ent_c = cost_frac(ent_m)[:, None]
    tgt = np.zeros((T, S, NH), np.float32)
    ok = np.zeros((T, S, NH), bool)
    ar = np.arange(S)
    for hi, H in enumerate(HORIZONS):
        want = np.minimum(np.asarray(M, np.int64) + 1 + H, NMIN)  # [T]
        want = np.clip(want, 0, NMIN - 1)
        xi = nxt[ar[None, :], want[:, None]]                  # [T,S]
        past = (xi >= NMIN) | (xi > flat_min[None, :]) | (H >= NMIN)
        xi_c = np.clip(xi, 0, NMIN - 1)
        ex_px = np.where(past, flat_px[None, :], o[ar[None, :], xi_c])
        ex_m = np.where(past, flat_min[None, :], xi_c)
        ex_c = cost_frac(ex_m)
        good = ent_ok & np.isfinite(ent_px) & np.isfinite(ex_px) \
            & (ex_m >= ent_m[:, None])
        with np.errstate(all="ignore"):
            r = (ex_px * (1.0 - ex_c)) / np.maximum(
                ent_px * (1.0 + ent_c), 1e-9) - 1.0
        tgt[:, :, hi] = np.where(good, np.nan_to_num(r), 0.0)
        ok[:, :, hi] = good
    return tgt, ok


def fit_profile():
    """Cumulative share of the day's volume by minute, pooled over TRAIN
    dates only (< PROFILE_END) and frozen. profile[m] in (0,1]."""
    cache = HERE / "out" / "vol_profile.npy"
    if cache.exists():
        return np.load(cache)
    tot = np.zeros(NMIN)
    n = 0
    for p in sorted(DAYS.glob("*.npz")):
        if p.stem >= PROFILE_END:
            continue
        v = np.load(p, allow_pickle=False)["v"].astype(np.float64)
        s = v.sum(axis=1)
        keep = s > 0
        if not keep.any():
            continue
        tot += (v[keep] / s[keep, None]).sum(axis=0)
        n += int(keep.sum())
    prof = np.cumsum(tot / max(n, 1))
    prof = np.maximum(prof, 1e-6)
    np.save(cache, prof)
    print(f"volume profile fitted on {n:,} symbol-days < {PROFILE_END}; "
          f"cum share at 09:30={prof[RTH_LO]:.3f} 16:00={prof[RTH_HI]:.3f}",
          flush=True)
    return prof


def main():
    FEAT.mkdir(parents=True, exist_ok=True)
    prof = fit_profile()
    daily = Daily()
    files = sorted(DAYS.glob("*.npz"))
    t0 = time.time()
    tot = 0
    for i, p in enumerate(files):
        tot += build_day(p, prof, daily)
        if (i + 1) % 50 == 0:
            el = time.time() - t0
            print(f"  [{i+1}/{len(files)}] {p.stem} {el:.0f}s eta "
                  f"{el/(i+1)*(len(files)-i-1):.0f}s", flush=True)
    print(f"feat: {len(files)} days, {tot:,} symbol-days, "
          f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
