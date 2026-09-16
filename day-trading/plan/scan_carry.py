"""Rebuild a run_scan dump from BASE given the LIVE ticker list, via dump_carry.py.

Written 2026-09-16 (Day 23). dump_carry.py needs an explicit --drop list, i.e.
the operator must diff base-vs-live tickers by eye every cycle. This wrapper
takes the live ticker list verbatim (cheap to transcribe: ~120 symbols in scan
order) and computes the diff mechanically:

    drops = base tickers not in LIVE
    new   = LIVE tickers not in base  -> MUST be supplied via --set with a NAME
                                         (or be in ticker_names.json); else error

Usage:
    python plan/scan_carry.py BASE.json OUT.json LIVE_TICKERS.txt \
        [--set "TICKER:PCT:LAST[:VOL[:NAME]]" ...]

LIVE_TICKERS.txt: whitespace/newline separated tickers, exactly as the live
scan returned them (order irrelevant). Any ticker in LIVE that is neither in
BASE nor in --set is a hard error -- a live row can never be silently invented
or silently lost. The --set specs pass straight through to dump_carry.py.
"""
import json
import subprocess
import sys
from pathlib import Path


def main():
    base_p, out_p, live_p, *rest = sys.argv[1:]
    sets = []
    mode = None
    for a in rest:
        if a == "--set":
            mode = "set"
            continue
        if mode == "set":
            sets.append(a)
    base = json.load(open(base_p, encoding="utf-8"))["data"]["result"]["results"]
    base_tk = {r["ticker"].upper() for r in base}
    live = {t.strip().upper() for t in Path(live_p).read_text(encoding="utf-8").split() if t.strip()}
    set_tk = {s.split(":")[0].upper() for s in sets}
    reg_p = Path(base_p).parent / "ticker_names.json"
    registry = json.load(open(reg_p, encoding="utf-8")) if reg_p.exists() else {}

    drops = sorted(base_tk - live)
    new = sorted(live - base_tk)
    unsupplied = [t for t in new if t not in set_tk and t not in registry]
    if unsupplied:
        print(f"ERROR: live tickers not in base and not supplied via --set "
              f"(need PCT:LAST:VOL:NAME): {unsupplied}", file=sys.stderr)
        return 1
    reg_only = [t for t in new if t not in set_tk and t in registry]
    if reg_only:
        print(f"ERROR: new tickers {reg_only} are in the registry but have no "
              f"--set numbers; supply TICKER:PCT:LAST:VOL", file=sys.stderr)
        return 1
    stray = sorted(set_tk - live)
    if stray:
        print(f"ERROR: --set tickers not in the live list: {stray}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(Path(__file__).with_name("dump_carry.py")), base_p, out_p]
    if drops:
        cmd += ["--drop", *drops]
    if sets:
        cmd += ["--set", *sets]
    print(f"scan_carry: live={len(live)} base={len(base_tk)} drops={len(drops)} "
          f"new={len(new)} sets={len(sets)}")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
