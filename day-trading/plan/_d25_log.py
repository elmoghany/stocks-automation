"""Day-25: append one cycle entry to the day JSON and beat the heartbeat.
Usage: python plan/_d25_log.py STATE "scan text" [armed:0|1] [veto;veto...]
The ET minute is read from zoneinfo, never typed by hand (CLOCK RULE).
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DIR = Path(__file__).resolve().parent.parent
now = datetime.now(ZoneInfo("America/New_York"))
date = now.strftime("%Y-%m-%d")
(DIR / "data/paper_days" / f"SESSION_ALIVE_{date}.flag").write_text(now.strftime("%Y-%m-%d %H:%M:%S ET") + "\n")
state, text = sys.argv[1], sys.argv[2]
armed = bool(int(sys.argv[3])) if len(sys.argv) > 3 else False
vetoes = [v for v in (sys.argv[4].split(";") if len(sys.argv) > 4 else []) if v]
dp = DIR / "data/paper_days" / f"{date}.json"
d = json.load(open(dp))
d["cycles_log"].append({"et": now.strftime("%H:%M"), "state": state, "scan": text, "armed": armed, "vetoes": vetoes})
json.dump(d, open(dp, "w"), indent=2)
print(f"logged {now:%H:%M:%S} ET [{state}] {text[:80]}")
