"""SWING-REVERSION final stats for the headline loser-reversal rules
(full engine stats: 6/12 bps, win, max DD, ex-top-5, 30-seed universe
random control, present-day-halal line).  python plan/sr_final.py gd|long"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sr_run as R  # noqa: E402

F, U = R.F, R.U
rk = F["dv20"].where(U).rank(axis=1, ascending=False)
out = {"spy": R.spy_bh()}
print("SPY", {k: round(v["mo"]) for k, v in out["spy"].items()}, {k: round(v["maxdd"]) for k, v in out["spy"].items()})
for K in (300, 500):
    UK = U & (rk <= K)
    for H in (3, 5):
        for n in (5, 10):
            for hal in (False, True):
                key = f"LOSER5d|top{K}|H{H}|N{n}" + ("|HALAL-present-day" if hal else "")
                res, tr = R.run_one(key, F["ret5"].where(UK), None, H, UK, n, "open", halal_only=hal)
                out[key] = res
                print(key, " ".join(
                    f"{sp}: mo {res[sp]['c6']['mo']:+.0f} (12bps {res[sp]['c12']['mo']:+.0f}) n/mo {res[sp]['c6']['tr_mo']:.1f}"
                    f" $/tr {res[sp]['c6']['per_tr']:+.0f} win {res[sp]['c6']['win']:.2f} dd {res[sp]['c6']['maxdd']:+.0f}"
                    f" ex5/mo {res[sp]['c6']['ex5_mo']:+.0f} ctl {res[sp]['ctl_mo_mean']:+.0f} p{res[sp]['ctl_pct']:.0f} ;"
                    for sp in R.SPLITS) + f" ALL {res['ALL_mo']:+.0f} ex5 {res['ALL_ex5_mo']:+.0f} pct {res['ALL_ctl_pct']:.0f}", flush=True)
(R.OUT / f"sr_final_{R.DS}.json").write_text(json.dumps(out, indent=1))
print("DONE")
