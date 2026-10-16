"""PAPER-3BOOK scan extractor (2026-10-16): latest run_scan result for a book, read verbatim from this
session's transcript jsonl, printed as scan3.py compact rows (no hand copying).
usage: python data/paper/scanx.py rl|r4 TRANSCRIPT.jsonl | python data/paper/scan3.py rl|r4 GRID TOTAL
stderr: 'SCANX book rows N/TOTAL result-ts ...' so the caller can confirm the result is the fresh one."""
import json, sys

SID = {"rl": "2f8e0fb0-197d-406d-a954-db0e4edff2b2", "r4": "0cc1cab3-408b-40bf-8a76-c6129ed0fed4"}
COLS = {"rl": ["Symbol", "Last", "P3 last time", "P3 vwap all", "P3 vwap reg", "Open"],
        "r4": ["Symbol", "Coil", "PriceReg", "PrevClose", "HighAll", "Volume", "Last"]}
book, path = sys.argv[1], sys.argv[2]
sid = SID[book]
hit = None
for ln in open(path, encoding="utf-8", errors="replace"):
    if sid not in ln or "scan_title" not in ln:
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
                r = json.loads(t)["data"]["result"]
            except (ValueError, KeyError, TypeError):
                continue
            if r.get("scan_id") == sid:
                hit = (ev.get("timestamp", "?"), r)
if not hit:
    sys.exit("SCANX no run_scan result found for " + book)
ts, r = hit
rows = r.get("results", [])
for row in rows:
    c = row.get("columns", {})
    print(" ".join((str(c.get(k, "")).strip() or "-").replace(" ", "_") for k in COLS[book]))
import datetime as _dt
tk = "P3 last time" if book == "rl" else "TradeTime"
mx = max((float(x["columns"].get(tk) or 0) for x in rows), default=0)
fresh = _dt.datetime.fromtimestamp(mx / 1000, _dt.timezone.utc).strftime("%H:%M:%SZ") if mx else "-"
print(f"SCANX {book} rows {len(rows)}/{r.get('total_items')} result-ts {ts} newest-print {fresh}", file=sys.stderr)
