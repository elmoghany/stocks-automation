"""LEGACY-2: coil rules inside the CHAMPION-REPLAY sequential engine.

Pure re-use of plan/cp_sim.py (no edits). A coil FLOOR is applied by
masking the eligibility grid with the causal coil at the same grid
minute (both are dated <= t), so the engine never sees a name below the
floor. Everything else is the R4 frame: rank=coil, no stop, trail +
bearish exit, rotation, 15:00 flatten, RS_DEFER fills, gap-through
sells. Reports gross and net at 6/15 bps per side, per $10k notional.

    python plan/lm2_coil_engine.py  -> plan/lm2_out/engine.json
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402
import cp_sim as S                                          # noqa: E402

OUT = Path(__file__).resolve().parent / "lm2_out"
Y1_END, OOS = "2025-08-01", "2026-08-01"


def jobs():
    R4 = dict(rank="coil", stop_pct=None)
    J = {
        "R4": (R4, None, None),
        "R4_rankNONE": (dict(rank="none", stop_pct=None), None, None),
        "R4_floor95": (R4, 0.95, None),
        "R4_floor98": (R4, 0.98, None),
        "R4_floor995": (R4, 0.995, None),
        "NONE_floor98": (dict(rank="none", stop_pct=None), 0.98, None),
        "R4_floor98_t1000": (dict(R4, t_start=L.mgrid(10, 0)), 0.98, None),
        "R4_floor98_gain40": (R4, 0.98, 0.40),
        "R4_gain40": (R4, None, 0.40),
    }
    for k in range(10):
        J[f"RNDf98_{k}"] = (dict(rank="none", rand=True, seed=k,
                                 stop_pct=None), 0.98, None)
    return J


def main():
    J = jobs()
    out = {k: [] for k in J}
    t0 = time.time()
    ds = F.dates()
    for n, date in enumerate(ds):
        Fd0 = F.load(date)
        day = L.load_day(date)
        if Fd0 is None or day is None:
            continue
        for key, (over, floor, gmax) in J.items():
            Fd = dict(Fd0)
            el = Fd0["elig_last"].copy()
            if floor is not None:
                el &= np.nan_to_num(Fd0["coil"], nan=0.0) >= floor
            if gmax is not None:
                el &= np.nan_to_num(Fd0["gain_now"], nan=9.0) <= gmax
            Fd["elig_last"] = el
            cfg = S.default_cfg(**over)
            for leg in S.run_day(day, Fd, cfg, None):
                out[key].append(dict(date=date, sym=leg["sym"],
                                     em=leg["entry_min"], xm=leg["exit_min"],
                                     entry=leg["entry"], exit=leg["exit"],
                                     sh=leg["shares"], gross=leg["gross"],
                                     reason=leg["reason"]))
        if n % 50 == 0:
            print(n, date, f"{time.time() - t0:.0f}s", flush=True)
    (OUT / "engine.json").write_text(json.dumps(out, default=float))
    summarize(out)


def summarize(out):
    print("\n| config | yr | tkts | gross $/tkt | gross bps | net@15 $/10k | net@6 $/10k | $/mo net@15 (10k) | months+ |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for k, legs in out.items():
        if k.startswith("RNDf98_") and k != "RNDf98_0":
            continue
        for yr in ["Y1", "Y2", "OOS", "ALL444"]:
            sel = [l for l in legs if
                   (yr == "Y1" and l["date"] < Y1_END) or
                   (yr == "Y2" and Y1_END <= l["date"] < OOS) or
                   (yr == "OOS" and l["date"] >= OOS) or
                   (yr == "ALL444" and l["date"] < OOS)]
            if not sel:
                continue
            row(k, yr, sel)
    rnd = [k for k in out if k.startswith("RNDf98_")]
    for yr in ["Y1", "Y2", "OOS", "ALL444"]:
        vals = []
        for k in rnd:
            sel = [l for l in out[k] if
                   (yr == "Y1" and l["date"] < Y1_END) or
                   (yr == "Y2" and Y1_END <= l["date"] < OOS) or
                   (yr == "OOS" and l["date"] >= OOS) or
                   (yr == "ALL444" and l["date"] < OOS)]
            r = np.array([l["exit"] / l["entry"] - 1 for l in sel])
            vals.append(r.mean() * 1e4)
        print(f"| RNDf98 x{len(rnd)} mean bps | {yr} | | | {np.mean(vals):+.1f} +- {np.std(vals):.1f} | | | | |")


def row(k, yr, sel):
    r = np.array([l["exit"] / l["entry"] - 1 for l in sel])
    g = np.array([l["gross"] for l in sel])
    months = {}
    for l, x in zip(sel, r):
        months.setdefault(l["date"][:7], 0.0)
        months[l["date"][:7]] += x * 1e4 - 30
    net15 = r.mean() * 1e4 - 30
    net6 = r.mean() * 1e4 - 12
    print(f"| {k} | {yr} | {len(sel)} | {g.mean():+.1f} | {r.mean()*1e4:+.1f} "
          f"| {net15:+.1f} | {net6:+.1f} | {np.mean(list(months.values())):+,.0f} "
          f"| {sum(v > 0 for v in months.values())}/{len(months)} |")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--summ":
        summarize(json.loads((OUT / "engine.json").read_text()))
    else:
        main()
