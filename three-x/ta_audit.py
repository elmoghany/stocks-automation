"""Audit one TradingAgents state log: what data the agents really saw, and whether the future leaked in."""
import json
import re
import sys

path = rf"E:\strategy-repos\ta_results\backtest\{sys.argv[1]}\{sys.argv[2]}\TradingAgentsStrategy_logs\full_states_log_{sys.argv[3]}.json"
d = json.load(open(path, encoding="utf-8"))
for k in ("fundamentals_report", "news_report"):
    print("==", k, len(d[k]))
    print(d[k][:650].encode("ascii", "replace").decode())
print("== decision")
print(d.get("final_trade_decision", "")[:700].encode("ascii", "replace").decode())
blob = json.dumps(d)
as_of = sys.argv[3]
later = sorted(x for x in set(re.findall(r"20\d\d-\d\d-\d\d", blob)) if x > as_of)
print("dates after the analysis date:", later[:12])
print("says stale:", len(re.findall(r"stale", blob, re.I)), "| mentions real today:", "2026-11-04" in blob)
