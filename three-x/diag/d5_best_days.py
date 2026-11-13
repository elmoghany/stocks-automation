"""Where do AMD's best (and worst) days sit relative to the 15% turning points? Hindsight description, used to judge how precise a buy or sell signal would need to be.

For the 20 best and 20 worst close-to-close days in each window: sessions since the latest 15%-zigzag trough (for best days) or peak (for worst days), the 5-day return
before the day, and whether the day came inside a fall leg or a rise leg. Also: how much of the total log return of each window lies within 10 sessions after a trough.
"""
import numpy as np
import pandas as pd
from common import *
from d1_ceiling import zigzag

f = load_amd()
o, c, idx = f.open.values, f.close.values, f.index
n = len(c)
W = windows(idx)
lc = np.log(c)
ret = np.r_[np.nan, np.diff(lc)]

rows = []
for w in ("recent", "early"):
    lo, hi = W[w]
    pts = zigzag(c[lo:hi], 0.15)
    troughs = np.array([lo + i for k, i in pts if k == "trough"])
    peaks = np.array([lo + i for k, i in pts if k == "peak"])
    r = ret[lo:hi]
    order = np.argsort(-r)[:20]
    worst = np.argsort(r)[:20]
    total = r.sum()

    def since(day, piv):
        prev = piv[piv <= day]
        return day - prev.max() if len(prev) else np.nan

    best_d = np.array([since(lo + i, troughs) for i in order])
    worst_d = np.array([since(lo + i, peaks) for i in worst])
    pre5 = np.array([lc[lo + i - 1] - lc[lo + i - 6] for i in order])
    # share of window log return inside 10 sessions after each trough
    inside = np.zeros(n, dtype=bool)
    for t in troughs:
        inside[t + 1:t + 11] = True
    inside[:lo] = False
    inside[hi:] = False
    share_after_trough10 = np.nansum(ret[inside]) / total
    rows.append({"window": w, "troughs": len(troughs), "best20_within_10_sessions_after_trough": int((best_d <= 10).sum()), "best20_within_20_sessions_after_trough": int((best_d <= 20).sum()),
                 "best20_median_sessions_after_trough": float(np.nanmedian(best_d)), "best20_after_5day_fall": int((pre5 < 0).sum()),
                 "worst20_within_10_sessions_after_peak": int((worst_d <= 10).sum()), "worst20_within_20_sessions_after_peak": int((worst_d <= 20).sum()), "worst20_median_sessions_after_peak": float(np.nanmedian(worst_d)),
                 "share_of_window_log_return_in_10_sessions_after_a_trough": share_after_trough10, "sessions_in_those_windows_share": float(inside[lo:hi].mean())})
    print(f"\n{w}: the 10 best days (date, return, sessions after trough, 5-day return before):")
    for i in order[:10]:
        print(f"   {idx[lo + i].date()}  {np.exp(r[i]) - 1:+.1%}  {since(lo + i, troughs):>4.0f}  {np.exp(lc[lo + i - 1] - lc[lo + i - 6]) - 1:+.1%}")
D = pd.DataFrame(rows)
D.to_csv(OUT / "d5_best_days.csv", index=False)
print(D.T.to_string(header=True, float_format=lambda v: f"{v:.2f}"))
