"""One-shot position state for an open C37 paper ticket.

Usage:
    python plan/posn.py SYM ENTRY_PX SHARES ENTRY_UTC_ISO

Prints everything the 1-minute loop layer needs to make a decision, computed
from the cached 1-minute bars with the SAME code the ranker and the backtest
use (day-trading.py's Candles.pressure), so the trail width cannot drift from
the champion's definition.

Reports, in one call:
  * peak since entry, last close, P&L in $ and %
  * 10-bar pressure and therefore the CURRENT trail width (20/10/40%)
  * the trail level, the -8% hard stop, and which of the two BINDS
  * an INTRABAR replay: the first bar since entry whose LOW breached the
    binding stop, tested against bar lows rather than a polled price, because
    a resting stop fills intrabar (RESTING-ORDER ARCHITECTURE, 2026-08-07)
  * the +25% scale-out level and whether pressure would skip the bank

The intrabar replay is re-run from entry on EVERY call rather than only over
new bars: if a poll is ever missed, the breach is still found instead of
silently stepped over. That is the Day-17 outage lesson turned into a check.
"""
import importlib.util
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("dt", DIR / "day-trading.py")
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)


def main():
    sym, entry_px, shares, entry_utc = sys.argv[1:5]
    entry_px, shares = float(entry_px), int(shares)

    df = dt.load_rh_bars(sym)
    if df is None or df.empty:
        print(f"ERROR: no cached bars for {sym}")
        return

    entry_ts = dt.pd.to_datetime(entry_utc, utc=True).tz_convert(dt.ET)
    held = df[df.index >= entry_ts]
    if held.empty:
        print(f"ERROR: no bars at or after entry {entry_ts}")
        return

    cd = dt.Candles(df)
    i = len(df) - 1
    press10 = cd.pressure(i, 10)
    press30 = cd.pressure(i, 30)

    peak = float(held["High"].max())
    peak_at = held["High"].idxmax()
    last = float(df["Close"].iloc[-1])
    last_at = df.index[-1]
    pnl = (last - entry_px) * shares
    pnl_pct = (last / entry_px - 1) * 100

    if press10 is None:
        width, wnote = 0.20, "20% (pressure UNTRUSTED, <20k sh - default width)"
    elif press10 <= -0.30:
        width, wnote = 0.10, "10% (10-bar pressure <= -0.30, sellers dominant)"
    elif press10 >= 0.30:
        width, wnote = 0.40, "40% (10-bar pressure >= +0.30, buyers dominant)"
    else:
        width, wnote = 0.20, "20% (default)"

    trail = peak * (1 - width)
    hard = max(entry_px * 0.92, peak * 0.60)
    binding = max(trail, hard)
    binding_name = "TRAIL" if trail >= hard else "HARD STOP -8%"
    scale_out = entry_px * 1.25

    print(f"{sym}  entry {entry_px:.4f} x{shares}  ({entry_ts:%H:%M} ET)")
    print(f"  last      {last:>10.4f}  at {last_at:%H:%M} ET")
    print(f"  peak      {peak:>10.4f}  at {peak_at:%H:%M} ET")
    print(f"  P&L       {pnl:>+10.2f}  ({pnl_pct:+.2f}%)")
    p10 = "n/a" if press10 is None else f"{press10:+.3f}"
    p30 = "n/a" if press30 is None else f"{press30:+.3f}"
    print(f"  pressure  10-bar {p10}   30-bar {p30}")
    print(f"  trail     {trail:>10.4f}  width {wnote}")
    print(f"  hardstop  {hard:>10.4f}  = max(entry x0.92, peak x0.60)")
    print(f"  BINDING   {binding:>10.4f}  <- {binding_name}   "
          f"({(last / binding - 1) * 100:+.2f}% away)")
    print(f"  scaleout  {scale_out:>10.4f}  "
          f"{'REACHED' if peak >= scale_out else 'not reached'}"
          f"{'  (pressure >= +0.3 would SKIP the bank)' if press10 is not None and press10 >= 0.3 else ''}")

    # intrabar replay from entry: recompute the running peak bar by bar so the
    # trail is tested at the width it actually had, not today's width.
    run_peak, breach = None, None
    for ts, row in held.iterrows():
        run_peak = float(row["High"]) if run_peak is None else max(run_peak, float(row["High"]))
        lvl = max(run_peak * (1 - width), max(entry_px * 0.92, run_peak * 0.60))
        if float(row["Low"]) <= lvl:
            breach = (ts, float(row["Low"]), lvl)
            break
    if breach:
        print(f"  *** INTRABAR BREACH at {breach[0]:%H:%M} ET: low {breach[1]:.4f} "
              f"<= binding {breach[2]:.4f} -- POSITION SHOULD BE FLAT ***")
    else:
        low = float(held["Low"].min())
        low_at = held["Low"].idxmin()
        print(f"  no breach since entry; lowest print {low:.4f} at {low_at:%H:%M} ET "
              f"({(low / binding - 1) * 100:+.2f}% vs binding)")


if __name__ == "__main__":
    main()
