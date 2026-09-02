"""One-call FLAT cycle: ingest a spilled get_equity_historicals dump, rank,
run Trigger C on the TOP name, heartbeat.
Usage:  python plan/cyc.py DUMP.txt HH:MM SYM:PREVCLOSE [SYM:PREVCLOSE ...]
                 [--top SYM]   (force the Trigger C name; default = rank TOP)
Written 2026-09-02 (Day 21) to cut the per-cycle tool-call count: every
step here already existed as its own command; this only chains them and
trims the noise lines (NO BARS / only N bars) from the rank output.
The trigger call is made IMMEDIATELY after the rank so its tag is read in
the same output (Trigger C loop-ordering rule, 2026-08-21).
"""
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
    args = sys.argv[1:]
    force_top = None
    if "--top" in args:
        i = args.index("--top"); force_top = args[i + 1]; del args[i:i + 2]
    dump, asof, *specs = args
    date = datetime.now(ET).strftime("%Y-%m-%d")
    syms = [s.split(":")[0] for s in specs]
    out = run([sys.executable, "plan/rh_bars_ingest.py", dump, date] + syms)
    lines = [l for l in out.splitlines() if " 0 bars total" not in l]
    print("\n".join(lines))
    rk = run([sys.executable, "day-trading.py", "rank"] + specs + ["--as-of", asof])
    top = force_top
    for l in rk.splitlines():
        if "excluded: NO BARS" in l or "excluded: only" in l:
            continue
        print(l)
        if "TOP = " in l and top is None:
            top = l.split("TOP = ")[1].split()[0].strip()
    if top and top != "none":
        tr = run([sys.executable, "day-trading.py", "trigger", top, "--as-of", asof])
        print("\n".join(l for l in tr.splitlines()
                        if "scores patterns only" not in l))
    print(run([sys.executable, "plan/hb.py", f"cyc {asof}"]).strip())


if __name__ == "__main__":
    main()
