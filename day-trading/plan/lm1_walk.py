"""LEGACY-1 exit walker: one causal bar-by-bar exit engine with variants.
Same honest-fill rules as cp_sim._walk_exit (gap-through stops fill at
min(level, open) clamped to [L,H]; limits above market at max(level, open)).
Close-based signals fill either at that bar's close ("close", cp_sim's
convention) or at the NEXT printed bar's open ("next", stricter)."""
import sys
import numpy as np
sys.path.insert(0, r"C:\cornell\stocks-automation\day-trading\plan")
import cp_lib as L
import cp_sim as S

BASE = dict(stop=None, trail=True, bear=True, bear_any=False, tp=None,
            tstop=None, tstop_red=None, vwap=False, vwap_min=0, atr_k=None,
            lock_at=None, lock_to=0.0, fill="close", end=L.M_1500,
            bear_min=0.0)

def V(**k):
    c = dict(BASE); c.update(k); return c

def _sell(o, l, h, lvl):
    return float(min(max(min(lvl, o), l), h))

def walk(day, i, em, entry, x, path=False):
    """Return (exit_min, exit_px, reason[, mfe, mae, px_at])."""
    end = x["end"]
    O, H, Lo, C, P = day.o[i], day.h[i], day.l[i], day.c[i], day.printed[i]
    stop = entry * (1 - x["stop"]) if x["stop"] else None
    tp = entry * (1 + x["tp"]) if x["tp"] else None
    peak = entry; peakc = entry
    locked = None
    pend = None
    # causal ATR(14) seeded from printed bars up to em-1
    tr = []; prevc = None
    for m in range(max(em - 60, 0), em):
        if P[m]:
            h_, l_, c_ = float(H[m]), float(Lo[m]), float(C[m])
            tr.append(max(h_ - l_, abs(h_ - prevc), abs(l_ - prevc)) if prevc is not None else h_ - l_)
            prevc = c_
    atr = float(np.mean(tr[-14:])) if tr else None
    vw_num = day.cumdv[i]; vw_den = day.cumv[i]; m0 = L.M_OPEN - 1
    nb = 0
    for m in range(em + 1, end + 1):
        if not P[m]:
            continue
        o, h, l, c = float(O[m]), float(H[m]), float(Lo[m]), float(C[m])
        if pend is not None:
            return m, o, pend
        nb += 1
        if stop is not None and l <= stop:
            return m, _sell(o, l, h, stop), "stop"
        if locked is not None and l <= locked:
            return m, _sell(o, l, h, locked), "lock"
        if tp is not None and h >= tp:
            return m, float(min(max(max(tp, o), l), h)), "tp"
        peak = max(peak, h)
        if x["trail"]:
            tw = 0.20
            p10 = S._pressure_at(day, i, m, 10)
            if p10 is not None:
                tw = 0.10 if p10 <= -0.30 else (0.40 if p10 >= 0.30 else 0.20)
            lvl = peak * (1 - tw)
            if l <= lvl < peak:
                return m, _sell(o, l, h, lvl), f"trail{tw:.2f}"
        if x["lock_at"] and locked is None and peak >= entry * (1 + x["lock_at"]):
            locked = entry * (1 + x["lock_to"])
        sig = None
        if x["bear"] and (x["bear_any"] or c > entry * (1 + x["bear_min"])) and S._bearish(day, i, m):
            sig = "bearish"
        if sig is None and x["vwap"] and nb > x["vwap_min"]:
            den = vw_den[m] - vw_den[m0]
            if den > 0 and c < (vw_num[m] - vw_num[m0]) / den:
                sig = "vwap"
        if sig is None and x["atr_k"] and atr:
            if c < peakc - x["atr_k"] * atr:
                sig = "atr"
        if sig is None and x["tstop"] and (m - em) >= x["tstop"]:
            sig = "time"
        if sig is None and x["tstop_red"] and (m - em) >= x["tstop_red"][0] and c < entry * (1 + x["tstop_red"][1]):
            sig = "time-red"
        peakc = max(peakc, c)
        if atr is not None:
            atr = (atr * 13 + (h - l)) / 14.0
        if sig is not None:
            if x["fill"] == "close":
                return m, c, sig
            pend = sig
    m = end
    while m > em and not P[m]:
        m -= 1
    if m <= em:
        return None, None, None
    return m, float(C[m]), "flatten" if pend is None else pend
