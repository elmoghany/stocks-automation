"""LEGACY-13 (volatility detector) shared helpers. Read-only use of the
CHAMPION-REPLAY engine (cp_sim / cp_feat / cp_lib): nothing is edited,
policies are injected by wrapping cp_sim's functions in-process.

Causality: every per-leg quantity a POLICY reads is taken at the decision
grid minute t (features from cp_feat, which `--verify` proved causal) or
from cp_detect's walk-forward score at 09:35/10:00 (scored only by folds
that ended before the row's date), forward-filled to later minutes.
Forward outcomes (mfe/mae) are computed for DIAGNOSIS only, never read
by a policy."""
import sys
from pathlib import Path

import numpy as np

PLAN = Path(__file__).resolve().parent
ROOT = PLAN.parent
sys.path.insert(0, str(PLAN))
import cp_lib as L          # noqa: E402
import cp_feat as F         # noqa: E402
import cp_sim as S          # noqa: E402

S.TICKETS = [10_000.0] * 7   # the mandate's $10k ticket, all seven
OOS_FROM = "2026-08-01"
FEATS = ("sigma1", "hi_gain", "rvol_now", "prior_range", "prevrange",
         "gain_now", "coil", "last", "dvol_now", "vwap_dist")


def r4_dates():
    return [d for d in F.dates() if d < OOS_FROM]


def load_scores():
    """{date: {sym: {335: s935, 360: s1000}}} from cp_detect's saved
    walk-forward scores (up30 target)."""
    z = np.load(ROOT / "data/massive/cp/scores.npz", allow_pickle=False)
    names = [str(x) for x in np.load(ROOT / "data/massive/cp/rows.npz",
                                     allow_pickle=False)["dates"]]
    out = {}
    for s, di, sym, tt in zip(z["score"], z["date"], z["sym"], z["tt"]):
        if not np.isfinite(s):
            continue
        m = L.mgrid(int(tt) // 100, int(tt) % 100)
        out.setdefault(names[int(di)], {}).setdefault(str(sym), {})[m] = float(s)
    return out


def score_at(sc_day, sym, t):
    """Latest walk-forward score at or before decision minute t."""
    if not sc_day:
        return np.nan
    d = sc_day.get(sym)
    if not d:
        return np.nan
    ks = [m for m in d if m <= t]
    return d[max(ks)] if ks else np.nan


# capture the decision minute on every leg (wrapping, not editing)
_orig_try = S._try_ticket


def _try_with_t(day, Fd, i, t, gi, budget, cfg, cost):
    leg = _orig_try(day, Fd, i, t, gi, budget, cfg, cost)
    if leg is not None:
        leg["t"], leg["gi"] = t, gi
    return leg


S._try_ticket = _try_with_t


def fwd(day, i, em, entry, end=L.M_1500):
    """DIAGNOSIS ONLY: max-high / min-low from the entry bar to 15:00."""
    p = day.printed[i, em:end + 1]
    if not p.any():
        return np.nan, np.nan
    h = day.h[i, em:end + 1][p]
    lo = day.l[i, em:end + 1][p]
    return float(h.max() / entry - 1), float(lo.min() / entry - 1)


def summ(legs, ndays, bps=(0, 6, 12, 18)):
    """$/ticket and $/month at several per-side costs."""
    if not legs:
        return {"n": 0}
    g = np.array([x["gross"] for x in legs])
    notl = np.array([x["shares"] * x["entry"] for x in legs])
    ex = np.array([x["shares"] * x["exit"] for x in legs])
    months = sorted({x["date"][:7] for x in legs})
    nm = max(len(months), 1)
    # months in the frame, not just traded months
    out = {"n": len(legs), "tkt_day": len(legs) / ndays,
           "avg_notional": float(notl.mean())}
    for b in bps:
        net = g - (notl + ex) * b / 1e4
        out[f"tkt_{b}"] = float(net.mean())
        out[f"mon_{b}"] = float(net.sum() / nm)
    byday = {}
    for x, v in zip(legs, g - (notl + ex) * 12 / 1e4):
        byday[x["date"]] = byday.get(x["date"], 0.0) + v
    top5 = sorted(g - (notl + ex) * 12 / 1e4)[-5:]
    out["ex_top5_mon_12"] = float((sum(byday.values()) - sum(top5)) / nm)
    mon = {}
    for d, v in byday.items():
        mon[d[:7]] = mon.get(d[:7], 0.0) + v
    out["months_pos_12"] = f"{sum(1 for v in mon.values() if v > 0)}/{nm}"
    return out
