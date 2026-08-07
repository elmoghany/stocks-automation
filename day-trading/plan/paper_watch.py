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

Usage:  python plan/paper_watch.py SYM ENTRY_PX SHARES [PREV_CLOSE]
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

import yfinance as yf

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
POS_F = ROOT / "data" / "paper" / "position.json"

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


def bars(tkr):
    """Recent 1-minute bars (paper-grade feed)."""
    try:
        h = tkr.history(period="1d", interval="1m")
        return h if len(h) else None
    except Exception:
        return None


def pressure(h, win=10):
    """Volume-pressure over the last `win` bars, in [-1, 1]."""
    if h is None or len(h) < 2:
        return None
    d = h.tail(win)
    sv = v = 0.0
    for _, b in d.iterrows():
        hi, lo, c, vol = (float(b["High"]), float(b["Low"]),
                          float(b["Close"]), float(b["Volume"]))
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

    peak, scaled, banked = entry, False, 0.0
    if POS_F.exists():
        st = json.loads(POS_F.read_text())
        if st.get("sym") == sym:
            entry, shares = st["entry"], st["shares"]
            peak, scaled = st["peak"], st["scaled"]
            banked = st.get("banked", 0.0)

    tkr = yf.Ticker(sym)
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
        h = bars(tkr)
        if h is None or not len(h):
            print("TICK no-data", flush=True)
            time.sleep(30)
            continue
        bar = h.iloc[-1]
        stamp = str(h.index[-1])
        px = float(bar["Close"])
        bar_low, bar_high = float(bar["Low"]), float(bar["High"])

        # 1) RESTING STOP -- fills intrabar, so test the bar's LOW.
        #    Only evaluate a bar once (avoid re-firing on a repeat poll).
        if stamp != last_bar and bar_low <= resting:
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

        peak = max(peak, bar_high, px)
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
        if px <= trail and trail > resting:
            close_out(px, "EXIT-TRAIL")
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
