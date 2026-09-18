"""Wait until a few seconds past the next minute boundary (heartbeat-safe).
Usage: python plan/_d25_minute.py [OFFSET_SECONDS=4]
Prints the ET clock on exit so the minute is read from zoneinfo, never typed.
"""
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DIR = Path(__file__).resolve().parent.parent
off = int(sys.argv[1]) if len(sys.argv) > 1 else 4
now = datetime.now(ET)
target = (now.replace(second=0, microsecond=0)).timestamp() + 60 + off
while time.time() < target:
    time.sleep(min(15, max(0.2, target - time.time())))
now = datetime.now(ET)
(DIR / "data/paper_days" / f"SESSION_ALIVE_{now:%Y-%m-%d}.flag").write_text(now.strftime("%Y-%m-%d %H:%M:%S ET") + "\n")
print(f"MINUTE {now:%H:%M:%S} ET ({now.astimezone(ZoneInfo('UTC')):%H:%M:%S}Z)")
