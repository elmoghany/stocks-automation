"""R061 (rotation stack) under the user's half-profit compounding.

Same semantics as c35_compound.py, kept exactly for comparability:
  profit day:  account += 0.5 * pnl   (half banked, half reinvested)
  loss day:    account += pnl         (losses taken in full)
  deployment = min(account, $100,000) -- the user's hard daily ceiling
Scaling: daily P&L is assumed linear in the deployed cap (the
c35_budget_scaling study measured size-stability across slot tiers,
so pnl_scaled = pnl_flat * deployed/100k). Rotation tickets are 15% of
the cap, so proportional shrink matches the flat-$15k structure.

Captures R061's per-day flat P&L by replaying run_day (no results-file
writes -- safe alongside other rotation processes).
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location("rs", ROOT / "plan/rotation_sim.py")
rs = importlib.util.module_from_spec(_s)
sys.modules["rs"] = _s and rs
_s.loader.exec_module(rs)
px = rs.px

CFG = rs.CFGS["R061"]
CEIL = 100_000.0
START = 100_000.0

daily = []
for lab in ("year", "y2025"):
    byday = px.load_by_day(lab, 50, "novol")
    for n, (date, cs) in enumerate(sorted(byday.items()), 1):
        dfs = {}
        cands = rs.day_candidates(cs, date, dfs)
        if not cands:
            continue
        tr = rs.run_day(cands, date, CFG)
        if tr:
            daily.append({"date": date,
                          "pnl": round(sum(x["pnl"] for x in tr), 2)})
        if n % 60 == 0:
            print(f"  ..{lab} {n} days", flush=True)

daily.sort(key=lambda r: r["date"])
(ROOT / "data/massive/r061_daily.json").write_text(json.dumps(daily))
flat = sum(r["pnl"] for r in daily)
print(f"\nflat total (sanity vs $781,159): ${flat:+,.0f} "
      f"over {len(daily)} traded days")

acct, banked = START, 0.0
curve = []
for r in daily:
    dep = min(acct, CEIL)
    scale = dep / CEIL
    pnl = r["pnl"] * scale
    if pnl > 0:
        acct += 0.5 * pnl
        banked += 0.5 * pnl
    else:
        acct += pnl
    curve.append({"date": r["date"], "deployed": round(dep),
                  "pnl": round(pnl), "acct": round(acct),
                  "banked": round(banked)})
(ROOT / "data/massive/r061_compound_curve.json").write_text(
    json.dumps(curve))

print(f"\nR061 COMPOUNDED (start ${START:,.0f}, cap ${CEIL:,.0f}):")
print(f"  account end     ${acct:,.0f}")
print(f"  cash banked     ${banked:,.0f}")
print(f"  TOTAL WEALTH    ${acct + banked:,.0f}  "
      f"(= +${acct + banked - START:,.0f} on $100k)")
under = [c for c in curve if c["deployed"] < CEIL]
print(f"  days below full deployment: {len(under)}/{len(curve)}")
if under:
    print(f"  smallest deployable day: "
          f"${min(c['deployed'] for c in curve):,.0f}")
mdd, peak = 0.0, -1e18
for c in curve:
    w = c["acct"] + c["banked"]
    peak = max(peak, w)
    mdd = min(mdd, w - peak)
print(f"  max drawdown on total wealth: ${mdd:,.0f}")
