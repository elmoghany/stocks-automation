"""plan/wait_until.py HH:MM, then +8 s so bar HH:MM-1 has printed (mandate: next minute + 0:05)."""
import subprocess, sys, time
subprocess.run([sys.executable, "plan/wait_until.py", sys.argv[1]])
time.sleep(8)
import datetime as _dt, zoneinfo as _z
print("go", _dt.datetime.now(_z.ZoneInfo("America/New_York")).strftime("%H:%M:%S"))
