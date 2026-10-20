"""PAPER-VS-BT: per-day P&L distribution of the R4 LIVE-policy backtest
(the r4_live expectation: p3_r4_live.live_sim, PINNED 0.6%, LEGACY-9 spread
proxy, $10k, 15 bps/side) over the 444 in-sample days + 22 Aug-2026 OOS
days, to place an 11-day paper result inside it (all 11-day windows of
consecutive backtest days). Writes data/pvb/r4_live_daily.json.

    python plan/pvb_dist.py [--coil-rth]

--coil-rth: rank on last / RTH-only high (what the live scanner's Coil
column measures, plan/pvb_coilcheck.py) instead of the premarket-inclusive
session high the expectation used.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as CL                                         # noqa: E402
import cp_run as CR                                         # noqa: E402
import p3_lib as P                                          # noqa: E402
import p3_parity_r4 as T                                    # noqa: E402
import p3_r4 as R                                           # noqa: E402
import p3_r4_live as V                                      # noqa: E402

RTH = "--coil-rth" in sys.argv     # scanner-style coil (RTH-only high)
out = {}
for lab, dates in (("insample", CR.dates()), ("oos", CR.dates(oos=True))):
    rows, allg = [], []
    for n, d in enumerate(dates):
        day = T.FullDay(d).day_at(CL.NMIN)
        Fd = R.fd_from_bars(day)
        if RTH:
            rh = day.runhigh_from(CL.M_OPEN)[:, R.GRID]
            with np.errstate(divide="ignore", invalid="ignore"):
                Fd["coil"] = np.where(rh > 0, day.last[:, R.GRID] / rh,
                                      np.nan).astype(np.float32)
        legs = V.live_sim(day, Fd, d, V.proxy_check("spread"), pin_thr=0.006)
        allg.extend(V.net(x) for x in legs if x.get("gross") is not None)
        rows.append(dict(date=d, n=len(legs),
                         net15=round(sum(V.net(x) for x in legs
                                         if x.get("gross") is not None), 2)))
        if n % 100 == 0:
            print(lab, n, d, flush=True)
    out[lab] = rows
    out[lab + "_per_trade"] = round(float(np.mean(allg)), 2) if allg else None
    out[lab + "_trades"] = len(allg)
allr = out["insample"] + out["oos"]
v = np.array([r["net15"] for r in allr])
nt = np.array([r["n"] for r in allr])
w = np.array([v[i:i + 11].sum() for i in range(len(v) - 10)])
wn = np.array([nt[i:i + 11].sum() for i in range(len(v) - 10)])
out["summary"] = dict(days=len(v), per_day_mean=round(float(v.mean()), 2),
                      per_day_sd=round(float(v.std()), 2),
                      win11_mean=round(float(w.mean()), 2),
                      win11_p05=round(float(np.percentile(w, 5)), 2),
                      win11_p10=round(float(np.percentile(w, 10)), 2),
                      win11_p25=round(float(np.percentile(w, 25)), 2),
                      win11_p50=round(float(np.percentile(w, 50)), 2),
                      win11_p90=round(float(np.percentile(w, 90)), 2),
                      trades11_mean=round(float(wn.mean()), 2))
for x in (-1698.0, -1700.0, -2434.0):
    out["summary"][f"pct_windows_at_or_below_{int(x)}"] = round(
        float((w <= x).mean() * 100), 2)
print(out["summary"])
(P.DATA / "pvb" / ("r4_live_daily_rthcoil.json" if RTH else
                   "r4_live_daily.json")).write_text(json.dumps(out, indent=1))
