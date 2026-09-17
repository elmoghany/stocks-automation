"""CHAMPION-REPLAY: a sequential-ticket engine on the causal universe.

WHAT THIS IS AND IS NOT. `plan/rotation_sim.py` + `day-trading.py` stay
the authoritative engine for anything labelled C31..C37; every champion
ABLATION in this line is run there, through new CFGS entries, so the
champion's own machinery is never re-implemented for those rows. This
file exists for the one job that engine cannot do cheaply: score a
walk-forward MODEL's picks over 444 days, thousands of times, on a
universe defined by the live scanner's own rule rather than by the
gapper pool file. It is a RE-IMPLEMENTATION and is labelled as one.

It is checked three ways before any number from it is reported
(`--selftest`):
  * HOLD-IS-ZERO: a config that enters and exits in the same minute at
    zero cost must return exactly $0.
  * POISON: corrupting every bar strictly after the decision minute
    must not move a single pick or entry price.
  * FORESIGHT: ranking on the realised forward return must dominate,
    and the anti-foresight mirror must lose by a similar amount.

THE FRAME (the user's standing cash rules, unchanged):
  one position at a time; $15,000 x 6 then $10,000; <= 7 tickets/day;
  <= $100,000/day; long only; flat by 15:00; never a bar after the
  decision minute in any decision.

FILL CONVENTION (the repo's post-retraction standard):
  a decision taken at grid minute m may first fill at the OPEN of the
  next PRINTED bar after m. Eligibility proven by bar m is therefore
  never tradeable inside bar m (RS_DEFER), and the decision bar's own
  close is never a fill price (MX retraction #1).

COSTS: reported both ways, always.
  flat10   -- 10 bps a side, the project's incumbent ladder
  measured -- per-fill half-spread from the trailing tape plus a
              square-root impact term (`cp_cost.py`), calibrated
              against plan/cr_cost.py's 1-second-tape model on the
              symbol-days where that model has data.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as L                                          # noqa: E402
import cp_feat as F                                         # noqa: E402

TICKETS = [15_000.0] * 6 + [10_000.0]
VOL_CAP = 0.20               # of trailing 5-minute share volume
FLAT_BPS = 10.0


def default_cfg(**over):
    c = dict(
        universe="LAST",        # LAST = live scanner; HIGH = RS_CROSS
        t_start=L.mgrid(9, 35), cutoff=L.mgrid(14, 30),
        exit_end=L.M_1500, step=5,
        rank="champ",           # see rank_key
        invert=False, rand=False, seed=0,
        trigger="defer",        # defer | orb | pmh
        gap7_max=0.35, gap7_max_other=0.20, min_px=2.0,
        halal=None,             # None = ignored (this line's mandate)
        stop_pct=0.08,
        trail_pct=0.20, trail_lo=0.10, trail_hi=0.40, trail_thr=0.30,
        scale_out_at=None, scale_out_frac=0.5,
        bearish_exit=True, time_stop=None,
        rotate=True, ntickets=7,
        score=None,             # (n, ngrid) array of model scores
    )
    c.update(over)
    return c


# ---------------------------------------------------------------------
# ranking keys -- all strictly causal (they read the feature grid only)
# ---------------------------------------------------------------------
def rank_key(Fd, gi, cfg):
    """Sort key array; SMALLER sorts first."""
    r = cfg["rank"]
    if r == "champ":
        coil = Fd["coil"][:, gi]
        prs = Fd["pressure30"][:, gi]
        grp = np.where(coil >= 0.95, 0.0, 1.0)
        k = grp * 10.0 - np.nan_to_num(prs, nan=-1.0)
    elif r == "gain_asc":
        k = Fd["gain_now"][:, gi]
    elif r == "coil":
        k = -np.nan_to_num(Fd["coil"][:, gi], nan=0.0)
    elif r == "pressure":
        k = -np.nan_to_num(Fd["pressure30"][:, gi], nan=-1.0)
    elif r == "vwap_lo":
        k = np.nan_to_num(Fd["vwap_dist"][:, gi], nan=9.9)
    elif r == "rvol_hi":
        k = -np.nan_to_num(Fd["rvol_now"][:, gi], nan=0.0)
    elif r == "model":
        k = -np.nan_to_num(cfg["score"][:, gi], nan=-1e9)
    elif r == "none":
        k = np.zeros(Fd["coil"].shape[0])
    else:
        raise ValueError(r)
    return -k if cfg["invert"] else k


def gates(Fd, cfg):
    """Static per-name gates, all pre-open or prior-session.

    The champion's SYMMETRIC GAP ALLOWANCE (rotation_sim, 2026-09-01):
    the wider 35% 07:00-gap limit belongs to the name the RANK put on
    top; everything else is held to 20%. Returned as two masks so the
    caller can apply the right one to the right name."""
    g7 = Fd["gap7"]
    top = ~(np.isfinite(g7) & (g7 > cfg["gap7_max"]))
    oth = ~(np.isfinite(g7) & (g7 > cfg["gap7_max_other"]))
    if cfg["halal"] is not None:
        hal = np.array([s in cfg["halal"] for s in Fd["syms"]])
        top = top & hal
        oth = oth & hal
    return top, oth


# ---------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------
def run_day(day, Fd, cfg, cost=None):
    """One session. Returns a list of leg dicts."""
    grid = list(Fd["grid"])
    gidx = {m: i for i, m in enumerate(grid)}
    elig = Fd["elig_last" if cfg["universe"] == "LAST" else "elig_high"]
    gate_top, gate_oth = gates(Fd, cfg)
    legs = []
    rng = np.random.default_rng(
        abs(hash((cfg["seed"], day.n, len(day.syms)))) % (2 ** 31))
    t = cfg["t_start"]
    ti = 0
    deployed = 0.0
    last_i = None
    while ti < cfg["ntickets"] and t < cfg["cutoff"]:
        if t not in gidx:
            t += 1
            continue
        gi = gidx[t]
        cand = np.where(elig[:, gi])[0]
        if len(cand) == 0:
            t += cfg["step"]
            continue
        if cfg["rand"]:
            order = cand[rng.permutation(len(cand))]
        else:
            k = rank_key(Fd, gi, cfg)[cand]
            order = cand[np.argsort(k, kind="stable")]
        # the wider gap allowance follows the RANKED top name, before any
        # shuffle, so the random control gets it on the same symbol
        ranked_top = int(cand[np.argsort(rank_key(Fd, gi, cfg)[cand],
                                         kind="stable")[0]])
        if not cfg["rotate"] and last_i is not None and last_i in set(order):
            order = np.concatenate(([last_i], order[order != last_i]))
        budget = TICKETS[ti]
        if deployed + budget > 100_000.0:
            break
        leg = None
        for i in order[:8]:
            i = int(i)
            if not (gate_top[i] if i == ranked_top else gate_oth[i]):
                continue
            leg = _try_ticket(day, Fd, i, t, gi, budget, cfg, cost)
            if leg is not None:
                break
        if leg is None:
            t += cfg["step"]
            continue
        leg["ticket"] = ti
        legs.append(leg)
        deployed += leg["shares"] * leg["entry"]
        last_i = leg["i"]
        ti += 1
        t = max(t + cfg["step"], leg["exit_min"] + 1)
    return legs


def _next_print(day, i, m0, limit=60):
    row = day.printed[i]
    for m in range(m0, min(m0 + limit, L.NMIN)):
        if row[m]:
            return m
    return None


def _try_ticket(day, Fd, i, t, gi, budget, cfg, cost):
    """Arm name i at decision minute t; None when it never fills."""
    trig = cfg["trigger"]
    if trig == "defer":
        em = _next_print(day, i, t + 1)
        if em is None:
            return None
        px = float(day.o[i, em])
    else:
        if trig == "orb":
            if getattr(day, "_orb", None) is None:
                day._orb = day.runhigh_from(L.M_OPEN)[:, L.M_OPEN + 4]
            lvl = float(day._orb[i])
        elif trig == "pmh":
            lvl = float(day.pc[i] * (1 + Fd["pm_high_gain"][i]))
        else:
            raise ValueError(trig)
        if not np.isfinite(lvl) or lvl <= 0:
            return None
        em, px = None, None
        for m in range(t + 1, min(t + 61, cfg["exit_end"])):
            if not day.printed[i, m]:
                continue
            if day.h[i, m] >= lvl:
                em = m
                px = max(lvl, float(day.o[i, m]))
                px = min(max(px, float(day.l[i, m])), float(day.h[i, m]))
                break
        if em is None:
            return None
    if not np.isfinite(px) or px < cfg["min_px"]:
        return None
    v5 = float(day.cumv[i, em - 1] - day.cumv[i, max(em - 6, 0)])
    sh = int(min(budget / px, VOL_CAP * v5))
    if sh < 1:
        return None
    ex_m, ex_px, reason = _walk_exit(day, Fd, i, em, px, cfg)
    if ex_px is None:
        return None
    gross = (ex_px - px) * sh
    c_flat = (px + ex_px) * sh * FLAT_BPS / 10_000.0
    c_meas = c_flat
    if cost is not None:
        c_meas = cost(day, i, em, px, sh) + cost(day, i, ex_m, ex_px, sh)
    return dict(i=i, sym=day.syms[i], entry_min=em, entry=px,
                exit_min=ex_m, exit=ex_px, shares=sh, reason=reason,
                gross=gross, net_flat=gross - c_flat,
                net_meas=gross - c_meas, cost_flat=c_flat, cost_meas=c_meas)


def _sell_fill(day, i, m, level):
    """Gap-through honest fill: a level hit inside bar m fills at
    min(level, Open) and is clamped into [Low, High]."""
    o = float(day.o[i, m])
    px = min(level, o)
    return float(min(max(px, day.l[i, m]), day.h[i, m]))


def _walk_exit(day, Fd, i, em, entry, cfg):
    stop = entry * (1 - cfg["stop_pct"]) if cfg["stop_pct"] else None
    peak = entry
    end = cfg["exit_end"]
    scaled = False
    so = (entry * (1 + cfg["scale_out_at"])
          if cfg["scale_out_at"] else None)
    part_px, part_w = 0.0, 0.0     # share-weighted scale-out proceeds
    w = cfg["scale_out_frac"] if so is not None else 0.0

    def blend(px):
        """Effective exit price: the scale-out fill and the final fill,
        weighted by the fraction of the ticket each one closed."""
        return part_px * part_w + px * (1.0 - part_w)

    for m in range(em + 1, end + 1):
        if not day.printed[i, m]:
            continue
        lo, hi, c, o = (float(day.l[i, m]), float(day.h[i, m]),
                        float(day.c[i, m]), float(day.o[i, m]))
        if stop is not None and lo <= stop:
            return (m, blend(_sell_fill(day, i, m, stop)),
                    f"stop {stop:.2f}")
        if so is not None and not scaled and hi >= so:
            # a limit ABOVE the market: a gap through it fills at the
            # OPEN, which is better, so take max(level, open), clamped
            px = min(max(max(so, o), lo), hi)
            part_px, part_w, scaled = px, w, True
        peak = max(peak, hi)
        if cfg["trail_pct"]:
            tw = cfg["trail_pct"]
            p10 = _pressure_at(day, i, m, 10)
            if p10 is not None:
                if p10 <= -cfg["trail_thr"]:
                    tw = cfg["trail_lo"]
                elif p10 >= cfg["trail_thr"]:
                    tw = cfg["trail_hi"]
            lvl = peak * (1 - tw)
            if lo <= lvl < peak:
                return m, blend(_sell_fill(day, i, m, lvl)), f"trail {tw:.2f}"
        if cfg["bearish_exit"] and c > entry and _bearish(day, i, m):
            return m, blend(c), "bearish"
        if cfg["time_stop"] and (m - em) >= cfg["time_stop"]:
            return m, blend(c), "time-stop"
    m = end
    while m > em and not day.printed[i, m]:
        m -= 1
    if m <= em:
        return None, None, None
    return m, blend(float(day.c[i, m])), "flatten"


def _pressure_at(day, i, m, nbars, min_vol=20_000.0):
    rown = day.cumn[i]
    cn = rown[m]
    if cn < 3:
        return None
    j = int(np.searchsorted(rown[:m + 1], cn - nbars, side="right"))
    v0 = day.cumv[i, j - 1] if j > 0 else 0.0
    vol = day.cumv[i, m] - v0
    if vol < min_vol or vol <= 0:
        return None
    s0 = day.cumsv[i, j - 1] if j > 0 else 0.0
    return float((day.cumsv[i, m] - s0) / vol)


def _prev_print(day, i, m):
    for k in range(m - 1, max(m - 90, -1), -1):
        if day.printed[i, k]:
            return k
    return None


def _bearish(day, i, m):
    """The dominant champion exit: a bearish ENGULFING bar.

    day-trading.py::Candles.bearish_patterns carries nine shapes; this
    keeps the one that produced the bulk of the champion's exits (631
    'bearish' exits, +$153k, on C37F-hf2 year) and is exact for it:
      previous bar bullish, this bar bearish, this open >= max(prev o,
      prev c), this close <= min(prev o, prev c), |c-o| > |pc-po|."""
    p = _prev_print(day, i, m)
    if p is None:
        return False
    po, pc = float(day.o[i, p]), float(day.c[i, p])
    o, c = float(day.o[i, m]), float(day.c[i, m])
    return (pc > po and c < o and o >= max(po, pc) and c <= min(po, pc)
            and abs(c - o) > abs(pc - po))


# ---------------------------------------------------------------------
def run(dates, cfg, cost=None, scores=None, progress=False):
    return run_many(dates, {"_": (cfg, cost, scores)},
                    progress=progress)["_"]


def run_many(dates, jobs, progress=False):
    """Run several (cfg, cost, scores) triples over the same dates,
    loading each date's panel and feature grid ONCE. The panel objects
    are identical for every job, so no config can influence another."""
    out = {k: [] for k in jobs}
    for n, date in enumerate(dates):
        Fd = F.load(date)
        if Fd is None:
            continue
        day = L.load_day(date)
        if day is None:
            continue
        for key, (cfg, cost, scores) in jobs.items():
            c = dict(cfg)
            if scores is not None:
                c["score"] = scores.get(date)
                if c["score"] is None:
                    continue
            for leg in run_day(day, Fd, c, cost):
                leg["date"] = date
                leg.pop("i", None)
                out[key].append(leg)
        if progress and (n + 1) % 50 == 0:
            print(f"  {n+1}/{len(dates)}", flush=True)
    return out


def summarize(legs, ndays):
    if not legs:
        return dict(n=0)
    g = np.array([x["gross"] for x in legs])
    nf = np.array([x["net_flat"] for x in legs])
    nm = np.array([x["net_meas"] for x in legs])
    byday = {}
    for x in legs:
        byday[x["date"]] = byday.get(x["date"], 0.0) + x["net_flat"]
    mon = {}
    for d, v in byday.items():
        mon[d[:7]] = mon.get(d[:7], 0.0) + v
    months = sorted(mon)
    tot = float(nf.sum())
    best = max(byday.values()) if byday else 0.0
    return dict(n=len(legs), gross_tkt=float(g.mean()),
                flat_tkt=float(nf.mean()), meas_tkt=float(nm.mean()),
                total_flat=tot, total_meas=float(nm.sum()),
                per_month=tot / max(len(months), 1),
                months=len(months),
                months_pos=sum(1 for m in months if mon[m] > 0),
                tkts_per_day=len(legs) / max(ndays, 1),
                ex_best=tot - best,
                traded_days=len(byday))
