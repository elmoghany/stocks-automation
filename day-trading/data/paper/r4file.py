"""Spilled R4 run_scan result file -> scan3.py r4 rows (2026-10-22 helper).
usage: python data/paper/r4file.py GRID_HH:MM PATH_TO_SPILLED_JSON
Writes every row (no coil trim) as 'SYM COIL PRICEREG PREVCLOSE HIGHALL VOLUME LAST' and calls scan3.py r4 with total_items."""
import json, subprocess, sys

grid, path = sys.argv[1], sys.argv[2]
d = json.load(open(path, encoding="utf-8"))
res = d["data"]["result"]
rows = []
for it in res["results"]:
    c = it["columns"]
    rows.append(" ".join([it["ticker"], c["Coil"], c["PriceReg"], c["PrevClose"], c["HighAll"], c["Volume"], c["Last"]]))
r = subprocess.run([sys.executable, "data/paper/scan3.py", "r4", grid, str(res["total_items"])], input="\n".join(rows),
                   capture_output=True, text=True)
print(len(rows), "rows;", r.stdout.strip(), r.stderr.strip()[-300:])
