"""Session heartbeat: write the current ET time into
data/paper_days/SESSION_ALIVE_{date}.flag and print it.
Usage:  python plan/hb.py [note]
The launcher and the 12:00 / 14:45 watchdog key on this file (2026-09-01
ops contract). Zone is named explicitly -- the TZ env var is broken here.
"""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def main():
    now = datetime.now(ET)
    d = Path(__file__).resolve().parent.parent / "data" / "paper_days"
    p = d / f"SESSION_ALIVE_{now:%Y-%m-%d}.flag"
    note = " ".join(sys.argv[1:])
    p.write_text(f"{now:%H:%M:%S} ET heartbeat {note}\n")
    print(f"HB {now:%H:%M:%S} ET {note}")


if __name__ == "__main__":
    main()
