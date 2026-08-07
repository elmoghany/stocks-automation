"""Paper-position watcher: checks the held stock EVERY 1 MINUTE and
prints C02 exit events to stdout (a Monitor turns each line into a
notification). Scans stay on their own 5-min cadence elsewhere.

Usage:  python plan/paper_watch.py SYM ENTRY_PX SHARES [PREV_CLOSE]
State:  data/paper/position.json (peak / scaled survive restarts)
Exits per C10: bank 1/3 at +25%, trail 20% from peak (12% when
sellers dominate / 30% when buyers do -- monitor prints pressure),
hard stop -8%,
forced flatten at 3PM ET (C34 default). Prints one line per event:
  TICK / SCALE-OUT / EXIT-STOP / EXIT-FLATTEN  (P&L included)
Data: yfinance 1-min bars + fast_info last price (paper-grade feed).
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent.parent
POS_F = ROOT / "data" / "paper" / "position.json"


def now_et():
    return datetime.now(ET)


def latest(sym, tkr):
    """(last_price, last_minute_high) best-effort."""
    px = hi = None
    try:
        px = float(tkr.fast_info["last_price"])
    except Exception:
        pass
    try:
        h = tkr.history(period="1d", interval="1m")
        if len(h):
            hi = float(h["High"].iloc[-1])
            if px is None:
                px = float(h["Close"].iloc[-1])
    except Exception:
        pass
    return px, hi


def main():
    sym = sys.argv[1].upper()
    entry = float(sys.argv[2])
    shares = int(sys.argv[3])
    prev_close = float(sys.argv[4]) if len(sys.argv) > 4 else None

    if POS_F.exists():
        st = json.loads(POS_F.read_text())
        if st.get("sym") == sym:
            entry = st["entry"]; shares = st["shares"]
            peak = st["peak"]; scaled = st["scaled"]
        else:
            peak, scaled = entry, False
    else:
        peak, scaled = entry, False

    banked = 0.0
    tkr = yf.Ticker(sym)
    print(f"WATCHING {sym}: entry {entry} x{shares} "
          f"(peak {peak:.2f}, scaled {scaled})", flush=True)
    while True:
        t = now_et()
        if t.hour >= 15:   # 3PM flatten (C34, adopted 2026-08-07)
            px, _ = latest(sym, tkr)
            px = px or entry
            pnl = banked + (px - entry) * shares
            print(f"EXIT-FLATTEN {sym} @ {px:.2f}  3PM close  "
                  f"P&L ${pnl:+,.0f}", flush=True)
            POS_F.unlink(missing_ok=True)
            return
        px, hi = latest(sym, tkr)
        if px is None:
            print("TICK no-data", flush=True)
            time.sleep(60)
            continue
        peak = max(peak, hi or px, px)
        if not scaled and peak >= entry * 1.25:
            part = shares // 3
            fill = entry * 1.25
            banked += (fill - entry) * part
            shares -= part
            scaled = True
            print(f"SCALE-OUT {sym} {part} sh @ {fill:.2f} (+25%)  "
                  f"banked ${banked:+,.0f}", flush=True)
        stop = max(entry * 0.92, peak * 0.80)
        if px <= stop:
            pnl = banked + (stop - entry) * shares
            reason = "trail-20%" if stop > entry * 0.92 else "stop-8%"
            print(f"EXIT-STOP {sym} @ {stop:.2f}  {reason}  "
                  f"P&L ${pnl:+,.0f}", flush=True)
            POS_F.unlink(missing_ok=True)
            return
        POS_F.write_text(json.dumps(dict(
            sym=sym, entry=entry, shares=shares, peak=peak,
            scaled=scaled, banked=banked, prev_close=prev_close,
            updated=t.isoformat())))
        print(f"TICK {sym} {px:.2f}  peak {peak:.2f}  stop {stop:.2f}  "
              f"open P&L ${banked + (px - entry) * shares:+,.0f}",
              flush=True)
        time.sleep(60)


if __name__ == "__main__":
    main()
