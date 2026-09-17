"""OPEN-UNIVERSE (2026-09-17) TEST 2, step 1: the $15,000-ticket table on the
open universe's minute subset.

This is WIDE-NET's table (plan/wn_table.py) pointed at a universe 10x wider.
NOTHING about the feature block, the fill rule, the volume cap, the cost ladder
or the labels is re-derived here: the day block is computed by calling
`rl2.features.compute_day` and then `wn_table.day_block` -- the same functions
plan/rl2/honesty.py poison-tested 64/64 and plan/wn_poison.py poison-tested at
the level of the picks.  What this module does is assemble the INPUT those
functions expect out of the m1o cache, which is stored symbol-major (one npz
per symbol, all 448 dates) because that is what makes 268,800 symbol-days
fetchable in ~7,000 API calls.

THE TRANSPOSE.  A per-date panel needs every symbol; a per-symbol file holds
every date.  Opening 600 symbol files per date would read the cache 600 times.
Instead the build walks BLOCKS of dates: load each symbol file once per block,
slice out the block's dates, and emit the block's per-date panels.  With
BLOCK = 32 the cache is read 14 times end to end instead of 600.

CAUSALITY.  Membership is the open universe's (prior-60-session liquidity +
an operating-company type gate), so nothing about date D's session decides who
is in it.  The intraday volume profile the relative-volume feature needs is
fitted on TRAIN DATES ONLY (< 2025-08-01) from this cache and frozen, exactly
as plan/rl2/features.fit_profile does, and it is written to plan/ou_out, never
into plan/rl2/.

Usage:
  python plan/ou_table.py --stage profile
  python plan/ou_table.py --stage build [--block 32] [--smoke 16]
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))
import ou_lib as L                                            # noqa: E402
import features as RF                                         # noqa: E402
import wn_table as WT                                         # noqa: E402

BLOCK = 32
PROFILE_F = L.OUT / "vol_profile.npy"
TABLE_F = L.OUT / "table.npz"


def raw_legs(o, printed, flat_min, flat_px):
    """(ent_px, ent_min, ex_px, ex_min, ok) per (decision, symbol, horizon).

    This is plan/rl2/features._targets with the TOLL TAKEN OUT: identical
    indexing, identical forced-flatten handling, identical `good` mask -- it
    just returns the two legs instead of folding a 10 bps ladder into them.
    Storing the legs is what lets plan/ou_rank.py re-price the same tickets
    under the measured cost model without rebuilding the table, and it gives
    a free identity gate: charging the flat ladder on these legs must
    reproduce `pnl_h*` (which wn_table.day_block computed the other way) to
    float32.  plan/ou_ident.py asserts exactly that.
    """
    S = o.shape[0]
    nxt = RF.next_printed(printed)
    M = RF.STEPS
    T, NH = len(M), len(RF.HORIZONS)
    ent_m = np.minimum(M + 1, RF.NMIN - 1)
    ent_ok = printed[:, ent_m].T
    ent_px = np.where(ent_ok, o[:, ent_m].T, np.nan)
    ex_px = np.zeros((T, S, NH), np.float64)
    ex_mn = np.zeros((T, S, NH), np.int32)
    ok = np.zeros((T, S, NH), bool)
    ar = np.arange(S)
    for hi, H in enumerate(RF.HORIZONS):
        want = np.clip(np.asarray(M, np.int64) + 1 + H, 0, RF.NMIN - 1)
        xi = nxt[ar[None, :], want[:, None]]
        past = (xi >= RF.NMIN) | (xi > flat_min[None, :]) | (H >= RF.NMIN)
        xi_c = np.clip(xi, 0, RF.NMIN - 1)
        ex_px[:, :, hi] = np.where(past, flat_px[None, :], o[ar[None, :], xi_c])
        ex_mn[:, :, hi] = np.where(past, flat_min[None, :], xi_c)
        ok[:, :, hi] = (ent_ok & np.isfinite(ent_px)
                        & np.isfinite(ex_px[:, :, hi])
                        & (ex_mn[:, :, hi] >= ent_m[:, None]))
    return ent_px, ent_m, ex_px, ex_mn, ok


# ------------------------------------------------------------ symbol cache
def load_symbol(sym):
    f = L.M1O / f"{sym}.npz"
    if not f.exists():
        return None
    try:
        z = np.load(f, allow_pickle=False)
        ds = [str(x) for x in z["dates"]]
        if not ds:
            return None
        return ds, z["o"], z["h"], z["l"], z["c"], z["v"]
    except Exception:
        return None


def fit_profile():
    """Cumulative share of the day's volume by minute, pooled over TRAIN dates
    only and frozen.  Same estimator as rl2.features.fit_profile."""
    pairs = json.loads((L.OUT / "minute_pairs.json").read_text())
    want = {}
    for s, d in pairs:
        if d < RF.PROFILE_END:
            want.setdefault(s, set()).add(d)
    tot = np.zeros(L.NMIN)
    n = 0
    for k, sym in enumerate(sorted(want)):
        rec = load_symbol(sym)
        if rec is None:
            continue
        ds, _o, _h, _l, _c, v = rec
        keep = np.array([i for i, d in enumerate(ds) if d in want[sym]], int)
        if not keep.size:
            continue
        vv = v[keep].astype(np.float64)
        s = vv.sum(axis=1)
        ok = s > 0
        if not ok.any():
            continue
        tot += (vv[ok] / s[ok, None]).sum(axis=0)
        n += int(ok.sum())
        if (k + 1) % 100 == 0:
            print(f"  profile [{k+1}/{len(want)}] {n:,} symbol-days",
                  flush=True)
    prof = np.maximum(np.cumsum(tot / max(n, 1)), 1e-6)
    np.save(PROFILE_F, prof)
    print(f"volume profile: {n:,} symbol-days < {RF.PROFILE_END}; cum share "
          f"09:30={prof[L.RTH_LO]:.3f} 16:00={prof[L.RTH_HI]:.3f}", flush=True)
    return prof


# ------------------------------------------------------------------ build
def build(block=BLOCK, smoke=0):
    prof = np.load(PROFILE_F)
    daily = RF.Daily()
    uni = L.universe()
    dates = [d for d in L.study_dates() if d in uni]
    if smoke:
        dates = dates[:smoke]
    all_td = L.trading_dates()
    prev_of = {d: all_td[i - 1] for i, d in enumerate(all_td) if i}
    sic2 = WT.load_sic2()
    earn = WT.load_earn()

    # how many rows will there be?  Pre-allocate; the table is ~3.8M x 32.
    members = {d: [r[0] for r in uni[d][:L.MINUTE_TOP]] for d in dates}
    NT = WT.NT
    cap = sum(len(v) for v in members.values()) * NT
    F = np.zeros((cap, len(WT.FEATURES)), np.float32)
    col = {k: np.zeros(cap, t) for k, t in
           (("date_i", np.int32), ("sym_i", np.int32), ("dec_i", np.int8),
            ("notional", np.float32), ("printed", bool),
            ("printed_m", bool), ("fill_px", np.float32))}
    for h in WT.HNAMES:
        col["pnl_" + h] = np.zeros(cap, np.float32)
        col["ok_" + h] = np.zeros(cap, bool)
        col["expx_" + h] = np.zeros(cap, np.float32)
        col["exmin_" + h] = np.zeros(cap, np.int16)
    syms_all, sidx = [], {}
    n = 0
    t0 = time.time()
    stats = {"dates": 0, "members": 0, "no_bars": 0, "S": []}

    for b0 in range(0, len(dates), block):
        db = dates[b0:b0 + block]
        need = sorted({s for d in db for s in members[d]})
        store = {}
        for sym in need:
            rec = load_symbol(sym)
            if rec is None:
                continue
            ds, o, h, l, c, v = rec
            di = {d: i for i, d in enumerate(ds)}
            keep = {d: di[d] for d in db if d in di}
            if keep:
                store[sym] = (keep, o, h, l, c, v)
        for date in db:
            cand = []
            pc_row = L.gd_day(prev_of[date])
            for sym in sorted(members[date]):
                rec = store.get(sym)
                stats["members"] += 1
                if rec is None or date not in rec[0]:
                    stats["no_bars"] += 1
                    continue
                i = rec[0][date]
                if not np.isfinite(rec[4][i]).any():
                    stats["no_bars"] += 1
                    continue
                p = (pc_row.get(sym) or {}).get("c")
                if not p:
                    stats["no_bars"] += 1
                    continue
                cand.append((sym, float(p), i, rec))
            if not cand:
                continue
            S = len(cand)
            stats["dates"] += 1
            stats["S"].append(S)
            bars = []
            for k in range(1, 6):
                a = np.empty((S, L.NMIN), np.float64)
                for j, (_s, _p, i, rec) in enumerate(cand):
                    a[j] = rec[k][i]
                bars.append(a)
            ss = [x[0] for x in cand]
            pc = np.array([x[1] for x in cand], np.float64)
            z = RF.compute_day(date, ss, pc, bars, prof, daily)
            blk = WT.day_block(date, z, sic2, earn, None, prev_of.get(date))
            for s in ss:
                if s not in sidx:
                    sidx[s] = len(syms_all)
                    syms_all.append(s)
            si = np.array([sidx[s] for s in ss], np.int32)
            m = NT * S
            di_ = dates.index(date)
            F[n:n + m] = blk["F"].reshape(m, -1)
            col["date_i"][n:n + m] = di_
            col["sym_i"][n:n + m] = np.tile(si, NT)
            col["dec_i"][n:n + m] = np.repeat(np.arange(NT, dtype=np.int8), S)
            col["notional"][n:n + m] = blk["notional"].reshape(-1)
            col["printed"][n:n + m] = blk["printed"].reshape(-1)
            col["printed_m"][n:n + m] = blk["printed_m"].reshape(-1)
            col["fill_px"][n:n + m] = blk["fill_px"].reshape(-1)
            _ep, _em, expx, exmin, _rok = raw_legs(
                bars[0], ~np.isnan(bars[3]), z["flat_min"],
                z["flat_px"].astype(np.float64))
            expx = expx[WT.DEC_T]
            exmin = exmin[WT.DEC_T]
            for hi, hn in enumerate(WT.HNAMES):
                col["pnl_" + hn][n:n + m] = blk["pnl"][:, :, hi].reshape(-1)
                col["ok_" + hn][n:n + m] = blk["ok"][:, :, hi].reshape(-1)
                col["expx_" + hn][n:n + m] = np.nan_to_num(
                    expx[:, :, hi]).reshape(-1)
                col["exmin_" + hn][n:n + m] = exmin[:, :, hi].reshape(-1)
            n += m
        el = time.time() - t0
        done = min(b0 + block, len(dates))
        print(f"  [{done}/{len(dates)}] {db[-1]} rows={n:,} {el:.0f}s eta "
              f"{el/done*(len(dates)-done)/60:.1f}m", flush=True)

    out = {k: v[:n] for k, v in col.items()}
    out["F"] = F[:n]
    out["dates"] = np.array(dates)
    out["syms"] = np.array(syms_all)
    out["features"] = np.array(WT.FEATURES)
    out["dec_et"] = np.array(WT.DEC_ET)
    out["horizons"] = np.array(WT.HNAMES)
    f = L.OUT / ("table_smoke.npz" if smoke else "table.npz")
    np.savez_compressed(f, **out)
    s = sorted(stats.pop("S"))
    rep = {"file": str(f), "rows": int(n), "dates": len(dates),
           "symbols": len(syms_all), "first": dates[0], "last": dates[-1],
           "members": stats["members"], "no_bars": stats["no_bars"],
           "S_min": s[0], "S_p50": s[len(s) // 2], "S_max": s[-1],
           "S_mean": round(sum(s) / len(s), 1),
           "eligible_rows_bar_m": int(out["printed_m"].sum()),
           "fillable_rows_bar_m1": int(out["printed"].sum()),
           "ok_h30": int(out["ok_h30"].sum()),
           "ok_h60": int(out["ok_h60"].sum()),
           "seconds": round(time.time() - t0, 1)}
    L.write("table_stats.json", rep)
    print(json.dumps(rep, indent=1), flush=True)


def main():
    stage = "build"
    if "--stage" in sys.argv:
        stage = sys.argv[sys.argv.index("--stage") + 1]
    blk = BLOCK
    if "--block" in sys.argv:
        blk = int(sys.argv[sys.argv.index("--block") + 1])
    smoke = 0
    if "--smoke" in sys.argv:
        smoke = int(sys.argv[sys.argv.index("--smoke") + 1])
    if stage == "profile":
        fit_profile()
    else:
        build(blk, smoke)


if __name__ == "__main__":
    main()
