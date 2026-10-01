"""LEGACY-13 step 4: PAIRED exit test. R4's own 965 entries are held
fixed; only the exit rule changes, so every leg is its own control and
the sequence/path noise that dominates the re-simulation (lm13_policy)
drops out. Also post-hoc position sizing on the same legs.
Writes plan/lm13_paired.json."""
import json
import math
from collections import defaultdict

import numpy as np

import lm13_policy as P     # installs the target-capable _walk_exit

M, S, F, L = P.M, P.S, P.F, P.L
LO, HI, MED = P.LO_CUT, P.HI_CUT, P.MED
base_legs = json.load(open(M.PLAN / "lm13_base_legs.json"))["legs"]
BASE = S.default_cfg(rank="coil", stop_pct=None)


def cfg_for(name, s):
    fin = np.isfinite(s)
    c = dict(BASE)
    if name == "base":
        pass
    elif name.startswith("trail_m"):
        if fin:
            tw = float(np.clip(float(name[7:]) * s, 0.03, 0.40))
            c.update(trail_pct=tw, trail_lo=tw / 2, trail_hi=min(2 * tw, .6))
    elif name in ("trail30_hi", "trail30_all"):
        if name.endswith("all") or (fin and s > HI):
            c.update(trail_pct=.30, trail_lo=.15, trail_hi=.50)
    elif name in ("trail06_lo", "trail06_all"):
        if name.endswith("all") or (fin and s <= LO):
            c.update(trail_pct=.06, trail_lo=.03, trail_hi=.12)
    elif name.startswith("tgtsig"):
        c["tgt_full"] = float(name[6:]) * (s if fin else MED)
    elif name.startswith("tgtflat"):
        c["tgt_full"] = float(name[7:]) * MED
    elif name == "nobear_hi":
        if fin and s > HI:
            c["bearish_exit"] = False
    elif name == "nobear_all":
        c["bearish_exit"] = False
    elif name == "nobear_lo":
        if fin and s <= LO:
            c["bearish_exit"] = False
    else:
        raise ValueError(name)
    return c


NAMES = ["base", "trail_m8", "trail_m12", "trail_m20", "trail30_hi",
         "trail30_all", "trail06_lo", "trail06_all", "tgtsig3", "tgtsig6",
         "tgtsig12", "tgtflat3", "tgtflat6", "tgtflat12", "nobear_hi",
         "nobear_lo", "nobear_all"]

byd = defaultdict(list)
for k, x in enumerate(base_legs):
    byd[x["date"]].append(k)
R = {n: np.full(len(base_legs), np.nan) for n in NAMES}   # ret per leg
for d, ks in byd.items():
    Fd = F.load(d)
    day = L.load_day(d)
    si = {s: i for i, s in enumerate(day.syms)}
    for k in ks:
        x = base_legs[k]
        i = si[x["sym"]]
        for n in NAMES:
            m, px, why = S._walk_exit(day, Fd, i, x["entry_min"], x["entry"],
                                      cfg_for(n, x["sigma1"]))
            if px is not None:
                R[n][k] = px / x["entry"] - 1

sig = np.array([x["sigma1"] for x in base_legs], float)
notl = np.array([x["shares"] * x["entry"] for x in base_legs])
h1 = np.array([x["date"] < "2025-09-12" for x in base_legs])
chk = np.array([x["exit"] / x["entry"] - 1 for x in base_legs])
print("base reproduces R4 exits:", np.nanmax(np.abs(R["base"] - chk)))
groups = {"all": np.ones(len(sig), bool), "lo": sig <= LO,
          "mid": (sig > LO) & (sig <= HI), "hi": sig > HI,
          "nan": ~np.isfinite(sig), "H1": h1, "H2": ~h1}
out = {}
print("per $10k ticket, gross; delta vs base with paired t; cost of extra "
      "trips is zero (one round trip per leg either way)")
print(f"{'rule':12s} " + " ".join(f"{g:>16s}" for g in groups))
for n in NAMES:
    row = {}
    cells = []
    for g, m in groups.items():
        r = R[n][m] * 1e4
        dlt = (R[n][m] - R["base"][m]) * 1e4
        t = dlt.mean() / (dlt.std(ddof=1) / math.sqrt(len(dlt)) + 1e-12)
        # trimmed: drop the 5 best and 5 worst deltas
        srt = np.sort(dlt)
        tr = srt[5:-5].mean() if len(srt) > 20 else np.nan
        row[g] = dict(n=int(m.sum()), mean=float(r.mean()),
                      d=float(dlt.mean()), t=float(t), d_trim=float(tr),
                      d_usd_actual=float(((R[n][m] - R["base"][m])
                                          * notl[m]).sum()))
        cells.append(f"{r.mean():+6.0f}({dlt.mean():+5.0f},{t:+4.1f})")
    out[n] = row
    print(f"{n:12s} " + " ".join(f"{c:>16s}" for c in cells))
print("\ntrimmed delta (drop 5 best/5 worst legs), all / H1 / H2:")
for n in NAMES:
    print(f"{n:12s} {out[n]['all']['d_trim']:+6.1f} {out[n]['H1']['d_trim']:+6.1f}"
          f" {out[n]['H2']['d_trim']:+6.1f}   actual-$ delta total "
          f"{out[n]['all']['d_usd_actual']:+9.0f}")

# ---- post-hoc sizing on R4's actual legs (shares only scale down) ----
ret = R["base"]
months = len({x["date"][:7] for x in base_legs})
sz = {}
for lab, f in {
        "as-is (vol-capped $10k)": np.ones(len(sig)),
        "inverse-vol: x min(1, 0.0116/sig)": np.where(np.isfinite(sig),
                                                      np.minimum(1, MED / sig), 1.0),
        "CTRL vol-up: x min(1, sig/0.0116)": np.where(np.isfinite(sig),
                                                      np.minimum(1, sig / MED), 1.0),
        "skip thin (nan sig)": np.where(np.isfinite(sig), 1.0, 0.0),
        "half size lo tercile": np.where(sig <= LO, 0.5, 1.0)}.items():
    n_ = notl * f
    for b in (0, 12):
        pnl = ret * n_ - 2 * n_ * b / 1e4
        sz[f"{lab}|{b}"] = dict(usd_month=float(pnl.sum() / months),
                                per_tkt=float(pnl.sum() / max((f > 0).sum(), 1)),
                                avg_notional=float(n_[f > 0].mean()),
                                ex_top5=float((np.sort(pnl)[:-5].sum()) / months),
                                per_10k_deployed=float(pnl.sum() / n_.sum() * 1e4))
    print(f"SIZE {lab:36s} gross $/mo {sz[lab+'|0']['usd_month']:+7.0f} "
          f"net12 $/mo {sz[lab+'|12']['usd_month']:+7.0f} "
          f"net12 per $10k deployed {sz[lab+'|12']['per_10k_deployed']:+6.1f} "
          f"ex-top5 {sz[lab+'|12']['ex_top5']:+6.0f} avg notional "
          f"{sz[lab+'|12']['avg_notional']:.0f}")
out["_sizing"] = sz
json.dump(out, open(M.PLAN / "lm13_paired.json", "w"), default=float)
