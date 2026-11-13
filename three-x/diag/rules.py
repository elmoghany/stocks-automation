"""Re-creates the position series (in or out at each close) of the AMD rules tried so far, for two windows, reusing the original rule code.

pos[i] = 1 means decided at the close of day i to hold AMD during day i+1 (fill at the next open). All series are causal: a signal on day i uses
data up to the close of day i. (Report dates are used in advance, as in the original studies; AMD announces them weeks ahead.)
Windows: recent = 2023-08-01 on (rules run from that day), early = 2013-01-02 to 2023-07-31 (data after that cut is not given to the rule).
Read-only use of amd_paper.positions and amd_surge_search; nothing is written outside diag/.
"""
import contextlib
import io

import numpy as np
import pandas as pd

from common import *

with contextlib.redirect_stdout(io.StringIO()):
    import amd_paper as AP
    import amd_surge_search as S
rules = AP.rules

SELL = {"sell_s": 90, "sell_r": 60, "sell_dn": 0.08, "min_days": 15}

ZONE_BEST = {"buy_s": 25, "buy_r": 40, "depth": 0, "buy_up": 0, "sell_s": 90, "sell_r": 60, "reach": 0, "sell_dn": 0.08, "min_days": 15, "stop": 0}
ZONE_TABLE = {"buy_s": 25, "buy_r": 40, "depth": 0.25, "buy_up": 0.05, "sell_s": 80, "sell_r": 65, "reach": 0, "sell_dn": 0.08, "min_days": 15, "stop": 0.25}

NAMES = {
    "day13": "Paper: day 13 + AMD above 200d",
    "month_end": "Paper: month-end after report",
    "zone_qqq": "Paper: zone + QQQ below 100d",
    "second_low": "Paper: second low",
    "day12_sell7": "Paper: buy day 12, sell 7 before",
    "zone_plain": "Zone: plain (best money)",
    "zone_table": "Zone: closest to table",
    "rebound": "Surge: rebound 8% off post-report low",
    "breakout": "Surge: breakout above 20d high",
    "thrust": "Surge: +15% in 5 days",
    "trend": "Surge: in-AMD-by-default trend",
    "day13_sell15": "Earnings: day 13, sell 15 before",
    "weekly_earn": "Earnings: weekly, out 2 Fridays before",
}

_cache = {}


def _frame_for(window):
    f = load_amd()
    W = windows(f.index)
    lo, hi = W[window]
    return f, lo, hi


def positions(window):
    """dict name -> pos array over the full AMD index (zeros outside the window)."""
    if window in _cache:
        return _cache[window]
    f, lo, hi = _frame_for(window)
    n = len(f)
    qqq = load_etf("QQQ")
    reports = [str(d.date()) for d in report_dates()]
    out = {}
    # five paper rules: give the rule only data up to the end of the window
    cut = f.iloc[:hi]
    AP.WARM = str(f.index[lo].date())
    with contextlib.redirect_stdout(io.StringIO()):
        paper = AP.positions(cut, qqq, [d for d in reports if d <= str(cut.index[-1].date())], None, str(f.index[lo].date()))
    for k in ("day13", "month_end", "zone_qqq", "second_low", "day12_sell7"):
        p = np.zeros(n)
        p[:hi] = paper[k][:hi]
        out[k] = p
    inputs = rules._zone_inputs(f)
    out["zone_plain"] = rules._zone_loop(*inputs, ZONE_BEST, lo)
    out["zone_table"] = rules._zone_loop(*inputs, ZONE_TABLE, lo)
    # surge rules, exactly as amd_surge_search ran them
    xs = {
        "rebound": (S.rebound(10, 0.0, 0.08), {"trail": None, "cap": None, "pre": True}),
        "breakout": (S.breakout(20, 20) & S.above200, {"trail": 0.20, "cap": 40, "pre": True}),
        "thrust": (S.thrust(5, 0.15), {"trail": None, "cap": 60, "pre": False}),
        "trend": (S.trend(20), {"trail": 0.15, "cap": 40, "pre": True}),
    }
    for k, (sig, x) in xs.items():
        _, pos = S.run(sig, x, lo, hi)
        out[k] = pos
    # earnings-timed rules via the original calendar rule code
    base = {"family": "amdcycle", "reports": [d for d in reports if d <= str(cut.index[-1].date())], "trade_from": str(f.index[lo].date())}
    out["day13_sell15"] = np.r_[rules._amdcycle(cut, {**base, "rule": "quarter", "cadence": "D", "buy_on": "day", "day": 13, "before_next": 15}).values, np.zeros(n - hi)]
    out["weekly_earn"] = np.r_[rules._amdcycle(cut, {**base, "rule": "earn", "cadence": "W", "k": 1, "w": 1}).values, np.zeros(n - hi)]
    for k in out:
        out[k] = np.asarray(out[k], dtype=float)
        out[k][:max(lo - 1, 0)] = 0.0
        out[k][hi - 1:] = 0.0 if hi < n else out[k][hi - 1:]
    _cache[window] = out
    return out


if __name__ == "__main__":
    f = load_amd()
    o, c = f.open.values, f.close.values
    W = windows(f.index)
    for w in ("recent", "early"):
        lo, hi = W[w]
        H = hold_mult(o, c, lo, hi)
        print(f"\n{w}: held {H:.2f}x")
        P = positions(w)
        for k, nm in NAMES.items():
            p = P[k]
            m = mult(p, o, c, lo, hi)
            tr = trades_from_pos(p, lo, hi)
            print(f"  {nm:<42} {m:8.2f}x  ({m / H:5.2f} of held)  trades {len(tr):3d}  in market {p[lo - 1:hi - 1].mean():.0%}")
