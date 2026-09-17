"""OPEN-UNIVERSE (2026-09-17) step 1: build the causal open universe.

Per date D (nothing about D's own session may enter):
  (a) Polygon `type` in {CS, ADRC} and SIC not a closed-end-fund code --
      i.e. an operating company's ordinary equity, of ANY sector.  This is
      the only place the halal screen used to sit, and the mandate removes
      it; a type gate is put in its place so the universe is companies and
      not ETFs / funds / warrants / units.
  (b) over the PRIOR 60 sessions (>= 40 present) median dollar volume
      >= $5M and median close >= $5.

Writes
  plan/ou_out/universe.json.gz   {date: [[sym, mdv, mpx], ...]}  mdv DESC
  plan/ou_out/universe_stats.json   the funnel, per date and in aggregate
  plan/ou_out/minute_pairs.json  the (sym, date) list for the top-600 subset
  plan/ou_out/screen_union.json  every symbol that clears (b), for ou_meta

Usage:  python plan/ou_universe.py [--stage union|build]
"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ou_lib as L                                            # noqa: E402


def matrices():
    dates = L.trading_dates()
    syms, sidx, A = L.gd_matrices(dates)
    return dates, syms, A["c"], A["c"] * A["v"]


def stage_union():
    """Rule (b) only -- the list ou_meta.py needs a `type` for."""
    dates, syms, close, dvol = matrices()
    study = L.study_dates()
    di = {d: i for i, d in enumerate(dates)}
    union = set()
    for d in study:
        i = di[d]
        lo = max(0, i - L.LOOKBACK)
        w_dv, w_px = dvol[lo:i], close[lo:i]
        n = np.sum(~np.isnan(w_dv), axis=0)
        with np.errstate(all="ignore"):
            mdv = np.nanmedian(w_dv, axis=0)
            mpx = np.nanmedian(w_px, axis=0)
        ok = (n >= L.MIN_OBS) & (mdv >= L.MIN_MDV) & (mpx >= L.MIN_MPX)
        union.update(syms[j] for j in np.flatnonzero(ok))
    L.OUT.mkdir(parents=True, exist_ok=True)
    (L.OUT / "screen_union.json").write_text(json.dumps(sorted(union)))
    print(f"screen union: {len(union):,} symbols", flush=True)


def stage_build():
    dates, syms, close, dvol = matrices()
    study = L.study_dates()
    di = {d: i for i, d in enumerate(dates)}
    M = L.meta()
    keep_mask = np.array([L.is_operating(s) for s in syms])
    tcnt = Counter((M.get(s) or {}).get("type") for s in syms)
    print(f"gd: {len(dates)} dates x {len(syms):,} symbols; "
          f"operating-equity symbols {int(keep_mask.sum()):,}", flush=True)

    uni, stats = {}, {}
    minute_pairs = []
    no_type = Counter()
    for d in study:
        i = di[d]
        lo = max(0, i - L.LOOKBACK)
        w_dv, w_px = dvol[lo:i], close[lo:i]
        n = np.sum(~np.isnan(w_dv), axis=0)
        with np.errstate(all="ignore"):
            mdv = np.nanmedian(w_dv, axis=0)
            mpx = np.nanmedian(w_px, axis=0)
        liq = (n >= L.MIN_OBS) & (mdv >= L.MIN_MDV) & (mpx >= L.MIN_MPX)
        ok = liq & keep_mask
        idx = np.flatnonzero(ok)
        order = idx[np.argsort(-mdv[idx])]
        rows = [[syms[j], round(float(mdv[j]), 1), round(float(mpx[j]), 4)]
                for j in order]
        uni[d] = rows
        for s, _, _ in rows[:L.MINUTE_TOP]:
            minute_pairs.append([s, d])
        dropped = np.flatnonzero(liq & ~keep_mask)
        for j in dropped:
            no_type[(M.get(syms[j]) or {}).get("type") or "NO-META"] += 1
        stats[d] = {"liquid": int(liq.sum()), "operating": len(rows),
                    "minute": min(len(rows), L.MINUTE_TOP)}

    with gzip.open(L.OUT / "universe.json.gz", "wt") as f:
        json.dump(uni, f)
    (L.OUT / "minute_pairs.json").write_text(json.dumps(minute_pairs))
    szs = np.array([v["operating"] for v in stats.values()])
    liqs = np.array([v["liquid"] for v in stats.values()])
    union = sorted({s for v in uni.values() for s, _, _ in v})
    munion = sorted({s for s, _ in minute_pairs})
    agg = {
        "rule": {"start": L.START, "end": L.END, "lookback": L.LOOKBACK,
                 "min_obs": L.MIN_OBS, "min_mdv": L.MIN_MDV,
                 "min_mpx": L.MIN_MPX, "keep_types": sorted(L.KEEP_TYPES),
                 "fund_sics": sorted(L.FUND_SICS),
                 "minute_top": L.MINUTE_TOP},
        "dates": len(study),
        "names_per_day": {"min": int(szs.min()), "max": int(szs.max()),
                          "mean": round(float(szs.mean()), 1)},
        "liquid_before_type": {"min": int(liqs.min()), "max": int(liqs.max()),
                               "mean": round(float(liqs.mean()), 1)},
        "symbol_days": int(szs.sum()),
        "union_symbols": len(union),
        "minute_symbol_days": len(minute_pairs),
        "minute_union_symbols": len(munion),
        "dropped_by_type": dict(no_type.most_common()),
        "type_counts_all_gd": {str(k): v for k, v in tcnt.most_common(15)},
        "per_date": stats,
    }
    L.write("universe_stats.json", agg)
    print(f"open universe: {len(study)} dates, per-day "
          f"{szs.min()}..{szs.max()} (mean {szs.mean():.0f}); liquid before "
          f"the type gate mean {liqs.mean():.0f}", flush=True)
    print(f"  symbol-days {int(szs.sum()):,}, union {len(union):,} symbols",
          flush=True)
    print(f"  minute subset (top {L.MINUTE_TOP}): "
          f"{len(minute_pairs):,} symbol-days, {len(munion):,} symbols",
          flush=True)
    print(f"  dropped by the type gate (symbol-days): "
          f"{dict(no_type.most_common(10))}", flush=True)


def main():
    stage = "build"
    if "--stage" in sys.argv:
        stage = sys.argv[sys.argv.index("--stage") + 1]
    if stage == "union":
        stage_union()
    else:
        stage_build()


if __name__ == "__main__":
    main()
