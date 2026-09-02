"""Foreground pacing wait, clock-driven and hard-capped.

Usage:  python plan/wait_until.py HH:MM [MAX_SECONDS]

HH:MM is ET (the session's working clock). MAX_SECONDS defaults to 480 and
is capped at 480: a headless -p turn backgrounds any tool call that runs
past the 600 s mark, and a backgrounded wait ends the session, so no single
wait may approach it (Day-14 postmortem).

Prints the ET/UTC clock on entry and exit so every wait is auditable in the
transcript, and returns immediately if the target is already past.
"""
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CAP = 480
# CLOCK RULE: the TZ env var is broken on this box, so the zone is named
# explicitly. zoneinfo handles DST itself (2026-09-01 live-tool fixes: the
# old fixed -4h offset would have been an hour wrong from 2026-11-01).
ET = ZoneInfo("America/New_York")


def et_now():
    return datetime.now(ET)


def main():
    target_s = sys.argv[1]
    budget = min(int(sys.argv[2]) if len(sys.argv) > 2 else CAP, CAP)

    hh, mm = (int(x) for x in target_s.split(":"))
    now = et_now()
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target < now:
        print(f"target {target_s} ET already past "
              f"(now {now:%H:%M:%S} ET) -- no wait")
        return 0

    wait_s = (target - now).total_seconds()
    capped = min(wait_s, budget)
    print(f"waiting {capped:.0f}s -> {target_s} ET "
          f"(now {now:%H:%M:%S} ET / "
          f"{now.astimezone(timezone.utc):%H:%M:%S} UTC"
          f"{'; CAPPED, call again' if capped < wait_s else ''})",
          flush=True)

    deadline = time.time() + capped
    while time.time() < deadline:
        time.sleep(min(15, max(0.5, deadline - time.time())))

    end = et_now()
    print(f"awake at {end:%H:%M:%S} ET / "
          f"{end.astimezone(timezone.utc):%H:%M:%S} UTC")
    return 0


if __name__ == "__main__":
    sys.exit(main())
