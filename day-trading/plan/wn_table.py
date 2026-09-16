"""WIDE-NET (2026-09-16) step 1: the labeled $15,000-ticket table.

USER DIRECTION (2026-09-16): "test buying with multiple $15k tickets -- it is
OK to buy the top-30 per day -- until you find the pattern on which a $15k
purchase usually wins; analyze the winning pattern; then backtest that pattern
buying only ONE stock."

This module turns the RL-SERIES v2 causal panel into a flat table of
*hypothetical tickets*: one row per (date, symbol, decision time), carrying

  * the 26 causal features of plan/rl2/features.py, computed from bars with
    grid index <= m and grouped-daily rows with date < D,
  * four WIDE-NET-only extra features that v2 does not have
    (day-of-week, 2-digit SIC sector, scheduled-earnings proximity, and a
    coil measure), all of which are also causal,
  * the realized NET dollar P&L of a $15,000 ticket opened at that decision
    and closed after 15 / 30 / 60 / 120 minutes or at the forced flatten.

NOTHING HERE IS NEW MODELLING. The features, the fills, the cost ladder and
the labels are read straight out of plan/rl2/out/feat/*.npz, which is the
cache plan/rl2/honesty.py poison-tested 64/64. This file only reshapes them
and adds the four extra columns. It never writes into plan/rl2/.

ELIGIBILITY (identical to plan/rl2/sim.py::run_day, corrected 2026-09-16)
  A name is a CANDIDATE at decision minute m iff bar m itself printed
  (`printed_m`).  Whether minute m+1 prints -- i.e. whether the order can
  actually fill -- is NOT knowable at m, so it must never filter the
  candidate set.  A chosen name whose m+1 did not print simply books $0:
  the order did not happen and the day's ticket is spent.  The first cut
  of this table gated candidates on `printed` (= m+1 fillable), which
  silently dropped 19.4% of printed bars using future information; the
  poison test in plan/wn_poison.py is what caught it.

P&L CONVENTION (identical to plan/rl2/sim.py::run_day)
  notional = min($15,000, 0.20 * trailing-5-minute share volume * fill price)
  a ticket below $500 of notional does not happen (the size cap killed it)
  pnl = notional * (1 + cost_frac(entry minute)) * tgt[t, s, h]
  cost_frac = 10 bps, +50 bps if the fill minute is outside 09:30-16:00.

DECISION TIMES are a fixed grid (ET): the five the mandate names
(09:35 10:00 10:30 11:00 13:00), four more regular-session ones for shape
(09:45 12:00 14:00 15:00), and five extended-hours ones (07:00 08:00 09:00
09:25 16:30) so the extended-hours toll is measured rather than assumed.

Usage:  python plan/wn_table.py            (writes data/massive/wn/table.npz)
        python plan/wn_table.py --smoke 20
"""
import json
import sys
import time
from datetime import date as _date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0]
FEAT = HERE / "rl2" / "out" / "feat"
OUT = ROOT / "data" / "massive" / "wn"

# ---- grid constants, copied (not imported) from plan/rl2/features.py so a
# ---- change there cannot silently move this table.  Asserted in main().
NMIN = 960
RTH_LO = 330          # 09:30 ET on the 04:00-based grid
RTH_HI = 720          # 16:00 ET
STEP = 5
STEPS = np.arange(0, NMIN - 5 + 1, STEP)
T = len(STEPS)
FEE_BPS = 10.0
EXT_BPS = 50.0
HORIZONS = [15, 30, 60, 120, 10 ** 6]
HNAMES = ["h15", "h30", "h60", "h120", "flat"]
TICKET = 15000.0
MIN_NOTIONAL = 500.0

RL2_FEATURES = [
    "gap_vs_prevclose", "ret_since_open", "dist_vwap_day", "dist_vwap30",
    "ret5", "ret15", "ret30", "ret60",
    "rvol_profile", "log_dv5", "dv_burst", "rvol30", "bar_range5",
    "print_density30", "print_density5", "amihud30",
    "tod", "min_to_1600", "is_ext", "log_price",
    "prev_day_ret", "log_mdv20", "dist_hi", "dist_lo",
    "xs_breadth", "xs_rank_ret30",
]
EXTRA_FEATURES = ["dow", "sic2", "earn_prox", "coil",
                  "earn_rh", "earn_fresh"]
FEATURES = RL2_FEATURES + EXTRA_FEATURES

# ET decision times -> grid minute (ET minute-of-day - 240)
DEC_ET = ["07:00", "08:00", "09:00", "09:25", "09:35", "09:45", "10:00",
          "10:30", "11:00", "12:00", "13:00", "14:00", "15:00", "16:30"]
CORE_ET = ["09:35", "10:00", "10:30", "11:00", "13:00"]


def et_to_step(hhmm):
    h, m = hhmm.split(":")
    g = int(h) * 60 + int(m) - 240
    assert g % STEP == 0 and 0 <= g <= STEPS[-1], hhmm
    return g // STEP


DEC_T = np.array([et_to_step(x) for x in DEC_ET], np.int32)
NT = len(DEC_T)


def cost_frac(minute):
    ext = (minute < RTH_LO) | (minute >= RTH_HI)
    return (FEE_BPS + EXT_BPS * ext) / 1e4


# --------------------------------------------------------------- extras
def load_sic2():
    """2-digit SIC per ticker from data/sic_codes.json (EDGAR submissions).

    A company's SIC changes essentially never, so a present-day snapshot is
    a legitimate slowly-varying label; it carries no information about any
    particular day's outcome.  Missing -> 0.
    """
    d = json.loads((ROOT / "data" / "sic_codes.json").read_text())
    out = {}
    for k, v in d.items():
        s = (v or {}).get("sic") or ""
        if s.isdigit():
            out[k] = int(s[:2])
    return out


def load_earn():
    """{sym: sorted [dates]} of reported earnings dates.

    CAUSALITY NOTE.  A scheduled earnings DATE is public weeks ahead, so
    "today is (or was yesterday / is tomorrow) an earnings day" is knowable
    at 09:35.  What is NOT knowable is the result, and nothing here reads
    `beat`.  The cache was fetched in 2026-09 so its *coverage* is
    backward-looking; the feature is therefore reported separately in the
    audit and never used to build the headline pattern.
    """
    try:
        d = json.loads((ROOT / "data" / "earnings_dates.json").read_text())
    except Exception:
        return {}
    out = {}
    for s, rows in d.items():
        ds = sorted({r["date"] for r in rows if r.get("date")})
        if ds:
            out[s] = ds
    return out


def load_earn_rh():
    """{sym: {date: timing}} from the Robinhood earnings calendar
    (data/massive/wn/rh_earnings_calendar.json, 51,140 events, 2024-10-01
    .. 2026-10-01, all 191 universe symbols covered, 1,714 events on them).

    CAUSALITY.  A scheduled report DATE and its am/pm slot are published
    weeks ahead, so at 09:35 on D a trader knows "this name reports before
    the open today" or "tonight".  What is NOT knowable is the result, and
    nothing here reads eps_actual / eps_estimate (the collector was
    instructed not to keep them).  The CAVEAT is that this calendar was
    pulled in 2026-09, so it is the REALISED schedule; a name that moved
    its date after the fact would be mis-flagged on the old date.  That is
    a small, unsigned error, and the feature is reported separately in the
    audit for exactly this reason.
    """
    f = ROOT / "data" / "massive" / "wn" / "rh_earnings_calendar.json"
    if not f.exists():
        return {}
    out = {}
    for e in json.loads(f.read_text()).get("events", []):
        s, d = e.get("symbol"), e.get("date")
        if s and d:
            out.setdefault(s, {})[d] = (e.get("timing") or "")[:2]
    return out


def earn_rh_feats(sym, date, cal, prev_date):
    """(signed days to nearest report, clipped to +-5; 9 = none) and
    (1 if the announcement became public between the previous close and
    today's open: a prior-session 'pm' report or a today 'am' report)."""
    ds = cal.get(sym)
    if not ds:
        return 9.0, 0.0
    y, m, dd = (int(x) for x in date.split("-"))
    d0 = _date(y, m, dd)
    best = 9.0
    for s in ds:
        yy, mm, ddd = (int(x) for x in s.split("-"))
        k = (_date(yy, mm, ddd) - d0).days
        if abs(k) <= 5 and abs(k) < abs(best):
            best = float(k)
    fresh = float(ds.get(date, "") == "am"
                  or (prev_date is not None and ds.get(prev_date, "") == "pm"))
    return best, fresh


def earn_prox(sym, date, earn):
    """Signed trading-day-ish distance to the nearest earnings date, clipped
    to +-5 calendar days; 9 = none nearby.  Negative = earnings already
    reported (post-event drift regime), positive = upcoming."""
    ds = earn.get(sym)
    if not ds:
        return 9.0
    y, m, dd = (int(x) for x in date.split("-"))
    d0 = _date(y, m, dd)
    best = 9.0
    for s in ds:
        yy, mm, ddd = (int(x) for x in s.split("-"))
        k = (_date(yy, mm, ddd) - d0).days
        if abs(k) <= 5 and abs(k) < abs(best):
            best = float(k)
    return best


# --------------------------------------------------------------- build
def day_block(date, z, sic2, earn, cal=None, prev_date=None):
    """The wide-net row block for one day, from an rl2 feature dict/npz.

    Factored out so plan/wn_poison.py can run the IDENTICAL code on a
    poisoned copy of the bars and compare arrays element-wise.  `z` must
    expose syms / F / printed / fill_o / volcap / tgt / tgt_ok.
    """
    ss = [str(x) for x in z["syms"]]
    S = len(ss)
    F = np.asarray(z["F"])[DEC_T]
    prn = np.asarray(z["printed"])[DEC_T]
    fo = np.asarray(z["fill_o"])[DEC_T].astype(np.float64)
    vc = np.asarray(z["volcap"])[DEC_T].astype(np.float64)
    tg = np.asarray(z["tgt"])[DEC_T].astype(np.float64)
    tok = np.asarray(z["tgt_ok"])[DEC_T]
    mfill = np.minimum(STEPS[DEC_T] + 1, NMIN - 1)
    cf = cost_frac(mfill)[:, None]
    with np.errstate(all="ignore"):
        notion = np.where(np.isfinite(fo) & (fo > 0),
                          np.minimum(TICKET, vc * fo), np.nan)
    live = prn & np.isfinite(notion) & (notion >= MIN_NOTIONAL)
    pnl = notion[:, :, None] * (1.0 + cf[:, :, None]) * tg
    dow = _date(*(int(x) for x in date.split("-"))).weekday()
    ex = np.zeros((NT, S, len(EXTRA_FEATURES)), np.float32)
    ex[:, :, 0] = dow
    ex[:, :, 1] = np.array([sic2.get(s, 0) for s in ss], np.float32)
    ex[:, :, 2] = np.array([earn_prox(s, date, earn) for s in ss], np.float32)
    ex[:, :, 3] = F[:, :, RL2_FEATURES.index("rvol30")] / \
        np.maximum(F[:, :, RL2_FEATURES.index("bar_range5")], 1e-6)
    er = np.array([earn_rh_feats(s, date, cal or {}, prev_date) for s in ss],
                  np.float32)
    ex[:, :, 4] = er[:, 0]
    ex[:, :, 5] = er[:, 1]
    return {"syms": ss,
            "F": np.concatenate([F, ex], axis=2).astype(np.float32),
            "notional": np.nan_to_num(notion), "printed": live,
            "printed_m": prn,
            "fill_px": np.nan_to_num(fo),
            "pnl": np.nan_to_num(pnl), "ok": live[:, :, None] & tok}


def build(smoke=0):
    OUT.mkdir(parents=True, exist_ok=True)
    sic2 = load_sic2()
    earn = load_earn()
    files = sorted(FEAT.glob("*.npz"))
    if smoke:
        files = files[:smoke]
    cal = load_earn_rh()
    cols = {k: [] for k in
            ("date_i", "sym_i", "dec_i", "notional", "printed",
             "printed_m", "fill_px")}
    for h in HNAMES:
        cols["pnl_" + h] = []
        cols["ok_" + h] = []
    Fl = []
    dates, syms_all, sidx = [], [], {}
    t0 = time.time()
    all_dates = [p.stem for p in sorted(FEAT.glob("*.npz"))]
    prevmap = {d: (all_dates[i - 1] if i else None)
               for i, d in enumerate(all_dates)}
    for di, p in enumerate(files):
        date = p.stem
        z = np.load(p, allow_pickle=False)
        assert int(z["steps"][0]) == 0 and len(z["steps"]) == T, date
        b = day_block(date, z, sic2, earn, cal, prevmap.get(date))
        ss = b["syms"]
        S = len(ss)
        for s in ss:
            if s not in sidx:
                sidx[s] = len(syms_all)
                syms_all.append(s)
        si = np.array([sidx[s] for s in ss], np.int32)
        nt, ns = np.mgrid[0:NT, 0:S]
        Fl.append(b["F"].reshape(NT * S, -1))
        cols["date_i"].append(np.full(NT * S, di, np.int32))
        cols["sym_i"].append(np.tile(si, NT))
        cols["dec_i"].append(nt.reshape(-1).astype(np.int8))
        cols["notional"].append(b["notional"].reshape(-1))
        cols["printed"].append(b["printed"].reshape(-1))
        cols["printed_m"].append(b["printed_m"].reshape(-1))
        cols["fill_px"].append(b["fill_px"].reshape(-1))
        for hi, hn in enumerate(HNAMES):
            cols["pnl_" + hn].append(b["pnl"][:, :, hi].reshape(-1))
            cols["ok_" + hn].append(b["ok"][:, :, hi].reshape(-1))
        dates.append(date)
        if (di + 1) % 100 == 0:
            el = time.time() - t0
            print(f"  [{di+1}/{len(files)}] {date} {el:.0f}s", flush=True)

    out = {k: np.concatenate(v) for k, v in cols.items()}
    out["F"] = np.concatenate(Fl).astype(np.float32)
    out["dates"] = np.array(dates)
    out["syms"] = np.array(syms_all)
    out["features"] = np.array(FEATURES)
    out["dec_et"] = np.array(DEC_ET)
    out["horizons"] = np.array(HNAMES)
    f = OUT / ("table_smoke.npz" if smoke else "table.npz")
    np.savez_compressed(f, **out)
    n = len(out["date_i"])
    print(json.dumps({
        "file": str(f), "rows": int(n), "dates": len(dates),
        "first": dates[0], "last": dates[-1], "symbols": len(syms_all),
        "eligible_rows_bar_m": int(out["printed_m"].sum()),
        "fillable_rows_bar_m1": int(out["printed"].sum()),
        "ok_h30": int(out["ok_h30"].sum()),
        "features": len(FEATURES), "dec_times": DEC_ET,
        "secs": round(time.time() - t0, 1)}, indent=1), flush=True)


if __name__ == "__main__":
    sm = 0
    if "--smoke" in sys.argv:
        sm = int(sys.argv[sys.argv.index("--smoke") + 1])
    build(sm)
