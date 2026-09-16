"""RL-SERIES v2 (2026-09-16): the ticket simulator.

ONE ENGINE FOR EVERY APPROACH AND EVERY CONTROL. A policy is just a score
matrix `sc[T,S]` (higher = more want to buy, -inf = never). The bandit,
the rule search, the RL agents, the random control and the foresight
control all produce a score matrix and all run through `run_day`, so the
only thing that differs between a reported row and its control is the
score.

RULES (the live cash-account rules)
  * flat $15,000 tickets, the 7th and last $10,000 -> <= 7 concurrent,
    <= $100,000 deployed per day; at most one open ticket per symbol;
    long only; no options, no margin, no shorting.
  * DECISIONS every STEP=5 minutes on the 04:00-19:55 ET grid. A decision
    at minute m is FILLED AT THE OPEN OF MINUTE m+1. If minute m+1 did
    not print, the order does not happen -- and the decision may not use
    that fact, so availability is read off bar m (`printed`), never m+1.
  * COSTS 10 bps per side, +50 bps on any fill outside 09:30-16:00.
  * SIZE CAP a fill may not exceed 20% of the symbol's volume over the
    trailing 5 minutes; a capped order is sized down and dropped below
    $500 notional (and then does NOT consume a ticket).
  * FORCED FLATTEN every open ticket is closed at the day's last printed
    bar for that symbol, at that bar's close, paying the cost ladder.
    Nothing is ever carried overnight.

EXIT RULES
  ("horizon", H)  exit at the first decision step at or after entry+H min
  ("flatten",)    hold to the forced flatten
  ("rule", d)     d = {stop, take, trail, tmax} in fractions/minutes,
                  evaluated on `mark` (last printed close <= m), filled at
                  the next bar's open -- used by plan/rl2/rules.py
"""
import numpy as np

from features import (EXT_BPS, FEE_BPS, NMIN, RTH_HI, RTH_LO, STEP, STEPS, T)

TICKETS = [15000.0] * 6 + [10000.0]
MAX_TICKETS = len(TICKETS)
MIN_NOTIONAL = 500.0


def _cost(minute):
    return (FEE_BPS + EXT_BPS * ((minute < RTH_LO) or (minute >= RTH_HI))) / 1e4


class Day:
    """One day's feature/fill arrays, as written by plan/rl2/features.py."""

    __slots__ = ("date", "syms", "S", "F", "mark", "printed", "fill_o",
                 "volcap", "flat_px", "flat_min", "tgt", "tgt_ok",
                 "prev_close")

    def __init__(self, path):
        z = np.load(path, allow_pickle=False)
        self.date = str(path).split("\\")[-1].split("/")[-1][:-4]
        self.syms = [str(s) for s in z["syms"]]
        self.S = len(self.syms)
        self.prev_close = z["prev_close"]
        self.F = z["F"]
        self.mark = z["mark"].astype(np.float64)
        self.printed = z["printed"]
        self.fill_o = z["fill_o"].astype(np.float64)
        self.volcap = z["volcap"].astype(np.float64)
        self.flat_px = z["flat_px"].astype(np.float64)
        self.flat_min = z["flat_min"]
        self.tgt = z["tgt"]
        self.tgt_ok = z["tgt_ok"]


def run_day(day, sc, exit_rule=("horizon", 30), min_score=-np.inf,
            max_new_per_step=MAX_TICKETS, first_step=0, last_entry_step=None):
    """Run one day. Returns (trades, day_pnl).

    `sc[T,S]` may be -inf to forbid a name. Entries are attempted in score
    order among names whose bar m PRINTED; a name whose minute m+1 does not
    print simply fails to fill (that is not knowable at decision time, so
    the attempt is still spent).
    """
    Tn, S = sc.shape
    if last_entry_step is None:
        last_entry_step = Tn - 1
    held = {}                                   # sym index -> position dict
    used = 0
    trades = []
    kind = exit_rule[0]

    for t in range(first_step, Tn):
        m = int(STEPS[t])
        # ---- exits first (a ticket freed at t may be reused at t)
        for i in list(held):
            p = held[i]
            if t <= p["t_in"]:
                continue
            mk = day.mark[t, i]
            want = False
            if kind == "horizon":
                want = m >= p["m_in"] + exit_rule[1]
            elif kind == "flatten":
                want = False
            elif kind == "rule":
                d = exit_rule[1]
                if np.isfinite(mk):
                    r = mk / p["px_in"] - 1.0
                    p["peak"] = max(p["peak"], mk)
                    if d.get("stop") is not None and r <= -d["stop"]:
                        want = True
                    if d.get("take") is not None and r >= d["take"]:
                        want = True
                    if d.get("trail") is not None and \
                            mk <= p["peak"] * (1.0 - d["trail"]):
                        want = True
                if d.get("tmax") is not None and m >= p["m_in"] + d["tmax"]:
                    want = True
            if not want:
                continue
            px = day.fill_o[t, i]
            if not np.isfinite(px) or px <= 0:
                continue                         # no print: carry
            mf = min(m + 1, NMIN - 1)
            pr = p["sh"] * px * (1.0 - _cost(mf))
            trades.append(_close(day, p, i, t, mf, px, pr, False))
            del held[i]

        # ---- entries
        if t > last_entry_step or used >= MAX_TICKETS:
            continue
        free = min(MAX_TICKETS - used, max_new_per_step)
        if free <= 0:
            continue
        row = sc[t]
        cand = np.flatnonzero(day.printed[t] & np.isfinite(row)
                              & (row > min_score))
        if cand.size == 0:
            continue
        cand = cand[np.argsort(-row[cand], kind="stable")]
        taken = 0
        for i in cand:
            if taken >= free or used >= MAX_TICKETS:
                break
            if i in held:
                continue
            taken += 1
            px = day.fill_o[t, i]
            if not np.isfinite(px) or px <= 0:
                continue                         # order did not happen
            notional = TICKETS[used]
            sh = notional / px
            cap = day.volcap[t, i]
            if np.isfinite(cap):
                sh = min(sh, cap)
            if sh * px < MIN_NOTIONAL:
                continue                         # too thin: no ticket spent
            mf = min(m + 1, NMIN - 1)
            cst = sh * px * (1.0 + _cost(mf))
            held[i] = {"t_in": t, "m_in": mf, "px_in": px, "sh": sh,
                       "cost": cst, "peak": px, "sym": day.syms[i]}
            used += 1

    # ---- forced flatten
    for i, p in held.items():
        px = day.flat_px[i]
        mf = int(day.flat_min[i])
        if not np.isfinite(px) or px <= 0:
            px, mf = p["px_in"], p["m_in"]       # degenerate: unwind at cost
        pr = p["sh"] * px * (1.0 - _cost(mf))
        trades.append(_close(day, p, i, T - 1, mf, px, pr, True))
    return trades, float(sum(t_["pnl"] for t_ in trades))


def _close(day, p, i, t_out, m_out, px_out, proceeds, forced):
    return {"date": day.date, "sym": p["sym"], "i": int(i),
            "t_in": int(p["t_in"]), "m_in": int(p["m_in"]),
            "px_in": float(p["px_in"]), "sh": float(p["sh"]),
            "m_out": int(m_out), "px_out": float(px_out),
            "pnl": float(proceeds - p["cost"]),
            "notional": float(p["cost"]),
            "ext_in": bool(p["m_in"] < RTH_LO or p["m_in"] >= RTH_HI),
            "ext_out": bool(m_out < RTH_LO or m_out >= RTH_HI),
            "forced": bool(forced), "hold": int(m_out - p["m_in"])}


# ------------------------------------------------------------- aggregation
def summarize(trades, ndays, label=""):
    if not trades:
        return {"label": label, "days": ndays, "tickets": 0, "total": 0.0,
                "per_ticket": 0.0, "tickets_per_day": 0.0, "sharpe": 0.0,
                "max_dd": 0.0, "win_rate": 0.0, "ext_exit_n": 0,
                "ext_exit_pnl": 0.0, "rth_exit_n": 0, "rth_exit_pnl": 0.0,
                "mean_hold": 0.0, "forced": 0}
    by_day = {}
    for t in trades:
        by_day[t["date"]] = by_day.get(t["date"], 0.0) + t["pnl"]
    dates = sorted(by_day)
    d = np.array([by_day[x] for x in dates])
    # days with no trade contribute a 0 to the daily series
    if ndays > len(d):
        d = np.concatenate([d, np.zeros(ndays - len(d))])
    eq = np.cumsum(d)
    dd = float(np.min(eq - np.maximum.accumulate(eq))) if len(eq) else 0.0
    sd = float(d.std(ddof=1)) if len(d) > 1 else 0.0
    ext = [t for t in trades if t["ext_out"]]
    rth = [t for t in trades if not t["ext_out"]]
    return {
        "label": label, "days": ndays, "tickets": len(trades),
        "total": round(float(sum(t["pnl"] for t in trades)), 2),
        "per_ticket": round(float(np.mean([t["pnl"] for t in trades])), 3),
        "tickets_per_day": round(len(trades) / max(ndays, 1), 2),
        "sharpe": round(float(d.mean() / sd * np.sqrt(252)) if sd else 0.0, 3),
        "max_dd": round(dd, 2),
        "win_rate": round(float(np.mean([t["pnl"] > 0 for t in trades])), 4),
        "ext_exit_n": len(ext),
        "ext_exit_pnl": round(float(sum(t["pnl"] for t in ext)), 2),
        "rth_exit_n": len(rth),
        "rth_exit_pnl": round(float(sum(t["pnl"] for t in rth)), 2),
        "mean_hold": round(float(np.mean([t["hold"] for t in trades])), 1),
        "forced": int(sum(t["forced"] for t in trades)),
    }


def daily_series(trades, dates):
    by = {}
    for t in trades:
        by[t["date"]] = by.get(t["date"], 0.0) + t["pnl"]
    return np.array([by.get(d, 0.0) for d in dates])
