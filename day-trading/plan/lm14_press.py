"""LEGACY-14: the old 'entry pressure as a SIZING input' lead
(CONFIGS-TESTED: p_entry >= +0.30 averaged $751/position vs $213-263,
never tested as sizing). Re-run R4 at $10k and tag each leg with the
causal pressure at entry: pressure30 on the decision grid minute and
10-bar signed-volume pressure through the bar BEFORE the fill bar."""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_run as R                                          # noqa: E402
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402

S = R.S
S.TICKETS = [10_000.0] * 7
_orig = S._try_ticket


def _tagged(day, Fd, i, t, gi, budget, cfg, cost):
    leg = _orig(day, Fd, i, t, gi, budget, cfg, cost)
    if leg is not None:
        leg["p30"] = float(Fd["pressure30"][i, gi])
        p = S._pressure_at(day, i, leg["entry_min"] - 1, 10)
        leg["p10"] = np.nan if p is None else p
        leg["gain"] = float(Fd["gain_now"][i, gi])
    return leg


S._try_ticket = _tagged
cfg = S.default_cfg(rank="coil", stop_pct=None)
legs = S.run(R.dates(), cfg)
Y2 = "2025-08-01"


def net(x, b=15):
    return x["gross"] - b / 1e4 * (x["entry"] + x["exit"]) * x["shares"]


print("legs", len(legs))
for key, edges in [("p10", [-9, -0.3, 0.0, 0.3, 9]), ("p30", [-9, -0.3, 0.0, 0.3, 9]),
                   ("gain", [-9, 0.15, 0.30, 0.60, 99])]:
    print(f"\n| {key} bucket | n | mean ret | $/tkt 15bps | Y1 / Y2 $/tkt | ex-top3 $/tkt |\n|---|---:|---:|---:|---:|---:|")
    for lo, hi in zip(edges, edges[1:]):
        xs = [x for x in legs if np.isfinite(x[key]) and lo <= x[key] < hi]
        if not xs:
            continue
        v = [net(x) for x in xs]
        y1 = [net(x) for x in xs if x["date"] < Y2]
        y2 = [net(x) for x in xs if x["date"] >= Y2]
        r = np.mean([x["exit"] / x["entry"] - 1 for x in xs]) * 100
        ex3 = sum(sorted(v, reverse=True)[3:]) / max(len(v) - 3, 1)
        print(f"| [{lo},{hi}) | {len(xs)} | {r:+.2f}% | {np.mean(v):+.1f} | "
              f"{np.mean(y1) if y1 else 0:+.1f} / {np.mean(y2) if y2 else 0:+.1f} | {ex3:+.1f} |")
    xs = [x for x in legs if not np.isfinite(x[key])]
    if xs:
        print(f"| nan | {len(xs)} | | {np.mean([net(x) for x in xs]):+.1f} | | |")
