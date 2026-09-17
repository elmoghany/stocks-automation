"""Day-24 helper: compact one-line-per-symbol summary of a live_halal --json dump."""
import json
import sys
from pathlib import Path

d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
passes = []
for s, v in d.items():
    verdict = str(v.get("verdict"))
    reason = str(v.get("fail_reason") or "")[:95]
    print(f"{s:6} {verdict:20} loan={v.get('loan_pct')} cash={v.get('cash_pct')} "
          f"comb={v.get('combined')} mcap={v.get('mcap')} :: {reason}")
    if verdict == "PASS":
        passes.append(s)
print()
print("Q1_PASS:", passes)
