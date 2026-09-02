"""Paper-position watcher, BOOK edition (2026-09-01, Part 3 / Commit 4).

One process watches EVERY open paper position (`--book`), owns the
end-of-day flatten ladder, books every exit itself, and is the ONLY thing
that removes a data/paper/position_{SYM}.json state file. The legacy
single-symbol argv path (SYM ENTRY SHARES PREV_CLOSE BARS_JSON) still works
and runs through the same engine, so it inherits every fix below.

WHY THE REWRITE (audit findings on the 2026-08 watcher):
  L5  position_{SYM}.json was loaded with only a `sym` check, so a file
      left over from an earlier day silently resurrected last month's
      entry/shares/peak. And the 14:57 ladder path only PRINTED -- it never
      booked or unlinked -- so stale files were the norm, not the exception.
      NOW: every state file carries `date`; a file whose date is not today
      (or has no date) is REFUSED with exit code 2 and never loaded. The
      ladder books, records and unlinks.
  L6  `if not h: continue` sat before the hard-flatten check, so a dead bar
      feed meant the flatten was never booked. NOW: the clock is read FIRST
      and the ladder fires on time even with no data (FLATTEN-NO-DATA,
      proxy = last known close).
  L12 the flatten booked the last bar in the file, which could be minutes
      old. NOW: rung fills come from the agent-written quote file
      (data/paper/quotes_{date}.json), falling back to the newest COMPLETED
      bar (BID-PROXY) and only then to the last known close.
  --  exits were done by hand while the watcher narrated. NOW: the watcher
      books stop/trail/ladder exits, writes data/paper_days/{date}.flatten.json
      and the equity curve, and the agent only feeds bars + quotes.

EXIT MODES (`--exit-mode` / EXIT_MODE env; default c37 so live is unchanged
until the switch):
  c37     today's live rules: -8% hard stop, 20/10/40% pressure trail from
          peak, bank 1/3 at +25% (skipped when buyers dominate), ladder.
  ptrail  NO hard stop (1%-of-entry sentinel), NO base trail; only the
          pressure-conditional legs (10% trail when 10-bar pressure <= -0.3,
          40% when >= +0.3, none in between); no scale-out; ladder.
  hold    no stop / trail / scale-out; ladder only.

INTRABAR SEMANTICS (parity with day-trading.py's simulate loop): for each
completed 1-minute bar, in order: peak = max(peak, bar HIGH); pressure over
the 10 bars ending at that bar; stop = max(hard, peak x (1 - width));
bar LOW <= stop -> exit AT THE STOP LEVEL. Only COMPLETED minutes count (a
bar whose start minute is the current minute is dropped). Bars are replayed
from the last bar already evaluated, so a slow feed costs awareness latency
but never settlement fidelity.

FLATTEN LADDER (times from market_calendar.session_times; full day
14:50/14:55/14:58/14:59, half day 12:50/12:55/12:58/12:59):
  rung k sells min(remaining, floor(0.20 x sum(volume of last 10 completed
  bars))) shares -- the FINAL rung has no size guard. Limit = bid x
  (1 - 0.5%/1%/2%/2%); fill = bid x (1 - 0.1%) with the limit as a floor.
  A rung is PENDING until the next completed bar: if that bar's LOW < limit
  the rung is UNFILLED (limit above market) and its shares roll forward.
  When remaining hits 0: VWAP, P&L, EXIT-FLATTEN, per-name record to
  {date}.flatten.json (with exit_parity vs the backtest's 14:59-close x
  0.999 fill once the 14:59 bar lands, <= 15:02), state file unlinked.

TICK ORDER (every 30 s): t = now_et() FIRST; (1) ladder rungs due, even
with no data; (2) bars -> peak/last_px and mode exits; (3) equity point
appended to {date}.equity.json (atomic rewrite); (4) circuit-breaker
MEASUREMENT only (-3/-5/-8% of deployed notional; CB-WOULD-FIRE is logged,
never acted on); (5) state + WATCH_ALIVE_{date}.json heartbeat.

USAGE
  python plan/paper_watch.py --book [--exit-mode c37|ptrail|hold] [--once]
  python plan/paper_watch.py --open SYM --entry PX --shares N [--ticket K]
        [--prev-close PC] [--entry-bar-utc ISO]        # create today's state
  python plan/paper_watch.py SYM ENTRY SHARES PREV_CLOSE BARS_JSON [--once]
  test hooks: --date YYYY-MM-DD --clock HH:MM --data-root DIR

NO REAL ORDERS ARE PLACED. Windows note: the TZ env var is unreliable here,
so every clock read goes through zoneinfo("America/New_York").
"""

import argparse
import csv
import json
import math
import os
import sys
import time
from datetime import date as ddate, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from market_calendar import session_times as _session_times
except Exception:                     # calendar module absent or older
    _session_times = None

DEFAULT_SESSION = {
    "close": dtime(16, 0), "exit_end": dtime(15, 0),
    "entry_cutoff": dtime(14, 30), "cross_cap": dtime(14, 0),
    "ladder": [dtime(14, 50), dtime(14, 55), dtime(14, 58), dtime(14, 59)],
}

# -------------------------------------------------------------------- rules
P_HI, P_LO = 0.30, -0.30
MIN_PRESSURE_VOL = 20_000
MODES = {
    # hard: stop as a fraction of entry (None = no stop at all)
    # base/tight/wide: trail widths from peak (None = no trail on that leg)
    "c37":    dict(hard=0.92, base=0.20, tight=0.10, wide=0.40,
                   scale_at=1.25, scale_frac=1 / 3),
    "ptrail": dict(hard=0.01, base=None, tight=0.10, wide=0.40,
                   scale_at=None, scale_frac=None),
    "hold":   dict(hard=None, base=None, tight=None, wide=None,
                   scale_at=None, scale_frac=None),
}
RUNG_LIMIT_PCT = (0.005, 0.01, 0.02, 0.02)   # bid - 0.5% / 1% / 2% / 2%
FILL_HAIRCUT = 0.001                          # fill = bid x (1 - 0.1%)
SIZE_FRAC = 0.20                              # 20% of trailing-10 volume
SIZE_BARS = 10
QUOTE_STALE_S = 90
FEED_STALE_MIN = 5          # newest completed bar older than this = no data
CB_LEVELS = (3, 5, 8)       # % of deployed notional, MEASUREMENT ONLY
PARITY_GRACE_MIN = 2        # exit_parity proxy at exit_end + 2 (15:02)
TICK_SLEEP = 30

FILLED, PENDING, UNFILLED, SKIPPED, CANCELLED = (
    "FILLED", "PENDING", "UNFILLED", "SKIPPED", "CANCELLED")


# -------------------------------------------------------------------- clock
class Clock:
    """now_et()/today() with --date/--clock overrides for replays."""

    def __init__(self, date_override=None, clock_override=None):
        self.date_override = date_override
        self.clock_override = clock_override

    def now(self):
        if self.clock_override or self.date_override:
            d = self.date_override or datetime.now(ET).date()
            hhmm = self.clock_override or datetime.now(ET).strftime("%H:%M")
            hh, mm = (int(x) for x in hhmm.split(":"))
            return datetime.combine(d, dtime(hh, mm), tzinfo=ET)
        return datetime.now(ET)

    def today(self):
        return self.now().date()


def session_for(d):
    if _session_times is not None:
        try:
            return _session_times(d)
        except Exception as e:      # non-trading day / uncovered year
            print(f"CALENDAR-FALLBACK {d}: {e} -- full-day defaults",
                  flush=True)
    return DEFAULT_SESSION


# -------------------------------------------------------------------- paths
class Paths:
    def __init__(self, data_root=None):
        self.root = Path(data_root) if data_root else ROOT / "data"
        self.bars = self.root / "rh_bars"
        self.state = self.root / "paper"
        self.days = self.root / "paper_days"

    def pos_file(self, sym):
        return self.state / f"position_{sym.upper()}.json"

    def all_pos_files(self):
        return sorted(self.state.glob("position_*.json"))

    def bars_csv(self, sym, day):
        return self.bars / f"{sym.upper()}_{day.isoformat()}.csv"

    def quotes(self, day):
        return self.state / f"quotes_{day.isoformat()}.json"

    def equity(self, day):
        return self.days / f"{day.isoformat()}.equity.json"

    def flatten(self, day):
        return self.days / f"{day.isoformat()}.flatten.json"

    def cb(self, day):
        return self.days / f"{day.isoformat()}.cb.json"

    def alive(self, day):
        return self.days / f"WATCH_ALIVE_{day.isoformat()}.json"


def write_atomic(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


# --------------------------------------------------------------------- bars
def _parse_utc(s):
    s = str(s)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _parse_et(s):
    s = str(s)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ET)
    return dt.astimezone(ET)


def _finish(rows, day, now):
    """Common tail: keep today's COMPLETED bars, sorted, deduped by minute."""
    cutoff = now.replace(second=0, microsecond=0)
    out = {}
    for b in rows:
        ts = b["ts"]
        if ts.date() != day or ts >= cutoff:
            continue                # other day / current minute / future
        out[ts] = b
    return [out[k] for k in sorted(out)]


def bars_from_csv(path, day, now):
    """data/rh_bars/{SYM}_{date}.csv: begins_at (UTC),open,high,low,close,
    volume -- appended by the agent each minute (plan/append_bars.py)."""
    rows = []
    try:
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                raw = r.get("begins_at") or r.get("timestamp")
                if not raw:
                    continue
                try:
                    ts = _parse_utc(raw).astimezone(ET)
                    rows.append(dict(ts=ts, t=ts.isoformat(),
                                     o=float(r["open"]), h=float(r["high"]),
                                     l=float(r["low"]), c=float(r["close"]),
                                     v=float(r["volume"] or 0)))
                except (ValueError, KeyError, TypeError):
                    continue
    except FileNotFoundError:
        return []
    return _finish(rows, day, now)


def bars_from_json(path, day, now):
    """Legacy BARS_JSON {"date":..., "bars":[{"t": ISO_ET, o,h,l,c,v}]}
    written by the agent (csv_to_watchjson.py). Bars from any other date
    are dropped -- a stale file must never be able to close a position."""
    d = read_json(path)
    if not d:
        return []
    rows = []
    for b in d.get("bars", []):
        try:
            ts = _parse_et(b["t"])
            rows.append(dict(ts=ts, t=ts.isoformat(), o=float(b["o"]),
                             h=float(b["h"]), l=float(b["l"]),
                             c=float(b["c"]), v=float(b.get("v", 0))))
        except (ValueError, KeyError, TypeError):
            continue
    return _finish(rows, day, now)


def pressure(win):
    """Volume-pressure over a list of bars, in [-1, 1]; None when the
    window volume is below MIN_PRESSURE_VOL (same formula as
    day-trading.py Candles.pressure)."""
    if not win:
        return None
    sv = v = 0.0
    for b in win:
        rng = b["h"] - b["l"]
        if rng > 0 and b["v"] > 0:
            sv += b["v"] * (2 * (b["c"] - b["l"]) - rng) / rng
            v += b["v"]
        elif b["v"] > 0:
            v += b["v"]
    if v < MIN_PRESSURE_VOL or v <= 0:
        return None
    return sv / v


def trail_width(mode, p):
    m = MODES[mode]
    if p is not None and p <= P_LO:
        return m["tight"], "TIGHT"
    if p is not None and p >= P_HI:
        return m["wide"], "WIDE"
    return m["base"], "BASE"


def stop_level(mode, entry, peak, p):
    """(stop, leg) for the current peak/pressure; stop None = no exit leg."""
    m = MODES[mode]
    stop, leg = None, "none"
    if m["hard"] is not None:
        stop, leg = entry * m["hard"], "HARD"
    width, name = trail_width(mode, p)
    if width is not None:
        tr = peak * (1 - width)
        if stop is None or tr > stop:
            stop, leg = tr, f"TRAIL-{name} {int(width * 100)}%"
    return stop, leg


# -------------------------------------------------------------------- state
class StaleState(Exception):
    pass


def new_state(sym, entry, shares, today, ticket=None, prev_close=None,
              entry_bar_utc=None):
    return dict(sym=sym.upper(), date=today.isoformat(), ticket=ticket,
                entry=float(entry), shares=int(shares),
                shares_initial=int(shares),
                entry_bar_utc=entry_bar_utc, prev_close=prev_close,
                peak=float(entry), last_px=float(entry), status="OPEN",
                rungs=[], scaled=False, banked=0.0, scale_out=None,
                last_bar_utc=None, updated=None)


def load_state(path: Path, today):
    st = read_json(path)
    if not isinstance(st, dict):
        raise StaleState(f"{path.name}: unreadable")
    d = st.get("date")
    if d != today.isoformat():
        raise StaleState(f"STALE-STATE {st.get('sym', path.name)} dated "
                         f"{d or 'NONE'} -- REFUSING; move it aside "
                         f"({path})")
    st.setdefault("shares_initial", st["shares"])
    st.setdefault("rungs", [])
    st.setdefault("status", "OPEN")
    st.setdefault("banked", 0.0)
    st.setdefault("scaled", False)
    st.setdefault("scale_out", None)
    st.setdefault("last_bar_utc", None)
    st.setdefault("last_px", st.get("entry"))
    st.setdefault("peak", st.get("entry"))
    return st


# ------------------------------------------------------------------- engine
class Watcher:
    def __init__(self, paths: Paths, clock: Clock, mode: str,
                 legacy=None):
        """legacy: (sym, bars_json_path) for the single-symbol argv path."""
        self.paths, self.clock, self.mode = paths, clock, mode
        self.legacy = legacy
        self.done = False

    # ---- helpers -------------------------------------------------------
    def log(self, msg):
        print(f"[{self.clock.now():%H:%M:%S}] {msg}", flush=True)

    def bars_for(self, sym, day, now):
        if self.legacy and self.legacy[0] == sym:
            return bars_from_json(self.legacy[1], day, now)
        return bars_from_csv(self.paths.bars_csv(sym, day), day, now)

    def load_positions(self, today):
        files = ([self.paths.pos_file(self.legacy[0])] if self.legacy
                 else self.paths.all_pos_files())
        out = []
        for f in files:
            if not f.exists():
                continue
            try:
                out.append(load_state(f, today))
            except StaleState as e:
                print(str(e), flush=True)
                sys.exit(2)
        return out

    def bid_for(self, st, t, quotes, bars):
        """(bid, source, is_no_data)."""
        q = (quotes or {}).get(st["sym"])
        if q and q.get("bid"):
            try:
                qts = _parse_et(q.get("ts"))
                if (t - qts).total_seconds() <= QUOTE_STALE_S:
                    return float(q["bid"]), "quote", False
            except Exception:
                pass
        if bars:
            nb = bars[-1]
            age = (t - nb["ts"]).total_seconds() / 60
            if age <= FEED_STALE_MIN + 1:
                return nb["c"], f"BID-PROXY bar {nb['ts']:%H:%M} close", False
        px = st.get("last_px") or (bars[-1]["c"] if bars else st["entry"])
        return float(px), "FLATTEN-NO-DATA proxy=last_known_close", True

    # ---- (1) ladder ----------------------------------------------------
    def ladder(self, st, t, sess, quotes, bars):
        sym, ladder = st["sym"], sess["ladder"]
        if t.time() < ladder[0]:
            return
        rungs = st["rungs"]

        def sold():
            return sum(r["shares"] for r in rungs
                       if r["status"] in (FILLED, PENDING))

        final_due = t.time() >= ladder[-1]
        # resolve PENDING rungs against the next completed bar
        for r in rungs:
            if r["status"] != PENDING:
                continue
            rt = dtime.fromisoformat(r["time"])
            rt_dt = datetime.combine(t.date(), rt, tzinfo=ET)
            nxt = next((b for b in bars if b["ts"] >= rt_dt), None)
            later_due = any(t.time() >= lt for lt in ladder
                            if lt > rt) or final_due
            if nxt is not None:
                if nxt["l"] < r["limit"]:
                    r["status"] = UNFILLED
                    r["note"] = (f"UNFILLED (limit above market: bar "
                                 f"{nxt['ts']:%H:%M} low {nxt['l']:.4f} < "
                                 f"limit {r['limit']:.4f})")
                    self.log(f"LADDER-{r['k'] + 1} {sym} {r['note']} -- "
                             f"{r['shares']} sh roll forward")
                else:
                    r["status"] = FILLED
                    r["note"] = f"confirmed by bar {nxt['ts']:%H:%M}"
            elif later_due:
                r["status"] = FILLED
                r["note"] = "UNCONFIRMED (no next bar before later rung)"
                self.log(f"LADDER-{r['k'] + 1} {sym} {r['note']}")

        remaining = st["shares"] - sold()
        for k, rt in enumerate(ladder):
            if t.time() < rt or any(r["k"] == k for r in rungs):
                continue
            if remaining <= 0:
                break
            bid, src, nodata = self.bid_for(st, t, quotes, bars)
            if nodata:
                self.log(f"FLATTEN-NO-DATA {sym} proxy=last_known_close "
                         f"{bid:.4f}")
            limit = bid * (1 - RUNG_LIMIT_PCT[k])
            fill = max(bid * (1 - FILL_HAIRCUT), limit)
            is_final = k == len(ladder) - 1
            note = ""
            if is_final:
                size = remaining
            else:
                win = bars[-SIZE_BARS:]
                vol10 = sum(b["v"] for b in win)
                if win:
                    size = min(remaining, int(math.floor(SIZE_FRAC * vol10)))
                    note = f"cap 20% x vol10 {int(vol10)}"
                else:
                    size, note = remaining, "NO-SIZE-GUARD (no bars)"
            if size < 1:
                rungs.append(dict(k=k, time=rt.isoformat(timespec="minutes"),
                                  shares=0, limit=round(limit, 4),
                                  fill=None, bid=round(bid, 4), bid_src=src,
                                  status=SKIPPED, note=f"size 0 ({note})"))
                self.log(f"LADDER-{k + 1} {sym} SKIPPED size 0 ({note})")
                continue
            rungs.append(dict(k=k, time=rt.isoformat(timespec="minutes"),
                              shares=size, limit=round(limit, 4),
                              fill=round(fill, 4), bid=round(bid, 4),
                              bid_src=src,
                              status=FILLED if is_final else PENDING,
                              note="FINAL rung, no size guard" if is_final
                              else note))
            remaining -= size
            st["status"] = "FLATTENING"
            self.log(f"LADDER-{k + 1} {sym} {size} sh limit {limit:.4f} "
                     f"fill {fill:.4f} bid {bid:.4f} ({src}) "
                     f"{'FINAL' if is_final else 'pending next bar'}"
                     f"  remaining {remaining}")

        if st["status"] == "FLATTENING" and remaining <= 0 \
                and not any(r["status"] == PENDING for r in rungs):
            self.book_flatten(st, t)

    # ---- (2) bars / mode exits ----------------------------------------
    def replay(self, st, t, sess, bars_all):
        sym, entry = st["sym"], st["entry"]
        since = _parse_utc(st["entry_bar_utc"]) if st.get("entry_bar_utc") \
            else None
        bars = [b for b in bars_all
                if since is None or b["ts"].astimezone(UTC) >= since]
        if not bars:
            return None
        st["last_px"] = bars[-1]["c"]
        last_seen = _parse_utc(st["last_bar_utc"]) if st.get("last_bar_utc") \
            else None
        new = [b for b in bars
               if last_seen is None or b["ts"].astimezone(UTC) > last_seen]
        if st["status"] == "FLATTENING":
            # the ladder owns the exit now; only bars that PREDATE the first
            # rung can still carry a stop hit the feed delivered late
            first = datetime.combine(t.date(), sess["ladder"][0], tzinfo=ET)
            new = [b for b in new if b["ts"] < first]
        m = MODES[self.mode]
        offset = len(bars_all) - len(bars)
        peak = max(float(st["peak"]), entry)
        p = None
        for b in new:
            idx = offset + bars.index(b)      # position in the full-day list
            peak = max(peak, b["h"])
            p = pressure(bars_all[max(0, idx - 9):idx + 1])
            # scale-out (c37): one-time decision at the +25% touch
            if (m["scale_at"] and not st["scaled"]
                    and peak >= entry * m["scale_at"]):
                st["scaled"] = True
                if p is not None and p >= P_HI:
                    self.log(f"SCALE-SKIP {sym} pressure {p:+.2f} >= {P_HI} "
                             f"-- holding full size")
                else:
                    part = int(st["shares"] * m["scale_frac"])
                    if part >= 1:
                        fill = entry * m["scale_at"]
                        st["banked"] += (fill - entry) * part
                        st["shares"] -= part
                        st["scale_out"] = dict(time=b["t"], shares=part,
                                               px=round(fill, 4))
                        self.log(f"SCALE-OUT {sym} {part} sh @ {fill:.4f} "
                                 f"(+{int((m['scale_at'] - 1) * 100)}%) "
                                 f"banked ${st['banked']:+,.2f}")
            stop, leg = stop_level(self.mode, entry, peak, p)
            st["peak"] = peak
            st["last_bar_utc"] = b["ts"].astimezone(UTC).isoformat()
            if stop is not None and b["l"] <= stop:
                tag = "EXIT-STOP" if leg == "HARD" else "EXIT-TRAIL"
                self.log(f"{tag} {sym} bar {b['ts']:%H:%M} low {b['l']:.4f}"
                         f" <= {stop:.4f} ({leg}, peak {peak:.4f}, "
                         f"P {'n/a' if p is None else round(p, 2)})")
                self.book_exit(st, t, stop, tag, b["t"])
                return None
        p = pressure(bars_all[-10:])
        stop, leg = stop_level(self.mode, entry, st["peak"], p)
        return dict(px=st["last_px"], peak=st["peak"], stop=stop, leg=leg,
                    p=p, bar=bars[-1]["ts"])

    # ---- booking -------------------------------------------------------
    def _record(self, st, t, kind, fills, vwap, pnl, exit_time):
        rec = dict(sym=st["sym"], ticket=st.get("ticket"), date=st["date"],
                   mode=self.mode, entry=st["entry"],
                   shares_initial=st["shares_initial"],
                   entry_bar_utc=st.get("entry_bar_utc"),
                   prev_close=st.get("prev_close"), exit_kind=kind,
                   fills=fills, vwap=round(vwap, 4) if vwap else None,
                   shares_exited=sum(f["shares"] for f in fills),
                   scale_out=st.get("scale_out"), banked=round(st["banked"], 2),
                   pnl=round(pnl, 2), peak=st["peak"], rungs=st["rungs"],
                   deployed=round(st["entry"] * st["shares_initial"], 2),
                   exit_time=exit_time, booked_at=t.isoformat(),
                   exit_parity=None)
        day = t.date()
        fl = read_json(self.paths.flatten(day)) or {
            "date": day.isoformat(), "records": []}
        fl["records"].append(rec)
        write_atomic(self.paths.flatten(day), fl)
        st["status"] = "CLOSED"
        self.paths.pos_file(st["sym"]).unlink(missing_ok=True)   # ONLY here
        return rec

    def book_flatten(self, st, t):
        fills = [dict(kind=f"rung{r['k'] + 1}", time=r["time"],
                      shares=r["shares"], px=r["fill"], src=r["bid_src"])
                 for r in st["rungs"] if r["status"] == FILLED]
        n = sum(f["shares"] for f in fills)
        vwap = sum(f["shares"] * f["px"] for f in fills) / n if n else 0.0
        pnl = st["banked"] + sum((f["px"] - st["entry"]) * f["shares"]
                                 for f in fills)
        self.log(f"EXIT-FLATTEN {st['sym']} vwap {vwap:.4f} x{n} "
                 f"P&L ${pnl:+,.2f} (entry {st['entry']:.4f}, "
                 f"{len(fills)} fills, banked ${st['banked']:+,.2f})")
        self._record(st, t, "ladder", fills, vwap, pnl,
                     st["rungs"][-1]["time"] if st["rungs"] else None)

    def book_exit(self, st, t, px, tag, bar_t):
        for r in st["rungs"]:
            if r["status"] == PENDING:
                r["status"] = CANCELLED
                r["note"] = "stop hit on an earlier bar"
        fills = [dict(kind=tag, time=bar_t, shares=st["shares"],
                      px=round(px, 4), src="stop level")]
        pnl = st["banked"] + (px - st["entry"]) * st["shares"]
        self.log(f"{tag} {st['sym']} @ {px:.4f} x{st['shares']} "
                 f"P&L ${pnl:+,.2f}")
        self._record(st, t, tag.lower(), fills, px, pnl, bar_t)

    # ---- exit parity (backtest fill = 14:59 close x 0.999) -------------
    def fill_parity(self, t, sess):
        day = t.date()
        fl = read_json(self.paths.flatten(day))
        if not fl:
            return
        changed = False
        last_rung = sess["ladder"][-1]
        deadline = (datetime.combine(day, sess["exit_end"], tzinfo=ET)
                    + timedelta(minutes=PARITY_GRACE_MIN))
        for rec in fl["records"]:
            if rec.get("exit_parity") is not None or rec["exit_kind"] != "ladder":
                continue
            bars = self.bars_for(rec["sym"], day, t)
            tgt = datetime.combine(day, last_rung, tzinfo=ET)
            bar = next((b for b in bars if b["ts"] == tgt), None)
            proxy = None
            if bar is None and t >= deadline:
                cands = [b for b in bars if b["ts"] <= tgt]
                bar = cands[-1] if cands else None
                proxy = f"{bar['ts']:%H:%M} bar (no {last_rung:%H:%M} bar)" \
                    if bar else "no bars at all"
            if bar is None and t < deadline:
                continue
            n = rec.get("shares_exited") or 0
            if bar is None:
                rec["exit_parity"] = dict(close_1459=None, backtest_exit=None,
                                          live_vwap=rec["vwap"],
                                          delta_usd=None, delta_bps=None,
                                          proxy=proxy)
            else:
                bt = bar["c"] * (1 - FILL_HAIRCUT)
                rec["exit_parity"] = dict(
                    close_1459=bar["c"], backtest_exit=round(bt, 4),
                    live_vwap=rec["vwap"],
                    delta_usd=round((rec["vwap"] - bt) * n, 2),
                    delta_bps=round((rec["vwap"] / bt - 1) * 1e4, 1)
                    if bt else None, proxy=proxy)
            self.log(f"EXIT-PARITY {rec['sym']} live {rec['vwap']} vs "
                     f"backtest {rec['exit_parity']['backtest_exit']} "
                     f"delta ${rec['exit_parity']['delta_usd']} "
                     f"({rec['exit_parity']['delta_bps']} bps)"
                     + (f" [proxy: {proxy}]" if proxy else ""))
            changed = True
        if changed:
            write_atomic(self.paths.flatten(day), fl)

    # ---- (3)-(5) equity / CB / heartbeat -------------------------------
    def bookkeeping(self, t, positions):
        day = t.date()
        opens = [st for st in positions if st["status"] != "CLOSED"]
        fl = read_json(self.paths.flatten(day)) or {"records": []}
        realized = sum(r["pnl"] for r in fl["records"])
        open_pnl = sum(st["banked"] + (st["last_px"] - st["entry"])
                       * st["shares"] for st in opens)
        deployed = (sum(st["entry"] * st["shares_initial"] for st in opens)
                    + sum(r["deployed"] for r in fl["records"]))
        book = open_pnl + realized
        dd = (book / deployed * 100) if deployed else 0.0
        point = dict(t=t.isoformat(),
                     marks={st["sym"]: st["last_px"] for st in opens},
                     open_pnl=round(open_pnl, 2), realized=round(realized, 2),
                     book_pnl=round(book, 2),
                     deployed_notional=round(deployed, 2),
                     dd_pct=round(dd, 3))
        eq = read_json(self.paths.equity(day)) or {"date": day.isoformat(),
                                                    "mode": self.mode,
                                                    "points": []}
        eq["points"].append(point)
        write_atomic(self.paths.equity(day), eq)
        # circuit breaker: MEASUREMENT ONLY
        cb = read_json(self.paths.cb(day)) or {"date": day.isoformat(),
                                                "fired": {}}
        for lvl in CB_LEVELS:
            key = str(lvl)
            if dd <= -lvl and key not in cb["fired"]:
                cb["fired"][key] = dict(t=t.isoformat(), book_pnl=round(book, 2),
                                        deployed=round(deployed, 2),
                                        dd_pct=round(dd, 3))
                self.log(f"CB-WOULD-FIRE -{lvl}% at {t:%H:%M} book "
                         f"${book:+,.2f} (LOG ONLY, NOT ACTING)")
                write_atomic(self.paths.cb(day), cb)
        for st in opens:
            st["updated"] = t.isoformat()
            write_atomic(self.paths.pos_file(st["sym"]), st)
        write_atomic(self.paths.alive(day),
                     dict(ts=t.isoformat(), open=[st["sym"] for st in opens],
                          book_pnl=round(book, 2), mode=self.mode,
                          pid=os.getpid()))
        return opens, book

    # ---- one tick ------------------------------------------------------
    def tick(self):
        t = self.clock.now()                    # FIRST, before any I/O
        day = t.date()
        sess = session_for(day)
        positions = self.load_positions(day)    # exits 2 on a stale file
        quotes = read_json(self.paths.quotes(day)) or {}
        for st in positions:
            bars_all = self.bars_for(st["sym"], day, t)
            self.ladder(st, t, sess, quotes, bars_all)          # (1)
            if st["status"] == "CLOSED":
                continue
            info = self.replay(st, t, sess, bars_all)           # (2)
            if st["status"] == "CLOSED":
                continue
            if info is None:
                self.log(f"TICK {st['sym']} no-data (no completed post-entry "
                         f"bars; NOT acting on price -- ladder still runs "
                         f"on the clock) last_px {st['last_px']:.4f}")
            else:
                stop = "-" if info["stop"] is None else f"{info['stop']:.4f}"
                p = "n/a" if info["p"] is None else f"{info['p']:+.2f}"
                self.log(f"TICK {st['sym']} {info['px']:.4f} "
                         f"(bar {info['bar']:%H:%M}) peak {info['peak']:.4f} "
                         f"stop {stop} [{info['leg']}] P {p} "
                         f"open P&L ${st['banked'] + (info['px'] - st['entry']) * st['shares']:+,.2f}"
                         f" {st['status']}")
        self.fill_parity(t, sess)
        opens, book = self.bookkeeping(t, positions)            # (3)-(5)
        if not opens:
            after = datetime.combine(day, sess["exit_end"], tzinfo=ET) \
                + timedelta(minutes=PARITY_GRACE_MIN)
            fl = read_json(self.paths.flatten(day)) or {"records": []}
            parity_pending = any(r["exit_kind"] == "ladder"
                                 and r.get("exit_parity") is None
                                 for r in fl["records"])
            if t >= after or (self.legacy and not parity_pending):
                self.done = True
        self.log(f"BOOK {len(opens)} open {[s['sym'] for s in opens]} "
                 f"book P&L ${book:+,.2f} mode {self.mode}")

    def run(self, once=False, interval=TICK_SLEEP):
        while True:
            self.tick()
            if once or self.done:
                if self.done:
                    self.log("BOOK FLAT -- watcher done")
                return
            time.sleep(interval)


# --------------------------------------------------------------------- CLI
def build_parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("legacy", nargs="*",
                    help="legacy: SYM ENTRY SHARES [PREV_CLOSE] [BARS_JSON]")
    ap.add_argument("--book", action="store_true",
                    help="watch every data/paper/position_*.json")
    ap.add_argument("--exit-mode", choices=sorted(MODES),
                    default=os.environ.get("EXIT_MODE", "c37").lower())
    ap.add_argument("--once", action="store_true", help="single tick")
    ap.add_argument("--interval", type=float, default=TICK_SLEEP)
    ap.add_argument("--clock", help="HH:MM ET override (replay)")
    ap.add_argument("--date", help="YYYY-MM-DD override (replay)")
    ap.add_argument("--data-root", help="alternate data/ root (tests)")
    ap.add_argument("--open", metavar="SYM",
                    help="create today's state file for a new fill")
    ap.add_argument("--entry", type=float)
    ap.add_argument("--shares", type=int)
    ap.add_argument("--ticket", type=int)
    ap.add_argument("--prev-close", type=float)
    ap.add_argument("--entry-bar-utc",
                    help="ISO UTC of the entry bar (default: this minute)")
    return ap


def cmd_open(args, paths, clock):
    if args.entry is None or args.shares is None:
        print("ERROR: --open needs --entry and --shares", flush=True)
        sys.exit(1)
    sym = args.open.upper()
    today = clock.today()
    f = paths.pos_file(sym)
    if f.exists():
        try:
            st = load_state(f, today)
        except StaleState as e:
            print(str(e), flush=True)
            sys.exit(2)
        print(f"ERROR: {sym} already open today (entry {st['entry']} x"
              f"{st['shares']}); refusing to overwrite", flush=True)
        sys.exit(1)
    now = clock.now()
    ebu = args.entry_bar_utc or now.astimezone(UTC).replace(
        second=0, microsecond=0).isoformat().replace("+00:00", "Z")
    st = new_state(sym, args.entry, args.shares, today, ticket=args.ticket,
                   prev_close=args.prev_close, entry_bar_utc=ebu)
    st["updated"] = now.isoformat()
    write_atomic(f, st)
    print(f"OPEN {sym} entry {args.entry:.4f} x{args.shares} ticket "
          f"{args.ticket} dated {today} entry_bar_utc {ebu} -> {f}",
          flush=True)


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.exit_mode not in MODES:
        print(f"ERROR: unknown exit mode {args.exit_mode}", flush=True)
        sys.exit(1)
    paths = Paths(args.data_root)
    clock = Clock(ddate.fromisoformat(args.date) if args.date else None,
                  args.clock)
    if args.open:
        cmd_open(args, paths, clock)
        return
    if args.book:
        w = Watcher(paths, clock, args.exit_mode)
        print(f"WATCH-BOOK mode {args.exit_mode} date {clock.today()} "
              f"state {paths.state} bars {paths.bars}", flush=True)
        w.run(once=args.once, interval=args.interval)
        return
    # ---- legacy single-symbol path ----------------------------------------
    if len(args.legacy) < 3:
        build_parser().print_help()
        sys.exit(1)
    sym = args.legacy[0].upper()
    entry, shares = float(args.legacy[1]), int(args.legacy[2])
    prev_close = float(args.legacy[3]) if len(args.legacy) > 3 else None
    bars_json = args.legacy[4] if len(args.legacy) > 4 else None
    if not bars_json:
        print("ERROR: BARS_JSON path required -- the agent must supply "
              "Robinhood bars; yfinance is no longer used", flush=True)
        sys.exit(1)
    today = clock.today()
    f = paths.pos_file(sym)
    if f.exists():
        try:
            st = load_state(f, today)       # same refusal as --book
        except StaleState as e:
            print(str(e), flush=True)
            sys.exit(2)
    else:
        st = new_state(sym, entry, shares, today, prev_close=prev_close,
                       entry_bar_utc=None)  # BARS_JSON is SINCE-filtered
        st["updated"] = clock.now().isoformat()
        write_atomic(f, st)
    print(f"WATCHING {sym}: entry {st['entry']:.4f} x{st['shares']} mode "
          f"{args.exit_mode} peak {st['peak']:.4f} scaled {st['scaled']} "
          f"(state dated {st['date']})", flush=True)
    w = Watcher(paths, clock, args.exit_mode, legacy=(sym, bars_json))
    w.run(once=args.once, interval=args.interval)


if __name__ == "__main__":
    main()
