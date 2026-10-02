"""SWING-EARNINGS: causal 'large-liquid' membership for minute-tape rules.
top600[d] = the 600 PIT-liquid names with the highest PRIOR-60-session median
dollar volume (the OPEN-UNIVERSE m1o rule, recomputed on se_panel so it
extends past 2026-08-06).  Membership never looks at day d's own session.
Writes data/research_oct/se_top600.json {date: [sym,...]} for event dates only,
and prints minute-tape coverage of top-600 events per split.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "research_oct"


def main():
    P = np.load(OUT / "se_panel.npz")
    dates, syms = P["dates"].tolist(), P["syms"].tolist()
    c, v, liq = P["c"].astype(np.float64), P["v"].astype(np.float64), P["liq"]
    dv = c * v
    ev = json.loads((OUT / "se_events.json").read_text())
    need = sorted({e["d1"] for e in ev})
    top = {}
    for i in need:
        with np.errstate(all="ignore"):
            mdv = np.nanmedian(dv[max(0, i - 60):i], axis=0)
        mdv = np.where(liq[i], mdv, -1)
        idx = np.argsort(-mdv)[:600]
        top[dates[i]] = [syms[j] for j in idx if mdv[j] > 0]
    (OUT / "se_top600.json").write_text(json.dumps(top))
    have = set()
    for f in (OUT / "se_m1").glob("part_*.npz"):
        have |= set(np.load(f)["keys"].tolist())
    cov = {}
    for e in ev:
        if e["sym"] in set(top[e["day1"]]):
            sp = "Y1" if e["day1"] <= "2025-07-31" else ("Y2" if e["day1"] <= "2026-07-31" else "OOS")
            cov.setdefault(sp, [0, 0])
            cov[sp][0] += 1
            cov[sp][1] += f"{e['sym']}|{e['day1']}" in have
    print("top-600 events / with tape:", cov)
    miss = [f"{e['sym']}|{e['day1']}" for e in ev
            if e["sym"] in set(top[e["day1"]]) and f"{e['sym']}|{e['day1']}" not in have]
    (OUT / "se_top600_missing.json").write_text(json.dumps(miss))


if __name__ == "__main__":
    main()
