"""PAPER-3BOOK scan helper (2026-10-15): compact run_scan rows -> dated scan file -> ingest -> --now.
usage: python data/paper/scan3.py rl|r4 GRID_HH:MM [TOTAL] < rows
  rl rows: 'SYM LAST LASTTIME VWAPALL VWAPREG OPEN'                   ('-' = empty cell)
  r4 rows: 'SYM COIL PRICEREG PREVCLOSE HIGHALL VOLUME LAST'
Rows are the scan's cells copied as returned (same order). Writes data/paper/{book}/scan_{day}_{HHMM wall}.json
in the run_scan format, runs p3_rl --snapshot/--now or p3_r4 --scan/--now, prints the P3 lines + heartbeat."""
import json, subprocess, sys
import datetime as _dt, zoneinfo as _z

COLS = {"rl": ["Symbol", "Last", "P3 last time", "P3 vwap all", "P3 vwap reg", "Open"],
        "r4": ["Symbol", "Coil", "PriceReg", "PrevClose", "HighAll", "Volume", "Last"]}
SID = {"rl": "2f8e0fb0-197d-406d-a954-db0e4edff2b2", "r4": "0cc1cab3-408b-40bf-8a76-c6129ed0fed4"}
now = _dt.datetime.now(_z.ZoneInfo("America/New_York"))
day, wall = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
book, grid = sys.argv[1], sys.argv[2]
cols = COLS[book]
res = []
for ln in sys.stdin.read().split("\n"):
    p = ln.split()
    if book == "rl" and len(p) == 4:  # Last/time/vwap-all only (as the 10-14 scan files)
        p += ["-", "-"]
    if len(p) != len(cols):
        if p:
            print("SKIP-ROW", ln)
        continue
    c = {k: ("" if v == "-" else v) for k, v in zip(cols, p)}
    res.append({"ticker": c["Symbol"], "columns": c})
tot = int(sys.argv[3]) if len(sys.argv) > 3 else len(res)
fn = f"data/paper/{book}/scan_{day}_{wall.replace(':', '')}.json"
json.dump({"data": {"result": {"scan_id": SID[book], "total_items": tot, "results": res,
                               "_note": f"compact copy of run_scan cells, wall {wall} ET, grid {grid}"}}},
          open(fn, "w"))
py = sys.executable
if book == "rl":
    a = subprocess.run([py, "plan/p3_rl.py", "--snapshot", fn, "--at", grid], capture_output=True, text=True)
    b = subprocess.run([py, "plan/p3_rl.py", "--now", wall], capture_output=True, text=True)
else:
    a = subprocess.run([py, "plan/p3_r4.py", "--scan", fn, "--at", grid], capture_output=True, text=True)
    b = subprocess.run([py, "plan/p3_r4.py", "--now", wall], capture_output=True, text=True)
print(f"{book.upper()} rows {len(res)}/{tot} -> {fn}")
print("INGEST", (a.stdout.strip() + " " + a.stderr.strip()[-300:])[:600])
print("NOW", (b.stdout.strip() + " " + b.stderr.strip()[-300:])[:1500])
r = subprocess.run([py, "data/paper/hb_3book.py"], capture_output=True, text=True)
print(r.stdout.strip())
