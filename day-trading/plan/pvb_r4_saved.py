"""PAPER-VS-BT: R4 LIVE track replayed end-of-day from the session's OWN
saved inputs (scan snapshots data/paper/r4/snaps_{D}.jsonl, the agent's
bars data/rh_bars, the logged book checks; bar proxies where no check was
logged) through p3_r4_live.oct_replay -> p3_r4.live_step + watch_exit.
Separates logic differences (this replay vs paper) from data differences
(this replay vs the full-bar backtest). Writes data/pvb/r4_saved.json.

    python plan/pvb_r4_saved.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_lib as P                                          # noqa: E402
import p3_r4_live as V                                      # noqa: E402

DAYS = ("2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08",
        "2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15",
        "2026-10-16", "2026-10-19")
res = V.oct_replay(DAYS, proxy=True)
(P.DATA / "pvb" / "r4_saved.json").write_text(json.dumps(res, indent=1,
                                                         default=str))
