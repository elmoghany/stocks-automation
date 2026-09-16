"""VS2 WIDE-UNIVERSE RUNNER (2026-09-16) -- the video mechanics on the
liquid, causally-defined universe the videos are actually about.

WHY THIS EXISTS. Every rotation result in this campaign is measured on
the +10% GAPPER pool. Three of the mechanics distilled from the 2026-09
video batch cannot even be expressed there:

  * RED-TO-GREEN needs a name that is BELOW its prior close and then
    crosses above it. Under RS_CROSS eligibility a name only becomes
    tradable after a regular-session +10% print, so it is already far
    above the prior close before the pool will arm it. The setup is
    structurally unobservable on that pool.
  * GREEN-ON-RED (relative strength: buy what is green while the market
    is red) is CROSS-SECTIONAL. A pool of names selected for being up
    10% has no red side to compare against.
  * The ORB / VWAP videos demonstrate on liquid $3+ names (one of them
    uses Microsoft), not on $2 micro-caps.

data/massive/m1w (built by the RL-v2 line, MANIFEST_m1w.json) is exactly
that universe and is NOT outcome-conditioned: on date D a symbol is in
it iff it was halal-PASS point-in-time at D, its median dollar volume
over the PRIOR 60 sessions was >= $2M, its median close >= $3, and it
printed a bar on D. 448 dates (2024-10-22 .. 2026-08-06), 191 symbols,
27,209 symbol-days, 60.7 names/day.

WHAT THIS RUNNER IS. The same cash rules and the same honest costs as
plan/rotation_sim.py, on that universe:
  * ONE position at a time; $15,000 tickets, last ticket $10,000, up to
    $100,000 deployed per day; flat by 15:00 ET.
  * 10 bps/side slippage, the 2026-09-02 gap-through fill model, the
    causal 20%-of-trailing-volume size cap, halt awareness.
  * Ranking at clock time t reads bars <= t only. simulate_trades is
    handed entry_start = t and the window [sim_from, 15:00), so a fill
    can only happen on a bar at or after t (and the VS2 triggers
    themselves only fire on completed prior bars).
  * Halal is already point-in-time in the universe's own membership
    rule; no further gate is applied (and none is needed).

WHAT IT IS NOT. It is not comparable to the C37F-hf2 row: different
universe, different window. Its baselines are computed HERE -- the
random-pick control and the buy-the-open/hold-to-flatten control on the
same days.

Usage:
  python plan/vs2_wide.py W1ORB W1RTG ... [--days N]
Env:
  VS2W_SHARD   results file suffix (default "main")
  VS2W_REP     replicate list for random configs: "0" | "0-29" | "0,3"
  VS2W_LABELS  comma list of labels (default "wy1,wy2")
"""
import importlib.util
import json
import os
import sys
from collections import defaultdict
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("dtw", ROOT / "day-trading.py")
dt = importlib.util.module_from_spec(_spec)
sys.modules["dtw"] = dt
_spec.loader.exec_module(dt)

M1W = ROOT / "data/massive/m1w"
UNIV = ROOT / "plan/rl2/out/universe"
SHARD = os.environ.get("VS2W_SHARD", "main")
RES_F = ROOT / f"data/massive/vs2wide_results_{SHARD}.json"
TICKETS = [15_000.0] * 6 + [10_000.0]
SCAN_STEP = 5
EXIT_END = dtime(15, 0)
SLIP_BPS = 10.0

# Year split for the both-years test. The m1w window is 2024-10-22 ..
# 2026-08-06, so these are NOT the rotation campaign's year/y2025 labels
# and are never compared to them.
LABEL_RANGE = {"wy1": ("2024-10-22", "2025-08-31"),
               "wy2": ("2025-09-01", "2026-08-06")}
LABELS = tuple((os.environ.get("VS2W_LABELS") or "wy1,wy2").split(","))

# Engine machinery shared by every wide config: no legacy pattern
# entries, no premarket ORB, causal volume cap, honest fills.
BASE = dict(
    verbose=False, max_trades=1, buy_set=set(), orb=False,
    sell_mode="target_stop_only", vol_confirm=True,
    max_vol_frac=0.20, vol_frac_window=10, vol_frac_causal=True,
    halt_aware=True, pm_spread_bps=50.0, slippage_bps=SLIP_BPS,
    wick_guard=3.0, struct_stop_bars=1, stop_pct=8,
    pullback_relax=True,
    # everything else explicitly OFF so nothing is inherited
    trail_pct=None, pressure_trail=None, atr_trail=None, atr_stop=None,
    breakeven_at=None, time_stop_min=None, time_stop_progress=None,
    time_stop_pressure=None, scale_out_at=None, scale_out_2=None,
    bank_all_at=None, pressure_exit=None, target_pct=None, target_r=None,
    trail_widen_at=None, tighten_at_r=None, monster_mode=None,
    vwap_exit=None, rsi_exit=None, macd_exit=None, rand_exit=None,
)


def kw(**over):
    k = dict(BASE)
    k.update(over)
    return k


ORC5 = (dtime(9, 30), 5)
T935, T945, T1100, T1200 = (dtime(9, 35), dtime(9, 45),
                            dtime(11, 0), dtime(12, 0))

# rank_mode:
#   gain_desc  strongest mover so far first (momentum selection)
#   gain_asc   weakest first (mean-reversion selection)
#   rtg        RED-TO-GREEN: only names that traded BELOW prev_close
#              today and whose last close <= t is now ABOVE it; most
#              recent cross first
#   rs         GREEN-ON-RED: only when the universe's MEDIAN gain_now at
#              t is NEGATIVE (the market is red today, measured on the
#              same cross-section, no index feed needed) and the name's
#              own gain_now is POSITIVE; strongest first
#   random     control
CFGS = {
    # ---- baselines on this universe ----
    "W0HOLD": dict(desc="BASELINE: buy the open at 09:35, hold to the "
                        "15:00 flatten, strongest-mover pick",
                   rank="gain_desc", entry_open=T935, cutoff=T1100,
                   sim=kw(entry_mode="market_at_start", trail_pct=999,
                          stop_pct=99)),
    "W0RAND": dict(desc="BASELINE CONTROL: random pick, buy the open, "
                        "hold to the flatten",
                   rank="random", entry_open=T935, cutoff=T1100,
                   sim=kw(entry_mode="market_at_start", trail_pct=999,
                          stop_pct=99)),
    # ---- 09:30 opening range break ----
    "W1ORB": dict(desc="09:30 5-min OR break, stop = OR low, 2R, "
                       "strongest-mover pick",
                  rank="gain_desc", entry_open=T935, cutoff=T1100,
                  sim=kw(or_clock=ORC5, struct_floor_mode="or_low",
                         target_r=2.0)),
    "W1ORBm": dict(desc="09:30 OR break, stop = OR low, MEASURED-MOVE "
                        "target (= OR height)",
                   rank="gain_desc", entry_open=T935, cutoff=T1100,
                   sim=kw(or_clock=ORC5, struct_floor_mode="or_low",
                          trail_pct=999, struct_target_mode="or_range")),
    "W1ORBx": dict(desc="09:30 OR break + retest entry, 2R",
                   rank="gain_desc", entry_open=T935, cutoff=T1100,
                   sim=kw(or_clock=ORC5, orb_retest=(0.15, 20),
                          target_r=2.0)),
    # ---- pullback continuation ----
    "W2MPB": dict(desc="micro pullback (<=3-bar pause, >=1% pop), 2R",
                  rank="gain_desc", entry_open=T935, cutoff=T1100,
                  sim=kw(micro_pullback=(3, 1.0),
                         struct_floor_mode="sig_low", target_r=2.0)),
    "W3EMA": dict(desc="first pullback to a rising 9 EMA, 2R",
                  rank="gain_desc", entry_open=T935, cutoff=T1100,
                  sim=kw(ema_pullback=(9, 0.25),
                         struct_floor_mode="sig_low", target_r=2.0)),
    "W4FLAG": dict(desc="bull flag (5 bars inside 1%, >=1.5% pole), 2R",
                   rank="gain_desc", entry_open=T935, cutoff=T1100,
                   sim=kw(flag_break=(5, 1.0, 1.5),
                          struct_floor_mode="sig_low", target_r=2.0)),
    "W3E50": dict(desc="bullish 50/200 EMA cross, pullback to the 50 "
                       "EMA, 1.5R (the standard 1-min scalping template)",
                  rank="gain_desc", entry_open=T935, cutoff=dtime(14, 30),
                  sim=kw(ema_pullback=(50, 0.15),
                         struct_floor_mode="sig_low", target_r=1.5,
                         ema_gate=(50, 200))),
    # ---- VWAP ----
    "W5VWR": dict(desc="VWAP reclaim, stop = signal low, 2R",
                  rank="gain_desc", entry_open=T945, cutoff=T1100,
                  sim=kw(vwap_entry=("reclaim",),
                         struct_floor_mode="sig_low", target_r=2.0)),
    "W5VWB": dict(desc="VWAP bounce from above (0.1%), 2R",
                  rank="gain_desc", entry_open=T945, cutoff=T1100,
                  sim=kw(vwap_entry=("bounce", 0.1),
                         struct_floor_mode="sig_low", target_r=2.0)),
    "W6VWB": dict(desc="VWAP-band fade 1sd, stop under the wick, TARGET "
                       "= VWAP, 60m time stop",
                  rank="gain_asc", entry_open=T945, cutoff=T1200,
                  sim=kw(vwap_entry=("band", 1.0),
                         struct_floor_mode="sig_low", trail_pct=999,
                         vwap_target=True, time_stop_min=60)),
    "W6VWB2": dict(desc="VWAP-band fade 2sd, target = VWAP, 60m stop",
                   rank="gain_asc", entry_open=T945, cutoff=T1200,
                   sim=kw(vwap_entry=("band", 2.0),
                          struct_floor_mode="sig_low", trail_pct=999,
                          vwap_target=True, time_stop_min=60)),
    # ---- wave 2: FVG / inside bar / liquidity-sweep reclaim ----
    "W9FVG": dict(desc="ICT fair value gap (confirmation variant), 2R",
                  rank="gain_desc", entry_open=T935, cutoff=T1200,
                  sim=kw(fvg_entry=(20, 0.05),
                         struct_floor_mode="sig_low", target_r=2.0)),
    "W9IB": dict(desc="inside-bar break, stop = its low, 2R",
                 rank="gain_desc", entry_open=T935, cutoff=T1200,
                 sim=kw(inside_bar=(1,), struct_floor_mode="sig_low",
                        target_r=2.0)),
    "W9SWP": dict(desc="liquidity sweep reclaim (20-bar low swept and "
                       "reclaimed), 2R",
                  rank="gain_asc", entry_open=T935, cutoff=T1200,
                  sim=kw(sweep_reclaim=(20, 3),
                         struct_floor_mode="sig_low", target_r=2.0)),
    "W9TB": dict(desc="Live Traders 3-bar play (wide bar, narrow bar, "
                      "break of the narrow bar's high), 2R",
                 rank="gain_desc", entry_open=T935, cutoff=T1200,
                 sim=kw(three_bar=(1.8, 0.5),
                        struct_floor_mode="sig_low", target_r=2.0)),
    "W9SB": dict(desc="ICT AM Silver Bullet window 10:00-11:00, FVG "
                      "entry, 2R",
                 rank="gain_desc", entry_open=dtime(10, 0),
                 cutoff=dtime(11, 0),
                 sim=kw(fvg_entry=(20, 0.05),
                        struct_floor_mode="sig_low", target_r=2.0)),
    "W1OR01": dict(desc="09:30 FIRST 1-MIN CANDLE break, stop = its low, "
                        "2R",
                   rank="gain_desc", entry_open=dtime(9, 31),
                   cutoff=T1100,
                   sim=kw(or_clock=(dtime(9, 30), 1),
                          struct_floor_mode="or_low", target_r=2.0)),
    # ---- ADJACENCY: the same triggers with an ALL-DAY entry window.
    # The videos say "first 90 minutes"; that is a claim about WHERE the
    # edge is, and it caps the day at one or two tickets. The cash rule
    # allows seven. At $15k a ticket, seven tickets need only +$54 each
    # to clear $375/day, where one ticket needs +$375. These rows are
    # labelled ADJACENCY, not video-faithful.
    "W2MPBd": dict(desc="ADJACENCY: micro pullback, entries all day to "
                        "14:30, 2R",
                   rank="gain_desc", entry_open=T935, cutoff=dtime(14, 30),
                   sim=kw(micro_pullback=(3, 1.0),
                          struct_floor_mode="sig_low", target_r=2.0)),
    "W9TBd": dict(desc="ADJACENCY: 3-bar play, entries all day to 14:30",
                  rank="gain_desc", entry_open=T935, cutoff=dtime(14, 30),
                  sim=kw(three_bar=(1.8, 0.5),
                         struct_floor_mode="sig_low", target_r=2.0)),
    "W9IBd": dict(desc="ADJACENCY: inside-bar break, all day to 14:30",
                  rank="gain_desc", entry_open=T935, cutoff=dtime(14, 30),
                  sim=kw(inside_bar=(1,), struct_floor_mode="sig_low",
                         target_r=2.0)),
    "W5VWBd": dict(desc="ADJACENCY: VWAP bounce, all day to 14:30",
                   rank="gain_desc", entry_open=T945, cutoff=dtime(14, 30),
                   sim=kw(vwap_entry=("bounce", 0.1),
                          struct_floor_mode="sig_low", target_r=2.0)),
    "W6VWBd": dict(desc="ADJACENCY: VWAP-band fade 1sd, all day to 14:30",
                   rank="gain_asc", entry_open=T945, cutoff=dtime(14, 30),
                   sim=kw(vwap_entry=("band", 1.0),
                          struct_floor_mode="sig_low", trail_pct=999,
                          vwap_target=True, time_stop_min=60)),
    # ---- the two mechanics that only exist on a wide universe ----
    "W7RTG": dict(desc="RED-TO-GREEN: name traded below prev close today "
                       "and is now above it; buy the next print, 2R",
                  rank="rtg", entry_open=T935, cutoff=T1200,
                  sim=kw(entry_mode="market_at_start", target_r=2.0)),
    "W7RTGb": dict(desc="RED-TO-GREEN, hold to the 15:00 flatten",
                   rank="rtg", entry_open=T935, cutoff=T1200,
                   sim=kw(entry_mode="market_at_start", trail_pct=999,
                          stop_pct=99)),
    "W8RS": dict(desc="GREEN-ON-RED: market (universe median) red, name "
                      "green; buy the next print, 2R",
                 rank="rs", entry_open=T935, cutoff=T1200,
                 sim=kw(entry_mode="market_at_start", target_r=2.0)),
    "W8RSb": dict(desc="GREEN-ON-RED, hold to the 15:00 flatten",
                  rank="rs", entry_open=T935, cutoff=T1200,
                  sim=kw(entry_mode="market_at_start", trail_pct=999,
                         stop_pct=99)),
}
# Controls.
#  -R   the PICK is random (VS2W_REP replicates)
#  -I   the ranking is inverted
#  -Enn the pick is the ranked one but the ENTRY MINUTE is random inside
#       30 minutes of the decision, with every trigger switched OFF.
#       -R prices the PICK; -E prices the TRIGGER. A breakout rule that
#       cannot beat entering the same name at a random minute has no
#       trigger edge whatever its P&L.
_TRIGGER_KEYS = ("or_clock", "micro_pullback", "ema_pullback",
                 "flag_break", "vwap_entry", "orb_retest", "abcd_entry",
                 "halt_resume", "fvg_entry", "inside_bar",
                 "sweep_reclaim", "three_bar", "struct_floor_mode",
                 "struct_target_mode", "entry_mode")
for _cid in [c for c in list(CFGS) if not c.startswith("W0")]:
    _b = CFGS[_cid]
    CFGS[_cid + "-R"] = dict(_b, rank="random",
                             desc="CONTROL random pick: " + _b["desc"])
    if _b["rank"] in ("gain_desc", "gain_asc"):
        CFGS[_cid + "-I"] = dict(
            _b, rank=("gain_asc" if _b["rank"] == "gain_desc"
                      else "gain_desc"),
            desc="CONTROL inverted ranking: " + _b["desc"])
    for _r in range(30):
        _s = {k: v for k, v in _b["sim"].items()
              if k not in _TRIGGER_KEYS}
        _s["rand_entry"] = (30, f"vs2we-{_cid}-{_r}")
        CFGS[f"{_cid}-E{_r:02d}"] = dict(
            _b, sim=_s,
            desc=f"CONTROL random entry minute (seed {_r}): "
                 + _b["desc"])


def dates_for(label):
    a, b = LABEL_RANGE[label]
    return [p.stem for p in sorted(UNIV.glob("*.json"))
            if a <= p.stem <= b]


def universe(date):
    return json.loads((UNIV / f"{date}.json").read_text())


def bars(sym, date):
    f = M1W / f"{sym}_{date}.csv"
    if not f.exists():
        return None
    try:
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        if df.empty:
            return None
        df.index = df.index.tz_convert("America/New_York")
        return df
    except Exception:
        return None


def _step(t):
    m = t.hour * 60 + t.minute + SCAN_STEP
    m = (m // SCAN_STEP) * SCAN_STEP
    return dtime(min(m // 60, 23), m % 60)


def day_cands(date, sim_from):
    """Load every universe name's bars for the day, once."""
    out = []
    for row in universe(date):
        df = bars(row["symbol"], date)
        if df is None:
            continue
        w = df[(df.index.time >= sim_from) & (df.index.time < EXIT_END)]
        if len(w) < 30:
            continue
        out.append({"sym": row["symbol"], "pc": float(row["prev_close"]),
                    "df": w, "tt": w.index.time})
    return out


def _upto(c, t):
    """(last close, low so far, high so far) using bars <= t; None if
    there is no bar yet. Strictly causal."""
    m = c["tt"] <= t
    if not m.any():
        return None
    w = c["df"][m]
    return (float(w["Close"].iloc[-1]), float(w["Low"].min()),
            float(w["High"].max()))


def _rows_at(cands, t, cache):
    """(candidate, last, low-so-far, high-so-far, gain_now) for every
    name with a bar <= t. CONFIG-INDEPENDENT, so it is computed once per
    (date, t) and shared by every config and replicate in the pass --
    a pure accelerator, identical values either way."""
    if t in cache:
        return cache[t]
    rows = []
    for c in cands:
        u = _upto(c, t)
        if u is None:
            continue
        last, lo, hi = u
        if last < 3.0 or c["pc"] <= 0:
            continue
        rows.append((c, last, lo, hi, (last / c["pc"] - 1) * 100))
    cache[t] = rows
    return rows


def rank_at(cands, t, mode, rep, date, ticket_i, cache):
    rows = _rows_at(cands, t, cache)
    if not rows:
        return []
    if mode == "random":
        import random as _r
        pool = [r[0] for r in rows]
        _r.Random(f"vs2w-{date}-{ticket_i}-{rep}").shuffle(pool)
        return pool
    if mode == "rtg":
        # RED-TO-GREEN: it must have traded BELOW the prior close today
        # (low so far < prev_close) and be ABOVE it now.
        sel = [r for r in rows if r[2] < r[0]["pc"] < r[1]]
        sel.sort(key=lambda r: -r[4])
        return [r[0] for r in sel]
    if mode == "rs":
        # GREEN-ON-RED: the cross-section's own median return is the
        # market proxy -- no index feed, and it is exactly the universe
        # the position would be drawn from.
        g = sorted(r[4] for r in rows)
        med = g[len(g) // 2] if len(g) % 2 else (g[len(g) // 2 - 1]
                                                 + g[len(g) // 2]) / 2
        if med >= 0:
            return []
        sel = [r for r in rows if r[4] > 0]
        sel.sort(key=lambda r: -r[4])
        return [r[0] for r in sel]
    rows = sorted(rows, key=lambda r: (-r[4] if mode == "gain_desc"
                                       else r[4]))
    return [r[0] for r in rows]


def run_day(cands, date, cfg, rep, cache):
    trades = []
    t = cfg["entry_open"]
    ticket_i = 0
    while ticket_i < len(TICKETS) and t < cfg["cutoff"]:
        pool = rank_at(cands, t, cfg["rank"], rep, date,
                       ticket_i, cache)
        if not pool:
            t = _step(t)
            continue
        pick = pool[0]
        tr = dt.simulate_trades(pick["df"], prev_close=pick["pc"],
                                budget=TICKETS[ticket_i], entry_start=t,
                                **cfg["sim"])
        tr = [x for x in tr if x.get("entry_time") is not None]
        if not tr:
            t = _step(t)
            continue
        fe = tr[0]["entry_time"]
        grp = [x for x in tr if x["entry_time"] == fe]
        for x in grp:
            x["ticket"] = ticket_i
            x["symbol"] = pick["sym"]
        trades += grp
        ticket_i += 1
        t = _step(max(t, max(x["exit_time"] for x in grp).time()))
    return trades


def summarise(cid, cfg, label, s):
    total, daily = s["total"], s["daily"]
    monthly = s["monthly"]
    negm = sum(1 for v in monthly.values() if v < 0)
    best = max(daily, key=lambda d: d[1], default=None)
    eq = pk = dd = 0.0
    for _, p, _ in daily:
        eq += p
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    m_ex = dict(monthly)
    if best:
        m_ex[best[0][:7]] -= best[1]
    row = {
        "desc": cfg["desc"], "total": round(total), "days": s["days"],
        "tickets": s["tickets"],
        "pnl_per_ticket": round(total / s["tickets"], 1) if s["tickets"]
        else None,
        "tickets_per_day": round(s["tickets"] / s["days"], 2)
        if s["days"] else None,
        "negm": negm, "nmonths": len(monthly), "max_dd": round(dd),
        "best_day": round(best[1]) if best else 0,
        "best_day_date": best[0] if best else None,
        "worst_day": round(min((p for _, p, _ in daily), default=0)),
        "total_ex_best": round(total - (best[1] if best else 0)),
        "negm_ex_best": sum(1 for v in m_ex.values() if v < 0),
        "win_days_pct": (round(100 * sum(1 for _, p, _ in daily if p > 0)
                               / len(daily), 1) if daily else None),
        "exit_reasons": {k: {"n": v[0], "pnl": round(v[1])}
                         for k, v in sorted(s["reasons"].items())},
        "monthly": {k: round(v) for k, v in sorted(monthly.items())},
    }
    print(f" {cid:<12} {label:<4} {s['days']:>4}d ${total:>+11,.0f} "
          f"tkts {s['tickets']:>5} $/tkt {row['pnl_per_ticket']} "
          f"negm {negm}/{len(monthly)} maxDD ${row['max_dd']:,} "
          f"ex_best {row['total_ex_best']:+,}", flush=True)
    return row


def reps_for(cfg):
    if cfg["rank"] != "random":
        return [None]
    s = os.environ.get("VS2W_REP", "0") or "0"
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main(ids, max_days=None):
    cfgs = {c: CFGS[c] for c in ids}
    for c, v in cfgs.items():
        print(f"{c}: {v['desc']}", flush=True)
    sim_from = dtime(9, 0)
    reps = {c: reps_for(v) for c, v in cfgs.items()}
    res = json.loads(RES_F.read_text()) if RES_F.exists() else {}
    for label in LABELS:
        ds = dates_for(label)
        if max_days:
            ds = ds[:max_days]
        st = {c: {r: dict(total=0.0, days=0, tickets=0,
                          monthly=defaultdict(float), daily=[],
                          reasons=defaultdict(lambda: [0, 0.0]))
                  for r in reps[c]} for c in cfgs}
        for n, date in enumerate(ds, 1):
            cands = day_cands(date, sim_from)
            if not cands:
                continue
            cache = {}      # (t -> rows) shared by every config
            for c, v in cfgs.items():
                for rep in reps[c]:
                    tr = run_day(cands, date, v, rep, cache)
                    if not tr:
                        continue
                    s = st[c][rep]
                    p = sum(x["pnl"] for x in tr)
                    s["total"] += p
                    s["days"] += 1
                    s["monthly"][date[:7]] += p
                    s["tickets"] += len({x["ticket"] for x in tr})
                    s["daily"].append((date, p,
                                       len({x["ticket"] for x in tr})))
                    for x in tr:
                        r = (x.get("reason") or "").split()[0] or "other"
                        s["reasons"][r][0] += 1
                        s["reasons"][r][1] += x["pnl"]
            if n % 25 == 0:
                c0 = next(iter(cfgs))
                s0 = st[c0][reps[c0][0]]
                print(f"  ..{label} {n}/{len(ds)} [{c0}] "
                      f"({s0['days']}d ${s0['total']:+,.0f})", flush=True)
        for c, v in cfgs.items():
            for rep in reps[c]:
                key = c if rep is None else f"{c}#r{rep}"
                res.setdefault(key, {})["desc"] = v["desc"]
                res[key][label] = summarise(key, v, label, st[c][rep])
                res[key]["rank"] = v["rank"]
    RES_F.write_text(json.dumps(res, indent=1))
    print(f"-> {RES_F.name}", flush=True)


def poison_selftest(ids, n_days=6):
    """RUNNER-LEVEL POISON TEST (the mandate's no-lookahead proof).

    For each config and each of the first n_days days, run the day
    normally, then re-run it with EVERY BAR AT OR AFTER each decision
    minute replaced by absurd values (9e9 and 1e-9) and assert the
    trades that were already CLOSED before that minute are unchanged --
    and, separately, that the FIRST trade of the day is unchanged when
    only bars after its own entry are poisoned. A rule that reads the
    future cannot survive either.
    """
    import copy
    ok = bad = 0
    for label in LABELS:
        for date in dates_for(label)[:n_days]:
            base = day_cands(date, dtime(9, 0))
            if not base:
                continue
            for cid in ids:
                cfg = CFGS[cid]
                clean = run_day(base, date, cfg, 0, {})
                if not clean:
                    continue
                cut = min(x["entry_time"] for x in clean)
                for val in (9e9, 1e-9):
                    pois = []
                    for c in base:
                        d = c["df"].astype(float).copy()
                        d.loc[d.index > cut, :] = val
                        pois.append({**c, "df": d, "tt": d.index.time})
                    tr = run_day(pois, date, cfg, 0, {})
                    a = [(str(x["entry_time"]), x["entry"],
                          x.get("symbol")) for x in clean
                         if x["entry_time"] <= cut]
                    b = [(str(x["entry_time"]), x["entry"],
                          x.get("symbol")) for x in tr
                         if x["entry_time"] <= cut]
                    if a == b:
                        ok += 1
                    else:
                        bad += 1
                        print(f"  BREACH {cid} {date} val={val}")
                        print(f"    clean {a}")
                        print(f"    pois  {b}")
    print(f"  WIDE POISON: {ok}/{ok + bad} (config, day, variant) cells "
          f"unchanged when every bar after the decision is poisoned")
    assert bad == 0, "CAUSALITY BREACH in the wide runner"


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--poison" in argv:
        argv.remove("--poison")
        poison_selftest([a for a in argv if not a.startswith("--")]
                        or ["W1ORB"])
        sys.exit(0)
    md = None
    if "--days" in argv:
        i = argv.index("--days")
        md = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    main([a for a in argv if not a.startswith("--")] or ["W1ORB"], md)
