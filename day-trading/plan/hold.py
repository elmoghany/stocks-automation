"""One-call HOLD cycle: ingest a spilled get_equity_historicals dump for the
bench symbols (feeds the watcher's CSVs), show the newest bars of the open
name(s), tail the watcher log for EXIT-* / CB-WOULD-FIRE / ladder events,
heartbeat.
Usage:  python plan/hold.py DUMP.txt SYM [SYM ...]   (SYMs = the request set)
Written 2026-09-02 (Day 21). The position watch owns the 1-minute cadence;
this only feeds it and reads what it says. It never exits by hand.
"""
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DIR = Path(__file__).resolve().parent.parent
ET = ZoneInfo("America/New_York")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=DIR)
    return (r.stdout or "") + (r.stderr or "")


def main():
    dump, *syms = sys.argv[1:]
    date = datetime.now(ET).strftime("%Y-%m-%d")
    out = run([sys.executable, "plan/rh_bars_ingest.py", dump, date] + syms)
    bad = [l for l in out.splitlines() if "ERROR" in l or "MISMATCH" in l]
    print("\n".join(bad) if bad else "ingest OK")
    # open positions
    for sp in sorted((DIR / "data" / "paper").glob("position_*.json")):
        st = json.load(open(sp))
        sym = st.get("sym") or sp.stem.split("_", 1)[1]
        p = DIR / "data" / "rh_bars" / f"{sym}_{date}.csv"
        rows = list(csv.DictReader(open(p))) if p.exists() else []
        for r in rows[-2:]:
            print(f"  {sym} {r['begins_at'][11:16]}Z o={r['open']} h={r['high']} "
                  f"l={r['low']} c={r['close']} v={r['volume']}")
    log = DIR / "data" / "paper" / f"watch_{date}.log"
    if log.exists():
        lines = log.read_text(errors="replace").splitlines()
        ev = [l for l in lines if any(k in l for k in
              ("EXIT", "FLATTEN", "CB-WOULD-FIRE", "LADDER", "RUNG", "SCALE",
               "BANK", "ERROR", "Traceback", "REFUSE", "exit 2"))]
        tick = [l for l in lines if " TICK " in l]
        print("  watcher:", tick[-1] if tick else "(no TICK yet)")
        for l in ev[-6:]:
            print("  EVENT:", l)
    else:
        print("  watcher log MISSING")
    print(run([sys.executable, "plan/hb.py", "hold"]).strip())


if __name__ == "__main__":
    main()
