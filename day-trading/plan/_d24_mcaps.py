"""Day-24: load the Robinhood market caps from the 06:28 scan into the
fundamentals cache halal_check reads.

Source: run_scan 5f132877 "Market cap" column, 2026-09-17 06:28 ET. Only the
agent can call Robinhood, so per update_rh_fundamentals.py's contract the
agent writes the numbers here. Values transcribed verbatim from that scan.
"""
import subprocess
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent

MCAPS = {
    "KXIN": 1.2788603e+07,
    "GNRC": 1.0332603874e+10,
    "DETX": 1.2363614e+07,
    "LRHC": 8.128693e+06,
    "CENN": 1.0808388e+07,
    "SPPL": 1.8398025e+07,
    "KFFB": 4.7266849e+07,
    "BRTX": 3.535687e+06,
    "WATT": 6.0521427e+07,
    "INLX": 2.2924469e+07,
    "COE": 6.1334685e+07,
    "VICR": 8.479489081e+09,
    "GLAS": 7.50170339e+08,
    "ARL": 2.56332922e+08,
    "GLOO": 3.72531336e+08,
    "RAPP": 1.984861691e+09,
    "BOLT": 6.992632e+06,
    "IMDX": 1.16531175e+08,
    "YI": 2.9733737e+07,
    "JL": 1.6024846e+07,
    "CHNR": 4.661199e+06,
}

for sym, mcap in MCAPS.items():
    r = subprocess.run(
        [sys.executable, str(DIR / "update_rh_fundamentals.py"), sym, repr(mcap)],
        capture_output=True, text=True)
    print(f"{sym:6} {r.stdout.strip() or r.stderr.strip()}")
