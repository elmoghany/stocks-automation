"""Item 1: what does 2x of held require? Hindsight ceilings (perfect foresight, long/cash, next-open fills, 5 bp per side) and the size of AMD's falls.

Everything here is HINDSIGHT: it uses the whole window to find the best trades. It is a ceiling, not a strategy.
Part A: best K round trips by dynamic programming on fill prices (every open, last close as exit if still in).
Part B: AMD falls (zigzag on closes, reversal threshold 10/15/20/25%): count, total size, and what dodging all of them would give.
Part C: how late can the exit/re-entry be, and how many falls can be missed, before 2x of held is lost.
"""
import numpy as np
import pandas as pd
from common import *

f = load_amd()
o, c, idx = f.open.values, f.close.values, f.index
W = windows(idx)
CB, CS = np.log(1 + COST), np.log(1 - COST)


def best_k(P, kmax):
    """Max total log gain with at most k non-overlapping buy-then-sell trades on price list P, for k=0..kmax. Also back-pointers."""
    L = np.log(P)
    N = len(L)
    NEG = -1e18
    hold = np.full(kmax + 1, NEG)
    cash = np.full(kmax + 1, NEG)
    cash[0] = 0.0
    bought = np.zeros((N, kmax + 1), dtype=bool)
    sold = np.zeros((N, kmax + 1), dtype=bool)
    for t in range(N):
        nh = hold.copy()
        cand = np.full(kmax + 1, NEG)
        cand[1:] = cash[:-1] - L[t] - CB
        mask = cand > nh
        nh[mask] = cand[mask]
        bought[t] = mask
        nc = cash.copy()
        cand2 = hold + L[t] + CS
        m2 = cand2 > nc
        nc[m2] = cand2[m2]
        sold[t] = m2
        hold, cash = nh, nc
    res = {}
    for k in range(1, kmax + 1):
        best_j = int(np.argmax(cash[:k + 1]))
        res[k] = (cash[best_j], best_j)
    return res, bought, sold, L


def trades_for(bought, sold, N, j):
    """Backtrack the optimal j-trade path ending in cash at time N-1."""
    t, k, h = N - 1, j, False
    legs = []
    sell_t = None
    while t >= 0 and (k > 0 or h):
        if not h:
            if sold[t, k]:
                sell_t = t
                h = True
            t -= 1
        else:
            if bought[t, k]:
                legs.append((t, sell_t))
                h = False
                k -= 1
            t -= 1
    return legs[::-1]


def part_a():
    rows, text = [], []
    for name, (lo, hi) in W.items():
        P = np.r_[o[lo:hi], c[hi - 1]]
        yrs = (hi - lo) / 252
        H = hold_mult(o, c, lo, hi)
        scale = yrs / 3.0
        ks = sorted(set([4, 8, 12, 20, 40] + ([int(round(k * scale)) for k in (4, 8, 12, 20)] if name == "early" else [])))
        kmax = max(ks)
        res, bought, sold, L = best_k(P, kmax)
        kbig = 400 if name == "recent" else 700
        res_big, _, _, _ = best_k(P, kbig)
        ubig = max(v[0] for v in res_big.values())
        for k in ks:
            g = np.exp(res[k][0])
            rows.append({"window": name, "years": round(yrs, 2), "round_trips_max": k, "trips_used": res[k][1], "ceiling_x": g, "held_x": H, "ceiling_over_held": g / H,
                         "needed_x_for_2x_held": 2 * H, "share_of_log_ceiling_needed": np.log(2 * H) / np.log(g), "share_of_log_edge_needed": np.log(2) / np.log(g / H) if g > H else np.nan})
        rows.append({"window": name, "years": round(yrs, 2), "round_trips_max": "no limit", "trips_used": "", "ceiling_x": np.exp(ubig), "held_x": H, "ceiling_over_held": np.exp(ubig) / H,
                     "needed_x_for_2x_held": 2 * H, "share_of_log_ceiling_needed": np.log(2 * H) / ubig, "share_of_log_edge_needed": np.log(2) / (ubig - np.log(H))})
        if name == "recent":
            for k in (4, 8, 12):
                legs = trades_for(bought, sold, len(P), res[k][1])
                text.append(f"\nPerfect-foresight best {k} round trips, Aug 2023 to Nov 2026 (HINDSIGHT), fills at the open:")
                for b, s in legs:
                    bd = idx[lo + b].date()
                    sd = idx[lo + s].date() if s < hi - lo else "last close (still in)"
                    text.append(f"  buy {bd} at {P[b]:7.2f}  sell {sd} at {P[s]:7.2f}  {P[s] / P[b] - 1:+7.1%}")
    return pd.DataFrame(rows), "\n".join(text)


def zigzag(cl, thr):
    """Peaks and troughs of closes with reversal threshold thr. Uses the whole window (HINDSIGHT)."""
    pts = []
    mode = 0
    hi_i = lo_i = 0
    for i in range(1, len(cl)):
        if mode == 0:
            if cl[i] > cl[hi_i]:
                hi_i = i
            if cl[i] < cl[lo_i]:
                lo_i = i
            if cl[i] <= cl[hi_i] * (1 - thr):
                pts.append(("peak", hi_i)); mode = -1; lo_i = i
            elif cl[i] >= cl[lo_i] * (1 + thr):
                pts.append(("trough", lo_i)); mode = 1; hi_i = i
        elif mode == -1:
            if cl[i] < cl[lo_i]:
                lo_i = i
            if cl[i] >= cl[lo_i] * (1 + thr):
                pts.append(("trough", lo_i)); mode = 1; hi_i = i
        else:
            if cl[i] > cl[hi_i]:
                hi_i = i
            if cl[i] <= cl[hi_i] * (1 - thr):
                pts.append(("peak", hi_i)); mode = -1; lo_i = i
    return pts


def falls_from(pts):
    return [(a[1], b[1]) for a, b in zip(pts[:-1], pts[1:]) if a[0] == "peak" and b[0] == "trough"]


def pos_dodge(n, lo, hi, falls, d_out=0, d_in=0, keep=None):
    """Hold the whole window except during dodged falls. Exit decision at close peak+d_out, re-entry decision at close trough+d_in (d=0 is perfect timing at the close).
    keep[j]=True means fall j is NOT dodged."""
    pos = np.zeros(n)
    pos[lo - 1:hi] = 1.0
    for j, (p, t) in enumerate(falls):
        if keep is not None and keep[j]:
            continue
        a, b = p + d_out, t + d_in
        if a >= b:
            continue
        pos[a:b] = 0.0
    return pos


def part_b():
    rows, store = [], {}
    for name, (lo, hi) in W.items():
        cl = c[lo:hi]
        H = hold_mult(o, c, lo, hi)
        for thr in (0.10, 0.15, 0.20, 0.25):
            pts = zigzag(cl, thr)
            fl = [(lo + a, lo + b) for a, b in falls_from(pts)]
            sizes = np.array([np.log(c[b] / c[a]) for a, b in fl])
            dur = np.array([b - a for a, b in fl])
            pos = pos_dodge(len(c), lo, hi, fl)
            m = mult(pos, o, c, lo, hi)
            ups = [(a[1], b[1]) for a, b in zip(pts[:-1], pts[1:]) if a[0] == "trough" and b[0] == "peak"]
            up_sum = float(sum(np.log(cl[b] / cl[a]) for a, b in ups))
            rows.append({"window": name, "threshold": thr, "falls": len(fl), "sum_log_falls": -sizes.sum(), "avg_fall_pct": (np.exp(sizes).mean() - 1), "median_sessions": float(np.median(dur)) if len(dur) else np.nan,
                         "held_x": H, "dodge_all_x": m, "dodge_all_over_held": m / H, "sum_log_falls_over_ln2": -sizes.sum() / np.log(2), "sum_log_rises": up_sum})
            store[(name, thr)] = fl
    return pd.DataFrame(rows), store


def part_c(store, nsim=300, seed=11):
    rng = np.random.default_rng(seed)
    rows = []
    n = len(c)
    for name, (lo, hi) in W.items():
        H = hold_mult(o, c, lo, hi)
        for thr in (0.10, 0.15, 0.20):
            fl = store[(name, thr)]
            for lag in (0, 1, 2, 3, 5, 7, 10, 15, 20):
                for kind, (do, di) in {"both late": (lag, lag), "exit late only": (lag, 0), "re-entry late only": (0, lag)}.items():
                    pos = pos_dodge(n, lo, hi, fl, do, di)
                    m = mult(pos, o, c, lo, hi)
                    rows.append({"window": name, "threshold": thr, "falls": len(fl), "kind": kind, "lag_days": lag, "hit_rate": 1.0, "false_alarms_per_true": 0, "mean_x": m, "over_held": m / H, "reaches_2x": m >= 2 * H})
            blocked = np.zeros(n, dtype=bool)
            for a, b in fl:
                blocked[a:b + 1] = True
            for lag in (0, 3, 5, 10):
                for p in (1.0, 0.8, 0.6, 0.5, 0.4, 0.3):
                    for fa in (0, 1, 2):
                        ms = []
                        for _ in range(nsim):
                            keep = rng.random(len(fl)) >= p
                            pos = pos_dodge(n, lo, hi, fl, lag, lag, keep)
                            ndodged = int((~keep).sum())
                            for _f in range(fa * ndodged):
                                for _try in range(20):
                                    s = int(rng.integers(lo, hi - 22))
                                    if not blocked[s:s + 22].any():
                                        pos[s:s + 20] = 0.0
                                        break
                            ms.append(mult(pos, o, c, lo, hi))
                        ms = np.array(ms)
                        rows.append({"window": name, "threshold": thr, "falls": len(fl), "kind": "hit-rate", "lag_days": lag, "hit_rate": p, "false_alarms_per_true": fa, "mean_x": ms.mean(), "over_held": np.median(ms) / H, "reaches_2x": float((ms >= 2 * H).mean())})
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 220, "display.max_columns", 30, "display.max_rows", 300)
    fmt = lambda v: f"{v:,.3f}"
    A, txt = part_a()
    A.to_csv(OUT / "d1_ceiling.csv", index=False)
    print("PART A: perfect-foresight ceilings (HINDSIGHT)")
    print(A.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    print(txt)
    B, store = part_b()
    B.to_csv(OUT / "d1_falls.csv", index=False)
    print("\nPART B: AMD falls found by zigzag (HINDSIGHT)")
    print(B.to_string(index=False, float_format=fmt))
    for thr in (0.15,):
        for name in ("recent",):
            print(f"\nFalls of {thr:.0%}+ since Aug 2023 (peak close -> trough close):")
            for a, b in store[(name, thr)]:
                print(f"  {idx[a].date()} {c[a]:7.2f} -> {idx[b].date()} {c[b]:7.2f}  {c[b] / c[a] - 1:+.1%}  ({b - a} sessions)")
    C = part_c(store)
    C.to_csv(OUT / "d1_precision.csv", index=False)
    print("\nPART C (lateness)")
    for w in ("recent", "early"):
        for thr in (0.10, 0.15, 0.20):
            s = C[(C.window == w) & (C.threshold == thr) & (C.kind != "hit-rate")]
            piv = s.pivot_table(index="lag_days", columns="kind", values="over_held")
            print(f"\n{w}, falls >= {thr:.0%}: result divided by held (2.0 needed)")
            print(piv.to_string(float_format=lambda v: f"{v:.2f}"))
    print("\nPART C (hit rate), falls >= 15%: median result over held across 300 random draws (2.0 needed)")
    for w in ("recent", "early"):
        s = C[(C.window == w) & (C.threshold == 0.15) & (C.kind == "hit-rate")]
        piv = s.pivot_table(index=["lag_days", "false_alarms_per_true"], columns="hit_rate", values="over_held")
        print(f"\n{w}")
        print(piv.to_string(float_format=lambda v: f"{v:.2f}"))


if __name__ == "__main__":
    main()
