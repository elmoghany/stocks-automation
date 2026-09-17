"""CHAMPION-REPLAY: the causal cross-section table.

One row per (date, decision minute, name on the live scanner). Features
come straight out of the verified cp_feat grid (bars <= the decision
minute, plus prior sessions); labels are computed from bars strictly
after it and are never fed back into anything.

Decision minutes: 09:35, 10:00, 10:30, 11:00, 12:00, 13:00, 14:00.
Membership: the LIVE scanner's rule (last close >= +10% over prev
close, last >= $2) -- see cp_lib for why that set is complete here.

    python plan/cp_scan.py --build
Output: data/massive/cp/rows.npz (+ cols.json)
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/massive/cp"

TIMES = [(9, 35), (10, 0), (10, 30), (11, 0), (12, 0), (13, 0), (14, 0)]
LABELS = ["r30", "r60", "r120", "r1500", "mfe1500", "mae1500",
          "up30", "up50", "up100", "gain_full_HINDSIGHT"]


def build(days=None):
    OUT.mkdir(parents=True, exist_ok=True)
    dates = F.dates()
    if days:
        dates = dates[:int(days)]
    cols = None
    rows, msym, mdate, mt = [], [], [], []
    for di, date in enumerate(dates):
        Fd = F.load(date)
        day = L.load_day(date)
        if Fd is None or day is None:
            continue
        grid = list(Fd["grid"])
        gpos = {m: i for i, m in enumerate(grid)}
        last = day.last
        feats = [k for k in F.KEYS if k != "vol5"]
        stat = [k for k in F.STATIC if k not in ("gain_full", "rvol_pool")]
        if cols is None:
            cols = feats + stat + LABELS
        for hh, mm in TIMES:
            T = L.mgrid(hh, mm)
            gi = gpos[T]
            msk = Fd["elig_last"][:, gi]
            if not msk.any():
                continue
            idx = np.where(msk)[0]
            base = last[:, T]
            fw = day.fwd(T, L.M_1500)
            lab = {}
            for h, nm in ((30, "r30"), (60, "r60"), (120, "r120")):
                lab[nm] = last[:, min(T + h, L.M_1500)] / base - 1.0
            lab["r1500"] = last[:, L.M_1500] / base - 1.0
            lab["mfe1500"] = fw["fwd_max"] / base - 1.0
            lab["mae1500"] = fw["fwd_min"] / base - 1.0
            for k, thr in (("up30", .30), ("up50", .50), ("up100", 1.0)):
                lab[k] = (lab["mfe1500"] >= thr).astype(float)
            lab["gain_full_HINDSIGHT"] = Fd["gain_full"]
            blk = [np.asarray(Fd[c], float)[:, gi][idx] for c in feats]
            blk += [np.asarray(Fd[c], float)[idx] for c in stat]
            blk += [np.asarray(lab[c], float)[idx] for c in LABELS]
            rows.append(np.vstack(blk).T.astype(np.float32))
            msym.extend(str(Fd["syms"][i]) for i in idx)
            mdate.extend([di] * len(idx))
            mt.extend([hh * 100 + mm] * len(idx))
        if (di + 1) % 50 == 0:
            print(f"  {di+1}/{len(dates)} {date} "
                  f"rows={sum(len(r) for r in rows)}", flush=True)
    X = np.vstack(rows)
    np.savez_compressed(OUT / "rows.npz", X=X, sym=np.array(msym),
                        date=np.array(mdate, np.int32),
                        tt=np.array(mt, np.int32), dates=np.array(dates))
    (OUT / "cols.json").write_text(json.dumps(cols))
    print(f"cp_scan: {X.shape[0]} rows x {X.shape[1]} cols over "
          f"{len(dates)} dates")


def load():
    z = np.load(OUT / "rows.npz", allow_pickle=False)
    cols = json.loads((OUT / "cols.json").read_text())
    return dict(X=z["X"], sym=z["sym"], date=z["date"], tt=z["tt"],
                dates=z["dates"], cols=cols,
                ci={c: i for i, c in enumerate(cols)})


if __name__ == "__main__":
    a = sys.argv[1:]
    build(a[a.index("--days") + 1] if "--days" in a else None)
