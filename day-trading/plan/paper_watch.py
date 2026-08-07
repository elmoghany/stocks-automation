"""Paper-position watcher, RESTING-ORDER architecture (2026-08-07).

WHY THIS SHAPE: in live trading a polling loop cannot react in seconds,
so anything time-critical must already be sitting at the broker. The
work is split:

  BROKER LAYER (resting, fills in microseconds, no code awake needed)
    * protective stop-limit -- ALWAYS resting while a position is open,
      at max(entry x0.92, peak x(1 - WIDE_TRAIL)). This is the disaster
      backstop; it is re-placed (cancel/replace) each minute as `peak`
      rises, but it is never absent.
    * entry stop-limits (ORB high / premarket high) are placed by the
      session agent, not here.
  LOOP LAYER (this file, once per minute -- judgment, not speed)
    * pressure-modulated trail TIGHTENING (10% when sellers dominate)
    * the 1/3 scale-out at +25%, including the pressure-skip decision
    * bearish-pattern exits while in profit
    * the 14:57 / 14:59 flatten ladder

CRITICAL SEMANTIC: a resting stop fills INTRABAR. So the resting level
is tested against each 1-minute bar's LOW, not against the last price
seen at poll time -- otherwise a fast spike down that recovers before
the next poll would be silently missed, and the paper record would be
better than reality. Loop-layer exits are tested on the bar CLOSE,
because that is how the backtest evaluates them.

Usage:  python plan/paper_watch.py SYM ENTRY_PX SHARES PREV_CLOSE BARS_JSON
        BARS_JSON is written each cycle by the session agent from
        Robinhood get_equity_historicals (interval minute, bounds
        extended). One evaluation per invocation -- the agent drives the
        cadence, because only the agent can call Robinhood.
State:  data/paper/position.json (peak/scaled/banked survive restarts)
Prints one line per event: WATCHING / TICK / REST-STOP-MOVED /
SCALE-OUT / EXIT-RESTING-STOP / EXIT-TRAIL / EXIT-PATTERN /
EXIT-FLATTEN, each with P&L. NO REAL ORDERS ARE PLACED.
"""

import json
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent

# STATE IS PER SYMBOL (fixed 2026-08-07, when the book first held two names
# at once). A single shared position.json meant two concurrent watchers
# overwrote each other: whichever ticked last owned the file, and the other
# symbol silently lost its peak / scaled / banked state on the next restart.
# With C35 expecting ~6-7 entries in a day that is not an edge case, it is
# the normal case, and losing `scaled` would let the same third be banked
# twice. Each symbol now gets its own file.
def pos_file(sym):
    return ROOT / "data" / "paper" / f"position_{sym.upper()}.json"

HARD_STOP = 0.92          # -8% from entry, never violated
BASE_TRAIL = 0.20         # 20% from peak, normal tape
TIGHT_TRAIL = 0.10        # sellers dominate (pressure <= -0.30)
WIDE_TRAIL = 0.40         # buyers dominate (pressure >= +0.30)
P_HI, P_LO = 0.30, -0.30
SCALE_AT = 1.25           # bank 1/3 at +25% unless buyers dominate
FLATTEN_H, FLATTEN_M = 15, 0          # C35: flat by 15:00
LADDER_1 = dtime(14, 57)              # start working out
LADDER_2 = dtime(14, 59)              # drop to bid -2%
MIN_PRESSURE_VOL = 20_000


def now_et():
    return datetime.now(ET)


def bars_from_json(path):
    """Load 1-minute bars supplied by the SESSION AGENT from Robinhood.

    WHY NOT yfinance (user directive 2026-08-07, after it cost us a fake
    exit): yfinance returns regular-session bars only unless prepost is
    set, and silently serves the PREVIOUS session before 09:30 -- on the
    TWLO fill at 08:48 that produced a phantom EXIT-RESTING-STOP at
    210.44 against a 228.74 entry, reporting -$1,995 on a winning
    position. A standalone script cannot call the Robinhood MCP tools,
    so the agent fetches bars with get_equity_historicals (interval
    minute, bounds extended) and writes them here; this file only
    decides. Wrong data can no longer come from an unattended source.

    Expected JSON: {"date": "YYYY-MM-DD",
                    "bars": [{"t": ISO8601_ET, "o":, "h":, "l":, "c":,
                              "v":}, ...]}
    Bars whose date is not TODAY are dropped -- a stale file must never
    be able to close a position.
    """
    try:
        d = json.loads(Path(path).read_text())
    except Exception:
        return None
    today = now_et().date().isoformat()
    rows = [b for b in d.get("bars", [])
            if str(b.get("t", ""))[:10] == today]
    return rows or None


def pressure(h, win=10):
    """Volume-pressure over the last `win` bars, in [-1, 1]."""
    if not h or len(h) < 2:
        return None
    d = h[-win:]
    sv = v = 0.0
    for b in d:
        hi, lo, c, vol = (float(b["h"]), float(b["l"]),
                          float(b["c"]), float(b["v"]))
        if hi > lo and vol > 0:
            sv += vol * (2 * (c - lo) - (hi - lo)) / (hi - lo)
            v += vol
    if v < MIN_PRESSURE_VOL:
        return None           # too thin to mean anything
    return sv / v


def main():
    sym = sys.argv[1].upper()
    entry = float(sys.argv[2])
    shares = int(sys.argv[3])
    prev_close = float(sys.argv[4]) if len(sys.argv) > 4 else None
    bars_json = sys.argv[5] if len(sys.argv) > 5 else None
    if not bars_json:
        print("ERROR: BARS_JSON path required -- the agent must supply "
              "Robinhood bars; yfinance is no longer used", flush=True)
        return

    POS_F = pos_file(sym)
    peak, scaled, banked = entry, False, 0.0
    if POS_F.exists():
        st = json.loads(POS_F.read_text())
        if st.get("sym") == sym:
            entry, shares = st["entry"], st["shares"]
            peak, scaled = st["peak"], st["scaled"]
            banked = st.get("banked", 0.0)

    resting = max(entry * HARD_STOP, peak * (1 - WIDE_TRAIL))
    last_bar = None
    print(f"WATCHING {sym}: entry {entry:.2f} x{shares} | RESTING STOP "
          f"@ {resting:.2f} (broker-side, fills intrabar) | peak "
          f"{peak:.2f} scaled {scaled}", flush=True)

    def close_out(px, tag):
        pnl = banked + (px - entry) * shares
        print(f"{tag} {sym} @ {px:.2f}  P&L ${pnl:+,.0f}", flush=True)
        POS_F.unlink(missing_ok=True)

    while True:
        t = now_et()
        h = bars_from_json(bars_json)
        if not h:
            print("TICK no-data (stale or empty RH bars -- NOT acting; "
                  "a bad read must never close a position)", flush=True)
            time.sleep(30)
            continue
        bar = h[-1]
        stamp = str(bar.get("t"))
        px = float(bar["c"])
        bar_low, bar_high = float(bar["l"]), float(bar["h"])

        # 1) RESTING STOP -- fills intrabar, so test EVERY unseen bar's LOW,
        #    not just the newest one (fixed 2026-08-07).
        #    The agent refreshes this file every few minutes, so bars arrive
        #    in BATCHES. Testing only h[-1] meant a bar that dipped through
        #    the stop and recovered before the next refresh was never
        #    examined -- the exact "fast spike down that recovers" the module
        #    docstring says this design exists to catch. The paper record
        #    would then be better than reality, which is the one failure mode
        #    this whole exercise cannot tolerate.
        #    Bars are replayed in order and each is evaluated once.
        new_bars = h
        if last_bar is not None:
            seen = [i for i, b in enumerate(h) if str(b.get("t")) == last_bar]
            if seen:
                new_bars = h[seen[-1] + 1:]
        for b in new_bars:
            if float(b["l"]) <= resting:
                print(f"REST-STOP HIT on bar {b.get('t')} "
                      f"(low {float(b['l']):.4f} <= {resting:.4f})", flush=True)
                close_out(resting, "EXIT-RESTING-STOP")
                return
        last_bar = stamp

        # 2) hard flatten / ladder (C35 window ends 15:00)
        if t.hour >= FLATTEN_H:
            close_out(px, "EXIT-FLATTEN")
            return
        if t.time() >= LADDER_1:
            tag = "LADDER-2 (bid-2%)" if t.time() >= LADDER_2 \
                else "LADDER-1 (bid-1%)"
            print(f"TICK {sym} {px:.2f}  {tag} working out before 15:00",
                  flush=True)

        # PEAK IS THE MAX OVER EVERY BAR IN THE FILE, not just the newest
        # one (fixed 2026-08-07). The old form, max(peak, bar_high, px),
        # only ever looked at h[-1]. That is correct when the loop sees
        # every minute, but the agent refreshes the bars file every few
        # minutes, so whole bars would appear and be superseded between
        # ticks and their highs were never counted. NRXP printed 4.1497
        # while the watcher's peak sat at 3.98. An understated peak drags
        # the trail down with it, which quietly disables the exit the
        # trail exists to provide.
        peak_carried_in = peak
        peak = max([peak, px] + [float(b["h"]) for b in h])
        p = pressure(h)

        # 3) scale-out at +25%, skipped while buyers dominate
        if not scaled and peak >= entry * SCALE_AT:
            if p is not None and p >= P_HI:
                print(f"SCALE-SKIP {sym} pressure {p:+.2f} >= {P_HI} "
                      f"-- holding full size", flush=True)
            else:
                part = shares // 3
                if part >= 1:
                    fill = entry * SCALE_AT
                    banked += (fill - entry) * part
                    shares -= part
                    scaled = True
                    print(f"SCALE-OUT {sym} {part} sh @ {fill:.2f} "
                          f"(+25%)  banked ${banked:+,.0f}", flush=True)

        # 4) loop-layer trail (tighter than the resting stop), on CLOSE
        width = (TIGHT_TRAIL if (p is not None and p <= P_LO)
                 else WIDE_TRAIL if (p is not None and p >= P_HI)
                 else BASE_TRAIL)
        trail = peak * (1 - width)
        # Evaluated on the CLOSE of every unseen bar -- but with the peak AND
        # the pressure that prevailed AT THAT BAR, never today's.
        #
        # WHY THIS CARE (2026-08-07): the first version of this replay applied
        # the CURRENT trail width to historical bars, and immediately booked a
        # phantom EXIT-TRAIL on NRXP. It flagged the 11:00 bar (close 3.6850)
        # against a 10% trail of 3.7347 -- but the 10% width comes from
        # pressure <= -0.30, and at 11:18 the measured pressure was -0.20, so
        # the live trail then was the 20% one at 3.3198 and 3.6850 was nowhere
        # near it. Sellers only took over later. Judging a past bar with a
        # later reading invents an exit that never happened, which corrupts
        # the record just as badly as missing a real one -- in the opposite
        # direction. So each bar is judged on a rolling 10-bar pressure window
        # ending at that bar, and on the peak as it stood at that bar.
        start = len(h) - len(new_bars)
        # peak as it stood BEFORE the unseen bars: carried-in state plus the
        # highs of bars already evaluated on earlier passes.
        run_peak = max([peak_carried_in, entry]
                       + [float(b["h"]) for b in h[:start]])
        for i, b in enumerate(new_bars):
            idx = start + i
            run_peak = max(run_peak, float(b["h"]))
            p_i = pressure(h[max(0, idx - 9):idx + 1])
            w_i = (TIGHT_TRAIL if (p_i is not None and p_i <= P_LO)
                   else WIDE_TRAIL if (p_i is not None and p_i >= P_HI)
                   else BASE_TRAIL)
            t_i = run_peak * (1 - w_i)
            if t_i > resting and float(b["c"]) <= t_i:
                print(f"TRAIL HIT on bar {b.get('t')} "
                      f"(close {float(b['c']):.4f} <= {t_i:.4f}, "
                      f"{int(w_i * 100)}% from peak {run_peak:.4f}, "
                      f"pressure {p_i if p_i is None else round(p_i, 2)})",
                      flush=True)
                close_out(float(b["c"]), "EXIT-TRAIL")
                return

        # 5) re-place the resting stop as peak rises (cancel/replace)
        new_rest = max(entry * HARD_STOP, peak * (1 - WIDE_TRAIL))
        if new_rest > resting + 0.005:
            print(f"REST-STOP-MOVED {sym} {resting:.2f} -> "
                  f"{new_rest:.2f} (peak {peak:.2f})", flush=True)
            resting = new_rest

        POS_F.write_text(json.dumps(dict(
            sym=sym, entry=entry, shares=shares, peak=peak,
            scaled=scaled, banked=banked, resting=resting,
            prev_close=prev_close, updated=t.isoformat())))
        print(f"TICK {sym} {px:.2f}  peak {peak:.2f}  rest {resting:.2f} "
              f"trail {trail:.2f} ({int(width*100)}%) "
              f"P {p if p is None else round(p, 2)}  "
              f"open P&L ${banked + (px - entry) * shares:+,.0f}",
              flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
