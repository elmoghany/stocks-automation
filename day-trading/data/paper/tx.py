"""PAPER-3BOOK 2026-10-23 helper: the latest MCP tool result of one kind, taken verbatim from this session's
transcript (or the spill file it points to), saved to a dated file and fed to the live scripts. No hand copying.
usage: python data/paper/tx.py TRANSCRIPT KIND [GRID_HH:MM] [--rl] [--r4]
  KIND rl | r4  : run_scan result -> data/paper/{book}/scan_{day}_{HHMM wall}.json -> --snapshot/--scan + --now
  KIND cyc      : get_equity_historicals -> data/paper/hist_{day}_{HHMM}.json -> rh_bars_ingest (symbols in it)
                  and get_equity_quotes -> plan/write_quote.py per symbol; then optional RL/R4 --now, watcher tails
  KIND bars     : bars only (NEED_DATA fetches), file suffix HHMM + 'n'
  KIND quotes   : print latest quote bid/ask per symbol (no write)
A result older than MAXAGE seconds (transcript event timestamp) is refused (no stale data)."""
import json, re, subprocess, sys, time, shutil
import datetime as _dt, zoneinfo as _z

MAXAGE = 100
SID = {"rl": "2f8e0fb0-197d-406d-a954-db0e4edff2b2", "r4": "0cc1cab3-408b-40bf-8a76-c6129ed0fed4"}
now = _dt.datetime.now(_z.ZoneInfo("America/New_York"))
day, wall = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
py = sys.executable
path, kind = sys.argv[1], sys.argv[2]
args = [a for a in sys.argv[3:] if not a.startswith("--")]
grid = args[0] if args else None


def results():
    """yield (epoch, text) for each tool_result in the transcript tail, newest first."""
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")[-300:]
    for ln in reversed(lines):
        if '"tool_result"' not in ln:
            continue
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        ts = ev.get("timestamp")
        ep = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() if ts else 0
        content = (ev.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "tool_result":
                continue
            c = part.get("content")
            for t in ([c] if isinstance(c, str) else [x.get("text", "") for x in c or [] if isinstance(x, dict)]):
                m = re.search(r"Output has been saved to (.+?\.(?:txt|json))", t)
                if m:
                    yield ep, open(m.group(1), encoding="utf-8").read(), m.group(1)
                else:
                    yield ep, t, None


def find(pred):
    for ep, t, sp in results():
        try:
            d = json.loads(t)
        except ValueError:
            continue
        if pred(d):
            age = time.time() - ep
            if age > MAXAGE:
                sys.exit(f"STALE {kind}: newest matching result is {age:.0f}s old -> not used")
            return d, t, sp, age
    return None, None, None, None


def is_bars(d):
    r = (d.get("data") or {}).get("results")
    return bool(r) and isinstance(r[0], dict) and "bars" in r[0]


def is_quotes(d):
    r = (d.get("data") or {}).get("results")
    return bool(r) and isinstance(r[0], dict) and "quote" in r[0]


def run(cmd):
    r = subprocess.run([py] + cmd, capture_output=True, text=True)
    return (r.stdout.strip() + (" ERR " + r.stderr.strip()[-400:] if r.returncode else "")).strip()


def ingest_bars(suffix=""):
    d, t, sp, age = find(is_bars)
    if not d:
        print("NO bars result"); return
    fn = f"data/paper/hist_{day}_{wall.replace(':', '')}{suffix}.json"
    if sp:
        shutil.copyfile(sp, fn)
    else:
        open(fn, "w", encoding="utf-8").write(t)
    syms = [r["symbol"] for r in d["data"]["results"]]
    nb = {r["symbol"]: sum(1 for b in r.get("bars", []) if not b.get("interpolated")) for r in d["data"]["results"]}
    print(f"BARS ({age:.0f}s) {nb} ->", run(["plan/rh_bars_ingest.py", fn, day] + syms).replace("\n", " | ")[:600])


def write_quotes():
    d, t, sp, age = find(is_quotes)
    if not d:
        print("NO quotes result"); return
    for r in d["data"]["results"]:
        q = r["quote"]
        ts = max(q.get("venue_bid_time") or "", q.get("venue_ask_time") or "")[:19] + "Z"
        b, a = q.get("bid_price") or "0", q.get("ask_price") or "0"
        if float(b) > 0 and float(a) > 0:
            out = run(["plan/write_quote.py", q["symbol"], b, a, ts, day])
            print("QUOTE", q["symbol"], b, a, ts[11:19], q.get("state"), out[-120:] if "ERR" in out else "")
        else:
            print("QUOTE-BAD", q["symbol"], b, a, q.get("state"))


if kind in ("rl", "r4"):
    d, t, sp, age = find(lambda d: ((d.get("data") or {}).get("result") or {}).get("scan_id") == SID[kind])
    if not d:
        sys.exit(f"NO {kind} scan result")
    fn = f"data/paper/{kind}/scan_{day}_{wall.replace(':', '')}.json"
    if sp:
        shutil.copyfile(sp, fn)
    else:
        open(fn, "w", encoding="utf-8").write(t)
    n = len(d["data"]["result"]["results"])
    if kind == "rl":
        a = run(["plan/p3_rl.py", "--snapshot", fn, "--at", grid])
        b = run(["plan/p3_rl.py", "--now", wall])
    else:
        a = run(["plan/p3_r4.py", "--scan", fn, "--at", grid])
        b = run(["plan/p3_r4.py", "--now", wall])
    print(f"{kind.upper()} scan ({age:.0f}s old) rows {n}/{d['data']['result'].get('total_items')} -> {fn}")
    print("INGEST", a[:500])
    print("NOW", b[:2500])
elif kind == "bars":
    ingest_bars("n")
elif kind == "cyc":
    ingest_bars()
    write_quotes()
    if "--rl" in sys.argv:
        print("RL", run(["plan/p3_rl.py", "--now", wall])[:600])
    if "--r4" in sys.argv:
        print("R4", run(["data/paper/r4s.py", wall])[:900])
elif kind == "quotes":
    d, t, sp, age = find(is_quotes)
    for r in d["data"]["results"]:
        q = r["quote"]
        print(q["symbol"], q.get("bid_price"), q.get("ask_price"), q.get("venue_bid_time"), q.get("state"))
if kind in ("cyc", "rl", "r4"):
    for bk in ("r4", "r15", "rl"):
        try:
            lines = open(f"data/paper_days/watch_{day}.{bk}.log", encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        ex = [x for x in lines if "EXIT" in x]
        print(f"W{bk}", (ex[-1][:220] + " || ") if ex else "", (lines[-1] if lines else "")[:160])
print(run(["data/paper/hb_3book.py"]))
