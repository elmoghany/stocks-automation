"""PAPER-3BOOK minute-cycle helper (2026-10-09).
usage: python data/paper/cyc3.py HHMM [--r4] [--rl] < lines
  'B SYM HH:MM(UTC) O H L C V'  real printed bar (interpolated bars omitted)
  'Q SYM BID ASK TS_UTC'        live quote -> plan/write_quote.py
Bars -> data/paper/hist_{day}_{HHMM}.json (rh format) -> rh_bars_ingest; quotes -> quotes_{day}.json;
then (optional) the compact R4 --now status / RL --now line, watcher EXIT lines, and the heartbeat."""
import json, subprocess, sys
from collections import OrderedDict
import datetime as _dt, zoneinfo as _z

now = _dt.datetime.now(_z.ZoneInfo("America/New_York"))
day = now.strftime("%Y-%m-%d")
wall = now.strftime("%H:%M")
hhmm = sys.argv[1]
py = sys.executable
bars, quotes = OrderedDict(), []
for ln in sys.stdin.read().replace("\ufeff", "").split("\n"):
    p = ln.split()
    if len(p) == 8 and p[0] == "B":
        _, s, t, o, h, l, c, v = p
        bars.setdefault(s, []).append({"begins_at": f"{day}T{t}:00Z", "open_price": o, "high_price": h,
                                       "low_price": l, "close_price": c, "volume": int(float(v)),
                                       "session": "reg"})
    elif len(p) == 5 and p[0] == "Q":
        quotes.append(p[1:])
if bars:
    fn = f"data/paper/hist_{day}_{hhmm}.json"
    json.dump({"data": {"results": [{"symbol": s, "interval": "minute", "bounds": "extended", "bars": b}
                                    for s, b in bars.items()]}}, open(fn, "w"))
    r = subprocess.run([py, "plan/rh_bars_ingest.py", fn, day] + list(bars), capture_output=True, text=True)
    print("BARS", " | ".join(x.strip() for x in r.stdout.splitlines() if x.strip() and x.strip() != "OK"))
for s, b, a, ts in quotes:
    if "T" not in ts:  # bare HH:MM:SS (UTC) -> full ISO; watcher's _parse_et rejects bare times
        ts = f"{day}T{ts}Z"
    r = subprocess.run([py, "plan/write_quote.py", s, b, a, ts, day], capture_output=True, text=True)
    print("QUOTE", s, b, a, ts[11:19], "" if r.returncode == 0 else r.stderr[-200:])
if "--r4" in sys.argv:
    r = subprocess.run([py, "data/paper/r4s.py", wall], capture_output=True, text=True)
    print("R4", r.stdout.strip()[:700])
if "--rl" in sys.argv:
    r = subprocess.run([py, "plan/p3_rl.py", "--now", wall], capture_output=True, text=True)
    print("RL", r.stdout.strip()[:500])
for b in ("r4", "r15", "rl"):
    try:
        lines = open(f"data/paper_days/watch_{day}.{b}.log", encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        continue
    ex = [x for x in lines if "EXIT" in x]
    last = lines[-1] if lines else ""
    print(f"W{b}", (ex[-1][:200] + " || ") if ex else "", last[:160])
r = subprocess.run([py, "data/paper/hb_3book.py"], capture_output=True, text=True)
print(r.stdout.strip())
