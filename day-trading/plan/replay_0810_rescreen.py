"""Re-screen every name the replay's backtest PICKED against TODAY'S
halal rules (day-trading.py::halal_check, i.e. the 2026-08-13 screen with
entertainment hard-failed and the 5%-proportion rule), and restate the
backtest P&L with the now-haram names' profits removed.

The backtest gate is axb.halal_pt, which is point-in-time and reads
industry text from caches that pre-date today's keyword fixes. So a
replay can legitimately "earn" money on a name we would now refuse --
exactly what happened live with ANGX. This script makes that visible
instead of banking it.

Usage: python plan/replay_0810_rescreen.py [trades.json]
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

_spec = importlib.util.spec_from_file_location("ps", ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)


def main():
    f = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        ROOT / "data/massive/replay0813_trades.json"
    d = json.loads(f.read_text())
    names = {}
    for date, v in d["days"].items():
        for t in v["trades"]:
            names.setdefault(t["symbol"], []).append((date, t["pnl"]))
    print(f"{len(names)} distinct names picked by the backtest\n")
    haram_pnl = 0.0
    rows = []
    for sym in sorted(names):
        try:
            r = ps.halal_check(sym)
        except Exception as e:
            r = {"halal": None, "verdict": "ERROR", "fail_reason": str(e)}
        ok = r.get("halal")
        pnl = sum(p for _, p in names[sym])
        if ok is not True:
            haram_pnl += pnl
        why = f"{r.get('verdict','')} {r.get('fail_reason','')}".strip()
        rows.append((sym, ok, why, pnl, [dt for dt, _ in names[sym]]))
        print(f"  {sym:<6} halal={str(ok):<5} ${pnl:+9,.2f}  {why[:78]}")
    print(f"\nP&L attributable to names TODAY'S screen would refuse: "
          f"${haram_pnl:+,.2f}")
    print(f"backtest total ${d['backtest_total']:+,.2f} -> "
          f"halal-adjusted ${d['backtest_total'] - haram_pnl:+,.2f}")
    out = f.with_name(f.stem + "_rescreen.json")
    out.write_text(json.dumps(
        {"rows": [{"sym": s, "halal": h, "reason": str(rn), "pnl": p,
                   "dates": dts} for s, h, rn, p, dts in rows],
         "haram_pnl": round(haram_pnl, 2),
         "backtest_total": d["backtest_total"],
         "halal_adjusted_total": round(d["backtest_total"] - haram_pnl, 2)},
        indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
