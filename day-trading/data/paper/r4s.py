"""Compact p3_r4 --now status. usage: python data/paper/r4s.py HH:MM"""
import json, subprocess, sys
r = subprocess.run([sys.executable, "plan/p3_r4.py", "--now", sys.argv[1]], capture_output=True, text=True).stdout
for ln in r.splitlines():
    if ln.startswith("P3 "):
        d = json.loads(ln[3:])
        cl = [(c["sym"], c["entry_min"], c["entry"], c["exit_min"], c["exit"], c["reason"]) for c in d.get("closed_legs", [])]
        print({k: d.get(k) for k in ("now", "state", "action", "sym", "decision_min", "model_entry", "model_entry_min",
                                       "shares_cap", "last_check", "need_bars", "track_bars", "model_need_bars") if d.get(k) is not None}, "closed:", cl[-2:],
              "MODEL:", {k: (d.get("model") or {}).get(k) for k in ("state", "sym", "closed")})
        if d.get("action") not in ("ENTER", "NOTHING", "HOLD"):
            print(ln[:600])
    else:
        print(ln)
