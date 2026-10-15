"""PAPER-3BOOK 2026-10-15: R4 run_scan result spilled to a tool-results file -> dated scan file -> p3_r4 --scan/--now.
usage: python data/paper/r4spill.py SPILL_PATH GRID_HH:MM"""
import json, subprocess, sys
import datetime as _dt, zoneinfo as _z

now = _dt.datetime.now(_z.ZoneInfo("America/New_York"))
day, wall = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
src, grid = sys.argv[1], sys.argv[2]
d = json.load(open(src, encoding="utf-8"))
r = d["data"]["result"]
fn = f"data/paper/r4/scan_{day}_{wall.replace(':', '')}.json"
json.dump(d, open(fn, "w"))
print(f"R4 rows {len(r['results'])}/{r['total_items']} -> {fn}")
py = sys.executable
for args in (["--scan", fn, "--at", grid], ["--now", wall]):
    p = subprocess.run([py, "plan/p3_r4.py", *args], capture_output=True, text=True)
    print((p.stdout.strip() + " " + p.stderr.strip()[-300:])[:1500])
print(subprocess.run([py, "data/paper/hb_3book.py"], capture_output=True, text=True).stdout.strip())
