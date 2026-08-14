"""One C37 paper-session scan cycle: ingest a spilled bars dump, rank, log.

Usage:
    python plan/paper_cycle.py <dump.json> <as-of HH:MM> <cycle-n> <state> \
        SYM:PREVCLOSE [SYM:PREVCLOSE ...] [--note "..."] [--new SYM,SYM]

Collapses what used to be three separate steps (ingest -> rank -> ledger
write) into one call, and prints only the few lines that actually drive a
decision: any truncation ERROR, the top 3 ranked names, and the TOP line.
Written on Paper Day 9 because the session runs 07:00-15:00 and the
per-cycle overhead was the binding constraint, not the API.

The symbols to ingest are taken from the SYM:PREVCLOSE list, so the ingest
assert (returned set == requested set) still covers exactly what we ranked.
"""
import json
import subprocess
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent
LEDGER = DIR / "data" / "paper_days" / "2026-08-14.json"


def main():
    argv = sys.argv[1:]
    note = ""
    new = []
    if "--note" in argv:
        i = argv.index("--note")
        note = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if "--new" in argv:
        i = argv.index("--new")
        new = [s for s in argv[i + 1].split(",") if s]
        argv = argv[:i] + argv[i + 2:]

    fetched = None
    if "--fetched" in argv:
        i = argv.index("--fetched")
        fetched = [s for s in argv[i + 1].split(",") if s]
        argv = argv[:i] + argv[i + 2:]

    dump, as_of, cyc, state, *pairs = argv
    # The ingest assert must cover exactly what was REQUESTED from the API,
    # not everything we rank -- a name ranked from cache (or deliberately
    # left out of the 10-symbol batch) would otherwise raise a permanent
    # false "TRUNCATED" and train us to ignore a real truncation.
    syms = fetched if fetched is not None else [p.split(":")[0] for p in pairs]

    # 1. ingest (asserts returned set == requested set)
    ing = subprocess.run(
        [sys.executable, str(DIR / "plan" / "rh_bars_ingest.py"),
         dump, "2026-08-14", *syms],
        capture_output=True, text=True)
    for ln in (ing.stdout + ing.stderr).splitlines():
        if "ERROR" in ln:
            print(ln)

    # 2. rank
    rk = subprocess.run(
        [sys.executable, str(DIR / "day-trading.py"), "rank", *pairs,
         "--as-of", as_of],
        capture_output=True, text=True)
    out = rk.stdout.splitlines()
    if rk.returncode != 0:
        print("ERROR: rank failed\n" + rk.stdout + rk.stderr)
        return
    body = [l for l in out if l.strip() and l.strip()[0].isdigit()]
    top = [l for l in out if "TOP =" in l]
    for l in body[:3]:
        print(l)
    print(top[0] if top else "ERROR: no TOP line")

    # 3. ledger
    d = json.loads(LEDGER.read_text())
    if new:
        d["crossed_set"] = sorted(set(d["crossed_set"]) | set(new))
    topname = top[0].split("TOP =")[1].strip() if top else "none"
    narm = top[0].split("/")[1].split("armable")[0].strip() if top else "?"
    d["cycles"].append(dict(cycle=int(cyc), time_et=as_of, state=state,
                            ranked=len(body), armable=narm, top=topname,
                            new_crossers=new, note=note))
    LEDGER.write_text(json.dumps(d, indent=2))


if __name__ == "__main__":
    main()
