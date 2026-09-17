"""CLOSE-MOMENTUM (2026-09-16): the decision-row table.

One row per (date, symbol, decision time). Every configuration in
plan/cm_single.py is then a mask + a score over this table, so a config
and its controls cannot end up on different fills, costs or eligibility.

WHAT A ROW HOLDS
  causal, known at the decision minute m = idx(label) - 1:
    F[...]      plan/cm_lib.features(panel, m)        (17 features)
    printed_m   bar m printed for this name  -- the candidate gate
    volcap      0.20 x shares traded in [m-5, m]      -- the size cap
  priced, NOT decided, from bars after m:
    px_in       OPEN of bar m+1               (the fill; NaN = no fill)
    px_out[x]   last printed CLOSE <= exit bar x, for every exit label
  bookkeeping: date, symbol, decision label.

DECISION LABELS are named by the FILL time. "15:30" means: decide on the
15:29 bar, fill at the 15:30 bar's open. That is the published
"15:30 -> 16:00 last half hour" trade, taken with no knowledge of any bar
at or after 15:30.

UNIVERSES
  wide  plan/rl2/out/days/{D}.npz -- the causal wide universe (halal-PASS
        point-in-time + prior-60-day liquidity), 448 dates, 191 names.
  gap   the +10% gapper pool under RS_CROSS eligibility: a name is a
        candidate at decision minute m only if its regular-session high
        has ALREADY printed >= +10% over the previous close at some bar
        <= m. Pool MEMBERSHIP is still outcome-conditioned (the list was
        built from the day's high), so these rows are reported as an
        upper bound and labelled as such -- see close-momentum-audit.md.

Usage:  python plan/cm_rows.py [--universe wide|gap] [--limit N]
Writes: data/massive/cm/rows_{universe}.npz
"""
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import cm_lib as L                                            # noqa: E402

# decision labels are FILL times; the decision bar is one minute earlier
DEC = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "15:15",
       "15:30", "15:45"]
EXITS = ["12:00", "13:00", "14:00", "15:00", "15:30", "15:50", "15:55",
         "15:59"]


def build_day(p, daily, prof):
    """(F, meta) for one panel: every (symbol, decision) row of that day."""
    rows = []
    for di, lab in enumerate(DEC):
        m = L.idx(lab) - 1
        f = L.features(p, m, daily, prof)
        F = np.stack([f[k] for k in L.FEATS], axis=1)          # [S, NF]
        px_in = p.o[:, m + 1].copy()
        px_in[~p.printed[:, m + 1]] = np.nan
        vc = p.volcap_shares(m)
        px_out = np.stack([p.cf[:, L.idx(x)] for x in EXITS], axis=1)
        # an exit that is not strictly after the fill is not a trade
        for xi, x in enumerate(EXITS):
            if L.idx(x) <= m + 1:
                px_out[:, xi] = np.nan
        rows.append((di, F, p.printed[:, m].copy(), px_in, vc, px_out))
    return rows


def gapper_pool():
    """{date: {symbol: prev_close}} from the campaign gapper caches."""
    pool = {}
    for f in ("gappers_y2025.json", "gappers_year.json",
              "gappers_novol_aug2026.json"):
        fp = L.ROOT / "data" / "massive" / f
        if not fp.exists():
            continue
        for r in json.loads(fp.read_text()):
            pool.setdefault(r["date"], {})[r["symbol"]] = float(r["prev_close"])
    return pool


def rs_cross_mask(p, m, thresh=0.10):
    """RS_CROSS eligibility: has the REGULAR-SESSION high already printed
    >= +10% over the previous close at some bar <= m?  Causal by
    construction -- it reads bars <= m only."""
    lo = L.RTH_LO
    if m < lo:
        return np.zeros(p.S, bool)
    hh = np.nanmax(np.where(np.isfinite(p.h[:, lo:m + 1]),
                            p.h[:, lo:m + 1], -np.inf), axis=1)
    with np.errstate(all="ignore"):
        return hh >= p.prev_close * (1.0 + thresh)


def main():
    uni = "wide"
    limit = None
    if "--universe" in sys.argv:
        uni = sys.argv[sys.argv.index("--universe") + 1]
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    dates = L.study_dates()
    if limit:
        dates = dates[:limit]
    daily = L.Daily.get()
    prof = L.profile()
    pool = gapper_pool() if uni == "gap" else None

    all_dates, all_syms = [], []
    di_l, si_l, dec_l = [], [], []
    F_l, prn_l, pxi_l, vc_l, pxo_l = [], [], [], [], []
    sidx = {}
    t0 = time.time()
    kept = 0
    for k, d in enumerate(dates):
        if uni == "wide":
            fp = L.DAYS / f"{d}.npz"
            if not fp.exists():
                continue
            p = L.Panel.from_rl2(d)
        else:
            names = pool.get(d) or {}
            if not names:
                continue
            p = L.Panel.from_csvs(d, sorted(names), names, dirs=(L.M1, L.M1W))
            if p is None:
                continue
        all_dates.append(d)
        dnum = len(all_dates) - 1
        for s in p.syms:
            if s not in sidx:
                sidx[s] = len(all_syms)
                all_syms.append(s)
        sj = np.array([sidx[s] for s in p.syms], np.int32)
        for di, F, prn, pxi, vc, pxo in build_day(p, daily, prof):
            if uni == "gap":
                prn = prn & rs_cross_mask(p, L.idx(DEC[di]) - 1)
            n = p.S
            di_l.append(np.full(n, dnum, np.int32))
            si_l.append(sj)
            dec_l.append(np.full(n, di, np.int8))
            F_l.append(F.astype(np.float32))
            prn_l.append(prn)
            pxi_l.append(pxi.astype(np.float32))
            vc_l.append(vc.astype(np.float32))
            pxo_l.append(pxo.astype(np.float32))
        kept += 1
        if kept % 50 == 0:
            el = time.time() - t0
            print(f"  [{kept}/{len(dates)}] {d} S={p.S} {el:.0f}s eta "
                  f"{el/kept*(len(dates)-kept):.0f}s", flush=True)

    out = dict(
        dates=np.array(all_dates), syms=np.array(all_syms),
        features=np.array(L.FEATS), dec=np.array(DEC), exits=np.array(EXITS),
        date_i=np.concatenate(di_l), sym_i=np.concatenate(si_l),
        dec_i=np.concatenate(dec_l), F=np.concatenate(F_l),
        printed_m=np.concatenate(prn_l), px_in=np.concatenate(pxi_l),
        volcap=np.concatenate(vc_l), px_out=np.concatenate(pxo_l))
    L.OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(L.OUT / f"rows_{uni}.npz", **out)
    print(f"rows_{uni}: {len(out['date_i']):,} rows, {len(all_dates)} dates, "
          f"{len(all_syms)} symbols, {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
