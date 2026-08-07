"""C35 COMPOUNDING replay (user 2026-08-07): start with a $100,000
account, re-invest HALF of each day's profit into the next day, and
take losses in FULL.

  profit day:  account += 0.5 * pnl      (half banked, half reinvested)
  loss day:    account += pnl            (losses hit the account fully)

The account IS the daily deployment cap (cash, T+1), and the ticket
sizes scale with it, preserving C35's shape:
  daily_deploy_cap = account
  first ticket     = 25% of account   (=$25k at $100k)
  later tickets    = 15% of account   (=$15k at $100k)
The 20%-of-10-min-volume rule still caps every fill, so growth
self-limits as tickets outgrow the tape -- that liquidity ceiling, not
the arithmetic, is what bounds this.

Runs the two backtest years chronologically (Oct24-Jul25 then
Aug25-Jul26) carrying the account across the boundary. Writes
data/massive/c35_compound_capped_curve.json.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plan"))
_spec = importlib.util.spec_from_file_location(
    "penny_x100", ROOT / "plan" / "penny_x100.py")
x = importlib.util.module_from_spec(_spec)
sys.modules["penny_x100"] = x
_spec.loader.exec_module(x)

START = 100_000.0
# HARD DEPLOYMENT CEILING (user 2026-08-07: "cap at 100k"): however big
# the account grows, never put more than this to work in a single day --
# profits above it simply accumulate as idle cash. Losses still bite: if
# the account falls BELOW the ceiling, that smaller number is what can be
# deployed, so tickets shrink until profits rebuild it.
DEPLOY_CEILING = 100_000.0
FIRST_FRAC, TICKET_FRAC = 0.25, 0.15
STATE = {"acct": START, "curve": []}
_orig = x.sim_window


def wrapper(w, c, spec, sub=None):
    a = STATE["acct"]
    dep = min(DEPLOY_CEILING, a)          # never deploy above the ceiling
    spec.setdefault("sim", {})
    spec["sim"]["budget"] = dep * TICKET_FRAC
    spec["sim"]["daily_deploy_cap"] = dep
    spec["sim"]["entry_ticket_schedule"] = (1, dep * FIRST_FRAC)
    tr = _orig(w, c, spec, sub)
    pnl = sum(t["pnl"] for t in tr)
    # half of profits reinvested; losses taken in full
    STATE["acct"] = a + (0.5 * pnl if pnl > 0 else pnl)
    if len(w):
        STATE["curve"].append(dict(date=str(w.index[0].date()),
                                   acct_before=round(a),
                                   deployed_cap=round(dep),
                                   pnl=round(pnl, 2),
                                   acct_after=round(STATE["acct"])))
    return tr


x.sim_window = wrapper

SPEC = dict(x.BYID["S095"])          # C35

for label in ("y2025", "year"):      # chronological
    start = STATE["acct"]
    out = x.run_experiment(dict(SPEC), label)
    print(f"{label}: raw P&L ${out['total']:+,} | account "
          f"${start:,.0f} -> ${STATE['acct']:,.0f}", flush=True)

curve = STATE["curve"]
(ROOT / "data/massive/c35_compound_capped_curve.json").write_text(json.dumps(curve))
banked = sum(0.5 * r["pnl"] for r in curve if r["pnl"] > 0)
peak = mx = START
dd = 0.0
for r in curve:
    mx = max(mx, r["acct_after"])
    dd = min(dd, (r["acct_after"] - mx) / mx)
neg = [r for r in curve if r["pnl"] < 0]
print(f"\nC35 COMPOUNDED from ${START:,.0f} over {len(curve)} traded days")
print(f"  final account   ${STATE['acct']:,.0f}")
print(f"  cash banked     ${banked:,.0f}  (the half NOT reinvested)")
print(f"  total wealth    ${STATE['acct'] + banked:,.0f}")
print(f"  max account drawdown {100*dd:.1f}%")
_under = [r for r in curve if r["deployed_cap"] < DEPLOY_CEILING]
print(f"  days forced to trade BELOW the ${DEPLOY_CEILING:,.0f} ceiling: "
      f"{len(_under)}/{len(curve)}")
print(f"  smallest deployable day: ${min(r['deployed_cap'] for r in curve):,.0f}")
print(f"  losing days {len(neg)}/{len(curve)} "
      f"({100*len(neg)/len(curve):.0f}%), worst ${min(r['pnl'] for r in curve):+,.0f}")
