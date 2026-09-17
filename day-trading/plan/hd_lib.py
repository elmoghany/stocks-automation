"""HARNESS-DIAGNOSTIC (2026-09-17): is the stack biased, or is the frame empty?

The user's question is not "does config X work" -- every config has failed --
but "why is nothing even close; something is wrong".  Two hypotheses:

  (A) the harness / data / cost stack is biased AGAINST us, so a real edge is
      being hidden by the measurement, or
  (B) the harness is honest and the SAME-DAY, LONG-ONLY, HALAL, MARKET-ORDER
      frame simply contains almost no harvestable drift.

The way to tell them apart is not another config.  It is to run KNOWN-POSITIVE
controls through the same stack.  If a published, robust, well-measured effect
comes out positive here with the right sign and the right order of magnitude,
the stack can see money when money is there, and (B) follows.  If the known
positives come out flat or negative, the stack is broken and (A) follows.

CONTROLS (each one is a thing the literature says must be there)
  1  overnight vs intraday decomposition (Lou/Polk/Skouras 2019 and a long
     replication line): close->open carries essentially all of the equity
     return; open->close is flat or negative.
  2  buy-and-hold of the same universe over a window in which the market rose:
     the equity premium itself.
  3  cost-model reconciliation: re-price the LIVE paper round trips through
     the harness and look at the sign of (harness - live).
  4  foresight ladder: perfect 5/10/30/60-minute information, same-day frame.
  5  frame ablation: relax ONE constraint at a time on the SAME data.

DATA
  gd    data/massive/gd/{D}.json.gz -- Polygon grouped daily, o/h/l/c/v for
        every US ticker, split-adjusted to the present.  VALIDATED here: its
        `o` matches the 09:30 minute-bar open EXACTLY on 789 sampled
        symbol-days (median |diff| 0.0000%), and its `c` sits 4.8 bps from the
        last RTH minute close (the closing auction print).  So gd is the
        regular-session open and close, and the overnight/intraday split can
        be computed on the FULL liquid universe, halal or not.
  m1w   data/massive/m1w -- 1-minute bars, 191 strict-halal names, 448 dates.
  m1etf data/massive/m1etf -- SPUS/HLAL/SPSK/SPRE/UMMA/SPWO + SPY.
  rl2   plan/rl2/out/days/{D}.npz -- the causal wide panel (45-82 names/day).

UNIVERSES (all three defined on the same 448 dates, all causal: membership on
date D reads only rows with date < D)
  liquid        plan/rl2/out/screen.json.gz     4,041-4,967 names/day, NO halal
  halal_wide    plan/uq_out/universe/{D}.json     225-316 names/day
  halal_strict  plan/rl2/out/universe/{D}.json     45-82  names/day  (the
                universe every intraday result in EXPERIMENTS-INDEX.md uses)

COSTS
  flat      10 bps/side inside 09:30-16:00, +50 bps outside  (the incumbent)
  measured  plan/cr_out/cost_decomp.json -- median 12.05 bps/side total
            (half-spread 2.77 + impact 9.21 at the conservative coef 1.0),
            and 2.77 bps/side if only the half-spread is charged.
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / "rl2"))

GD = ROOT / "data" / "massive" / "gd"
M1W = ROOT / "data" / "massive" / "m1w"
M1 = ROOT / "data" / "massive" / "m1"
M1ETF = ROOT / "data" / "massive" / "m1etf"
DAYS = HERE / "rl2" / "out" / "days"
SCREEN = HERE / "rl2" / "out" / "screen.json.gz"
UNI_STRICT = HERE / "rl2" / "out" / "universe"
UNI_WIDE = HERE / "uq_out" / "universe"
TRADING_DATES = HERE / "rl2" / "out" / "trading_dates.json"
OUT = ROOT / "data" / "massive" / "hd"

START = "2024-10-22"
END = "2026-08-06"
TRAIN_END = "2025-08-01"
OOS_END = "2026-08-01"

NMIN = 960
BASE_MIN = 240
RTH_LO = 330                       # 09:30
RTH_HI = 720                       # 16:00
FEE_BPS = 10.0
EXT_BPS = 50.0

TICKET = 15000.0
TICKETS_PER_DAY = 7
DAYS_PER_MONTH = 21.0
TICKETS_PER_MONTH = TICKETS_PER_DAY * DAYS_PER_MONTH      # 147
TARGET_PER_MONTH = 7500.0


def idx(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m) - BASE_MIN


def clock(k):
    m = k + BASE_MIN
    return f"{m//60:02d}:{m%60:02d}"


def split_of(d):
    return 0 if d < TRAIN_END else (1 if d < OOS_END else 2)


def cost_frac(minute):
    ext = (minute < RTH_LO) or (minute >= RTH_HI)
    return (FEE_BPS + EXT_BPS * ext) / 1e4


def study_dates():
    ds = json.loads(TRADING_DATES.read_text())
    return [d for d in ds if START <= d <= END]


def all_gd_dates():
    ds = json.loads(TRADING_DATES.read_text())
    return ds


# ------------------------------------------------------------------ gd panel
_GD_CACHE = {}


def gd_day(d):
    if d not in _GD_CACHE:
        if len(_GD_CACHE) > 600:
            _GD_CACHE.clear()
        rows = json.loads(gzip.open(GD / f"{d}.json.gz", "rt").read())
        _GD_CACHE[d] = {x["T"]: x for x in rows if x.get("T")}
    return _GD_CACHE[d]


def gd_matrix(dates):
    """syms, O, C, V (len(dates) x S) float64 with NaN for absent rows."""
    per = [gd_day(d) for d in dates]
    syms = sorted(set().union(*[set(p) for p in per]))
    sidx = {s: i for i, s in enumerate(syms)}
    D, S = len(dates), len(syms)
    O = np.full((D, S), np.nan)
    C = np.full((D, S), np.nan)
    V = np.full((D, S), np.nan)
    for i, p in enumerate(per):
        for s, x in p.items():
            j = sidx[s]
            o, c, v = x.get("o"), x.get("c"), x.get("v")
            if o is None or c is None:
                continue
            O[i, j] = o
            C[i, j] = c
            V[i, j] = v if v is not None else np.nan
    return syms, O, C, V


# ------------------------------------------------------------------ universes
def members(kind, dates):
    """{date: set(sym)} for 'liquid' / 'halal_wide' / 'halal_strict'."""
    if kind == "liquid":
        sc = json.loads(gzip.open(SCREEN, "rt").read())
        # rows are [symbol, median_dollar_volume, median_close]
        return {d: {r[0] if isinstance(r, list) else r for r in sc.get(d, [])}
                for d in dates}
    src = UNI_WIDE if kind == "halal_wide" else UNI_STRICT
    out = {}
    for d in dates:
        f = src / f"{d}.json"
        if not f.exists():
            out[d] = set()
            continue
        rows = json.loads(f.read_text())
        out[d] = {r["symbol"] if isinstance(r, dict) else r for r in rows}
    return out


# --------------------------------------------------------------- statistics
def tstat(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < 3 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(x.size)))


def nw_tstat(x, lags=5):
    """Newey-West t-stat (the daily series is close to iid, but say it)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 10:
        return 0.0
    e = x - x.mean()
    g0 = float(e @ e) / n
    s = g0
    for L in range(1, min(lags, n - 1) + 1):
        gl = float(e[L:] @ e[:-L]) / n
        s += 2.0 * (1.0 - L / (lags + 1.0)) * gl
    if s <= 0:
        return 0.0
    return float(x.mean() / np.sqrt(s / n))


def ticket_pnl(r, cost_bps_side, notional=TICKET):
    """$ P&L of a `notional` ticket earning simple return r with a
    cost_bps_side toll charged on each side."""
    c = cost_bps_side / 1e4
    return notional * ((1.0 + r) * (1.0 - c) / (1.0 + c) - 1.0)


def per_month(per_ticket, tickets_per_month=TICKETS_PER_MONTH):
    return per_ticket * tickets_per_month


def write(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(obj, indent=1, default=str))
    return p


def load(name):
    return json.loads((OUT / name).read_text())


# ------------------------------------------------------------- minute panels
def read_m1(path, date):
    """(o,h,l,c,v) on the 960-slot ET grid, or None.  Same parser as
    plan/cm_lib._read_csv_grid / plan/rl2/panel.read_m1."""
    import csv
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    off = int(datetime.strptime(date, "%Y-%m-%d").replace(hour=12, tzinfo=ET)
              .utcoffset().total_seconds() // 60)
    o = np.full(NMIN, np.nan)
    h = np.full(NMIN, np.nan)
    lo = np.full(NMIN, np.nan)
    c = np.full(NMIN, np.nan)
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


def find_m1(sym, date, dirs=(M1W, M1, M1ETF)):
    for d in dirs:
        f = d / f"{sym}_{date}.csv"
        if f.exists():
            b = read_m1(f, date)
            if b is not None:
                return b
    return None


def npz_panel(date):
    """(syms, o,h,l,c,v, prev_close) for the causal wide panel, or None."""
    f = DAYS / f"{date}.npz"
    if not f.exists():
        return None
    z = np.load(f, allow_pickle=False)
    return ([str(s) for s in z["syms"]],
            z["o"].astype(float), z["h"].astype(float), z["l"].astype(float),
            z["c"].astype(float), z["v"].astype(float),
            z["prev_close"].astype(float))


def ffill(a):
    """Row-wise forward fill; NaN before the first print."""
    a = np.atleast_2d(a)
    idx_ = np.where(~np.isnan(a), np.arange(a.shape[1])[None, :], 0)
    np.maximum.accumulate(idx_, axis=1, out=idx_)
    out = a[np.arange(a.shape[0])[:, None], idx_]
    never = np.isnan(a).all(axis=1)
    first = np.argmax(~np.isnan(a), axis=1)
    for i in range(a.shape[0]):
        if never[i]:
            out[i] = np.nan
        else:
            out[i, :first[i]] = np.nan
    return out
