"""LEGACY-1 mode A: full sequential cp_sim (R4 frame: coil rank, no -8% stop)
with the exit walker swapped for lm1_walk variants (monkeypatch, no file edits).
Each variant also runs 10 random-pick seeds in its own frame. IS 444 + OOS 22."""
import json, sys, time
sys.path.insert(0, r"C:\cornell\stocks-automation\day-trading\plan")
import cp_run as R
import cp_sim as S
from lm1_walk import V, walk
import cp_lib as L
VARS = json.loads(sys.argv[1])          # {"name": {walk overrides}}
NSEED = int(sys.argv[2]) if len(sys.argv) > 2 else 10
def _wx(day, Fd, i, em, entry, cfg):
    return walk(day, i, em, entry, cfg["xv"])
S._walk_exit = _wx
jobs = {}
for vn, ov in VARS.items():
    if "end" in ov: ov["end"] = L.mgrid(*ov["end"])
    x = V(**ov)
    jobs[vn] = (S.default_cfg(rank="coil", stop_pct=None, xv=x, exit_end=x["end"]), None, None)
    for k in range(NSEED):
        jobs[f"{vn}|RND{k}"] = (S.default_cfg(rank="none", rand=True, stop_pct=None, seed=k, xv=x, exit_end=x["end"]), None, None)
t0 = time.time(); out = {}
for tag, ds in (("IS", R.dates()), ("OOS", R.dates(True))):
    legs = S.run_many(ds, jobs, progress=False)
    out[tag] = {k: [(v["date"], v["exit"] / v["entry"] - 1, v["reason"], v["exit_min"] - v["entry_min"], v["entry_min"]) for v in L_] for k, L_ in legs.items()}
    out[tag + "_ndays"] = len(ds)
    print(tag, round(time.time() - t0), flush=True)
name = sys.argv[3] if len(sys.argv) > 3 else "seq"
json.dump(out, open(rf"C:\cornell\stocks-automation\day-trading\plan\pa_out\lm1_{name}.json", "w"), default=float)
print("done", round(time.time() - t0))
