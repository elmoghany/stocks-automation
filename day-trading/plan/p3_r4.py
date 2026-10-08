"""PAPER-3BOOK book R4: CHAMPION-REPLAY "coil + no stop", live.

Paper only, open-ended. Real orders never, unless the user explicitly
authorizes them in conversation.

THE RULE (champion-replay-audit.md Part 4, row R4; engine plan/cp_sim.py
with default_cfg(rank="coil", stop_pct=None) -- imported, not copied):
  universe   names whose last RTH close since 09:30 printed >= 1.10 x prev
             close (sticky -- Robinhood's own +10% scanner rule), last >= $2
  decisions  every 5 minutes on the grid 09:35, 09:40, ... < 14:30; a grid
             minute t is decided once bar t is complete (wall t+1)
  rank       coil = last / session high (04:00 onward), highest first;
             LIVE ties: volume so far, then a seeded hash (LEGACY-2; the
             published backtest broke ties by pool-file order, a leak)
  gate       07:00 gap (last print <= 07:00 / prev close - 1) <= 35% for the
             top-ranked name, <= 20% for every other; try the first 8
  entry      the OPEN of the next printed bar after t (RS_DEFER); price >= $2;
             shares = min(ticket / px, 20% of the 5 bars before the fill bar)
  exits      NO hard stop; trail from peak HIGH: 20% base, 10% when 10-bar
             pressure <= -0.30, 40% when >= +0.30 (fills at min(level, open)
             clamped to the bar); bearish ENGULFING bar while close > entry
             (published backtest: fills at that bar's close; LIVE: at the
             NEXT printed bar's open -- LEGACY-14); flatten at the last printed bar
             <= 15:00 (its close)
  structure  one position at a time; <= 7 tickets/day; <= $100k/day; after
             an exit the next decision is the first grid minute >= max(t+5,
             exit+1); rotation on (any name may be re-picked)
  tickets    LIVE $10,000 each (user); backtest $15,000 x 6 + $10,000

LIVE DATA (the session agent fetches; this file only reads files)
  * every grid minute t (wall t+1, 09:36..14:26), run the saved Robinhood
    scan SCAN_ID ("P3 R4 gapper coil": Last > $2 AND RTH high >= 1.10 x
    prev close, sorted by Coil desc, <= 200 rows) and ingest it:
        python plan/p3_r4.py --scan FILE --at HH:MM
    -> data/paper/r4/snaps_{D}.jsonl. Coil and the sticky LAST-rule
    universe come from these snapshots.
  * bars (data/rh_bars) for the names the decision asks for (need_bars:
    the top-8 candidates, for the 07:00 gap gate, the fill bar and the
    sizing cap) and for the held name every minute.
  * decision:  python plan/p3_r4.py --date D --now HH:MM

TWO TRACKS (R4-FIX, user-approved 2026-10-08, paper only)
  * PARITY/MODEL track = run_live (the rule above, unchanged): replayed
    every --now for scoring only (the "model" block of the output, its
    closed_legs, track_bars / model_need_bars); it never blocks the live
    book. p3_eod scores it as the R4 PARITY row; model legs the live book
    did not take are SHADOW legs.
  * LIVE track = live_screen / live_step (the top-level action): at each
    grid while the live book is flat, the first of the ranked top 8 that
    passes GAP7, PRICE, PINNED (15 printed bars range < PIN_THR), VOLCAP
    and then the agent's --check-book (HALT / SPREAD / DEPTH). A VETO skips
    that name at that grid; re-run --now for the next candidate. Refusals:
    data/paper/r4/refusals_{D}.json. Tests/backtest: plan/p3_r4_live.py.

The same engine (`run_live`) is driven by plan/p3_parity_r4.py with the
historical minute caches as the feed; `watch_exit` is what
plan/paper_watch.py EXIT_MODE r4 calls, so live exits, replay exits and the
parity test are one function.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_lib as CL                                         # noqa: E402
import cp_sim as S                                          # noqa: E402
import p3_lib as P                                          # noqa: E402

BOOK = "r4"
SCAN_ID = "0cc1cab3-408b-40bf-8a76-c6129ed0fed4"
CFG = S.default_cfg(rank="coil", stop_pct=None)       # the published R4
# LEGACY-14 (2026-10-01): cp_sim sells the bearish-engulfing exit at the
# CLOSE of the very bar that completes the pattern -- a price that is gone
# by the time the pattern is known. LIVE sells at the next printed bar's
# OPEN (the earliest real fill). The published-close variant (CFG) is kept
# only so the parity test can compare against the published dump.
# LEGACY-2 (2026-10-01): cp_sim ranks with a STABLE sort on -coil, and at a
# typical decision ~5 names tie at coil = 1.0, so ties fall back to the
# gapper-pool FILE order -- which correlates with FULL-DAY volume (Spearman
# -0.40..-0.53): a look-ahead. LIVE breaks ties causally: share volume so far
# (04:00..t, the scan's Volume column live), then a seeded hash of
# (date, t, symbol). Never pool, file or scanner order.
CFG_LIVE = dict(CFG, bearish_fill="next_open", tiebreak="causal")
GRID = np.arange(CL.M_OPEN, CL.M_1500 + 1, 5)               # 330..660
TICKETS_LIVE = [P.TICKET] * 7
TICKETS_BT = list(S.TICKETS)
DAY_CAP = 100_000.0
CM = CL.NMIN                                                # 720-min grid


# --------------------------------------------------------------- the day
def make_day(syms, pcs, feed):
    """cp_lib.Day from a feed (bars <= feed.now-1 only)."""
    n = len(syms)
    arr = {k: np.full((n, CM), np.nan) for k in "ohlc"}
    arr["v"] = np.zeros((n, CM))
    for i, s in enumerate(syms):
        b = feed.bars(s)
        if b is None:
            continue
        for k, a in zip("ohlcv", b):
            arr[k][i] = a[:CM]
    return CL.Day(dict(syms=np.array(syms), pc=np.asarray(pcs, float), **arr))


def fd_from_bars(day):
    """The cp_feat keys R4 reads, computed from bars exactly as
    plan/cp_feat.build_date does (coil stored float32 there, so here)."""
    G = GRID
    last = day.last[:, G]
    hi = day.runhigh[:, G]
    with np.errstate(divide="ignore", invalid="ignore"):
        coil = np.where(hi > 0, last / hi, np.nan).astype(np.float32)
        gap7 = day.last[:, CL.mgrid(7, 0)] / day.pc - 1.0
    thr = CL.CROSS * day.pc
    c = np.where(day.printed, day.c, -np.inf).copy()
    c[:, :CL.M_OPEN] = -np.inf
    hit = np.maximum.accumulate(c, axis=1)[:, G]
    lastG = day.last[:, G]
    elig = ((hit >= thr[:, None]) & np.isfinite(lastG)
            & (lastG >= CL.MIN_PRICE) & (day.pc > 0)[:, None])
    return dict(syms=np.array(day.syms), grid=G.astype(np.int32), coil=coil,
                gap7=gap7, elig_last=elig, elig_high=elig,
                vol=day.cumv[:, G].astype(float))


def fd_from_snaps(day, snaps):
    """LIVE: coil and the sticky LAST-rule universe from scan snapshots;
    gap7 from bars where the agent fetched them (NaN = unknown)."""
    n = day.n
    sidx = {s: i for i, s in enumerate(day.syms)}
    coil = np.full((n, len(GRID)), np.nan, np.float32)
    vol = np.full((n, len(GRID)), np.nan)
    elig = np.zeros((n, len(GRID)), bool)
    seen = np.zeros(n, bool)
    by_t = {int(x["t"]): x["rows"] for x in snaps}
    for gi, m in enumerate(GRID):
        rows = by_t.get(int(m))
        if rows is None:
            elig[:, gi] = seen & False
            continue
        cur = np.zeros(n, bool)
        for s, r in rows.items():
            i = sidx.get(s)
            if i is None:
                continue
            pc, px = r.get("pc"), r.get("last")
            if pc and px and px >= CL.CROSS * pc:
                seen[i] = True
            if px and px >= CL.MIN_PRICE:
                cur[i] = True
            if r.get("coil") is not None:
                coil[i, gi] = r["coil"]
            if r.get("vol") is not None:
                vol[i, gi] = r["vol"]
        elig[:, gi] = seen & cur
    with np.errstate(divide="ignore", invalid="ignore"):
        gap7 = day.last[:, CL.mgrid(7, 0)] / day.pc - 1.0
    has_bars = day.printed.any(axis=1)
    return dict(syms=np.array(day.syms), grid=GRID.astype(np.int32),
                coil=coil, gap7=gap7, elig_last=elig, elig_high=elig,
                has_bars=has_bars, vol=vol)


def causal_score(Fd, date):
    """Ranking score for cp_sim's rank="model": the coil key exactly as
    cp_sim.rank_key builds it (float32, NaN -> 0), ties broken by share
    volume so far (desc), then crc32(date|t|sym). score = -position, so a
    stable argsort on -score reproduces the order."""
    import zlib
    syms = [str(x) for x in Fd["syms"]]
    n, ng = len(syms), len(Fd["grid"])
    out = np.zeros((n, ng))
    for gi, m in enumerate(Fd["grid"]):
        key = -np.nan_to_num(Fd["coil"][:, gi], nan=0.0)
        vol = np.nan_to_num(np.asarray(Fd["vol"][:, gi], float), nan=-1.0)
        h = np.array([zlib.crc32(f"{date}|{int(m)}|{s}".encode())
                      for s in syms], float)
        order = np.lexsort((h, -vol, key))
        out[order, gi] = -np.arange(n, dtype=float)
    return out


def cfg_for(cfg, Fd, date):
    """Resolve the tie-break: 'causal' -> cp_sim rank='model' on the causal
    score; anything else -> cp_sim's own stable sort (the published key)."""
    if cfg.get("tiebreak") == "causal":
        return dict(cfg, rank="model", score=causal_score(Fd, date))
    return cfg


# --------------------------------------------------------------- engine
def next_print(day, i, m0, now, limit=60):
    """(minute, None) when found; (None, 'PENDING') when it may still
    print; (None, None) when the 60-minute window passed without one."""
    top = min(m0 + limit, CM)
    for m in range(m0, min(top, now)):
        if day.printed[i, m]:
            return m, None
    return (None, "PENDING") if now < top else (None, None)


def walk_exit(day, i, em, entry, now, cfg=CFG_LIVE):
    """cp_sim._walk_exit, bounded by the live clock: scans bars em+1 ..
    min(exit_end, now-1). Returns (exit_min, px, reason, decided_min);
    (None, None, 'OPEN', None) while holding; (None, None, 'EXITING', m)
    when a bearish exit was decided at m and its next-open fill bar has not
    completed yet. Same arithmetic, same order of tests, same helpers."""
    peak = entry
    end = cfg["exit_end"]
    for m in range(em + 1, min(end, now - 1) + 1):
        if not day.printed[i, m]:
            continue
        lo, hi, c = (float(day.l[i, m]), float(day.h[i, m]),
                     float(day.c[i, m]))
        peak = max(peak, hi)
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
                return (m, S._sell_fill(day, i, m, lvl), f"trail {tw:.2f}",
                        m)
        if cfg["bearish_exit"] and c > entry and S._bearish(day, i, m):
            if cfg.get("bearish_fill") != "next_open":
                return m, c, "bearish", m
            for m2 in range(m + 1, min(CM, now)):
                if day.printed[i, m2]:
                    return m2, float(day.o[i, m2]), "bearish", m
            if now >= CM:                      # never printed again
                return m, c, "bearish", m
            return None, None, "EXITING", m
    if now - 1 < end:
        return None, None, "OPEN", None
    m = end
    while m > em and not day.printed[i, m]:
        m -= 1
    if m <= em:
        return None, None, "NOFLAT", None
    return m, float(day.c[i, m]), "flatten", m


def try_ticket(day, Fd, i, t, budget, now, cfg=CFG_LIVE):
    em, why = next_print(day, i, t + 1, now)
    if em is None:
        return why                                   # PENDING or None
    px = float(day.o[i, em])
    if not np.isfinite(px) or px < cfg["min_px"]:
        return None
    v5 = float(day.cumv[i, em - 1] - day.cumv[i, max(em - 6, 0)])
    sh = int(min(budget / px, S.VOL_CAP * v5))
    if sh < 1:
        return None
    ex_m, ex_px, reason, _dm = walk_exit(day, i, em, px, now, cfg)
    if reason == "NOFLAT":
        return None
    return dict(i=i, sym=day.syms[i], t=int(t), entry_min=int(em), entry=px,
                shares=sh, exit_min=None if ex_m is None else int(ex_m),
                exit=ex_px, reason=reason, open=ex_m is None,
                gross=None if ex_m is None else (ex_px - px) * sh)


def run_live(day, Fd, now, tickets=TICKETS_LIVE, cfg=CFG_LIVE,
             live=False, date=""):
    """cp_sim.run_day, made clock-aware. Returns (legs, state)."""
    cfg = cfg_for(cfg, Fd, date)
    gidx = {int(m): k for k, m in enumerate(Fd["grid"])}
    elig = Fd["elig_last"]
    gate_top, gate_oth = S.gates(Fd, cfg)
    legs, t, ti, deployed = [], cfg["t_start"], 0, 0.0
    while ti < cfg["ntickets"] and t < cfg["cutoff"]:
        if t not in gidx:
            t += 1
            continue
        if t > now - 1:
            return legs, dict(state="FLAT", next_t=int(t), tickets_used=ti)
        gi = gidx[t]
        cand = np.where(elig[:, gi])[0]
        if len(cand) == 0:
            t += cfg["step"]
            continue
        key = S.rank_key(Fd, gi, cfg)[cand]
        order = cand[np.argsort(key, kind="stable")]
        ranked_top = int(order[0])
        budget = tickets[ti]
        if deployed + budget > DAY_CAP:
            break
        leg = None
        for i in order[:8]:
            i = int(i)
            if live and not Fd["has_bars"][i]:
                need = [day.syms[int(j)] for j in order[:8]
                        if not Fd["has_bars"][int(j)]]
                return legs, dict(state="NEED_DATA", t=int(t), need_bars=need,
                                  tickets_used=ti,
                                  ranked=[day.syms[int(j)] for j in order[:8]])
            if not (gate_top[i] if i == ranked_top else gate_oth[i]):
                continue
            r = try_ticket(day, Fd, i, t, budget, now, cfg)
            if r == "PENDING":
                return legs, dict(state="ARMED", t=int(t), sym=day.syms[i],
                                  tickets_used=ti, budget=budget,
                                  ranked=[day.syms[int(j)] for j in order[:8]])
            if r is None:
                continue
            leg = r
            break
        if leg is None:
            t += cfg["step"]
            continue
        leg["ticket"] = ti
        legs.append(leg)
        if leg["open"]:
            return legs, dict(state="HOLDING", t=int(t), sym=leg["sym"],
                              tickets_used=ti + 1)
        deployed += leg["shares"] * leg["entry"]
        ti += 1
        t = max(t + cfg["step"], leg["exit_min"] + 1)
    return legs, dict(state="DONE", tickets_used=ti)


# --------------------------------------------------------------- LIVE track
# R4-FIX (2026-10-08, user-approved, paper only). run_live above is the
# PARITY/MODEL track: the unchanged backtest, tracked from bars for scoring
# only -- it never blocks the live book. The LIVE track below moves on: at
# each grid t (09:35..14:25) while the live book is flat it walks the same
# ranked top 8 (same rank key, same causal tie-break, same 07:00 gap gate)
# and takes the FIRST name that passes every entry check right now:
#   bar checks (here):  eligibility, GAP7 gate, PRICE >= $2, PINNED
#                       (range of the last 15 printed bars <= t, over the
#                       last close, < PIN_THR -- a buyout target sits at the
#                       deal price), VOLCAP (20%-of-5-bar size cap < 1 sh)
#   book checks (agent quote + price book, check_book): HALT (locked /
#                       crossed quote or halted), SPREAD > 0.5%, DEPTH < 25%
#   staleness:          a grid is acted on only until wall t+1+STALE_MIN
# A name refused at t may be reconsidered at later grids. Exits are the R4
# exits (the watcher's watch_exit, decision_min = t). One live position,
# $10k, <= 7 tickets, <= $100k/day, entries until 14:30, flatten 15:00.
LIVE_TOPN = 8
PIN_BARS = 15
PIN_THR = 0.006              # set by plan/p3_r4_live.py --pinned (see notes)


def pinned_range(day, i, t, nb=PIN_BARS):
    """(max high - min low) / last close over the last `nb` PRINTED bars at
    or before t; None when fewer than `nb` bars printed since 04:00 (a thin
    name is not a pinned one)."""
    idx = np.flatnonzero(day.printed[i, :t + 1])
    if idx.size < nb:
        return None
    idx = idx[-nb:]
    c = float(day.c[i, idx[-1]])
    if not c > 0:
        return None
    return float((np.nanmax(day.h[i, idx]) - np.nanmin(day.l[i, idx])) / c)


def live_screen(day, Fd, gi, cfgr, refused=None, fresh=None, pin_thr=None):
    """The ranked top 8 at grid index gi with every BAR-based verdict.
    cfgr = cfg_for(...) resolved. refused: {(sym, t): reason} from the book
    checks. fresh(sym, t): True when the agent's bars for sym include bar t
    (None = always). Verdicts: OK | NEED_BARS | GAP7 | PRICE | PINNED |
    VOLCAP | <book reason already logged at t>."""
    pin_thr = PIN_THR if pin_thr is None else pin_thr
    t = int(Fd["grid"][gi])
    cand = np.where(Fd["elig_last"][:, gi])[0]
    if len(cand) == 0:
        return []
    key = S.rank_key(Fd, gi, cfgr)[cand]
    order = [int(i) for i in cand[np.argsort(key, kind="stable")]][:LIVE_TOPN]
    gate_top, gate_oth = S.gates(Fd, cfgr)
    hb = Fd.get("has_bars")
    out = []
    for r, i in enumerate(order):
        sym = str(day.syms[i])
        d = dict(i=i, sym=sym, rank=r + 1, verdict="OK", detail="")
        if refused and (sym, t) in refused:
            d.update(verdict=refused[(sym, t)], detail="refused at this grid")
            out.append(d)
            continue
        if (hb is not None and not hb[i]) or (fresh and not fresh(sym, t)):
            d["verdict"] = "NEED_BARS"
            out.append(d)
            continue
        g7 = float(Fd["gap7"][i])
        if not (gate_top[i] if r == 0 else gate_oth[i]):
            d.update(verdict="GAP7", detail=f"07:00 gap {g7 * 100:.1f}% > "
                     f"{(cfgr['gap7_max'] if r == 0 else cfgr['gap7_max_other']) * 100:.0f}%")
            out.append(d)
            continue
        last = P.ffill_last(day.c[i], t)
        pr = pinned_range(day, i, t)
        v5 = float(day.cumv[i, t] - day.cumv[i, max(t - 5, 0)])
        cap = int(S.VOL_CAP * v5)
        d.update(last=last, range15=None if pr is None else round(pr, 5),
                 shares_cap=cap)
        if not (np.isfinite(last) and last >= cfgr["min_px"]):
            d.update(verdict="PRICE", detail=f"last {last} < $2")
        elif pr is not None and pr < pin_thr:
            d.update(verdict="PINNED", detail=f"15-bar range {pr * 100:.2f}%"
                     f" < {pin_thr * 100:.1f}%")
        elif cap < 1:
            d.update(verdict="VOLCAP", detail="20% of the 5-bar volume < 1 sh")
        out.append(d)
    return out


def live_step(day, Fd, now, hist, refused, date, cfg=CFG_LIVE, fresh=None,
              pin_thr=None):
    """The LIVE-track decision at wall minute `now`. hist: today's live
    legs [{sym, t, open, exit_min, notional}] (open legs from the watcher's
    position files, closed ones from its flatten file); refused: {(sym, t):
    reason} book-check refusals. Returns a dict with state HOLDING | DONE |
    WAIT | NEED_DATA | PICK | NONE (rows = the screened top 8)."""
    held = [h for h in hist if h.get("open")]
    if held:
        return dict(state="HOLDING", sym=held[0]["sym"], t=held[0].get("t"))
    used = len(hist)
    if used >= cfg["ntickets"]:
        return dict(state="DONE", reason="7 live tickets used")
    if sum(h.get("notional") or P.TICKET for h in hist) + P.TICKET > DAY_CAP:
        return dict(state="DONE", reason="$100k/day cap")
    t0 = int(cfg["t_start"])
    for h in hist:
        if h.get("exit_min") is not None:
            t0 = max(t0, int(h["exit_min"]) + 1)
        if h.get("t") is not None:
            t0 = max(t0, int(h["t"]) + cfg["step"])
    grids = [int(g) for g in GRID if t0 <= g < cfg["cutoff"]]
    if not grids:
        return dict(state="DONE", reason="entry window closed (14:30)")
    cur = [g for g in grids if g <= now - 1]
    if not cur:
        return dict(state="WAIT", next_t=grids[0])
    t = cur[-1]
    nxt = next((g for g in grids if g > t), None)
    if now - (t + 1) > STALE_MIN:
        return dict(state="WAIT", next_t=nxt, stale_t=t, reason=(
            f"grid {P.hhmm(t)} is stale at {P.hhmm(now)} (> {STALE_MIN} min)"))
    gi = {int(m): k for k, m in enumerate(Fd["grid"])}[t]
    cfgr = cfg_for(cfg, Fd, date)
    rows = live_screen(day, Fd, gi, cfgr, refused, fresh, pin_thr)
    need = [r["sym"] for r in rows if r["verdict"] == "NEED_BARS"]
    ok = [r for r in rows if r["verdict"] == "OK"]
    # bars are needed only when a name ranked ABOVE the first passing one
    # cannot be judged yet (then fetch every missing top-8 name, one call)
    if need and (not ok or any(r["verdict"] == "NEED_BARS"
                               for r in rows[:rows.index(ok[0])])):
        return dict(state="NEED_DATA", t=t, need_bars=need, rows=rows)
    if ok:
        return dict(state="PICK", t=t, sym=ok[0]["sym"], i=ok[0]["i"],
                    shares_cap=ok[0]["shares_cap"], rows=rows,
                    candidates=[r["sym"] for r in ok], next_t=nxt)
    return dict(state="NONE", t=t, rows=rows, next_t=nxt)


# --------------------------------------------------------------- watcher
def watch_exit(date, st, bars, now):
    """EXIT_MODE r4 for plan/paper_watch.py. st: sym, decision_min,
    model_entry (optional), bars = p3_lib bar tuple (completed <= now-1).
    Model entry = open of the first printed bar after decision_min."""
    if bars is None:
        return None
    o, h, l, c, v = (a[:CM] for a in bars)
    day = CL.Day(dict(syms=np.array([st["sym"]]), pc=np.array([1.0]),
                      o=o[None], h=h[None], l=l[None], c=c[None], v=v[None]))
    t = int(st["decision_min"])
    em, _ = next_print(day, 0, t + 1, now)
    if em is None:
        return None
    entry = float(day.o[0, em])
    st["model_entry"], st["model_entry_min"] = entry, int(em)
    m, px, reason, dm = walk_exit(day, 0, em, entry, now)
    if reason == "EXITING":
        return dict(decided_min=int(dm), min=None, px=None, reason="bearish")
    if m is None:
        return None
    return dict(decided_min=int(dm), min=int(m), px=float(px), reason=reason)


# --------------------------------------------------------------- live io
def snaps_path(date):
    return P.book_dir(BOOK) / f"snaps_{date}.jsonl"


def ingest_scan(path, date, at):
    rows = {}
    for r in P.scan_rows(P.load_tool_json(path)):
        cc = r["cols"]
        last = P.fnum(cc.get("PriceReg") or cc.get("Last"))
        pc = P.fnum(cc.get("PrevClose"))
        hi = P.fnum(cc.get("HighAll") or cc.get("High"))
        coil = P.fnum(cc.get("Coil"))
        if not np.isfinite(coil) and np.isfinite(hi) and hi > 0:
            coil = last / hi
        if not r["sym"] or not np.isfinite(pc) or pc <= 0:
            continue
        vol = P.fnum(cc.get("Volume"))
        rows[r["sym"]] = dict(last=last, pc=pc, high=hi,
                              coil=None if not np.isfinite(coil) else coil,
                              vol=None if not np.isfinite(vol) else vol)
    f = snaps_path(date)
    keep = [json.loads(x) for x in f.read_text().splitlines()] \
        if f.exists() else []
    keep = [x for x in keep if int(x["t"]) != at]
    keep.append(dict(t=at, n=len(rows), rows=rows))
    keep.sort(key=lambda x: x["t"])
    f.write_text("\n".join(json.dumps(x) for x in keep) + "\n")
    top = sorted(rows.items(), key=lambda kv: (-(kv[1]["coil"] or 0),
                                             -(kv[1]["vol"] or 0)))[:8]
    need = [s for s, _ in top
            if not (P.RH_BARS / f"{s}_{date}.csv").exists()]
    P.emit(dict(book=BOOK, ingested=len(rows), at=P.hhmm(at),
                top8=[s for s, _ in top], need_bars=need))


def load_live(date, now):
    """(day, Fd) from today's scan snapshots + the agent's bars, or None."""
    snaps = []
    f = snaps_path(date)
    if f.exists():
        snaps = [json.loads(x) for x in f.read_text().splitlines() if x]
    syms, pcs = [], []
    for x in snaps:
        for s, r in x["rows"].items():
            if s not in syms:
                syms.append(s)
                pcs.append(r["pc"])
    if not syms:
        return None
    feed = P.LiveFeed(date, now)
    day = make_day(syms, pcs, feed)
    return day, fd_from_snaps(day, snaps)


def live_decision(date, now):
    """PARITY/MODEL track at wall `now` (also what p3_eod replays)."""
    ld = load_live(date, now)
    if ld is None:
        return [], dict(state="FLAT", next_t=int(CFG["t_start"]),
                        reason="no scan snapshot yet")
    day, Fd = ld
    return run_live(day, Fd, now, live=True, date=date)


# --------------------------------------------------------------- veto
STALE_MIN = 5                # an ENTER first seen > 5 min after t+1 is stale
SPREAD_CAP = 0.005           # inside spread > 0.5% of mid -> refuse
DEPTH_MIN = 0.25             # displayed ask depth to ask x 1.005 < 25% of
                             # the intended shares -> refuse (LEGACY-15)


def vetoes_path(date):
    return P.book_dir(BOOK) / f"vetoes_{date}.json"


def refusals_path(date):
    """LIVE-track refusal log: every refused candidate with its reason."""
    return P.book_dir(BOOK) / f"refusals_{date}.json"


def log_refusals(date, now, t, rows):
    """Append bar-based refusals (and book ones passed as rows), one entry
    per (sym, grid, reason)."""
    log = P.read_json(refusals_path(date), []) or []
    seen = {(x["sym"], x["grid"], x["reason"]) for x in log}
    add = 0
    for r in rows:
        if r["verdict"] in ("OK", "NEED_BARS"):
            continue
        k = (r["sym"], P.hhmm(t), r["verdict"])
        if k in seen:
            continue
        seen.add(k)
        log.append(dict(sym=r["sym"], grid=P.hhmm(t), reason=r["verdict"],
                        rank=r.get("rank"), detail=r.get("detail", ""),
                        at=P.hhmm(now)))
        add += 1
    if add:
        P.write_atomic(refusals_path(date), log)


def check_book(date, now, sym, decision, bid, ask, depth, halted=False):
    """LEGACY-15 book veto for an R4 LIVE-track entry (plus the halt check).
    Every check is logged in vetoes_{D}.json; a refusal also goes to the
    live-track refusal log, and the next `--now` run skips this name at this
    grid (it may come back at a later grid). p3_eod uses the first refusal
    ask of a model leg as that SHADOW leg's entry."""
    bid = bid or 0.0
    ask = ask or 0.0
    mid = (bid + ask) / 2.0
    locked = bid > 0 and ask > 0 and bid >= ask
    spread = (ask - bid) / mid if (mid > 0 and not locked) else float("inf")
    want = int(P.TICKET // ask) if ask > 0 else 0
    depth_ok = depth is None or (want > 0 and depth >= DEPTH_MIN * want)
    why, reason = [], None
    if halted or locked or bid <= 0 or ask <= 0:
        reason = "HALT"
        why.append("HALT: " + ("halted (agent)" if halted else
                               "locked/crossed or missing quote "
                               f"{bid}/{ask}"))
    elif spread > SPREAD_CAP:
        reason = "SPREAD"
        why.append(f"SPREAD {spread * 100:.2f}% > 0.50%")
    if reason != "HALT" and not depth_ok:
        reason = reason or "DEPTH"
        why.append(f"DEPTH {depth} sh < 25% of {want}")
    ok = reason is None
    log = P.read_json(vetoes_path(date), []) or []
    key = f"{sym}@{decision}"
    log.append(dict(key=key, sym=sym, decision=decision, at=P.hhmm(now),
                    bid=bid, ask=ask, mid=round(mid, 4),
                    spread_pct=None if not np.isfinite(spread)
                    else round(spread * 100, 3), depth=depth,
                    want=want, result="PASS" if ok else "VETO",
                    reason=reason, track="live", why="; ".join(why)))
    P.write_atomic(vetoes_path(date), log)
    if not ok:
        t = P.parse_hhmm(decision) if decision else ((now - 1) // 5) * 5
        log_refusals(date, now, t, [dict(sym=sym, verdict=reason, rank=None,
                                         detail="; ".join(why))])
    P.emit(dict(book=BOOK, check=key, result="PASS" if ok else "VETO",
                reason=reason,
                spread_pct=None if not np.isfinite(spread)
                else round(spread * 100, 3), depth=depth, want=want,
                shares=want, why="; ".join(why) or "book passes",
                next="ENTER now at the ask (live track)" if ok else
                "do NOT enter; re-run --now NOW for the next candidate at "
                "this grid"))


def read_refused(date):
    """{(sym, grid_min): reason} for every book-check refusal today (and
    every NOBARS mark: the agent's bars call returned nothing for it)."""
    out = {}
    for x in P.read_json(refusals_path(date), []) or []:
        if x.get("reason") == "NOBARS":
            out.setdefault((x["sym"], P.parse_hhmm(x["grid"])), "NOBARS")
    for v in P.read_json(vetoes_path(date), []) or []:
        if v.get("result") == "VETO" and v.get("decision"):
            r = v.get("reason") or ("SPREAD" if "SPREAD" in (v.get("why") or "")
                                    else "DEPTH")
            out.setdefault((v["sym"], P.parse_hhmm(v["decision"])), r)
    return out


def live_hist(date):
    """Today's LIVE legs from the r4 watcher's files: open positions
    (position_*.json) and booked exits ({D}.r4.flatten.json)."""
    hist = []
    fl = P.read_json(P.DATA / "paper_days" / f"{date}.{BOOK}.flatten.json",
                     {}) or {}
    for r in fl.get("records", []):
        xt = str(r.get("exit_time") or r.get("booked_at") or "")
        xm = None
        if len(xt) >= 16:          # booked at wall w -> exit bar w-1, so
            xm = int(xt[11:13]) * 60 + int(xt[14:16]) - P.BASE - 1
            # the next live grid is the first one >= w (as the replay)
        hist.append(dict(sym=r["sym"], open=False, exit_min=xm, t=None,
                         notional=r.get("deployed")
                         or (r.get("entry") or 0) * (r.get("shares_initial")
                                                     or 0)))
    for f in sorted(P.book_dir(BOOK).glob("position_*.json")):
        st = P.read_json(f, {}) or {}
        if st.get("date") not in (None, date):
            continue
        hist.append(dict(sym=st.get("sym") or f.stem[9:], open=True,
                         t=st.get("decision_min"), exit_min=None,
                         notional=(st.get("entry") or 0) * (st.get("shares")
                                                            or 0)))
    return hist


def bars_fresh(date):
    """fresh(sym, t): the agent's bars file for sym was written at or after
    wall t+1 (so it holds bar t). Live only; replays pass fresh=None."""
    from datetime import datetime as _dt

    def f(sym, t):
        p = P.RH_BARS / f"{sym}_{date}.csv"
        if not p.exists():
            return False
        k = int(t) + 1 + P.BASE
        due = _dt.strptime(date, "%Y-%m-%d").replace(
            hour=k // 60, minute=k % 60, tzinfo=P.ET).timestamp()
        return p.stat().st_mtime >= due
    return f


def booked(date, sym, t):
    """True when the r4 watcher already booked an exit for this leg."""
    fl = P.read_json(P.DATA / "paper_days" / f"{date}.{BOOK}.flatten.json",
                     {}) or {}
    t_utc = P.utc_iso(date, t)
    for r in fl.get("records", []):
        if r.get("sym") == sym and str(r.get("entry_bar_utc") or "") >= t_utc:
            return True
    return False


def model_summary(legs, st):
    """The PARITY/MODEL track, for scoring only (never an order)."""
    m = dict(state=st["state"], tickets_used=st.get("tickets_used", 0))
    if st.get("sym"):
        m.update(sym=st["sym"], decision_min=P.hhmm(st["t"]))
    if st["state"] == "HOLDING" and legs:
        lg = legs[-1]
        m.update(model_entry=lg["entry"],
                 model_entry_min=P.hhmm(lg["entry_min"]))
    if st["state"] == "FLAT":
        m["next_t"] = P.hhmm(st["next_t"])
    if st["state"] == "NEED_DATA":
        m.update(decision_min=P.hhmm(st["t"]), ranked=st.get("ranked"))
    m["closed"] = len([x for x in legs if not x["open"]])
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--now", help="wall clock HH:MM ET (default: now)")
    ap.add_argument("--scan", help="saved run_scan result to ingest")
    ap.add_argument("--at", help="grid minute HH:MM the scan represents")
    ap.add_argument("--check-book", metavar="SYM",
                    help="LIVE-track book check (halt / spread / depth) for "
                         "an ENTER candidate")
    ap.add_argument("--decision", help="grid HH:MM of the decision")
    ap.add_argument("--bid", type=float)
    ap.add_argument("--ask", type=float)
    ap.add_argument("--depth", type=float,
                    help="displayed ask shares from the inside ask up to "
                         "ask x 1.005 (get_equity_price_book); omit if the "
                         "book call failed (then spread-only)")
    ap.add_argument("--no-bars", nargs="+", metavar="SYM",
                    help="the bars call returned no bars for these need_bars"
                         " names: skip them at --decision's grid (NOBARS)")
    ap.add_argument("--halted", action="store_true",
                    help="the agent saw a halt (LULD / crossed book / no "
                         "trade for minutes) even if the quote looks normal")
    a = ap.parse_args()
    date = a.date or P.now_et().date().isoformat()
    now = P.parse_hhmm(a.now) if a.now else P.now_min()
    if a.scan:
        at = P.parse_hhmm(a.at) if a.at else ((now - 1) // 5) * 5
        return ingest_scan(a.scan, date, at)
    if a.check_book:
        return check_book(date, now, a.check_book.upper(), a.decision,
                          a.bid, a.ask, a.depth, a.halted)
    if a.no_bars:
        t = P.parse_hhmm(a.decision) if a.decision else ((now - 1) // 5) * 5
        log_refusals(date, now, t, [dict(sym=x.upper(), verdict="NOBARS",
                                         detail="bars call returned none")
                                    for x in a.no_bars])
        return P.emit(dict(book=BOOK, no_bars=[x.upper() for x in a.no_bars],
                           grid=P.hhmm(t), next="re-run --now"))
    out = dict(book=BOOK, now=P.hhmm(now), track="live")
    ld = load_live(date, now)
    if ld is None:
        out.update(action="NOTHING", state="WAIT",
                   reason="no scan snapshot yet",
                   model=dict(state="FLAT"), closed_legs=[])
        return P.emit(out)
    day, Fd = ld
    # ---- PARITY / MODEL track (scoring only; never blocks the live book)
    legs, mst = run_live(day, Fd, now, live=True, date=date)
    out["model"] = model_summary(legs, mst)
    out["closed_legs"] = [dict(sym=lg["sym"], decision=P.hhmm(lg["t"]),
                               entry_min=P.hhmm(lg["entry_min"]),
                               entry=lg["entry"],
                               exit_min=P.hhmm(lg["exit_min"]),
                               exit=lg["exit"], reason=lg["reason"])
                          for lg in legs if not lg["open"]]
    track = []
    if mst["state"] in ("ARMED", "HOLDING"):
        track.append(mst["sym"])          # model leg bars, for the EOD score
    # ---- LIVE track
    hist = live_hist(date)
    fresh = bars_fresh(date) if not a.date or a.date == \
        P.now_et().date().isoformat() else None
    st = live_step(day, Fd, now, hist, read_refused(date), date, fresh=fresh)
    s = st["state"]
    out["state"] = s
    out["tickets_used"] = len(hist)
    if st.get("rows") is not None:
        log_refusals(date, now, st["t"], st["rows"])
        out["screen"] = [f"{r['rank']}:{r['sym']}:{r['verdict']}"
                         for r in st["rows"]]
    need = list(st.get("need_bars") or [])
    mneed = list(mst.get("need_bars") or [])         if mst["state"] == "NEED_DATA" else []
    if mneed:
        out["model_need_bars"] = mneed     # scoring only: fetch, no re-run
    if s == "HOLDING":
        out.update(action="HOLD", sym=st["sym"],
                   reason="live position open; exits owned by the r4 watcher")
        track.append(st["sym"])
    elif s == "DONE":
        out.update(action="DONE", reason=st["reason"])
    elif s == "WAIT":
        out.update(action="NOTHING", reason=st.get("reason") or (
            f"next live decision at grid {P.hhmm(st['next_t'])} (run at "
            f"wall {P.hhmm(st['next_t'] + 1)})" if st.get("next_t") is not None
            else "no grid left"))
    elif s == "NEED_DATA":
        need += [x for x in mneed if x not in need]
        out.update(action="NEED_DATA", need_bars=need,
                   decision_min=P.hhmm(st.get("t", mst.get("t", now - 1))),
                   reason="fetch minute bars 04:00->now (bounds=extended, "
                          "from 08:00Z) for need_bars, ingest, re-run --now")
    elif s == "PICK":
        t = st["t"]
        out.update(action="ENTER", sym=st["sym"], decision_min=P.hhmm(t),
                   ticket_usd=P.TICKET, shares_cap=st["shares_cap"],
                   candidates=st["candidates"], reason=(
                       f"LIVE track, grid {P.hhmm(t)}: first of the ranked "
                       "top 8 passing the bar checks. Quote it (one "
                       "get_equity_quotes for all `candidates`), then run "
                       "--check-book SYM --decision " + P.hhmm(t) + " (price "
                       "book only when the spread is <= 0.5%). PASS -> enter "
                       "at the ask, watcher --decision-min " + P.hhmm(t) +
                       ". VETO -> re-run --now at once: the next candidate."))
    else:                                              # NONE
        nt = st.get("next_t")
        out.update(action="NOTHING", decision_min=P.hhmm(st["t"]),
                   reason=f"no top-8 name passes at grid {P.hhmm(st['t'])}"
                   + (f"; next grid {P.hhmm(nt)} (wall {P.hhmm(nt + 1)})"
                      if nt is not None else "; entry window closed"))
    tb = []
    for x in track:
        if x not in tb:
            tb.append(x)
    out["track_bars"] = tb
    P.emit(out)


if __name__ == "__main__":
    main()
