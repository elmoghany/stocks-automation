"""R-campaign Phase 2: SEQUENTIAL TICKET ROTATION simulator.

CASH RULES (user 2026-08-09, hard constraints):
  * ONE position at a time -- ticket N+1 deploys only after ticket N
    has fully exited. Never two open names.
  * Flat $15,000 tickets, final ticket $10,000, up to $100,000/day.

THE IDEA: Z104 marries the whole day to one 7AM pick; every re-entry
returns to the same name. Rotation frees each ticket: when a ticket
exits, the NEXT ticket goes to whichever name ranks best on the
CURRENT 5-minute data (coiled-first, premarket... rather, as-of-now
pressure order). The day becomes up to 7 information-fresh sequential
picks. Fully causal: ranking at time t uses bars <= t only; a name is
eligible only after its +10% crossing has printed.

Reuses day-trading.py::simulate_trades per ticket (max_trades=1,
entry_start=t, Z104 exit machinery, halt_aware, 50bps premarket
spread, causal sizing). Only the FIRST entry group of each call is
consumed; control then returns to the rotation loop at its exit time.

Configs (CFGS): R020 full rotation, R021 rotate-on-loss-only,
R023 no-rotation baseline (same-name ladder under the flat schedule),
R024 top-3 restriction, R025/R026 stale-pick escape, R028 late-entry
window sweep, R029 afternoon-only control.

Usage: python plan/rotation_sim.py R020 [--days N]  (N=quick smoke)
Results appended to data/massive/rotation_results.json.
"""

import gzip
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
_spec = importlib.util.spec_from_file_location("px", ROOT / "plan/penny_x100.py")
px = importlib.util.module_from_spec(_spec)
sys.modules["px"] = px
_spec.loader.exec_module(px)
dt = px.ps          # day-trading module (loaded by the x100 chain)
axb = px.axb

M1 = ROOT / "data/massive/m1"
RES_F = ROOT / "data/massive/rotation_results.json"
TICKETS = [15_000.0] * 6 + [10_000.0]          # user schedule: 6x15k + 10k
SCAN_STEP = 5                                   # minutes between re-ranks
EXIT_END = dtime(15, 0)

# Z104's OWN merged sim machinery -- pulled from the registry so the
# rotation ticket trades exactly like the champion (incl. its buy_set
# pattern exclusions). Only capital keys are overridden: budget is
# per-ticket, the daily cap and ticket schedule are enforced by the
# rotation loop itself, and max_trades=1 hands control back after one
# entry+exit.
SIMKW = dict(px.BYID["Z104"]["sim"])
for _k in ("entry_ticket_schedule", "daily_deploy_cap", "budget"):
    SIMKW.pop(_k, None)
SIMKW.update(verbose=False, max_trades=1, daily_deploy_cap=None)

CFGS = {
    "R020": dict(desc="full rotation, re-pick every freed ticket"),
    "R021": dict(desc="rotate only after a LOSING ticket", on_win="stay"),
    "R023": dict(desc="no-rotation baseline: same-name ladder, flat "
                      "15k schedule", rotate=False),
    "R024": dict(desc="rotation restricted to current top-3", top=3),
    "R025": dict(desc="R020 + stale-pick escape 09:30",
                 escape=dtime(9, 30)),
    "R026": dict(desc="R020 + stale-pick escape 10:00",
                 escape=dtime(10, 0)),
    "R028a": dict(desc="rotation, last new ticket 13:00",
                  entry_cutoff=dtime(13, 0)),
    "R028b": dict(desc="rotation, last new ticket 14:00",
                  entry_cutoff=dtime(14, 0)),
    "R029": dict(desc="CONTROL afternoon-only rotation 12:00-15:00",
                 entry_open=dtime(12, 0), entry_cutoff=dtime(14, 0)),
}


def bars_for(sym, date):
    f = M1 / f"{sym}_{date}.csv"
    if not f.exists() or f.read_text(errors="ignore").startswith("EMPTY"):
        return None
    try:
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        df.index = df.index.tz_convert("America/New_York")
        return df
    except Exception:
        return None


def day_candidates(cs, date, dfs):
    """Pre-compute per-candidate causal series needed by the ranker."""
    out = []
    for c in sorted(cs, key=lambda x: -x["gain_pct"])[:16]:
        pc = c.get("prev_close") or 0
        if pc <= 0:
            continue
        df = dfs.get(c["symbol"])
        if df is None:
            df = bars_for(c["symbol"], date)
            dfs[c["symbol"]] = df
        if df is None:
            continue
        thr = 1.10 * pc
        cross = None
        for ts, hi in zip(df.index, df["High"].values):
            if ts.time() > dtime(14, 0):
                break
            if float(hi) >= thr:
                cross = ts.time()
                break
        if cross is None:
            continue
        w7 = df[df.index.time <= dtime(7, 0)]
        gap7 = (float(w7["Close"].iloc[-1]) / pc - 1) * 100 if len(w7) \
            else None
        out.append({"c": c, "df": df, "pc": pc, "cross": cross,
                    "gap7": gap7, "halal": None})
    return out


def rank_at(cands, t, top=None):
    """Causal rank at clock time t: crossed names only; coiled group
    first (last<=t close / high<=t >= 0.95), pressure(30) order within."""
    scored = []
    for r in cands:
        if r["cross"] > t:
            continue
        w = r["df"][r["df"].index.time <= t]
        if len(w) < 3:
            continue
        last = float(w["Close"].iloc[-1])
        hi = float(w["High"].max())
        coil = last / hi if hi > 0 else 0
        prs = None
        if len(w) >= 5:
            cd = dt.Candles(w)
            prs = cd.pressure(cd.n - 1, 30, 20_000)
        scored.append(((0 if coil >= 0.95 else 1,
                        -(prs if prs is not None else -1)), r))
    scored.sort(key=lambda x: x[0])
    rs = [r for _, r in scored]
    return rs[:top] if top else rs


def gates_ok(r, is_top):
    lim = 35.0 if is_top else 20.0
    if r["gap7"] is None or r["gap7"] > lim:
        return False
    if r["halal"] is None:
        r["halal"] = axb.halal_pt(r["c"]["symbol"], r["c"]["date"],
                                  r["pc"])
    return r["halal"]


def run_day(cands, date, cfg):
    entry_open = cfg.get("entry_open", dtime(7, 0))
    cutoff = cfg.get("entry_cutoff", dtime(12, 0))
    rotate = cfg.get("rotate", True)
    trades = []
    t = entry_open
    ticket_i = 0
    last_sym, last_pnl = None, 0.0
    while ticket_i < len(TICKETS):
        if t >= cutoff:
            break
        # pick at time t
        pool = rank_at(cands, t, cfg.get("top"))
        pick = None
        if not rotate and last_sym is not None:
            pick = next((r for r in pool
                         if r["c"]["symbol"] == last_sym), None)
        elif cfg.get("on_win") == "stay" and last_sym is not None \
                and last_pnl > 0:
            pick = next((r for r in pool
                         if r["c"]["symbol"] == last_sym), None)
        if pick is None:
            for i, r in enumerate(pool):
                if gates_ok(r, i == 0):
                    pick = r
                    break
        if pick is None:
            t = _step(t)
            continue
        # simulate ONE ticket on this name from t
        df = pick["df"]
        w = df[(df.index.time >= entry_open) & (df.index.time < EXIT_END)]
        if len(w) < 20:
            t = _step(t)
            continue
        esc = cfg.get("escape")
        tr = dt.simulate_trades(
            w, prev_close=pick["pc"], budget=TICKETS[ticket_i],
            entry_start=max(t, pick["cross"]), **SIMKW)
        tr = [x for x in tr if x.get("entry_time") is not None]
        if not tr:
            # never triggered: stale-pick escape re-ranks at esc, else
            # step forward and re-pick
            t = esc if (esc and t < esc) else _step(t)
            last_sym = pick["c"]["symbol"] if not rotate else last_sym
            continue
        first_entry = tr[0]["entry_time"]
        grp = [x for x in tr if x["entry_time"] == first_entry]
        pnl = sum(x["pnl"] for x in grp)
        exit_t = max(x["exit_time"] for x in grp).time()
        for x in grp:
            x["ticket"] = ticket_i
            x["symbol"] = pick["c"]["symbol"]
        trades += grp
        ticket_i += 1
        last_sym, last_pnl = pick["c"]["symbol"], pnl
        t = _step(max(t, exit_t))
    return trades


def _step(t):
    m = t.hour * 60 + t.minute + SCAN_STEP
    m = (m // SCAN_STEP) * SCAN_STEP
    return dtime(min(m // 60, 23), m % 60)


def run(cfg_id, max_days=None):
    cfg = CFGS[cfg_id]
    print(f"{cfg_id}: {cfg['desc']}", flush=True)
    out = {}
    for lab in ("year", "y2025"):
        byday = px.load_by_day(lab, 50, "novol")
        total, days, monthly = 0.0, 0, defaultdict(float)
        items = sorted(byday.items())
        if max_days:
            items = items[:max_days]
        for n, (date, cs) in enumerate(items, 1):
            dfs = {}
            cands = day_candidates(cs, date, dfs)
            if not cands:
                continue
            tr = run_day(cands, date, cfg)
            if tr:
                p = sum(x["pnl"] for x in tr)
                total += p
                days += 1
                monthly[date[:7]] += p
            if n % 50 == 0:
                print(f"  ..{lab} {n}/{len(items)} "
                      f"({days}d ${total:+,.0f})", flush=True)
        negm = sum(1 for v in monthly.values() if v < 0)
        print(f" {cfg_id} {lab:<6} {days:>4}d ${total:>+12,.0f} "
              f"{negm}/{len(monthly)}  [{cfg['desc']}]", flush=True)
        out[lab] = {"total": round(total), "days": days, "negm": negm,
                    "nmonths": len(monthly)}
    res = json.loads(RES_F.read_text()) if RES_F.exists() else {}
    res[cfg_id] = {"desc": cfg["desc"], **out}
    RES_F.write_text(json.dumps(res, indent=1))
    return out


if __name__ == "__main__":
    md = None
    argv = sys.argv[1:]
    if "--days" in argv:
        i = argv.index("--days")
        md = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("--")]
    for cid in (args or ["R020"]):
        run(cid, md)
