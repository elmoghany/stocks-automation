"""Day-25 one-minute TOP-name poll (coordinator-owned Trigger C loop).

Usage:  python plan/_d25_poll.py SYM PREVCLOSE BID ASK [TICKET_DOLLARS] < bar_lines

stdin: bars_paste.py lines ("SYM ts o h l c v"), may be empty.
Steps, in the required order: append bars -> run `trigger` -> READ THE TAG NOW
-> print Trigger B arming numbers (session high, fill-arming, spread vs the
0.5% cap, 20%-of-trailing-10 size cap) -> beat heartbeat -> append one line to
data/paper_days/poll_{date}.log. Nothing here arms or fills; it reports.
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DIR = Path(__file__).resolve().parent.parent
PLAN = DIR / "plan"
sym, pc, bid, ask = sys.argv[1].upper(), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
ticket = float(sys.argv[5]) if len(sys.argv) > 5 else 15000.0
now = datetime.now(ZoneInfo("America/New_York"))
date = now.strftime("%Y-%m-%d")
(DIR / "data/paper_days" / f"SESSION_ALIVE_{date}.flag").write_text(now.strftime("%Y-%m-%d %H:%M:%S ET") + "\n")

blob = sys.stdin.read()
paste = subprocess.run([sys.executable, str(PLAN / "bars_paste.py"), date], input=blob,
                       capture_output=True, text=True)
print(paste.stdout.rstrip())
trig = subprocess.run([sys.executable, str(DIR / "day-trading.py"), "trigger", sym],
                      capture_output=True, text=True)
tlines = [l for l in trig.stdout.splitlines() if sym in l or "TAKEABLE" in l or "STALE" in l or "no signal" in l.lower()]
print("TRIGGER:", " | ".join(tlines) if tlines else trig.stdout.strip().splitlines()[-1:])

# Trigger B numbers from the stored bars
import csv
hi, last, vols, rth_hi = 0.0, None, [], 0.0
p = DIR / "data/rh_bars" / f"{sym}_{date}.csv"
if p.exists():
    rows = list(csv.DictReader(open(p)))
    for r in rows:
        hi = max(hi, float(r["high"]))
        if r["begins_at"] >= f"{date}T13:30:00Z":
            rth_hi = max(rth_hi, float(r["high"]))
        last = float(r["close"])
        vols.append(float(r["volume"]))
trail10 = sum(vols[-10:])
cap = int(0.2 * trail10)
spread = (ask - bid) / bid * 100 if bid > 0 else float("nan")
shares = int(ticket // ask) if ask > 0 else 0
fill_arm = "PASS (ask < trigger)" if ask < hi else "FAIL (trigger already met -- would be a market order)"
verdict = []
if spread > 0.5: verdict.append(f"SPREAD-VETO {spread:.2f}%")
if shares > cap: verdict.append(f"SIZE-CAP {cap} < {shares}")
if ask >= hi: verdict.append("CHASE (ask >= session high)")
orb = f"ORB/rth_hi={rth_hi} A-arm={'PASS' if ask < rth_hi else 'CHASE'}" if rth_hi else "ORB=n/a"
line = (f"{now:%H:%M:%S} {sym} last={last} hi={hi} {orb} bid={bid} ask={ask} spread={spread:.2f}% "
        f"trail10vol={int(trail10)} cap20={cap} shares@ask={shares} fillarm={fill_arm} "
        f"| {'; '.join(verdict) if verdict else 'ALL B-GATES OPEN'} | trig: {' | '.join(tlines)}")
print(line)
with open(DIR / "data/paper_days" / f"poll_{date}.log", "a") as f:
    f.write(line + "\n")
