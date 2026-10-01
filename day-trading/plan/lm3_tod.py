"""LEGACY-3: time-of-day / ticket-index split of the FULL honest C37F
ledger (rotation_trades_C37F_rs_def.json = C37F-df: hygiene + RS_CROSS +
RS_DEFER + honest fills, all 445 days). $ normalised to a $10k ticket.
Usage: python plan/lm3_tod.py"""
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
L = json.loads((ROOT / "data/massive/rotation_trades_C37F_rs_def.json")
               .read_text())
grp = defaultdict(list)
for x in L:
    grp[(x["date"], x["ticket"])].append(x)
legs = []
for (d, tk), g in grp.items():
    no = sum(y["shares"] * y["entry"] for y in g)
    if no <= 0:
        continue
    legs.append(dict(d=d, tk=tk, t=g[0]["entry_time"][11:16],
                     r=sum(y["pnl"] for y in g) / no * 10_000))
ndays = 445


def b(t):
    for lim, nm in (("09:45", "09:30-09:45"), ("10:00", "09:45-10:00"),
                    ("10:30", "10:00-10:30"), ("11:30", "10:30-11:30"),
                    ("13:00", "11:30-13:00"), ("99", "13:00-14:30")):
        if t < lim:
            return nm


def show(title, key):
    g = defaultdict(list)
    for x in legs:
        g[key(x)].append(x)
    print(f"\n### {title}\n\n| bucket | n | win | gross $/tkt | net@15 | "
          "Y1 | Y2 | sum gross $ (10k) |\n|---|---:|---:|---:|---:|---:|"
          "---:|---:|")
    for k in sorted(g):
        v = [x["r"] for x in g[k]]
        a = [x["r"] for x in g[k] if x["d"] < "2025-08-01"]
        c = [x["r"] for x in g[k] if x["d"] >= "2025-08-01"]
        print(f"| {k} | {len(v)} | {sum(1 for y in v if y > 0) / len(v):.0%}"
              f" | {st.fmean(v):+.1f} | {st.fmean(v) - 30:+.1f} | "
              f"{st.fmean(a) if a else 0:+.1f} | "
              f"{st.fmean(c) if c else 0:+.1f} | {sum(v):+,.0f} |")


print(f"legs {len(legs)}, all-mean {st.fmean(x['r'] for x in legs):+.1f}")
show("entry time", lambda x: b(x["t"]))
show("ticket index", lambda x: x["tk"])
