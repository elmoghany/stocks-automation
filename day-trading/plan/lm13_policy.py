"""LEGACY-13 step 3: honest long-only USES of a range forecast on R4's
entries, each a full sequential re-simulation (one position at a time,
so a policy that changes an exit also changes every later ticket).

Range forecast = sigma1 at the decision minute (realised 1-min log-return
s.d. of the name's printed bars up to t, cp_feat; causal). Among R4 legs
it ranks forward range almost exactly as well as the up30 walk-forward
model (rho 0.606 vs 0.619, lm13_diag) and exists on every leg, the model
score on fewer than half. Every threshold below is fixed from the FIRST
HALF of R4's legs (dates < 2025-09-12): tercile cuts 0.0086 / 0.0170,
median 0.0116. Writes plan/lm13_policy.json."""
import json
import math
import sys
import time

import numpy as np

import lm13_lib as M

S, F, L = M.S, M.F, M.L
LO_CUT, HI_CUT, MED = 0.0086, 0.0170, 0.0116

_inner_try = S._try_ticket            # lm13_lib's t-capturing wrapper
_orig_walk = S._walk_exit


def _walk_target(day, Fd, i, em, entry, cfg):
    """cp_sim._walk_exit plus a FULL take-profit limit (`tgt_full`, a
    fraction above entry). A gap through the limit fills at the open."""
    tgt = cfg.get("tgt_full")
    if not tgt:
        return _orig_walk(day, Fd, i, em, entry, cfg)
    lvl_t = entry * (1 + tgt)
    end = cfg["exit_end"]
    peak = entry
    for m in range(em + 1, end + 1):
        if not day.printed[i, m]:
            continue
        lo, hi, c, o = (float(day.l[i, m]), float(day.h[i, m]),
                        float(day.c[i, m]), float(day.o[i, m]))
        # pessimistic intrabar order: the trail (set by the PRIOR peak)
        # is checked before the target
        tw = cfg["trail_pct"]
        p10 = S._pressure_at(day, i, m, 10)
        if p10 is not None:
            if p10 <= -cfg["trail_thr"]:
                tw = cfg["trail_lo"]
            elif p10 >= cfg["trail_thr"]:
                tw = cfg["trail_hi"]
        lvl = peak * (1 - tw)
        if lo <= lvl < peak:
            return m, S._sell_fill(day, i, m, lvl), f"trail {tw:.2f}"
        if hi >= lvl_t:
            return m, min(max(max(lvl_t, o), lo), hi), "target"
        peak = max(peak, hi)
        if cfg["bearish_exit"] and c > entry and S._bearish(day, i, m):
            return m, c, "bearish"
    m = end
    while m > em and not day.printed[i, m]:
        m -= 1
    if m <= em:
        return None, None, None
    return m, float(day.c[i, m]), "flatten"


S._walk_exit = _walk_target


def _patient(day, Fd, i, t, gi, budget, cfg, k, W):
    """Rest a buy limit k*sigma*sqrt(5) below the decision-minute price
    for W minutes. Unfilled -> a zero-share placeholder leg that only
    advances the clock to t+W (no going back in time to try the next
    name at t)."""
    s = float(Fd["sigma1"][i, gi])
    last = float(Fd["last"][i, gi])
    lvl = last * (1 - k * s * math.sqrt(5))
    em = None
    for m in range(t + 1, min(t + W + 1, cfg["exit_end"])):
        if day.printed[i, m] and day.l[i, m] < lvl:     # trade-through
            em = m
            px = min(lvl, float(day.o[i, m]))
            px = min(max(px, float(day.l[i, m])), float(day.h[i, m]))
            break
    if em is None:
        return dict(i=i, sym=day.syms[i], entry_min=t, entry=last,
                    exit_min=t + W, exit=last, shares=0, reason="unfilled",
                    gross=0.0, net_flat=0.0, net_meas=0.0, cost_flat=0.0,
                    cost_meas=0.0, t=t, gi=gi)
    if px < cfg["min_px"]:
        return None
    v5 = float(day.cumv[i, em - 1] - day.cumv[i, max(em - 6, 0)])
    sh = int(min(budget / px, S.VOL_CAP * v5))
    if sh < 1:
        return None
    ex_m, ex_px, reason = S._walk_exit(day, Fd, i, em, px, cfg)
    if ex_px is None:
        return None
    g = (ex_px - px) * sh
    return dict(i=i, sym=day.syms[i], entry_min=em, entry=px, exit_min=ex_m,
                exit=ex_px, shares=sh, reason=reason, gross=g, net_flat=g,
                net_meas=g, cost_flat=0.0, cost_meas=0.0, t=t, gi=gi)


def _policy_try(day, Fd, i, t, gi, budget, cfg, cost):
    pol = cfg.get("pol") or {}
    s = float(Fd["sigma1"][i, gi])
    fin = np.isfinite(s)
    if pol.get("skip_nan") and not fin:
        return None
    if "min_sig" in pol and not (fin and s >= pol["min_sig"]):
        return None
    if "max_sig" in pol and fin and s > pol["max_sig"]:
        return None
    c2 = dict(cfg)
    if "trail_m" in pol and fin:
        tw = float(np.clip(pol["trail_m"] * s, 0.03, 0.40))
        c2.update(trail_pct=tw, trail_lo=tw / 2, trail_hi=min(2 * tw, 0.6))
    if "trail_fixed" in pol:
        sel = pol.get("trail_sel", "all")
        hit = (sel == "all" or (sel == "hi" and fin and s > HI_CUT)
               or (sel == "lo" and fin and s <= LO_CUT))
        if hit:
            a, b, c = pol["trail_fixed"]
            c2.update(trail_pct=a, trail_lo=b, trail_hi=c)
    if "tgt_k" in pol:
        base = s if (fin and not pol.get("tgt_uniform")) else MED
        c2["tgt_full"] = pol["tgt_k"] * base
    if "pat_k" in pol:
        sel = pol.get("pat_sel", "hi")
        if fin and (sel == "all" or (sel == "hi" and s > HI_CUT)):
            return _patient(day, Fd, i, t, gi, budget, c2, pol["pat_k"],
                            pol.get("pat_w", 15))
    return _inner_try(day, Fd, i, t, gi, budget, c2, cost)


S._try_ticket = _policy_try

POL = {
    "base": {},
    # --- gates (who gets a ticket) ---
    "gate_skip_thin(nan sigma)": {"skip_nan": True},
    "gate_sig>=0.0086 (drop low tercile)": {"min_sig": LO_CUT},
    "gate_sig>=0.0170 (high tercile only)": {"min_sig": HI_CUT},
    "CTRL gate_sig<=0.0170 (drop high)": {"max_sig": HI_CUT},
    # --- trail width by forecast ---
    "trail=clip(8*sig) lo/2 hi*2": {"trail_m": 8},
    "trail=clip(12*sig) lo/2 hi*2": {"trail_m": 12},
    "trail=clip(20*sig) lo/2 hi*2": {"trail_m": 20},
    "trail hi-range names .30/.15/.50": {"trail_fixed": (0.30, 0.15, 0.50),
                                         "trail_sel": "hi"},
    "CTRL trail ALL .30/.15/.50": {"trail_fixed": (0.30, 0.15, 0.50)},
    "trail lo-range names .06/.03/.12": {"trail_fixed": (0.06, 0.03, 0.12),
                                         "trail_sel": "lo"},
    "CTRL trail ALL .06/.03/.12": {"trail_fixed": (0.06, 0.03, 0.12)},
    # --- profit target in forecast units ---
    "target 3*sig": {"tgt_k": 3},
    "target 6*sig": {"tgt_k": 6},
    "target 12*sig": {"tgt_k": 12},
    "CTRL target 6*median sig (flat 7%)": {"tgt_k": 6, "tgt_uniform": True},
    "CTRL target 12*median sig (flat 14%)": {"tgt_k": 12,
                                             "tgt_uniform": True},
    # --- entry patience on high-range names ---
    "patience hi: limit -0.5*sig*sqrt5, 15m": {"pat_k": 0.5},
    "patience hi: limit -1*sig*sqrt5, 15m": {"pat_k": 1.0},
    "patience hi: limit -1*sig*sqrt5, 30m": {"pat_k": 1.0, "pat_w": 30},
    "CTRL patience ALL: -1*sig*sqrt5, 15m": {"pat_k": 1.0, "pat_sel": "all"},
}

if __name__ == "__main__":
    t0 = time.time()
    ds = M.r4_dates()
    if "--quick" in sys.argv:
        ds = ds[::8]
    jobs = {k: (S.default_cfg(rank="coil", stop_pct=None, pol=v), None,
                None) for k, v in POL.items()}
    res = S.run_many(ds, jobs, progress=True)
    out = {}
    for k, legs in res.items():
        legs = [x for x in legs if x["shares"] > 0]
        h1 = [x for x in legs if x["date"] < "2025-09-12"]
        h2 = [x for x in legs if x["date"] >= "2025-09-12"]
        out[k] = {"all": M.summ(legs, len(ds)),
                  "h1": M.summ(h1, sum(d < "2025-09-12" for d in ds)),
                  "h2": M.summ(h2, sum(d >= "2025-09-12" for d in ds)),
                  "legs": [{kk: x[kk] for kk in ("date", "sym", "entry_min",
                                                 "exit_min", "entry", "exit",
                                                 "shares", "gross", "reason")}
                           for x in legs]}
        a = out[k]["all"]
        print(f"{k:42s} n={a['n']:4d} g/t={a['tkt_0']:+7.1f} "
              f"n12/t={a['tkt_12']:+7.1f} mon12={a['mon_12']:+8.0f} "
              f"exTop5={a['ex_top5_mon_12']:+7.0f} h1={out[k]['h1']['mon_12']:+7.0f}"
              f" h2={out[k]['h2']['mon_12']:+7.0f}", flush=True)
    name = "lm13_policy_quick.json" if "--quick" in sys.argv else "lm13_policy.json"
    json.dump(out, open(M.PLAN / name, "w"), default=float)
    print("secs", round(time.time() - t0))
