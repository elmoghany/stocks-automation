"""PAPER-3BOOK, book R15 (2026-10-01): CATALYST-MINER
"fresh earnings AND green @09:35, h60" as a live, causal paper rule.

Paper only, open-ended. Real orders never, unless the user explicitly
authorizes them in conversation.

THE RULE (catalyst-audit.md Part 5; plan/cat_veto.rule_detail + the wide
table of plan/wn_table/cat_table, replicated here line by line):
  universe   the causal wide universe (plan/rl2 universe builder; live:
             data/paper/universe_wide.json, alphabetical order).
  fresh      the name's MOST RECENT earnings event at or before 09:35 ET is
             <= 18h old. Event clock (plan/cat_events.earnings_events):
             timing 'am' -> 07:30 ET of the report date; 'pm' or unknown
             -> 16:30 ET. So fresh = an am report TODAY, or a pm/unknown
             report on the immediately previous CALENDAR day (a Friday-pm
             report is 65h old on Monday: NOT fresh).
  candidate  bar 09:35 (grid 335) printed  (the table's printed_m gate).
  green      ret_since_open = log(close@09:35 / op) > 0, op = the
             forward-filled close at 09:30 (plan/rl2/features.py F[...,1]).
  pick       ONE name: most recent report first (smallest hours since the
             event), ties in universe (alphabetical) order. The top name is
             taken even if its order cannot fill -- the ticket is spent
             (wn_lib.single_pick takes the row, pnl 0).
  entry      model fill = OPEN of bar 09:36 (grid 336); no print -> no trade.
  size       notional = min($10,000, 0.20 x volume of bars 09:31..09:35 x
             fill) (features.volcap = 0.20 * win(cvol, 5) at m=335);
             below $500 -> no trade.
  exit       h60: OPEN of the first printed bar at or after 10:36 (grid
             396); if the symbol never prints again that day, the day's last
             printed close (features._targets forced flatten).

LIVE USE (the session agent):
  1. premarket, once:  get_earnings_calendar(start_date=TODAY, days=-2)
     -> save the result to a file -> python plan/p3_r15.py --ingest-calendar FILE
  2. at 09:36:00+ :    fetch 1-min bars (bounds=extended, 13:25Z..now in EDT)
     for the names in need_bars (<= 10/call) -> plan/p3_ingest.py or
     append_bars.py -> python plan/p3_r15.py --now HH:MM
     -> ENTER sym: buy at the ask NOW (by 09:41 or the ticket is MISSED)
  3. at 10:36:00+ :    EXIT (the watcher in EXIT_MODE r15 books it).

  python plan/p3_r15.py [--date D] [--now HH:MM] [--feed live|cache]
  python plan/p3_r15.py --ingest-calendar FILE [--date D]
"""
import argparse
import json
import math
import sys
from datetime import date as ddate, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_lib as L                                           # noqa: E402

BOOK = "r15"
DEC = L.mgrid(9, 35)          # 335 decision minute (bar 335 complete at 09:36)
FILL = DEC + 1                # 336: model entry = open of the 09:36 bar
HORIZON = 60
EXIT_K = FILL + HORIZON       # 396: h60 exit = open of first print >= 10:36
ENTER_BY = FILL + 5           # 09:41: later than this the entry is MISSED
FRESH_S = 18 * 3600.0         # cat_events WIN["18h"]
STEP = 5                      # volcap window (features.STEP)
CAP_FRAC = 0.20
MIN_NOTIONAL = 500.0
FEE_BPS, EXT_BPS = 10.0, 50.0
OPEN_K = L.M_OPEN             # 330


# ------------------------------------------------------------- universe
def universe(date=None):
    """Alphabetical wide-universe list (the rl2 panel order)."""
    f = L.DATA / "paper" / "universe_wide.json"
    d = L.read_json(f)
    if d and d.get("symbols"):
        return sorted(set(d["symbols"]))
    u = set()
    for p in sorted((L.PLAN / "rl2" / "out" / "universe").glob("2026-0[78]*.json")):
        u |= {r["symbol"] for r in json.loads(p.read_text())}
    return sorted(u)


# ------------------------------------------------------------- earnings
def event_ts(report_date, timing):
    """cat_events clock: am -> 07:30 ET, pm / unknown -> 16:30 ET."""
    y, m, d = (int(x) for x in report_date.split("-"))
    hh, mm = (7, 30) if (timing or "").lower() == "am" else (16, 30)
    return datetime(y, m, d, hh, mm, tzinfo=L.ET).timestamp()


def decision_ts(date):
    y, m, d = (int(x) for x in date.split("-"))
    return datetime(y, m, d, 9, 35, tzinfo=L.ET).timestamp()


def freshness(events, date):
    """(fresh, hrs_since) from the MOST RECENT event at or before 09:35."""
    t = decision_ts(date)
    ts = sorted(event_ts(e["report_date"], e.get("timing")) for e in events)
    ts = [x for x in ts if x <= t]
    if not ts:
        return False, 720.0
    age = t - ts[-1]
    return age <= FRESH_S, min(720.0, age / 3600.0)


def earnings_file(date):
    return L.book_dir(BOOK) / f"earnings_{date}.json"


def ingest_calendar(path, date, uni=None):
    """Saved get_earnings_calendar result -> data/paper/r15/earnings_{D}.json.

    Keeps rows whose report date is D or D-1..D-3 (enough for the 18h test),
    de-duplicated by (symbol, date). A row counts as REPORTED only when
    eps.actual is non-null -- the backtest's Robinhood source dropped rows
    without an actual (cat_events: `if r.get("act") is None: continue`).
    Unreported rows are kept with reported=false and ignored by the rule."""
    d = L.load_tool_json(path)
    if isinstance(d, dict) and "data" in d:
        d = d["data"]
    rows = d.get("results", []) if isinstance(d, dict) else []
    uni = set(uni or universe(date))
    lo = (ddate.fromisoformat(date) - timedelta(days=3)).isoformat()
    out, seen = [], set()
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        rep = r.get("report") or {}
        rd = rep.get("date")
        if not sym or not rd or not (lo <= rd <= date):
            continue
        key = (sym, rd)
        if key in seen:
            continue
        seen.add(key)
        act = (r.get("eps") or {}).get("actual")
        out.append({"symbol": sym, "report_date": rd,
                    "timing": rep.get("timing"),
                    "reported": act is not None,
                    "verified": bool(rep.get("verified")),
                    "in_universe": sym in uni})
    f = earnings_file(date)
    prev = L.read_json(f, {}) or {}
    merged = {(e["symbol"], e["report_date"]): e for e in prev.get("events", [])}
    for e in out:
        merged[(e["symbol"], e["report_date"])] = e
    ev = sorted(merged.values(), key=lambda e: (e["symbol"], e["report_date"]))
    L.write_atomic(f, {"date": date, "source": str(path), "events": ev})
    inu = [e for e in ev if e["in_universe"]]
    print(f"R15 earnings {date}: {len(ev)} rows in window, {len(inu)} in the "
          f"universe ({len(uni)} names): "
          + ", ".join(f"{e['symbol']} {e['report_date']} {e['timing']}"
                      f"{'' if e['reported'] else ' (NOT REPORTED)'}"
                      for e in inu), flush=True)
    return ev


def load_earnings(date):
    """{sym: [events]} with reported rows only (live)."""
    d = L.read_json(earnings_file(date))
    if d is None:
        return None
    out = {}
    for e in d.get("events", []):
        if e.get("reported", True):
            out.setdefault(e["symbol"], []).append(e)
    return out


# ------------------------------------------------------------- the rule
def fresh_names(uni, earnings, date):
    """Fresh-earnings names in pick order: hrs_since asc, then universe
    order (alphabetical)."""
    rows = []
    for i, s in enumerate(uni):
        ev = earnings.get(s)
        if not ev:
            continue
        fr, hrs = freshness(ev, date)
        if fr:
            rows.append((hrs, i, s))
    rows.sort()
    return [(s, hrs) for hrs, i, s in rows]


def name_state(bars):
    """(printed_m, ret_since_open, green) at 09:35 from bars <= 335."""
    if bars is None:
        return False, float("nan"), False
    o, h, lo, c, v = bars
    printed = not math.isnan(c[DEC])
    mark = L.ffill_last(c, DEC)
    op = L.ffill_last(c, OPEN_K)
    ret = math.log(mark / op) if (mark > 0 and op > 0) else float("nan")
    green = (not math.isnan(ret)) and ret > 0
    return printed, ret, green


def cost_frac(k, base_bps=FEE_BPS):
    ext = (k < L.M_OPEN) or (k >= L.M_CLOSE)
    return (base_bps + EXT_BPS * ext) / 1e4


def model_trade(bars, ticket=L.TICKET, now=None):
    """Entry / size / exit on the model convention. Bars must be the
    feed's (already truncated) view. Returns dict; fields None when the
    needed bar is not complete yet."""
    o, h, lo, c, v = bars
    out = {"entry_k": None, "entry": None, "notional": None, "shares": None,
           "exit_k": None, "exit": None, "exit_kind": None,
           "spent_no_fill": False}
    if math.isnan(o[FILL]):
        last = int(np.flatnonzero(~np.isnan(c)).max()) if (~np.isnan(c)).any() else -1
        if last >= FILL or (now is not None and now - 1 >= FILL):
            out["spent_no_fill"] = True
        return out
    fo = float(o[FILL])
    volcap = CAP_FRAC * float(np.nansum(v[DEC - STEP + 1:DEC + 1]))
    notional = min(ticket, volcap * fo)
    out.update(entry_k=FILL, entry=fo, notional=notional,
               shares=notional / fo if fo > 0 else 0.0)
    pr = np.flatnonzero(~np.isnan(c))
    after = pr[pr >= EXIT_K]
    if after.size:
        k = int(after[0])
        out.update(exit_k=k, exit=float(o[k]), exit_kind="h60")
    elif now is None or now - 1 >= L.NMIN - 1:
        # forced flatten: the day's last printed bar (only knowable at EOD)
        k = int(pr.max())
        if k >= FILL:
            out.update(exit_k=k, exit=float(c[k]), exit_kind="flatten")
    return out


def pnl_of(tr, bps=FEE_BPS):
    """features._targets: pnl = sh*ex*(1-c_out) - sh*en*(1+c_in)."""
    if tr.get("entry") is None or tr.get("exit") is None:
        return 0.0
    sh = tr["shares"]
    return (sh * tr["exit"] * (1 - cost_frac(tr["exit_k"], bps))
            - sh * tr["entry"] * (1 + cost_frac(tr["entry_k"], bps)))


def has_file(feed, sym):
    """A bar file exists for sym (fetched), even if it holds no bar <= now-1
    (a name with no print yet is NOT printed, not missing data)."""
    if isinstance(feed, L.CacheFeed):
        return any((L.MASSIVE / d / f"{sym}_{feed.date}.csv").exists()
                   for d in feed.DIRS)
    return (L.RH_BARS / f"{sym}_{feed.date}.csv").exists()


def mark_empty(syms, date):
    """Header-only rh_bars CSV for names a fetch returned NO bars for, so the
    rule reads them as 'did not print' instead of 'not fetched'."""
    for s in syms:
        f = L.RH_BARS / f"{s.upper()}_{date}.csv"
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("begins_at,open,high,low,close,volume\n")
            print(f"R15 marked {s.upper()} fetched-with-no-bars -> {f}")


def decide(date, now, feed, uni, earnings, ticket=L.TICKET):
    """The decision for wall minute `now` (bars <= now-1 visible)."""
    d = {"book": BOOK, "date": date, "now": L.hhmm(now), "action": "NOTHING",
         "sym": None, "reason": "", "decision_min": L.hhmm(DEC),
         "model_entry": None, "model_exit": None,
         "exit_due": L.hhmm(EXIT_K), "enter_by": L.hhmm(ENTER_BY),
         "need_bars": [], "candidates": []}
    if earnings is None:
        d.update(action="NEED_DATA",
                 reason="earnings calendar not ingested: get_earnings_calendar"
                        f"(start_date={date}, days=-2) -> --ingest-calendar")
        return d
    fr = fresh_names(uni, earnings, date)
    d["fresh"] = [{"sym": s, "hrs_since": round(hh, 2)} for s, hh in fr]
    if not fr:
        d.update(action="DONE", reason="no fresh-earnings name in the universe")
        return d
    names = [s for s, _ in fr]
    if now <= DEC:
        d.update(action="NOTHING", need_bars=names[:10],
                 reason=f"decision at 09:36 on the 09:35 bar; prefetch bars "
                        f"for {len(names)} fresh name(s)")
        return d
    pick = None
    for s, hrs in fr:
        b = feed.bars(s)
        fetched = b is not None or has_file(feed, s)
        printed, ret, green = name_state(b)
        row = {"sym": s, "hrs_since": round(hrs, 2), "have_bars": b is not None,
               "fetched": fetched, "printed_0935": printed,
               "ret_since_open_bp": None if math.isnan(ret) else round(ret * 1e4, 1),
               "green": green}
        d["candidates"].append(row)
        if not fetched:
            # names AHEAD of the first qualifier must be known to decide
            d["need_bars"].append(s)
            break
        if printed and green:
            pick = s
            break
    if d["need_bars"]:
        d.update(action="NEED_DATA",
                 reason="fetch 1-min bars (bounds=extended) for need_bars, "
                        "ingest, re-run")
        return d
    if pick is None:
        d.update(action="DONE", reason="no fresh name both printed @09:35 and "
                                       "green since the open")
        return d
    d["sym"] = pick
    tr = model_trade(feed.bars(pick), ticket=ticket, now=now)
    d["model_entry"] = tr["entry"]
    d["model_notional"] = tr["notional"]
    d["model_exit"] = tr["exit"]
    d["model_exit_kind"] = tr["exit_kind"]
    if tr["spent_no_fill"]:
        d.update(action="DONE", reason=f"{pick} picked but the 09:36 bar did "
                                       "not print: ticket spent, $0")
        return d
    if tr["notional"] is not None and tr["notional"] < MIN_NOTIONAL:
        d.update(action="DONE", reason=f"{pick} size cap: notional "
                 f"${tr['notional']:.0f} < $500 (20% of 5-min volume)")
        return d
    if now < EXIT_K:
        if now <= ENTER_BY:
            d.update(action="ENTER", reason=f"fresh earnings + green; buy at "
                     f"the ask now (model fill = 09:36 open); exit due 10:36")
        else:
            d.update(action="HOLD", reason="position (if entered by 09:41) "
                     "held to the 10:36 open")
        return d
    d.update(action="EXIT", reason="h60: sell at the 10:36 open (bid now)")
    return d


def watch_exit(date, st, bars, now):
    """Watcher hook (paper_watch EXIT_MODE r15). None = hold."""
    dm = st.get("decision_min")
    dm = L.parse_hhmm(dm) if isinstance(dm, str) else (DEC if dm is None else int(dm))
    k_due = dm + 1 + HORIZON
    if now < k_due:
        return None
    px, k = None, None
    if bars is not None:
        o, h, lo, c, v = bars
        pr = np.flatnonzero(~np.isnan(c))
        after = pr[pr >= k_due]
        if after.size:
            k = int(after[0])
            px = float(o[k])
    return {"decided_min": k_due, "min": k, "px": px, "reason": "h60"}


# ------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--now", help="HH:MM ET wall clock (default: now)")
    ap.add_argument("--feed", choices=("live", "cache"), default="live")
    ap.add_argument("--ingest-calendar", metavar="FILE")
    ap.add_argument("--mark-empty", metavar="SYM,SYM",
                    help="a bars fetch returned nothing for these names")
    a = ap.parse_args(argv)
    date = a.date or L.now_et().date().isoformat()
    if a.mark_empty:
        mark_empty([x for x in a.mark_empty.split(",") if x], date)
    uni = universe(date)
    if a.ingest_calendar:
        ingest_calendar(a.ingest_calendar, date, uni)
        return
    now = L.parse_hhmm(a.now) if a.now else L.now_min()
    feed = (L.LiveFeed if a.feed == "live" else L.CacheFeed)(date, now)
    dfile = L.book_dir(BOOK) / f"decision_{date}.json"
    prev = L.read_json(dfile)
    d = decide(date, now, feed, uni, load_earnings(date))
    # idempotence: once a pick is made it is frozen for the day
    if prev and prev.get("sym") and d.get("sym") != prev["sym"]:
        d["warning"] = (f"pick changed {prev['sym']} -> {d.get('sym')}; "
                        f"keeping the frozen pick {prev['sym']}")
        d["sym"] = prev["sym"]
    if d.get("sym") and not (prev and prev.get("sym")):
        L.write_atomic(dfile, {"date": date, "sym": d["sym"],
                               "frozen_at": d["now"], "decision": d})
    elif prev and prev.get("sym"):
        prev["last"] = d
        L.write_atomic(dfile, prev)
    elif d["action"] == "DONE":
        L.write_atomic(dfile, {"date": date, "sym": None, "frozen_at": d["now"],
                               "decision": d})
    L.emit(d)


if __name__ == "__main__":
    main()
