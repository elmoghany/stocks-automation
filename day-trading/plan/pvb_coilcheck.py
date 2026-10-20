"""PAPER-VS-BT: which "high" does the live R4 scanner's HighAll/Coil use?
For every saved snapshot row with bars, at grid t: compare the scan high
with the bar session high incl. premarket (04:00..t) and the RTH-only high
(09:30..t), on the rows where they differ (premarket high above the RTH
high by > 0.5%). Also counts scan coil > 1.0 rows.

    python plan/pvb_coilcheck.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as CL                                         # noqa: E402
import pvb_r4 as B                                          # noqa: E402
import p3_r4 as R                                           # noqa: E402

uni = json.loads((B.PV / "r4_universe.json").read_text())
out = {}
for d in B.DAYS:
    day, syms, have = B.load_day(d, B.PV / "rhx", uni)
    idx = {s: i for i, s in enumerate(syms)}
    rth = day.runhigh_from(CL.M_OPEN)
    sn = [json.loads(x) for x in R.snaps_path(d).read_text().splitlines()
          if x.strip()]
    n_disc = m_rth = m_all = gt1 = rows = top8_affected = 0
    for x in sn:
        t = int(x["t"])
        for s, r in x["rows"].items():
            rows += 1
            if r.get("coil") and r["coil"] > 1.0001:
                gt1 += 1
            i = idx.get(s)
            hi = r.get("high")
            if i is None or not hi:
                continue
            a, b = day.runhigh[i, t], rth[i, t]
            if not (np.isfinite(a) and np.isfinite(b)) or a <= b * 1.005:
                continue
            n_disc += 1
            if abs(hi / b - 1) < abs(hi / a - 1):
                m_rth += 1
            else:
                m_all += 1
    out[d] = dict(rows=rows, discriminating=n_disc, scan_high_is_rth=m_rth,
                  scan_high_is_all_session=m_all, coil_gt_1=gt1)
    print(d, out[d], flush=True)
(B.PV / "coilcheck.json").write_text(json.dumps(out, indent=1))
