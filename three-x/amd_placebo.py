"""Is the earnings-timing edge about earnings? Re-run the two best rules with the report dates moved by -6 to +6 weeks.

Added after seeing run 1, so the two rules were chosen by their results. A quarter is about 13 weeks, so these shifts cover
nearly the whole cycle. If the real dates sit near the top, timing around reports may matter. If shifted dates do as well,
the result is about something else. Runs in Vibe-Trading. Writes results/amd_placebo.csv and a Lumibot job file.

Usage: venvs/vt/Scripts/python amd_placebo.py <lumibot job path>
"""
import json
import multiprocessing as mp
import os
import sys

import pandas as pd

import amd_cycle as A
import sweep

RULES = {"M_two_months_after_report": {"rule": "after", "cadence": "M", "a": 0, "b": 2},
         "W_cash_1w_before_until_1w_after": {"rule": "earn", "cadence": "W", "k": 1, "w": 1}}
SHIFTS = [w for w in range(-6, 7) if w != 0]


def moved(weeks):
    return [(pd.Timestamp(d) + pd.Timedelta(weeks=weeks)).strftime("%Y-%m-%d") for d in A.REPORTS]


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
    os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
    jobs = [A.job(f"{name}_shift{w}", {**params, "reports": moved(w)}) for name, params in RULES.items() for w in SHIFTS]
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        bad = [(n, e) for n, status, e in pool.imap_unordered(sweep.run_one, jobs) if status == "error"]
    if bad:
        print("errors", len(bad), str(bad[0])[:400])
    rows = []
    for name in RULES:
        real = A.curve(name)
        rows.append({"rule": name, "shift_weeks": 0, "three_years": real.iloc[-1] / real.iloc[0]})
        for w in SHIFTS:
            eq = A.curve(f"{name}_shift{w}")
            rows.append({"rule": name, "shift_weeks": w, "three_years": eq.iloc[-1] / eq.iloc[0]})
    table = pd.DataFrame(rows)
    table.to_csv(A.RES / "amd_placebo.csv", index=False)
    for name, part in table.groupby("rule"):
        real = part[part.shift_weeks == 0].three_years.iloc[0]
        rank = int((part.three_years > real).sum()) + 1
        print(f"{name}: real dates {real:.2f}x, rank {rank} of {len(part)}; shifted median {part[part.shift_weeks != 0].three_years.median():.2f}x")
        print("  " + ", ".join(f"{int(w):+d}w {m:.2f}" for w, m in zip(part.shift_weeks, part.three_years)))
    held = A.curve("hold")
    print(f"AMD held {held.iloc[-1] / held.iloc[0]:.2f}x")
    cfgs = [{"name": sweep.key(*A.job(n, p)), "codes": ["AMD"], "cfg": A.job(n, p)[1], "start": A.FROM, "end": "2026-11-03"} for n, p in RULES.items()]
    cfgs.append({"name": "AMD__amdcycle__hold", "codes": ["AMD"], "cfg": A.job("hold", {"rule": "hold", "cadence": "W"})[1], "start": A.FROM, "end": "2026-11-03"})
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(cfgs, f)


if __name__ == "__main__":
    main()
