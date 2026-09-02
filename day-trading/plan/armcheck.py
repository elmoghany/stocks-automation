"""Compute the Trigger-B arming numbers for one symbol from cached RH bars.

Written 2026-08-31 (Day 19). Keeps the premarket high, the stop-limit ceiling,
the 20pct-of-trailing-10-completed-minutes size cap and the intended share count
out of conversation arithmetic -- the Day-7 lesson that anything the tooling can
compute must not be recomputed by hand.

Usage:
    python plan/armcheck.py SYM PREV_CLOSE AS_OF_UTC_ISO [TICKET_DOLLARS]
"""
import sys
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

D = Path(__file__).resolve().parent.parent / "data" / "rh_bars"
# Session boundaries are ET wall-clock, not fixed UTC minutes (2026-09-01
# live-tool fixes): 09:30 ET is 13:30Z in summer and 14:30Z after the
# 2026-11-01 DST change. The bars are UTC on disk; convert each one.
ET = ZoneInfo("America/New_York")
OPEN = dtime(9, 30)
ORB_END = dtime(9, 35)


def main():
    sym, pc, as_of = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    ticket = float(sys.argv[4]) if len(sys.argv) > 4 else 15000.0
    cutoff = datetime.fromisoformat(as_of.replace("Z", "+00:00"))

    rows = []
    for p in sorted(D.glob(f"{sym.upper()}_*.csv")):
        for ln in p.read_text().splitlines()[1:]:
            if not ln.strip():
                continue
            t, o, h, l, c, v = ln.split(",")
            ts = datetime.fromisoformat(
                t.replace("Z", "+00:00")).astimezone(ET)
            if ts <= cutoff:
                rows.append((ts, float(o), float(h), float(l), float(c), int(v)))
    if not rows:
        sys.exit(f"ERROR: no cached bars for {sym}")
    rows.sort()

    # Trigger B level = the PREMARKET high (bars strictly before 09:30 ET).
    # Trigger A level = the 5-minute opening-range high (09:30-09:34 ET
    # inclusive), then ratcheted to the RTH session high once the ORB has
    # been taken out. All comparisons in ET (rows were converted above).
    pre = [r for r in rows if r[0].time() < OPEN]
    rth = [r for r in rows if r[0].time() >= OPEN]
    orb = [r for r in rth if r[0].time() < ORB_END]
    if orb:
        orb_hi = max(r[2] for r in orb)
        rth_hi = max(r[2] for r in rth)
        print(f"  ORB high (5m)   {orb_hi:.4f}   from {len(orb)} bars "
              f"09:30-09:34 ET")
        print(f"  RTH session hi  {rth_hi:.4f}   -> Trigger A ratchet level")
        print(f"  premarket high  {max(r[2] for r in pre):.4f}   -> Trigger B level")

    hi = max(r[2] for r in rows)
    hi_t = [r[0] for r in rows if r[2] == hi][0]
    last = rows[-1][4]
    # sizing: 20% of the trailing 10 COMPLETED minutes only (leak #4)
    trail = rows[-10:]
    trail_vol = sum(r[5] for r in trail)
    trigger = hi
    ceiling = round(trigger * 1.005, 4)

    print(f"{sym.upper()}  bars={len(rows)}  last_bar={rows[-1][0].isoformat()}")
    print(f"  prev_close      {pc}")
    print(f"  session HIGH    {hi:.4f}   set at {hi_t.isoformat()}")
    print(f"  last close      {last:.4f}   ({(last/pc-1)*100:+.2f}% vs prev_close)")
    print(f"  coil last/high  {last/hi:.4f}")
    print(f"  TRIGGER (B)     {trigger:.4f}")
    print(f"  limit ceiling   {ceiling:.4f}   (trigger x 1.005)")
    print(f"  intended shares {int(ticket/trigger)}  for a ${ticket:,.0f} ticket")
    print(f"  trailing-10 vol {trail_vol:,} sh over "
          f"{trail[0][0].strftime('%H:%M')}-{trail[-1][0].strftime('%H:%M')} ET")
    print(f"  20% size cap    {int(trail_vol*0.20):,} sh"
          f"   -> {'BINDING' if trail_vol*0.20 < ticket/trigger else 'not binding'}")
    print(f"  fill-arming     last {last:.4f} vs trigger {trigger:.4f} -> "
          f"{'PASS (forward stop)' if last < trigger else 'CHASE - do NOT arm a stop'}")


if __name__ == "__main__":
    main()
