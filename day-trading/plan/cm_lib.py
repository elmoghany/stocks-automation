"""CLOSE-MOMENTUM (2026-09-16): shared panel, causal features, and the
clock-exit ticket engine.

WHY A NEW ENGINE AND NOT plan/rl2/sim.py
  rl2's simulator exits at the OPEN of the next 5-minute decision bar. The
  hypotheses here are about the LAST half hour, whose natural exit is the
  closing print, and the mandate fixes the convention:

      entry  = the NEXT bar's OPEN  x (1 + cost)
      exit   = the STATED bar's CLOSE x (1 - cost)

  so 15:59's close can be used as an approximation of the closing auction
  and 15:55 / 15:50 can be shown as sensitivities. Everything else -- the
  $15k/$10k ticket ladder, <= 7 concurrent, <= $100k/day, the 20%-of-
  trailing-volume size cap, the 10 bps + 50 bps-outside-RTH ladder, the
  "availability is read off bar m, never bar m+1" rule -- is copied from
  plan/rl2/sim.py deliberately so the two cannot drift.

MINUTE GRID
  k = ET minute-of-day - 240, so k in [0, 960) covers 04:00..19:59 ET.
      09:30 -> 330    10:00 -> 360    12:00 -> 480    13:00 -> 540
      15:00 -> 660    15:30 -> 690    15:50 -> 710    15:55 -> 715
      15:59 -> 719    16:00 -> 720

CAUSALITY CONTRACT
  `features(panel, m)` may read bars with grid index <= m and grouped-daily
  rows with date < D, and nothing else. plan/cm_honesty.py proves it by
  replacing every bar after m with garbage and requiring the feature block
  AND the selected trades to be identical. The fill price o[m+1] and the
  exit close c[x] are future at decision time; they price a trade, they
  never choose one.

SPLITS (identical to plan/wn_lib.py so rows stay comparable)
  Y1 / train   2024-10-22 .. 2025-07-31   (fit anything here, and only here)
  Y2 / oos     2025-08-01 .. 2026-07-31
  aug2026      2026-08-03 .. 2026-08-06   (4-day stub, never in $/month)
"""
import csv
import gzip
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / "rl2"))

DAYS = HERE / "rl2" / "out" / "days"
M1ETF = ROOT / "data" / "massive" / "m1etf"
M1 = ROOT / "data" / "massive" / "m1"
M1W = ROOT / "data" / "massive" / "m1w"
GD = ROOT / "data" / "massive" / "gd"
OUT = ROOT / "data" / "massive" / "cm"

NMIN = 960
BASE_MIN = 240
RTH_LO = 330                 # 09:30
RTH_HI = 720                 # 16:00
FEE_BPS = 10.0
EXT_BPS = 50.0
TICKETS = [15000.0] * 6 + [10000.0]
MAX_TICKETS = len(TICKETS)
MIN_NOTIONAL = 500.0
VOLCAP_FRAC = 0.20
VOLCAP_WIN = 5

TRAIN_END = "2025-08-01"     # exclusive
OOS_END = "2026-08-01"       # exclusive


def idx(hhmm):
    """'15:30' -> 690."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m) - BASE_MIN


def clock(k):
    m = k + BASE_MIN
    return f"{m//60:02d}:{m%60:02d}"


def split_of(date):
    return 0 if date < TRAIN_END else (1 if date < OOS_END else 2)


def cost_frac(minute):
    ext = (minute < RTH_LO) or (minute >= RTH_HI)
    return (FEE_BPS + EXT_BPS * ext) / 1e4


# ------------------------------------------------------------------ panel
def _read_csv_grid(path, date):
    """(o,h,l,c,v) on the 960-slot ET grid, or None.

    Identical parsing to plan/rl2/panel.read_m1 -- UTC timestamps, one
    fixed offset per day (the 04:00-20:00 ET window sits inside one UTC
    date), duplicate minutes keep the last row.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    off = int(datetime.strptime(date, "%Y-%m-%d").replace(hour=12, tzinfo=ET)
              .utcoffset().total_seconds() // 60)
    o = np.full(NMIN, np.nan); h = np.full(NMIN, np.nan)
    lo = np.full(NMIN, np.nan); c = np.full(NMIN, np.nan)
    v = np.zeros(NMIN)
    seen = False
    with open(path, newline="") as fh:
        rd = csv.reader(fh)
        hdr = next(rd, None)
        if hdr is None or (hdr and hdr[0].startswith("EMPTY")):
            return None
        for row in rd:
            if len(row) < 6 or row[0][:10] != date:
                continue
            try:
                k = int(row[0][11:13]) * 60 + int(row[0][14:16]) + off - BASE_MIN
            except ValueError:
                continue
            if not (0 <= k < NMIN):
                continue
            try:
                o[k] = float(row[1]); h[k] = float(row[2])
                lo[k] = float(row[3]); c[k] = float(row[4]); v[k] = float(row[5])
            except ValueError:
                continue
            seen = True
    return (o, h, lo, c, v) if seen else None


class Panel:
    """One trading day's bars for S names, plus the causal derived arrays."""

    def __init__(self, date, syms, prev_close, bars):
        self.date = date
        self.syms = list(syms)
        self.S = len(self.syms)
        self.prev_close = np.asarray(prev_close, float)
        self.o, self.h, self.l, self.c, self.v = [np.asarray(a, float)
                                                  for a in bars]
        self._derive()

    def _derive(self):
        self.printed = ~np.isnan(self.c)
        self.cf = _ffill(self.c)                      # last printed close <= k
        self.hf = np.fmax.accumulate(np.where(np.isnan(self.h), -np.inf,
                                              self.h), axis=1)
        self.lf = np.fmin.accumulate(np.where(np.isnan(self.l), np.inf,
                                              self.l), axis=1)
        dv = np.nan_to_num(self.c) * self.v
        self.cdv = np.cumsum(dv, axis=1)
        self.cvol = np.cumsum(self.v, axis=1)
        # session-open reference: the OPEN of the first bar printed at or
        # after 09:30 (falls back to its close if the open is missing)
        ao = np.where(self.printed[:, RTH_LO:], 1, 0)
        has = ao.any(axis=1)
        first = np.where(has, RTH_LO + np.argmax(ao, axis=1), -1)
        ar = np.arange(self.S)
        op = np.where(first >= 0, self.o[ar, np.maximum(first, 0)], np.nan)
        opc = np.where(first >= 0, self.c[ar, np.maximum(first, 0)], np.nan)
        self._open_px = np.where(np.isfinite(op), op, opc)
        self.open_min = first

    def open_ref(self, m):
        """The session-open reference AS KNOWN AT MINUTE m.

        A name whose first regular-session bar has not printed by m has no
        open yet, and the unguarded version of this (the day's first RTH
        print, whenever it happens) would hand a 10:00 decision the price
        of a bar that prints at 15:00. That is look-ahead; the poison test
        catches it, and this guard is why it does not fire.
        """
        return np.where((self.open_min >= 0) & (self.open_min <= m),
                        self._open_px, np.nan)

    @classmethod
    def from_rl2(cls, date):
        z = np.load(DAYS / f"{date}.npz", allow_pickle=False)
        return cls(date, [str(s) for s in z["syms"]],
                   z["prev_close"].astype(float),
                   [z[k].astype(float) for k in "ohlcv"])

    @classmethod
    def from_csvs(cls, date, syms, prev_close, dirs=(M1ETF, M1W, M1)):
        keep, pc, arrs = [], [], []
        for s in syms:
            b = None
            for d in dirs:
                f = d / f"{s}_{date}.csv"
                if f.exists():
                    b = _read_csv_grid(f, date)
                    if b is not None:
                        break
            if b is None:
                continue
            keep.append(s)
            pc.append(prev_close[s])
            arrs.append(b)
        if not keep:
            return None
        S = len(keep)
        bars = [np.empty((S, NMIN)) for _ in range(5)]
        for j, b in enumerate(arrs):
            for k in range(5):
                bars[k][j] = b[k]
        return cls(date, keep, pc, bars)

    # -------------------------------------------------------- causal reads
    def mark(self, m):
        """Last printed close at or before minute m (NaN before first print)."""
        return self.cf[:, m]

    def vwap(self, m, win=None):
        a = self.cdv[:, m]
        b = self.cvol[:, m]
        if win is not None:
            lo = max(m - win, 0)
            a = a - (self.cdv[:, lo] if m - win >= 0 else 0.0)
            b = b - (self.cvol[:, lo] if m - win >= 0 else 0.0)
        with np.errstate(all="ignore"):
            return np.where(b > 0, a / np.maximum(b, 1e-9), np.nan)

    def volcap_shares(self, m):
        """20% of the shares traded over the trailing VOLCAP_WIN minutes."""
        lo = max(m - VOLCAP_WIN, 0)
        w = self.cvol[:, m] - (self.cvol[:, lo] if m - VOLCAP_WIN >= 0 else 0.0)
        return VOLCAP_FRAC * w


def _ffill(a):
    idx_ = np.where(~np.isnan(a), np.arange(a.shape[1])[None, :], 0)
    np.maximum.accumulate(idx_, axis=1, out=idx_)
    out = a[np.arange(a.shape[0])[:, None], idx_]
    # before the first print there is nothing to carry
    never = np.isnan(a).all(axis=1)
    out[never] = np.nan
    first = np.argmax(~np.isnan(a), axis=1)
    for i in range(a.shape[0]):
        if not never[i]:
            out[i, :first[i]] = np.nan
    return out


# --------------------------------------------------------------- features
def halfhour_returns(p, m):
    """The three Gao-Han-Li-Zhou half-hour returns, as far as minute m
    allows. Anything whose window has not closed by m is NaN.

      r_first  09:30 open -> 10:00      (complete once m >= 359)
      r_mid    close(m-30) -> close(m)  (the trailing half hour AT m; at
                                         m = 689 this is the published
                                         "second-to-last half-hour return")
    """
    out = {}
    r1 = np.full(p.S, np.nan)
    if m >= RTH_LO + 29:
        with np.errstate(all="ignore"):
            r1 = p.cf[:, RTH_LO + 29] / np.maximum(p.open_ref(m), 1e-9) - 1.0
    out["r_first"] = r1
    with np.errstate(all="ignore"):
        prev = p.cf[:, max(m - 30, 0)]
        out["r_mid"] = np.where(m - 30 >= 0, p.cf[:, m] / np.maximum(prev, 1e-9)
                                - 1.0, np.nan)
    return out


class Daily:
    """Prior-day grouped-daily statistics, dates STRICTLY < D. Thin wrapper
    around plan/rl2/features.Daily so the same numbers are used."""

    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            import features as FT
            cls._inst = FT.Daily()
        return cls._inst


_PROFILE = None


def profile():
    """The FROZEN train-only intraday cumulative volume shape from
    plan/rl2/features.fit_profile (fitted on dates < 2025-08-01)."""
    global _PROFILE
    if _PROFILE is None:
        import features as FT
        _PROFILE = FT.fit_profile()
    return _PROFILE


FEATS = ["r_first", "r_mid", "ret_open", "gap", "dist_vwap", "dist_vwap30",
         "rvol", "dist_hi", "dist_lo", "sigma30", "log_px", "log_dv_day",
         "breadth", "xs_rank_first", "xs_rank_mid", "r_first_dm", "r_mid_dm"]


def features(p, m, daily=None, prof=None):
    """The causal late-session feature block at decision minute m.

    Reads bars <= m and grouped-daily rows < D only.
    """
    daily = daily or Daily.get()
    prof = profile() if prof is None else prof
    mk = p.mark(m)
    hh = halfhour_returns(p, m)
    prev_ret, mvol, mdv20 = daily.stats(p.date, p.syms)
    with np.errstate(all="ignore"):
        f = {}
        f["r_first"] = hh["r_first"]
        f["r_mid"] = hh["r_mid"]
        opref = p.open_ref(m)
        f["ret_open"] = mk / np.maximum(opref, 1e-9) - 1.0
        f["gap"] = opref / np.maximum(p.prev_close, 1e-9) - 1.0
        f["dist_vwap"] = mk / np.maximum(p.vwap(m), 1e-9) - 1.0
        f["dist_vwap30"] = mk / np.maximum(p.vwap(m, 30), 1e-9) - 1.0
        exp_v = mvol * prof[m]
        f["rvol"] = p.cvol[:, m] / np.maximum(exp_v, 1.0)
        f["dist_hi"] = mk / np.maximum(p.hf[:, m], 1e-9) - 1.0
        f["dist_lo"] = mk / np.maximum(p.lf[:, m], 1e-9) - 1.0
        lo = max(m - 30, 0)
        lr = np.diff(np.log(np.maximum(p.cf[:, lo:m + 1], 1e-9)), axis=1)
        f["sigma30"] = np.nanstd(np.where(np.isfinite(lr), lr, np.nan), axis=1)
        f["log_px"] = np.log(np.maximum(mk, 1e-9))
        f["log_dv_day"] = np.log1p(p.cdv[:, m])
        prn = p.printed[:, m]
        ro = np.where(prn, f["ret_open"], np.nan)
        br = np.nanmean(ro) if np.isfinite(ro).any() else 0.0
        f["breadth"] = np.full(p.S, float(br))
        f["xs_rank_first"] = _rank(f["r_first"], prn)
        f["xs_rank_mid"] = _rank(f["r_mid"], prn)
        # market-demeaned versions (the cross-sectional form of hypothesis 4)
        for k in ("r_first", "r_mid"):
            a = np.where(prn, f[k], np.nan)
            mu = np.nanmean(a) if np.isfinite(a).any() else 0.0
            f[k + "_dm"] = f[k] - mu
    for k in f:
        f[k] = np.nan_to_num(np.asarray(f[k], float), nan=0.0, posinf=0.0,
                             neginf=0.0)
    return f


def _rank(x, prn):
    a = np.where(prn & np.isfinite(x), x, np.nan)
    n = int(np.isfinite(a).sum())
    out = np.zeros_like(a)
    if n <= 1:
        return out
    order = np.argsort(np.argsort(np.where(np.isfinite(a), a, -1e18)))
    out = (order - (len(a) - n)) / max(n - 1, 1)
    out = np.clip(out, 0.0, 1.0)
    return np.where(np.isfinite(a), out, 0.0)


# ----------------------------------------------------------------- engine
def trade_day(p, picks, exit_idx, tickets=None, cost=True):
    """Execute `picks` and flatten every ticket at `exit_idx`'s close.

    picks : list of (m, [i, i, ...]) -- decision minute and the symbol
            indices in priority order; the list IS the attempt budget for
            that minute. A pick is only legal if bar m printed for that
            symbol (availability is read off bar m, not off the fill bar).
            A name whose bar m+1 does not print spends the attempt but
            NOT a ticket -- exactly plan/rl2/sim.run_day.
    Returns a list of trade dicts.
    """
    tickets = TICKETS if tickets is None else tickets
    used = 0
    held = {}
    trades = []
    for m, order in picks:
        if m >= exit_idx:
            continue
        for i in order:
            if used >= len(tickets):
                break
            if i in held:
                continue
            if not p.printed[m, i]:
                continue                       # not available at decision time
            mf = m + 1
            if mf >= NMIN:
                continue
            px = p.o[i, mf]
            if not np.isfinite(px) or px <= 0:
                continue                       # the minute did not print
            sh = tickets[used] / px
            cap = p.volcap_shares(m)[i]
            if np.isfinite(cap):
                sh = min(sh, cap)
            if sh * px < MIN_NOTIONAL:
                continue                       # too thin: no ticket consumed
            used += 1
            cf_in = cost_frac(mf) if cost else 0.0
            held[i] = {"m_in": mf, "px_in": px, "sh": sh,
                       "cost": sh * px * (1.0 + cf_in), "sym": p.syms[i],
                       "m_dec": m}
    # ---- flatten at the stated bar's CLOSE
    for i, t in held.items():
        x = exit_idx
        px = p.cf[i, x]
        if not np.isfinite(px) or px <= 0:
            px = t["px_in"]
            x = t["m_in"]
        cf_out = cost_frac(x) if cost else 0.0
        proceeds = t["sh"] * px * (1.0 - cf_out)
        trades.append({"date": p.date, "sym": t["sym"], "i": int(i),
                       "m_dec": t["m_dec"], "m_in": t["m_in"],
                       "px_in": float(t["px_in"]), "sh": float(t["sh"]),
                       "m_out": int(x), "px_out": float(px),
                       "notional": float(t["cost"]),
                       "pnl": float(proceeds - t["cost"]),
                       "gross": float(t["sh"] * (px - t["px_in"])),
                       "hold": int(x - t["m_in"])})
    return trades


# -------------------------------------------------------------- reporting
def summarize(trades, ndays, label="", dates=None):
    pnl = np.array([t["pnl"] for t in trades], float)
    tdates = [t["date"] for t in trades]
    if pnl.size == 0:
        return {"label": label, "tickets": 0, "total": 0.0, "per_ticket": 0.0,
                "per_month": 0.0, "months_pos": "0/0", "max_dd": 0.0,
                "win_rate": 0.0, "days": ndays, "best": 0.0,
                "ex_best_total": 0.0, "gross_per_ticket": 0.0}
    by_day = {}
    for d, x in zip(tdates, pnl):
        by_day[d] = by_day.get(d, 0.0) + x
    ser = np.array([by_day[d] for d in sorted(by_day)])
    if ndays > ser.size:
        ser = np.concatenate([ser, np.zeros(ndays - ser.size)])
    eq = np.cumsum(ser)
    dd = float(np.min(eq - np.maximum.accumulate(eq)))
    mon = {}
    for d, x in zip(tdates, pnl):
        mon[d[:7]] = mon.get(d[:7], 0.0) + x
    mv = np.array([mon[k] for k in sorted(mon)])
    nmon = max(ndays / 21.0, 1e-9)
    gross = np.array([t["gross"] for t in trades], float)
    return {"label": label, "tickets": int(pnl.size),
            "total": round(float(pnl.sum()), 2),
            "per_ticket": round(float(pnl.mean()), 2),
            "gross_per_ticket": round(float(gross.mean()), 2),
            "per_month": round(float(pnl.sum()) / nmon, 2),
            "months_pos": f"{int((mv>0).sum())}/{len(mv)}",
            "max_dd": round(dd, 2),
            "win_rate": round(float((pnl > 0).mean()), 4),
            "sharpe": round(float(ser.mean() / ser.std(ddof=1) * np.sqrt(252))
                            if ser.size > 1 and ser.std(ddof=1) > 0 else 0.0, 2),
            "days": ndays, "trade_days": len(by_day),
            "best": round(float(pnl.max()), 2),
            "ex_best_total": round(float(pnl.sum() - pnl.max()), 2),
            "mean_notional": round(float(np.mean([t["notional"]
                                                  for t in trades])), 0)}


def split_rows(trades, dates, label=""):
    """The full row: ALL / Y1 / Y2 / aug2026."""
    ds = {0: [d for d in dates if split_of(d) == 0],
          1: [d for d in dates if split_of(d) == 1],
          2: [d for d in dates if split_of(d) == 2]}
    out = {"all": summarize(trades, len(dates), label)}
    for k, name in ((0, "y1"), (1, "y2"), (2, "aug2026")):
        sub = [t for t in trades if split_of(t["date"]) == k]
        out[name] = summarize(sub, len(ds[k]), f"{label}-{name}")
    return out


def study_dates():
    import universe as UV
    return [d for d in UV.gd_dates() if UV.START <= d <= UV.END]


def write_json(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=1, default=str))
    return OUT / name
