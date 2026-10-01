"""LEGACY-14: old-champion components bolted onto CHAMPION-REPLAY R4
(cp_sim, rank=coil, no stop, defer fill, live-scanner LAST universe,
gap-through fills). One pass over the 444 in-sample sessions, all jobs
share the loaded panels. cp_sim.py is NOT edited: extra exit rules live
in a copy of _walk_exit here (identical when no extra key is set -- the
R4_15k job must reproduce the published 965 legs / $66,760.10), and the
honest ARMED trigger (ORB / premarket-high stop-buy with re-rank) is a
new run_day that arms ONE name at a time -- cp_sim's own orb mode tries
the next name only after learning the first will not trigger within 60
minutes, which is a look-ahead, so it is not used.

Output: legs per job (json) to the path given as argv[1]."""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_run as R                                          # noqa: E402
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402

S = R.S
ORIG_TICKETS = list(S.TICKETS)


# ---------------------------------------------------------------------
# exit walk with optional legacy components
# ---------------------------------------------------------------------
def walk_exit(day, Fd, i, em, entry, cfg):
    stop = entry * (1 - cfg["stop_pct"]) if cfg["stop_pct"] else None
    peak = entry
    end = cfg["exit_end"]
    scaled = False
    so = entry * (1 + cfg["scale_out_at"]) if cfg["scale_out_at"] else None
    part_px, part_w = 0.0, 0.0
    w = cfg["scale_out_frac"] if so is not None else 0.0
    wick = cfg.get("wick_guard")          # X319: cap peak at k x max close seen
    so_skip = cfg.get("so_skip_p")        # C21: skip scale-out when p10 >= x
    uw = cfg.get("uw_min")                # exit if underwater after N minutes
    pk_delay = cfg.get("peak_delay")      # peak from bar m enters trail at m+1
    maxc = entry
    pend = None

    def blend(px):
        return part_px * part_w + px * (1.0 - part_w)

    for m in range(em + 1, end + 1):
        if not day.printed[i, m]:
            continue
        lo, hi, c, o = (float(day.l[i, m]), float(day.h[i, m]),
                        float(day.c[i, m]), float(day.o[i, m]))
        if stop is not None and lo <= stop:
            return m, blend(S._sell_fill(day, i, m, stop)), f"stop {stop:.2f}"
        if so is not None and not scaled and hi >= so:
            skip = False
            if so_skip is not None:
                p = S._pressure_at(day, i, m - 1, 10)
                skip = p is not None and p >= so_skip
            if not skip:
                px = min(max(max(so, o), lo), hi)
                part_px, part_w, scaled = px, w, True
        hcap = min(hi, maxc * wick) if wick else hi
        if pk_delay:
            if pend is not None:
                peak = max(peak, pend)
            pend = hcap
        else:
            peak = max(peak, hcap)
        if cfg["trail_pct"]:
            tw = cfg["trail_pct"]
            p10 = S._pressure_at(day, i, m, 10)
            if p10 is not None:
                if p10 <= -cfg["trail_thr"]:
                    tw = cfg["trail_lo"]
                elif p10 >= cfg["trail_thr"]:
                    tw = cfg["trail_hi"]
            lvl = peak * (1 - tw)
            if lo <= lvl < peak:
                return m, blend(S._sell_fill(day, i, m, lvl)), f"trail {tw:.2f}"
        if cfg["bearish_exit"] and c > entry and S._bearish(day, i, m):
            if cfg.get("bear_next"):
                # honesty check: the pattern is only known at bar m's
                # close, so a market sell fills at the NEXT printed open
                for m2 in range(m + 1, L.NMIN):
                    if day.printed[i, m2]:
                        return m2, blend(float(day.o[i, m2])), "bearish-next"
            return m, blend(c), "bearish"
        if cfg["time_stop"] and (m - em) >= cfg["time_stop"]:
            return m, blend(c), "time-stop"
        if uw and (m - em) >= uw and c < entry:
            return m, blend(c), "uw-exit"
        maxc = max(maxc, c)
    m = end
    while m > em and not day.printed[i, m]:
        m -= 1
    if m <= em:
        return None, None, None
    return m, blend(float(day.c[i, m])), "flatten"


S._walk_exit = walk_exit


# ---------------------------------------------------------------------
# honest armed trigger: ONE armed name, re-ranked every `rearm` minutes
# ---------------------------------------------------------------------
def run_day_armed(day, Fd, cfg, cost=None):
    grid = list(Fd["grid"])
    gidx = {m: k for k, m in enumerate(grid)}
    elig = Fd["elig_last" if cfg["universe"] == "LAST" else "elig_high"]
    gate_top, gate_oth = S.gates(Fd, cfg)
    legs = []
    t, ti = cfg["t_start"], 0
    rearm = cfg["rearm"]
    if getattr(day, "_orb", None) is None:
        day._orb = day.runhigh_from(L.M_OPEN)[:, L.M_OPEN + 4]
    while ti < cfg["ntickets"] and t < cfg["cutoff"]:
        if t not in gidx:
            t += 1
            continue
        gi = gidx[t]
        cand = np.where(elig[:, gi])[0]
        if len(cand) == 0:
            t += cfg["step"]
            continue
        k = S.rank_key(Fd, gi, cfg)[cand]
        order = cand[np.argsort(k, kind="stable")]
        top = int(order[0])
        pick = None
        for i in order[:8]:        # gates are static/pre-open: causal
            i = int(i)
            if gate_top[i] if i == top else gate_oth[i]:
                pick = i
                break
        if pick is None:
            t += cfg["step"]
            continue
        i = pick
        if cfg["trigger"] == "orb":
            lvl = float(day._orb[i])
        else:
            lvl = float(day.pc[i] * (1 + Fd["pm_high_gain"][i]))
        if not np.isfinite(lvl) or lvl <= 0:
            t += cfg["step"]
            continue
        em = px = None
        stop_at = min(t + rearm, cfg["cutoff"])
        for m in range(t + 1, stop_at + 1):
            if not day.printed[i, m]:
                continue
            if day.h[i, m] >= lvl:
                em = m
                px = max(lvl, float(day.o[i, m]))
                px = min(max(px, float(day.l[i, m])), float(day.h[i, m]))
                break
        if em is None:
            t = stop_at          # stale pick: re-rank
            continue
        if px < cfg["min_px"]:
            t = em
            continue
        budget = S.TICKETS[ti]
        v5 = float(day.cumv[i, em - 1] - day.cumv[i, max(em - 6, 0)])
        sh = int(min(budget / px, S.VOL_CAP * v5))
        if sh < 1:
            t = em
            continue
        ex_m, ex_px, reason = walk_exit(day, Fd, i, em, px, cfg)
        if ex_px is None:
            t = em
            continue
        gross = (ex_px - px) * sh
        legs.append(dict(sym=day.syms[i], entry_min=em, entry=px, exit_min=ex_m,
                         exit=ex_px, shares=sh, reason=reason, gross=gross,
                         ticket=ti))
        ti += 1
        t = max(t + cfg["step"], ex_m + 1)
    return legs


def main(outp):
    T10 = [10_000.0] * 7
    base = dict(rank="coil", stop_pct=None)
    jobs = {
        "R4_15k": dict(base, _tk=ORIG_TICKETS),
        "R4": dict(base),
        "SO15": dict(base, scale_out_at=0.15, scale_out_frac=1 / 3),
        "SO25": dict(base, scale_out_at=0.25, scale_out_frac=1 / 3),
        "SO25skip": dict(base, scale_out_at=0.25, scale_out_frac=1 / 3, so_skip_p=0.30),
        "SO50": dict(base, scale_out_at=0.50, scale_out_frac=1 / 3),
        "WICK3": dict(base, wick_guard=3.0),
        "PKDELAY": dict(base, peak_delay=True),
        "EXIT13": dict(base, exit_end=L.mgrid(13, 0), cutoff=L.mgrid(12, 30)),
        "CUT12": dict(base, cutoff=L.mgrid(12, 0)),
        "UW60": dict(base, uw_min=60),
        "UW120": dict(base, uw_min=120),
        "TS120": dict(base, time_stop=120),
        "ORB_r5": dict(base, _armed=True, trigger="orb", rearm=5),
        "ORB_r30": dict(base, _armed=True, trigger="orb", rearm=30),
        "PMH_r5": dict(base, _armed=True, trigger="pmh", rearm=5),
        "PMH_r30": dict(base, _armed=True, trigger="pmh", rearm=30),
        # retained old components, removed one at a time (batch 2)
        "TRAILFLAT": dict(base, trail_thr=9.0),             # C11 pressure-trail off
        "NOTRAIL": dict(base, trail_pct=None),
        "NOBEAR": dict(base, bearish_exit=False),
        "NOGAP": dict(base, gap7_max=9.0, gap7_max_other=9.0),  # calm-gap gate off
        "GAP20": dict(base, gap7_max=0.20),                 # no 35% top-name allowance
        "TRAIL30": dict(base, trail_pct=0.30),              # AX16 Y2-favoured width
        "BEARNEXT": dict(base, bear_next=True),             # fill check
    }
    only = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    if only:
        jobs = {k: v for k, v in jobs.items() if k in only}
    cfgs = {}
    for k, v in jobs.items():
        v = dict(v)
        tk = v.pop("_tk", T10)
        armed = v.pop("_armed", False)
        cfgs[k] = (S.default_cfg(**v), tk, armed)
    out = {k: [] for k in cfgs}
    ds = R.dates()
    t0 = time.time()
    for n, date in enumerate(ds):
        Fd = F.load(date)
        if Fd is None:
            continue
        day = L.load_day(date)
        if day is None:
            continue
        for k, (cfg, tk, armed) in cfgs.items():
            S.TICKETS = tk
            legs = (run_day_armed if armed else S.run_day)(day, Fd, dict(cfg))
            for x in legs:
                x.pop("i", None)
                x["date"] = date
                out[k].append({kk: (float(vv) if isinstance(vv, (np.floating, np.integer)) else vv)
                               for kk, vv in x.items()})
        if (n + 1) % 100 == 0:
            print(f"  {n+1}/{len(ds)} {time.time()-t0:.0f}s", flush=True)
    S.TICKETS = ORIG_TICKETS
    Path(outp).write_text(json.dumps({"ndays": len(ds), "legs": out}, default=float))
    r4 = out.get("R4_15k")
    if r4 is not None:
        print("identity R4_15k n=", len(r4), "flat10 total=",
              round(sum(x["net_flat"] for x in r4), 2))
    print("done", round(time.time() - t0), {k: len(v) for k, v in out.items()})


if __name__ == "__main__":
    main(sys.argv[1])
