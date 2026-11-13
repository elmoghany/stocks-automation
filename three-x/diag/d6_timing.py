"""How precise were the tried rules, measured the same way d1 asks for? For each rule and window:
  - every stretch in cash (from a sell fill to the next buy fill; also the wait at the start): did AMD fall during it (a good stay in cash) or rise (a false alarm)? How much of each, in log points.
  - against the 15% falls and rises (hindsight labels): how many falls was the rule already out of at the peak, how many did it exit before the trough and how many sessions after the peak,
    how many did it ride all the way down; for rises: sessions from the trough to the buy, and how many rises it never joined.
Decision-day convention as elsewhere: pos[i]=0 at the close of day i means out from the next open. "Sessions late" counts decision closes after the peak/trough close.
"""
import numpy as np
import pandas as pd
import rules as R
from common import *
from d1_ceiling import zigzag, falls_from

f = load_amd()
o, c, idx = f.open.values, f.close.values, f.index
n = len(c)
W = windows(idx)


def cash_stretches(pos, lo, hi):
    P = np.r_[o, c[hi - 1]]
    tr = trades_from_pos(pos, lo, hi)
    out = []
    prev_end = lo               # fill index where the last stay ended (window start counts as flat)
    for b, s in tr:
        buy_fill = max(b + 1, lo)
        if buy_fill > prev_end:
            out.append((prev_end, buy_fill))
        prev_end = hi if s is None else s + 1
    if prev_end < hi:
        out.append((prev_end, hi))
    res = []
    for a, e in out:
        pa = o[a]
        pe = c[hi - 1] if e >= hi else o[e]
        res.append((a, e, np.log(pe / pa)))
    return res


def main():
    pd.set_option("display.width", 250, "display.max_columns", 50, "display.max_rows", 300)
    rows = []
    for w in ("recent", "early"):
        lo, hi = W[w]
        pts = zigzag(c[lo:hi], 0.15)
        fl = [(lo + a, lo + b) for a, b in falls_from(pts)]
        rs = [(lo + a[1], lo + b[1]) for a, b in zip(pts[:-1], pts[1:]) if a[0] == "trough" and b[0] == "peak"]
        P = R.positions(w)
        for k, nm in R.NAMES.items():
            pos = P[k]
            cs = cash_stretches(pos, lo, hi)
            good = [x for x in cs if x[2] < 0]
            bad = [x for x in cs if x[2] >= 0]
            days_cash = sum(e - a for a, e, _ in cs)
            # falls
            out_at_peak = exit_before = rode = 0
            exit_lag, exit_saved = [], []
            for p, t in fl:
                if p < 1 or pos[p - 1] == 0:
                    out_at_peak += 1
                    continue
                later = np.nonzero(pos[p:t] == 0)[0]
                if len(later):
                    exit_before += 1
                    e = p + later[0]
                    exit_lag.append(e - p)
                    exit_saved.append(np.log(c[t] / c[e]) / np.log(c[t] / c[p]))     # share of the fall's log size still ahead when it exited
                else:
                    rode += 1
            # rises
            in_at_trough = entered = missed = 0
            entry_lag, entry_share_left = [], []
            for t, p in rs:
                if pos[t - 1] == 1:
                    in_at_trough += 1
                    continue
                later = np.nonzero(pos[t:p] == 1)[0]
                if len(later):
                    entered += 1
                    e = t + later[0]
                    entry_lag.append(e - t)
                    entry_share_left.append(np.log(c[p] / c[e]) / np.log(c[p] / c[t]))
                else:
                    missed += 1
            rows.append({"window": w, "rule": nm, "cash_stretches": len(cs), "days_in_cash": days_cash, "stretches_where_AMD_fell": len(good), "stretches_where_AMD_rose_false_alarm": len(bad),
                         "log_avoided_in_good_stretches": -sum(x[2] for x in good), "log_missed_in_false_alarms": sum(x[2] for x in bad),
                         "falls": len(fl), "already_out_at_peak": out_at_peak, "exited_before_trough": exit_before, "rode_to_trough": rode,
                         "median_sessions_exit_after_peak": float(np.median(exit_lag)) if exit_lag else np.nan, "median_share_of_fall_still_ahead_at_exit": float(np.median(exit_saved)) if exit_saved else np.nan,
                         "rises": len(rs), "in_at_trough": in_at_trough, "entered_during_rise": entered, "rise_never_joined": missed,
                         "median_sessions_entry_after_trough": float(np.median(entry_lag)) if entry_lag else np.nan, "median_share_of_rise_still_ahead_at_entry": float(np.median(entry_share_left)) if entry_share_left else np.nan})
    T = pd.DataFrame(rows)
    T.to_csv(OUT / "d6_timing.csv", index=False)
    for w in ("recent", "early"):
        s = T[T.window == w].drop(columns="window")
        print(f"\n=== {w}")
        print(s.to_string(index=False, float_format=lambda v: f"{v:.2f}"))


if __name__ == "__main__":
    main()
