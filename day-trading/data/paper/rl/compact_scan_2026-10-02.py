# one-off helper for the late-launch 2026-10-02 session: compact "SYM Last tt vwap" text (transcribed
# from the inline run_scan result) -> scan-format JSON readable by p3_lib.scan_rows
import json, sys
src, out, note = sys.argv[1], sys.argv[2], sys.argv[3]
res = []
for ln in open(src).read().split("\n"):
    if ln.strip():
        s, l, t, v = ln.split()
        res.append({"ticker": s, "columns": {"Last": l, "P3 last time": t, "P3 vwap all": v}})
assert len(res) == 95, len(res)
json.dump({"note": note, "data": {"result": {"scan_id": "2f8e0fb0-197d-406d-a954-db0e4edff2b2", "total_items": 95, "results": res}}}, open(out, "w"))
print("wrote", out, len(res))
