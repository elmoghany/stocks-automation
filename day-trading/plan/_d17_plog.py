"""Append one position_log row to the Day-17 ledger and refresh the heartbeat.

Usage:
    python plan/_d17_plog.py ET LAST PNL PEAK PRESS10 WIDTH BINDING [NOTE]

Keeps the per-poll ledger write to a single short command, so the 1-minute
loop layer never has to embed a multi-line python heredoc in a shell string --
that pattern wedged the session's Bash shell once already today.
"""
import json
import sys
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "data" / "paper_days" / "2026-08-27.json"


def main():
    a = sys.argv[1:]
    et, last, pnl, peak, press10, width, binding = a[:7]
    note = a[7] if len(a) > 7 else ""
    d = json.load(open(P))
    row = {"et": et, "last": float(last), "pnl": float(pnl), "peak": float(peak),
           "pressure10": None if press10 == "na" else float(press10),
           "trail_width": width, "binding": float(binding),
           "binding_distance_pct": round((float(last) / float(binding) - 1) * 100, 2)}
    if note:
        row["note"] = note
    d.setdefault("position_log", []).append(row)
    d["ops"]["heartbeat_et"] = et
    if d.get("trades"):
        t = d["trades"][0]
        if t.get("status") == "OPEN":
            t["peak_since_entry"] = max(t.get("peak_since_entry", 0), float(peak))
            t["mark_pnl"] = float(pnl)
            t["mark_et"] = et
    json.dump(d, open(P, "w"), indent=1)
    print("logged", et, "pnl", pnl, "rows", len(d["position_log"]))


if __name__ == "__main__":
    main()
