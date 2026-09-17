"""OPEN-UNIVERSE (2026-09-17) -- shared library.

USER DIRECTION (2026-09-17): "work on the agents but IGNORE whether the stock
is halal for now" -- the halal gate is being repaired separately, so the edge
search runs on the FULL liquid US universe and the halal filter is applied
post-hoc (plan/ou_halal.py).  Everything else in the mandate is unchanged:
net >= $7,500/month, $15k same-day tickets (<= $100k/day, <= 7/day), long-only,
and NEVER future / end-of-day information at decision time.

THE UNIVERSE (causal; membership on date D reads only rows with date < D)
  (a) TYPE: the listing must be an operating company's ordinary equity --
      Polygon `type` in {CS, ADRC} (data/hgr_ticker_meta.json, topped up by
      plan/ou_meta.py).  ETF / ETV / ETN / ETS / FUND / PFD / UNIT / WARRANT /
      RIGHT / SP / BOND / ADRP / ADRR / ADRW are excluded, and so is the
      closed-end-fund SIC 6726, because the mandate asks for operating
      companies of EVERY SECTOR -- so financials (SIC 6xxx), which the halal
      screen removed wholesale, are KEPT here except for the fund codes.
      A symbol whose type cannot be established is EXCLUDED and counted.
  (b) LIQUIDITY: over the PRIOR 60 trading sessions (grouped-daily rows with
      date < D, at least 40 present) median dollar volume >= $5,000,000 and
      median close >= $5.00.

  This is the rl2/uq screen with the thresholds raised ($2M/$3 -> $5M/$5), the
  halal gate removed, and a type gate added.  ~1,900 names/day.

  MINUTE SUBSET: the top MINUTE_TOP names per date by that same prior-60-day
  median dollar volume get 1-minute bars in data/massive/m1o; the rest of the
  universe is tested on the grouped-daily open/close grid only.

COSTS.  Two models are reported side by side for every result, per the
mandate:
  flat10    10 bps/side inside 09:30-16:00, +50 bps outside  (the incumbent)
  measured  plan/cr_cost.CostModel over per-minute statistics.  COST-REBASE
            built those statistics from the 1-second tape; this line has no
            1-second tape for most of the open universe, so plan/ou_cost.py
            builds the SAME npz shape out of the 1-minute bars with the
            `hl2` (per-second bid-ask-bounce) channel set to NaN.  The
            estimator then reduces to max(Corwin-Schultz, Abdi-Ranaldo) on
            trailing 1-minute bars plus the identical square-root impact
            term, and plan/ou_cost.py --validate checks the 1-minute-derived
            number against the 1-second-derived number on every symbol-day
            where BOTH exist.

Nothing in this module reads a date >= the decision date, and nothing reads a
minute >= the decision minute.
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "ou_out"
GD = ROOT / "data" / "massive" / "gd"
M1O = ROOT / "data" / "massive" / "m1o"
META_F = ROOT / "data" / "hgr_ticker_meta.json"
TRADING_DATES = HERE / "rl2" / "out" / "trading_dates.json"

# ---------------------------------------------------------------- the window
START = "2024-10-22"
END = "2026-08-06"
TRAIN_END = "2025-08-01"          # Y1 = [START, TRAIN_END)
OOS_END = "2026-08-01"            # Y2 = [TRAIN_END, OOS_END); aug2026 after

# ------------------------------------------------------------ the screen
LOOKBACK = 60
MIN_OBS = 40
MIN_MDV = 5_000_000.0
MIN_MPX = 5.0
MINUTE_TOP = 600

KEEP_TYPES = {"CS", "ADRC"}
FUND_SICS = {"6726"}              # closed-end funds / investment offices NEC

# ------------------------------------------------------------ the frame
NMIN = 960                        # 04:00-20:00 on a 1-minute grid
BASE_MIN = 240                    # grid slot 0 == 04:00 ET
RTH_LO = 330                      # 09:30
RTH_HI = 720                      # 16:00
FEE_BPS = 10.0
EXT_BPS = 50.0
TICKET = 15000.0
TICKETS_PER_DAY = 7
DAILY_CAP = 100_000.0
DAYS_PER_MONTH = 21.0
TICKETS_PER_MONTH = TICKETS_PER_DAY * DAYS_PER_MONTH
TARGET_PER_MONTH = 7500.0
VOL_CAP_FRAC = 0.20               # <= 20% of trailing 5-minute share volume
MIN_NOTIONAL = 500.0


def ticket_sizes(k):
    """The account's own ladder: flat $15,000 tickets with the LAST one cut
    so the day never exceeds $100,000 of same-day notional (memory rule
    "cash-account-ticket-rules": one position at a time, flat $15k tickets,
    $10k last, $100k/day cap).  At k = 7 this is 6 x $15,000 + 1 x $10,000,
    not 7 x $15,000 -- which is what HARNESS-DIAGNOSTIC's frame ablation and
    every hd_frame-derived number actually charged.  Reported both ways."""
    sizes = np.full(k, TICKET)
    if k * TICKET > DAILY_CAP:
        head = int(DAILY_CAP // TICKET)
        sizes = np.full(k, 0.0)
        sizes[:head] = TICKET
        rem = DAILY_CAP - head * TICKET
        if head < k:
            sizes[head] = rem
    return sizes


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


def trading_dates():
    return json.loads(TRADING_DATES.read_text())


def study_dates():
    return [d for d in trading_dates() if START <= d <= END]


# ------------------------------------------------------------------- gd panel
_GD = {}


def gd_day(d):
    if d not in _GD:
        if len(_GD) > 700:
            _GD.clear()
        rows = json.loads(gzip.open(GD / f"{d}.json.gz", "rt").read())
        _GD[d] = {x["T"]: x for x in rows if x.get("T")}
    return _GD[d]


def gd_matrices(dates):
    """syms, sidx, {o,h,l,c,v} each (len(dates), S) float64, NaN if absent."""
    per = [gd_day(d) for d in dates]
    syms = sorted(set().union(*[set(p) for p in per]))
    sidx = {s: i for i, s in enumerate(syms)}
    D, S = len(dates), len(syms)
    A = {k: np.full((D, S), np.nan) for k in "ohlcv"}
    for i, p in enumerate(per):
        for s, x in p.items():
            j = sidx[s]
            for k in "ohlcv":
                val = x.get(k)
                if val is not None:
                    A[k][i, j] = val
    return syms, sidx, A


# ------------------------------------------------------------------- metadata
_META = [None]


def meta():
    if _META[0] is None:
        _META[0] = json.loads(META_F.read_text())
    return _META[0]


def is_operating(sym):
    """True iff `sym` is an operating company's ordinary equity."""
    m = meta().get(sym)
    if not m or m.get("status") != "ok":
        return False
    if m.get("type") not in KEEP_TYPES:
        return False
    if (m.get("sic_code") or "") in FUND_SICS:
        return False
    return True


def sic2(sym):
    m = meta().get(sym) or {}
    s = m.get("sic_code") or ""
    return s[:2] if len(s) >= 2 else "??"


def mcap(sym):
    """PRESENT-DAY market cap.  NOT causal -- see `mcap_matrix`."""
    m = meta().get(sym) or {}
    v = m.get("market_cap")
    return float(v) if v else np.nan


def shares(sym):
    m = meta().get(sym) or {}
    v = m.get("share_class_shares_outstanding") \
        or m.get("weighted_shares_outstanding")
    return float(v) if v else np.nan


def prev_close_matrix(dates, syms, sidx):
    """(D, S) grouped-daily close of the PREVIOUS trading session."""
    td = trading_dates()
    prev_of = {d: td[i - 1] for i, d in enumerate(td) if i}
    P = np.full((len(dates), len(syms)), np.nan)
    for i, d in enumerate(dates):
        pd_ = prev_of.get(d)
        if pd_ is None:
            continue
        for s, x in gd_day(pd_).items():
            j = sidx.get(s)
            if j is not None and x.get("c") is not None:
                P[i, j] = x["c"]
    return P


def mcap_matrix(dates, syms, sidx):
    """(D, S) CAUSAL market cap = present-day share count x the PREVIOUS
    session's close.

    The `market_cap` field in data/hgr_ticker_meta.json is a 2026-09
    snapshot.  Slicing 2024-2026 dates on it is look-ahead on MEMBERSHIP --
    a name is in the "> $10B" bucket partly *because* it went up during the
    study window, which is exactly the outcome-conditioned membership that
    retracted the MX series.  Replacing the price leg with the previous
    session's close removes the dominant term; what remains is drift in the
    share count, which moves a few percent a year and is not a function of
    the day's outcome.  Grouped-daily closes are split-adjusted to the
    present and so is the present-day share count, so the product is
    consistent across splits -- the same convention plan/rl2/universe.py
    records for its own mcap.
    """
    sh = np.array([shares(s) for s in syms], float)
    return prev_close_matrix(dates, syms, sidx) * sh[None, :]


# ------------------------------------------------------------------ universe
def universe(dates=None):
    """{date: [[sym, mdv, mpx], ...]} sorted by mdv DESC.  Built once by
    plan/ou_universe.py into plan/ou_out/universe.json.gz."""
    u = json.loads(gzip.open(OUT / "universe.json.gz", "rt").read())
    if dates is None:
        return u
    return {d: u[d] for d in dates if d in u}


def minute_members(dates=None):
    """{date: [sym, ...]} -- the top MINUTE_TOP by mdv that have m1o bars."""
    u = universe(dates)
    return {d: [r[0] for r in v[:MINUTE_TOP]] for d, v in u.items()}


# --------------------------------------------------------------- minute bars
def m1o_path(sym, date):
    return M1O / f"{sym}_{date}.npz"


def read_m1o(sym, date):
    """(o,h,l,c,v) on the 960-slot 04:00-20:00 ET grid, or None."""
    f = m1o_path(sym, date)
    if not f.exists():
        return None
    try:
        with np.load(f) as z:
            if z["o"].size != NMIN:
                return None
            return (z["o"].astype(np.float64), z["h"].astype(np.float64),
                    z["l"].astype(np.float64), z["c"].astype(np.float64),
                    z["v"].astype(np.float64))
    except Exception:
        return None


def write_m1o(sym, date, o, h, l, c, v):
    import os
    M1O.mkdir(parents=True, exist_ok=True)
    f = m1o_path(sym, date)
    tmp = f.with_name(f.name + f".{os.getpid()}.part.npz")
    np.savez_compressed(tmp, o=o.astype(np.float32), h=h.astype(np.float32),
                        l=l.astype(np.float32), c=c.astype(np.float32),
                        v=v.astype(np.float32))
    os.replace(tmp, f)


# --------------------------------------------------------------- statistics
def tstat(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < 3 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(x.size)))


def ticket_pnl(r, cost_bps_side, notional=TICKET):
    c = cost_bps_side / 1e4
    return notional * ((1.0 + r) * (1.0 - c) / (1.0 + c) - 1.0)


def spearman(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 5:
        return np.nan
    from scipy.stats import rankdata
    ra = rankdata(a[ok])
    rb = rankdata(b[ok])
    ra -= ra.mean()
    rb -= rb.mean()
    den = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / den) if den > 0 else np.nan


def write(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(obj, indent=1, default=str))
    return p


def load(name):
    return json.loads((OUT / name).read_text())


def summarise(day_pnl, dates_used, tk, label=""):
    """Standard result block: total / Y1 / Y2 / aug2026 / months / ex-best."""
    day_pnl = np.asarray(day_pnl, float)
    tk = np.asarray(tk, float)
    if day_pnl.size == 0:
        return {"label": label, "tickets": 0, "per_month": 0.0}
    sp = np.array([split_of(d) for d in dates_used])
    nmon = day_pnl.size / DAYS_PER_MONTH
    eq = np.cumsum(day_pnl)
    mon = {}
    for d, p in zip(dates_used, day_pnl):
        mon.setdefault(d[:7], 0.0)
        mon[d[:7]] += float(p)
    mv = np.array(list(mon.values()))
    y1 = day_pnl[sp == 0]
    y2 = day_pnl[sp == 1]
    aug = day_pnl[sp == 2]

    def _pm(a):
        return round(float(a.sum()) / max(a.size / DAYS_PER_MONTH, 1e-9), 2) \
            if a.size else None

    return {
        "label": label,
        "days": int(day_pnl.size), "tickets": int(tk.size),
        "per_ticket": round(float(tk.mean()), 2) if tk.size else None,
        "per_day": round(float(day_pnl.mean()), 2),
        "per_month": round(float(day_pnl.sum()) / nmon, 2),
        "total": round(float(day_pnl.sum()), 2),
        "y1_per_month": _pm(y1), "y2_per_month": _pm(y2),
        "aug2026_total": round(float(aug.sum()), 2) if aug.size else None,
        "months_positive": int((mv > 0).sum()), "months": int(mv.size),
        "max_dd": round(float(np.min(eq - np.maximum.accumulate(eq))), 2),
        "ex_best": round(float(tk.sum() - tk.max()), 2) if tk.size else None,
        "ex_best_day": round(float(day_pnl.sum() - day_pnl.max()), 2),
        "win_rate": round(float((tk > 0).mean()), 4) if tk.size else None,
    }


def percentile_of(value, controls):
    c = np.asarray(controls, float)
    c = c[np.isfinite(c)]
    if c.size == 0:
        return None
    return round(100.0 * float((c < value).mean()), 1)
