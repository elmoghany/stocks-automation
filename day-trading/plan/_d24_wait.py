"""Day-24 pacing wait that keeps the heartbeat alive while it blocks.

Usage:  python plan/_d24_wait.py HH:MM [MAX_SECONDS]

plan/wait_until.py is the clock authority, but a single 8-minute foreground
wait would leave data/paper_days/SESSION_ALIVE_{date}.flag untouched for
longer than the 5-minute watchdog limit, which reads as NO/STALE HEARTBEAT
and pages a human. So this waits in 30-second slices and touches the flag on
every slice, using the same zoneinfo clock and the same 480 s cap (a headless
turn backgrounds any call approaching 600 s, and a backgrounded wait ends the
session -- Day-14 postmortem).

Prints the ET/UTC clock on entry and exit so every wait stays auditable.
"""
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CAP = 480
SLICE = 30
ET = ZoneInfo("America/New_York")
DIR = Path(__file__).resolve().parent.parent


def beat(now):
    d = DIR / "data" / "paper_days" / f"SESSION_ALIVE_{now.strftime('%Y-%m-%d')}.flag"
    d.write_text(now.strftime("%Y-%m-%d %H:%M:%S ET") + "\n")


def main():
    target_s = sys.argv[1]
    budget = min(int(sys.argv[2]) if len(sys.argv) > 2 else CAP, CAP)
    hh, mm = (int(x) for x in target_s.split(":"))

    now = datetime.now(ET)
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    print(f"WAIT -> {target_s} ET | now {now:%H:%M:%S} ET "
          f"({now.astimezone(ZoneInfo('UTC')):%H:%M:%S} UTC)")
    beat(now)

    deadline = time.time() + budget
    while True:
        now = datetime.now(ET)
        if now >= target:
            print(f"REACHED {target_s} | now {now:%H:%M:%S} ET")
            return 0
        if time.time() >= deadline:
            print(f"BUDGET SPENT ({budget}s) | now {now:%H:%M:%S} ET "
                  f"-- target {target_s} NOT yet reached, call again")
            return 0
        beat(now)
        time.sleep(min(SLICE, max(1, (target - now).total_seconds()),
                       max(1, deadline - time.time())))


if __name__ == "__main__":
    raise SystemExit(main())
