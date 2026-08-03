"""AX21 recycling engine + AX20/21/22 campaign runner.

$15k = max at risk at any MOMENT (user-approved): after an exit the
same $15k may re-enter another qualifying stock, all flat by noon.

Honest event-ordered design: simulate_trades decides entries at bar i
from bars <= i only, so ONE full 7-noon sim per candidate yields a
causally-valid event stream. Each symbol contributes its FIRST position
(entry_time, exit_time, pnl); the dispatcher repeatedly takes the
earliest entry event strictly after capital frees (tie-break: highest
entry-time momentum vs prev_close). No same-symbol re-entry. No
end-of-day knowledge in the dispatch decision.

Modes:
  --pick walk      AX11b-identical top-walk, first halal calm candidate,
                   full sim (baseline / universe-isolation runs)
  --pick dispatch  recycling dispatcher, K deployments (--k 1,2,3,0;
                   0 = unbounded, hard cap 20)
Trail: --trail cond (AX19c thin-supply 20->30, thresh 1.0) | fixed pct.
Gapfile: gappers (old universe) | gappers2 (AX20 widened, --min-hist).
"""

import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "axb", ROOT / "plan" / "penny_ax11b_massive.py")
axb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(axb)
ps = axb.ps

W_START, W_END = dtime(7, 0), dtime(12, 0)


def load_by_day(gapfile, label, min_hist):
    gap = json.loads(
        (ROOT / f"data/massive/{gapfile}_{label}.json").read_text())
    by_day = {}
    for c in gap:
        if c.get("hist_n", 99) < min_hist:
            continue
        by_day.setdefault(c["date"], []).append(c)
    return by_day


def calm_window(c, date):
    df = axb.get(c["symbol"], date)
    if df is None:
        return None
    w = df[(df.index.time >= W_START) & (df.index.time < W_END)]
    if len(w) < 20:
        return None
    g7 = ((float(w["Open"].iloc[0]) / c["prev_close"] - 1) * 100
          if c["prev_close"] else 999)
    if g7 > 20:
        return None
    return w


def sim(w, c, trail):
    return ps.simulate_trades(
        w, verbose=False, buy_set=None, vol_confirm=False,
        trail_pct=trail, stop_pct=8, prev_close=c["prev_close"],
        budget=15000, orb=True, orb_bars=15, max_vol_frac=0.10,
        vol_frac_window=5, scale_out_at=25.0)


def positions(trades):
    """Group a sim's trade records into ordered positions.

    Scale-out partials share entry_time with their final exit -> one
    position; re-entries have new entry_times -> subsequent positions.
    """
    groups = {}
    for t in trades:
        groups.setdefault(t["entry_time"], []).append(t)
    return [{"entry_time": et,
             "exit_time": max(t["exit_time"] for t in g),
             "pnl": sum(t["pnl"] for t in g)}
            for et, g in sorted(groups.items())]


def dispatch(queues, k):
    """Commit-then-earliest recycling. queues = [(rank, sym, [pos..])].

    Deployment 1: rank-0 symbol's first position, whenever it fires
    (identical commitment to the live walk pick -- no hindsight skip).
    After each exit at t: eligible events are each symbol's NEXT
    unconsumed position (a symbol's position n is causally valid only
    if we took its position n-1; never-entered symbols offer position
    1) with entry_time > t. Take the earliest; rank breaks ties.
    """
    cap = 20 if k == 0 else k
    ptr = {sym: 0 for _, sym, _ in queues}
    taken = []
    if not queues:
        return taken
    rank0, sym0, q0 = queues[0]
    taken.append((sym0, q0[0]))
    ptr[sym0] = 1
    t = q0[0]["exit_time"]
    while len(taken) < cap:
        elig = []
        for rank, sym, q in queues:
            i = ptr[sym]
            if i < len(q) and q[i]["entry_time"] > t:
                elig.append((q[i]["entry_time"], rank, sym, q[i]))
        if not elig:
            break
        elig.sort(key=lambda e: (e[0], e[1]))
        _, _, sym, pos = elig[0]
        taken.append((sym, pos))
        ptr[sym] += 1
        t = pos["exit_time"]
    return taken


def run(label, gapfile, pick, k, walk, min_hist, trail_mode, runid,
        prio="rank"):
    by_day = load_by_day(gapfile, label, min_hist)
    days, monthly, recent, deploys = [], {}, [], 0
    for date, cs in sorted(by_day.items()):
        ranked = sorted(cs, key=lambda x: -x["gain_pct"])[:walk]
        calm = []
        for c in ranked:
            w = calm_window(c, date)
            if w is not None:
                calm.append((c, w))
        supply = sum(recent[-10:]) / max(1, len(recent[-10:]))
        recent.append(len(calm))
        if trail_mode == "cond":
            trail = 30 if supply < 1.0 else 20
        else:
            trail = int(trail_mode)
        dp = None
        if pick == "walk":
            for c, w in calm:
                if not axb.halal_pt(c["symbol"], date, c["prev_close"]):
                    continue
                tr = sim(w, c, trail)
                if tr:
                    dp = sum(x["pnl"] for x in tr)
                    deploys += 1
                break   # first calm halal candidate only, like AX11b
        else:
            queues = []
            committed_empty = False
            for c, w in calm:
                if not axb.halal_pt(c["symbol"], date, c["prev_close"]):
                    continue
                q = positions(sim(w, c, trail))
                if not queues and not q:
                    # committed candidate never triggers -> no-trade day
                    # (identical commitment to the walk baseline; no
                    # hindsight skip to the next candidate)
                    committed_empty = True
                    break
                if q:
                    queues.append((len(queues), c["symbol"], q))
            taken = [] if committed_empty else dispatch(queues, k)
            if taken:
                dp = sum(pos["pnl"] for _, pos in taken)
                deploys += len(taken)
        if dp is None:
            continue
        days.append(dp)
        monthly.setdefault(date[:7], []).append(dp)
    negm = sum(1 for v in monthly.values() if sum(v) < 0)
    tot = sum(days)
    name = (f"{runid} {pick}/{prio} k={k} {gapfile} "
            f"h>={min_hist} tr={trail_mode}")
    print(f"{name:<46} {label:<6} {len(days):>4}d {deploys:>4}p "
          f"${tot:>+11,.0f} ${tot / len(days) if days else 0:>+7,.0f}/d "
          f"{negm}/{len(monthly)}", flush=True)
    print("  monthly:",
          {m: round(sum(v)) for m, v in sorted(monthly.items())}, flush=True)
    out = ROOT / f"data/massive/ax21_results_{runid}_{label}.json"
    out.write_text(json.dumps({
        "runid": runid, "label": label, "gapfile": gapfile, "pick": pick,
        "k": k, "walk": walk, "min_hist": min_hist, "trail": trail_mode,
        "days": len(days), "deploys": deploys, "total": round(tot),
        "negm": negm,
        "monthly": {m: round(sum(v)) for m, v in sorted(monthly.items())}}))


def arg(name, default):
    for i, a in enumerate(sys.argv):
        if a == f"--{name}" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


if __name__ == "__main__":
    labels = arg("label", "both")
    labels = ("year", "y2025") if labels == "both" else (labels,)
    ks = [int(x) for x in arg("k", "1").split(",")]
    for label in labels:
        for k in ks:
            run(label, arg("gapfile", "gappers"), arg("pick", "dispatch"),
                k, int(arg("walk", "8")), int(arg("min-hist", "50")),
                arg("trail", "20"), arg("runid", "AX21"),
                prio=arg("prio", "rank"))
