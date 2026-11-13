"""Two extra measurements.
 (a) How much of the 2x depends on the very biggest falls: dodge only the k largest 15%+ falls (HINDSIGHT labels), with perfect timing or a few sessions late.
 (b) Trailing-stop base rates, using only data up to each decision close: the first close at least X% below the highest close of the past 126 sessions (after AMD had been back within X/2 of that high).
     What happens next, from the next open: 5, 21, 63 sessions later, share of times it fell a further 10% and share of times it was back at the old high within 63 sessions.
"""
import numpy as np
import pandas as pd
from common import *
from d1_ceiling import zigzag, falls_from, pos_dodge

f = load_amd()
o, c, idx = f.open.values, f.close.values, f.index
n = len(c)
W = windows(idx)
lc = np.log(c)


def part_a():
    rows = []
    for w in ("recent", "early"):
        lo, hi = W[w]
        H = hold_mult(o, c, lo, hi)
        fl = [(lo + a, lo + b) for a, b in falls_from(zigzag(c[lo:hi], 0.15))]
        sizes = np.array([np.log(c[b] / c[a]) for a, b in fl])
        order = np.argsort(sizes)           # most negative first
        for k in (1, 2, 3, 5, 8, 11):
            if k > len(fl):
                continue
            keep = np.ones(len(fl), dtype=bool)
            keep[order[:k]] = False         # False = dodged
            for lag in (0, 3, 5, 10):
                pos = pos_dodge(n, lo, hi, fl, lag, lag, keep)
                m = mult(pos, o, c, lo, hi)
                rows.append({"window": w, "dodge_the_k_biggest_falls": k, "lag_sessions_each_end": lag, "result_x": m, "over_held": m / H, "log_avoided_in_those_falls": float(-sizes[order[:k]].sum())})
    return pd.DataFrame(rows)


def part_b():
    rows = []
    hi_run = pd.Series(c).rolling(126, min_periods=126).max().values
    for w in ("early", "recent"):
        lo, hi = W[w]
        top = hi - 64 if w == "early" else n - 64
        for x in (0.10, 0.15, 0.20):
            ev, armed = [], True
            for t in range(max(lo, 126), top):
                dd = c[t] / hi_run[t] - 1
                if dd > -x / 2:
                    armed = True
                if armed and dd <= -x:
                    ev.append(t)
                    armed = False
            if not ev:
                continue
            r5 = [lc[t + 5] - np.log(o[t + 1]) for t in ev]
            r21 = [lc[t + 21] - np.log(o[t + 1]) for t in ev]
            r63 = [lc[t + 63] - np.log(o[t + 1]) for t in ev]
            more10 = [bool((c[t + 1:t + 64] <= c[t] * 0.90).any()) for t in ev]
            back = [bool((c[t + 1:t + 64] >= hi_run[t]).any()) for t in ev]
            ordinary21 = np.nanmean([lc[t + 21] - np.log(o[t + 1]) for t in range(lo, top)])
            rows.append({"window": w, "trigger_X": x, "events": len(ev), "mean_next5_pct": 100 * (np.exp(np.mean(r5)) - 1), "mean_next21_pct": 100 * (np.exp(np.mean(r21)) - 1), "ordinary_next21_pct": 100 * (np.exp(ordinary21) - 1),
                         "mean_next63_pct": 100 * (np.exp(np.mean(r63)) - 1), "share_next21_negative": float(np.mean(np.array(r21) < 0)), "share_fell_further_10pct_within_63": float(np.mean(more10)), "share_back_at_old_high_within_63": float(np.mean(back))})
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 250, "display.max_columns", 50, "display.max_rows", 300)
    A = part_a()
    A.to_csv(OUT / "d7_topfalls.csv", index=False)
    print("(a) Dodging only the k biggest 15%+ falls (HINDSIGHT labels), result divided by held (2.0 needed)")
    for w in ("recent", "early"):
        print(f"\n{w}")
        print(A[A.window == w].pivot_table(index="dodge_the_k_biggest_falls", columns="lag_sessions_each_end", values="over_held").to_string(float_format=lambda v: f"{v:.2f}"))
    B = part_b()
    B.to_csv(OUT / "d7_trailing_stop_base_rates.csv", index=False)
    print("\n(b) After the first close X below the 126-day high (causal trigger)")
    print(B.to_string(index=False, float_format=lambda v: f"{v:.2f}"))


if __name__ == "__main__":
    main()
