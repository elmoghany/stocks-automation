"""LEADS-TEST leads 1 (TC regime) and 2 (quiet-near-the-high) on the honest
466-session panel (2024-10-22 .. 2026-09-01), one process, all jobs per date.
Writes data/research_oct/lt_legs.json.
    python plan/lt_run.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_feat as F                                         # noqa: E402
import lt_sim as T                                          # noqa: E402

OUT = T.ROOT / "data/research_oct/lt_legs.json"
M950 = T.L.mgrid(9, 50)


def jobs():
    j = {
        "r4ref": T.cfg(rank="coil", hyg=False, exit="r4"),
        "r4H": T.cfg(rank="coil"),
        "quiet": T.cfg(rank="quiet", t_start=M950, gain_max=0.40),
        "ret15": T.cfg(rank="ret15", t_start=M950, gain_max=0.40),
        "quietN": T.cfg(rank="quiet", t_start=M950, gain_max=0.40,
                        hyg=False, exit="r4"),
        "ret15N": T.cfg(rank="ret15", t_start=M950, gain_max=0.40,
                        hyg=False, exit="r4"),
        "quietH_r4x": T.cfg(rank="quiet", t_start=M950, gain_max=0.40,
                            exit="r4"),
        "quietS_nohyg": T.cfg(rank="quiet", t_start=M950, gain_max=0.40,
                              hyg=False),
    }
    for s in range(30):
        j[f"rand_{s}"] = T.cfg(rank="rand", seed=s)
        j[f"randQ_{s}"] = T.cfg(rank="rand", seed=s, t_start=M950,
                                gain_max=0.40)
    for s in range(10):
        j[f"randN_{s}"] = T.cfg(rank="rand", seed=s, t_start=M950,
                                gain_max=0.40, hyg=False, exit="r4")
    return j


KEEP = ("date", "sym", "dec", "entry_min", "entry", "exit_min", "exit",
        "reason", "g", "n_c", "n_12", "h_e", "notional")


def main():
    t0 = time.time()
    ds = F.dates()
    out = T.run_many(ds, jobs(), progress=True)
    res = {k: [{f: x[f] for f in KEEP} for x in v] for k, v in out.items()}
    OUT.write_text(json.dumps(dict(dates=ds, legs=res)))
    print("done", round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
