"""Latest RL run_scan result from the session transcript -> scan3.py rl rows (2026-10-22 helper).
usage: python data/paper/rlfile.py GRID_HH:MM TRANSCRIPT_JSONL
Finds the newest tool_result carrying the RL scan JSON (scan_id 2f8e0fb0...), refuses if its newest
'P3 last time' is >180 s old (stale/previous grid), and feeds every row verbatim to scan3.py rl (no transcription)."""
import json, subprocess, sys, time

SCAN = "2f8e0fb0-197d-406d-a954-db0e4edff2b2"
grid, path = sys.argv[1], sys.argv[2]


def texts(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from texts(v)
    elif isinstance(o, list):
        for v in o:
            yield from texts(v)


res = None
for ln in reversed(open(path, encoding="utf-8").read().split("\n")[-400:]):
    if SCAN not in ln or '"tool_result"' not in ln:
        continue
    for t in texts(json.loads(ln)):
        if t.startswith('{"data":{"result":{"scan_id":"' + SCAN):
            res = json.loads(t)["data"]["result"]
            break
    if res:
        break
if not res:
    sys.exit("NO RL scan result found in transcript tail")
rows, newest = [], 0.0
for it in res["results"]:
    c = it["columns"]
    lt = c["P3 last time"] or "-"
    if lt != "-":
        newest = max(newest, float(lt) / 1000)
    rows.append(" ".join([it["ticker"], c["Last"], lt, c["P3 vwap all"]]))
age = time.time() - newest
if grid == "DRY":  # parse check only, nothing ingested
    sys.exit(f"DRY {len(rows)} rows total {res['total_items']} newest tick {age:.0f}s old; first {rows[0]}; last {rows[-1]}")
if age > 180:
    sys.exit(f"STALE RL result: newest P3 last time {age:.0f}s old -> not ingested")
r = subprocess.run([sys.executable, "data/paper/scan3.py", "rl", grid, str(res["total_items"])], input="\n".join(rows),
                   capture_output=True, text=True)
print(len(rows), f"rows (newest tick {age:.0f}s old);", r.stdout.strip(), r.stderr.strip()[-300:])
