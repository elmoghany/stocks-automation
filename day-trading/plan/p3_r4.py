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
    top = sorted(rows.items(), key=lambda kv: -(kv[1]["coil"] or 0))[:8]
    need = [s for s, _ in top
            if not (P.RH_BARS / f"{s}_{date}.csv").exists()]
    P.emit(dict(book=BOOK, ingested=len(rows), at=P.hhmm(at),
                top8=[s for s, _ in top], need_bars=need))


def live_decision(date, now):
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
    feed = P.LiveFeed(date, now)
    day = make_day(syms, pcs, feed) if syms else None
    if day is None:
        return [], dict(state="FLAT", next_t=int(CFG["t_start"]),
                        reason="no scan snapshot yet")
    Fd = fd_from_snaps(day, snaps)
    return run_live(day, Fd, now, live=True, date=date)


# --------------------------------------------------------------- veto
STALE_MIN = 5                # an ENTER first seen > 5 min after t+1 is stale
SPREAD_CAP = 0.005           # inside spread > 0.5% of mid -> refuse
DEPTH_MIN = 0.25             # displayed ask depth to ask x 1.005 < 25% of
                             # the intended shares -> refuse (LEGACY-15)


def vetoes_path(date):
    return P.book_dir(BOOK) / f"vetoes_{date}.json"


def check_book(date, now, sym, decision, bid, ask, depth):
    """LEGACY-15 book veto for an R4 entry. Every check is logged; the
    first VETO of a (sym, decision) opens a SHADOW leg (entry = this ask,
    exits = the model's), which p3_eod scores as the backtest-parity book."""
    mid = (bid + ask) / 2.0
    spread = (ask - bid) / mid if mid > 0 else float("inf")
    want = int(P.TICKET // ask) if ask > 0 else 0
    depth_ok = depth is None or (want > 0 and depth >= DEPTH_MIN * want)
    ok = spread <= SPREAD_CAP and depth_ok
    why = []
    if spread > SPREAD_CAP:
        why.append(f"SPREAD {spread * 100:.2f}% > 0.50%")
    if not depth_ok:
        why.append(f"DEPTH {depth} sh < 25% of {want}")
    log = P.read_json(vetoes_path(date), []) or []
    key = f"{sym}@{decision}"
    log.append(dict(key=key, sym=sym, decision=decision, at=P.hhmm(now),
                    bid=bid, ask=ask, mid=round(mid, 4),
                    spread_pct=round(spread * 100, 3), depth=depth,
                    want=want, result="PASS" if ok else "VETO",
                    why="; ".join(why)))
    P.write_atomic(vetoes_path(date), log)
    P.emit(dict(book=BOOK, check=key, result="PASS" if ok else "VETO",
                spread_pct=round(spread * 100, 3), depth=depth, want=want,
                shares=want, why="; ".join(why) or "book passes",
                next="ENTER now at the ask" if ok else
                "do NOT enter; logged as SHADOW; re-check next minute"))


def booked(date, sym, t):
    """True when the r4 watcher already booked an exit for this leg."""
    fl = P.read_json(P.DATA / "paper_days" / f"{date}.{BOOK}.flatten.json",
                     {}) or {}
    t_utc = P.utc_iso(date, t)
    for r in fl.get("records", []):
        if r.get("sym") == sym and str(r.get("entry_bar_utc") or "") >= t_utc:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--now", help="wall clock HH:MM ET (default: now)")
    ap.add_argument("--scan", help="saved run_scan result to ingest")
    ap.add_argument("--at", help="grid minute HH:MM the scan represents")
    ap.add_argument("--check-book", metavar="SYM",
                    help="LEGACY-15 spread/depth veto check for an entry")
    ap.add_argument("--decision", help="grid HH:MM of the decision")
    ap.add_argument("--bid", type=float)
    ap.add_argument("--ask", type=float)
    ap.add_argument("--depth", type=float,
                    help="displayed ask shares from the inside ask up to "
                         "ask x 1.005 (get_equity_price_book); omit if the "
                         "book call failed (then spread-only)")
    a = ap.parse_args()
    date = a.date or P.now_et().date().isoformat()
    now = P.parse_hhmm(a.now) if a.now else P.now_min()
    if a.scan:
        at = P.parse_hhmm(a.at) if a.at else ((now - 1) // 5) * 5
        return ingest_scan(a.scan, date, at)
    if a.check_book:
        return check_book(date, now, a.check_book.upper(), a.decision,
                          a.bid, a.ask, a.depth)
    legs, st = live_decision(date, now)
    pos = P.book_dir(BOOK) / f"position_{st.get('sym', '')}.json"
    out = dict(book=BOOK, now=P.hhmm(now), state=st["state"],
               tickets_used=st.get("tickets_used", 0))
    closed = [lg for lg in legs if not lg["open"]]
    out["closed_legs"] = [dict(sym=lg["sym"], decision=P.hhmm(lg["t"]),
                               entry_min=P.hhmm(lg["entry_min"]),
                               entry=lg["entry"],
                               exit_min=P.hhmm(lg["exit_min"]),
                               exit=lg["exit"], reason=lg["reason"])
                          for lg in closed]
    s = st["state"]
    if s == "FLAT":
        out.update(action="NOTHING", reason=st.get("reason") or
                   f"next decision at grid {P.hhmm(st['next_t'])} "
                   f"(run at wall {P.hhmm(st['next_t'] + 1)})")
    elif s == "NEED_DATA":
        out.update(action="NEED_DATA", need_bars=st["need_bars"],
                   decision_min=P.hhmm(st["t"]), ranked=st["ranked"],
                   reason="fetch minute bars 04:00->now (bounds=extended) "
                          "for need_bars, ingest, re-run")
    elif s in ("ARMED", "HOLDING"):
        sym, t = st["sym"], st["t"]
        out.update(sym=sym, decision_min=P.hhmm(t), ticket_usd=P.TICKET,
                   track_bars=[sym])
        checks = [v for v in (P.read_json(vetoes_path(date), []) or [])
                  if v["key"] == f"{sym}@{P.hhmm(t)}"]
        others = [f.stem[9:] for f in P.book_dir(BOOK).glob("position_*.json")
                  if f != pos]
        if pos.exists():
            out.update(action="HOLD", reason="exits owned by the r4 watcher")
        elif others:
            out.update(action="BLOCKED", reason=(
                f"the r4 book still holds {others} (one position at a time); "
                f"this model leg is NOT entered -- log it as a divergence"))
        elif booked(date, sym, t):
            out.update(action="HOLD", reason="leg already exited (booked by "
                       "the watcher); waiting for the model to release the "
                       "ticket")
        elif now - (t + 1) > STALE_MIN and not checks:
            # the model reached this leg late (e.g. cp_sim's 60-minute
            # look-ahead past a top name that never printed): a live trader
            # could not have acted at t -- never enter on a stale signal
            out.update(action="MISSED", reason=(
                f"stale: leg decided at grid {P.hhmm(t)} only became known "
                f"at {P.hhmm(now)}; log as MISSED (no entry, no shadow)"))
        else:
            out.update(action="ENTER", reason=(
                "coil rank, decided at grid " + P.hhmm(t) + ". FIRST run "
                "--check-book (quote + price book); enter at the ask ONLY on "
                "PASS, opening the watcher with --decision-min " + P.hhmm(t)
                + ". A VETO is logged as a SHADOW leg; re-check every minute "
                "while the model leg is open."),
                ranked=st.get("ranked"), book_checks=len(checks),
                last_check=checks[-1]["result"] if checks else None)
        if s == "HOLDING":
            lg = legs[-1]
            out.update(model_entry=lg["entry"],
                       model_entry_min=P.hhmm(lg["entry_min"]),
                       shares_cap=lg["shares"])
    else:
        out.update(action="DONE", reason="7 tickets used or window closed")
    P.emit(out)


if __name__ == "__main__":
    main()
