"""Item 2: where did each tried rule lose against holding? Exact decomposition of log(rule / held) into parts.

For every rule and each window (recent = Aug 2023 to Nov 11 2026, early = 2013 to Jul 2023) the daily difference between the rule's growth and the held
growth is assigned to one of these buckets (they add up exactly to log(rule/held)):
  falls avoided      days in cash while AMD was inside a fall (HINDSIGHT label: 15%+ zigzag fall leg, peak close to trough close). Positive.
  late entry         days in cash inside a rise leg (trough to peak) BEFORE the rule's first day in AMD during that rise. Negative.
  early exit         days in cash inside a rise leg AFTER the rule had already been in AMD during that same rise. Negative.
  fall taken         (not a gain or loss against held; shown only as a count) days in AMD during a fall leg.
  trade-day gaps     on the day of a buy (fills at the open, misses the overnight gap) or a sell (fills at the open, misses the intraday move), plus 5 bp each side.
  costs              the 5 bp per side part of the line above, shown separately.
Also: AMD's best 10 and 20 days (close to close) and how many of them each rule was fully in AMD for, the share of AMD's total log return they hold,
and per leg capture: of the 15%+ falls, how many were dodged by at least half of their log size; of the rises, how much of each the rule captured.
All leg labels use the whole window (HINDSIGHT); they describe what happened, they are not used by any rule.
"""
import numpy as np
import pandas as pd
import rules as R
from common import *
from d1_ceiling import zigzag

f = load_amd()
o, c, idx = f.open.values, f.close.values, f.index
n = len(c)
W = windows(idx)
THR = 0.15


def leg_labels(lo, hi):
    """+1 on days inside a rise leg, -1 inside a fall leg (day t belongs to the leg if its close move from t-1 to t is on the path peak->trough or trough->peak)."""
    cl = c[lo:hi]
    pts = zigzag(cl, THR)
    lab = np.zeros(n, dtype=int)
    ids = np.zeros(n, dtype=int)
    bounds = [(0, None)] + [(i, k) for k, (kind, i) in enumerate(pts)]
    # build segments
    seg_start = 0
    segs = []
    first_kind = pts[0][0] if pts else "peak"
    cur = +1 if first_kind == "peak" else -1  # before the first pivot the move is a rise if the first pivot is a peak
    prev = 0
    for kind, i in pts:
        segs.append((prev, i, cur))
        prev = i
        cur = -1 if kind == "peak" else +1
    segs.append((prev, len(cl) - 1, cur))
    sid = 0
    for a, b, d in segs:
        sid += 1
        # days a+1..b have their close-to-close return on this leg
        lab[lo + a + 1: lo + b + 1] = d
        ids[lo + a + 1: lo + b + 1] = sid
    return lab, ids, segs


def decompose(pos, lo, hi, lab, ids):
    now = np.zeros(n)
    now[1:] = pos[:-1]
    before = np.zeros(n)
    before[1:] = now[:-1]
    before[lo] = 0.0
    fr = factors(pos, o, c, lo, hi)
    fh = factors(np.r_[np.zeros(lo - 1), np.ones(n - lo + 1)], o, c, lo, hi)
    diff = np.zeros(n)
    diff[lo:hi] = np.log(fr[lo:hi]) - np.log(fh[lo:hi])
    out_day = (now == 0) & (before == 0)
    buy_day = (now == 1) & (before == 0)
    sell_day = (now == 0) & (before == 1)
    in_day = (now == 1) & (before == 1)
    res = {"falls_avoided": 0.0, "late_entry": 0.0, "early_exit": 0.0, "trade_day_gaps": 0.0, "costs": 0.0, "other": 0.0}
    seen_in = {}
    fall_days_in = 0
    fall_days = 0
    for t in range(lo, hi):
        sid = ids[t]
        if out_day[t]:
            if lab[t] < 0:
                res["falls_avoided"] += diff[t]
            elif lab[t] > 0:
                if seen_in.get(sid, False):
                    res["early_exit"] += diff[t]
                else:
                    res["late_entry"] += diff[t]
            else:
                res["other"] += diff[t]
        elif buy_day[t] or sell_day[t]:
            res["trade_day_gaps"] += diff[t]
        if now[t] == 1 or before[t] == 1:
            seen_in[sid] = True
        if lab[t] < 0:
            fall_days += 1
            fall_days_in += int(in_day[t])
    ntr = int(buy_day[lo:hi].sum() + sell_day[lo:hi].sum())
    res["costs"] = ntr * np.log(1 - COST)
    res["trade_day_gaps"] -= res["costs"]
    res["total_log"] = float(np.sum(diff[lo:hi]))
    res["check"] = sum(v for k, v in res.items() if k not in ("total_log",)) - res["total_log"]
    return res, now, before


def legs_capture(pos, lo, hi, segs, now, before):
    """Per leg: share of log move captured (days with the day's whole close-to-close return in AMD)."""
    rows = []
    for a, b, d in segs:
        days = np.arange(lo + a + 1, lo + b + 1)
        if not len(days):
            continue
        r = np.log(c[days] / c[days - 1])
        inn = (now[days] == 1) & (before[days] == 1)
        tot = r.sum()
        cap = r[inn].sum()
        rows.append({"dir": d, "start": idx[lo + a].date(), "end": idx[lo + b].date(), "move_log": tot, "captured_log": cap, "share": cap / tot if tot else np.nan, "size_pct": np.exp(tot) - 1})
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 300)
    allrows, legrows, bestrows = [], [], []
    for w in ("recent", "early"):
        lo, hi = W[w]
        H = hold_mult(o, c, lo, hi)
        lab, ids, segs = leg_labels(lo, hi)
        r_all = np.zeros(n)
        r_all[1:] = np.log(c[1:] / c[:-1])
        r_win = r_all[lo:hi]
        total_log = r_win.sum()
        order = np.argsort(-r_win)
        top10, top20 = lo + order[:10], lo + order[:20]
        share10, share20 = r_win[order[:10]].sum() / total_log, r_win[order[:20]].sum() / total_log
        # return left if the best 10 / 20 days are removed
        x10 = np.exp(total_log - r_win[order[:10]].sum())
        x20 = np.exp(total_log - r_win[order[:20]].sum())
        bestrows.append({"window": w, "held_x": np.exp(total_log), "total_log_return": total_log, "best10_share_of_log": share10, "best20_share_of_log": share20, "held_x_without_best10": x10, "held_x_without_best20": x20,
                         "worst10_log": r_win[np.argsort(r_win)[:10]].sum(), "n_days": hi - lo, "days_up_5pct": int((r_win > np.log(1.05)).sum()), "days_down_5pct": int((r_win < np.log(0.95)).sum())})
        P = R.positions(w)
        for k, nm in R.NAMES.items():
            pos = P[k]
            m = mult(pos, o, c, lo, hi)
            res, now, before = decompose(pos, lo, hi, lab, ids)
            full = (now == 1) & (before == 1)
            hit10 = int(full[top10].sum())
            hit20 = int(full[top20].sum())
            lc = legs_capture(pos, lo, hi, segs, now, before)
            falls = lc[(lc.dir < 0) & (lc.size_pct.abs() >= THR - 1e-9)]
            rises = lc[(lc.dir > 0)]
            dodged = int((falls.share <= 0.5).sum())       # captured (suffered) at most half of the fall
            eq = curve(pos, o, c, lo, hi)
            allrows.append({"window": w, "rule": nm, "key": k, "held_x": H, "rule_x": m, "rule_over_held": m / H, "trades": len(trades_from_pos(pos, lo, hi)), "in_market": float(now[lo:hi].mean()),
                            "log_gap": res["total_log"], "falls_avoided": res["falls_avoided"], "late_entry": res["late_entry"], "early_exit": res["early_exit"], "trade_day_gaps": res["trade_day_gaps"], "costs": res["costs"],
                            "other": res["other"], "check": res["check"], "best10_hit": hit10, "best20_hit": hit20, "fall_legs": len(falls), "falls_dodged_half": dodged,
                            "rise_legs": len(rises), "avg_rise_share_captured": float(rises.share.mean()), "avg_fall_share_suffered": float(falls.share.mean()) if len(falls) else np.nan, "max_dd": max_dd(eq), "held_max_dd": max_dd(curve(np.r_[np.zeros(lo - 1), np.ones(n - lo + 1)], o, c, lo, hi))})
            lc.insert(0, "rule", nm)
            lc.insert(0, "window", w)
            legrows.append(lc)
    A = pd.DataFrame(allrows)
    A.to_csv(OUT / "d2_decompose.csv", index=False)
    pd.concat(legrows).to_csv(OUT / "d2_legs.csv", index=False)
    Bd = pd.DataFrame(bestrows)
    Bd.to_csv(OUT / "d2_best_days.csv", index=False)
    print("AMD concentration of returns")
    print(Bd.to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
    for w in ("recent", "early"):
        s = A[A.window == w]
        print(f"\n=== {w}: log points vs held (negative = lost against holding). Sum of the five columns = log_gap.  check should be 0")
        cols = ["rule", "held_x", "rule_x", "rule_over_held", "trades", "in_market", "log_gap", "falls_avoided", "late_entry", "early_exit", "trade_day_gaps", "costs", "check"]
        print(s[cols].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
        cols = ["rule", "best10_hit", "best20_hit", "fall_legs", "falls_dodged_half", "rise_legs", "avg_rise_share_captured", "avg_fall_share_suffered", "max_dd", "held_max_dd"]
        print(s[cols].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    # the leg list for the recent window
    lo, hi = W["recent"]
    lab, ids, segs = leg_labels(lo, hi)
    print("\nLegs (15% zigzag, HINDSIGHT), recent window")
    for a, b, d in segs:
        print(f"  {'rise' if d > 0 else 'fall'} {idx[lo + a].date()} {c[lo + a]:7.2f} -> {idx[lo + b].date()} {c[lo + b]:7.2f}  {c[lo + b] / c[lo + a] - 1:+.1%}")


if __name__ == "__main__":
    main()
