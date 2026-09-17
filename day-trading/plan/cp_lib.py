"""CHAMPION-REPLAY: the causal live-scannable universe, on the panel.

THE CENTRAL CLAIM THIS FILE ENCODES (and `cp_universe.py --prove`
checks): for any REGULAR-SESSION minute t, the set

    U(t) = { name : last printed close at or before t  >=  1.10 x
                    prev_close,  and that close >= $2 }

is COMPLETE inside `data/massive/m1`, with no survivorship.

  Why complete: the pool file's membership rule is the grouped-daily
  REGULAR-SESSION HIGH >= +10% over prev_close. If a name's last RTH
  close at t is already >= +10%, then its RTH high is >= +10% too, so
  it is necessarily in the pool and necessarily has bars. Membership is
  therefore IMPLIED by the same past print that puts the name on the
  live scanner -- there is nothing about the rest of the day in it.

  Why this is the LIVE scanner: Robinhood `run_scan` filters on
  Last > $2 and %Change > 10%. %Change is quoted off the last trade,
  not off the session high, so the scanner's own rule is a CLOSE rule.
  `rotation_sim`'s RS_CROSS uses the bar HIGH, which is looser (a wick
  that never printed a close above +10% still arms a name). Both are
  provided: MODE_LAST (the live scanner) and MODE_HIGH (RS_CROSS).

  What is NOT complete: PREMARKET. A name whose premarket last crosses
  +10% and whose regular session never reaches +10% is invisible to the
  grouped-daily pool and has no bars on disk. That set is measured
  separately by `cp_premkt.py`; it is the piece the old pool never had,
  and it is why every premarket entry in the C31..C37 family was
  survivorship-conditioned.

GRID. Panel minute m = minutes since 04:00 ET. 09:30 = 330.
"""

import json
from datetime import time as dtime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
GRID_START = 4 * 60
NMIN = 720

M_PM_START = 0            # 04:00
M_OPEN = 9 * 60 + 30 - GRID_START        # 330
M_0935 = 9 * 60 + 35 - GRID_START        # 335
M_1000 = 10 * 60 - GRID_START            # 360
M_1500 = 15 * 60 - GRID_START            # 660
M_CLOSE = 16 * 60 - GRID_START - 1       # 719

MIN_PRICE = 2.0
CROSS = 1.10


def mgrid(hh, mm=0):
    return hh * 60 + mm - GRID_START


class Day:
    """Vectorised causal views of one date's panel.

    Every array is (n_names, 720). All the `*_at` helpers answer with
    information dated <= the minute asked for, by construction: they
    are cumulative scans, never reversed."""

    def __init__(self, z):
        self.syms = [str(s) for s in z["syms"]]
        self.pc = z["pc"].astype(np.float64)
        self.o = z["o"].astype(np.float64)
        self.h = z["h"].astype(np.float64)
        self.l = z["l"].astype(np.float64)
        self.c = z["c"].astype(np.float64)
        self.v = np.nan_to_num(z["v"].astype(np.float64))
        for k in ("gain_pct", "hist_n", "rvol", "rvol30",
                  "gdopen", "gdhigh", "gdclose", "gdvol"):
            setattr(self, k, z[k].astype(np.float64) if k in z else None)
        self.n = len(self.syms)
        self.printed = ~np.isnan(self.c)
        self._ffill = None
        self._runhi = None
        self._cumv = None
        self._cumdv = None
        self._cumsv = None
        self._cumn = None

    # ---- cumulative causal views -------------------------------------
    @property
    def last(self):
        """last[i, m] = last printed close at or before minute m."""
        if self._ffill is None:
            c = self.c.copy()
            idx = np.where(self.printed, np.arange(NMIN)[None, :], -1)
            np.maximum.accumulate(idx, axis=1, out=idx)
            safe = np.where(idx < 0, 0, idx)
            out = np.take_along_axis(c, safe, axis=1)
            out[idx < 0] = np.nan
            self._ffill = out
        return self._ffill

    @property
    def runhigh(self):
        """runhigh[i, m] = max printed HIGH at or before m (session-wide)."""
        if self._runhi is None:
            h = np.where(self.printed, self.h, -np.inf)
            out = np.maximum.accumulate(h, axis=1)
            out[~np.isfinite(out)] = np.nan
            self._runhi = out
        return self._runhi

    def runhigh_from(self, m0):
        """max printed HIGH over [m0, m], NaN before the first print."""
        h = np.where(self.printed, self.h, -np.inf).copy()
        h[:, :m0] = -np.inf
        out = np.maximum.accumulate(h, axis=1)
        out[~np.isfinite(out)] = np.nan
        return out

    @property
    def cumv(self):
        if self._cumv is None:
            self._cumv = np.cumsum(self.v, axis=1)
        return self._cumv

    @property
    def cumdv(self):
        """cumulative DOLLAR volume (close x volume, 0 where unprinted)."""
        if self._cumdv is None:
            px = np.nan_to_num(self.c)
            self._cumdv = np.cumsum(px * self.v, axis=1)
        return self._cumdv

    @property
    def cumsv(self):
        """cumulative SIGNED volume, day-trading.py's X200 proxy:
        v * (2(c-l) - (h-l)) / (h-l), one-price bars contribute 0."""
        if self._cumsv is None:
            rng = self.h - self.l
            with np.errstate(divide="ignore", invalid="ignore"):
                pos = np.where(rng > 0, (2 * (self.c - self.l) - rng) / rng,
                               0.0)
            pos = np.nan_to_num(pos)
            self._cumsv = np.cumsum(self.v * pos, axis=1)
        return self._cumsv

    @property
    def cumn(self):
        """cumulative count of printed bars (the champion's 'bars')."""
        if self._cumn is None:
            self._cumn = np.cumsum(self.printed.astype(np.int32), axis=1)
        return self._cumn

    # ---- causal universe ---------------------------------------------
    def crossed_by(self, m, mode="LAST", start=M_OPEN):
        """Boolean mask: name is on the live scanner at minute m.

        mode LAST  -- last printed CLOSE in [start, m] >= 1.10 x pc
                      (Robinhood run_scan: Last > $2, %Change > 10%)
        mode HIGH  -- any printed HIGH in [start, m] >= 1.10 x pc
                      (rotation_sim's RS_CROSS convention)
        `start` = M_OPEN keeps it regular-session (complete, provable);
        `start` = 0 includes premarket (INCOMPLETE on this cache)."""
        thr = CROSS * self.pc
        if mode == "HIGH":
            rh = self.runhigh_from(start)[:, m]
            ok = rh >= thr
            px = self.last[:, m]
        else:
            c = np.where(self.printed, self.c, -np.inf).copy()
            c[:, :start] = -np.inf
            hit = np.maximum.accumulate(c, axis=1)[:, m]
            ok = hit >= thr
            px = self.last[:, m]
        return ok & np.isfinite(px) & (px >= MIN_PRICE) & (self.pc > 0)

    def cross_minute(self, mode="LAST", start=M_OPEN, end=M_CLOSE):
        """First minute in [start, end] at which the name is on the
        scanner; NMIN when it never is."""
        thr = (CROSS * self.pc)[:, None]
        if mode == "HIGH":
            arr = np.where(self.printed, self.h, -np.inf)
        else:
            arr = np.where(self.printed, self.c, -np.inf)
        ok = arr >= thr
        ok[:, :start] = False
        ok[:, end + 1:] = False
        # price floor at the crossing print itself
        px = np.where(self.printed, self.c, -np.inf)
        ok &= (px >= MIN_PRICE)
        any_ = ok.any(axis=1)
        first = np.where(any_, ok.argmax(axis=1), NMIN)
        return first

    # ---- causal features at a decision minute -------------------------
    def features(self, m, prior=None):
        """Feature block for every name, using bars <= m only.

        `prior` (optional) is the per-symbol prior-history dict from
        cp_prior.py: slowly-varying context (median dollar volume and
        range over the PRIOR 60 sessions, shares outstanding, float).
        Nothing in here reads a bar after m."""
        last = self.last[:, m]
        hi = self.runhigh[:, m]
        pc = self.pc
        with np.errstate(divide="ignore", invalid="ignore"):
            f = {}
            f["px"] = last
            f["gain_now"] = last / pc - 1.0
            f["coil"] = np.where(hi > 0, last / hi, np.nan)
            f["hi_gain"] = hi / pc - 1.0
            # premarket block (read at the OPEN, so it is pre-open info)
            pmv = self.cumdv[:, M_OPEN - 1]
            f["pm_dvol"] = pmv
            pmh = self.runhigh[:, M_OPEN - 1]
            f["pm_high_gain"] = pmh / pc - 1.0
            pmlast = self.last[:, M_OPEN - 1]
            f["gap_open"] = pmlast / pc - 1.0
            f["pm_bars"] = self.cumn[:, M_OPEN - 1].astype(float)
            # session-so-far block
            dv = self.cumdv[:, m] - self.cumdv[:, M_OPEN - 1]
            f["dvol_now"] = dv
            f["bars_now"] = (self.cumn[:, m]
                             - self.cumn[:, M_OPEN - 1]).astype(float)
            # VWAP so far (regular session)
            vv = self.cumv[:, m] - self.cumv[:, M_OPEN - 1]
            f["vwap_dist"] = np.where(vv > 0, last / (dv / vv) - 1.0, np.nan)
            # 30-printed-bar pressure, the champion's ordering key
            f["pressure30"] = self._pressure(m, 30)
            f["pressure10"] = self._pressure(m, 10)
            # opening range
            orb_hi = self.runhigh_from(M_OPEN)[:, min(m, M_OPEN + 4)]
            f["orb_dist"] = last / orb_hi - 1.0
            # tape density and 1-min realised vol
            f["dens"] = f["bars_now"] / max(1, m - M_OPEN + 1)
            r = np.diff(np.log(np.where(self.printed[:, :m + 1],
                                        self.c[:, :m + 1], np.nan)),
                        axis=1)
            with np.errstate(invalid="ignore"):
                f["sigma1"] = np.nanstd(r, axis=1)
            if prior is not None:
                pdv = np.array([prior.get(s, {}).get("dvol60", np.nan)
                                for s in self.syms])
                prg = np.array([prior.get(s, {}).get("range60", np.nan)
                                for s in self.syms])
                psh = np.array([prior.get(s, {}).get("shares", np.nan)
                                for s in self.syms])
                f["dvol60"] = pdv
                f["prior_range"] = prg
                f["rvol_pm"] = np.where(pdv > 0, pmv / pdv, np.nan)
                f["rvol_now"] = np.where(pdv > 0, dv / pdv, np.nan)
                f["shares"] = psh
                f["mcap_now"] = psh * last
                f["turn_now"] = np.where(psh > 0, (self.cumv[:, m]) / psh,
                                         np.nan)
        return f

    def _pressure(self, m, nbars, min_vol=20_000.0):
        """Pressure over the last `nbars` PRINTED bars ending at m --
        the same object day-trading.py::Candles.pressure builds, which
        counts printed bars, not clock minutes."""
        cn = self.cumn[:, m]
        target = cn - nbars
        out = np.full(self.n, np.nan)
        # index of the bar where the cumulative count first exceeds target
        for i in range(self.n):
            if cn[i] < 3:
                continue
            t = max(0, int(target[i]))
            row = self.cumn[i, :m + 1]
            j = int(np.searchsorted(row, t, side="right"))
            vol = self.cumv[i, m] - (self.cumv[i, j - 1] if j > 0 else 0.0)
            if vol < min_vol or vol <= 0:
                continue
            sv = self.cumsv[i, m] - (self.cumsv[i, j - 1] if j > 0 else 0.0)
            out[i] = sv / vol
        return out

    # ---- forward outcomes (LABELS ONLY -- never a feature) ------------
    def fwd(self, m0, m1):
        """Outcomes over (m0, m1]: max high, min low, last close."""
        hh = np.where(self.printed[:, m0 + 1:m1 + 1],
                      self.h[:, m0 + 1:m1 + 1], np.nan)
        ll = np.where(self.printed[:, m0 + 1:m1 + 1],
                      self.l[:, m0 + 1:m1 + 1], np.nan)
        with np.errstate(invalid="ignore"):
            mx = np.nanmax(hh, axis=1) if hh.size else np.full(self.n, np.nan)
            mn = np.nanmin(ll, axis=1) if ll.size else np.full(self.n, np.nan)
        return dict(fwd_max=mx, fwd_min=mn, fwd_last=self.last[:, m1])


def load_day(date):
    f = ROOT / f"data/massive/cp_panel/{date}.npz"
    if not f.exists():
        return None
    z = np.load(f, allow_pickle=False)
    return Day({k: z[k] for k in z.files})


def panel_dates():
    d = ROOT / "data/massive/cp_panel"
    return sorted(p.stem for p in d.glob("[0-9]*.npz"))


_HALAL = {}


def halal_set(which="415"):
    """Post-hoc halal lists. NOT used in any decision on this line."""
    if which in _HALAL:
        return _HALAL[which]
    f = ROOT / ("data/halal_list.NEW.json" if which == "NEW"
                else "data/halal_list.json")
    s = set()
    if f.exists():
        try:
            d = json.loads(f.read_text())
            if isinstance(d, dict):
                s = set(d.get("symbols") or [])
            else:
                s = set(d)
        except Exception:
            pass
    _HALAL[which] = s
    return s
