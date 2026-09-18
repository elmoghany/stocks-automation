"""Day-25 scan-cycle helper: sweep a dump, then screen (Q1) every candidate
that has no verdict yet, loading its RH market cap from the dump first.

Usage:  python plan/_d25_cycle.py <dump.json> <YYYY-MM-DD> <HH:MM>

Q1 FAILs are written to scan_state halal_fail (a real FAIL is never
re-litigated). Q1 PASS names are printed for the Q2 business-line judgement,
which is NOT mechanised -- only a name passing BOTH is armable. Also beats
the SESSION_ALIVE heartbeat.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DIR = Path(__file__).resolve().parent.parent
PLAN = DIR / "plan"

dump, date, hhmm = sys.argv[1:4]
now = datetime.now(ZoneInfo("America/New_York"))
(DIR / "data/paper_days" / f"SESSION_ALIVE_{date}.flag").write_text(
    now.strftime("%Y-%m-%d %H:%M:%S ET") + "\n")
print(f"CYCLE clock {now:%H:%M:%S} ET")

out = subprocess.run([sys.executable, str(PLAN / "scan_sweep.py"), dump, date, hhmm],
                     capture_output=True, text=True)
print(out.stdout.rstrip())
if out.returncode:
    print(out.stderr); sys.exit(1)

sp = DIR / "data/paper_days" / f"scan_state_{date}.json"
st = json.load(open(sp))
known = set(st["halal_fail"]) | set(st["cannot_verify"]) | set(st.get("halal_pass", []))
todo = [s for s in st["candidates"] if s not in known]
if not todo:
    print("SCREEN: no unscreened candidates"); sys.exit(0)

print(f"SCREEN Q1 on {todo}")
subprocess.run([sys.executable, str(PLAN / "_d24_mcap_from_dump.py"), dump] + todo)
r = subprocess.run([sys.executable, str(PLAN / "live_halal.py"), "--json"] + todo,
                   capture_output=True, text=True)
try:
    q = json.loads(r.stdout)
except Exception:
    print("ERROR: live_halal produced no JSON"); print(r.stdout[-2000:]); print(r.stderr[-2000:]); sys.exit(1)
hp = DIR / "data/paper_days" / f"halal_{date}_{hhmm.replace(':', '')}.json"
json.dump(q, open(hp, "w"), indent=1)
q1pass = []
for s, v in q.items():
    verdict = v.get("verdict") if isinstance(v, dict) else str(v)
    print(f"  {s:<6} Q1 {verdict:<20} loan {v.get('loan_pct')} cash {v.get('cash_pct')} mcap {v.get('mcap')}")
    if verdict == "PASS":
        q1pass.append(s)
    elif verdict == "REFUSE-TO-EVALUATE":
        st["cannot_verify"].append(s)
    else:
        st["halal_fail"].append(s)
json.dump(st, open(sp, "w"), indent=1)
print(f"Q1 PASS (needs Q2 business-line judgement before arming): {q1pass or 'none'}")
