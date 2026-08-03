"""Price-cap matrix ($16/$14/$12/$10) for the top-3 performers:

  A2 = $2-cap, no float, 7-noon, TOP-2 gappers/day   (+$55,373 at $16)
  B3 = $2-cap, no float, 7-4PM,  TOP-2 gappers/day   (+$54,345 at $16)
  B2 = $2-cap, no float, 7-2PM,  top-1               (+$53,606 at $16)

Everything else fixed: $15k/position, 10% vol cap, trail 20/stop 5,
ORB+dip entries, halal + upward sectors + up>=10% + rvol>=5x.
"""

import importlib.util
import sys
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plan"))
_v = importlib.util.spec_from_file_location(
    "v2a", ROOT / "plan" / "penny_v2a_variants.py")
v2a = importlib.util.module_from_spec(_v)
_v.loader.exec_module(v2a)

BASES = [
    ("A2 noon top-2", dtime(12, 0), 2),
    ("B3 full-day top-2", dtime(16, 0), 2),
    ("B2 7-2PM top-1", dtime(14, 0), 1),
]

print(f"{'CONFIG x PRICE CAP':<38} {'days':>4} "
      f"{'total':>11} {'avg/day':>9} {'win':>7} {'>=1k':>4} {'worst':>9}")
for name, end_t, top_n in BASES:
    print("-" * 92)
    for cap in (16.0, 14.0, 12.0, 10.0):
        v2a.run(f"{name}  cap ${cap:.0f}", v2a.POOL_BAND, end_t, cap,
                top_n=top_n)
