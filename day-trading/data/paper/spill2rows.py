"""Convert a spilled run_scan JSON dump into scan3.py stdin rows.
usage: python data/paper/spill2rows.py rl|r4 FILE  -> prints TOTAL on stderr, rows on stdout"""
import json, sys
book, path = sys.argv[1], sys.argv[2]
d = json.load(open(path, encoding="utf-8"))
res = d.get("data", d)["result"]
rows = res["results"]
for r in rows:
    c = r["columns"]
    if book == "rl":
        print(c["Symbol"], c["Last"], c["P3 last time"], c["P3 vwap all"], c["P3 vwap reg"], c["Open"])
    else:
        print(c["Symbol"], c["Coil"], c["PriceReg"], c["PrevClose"], c["HighAll"], int(float(c["Volume"] or 0)), c["Last"])
sys.stderr.write(f"TOTAL {res['total_items']} ROWS {len(rows)}\n")
