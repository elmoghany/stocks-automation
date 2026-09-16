"""WIDE-NET (2026-09-16) step 1b + 2a: the top-30 orderings and the
per-feature decile tables.  TRAIN WINDOW ONLY (2024-10-22 .. 2025-07-31).

Step 1b answers the user's literal instruction -- "buy the top-30 per day"
by several simple causal orderings, at each decision time, at each exit
horizon -- and reports what a $15,000 ticket did on average.

Step 2a is the first of the three pattern searches: for every feature,
split the train tickets into deciles and report win rate and mean net
dollars per ticket, so a monotone or a single-bucket edge is visible
before any model is fitted.

Usage: python plan/wn_mine.py
"""
import json
import sys

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from wn_lib import HNAMES, Table, write_json          # noqa: E402

TOPK = 30
ORDERINGS = {
    "dollar_volume": ("log_dv5", -1),
    "gap_desc": ("gap_vs_prevclose", -1),
    "gap_asc": ("gap_vs_prevclose", +1),
    "coil": ("coil", +1),                  # small rvol30/bar_range5 = quiet
    "gain_now_desc": ("ret_since_open", -1),
    "gain_now_asc": ("ret_since_open", +1),
    "rvol_desc": ("rvol_profile", -1),
    "vwap_below": ("dist_vwap_day", +1),
    "vwap_above": ("dist_vwap_day", -1),
    "price_asc": ("log_price", +1),
    "liquidity_desc": ("log_mdv20", -1),
    "random": (None, 0),
}


def topk_pnl(t, mask, score, h, k=TOPK):
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return np.zeros(0), np.zeros(0, "U10")
    key = t.date_i[idx].astype(np.int64) * 64 + t.dec_i[idx]
    order = np.lexsort((-score[idx], key))
    idx, key = idx[order], key[order]
    rank = np.zeros(len(idx), np.int64)
    starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    ends = np.r_[starts[1:], len(idx)]
    for s, e in zip(starts, ends):
        rank[s:e] = np.arange(e - s)
    sel = idx[rank < k]
    return t.pnl[h][sel], t.date_s[sel]


def main():
    t = Table()
    rng = np.random.default_rng(0)
    nd = t.ndays(0)
    print(f"train days = {nd}", flush=True)

    # ---------------- step 1b: top-30 orderings -------------------------
    rows = []
    for dec in t.dec:
        for name, (feat, sgn) in ORDERINGS.items():
            sc = (rng.random(len(t.date_i)) if feat is None
                  else sgn * t.f(feat).astype(np.float64))
            for h in HNAMES:
                m = t.mask(split=0, dec=dec, h=h)
                p, d = topk_pnl(t, m, sc, h)
                if p.size < 100:
                    continue
                rows.append({"dec": dec, "ordering": name, "h": h,
                             "n": int(p.size),
                             "per_ticket": round(float(p.mean()), 2),
                             "win": round(float((p > 0).mean()), 4),
                             "total": round(float(p.sum()), 0),
                             "per_day": round(float(p.sum()) / nd, 1)})
    write_json("mine_orderings.json", rows)
    rows.sort(key=lambda r: -r["per_ticket"])
    print("\n=== TOP-30 ORDERINGS, train, best 25 by $/ticket ===")
    print(f"{'dec':>6} {'ordering':>15} {'h':>5} {'n':>7} {'$/tkt':>8} "
          f"{'win':>6} {'$/day':>9}")
    for r in rows[:25]:
        print(f"{r['dec']:>6} {r['ordering']:>15} {r['h']:>5} {r['n']:>7} "
              f"{r['per_ticket']:>8.2f} {r['win']:>6.3f} {r['per_day']:>9.1f}")
    print("\n--- worst 8 ---")
    for r in rows[-8:]:
        print(f"{r['dec']:>6} {r['ordering']:>15} {r['h']:>5} {r['n']:>7} "
              f"{r['per_ticket']:>8.2f} {r['win']:>6.3f} {r['per_day']:>9.1f}")

    # ---------------- step 2a: decile tables ---------------------------
    RTH = ["09:35", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
           "14:00", "15:00"]
    dec_tables = {}
    print("\n=== DECILE TABLES (train, regular-session decisions, h=h30) ===")
    print(f"{'feature':>18} " + " ".join(f"d{i}" .rjust(7) for i in range(10))
          + f"  {'spread':>8}")
    for h in ("h30", "h120"):
        m = t.mask(split=0, dec=RTH, h=h)
        idx = np.flatnonzero(m)
        p = t.pnl[h][idx]
        tab = {}
        for f in t.feat:
            x = t.f(f)[idx].astype(np.float64)
            if f == "sic2":
                continue
            q = np.quantile(x, np.linspace(0, 1, 11))
            q[0], q[-1] = -np.inf, np.inf
            b = np.clip(np.searchsorted(q, x, "right") - 1, 0, 9)
            mu = np.array([p[b == i].mean() if (b == i).any() else np.nan
                           for i in range(10)])
            wr = np.array([(p[b == i] > 0).mean() if (b == i).any() else np.nan
                           for i in range(10)])
            nn = np.array([int((b == i).sum()) for i in range(10)])
            tab[f] = {"mean": [round(float(v), 1) for v in mu],
                      "win": [round(float(v), 3) for v in wr],
                      "n": nn.tolist(),
                      "edges": [round(float(v), 5) for v in q[1:-1]],
                      "spread": round(float(np.nanmax(mu) - np.nanmin(mu)), 1),
                      "best_decile": int(np.nanargmax(mu)),
                      "best_mean": round(float(np.nanmax(mu)), 1)}
            if h == "h30":
                print(f"{f:>18} " +
                      " ".join(f"{v:7.1f}" for v in mu) +
                      f"  {tab[f]['spread']:8.1f}")
        dec_tables[h] = tab
    write_json("mine_deciles.json", dec_tables)

    print("\n=== features ranked by best-decile mean $/ticket (h30) ===")
    rk = sorted(dec_tables["h30"].items(), key=lambda kv: -kv[1]["best_mean"])
    for f, v in rk[:12]:
        print(f"{f:>18} best decile d{v['best_decile']} "
              f"${v['best_mean']:+.1f}/tkt  n={v['n'][v['best_decile']]}  "
              f"win={v['win'][v['best_decile']]:.3f}")

    # ---------------- sector (SIC 2-digit) -----------------------------
    m = t.mask(split=0, dec=RTH, h="h30")
    idx = np.flatnonzero(m)
    s2 = t.f("sic2")[idx].astype(int)
    p = t.pnl["h30"][idx]
    sec = []
    for v in np.unique(s2):
        k = s2 == v
        if k.sum() < 300:
            continue
        sec.append({"sic2": int(v), "n": int(k.sum()),
                    "per_ticket": round(float(p[k].mean()), 2),
                    "win": round(float((p[k] > 0).mean()), 3)})
    sec.sort(key=lambda r: -r["per_ticket"])
    write_json("mine_sectors.json", sec)
    print("\n=== SIC-2 sectors, train, h30 (n>=300) ===")
    for r in sec[:8] + [{"sic2": -1, "n": 0, "per_ticket": 0, "win": 0}] + sec[-4:]:
        print(f"  sic2={r['sic2']:>3} n={r['n']:>6} ${r['per_ticket']:+8.2f} "
              f"win={r['win']:.3f}")


if __name__ == "__main__":
    main()
