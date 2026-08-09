"""Unattended Z4xx chain (2026-08-09).

Order matters:
 0. IDENTITY GATE -- pandas was force-upgraded to 3.x tonight; if S095
    does not reproduce EXACTLY under the new library, STOP EVERYTHING
    (results would be incomparable with the whole campaign).
 1. Z404/Z405 (local data only).
 2. Wait for the halal build to exit (avoid two yfinance consumers).
 3. fetch_earnings_yf.py (2,045 symbols, ~45 min).
 4. build_earnings_flags.py (local join).
 5. Z400-Z403 + ZC40.
Every step logs loudly; any failure aborts the chain rather than
producing silently-wrong numbers.
"""

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def log(msg):
    print(f"[chain] {msg}", flush=True)


def run(cmd):
    log("RUN " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        log(f"ERROR: {' '.join(cmd)} exited {r.returncode} -- ABORT")
        sys.exit(1)


def main():
    # 0. identity gate under pandas 3
    spec = importlib.util.spec_from_file_location(
        "px", ROOT / "plan/penny_x100.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["px"] = m
    spec.loader.exec_module(m)
    stored = m.load_results()
    for lab in ("year", "y2025"):
        ref = stored[f"S095|{lab}"]["total"]
        out = m.run_experiment(dict(m.BYID["S095"], id="VCHK3"), lab)
        if out["total"] != ref:
            log(f"ERROR: IDENTITY FAIL under pandas 3 ({lab}: "
                f"{out['total']:+,} vs stored {ref:+,}) -- ABORTING "
                f"the entire chain. Nothing was run.")
            sys.exit(1)
        log(f"identity {lab}: EXACT ({ref:+,})")

    # 1. local experiments
    run([sys.executable, "plan/penny_x100.py",
         "--ids", "Z404,Z405", "--shard", "Z5"])

    # 2. wait for the halal build to release yfinance
    log("waiting for halal build (build_halal_universe) to exit...")
    while True:
        chk = subprocess.run(
            ["powershell", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name like "
             "'python%'\" | Where-Object {$_.CommandLine -match "
             "'build_halal_universe'}).Count"],
            capture_output=True, text=True)
        if (chk.stdout or "").strip() in ("", "0"):
            break
        time.sleep(120)
    log("halal build gone -- yfinance is free")

    # 3-4. earnings data
    run([sys.executable, "plan/fetch_earnings_yf.py"])
    run([sys.executable, "plan/build_earnings_flags.py"])
    nf = len(json.loads((ROOT / "data/earnings_flags.json").read_text()))
    log(f"{nf:,} earnings-day candidate flags")
    if nf < 50:
        log("ERROR: implausibly few earnings flags -- ABORT before the "
            "gated experiments produce garbage")
        sys.exit(1)

    # 5. earnings experiments
    run([sys.executable, "plan/penny_x100.py",
         "--ids", "Z400,Z401,Z402,Z403,ZC40", "--shard", "Z6"])
    log("CHAIN COMPLETE")


if __name__ == "__main__":
    main()
