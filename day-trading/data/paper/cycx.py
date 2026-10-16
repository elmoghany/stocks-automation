"""PAPER-3BOOK minute extractor (2026-10-16): latest get_equity_historicals + get_equity_quotes results,
read verbatim from this session's transcript jsonl, printed as cyc3.py 'B'/'Q' lines (no hand copying).
usage: python data/paper/cycx.py TRANSCRIPT.jsonl | python data/paper/cyc3.py HHMM [--rl] [--r4]
Interpolated bars are dropped; quote ts = the later of venue bid/ask time. stderr: SCANX-style summary."""
import json, sys

path = sys.argv[1]
bars = quotes = None
for ln in open(path, encoding="utf-8", errors="replace"):
    if '"tool_result"' not in ln or ('"bars' not in ln and 'bid_price' not in ln):
        continue
    try:
        ev = json.loads(ln)
    except ValueError:
        continue
    content = (ev.get("message") or {}).get("content")
    if not isinstance(content, list):
        continue
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "tool_result":
            continue
        texts = part.get("content")
        texts = [texts] if isinstance(texts, str) else [t.get("text", "") for t in texts or [] if isinstance(t, dict)]
        for t in texts:
            try:
                res = json.loads(t)["data"]["results"]
            except (ValueError, KeyError, TypeError):
                continue
            if res and isinstance(res[0], dict) and "bars" in res[0]:
                bars = (ev.get("timestamp", "?"), res)
            elif res and isinstance(res[0], dict) and "quote" in res[0]:
                quotes = (ev.get("timestamp", "?"), res)
n = 0
if bars:
    for r in bars[1]:
        for b in r.get("bars", []):
            if b.get("interpolated"):
                continue
            hm = b["begins_at"][11:16]
            print("B", r["symbol"], hm, b["open_price"], b["high_price"], b["low_price"], b["close_price"], b["volume"])
            n += 1
nq = 0
if quotes:
    for r in quotes[1]:
        q = r["quote"]
        ts = max(q.get("venue_bid_time") or "", q.get("venue_ask_time") or "")[:19] + "Z"
        if float(q.get("bid_price") or 0) > 0 and float(q.get("ask_price") or 0) > 0:
            print("Q", q["symbol"], q["bid_price"], q["ask_price"], ts)
            nq += 1
print(f"CYCX bars {n} (ts {bars[0] if bars else '-'}) quotes {nq} (ts {quotes[0] if quotes else '-'})", file=sys.stderr)
