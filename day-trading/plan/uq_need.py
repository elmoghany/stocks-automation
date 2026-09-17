"""UNIVERSE+QUOTES (2026-09-16): the break-even information coefficient
UNDER LIMIT FILLS -- the same measurement plan/wn_need.py made under
market fills, so the two are directly comparable.

wn_need's answer, on the incumbent 61-name universe with a next-bar-open
market fill and 10 bps a side: $7,500/month needs a sustained daily
cross-sectional rho of 0.477 with one ticket a day, 0.267 with three,
0.189 with seven, 0.150 with seven across all nine RTH slots -- against
an achieved rho of 0.033.

The point of attacking the toll is that it should move those numbers. So
the identical machinery is re-run on the LIMIT-FILLED P&L cross-section:

    score = rho * z(pnl) + sqrt(1 - rho^2) * noise
    buy the top-k by that score at each slot, sum the realized P&L

with one difference that is the entire experiment: a name's P&L is the
limit ticket's, and a name whose limit did not fill contributes $0 -- the
attempt is spent. That makes high-rho configurations WORSE than they look
under market fills (you cannot buy the winner if it never trades down to
your limit) and low-rho configurations BETTER (the toll is smaller).
Which effect wins is the measurement.

Usage:
  python plan/uq_need.py --stage matrix [--offset 10] [--wait 1]
  python plan/uq_need.py --stage curve  [--offset 10] [--wait 1]
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import uq_econ as UE                                          # noqa: E402
import uq_fills as UF                                         # noqa: E402
from wn_lib import Table                                      # noqa: E402

OUT = HERE / "uq_out"
RTH = UF.RTH_DEC
RHOS = [0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.70, 1.0]
TARGET = 7500.0


def mat_path(h, offset, wait, split):
    return OUT / f"need_matrix_{h}_o{offset:.0f}_w{wait}_s{split}.npz"


def stage_matrix(h="h30", offset=10.0, wait=1, split=1, exit_bps=UF.FEE_BPS):
    t = Table()
    days = UE.cached_days(t, split)
    if not days:
        raise SystemExit("no tape-complete day in this split yet")
    di = {d: i for i, d in enumerate(t.dates)}
    dec_i = [UF.DEC_ET.index(x) for x in RTH]
    rows = np.flatnonzero(t.printed_m
                          & np.isin(t.date_i, [di[d] for d in days])
                          & np.isin(t.dec_i, dec_i))
    print(f"matrix: {len(rows):,} eligible tickets over {len(days)} days",
          flush=True)
    res = UE.price_rows(t, rows, h, offsets=[offset], nwait=[wait],
                        exit_bps=exit_bps, spread_offset=False)
    ht = res["have_tape"]
    keep = rows[ht]
    np.savez_compressed(
        mat_path(h, offset, wait, split),
        rows=keep, date_i=t.date_i[keep], dec_i=t.dec_i[keep],
        base=res["base"][ht], lim=res["lim"][(offset, wait)][ht],
        filled=res["filled"][(offset, wait)][ht])
    print(f"saved {mat_path(h, offset, wait, split).name}: "
          f"{int(ht.sum()):,} rows, fill rate "
          f"{float(res['filled'][(offset, wait)][ht].mean()):.3f}")


def curve(date_i, dec_i, pnl, ndays, ks=(1, 3, 7), seeds=12, slots=None):
    """rho -> $/month for top-k per (day, slot)."""
    key = date_i.astype(np.int64) * 64 + dec_i
    if slots is not None:
        m = np.isin(dec_i, slots)
        key, pnl = key[m], pnl[m]
    order = np.argsort(key, kind="stable")
    key, pnl = key[order], pnl[order]
    st = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    en = np.r_[st[1:], len(key)]
    nmonth = ndays / 21.0
    out = {}
    for k in ks:
        rowsk = []
        for rho in RHOS:
            tot = []
            ns = seeds if rho not in (0.0, 1.0) else max(seeds, 20)
            for s in range(ns):
                rng = np.random.default_rng(777 + s)
                acc, ntk = 0.0, 0
                for a, b in zip(st, en):
                    q = pnl[a:b]
                    n = b - a
                    if n == 0:
                        continue
                    if rho >= 1.0:
                        sc = q
                    elif rho <= 0.0:
                        sc = rng.standard_normal(n)
                    else:
                        z = (q - q.mean()) / (q.std() or 1.0)
                        sc = rho * z + np.sqrt(1 - rho ** 2) * \
                            rng.standard_normal(n)
                    take = np.argsort(-sc)[:k]
                    acc += float(q[take].sum())
                    ntk += len(take)
                tot.append((acc, ntk))
            a = np.array([x[0] for x in tot])
            nt = float(np.mean([x[1] for x in tot]))
            rowsk.append({"rho": rho,
                          "per_month": round(float(a.mean() / nmonth), 0),
                          "per_ticket": round(float(a.mean() / max(nt, 1)), 2),
                          "tickets": int(nt)})
        out[k] = rowsk
    return out


def needed_rho(rows, target=TARGET):
    xs = [r["rho"] for r in rows]
    ys = [r["per_month"] for r in rows]
    for i in range(1, len(xs)):
        if ys[i - 1] < target <= ys[i]:
            f = (target - ys[i - 1]) / max(ys[i] - ys[i - 1], 1e-9)
            return round(xs[i - 1] + f * (xs[i] - xs[i - 1]), 3)
    return None if ys[-1] < target else 0.0


def stage_curve(h="h30", offset=10.0, wait=1, split=1):
    f = mat_path(h, offset, wait, split)
    if not f.exists():
        raise SystemExit(f"run --stage matrix first ({f.name})")
    z = np.load(f)
    nd = len(set(z["date_i"].tolist()))
    rep = {"h": h, "offset_bps": offset, "wait_min": wait, "split": split,
           "days": nd, "rows": int(len(z["base"])),
           "fill_rate": round(float(z["filled"].mean()), 4)}
    for name, p in (("market", z["base"]), ("limit", z["lim"])):
        c = curve(z["date_i"], z["dec_i"], p, nd)
        rep[name] = {str(k): v for k, v in c.items()}
        rep[f"rho_needed_{name}"] = {
            str(k): needed_rho(v) for k, v in c.items()}
        # all nine slots pooled, i.e. "any RTH time"
        s9 = curve(z["date_i"], np.zeros_like(z["dec_i"]), p, nd, ks=(1, 7))
        rep[f"rho_needed_{name}_anyslot"] = {
            str(k): needed_rho(v) for k, v in s9.items()}
    (OUT / f"need_{h}_o{offset:.0f}_w{wait}_s{split}.json").write_text(
        json.dumps(rep, indent=1, default=str))
    print(json.dumps({k: v for k, v in rep.items()
                      if k not in ("market", "limit")}, indent=1))
    print(f"\n{'rho':>6} | {'market $/mo k=1':>16} {'limit $/mo k=1':>15} "
          f"| {'market k=7':>12} {'limit k=7':>11}")
    for i, r in enumerate(rep["market"]["1"]):
        print(f"{r['rho']:>6.2f} | {r['per_month']:>16,.0f} "
              f"{rep['limit']['1'][i]['per_month']:>15,.0f} | "
              f"{rep['market']['7'][i]['per_month']:>12,.0f} "
              f"{rep['limit']['7'][i]['per_month']:>11,.0f}")
    return rep


if __name__ == "__main__":
    a = sys.argv
    g = lambda f, d: (type(d)(a[a.index(f) + 1]) if f in a else d)  # noqa: E731
    OUT.mkdir(parents=True, exist_ok=True)
    st = g("--stage", "matrix")
    if st == "matrix":
        stage_matrix(g("--h", "h30"), g("--offset", 10.0), g("--wait", 1),
                     g("--split", 1), g("--exit", UF.FEE_BPS))
    else:
        stage_curve(g("--h", "h30"), g("--offset", 10.0), g("--wait", 1),
                    g("--split", 1))
