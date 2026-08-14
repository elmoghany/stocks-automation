"""Cache TODAY'S halal verdict (day-trading.py::halal_check, the
2026-08-13 screen: entertainment hard-failed, 5%-proportion rule, retail
allowed) for every symbol in the replay pool.

Written to data/massive/replay0813_today_screen.json so the replay can be
re-run with the CURRENT gate in addition to the champion's point-in-time
one. Resumable.

Usage: python plan/replay_0810_today_screen.py
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

POOL_F = ROOT / "data/massive/gappers_novol_replay0813.json"
OUT_F = ROOT / "data/massive/replay0813_today_screen.json"


def main():
    syms = sorted({c["symbol"] for c in json.loads(POOL_F.read_text())})
    out = json.loads(OUT_F.read_text()) if OUT_F.exists() else {}
    todo = [s for s in syms if s not in out]
    print(f"{len(syms)} symbols, {len(todo)} to screen", flush=True)
    for i, s in enumerate(todo, 1):
        try:
            r = ps.halal_check(s)
            out[s] = {"halal": bool(r.get("halal")),
                      "verdict": r.get("verdict"),
                      "reason": r.get("fail_reason", ""),
                      "source": r.get("source")}
        except Exception as e:
            out[s] = {"halal": False, "verdict": "ERROR", "reason": str(e)[:120]}
        if i % 25 == 0 or i == len(todo):
            OUT_F.write_text(json.dumps(out, indent=1))
            print(f"  [{i}/{len(todo)}]", flush=True)
    OUT_F.write_text(json.dumps(out, indent=1))
    npass = sum(1 for v in out.values() if v["halal"])
    print(f"done: {npass}/{len(out)} pass today's screen", flush=True)


if __name__ == "__main__":
    main()
