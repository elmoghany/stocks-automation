"""WIDE-NET (2026-09-16): shared loading, splits and scoring.

Every wide-net script imports this so a split or a cost convention cannot
drift between the mining step and the validation step.

SPLITS
  train   2024-10-22 .. 2025-07-31   193 days   (pattern discovery ONLY)
  oos     2025-08-01 .. 2026-07-31   251 days   (touched once per pattern)
  aug26   2026-08-03 .. 2026-08-06     4 days   (the tail of the bar cache)

The m1w bar cache ends 2026-08-06, so "aug2026" is a 4-day stub and is
reported as such, never folded into the monthly average.
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0]
TAB = ROOT / "data" / "massive" / "wn" / "table.npz"
OUT = ROOT / "data" / "massive" / "wn"

TRAIN_END = "2025-08-01"        # exclusive
OOS_END = "2026-08-01"          # exclusive; the rest is the aug2026 stub
HNAMES = ["h15", "h30", "h60", "h120", "flat"]


class Table:
    def __init__(self, path=TAB):
        z = np.load(path, allow_pickle=False)
        self.dates = [str(x) for x in z["dates"]]
        self.syms = [str(x) for x in z["syms"]]
        self.feat = [str(x) for x in z["features"]]
        self.dec = [str(x) for x in z["dec_et"]]
        self.date_i = z["date_i"]
        self.sym_i = z["sym_i"]
        self.dec_i = z["dec_i"].astype(np.int32)
        self.F = z["F"]
        self.notional = z["notional"]
        self.printed = z["printed"]          # bar m+1 fillable (NOT causal)
        self.printed_m = z["printed_m"]      # bar m printed  (the candidate
                                             # gate; this one IS causal)
        self.fill_px = z["fill_px"]
        self.pnl = {h: z["pnl_" + h] for h in HNAMES}
        self.ok = {h: z["ok_" + h] for h in HNAMES}
        self.fidx = {f: i for i, f in enumerate(self.feat)}
        da = np.array(self.dates)
        self.split = np.where(da < TRAIN_END, 0,
                              np.where(da < OOS_END, 1, 2))[self.date_i]
        self.date_s = da[self.date_i]
        self.month = np.array([d[:7] for d in self.dates])[self.date_i]

    def f(self, name):
        return self.F[:, self.fidx[name]]

    def mask(self, split=None, dec=None, h="h30"):
        """The CAUSAL candidate set: bar m printed.  A candidate whose
        minute m+1 did not print books $0 (pnl is already 0 there), which
        is what plan/rl2/sim.py does -- the attempt is spent, not undone."""
        m = self.printed_m.copy()
        if split is not None:
            m &= np.isin(self.split, np.atleast_1d(split))
        if dec is not None:
            di = [self.dec.index(d) for d in np.atleast_1d(dec)]
            m &= np.isin(self.dec_i, di)
        return m

    def ndays(self, split):
        return int(np.sum([(d < TRAIN_END) if split == 0 else
                           (TRAIN_END <= d < OOS_END) if split == 1 else
                           (d >= OOS_END) for d in self.dates]))


# --------------------------------------------------------------- scoring
def summarize(pnl, dates, ndays, label=""):
    """$/ticket + monthly stats for a set of realized tickets."""
    pnl = np.asarray(pnl, float)
    if pnl.size == 0:
        return {"label": label, "tickets": 0, "total": 0.0, "per_ticket": 0.0,
                "per_month": 0.0, "months_pos": "0/0", "max_dd": 0.0,
                "win_rate": 0.0, "days": ndays}
    by_day = {}
    for d, p in zip(dates, pnl):
        by_day[d] = by_day.get(d, 0.0) + p
    ds = sorted(by_day)
    ser = np.array([by_day[d] for d in ds])
    eq = np.cumsum(ser)
    dd = float(np.min(eq - np.maximum.accumulate(eq))) if eq.size else 0.0
    mon = {}
    for d, p in by_day.items():
        mon[d[:7]] = mon.get(d[:7], 0.0) + p
    mv = np.array([mon[m] for m in sorted(mon)])
    nmon = max(ndays / 21.0, 1e-9)
    return {"label": label, "tickets": int(pnl.size),
            "total": round(float(pnl.sum()), 2),
            "per_ticket": round(float(pnl.mean()), 2),
            "per_month": round(float(pnl.sum()) / nmon, 2),
            "months_pos": f"{int((mv > 0).sum())}/{len(mv)}",
            "months_pos_frac": round(float((mv > 0).mean()), 3),
            "max_dd": round(dd, 2),
            "win_rate": round(float((pnl > 0).mean()), 4),
            "sharpe": round(float(ser.mean() / ser.std(ddof=1) * np.sqrt(252))
                            if ser.size > 1 and ser.std(ddof=1) > 0 else 0.0, 2),
            "days": ndays, "trade_days": len(ds),
            "best": round(float(pnl.max()), 2),
            "ex_best_total": round(float(pnl.sum() - pnl.max()), 2),
            "monthly": {m: round(mon[m], 1) for m in sorted(mon)}}


def single_pick(t, score, mask, h="h30", topk=1, rng=None):
    """One (or top-k) $15k ticket per (date, decision time) among `mask`.

    Ties and NaN scores are broken by `rng` (a seeded Generator) if given,
    otherwise by the stable index order.  Returns (pnl array, date array,
    row-index array).
    """
    idx = np.flatnonzero(mask & np.isfinite(score))
    if idx.size == 0:
        return np.zeros(0), np.zeros(0, "U10"), np.zeros(0, int)
    key = t.date_i[idx].astype(np.int64) * 64 + t.dec_i[idx]
    sc = score[idx]
    if rng is not None:
        sc = sc + rng.random(sc.size) * 1e-12
    order = np.lexsort((-sc, key))
    idx, key = idx[order], key[order]
    first = np.r_[True, key[1:] != key[:-1]]
    starts = np.flatnonzero(first)
    take = []
    ends = np.r_[starts[1:], len(idx)]
    for s, e in zip(starts, ends):
        take.append(idx[s:min(s + topk, e)])
    take = np.concatenate(take)
    return t.pnl[h][take], t.date_s[take], take


def write_json(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=1, default=str))
    return OUT / name
