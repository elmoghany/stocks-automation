"""LEGACY-4 bias check: the 444-session premarket-entry numbers in
lm4_largecap.py are drawn from the panel (names that later printed +10% in
the regular session). On the 12 census days, compare the panel-drawn set
with the honest census set (PM-ONLY included) slice by slice, so the size
of the survivorship bias is measured rather than assumed.

    python plan/lm4_check.py
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lm4_premkt as LM                                     # noqa: E402
import lm4_largecap as LC                                   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    A = LM.part_a()
    cdates = sorted({r["date"] for r in A})
    st, _ = LM.static_table()
    ev = pickle.load(open(ROOT / "data/massive/cat/events.pkl", "rb"))
    pmx = {k: f for k, f in st.items() if k[0] in cdates
           and np.isfinite(f["pm_high_gain"]) and f["pm_high_gain"] >= 0.10}
    for f in pmx.values():
        if not np.isfinite(f["shares"]):
            f["shares"] = np.nan
    R = LC.run("PM", pmx, ev)
    rk = {"x_open": "0930", "x_0945": "0945", "x_1000": "1000",
          "x_1500": "1500"}
    sl = {
        "all": (lambda a: True, lambda r: True),
        "mcap>=2B": (lambda a: a["mcap"] >= 2e9, lambda r: r["mcap"] >= 2e9),
        "mcap>=2B & cross>=07:00": (
            lambda a: a["mcap"] >= 2e9 and a["cross_min"] >= 180,
            lambda r: r["mcap"] >= 2e9 and r["m0"] >= 180),
        "cross>=07:00": (lambda a: a["cross_min"] >= 180,
                         lambda r: r["m0"] >= 180),
        "cat": (lambda a: a["cat"] == 1, lambda r: r["cat"] == 1),
    }
    print(f"census days {len(cdates)}; panel PM rows on those days {len(R)}\n")
    print("| slice | census n (PM-ONLY share) | census ->open / 09:45 / 10:00 / 15:00 "
          "| panel n | panel ->open / 09:45 / 10:00 / 15:00 |")
    print("|---|---|---|---|---|")
    for name, (fa, fr) in sl.items():
        a = [x for x in A if fa(x)]
        p = [x for x in R if fr(x)]
        po = np.mean([x["kind"] == "PM-ONLY" for x in a]) if a else np.nan
        ca = " / ".join(f"{np.nanmean([x[k] for x in a])*1e4:+.0f}"
                        for k in rk) if a else "-"
        pa = " / ".join(f"{np.nanmean([x[v] for x in p])*1e4:+.0f}"
                        for v in rk.values()) if p else "-"
        print(f"| {name} | {len(a)} ({po:.0%}) | {ca} | {len(p)} | {pa} |")
    # large-cap, late-cross census rows in detail
    print("\ncensus rows mcap>=2B & cross>=07:00:")
    for x in sorted((x for x in A if x["mcap"] >= 2e9 and x["cross_min"] >= 180),
                    key=lambda x: x["date"]):
        print(f"  {x['date']} {x['sym']:6} {x['kind']:11} cross {x['cross_hhmm']} "
              f"mcap {x['mcap']/1e9:.1f}B cat {x['cat']} open {x['x_open']*1e4:+.0f} "
              f"1000 {x['x_1000']*1e4:+.0f} 1500 {x['x_1500']*1e4:+.0f}")
