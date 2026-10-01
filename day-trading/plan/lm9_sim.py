"""LEGACY-9 step 3: CHAMPION-REPLAY R4 re-run at $10k tickets with a CAUSAL
entry-cost gate inside the engine (a gated name is skipped and the slot goes
to the next name in coil order, exactly like any other failed arm), plus the
30-seed random control under the SAME gate.

Gate: half-spread = max(CS, AR)/2 on bars [em-30, em-1] (cp_cost estimator,
no impact).  em is the first print after the decision minute t, so bars in
(t, em) are empty: the gate only sees information dated <= t.

Cost charged (both reported): per side  k*half + (4.4 if <10:30 else 3.1),
k = 0.5 (central: max-of-two ~2x the median estimator, PESSIMISM-AUDIT 1c)
and k = 1.0 (upper = EVID).  Monkeypatches cp_sim in-process; edits nothing.
"""
import json, sys, time
from pathlib import Path
import numpy as np

P = Path(r"C:\cornell\stocks-automation\day-trading\plan")
sys.path.insert(0, str(P))
import cp_run as R
import cp_sim as S
from lm9_feat import half_at

S.TICKETS = [10_000.0] * 7
T1030 = 10 * 60 + 30 - 240
_orig_try = S._try_ticket
GATE = {"x": None}


def gated_try(day, Fd, i, t, gi, budget, cfg, cost):
    X = cfg.get("gate_h")
    if X is not None:
        em = S._next_print(day, i, t + 1)
        if em is None:
            return None
        if half_at(day, i, em)[0] > X:
            return None
    return _orig_try(day, Fd, i, t, gi, budget, cfg, cost)


S._try_ticket = gated_try
REC = {}


def mk(name):
    REC[name] = []

    def f(day, i, m, px, sh):
        h = half_at(day, i, m)[0]
        imp = 4.4 if m < T1030 else 3.1
        REC[name].append((h, imp, px * sh))
        return px * sh * (0.5 * h + imp) / 1e4
    return f


def main():
    t0 = time.time()
    ds = R.dates() + R.dates(oos=True)
    jobs = {}
    for X in (None, 8, 10, 12, 15, 20):
        jobs[f"R4_g{X}"] = (S.default_cfg(rank="coil", stop_pct=None, gate_h=X), mk(f"R4_g{X}"), None)
    for X in (None, 10):
        for k in range(30):
            nm = f"RND{k}_g{X}"
            jobs[nm] = (S.default_cfg(rank="none", rand=True, stop_pct=None, seed=k, gate_h=X), mk(nm), None)
    legs = S.run_many(ds, jobs, progress=True)
    out = {}
    for k, Lg in legs.items():
        rec = REC[k]
        assert len(rec) == 2 * len(Lg), (k, len(rec), len(Lg))
        rows = []
        for j, v in enumerate(Lg):
            (he, ie, ne), (hx, ix, nx) = rec[2 * j], rec[2 * j + 1]
            rows.append(dict(date=v["date"], sym=v["sym"], em=v["entry_min"], xm=v["exit_min"],
                             N=ne, g=v["gross"], h_e=he, h_x=hx,
                             c_c=(ne * (0.5 * he + ie) + nx * (0.5 * hx + ix)) / 1e4,
                             c_u=(ne * (he + ie) + nx * (hx + ix)) / 1e4,
                             reason=v["reason"]))
        out[k] = rows
    (P / "lm9_out/sim_legs.json").write_text(json.dumps({"dates": ds, "legs": out}, default=float))
    print("done", round(time.time() - t0))


if __name__ == "__main__":
    main()
