"""PAPER-3BOOK 2026-10-26: pull the newest MCP tool result out of the session transcript, save it verbatim
(dated), and run the matching ingest/decision. No hand transcription.
usage: python data/paper/tr.py TRANSCRIPT KIND ARGS
  r4 GRID_HH:MM     newest run_scan "P3 R4 gapper coil" -> data/paper/r4/scan_{day}_{wallHHMM}.json -> p3_r4 --scan/--now
  rl GRID_HH:MM     newest run_scan "P3 RL wide universe" -> data/paper/rl/scan_{day}_{wallHHMM}.json -> p3_rl --snapshot/--now
  hist SYM ...      newest get_equity_historicals -> data/paper/hist_{day}_{wallHHMM}.json -> rh_bars_ingest SYM ...
  quotes            newest get_equity_quotes -> write_quote.py per symbol (bid/ask, ts = later of bid/ask venue time)
  r4now / rlnow     just the --now line (wall clock)
A result older than MAXAGE s (default 240, by transcript timestamp) is refused (stale)."""
import json, os, re, subprocess, sys, time
import datetime as _dt, zoneinfo as _z

ET = _z.ZoneInfo("America/New_York")
now = _dt.datetime.now(ET)
day, wall = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
hhmm = wall.replace(":", "")
py = sys.executable
SID = {"r4": "0cc1cab3-408b-40bf-8a76-c6129ed0fed4", "rl": "2f8e0fb0-197d-406d-a954-db0e4edff2b2"}
MAXAGE = float(os.environ.get("MAXAGE", "240"))


def texts(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from texts(v)
    elif isinstance(o, list):
        for v in o:
            yield from texts(v)


def resolve(t):
    """inline JSON text, or a spill notice naming a file -> JSON text"""
    s = t.lstrip()
    if s.startswith("{"):
        return s
    m = re.search(r"([A-Za-z]:[\\/][^\"'<>\n]+?\.(?:json|txt))", t)
    if m and os.path.exists(m.group(1)):
        raw = open(m.group(1), encoding="utf-8", errors="ignore").read().strip()
        try:
            d = json.loads(raw)
            if isinstance(d, list) and d and isinstance(d[0], dict) and "text" in d[0]:
                return d[0]["text"]
            return raw
        except json.JSONDecodeError:
            i = raw.find("{")
            return raw[i:] if i >= 0 else None
    return None


def newest(pred):
    lines = open(TR, encoding="utf-8").read().split("\n")[-300:]
    for ln in reversed(lines):
        if '"tool_result"' not in ln:
            continue
        o = json.loads(ln)
        ts = o.get("timestamp")
        for blk in (o.get("message") or {}).get("content") or []:
            if not isinstance(blk, dict) or blk.get("type") != "tool_result":
                continue
            for t in texts(blk.get("content")):
                j = resolve(t)
                if j and pred(j):
                    age = None
                    if ts:
                        tt = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        age = (_dt.datetime.now(_dt.timezone.utc) - tt).total_seconds()
                    return j, age
    return None, None


def run(args):
    r = subprocess.run([py] + args, capture_output=True, text=True)
    return (r.stdout.strip() + " " + r.stderr.strip()[-400:]).strip()


def fmt(a):
    return "?" if a is None else f"{a:.0f}"


def stale(age):
    if age is not None and age > MAXAGE:
        sys.exit(f"STALE result {fmt(age)}s old -> not used")


TR, kind, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
if kind in ("r4", "rl"):
    grid = rest[0]
    j, age = newest(lambda s: s.startswith('{"data":{"result":{"scan_id":"' + SID[kind]))
    if not j:
        sys.exit(f"NO {kind} scan result in transcript tail")
    stale(age)
    tcol = "P3 last time" if kind == "rl" else "TradeTime"
    newest_tick = max((float(r["columns"].get(tcol) or 0) for r in json.loads(j)["data"]["result"]["results"]),
                      default=0) / 1000
    if time.time() - newest_tick > 180:
        sys.exit(f"STALE {kind} scan: newest {tcol} {time.time() - newest_tick:.0f}s old -> not ingested")
    fn = f"data/paper/{kind}/scan_{day}_{hhmm}.json"
    open(fn, "w", encoding="utf-8").write(j)
    n = json.loads(j)["data"]["result"]
    print(f"{kind.upper()} scan rows {len(n.get('results', []))}/{n.get('total_items')} age {fmt(age)}s -> {fn}")
    if kind == "rl":
        print("INGEST", run(["plan/p3_rl.py", "--snapshot", fn, "--at", grid])[:500])
        print("NOW", run(["plan/p3_rl.py", "--now", wall])[:1500])
    else:
        print("INGEST", run(["plan/p3_r4.py", "--scan", fn, "--at", grid])[:500])
        print("NOW", run(["plan/p3_r4.py", "--now", wall])[:2500])
elif kind == "hist":
    want = set(rest)
    j, age = newest(lambda s: s.startswith('{"data":{"results":[') and '"bars"' in s[:2000] or
                    (s.startswith('{"data":{"results":[') and '"bars":' in s))
    if not j:
        sys.exit("NO historicals result in transcript tail")
    stale(age)
    got = {r.get("symbol") for r in json.loads(j)["data"]["results"]}
    if want and not want <= got:
        print("WARN historicals symbols", sorted(got), "!= wanted", sorted(want))
    fn = f"data/paper/hist_{day}_{hhmm}.json"
    if os.path.exists(fn):
        fn = f"data/paper/hist_{day}_{hhmm}b.json"
    open(fn, "w", encoding="utf-8").write(j)
    nb = {r.get("symbol"): len(r.get("bars") or []) for r in json.loads(j)["data"]["results"]}
    print("HIST", fn, nb, f"age {fmt(age)}s")
    print("INGEST", run(["plan/rh_bars_ingest.py", fn, day] + (rest or sorted(got)))[:600])
elif kind == "quotes":
    j, age = newest(lambda s: s.startswith('{"data":{"results":[{"quote":'))
    if not j:
        sys.exit("NO quotes result in transcript tail")
    stale(age)
    for r in json.loads(j)["data"]["results"]:
        q = r["quote"]
        b, a = q.get("bid_price"), q.get("ask_price")
        ts = max(q.get("venue_bid_time") or "", q.get("venue_ask_time") or "")
        if not b or not a or float(b) <= 0 or float(a) <= 0:
            print("QUOTE-SKIP", q.get("symbol"), b, a)
            continue
        print("QUOTE", q["symbol"], float(b), float(a), ts[11:19], "spread%",
              round(200 * (float(a) - float(b)) / (float(a) + float(b)), 3), "last", q.get("last_trade_price"),
              q.get("venue_last_trade_time", "")[11:19], q.get("state"),
              run(["plan/write_quote.py", q["symbol"], b, a, ts, day])[:0])
elif kind == "r4now":
    print(run(["plan/p3_r4.py", "--now", wall])[:2500])
elif kind == "rlnow":
    print(run(["plan/p3_rl.py", "--now", wall])[:1500])
print(run(["data/paper/hb_3book.py"]))
