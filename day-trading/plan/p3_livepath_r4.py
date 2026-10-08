"""PAPER-3BOOK R4 live I/O path test (2026-10-01): run as
    python plan/p3_livepath_r4.py

Smoke test of R4's LIVE I/O path on a historical day: fake run_scan
result files (emulated from bars), rh_bars CSVs written only for the names
the decision asks for, CLI runs at chosen wall minutes."""
import json, subprocess, sys, shutil
from pathlib import Path
sys.path.insert(0, r"C:\cornell\stocks-automation\day-trading\plan")
import numpy as np
import p3_lib as P, cp_lib as CL, p3_parity_r4 as T, p3_r4 as R

D = "2024-10-22"
SCR = P.DATA / "_p3_livepath_r4"
SCR.mkdir(exist_ok=True)
fd = T.FullDay(D)
full = fd.day_at(CL.NMIN)
snaps = {x["t"]: x for x in T.snaps_from_bars(full, CL.NMIN)}
made = []


def write_bars(sym, upto):
    i = fd.syms.index(sym)
    rows = ["begins_at,open,high,low,close,volume"]
    for k in range(0, upto):
        if np.isnan(fd.arr["c"][i, k]):
            continue
        rows.append(f"{P.utc_iso(D, k)},{fd.arr['o'][i,k]},{fd.arr['h'][i,k]},"
                    f"{fd.arr['l'][i,k]},{fd.arr['c'][i,k]},{fd.arr['v'][i,k]}")
    f = P.RH_BARS / f"{sym}_{D}.csv"
    f.write_text("\n".join(rows) + "\n")
    made.append(f)


def cli(*a):
    out = subprocess.run([sys.executable, str(P.PLAN / "p3_r4.py"), "--date", D, *a],
                         capture_output=True, text=True).stdout
    line = [l for l in out.splitlines() if l.startswith("P3 ")]
    return json.loads(line[-1][3:]) if line else out


held = set()
events = []
for wall in range(336, 662):
    t = wall - 1
    if t in snaps and t <= 655:
        sn = snaps[t]
        res = {"data": {"result": {"total_items": len(sn["rows"]), "results": [
            {"ticker": s, "columns": {"PriceReg": str(r["last"]), "PrevClose": str(r["pc"]),
                                      "Coil": str(r["coil"])}} for s, r in sn["rows"].items()]}}}
        f = SCR / f"scan_{D}_{P.hhmm(t).replace(':','')}.json"
        f.write_text(json.dumps(res))
        cli("--scan", str(f), "--at", P.hhmm(t), "--now", P.hhmm(wall))
    for s in held:
        write_bars(s, wall)
    o = cli("--now", P.hhmm(wall))
    if o.get("action") == "NEED_DATA":
        for s in o["need_bars"]:
            write_bars(s, wall)
            held.add(s)
        o = cli("--now", P.hhmm(wall))
    if o.get("action") not in ("NOTHING", "HOLD") or wall % 30 == 0:
        events.append((P.hhmm(wall), o.get("action"), o.get("sym"), o.get("state"), len(o.get("closed_legs", []))))
    if o.get("sym"):
        held.add(o["sym"])
for e in events:
    print(e)
print("final closed:", o.get("closed_legs"))
truth = [(x["sym"], x["entry_min"], x["exit_min"], round(x["exit"], 4))
         for x in T.bt_next_open([D], causal=True)]
got = [(x["sym"], P.parse_hhmm(x["entry_min"]), P.parse_hhmm(x["exit_min"]),
        round(x["exit"], 4)) for x in o.get("closed_legs", [])]
print("LIVE-PATH", "PASS" if got == truth else f"FAIL {got} vs {truth}")
shutil.rmtree(SCR, ignore_errors=True)
for f in made:
    f.unlink(missing_ok=True)
for f in (P.book_dir("r4") / f"snaps_{D}.jsonl", R.refusals_path(D),
          R.vetoes_path(D)):
    f.unlink(missing_ok=True)
