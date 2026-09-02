"""Read-only report on the open paper book (2026-09-01 rewrite).

REPORTING ONLY: nothing here books, unlinks or decides. The watcher
(plan/paper_watch.py --book) owns every exit; this prints what it will
act on so the session agent can narrate without re-deriving the rules.

Usage:
    python plan/posn.py                       # every open position file
    python plan/posn.py SYM                   # one open position file
    python plan/posn.py SYM ENTRY SHARES ENTRY_UTC_ISO   # legacy ad-hoc
    options: --exit-mode c37|ptrail|hold (default EXIT_MODE env / c37)
             --date YYYY-MM-DD --clock HH:MM --data-root DIR (replays)

Per open name: entry, shares, last, peak, P&L, 10-bar pressure, the
ACTIVE exit leg for the selected mode (c37: hard -8% vs 20/10/40 trail;
ptrail: only the pressure-conditional 10%/40% legs, so the leg can be
"none -- no stop armed"; hold: none), minutes to the first ladder rung,
and the exit-side size cap (20% of trailing-10-bar volume), plus an
intrabar replay from entry that reports the first bar whose LOW breached
the leg that was active AT THAT BAR (a missed poll is still found).

Stale state files (date != today) are reported as STALE and skipped --
they are never interpreted as a live position.
"""
import argparse
import os
import sys
from datetime import date as ddate, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_watch as pw                                    # noqa: E402


def report(sym, st, mode, paths, clock):
    t = clock.now()
    day = t.date()
    sess = pw.session_for(day)
    entry, shares = float(st["entry"]), int(st["shares"])
    bars_all = pw.bars_from_csv(paths.bars_csv(sym, day), day, t)
    since = pw._parse_utc(st["entry_bar_utc"]) if st.get("entry_bar_utc") \
        else None
    held = [b for b in bars_all
            if since is None or b["ts"].astimezone(pw.UTC) >= since]
    first_rung = datetime.combine(day, sess["ladder"][0], tzinfo=pw.ET)
    mins = (first_rung - t).total_seconds() / 60
    print(f"{sym}  entry {entry:.4f} x{shares}  ticket {st.get('ticket')}  "
          f"status {st.get('status', 'OPEN')}  mode {mode}  "
          f"(state dated {st.get('date')})")
    if not held:
        print(f"  no completed post-entry bars yet (entry_bar_utc "
              f"{st.get('entry_bar_utc')}); last_px {st.get('last_px')}")
        print(f"  ladder     first rung {sess['ladder'][0]:%H:%M} in "
              f"{mins:+.0f} min; the watcher flattens on the clock even "
              f"with no data")
        return
    last, last_at = held[-1]["c"], held[-1]["ts"]
    peak_bar = max(held, key=lambda b: b["h"])
    peak = max(float(st.get("peak", entry)), peak_bar["h"], entry)
    banked = float(st.get("banked", 0.0))
    pnl = banked + (last - entry) * shares
    p10 = pw.pressure(bars_all[-10:])
    p30 = pw.pressure(bars_all[-30:])
    stop, leg = pw.stop_level(mode, entry, peak, p10)
    vol10 = sum(b["v"] for b in bars_all[-pw.SIZE_BARS:])
    cap = int(pw.SIZE_FRAC * vol10)
    fmt = lambda x: "n/a" if x is None else f"{x:+.3f}"           # noqa
    print(f"  last      {last:>10.4f}  at {last_at:%H:%M} ET")
    print(f"  peak      {peak:>10.4f}  at {peak_bar['ts']:%H:%M} ET  "
          f"({(peak / entry - 1) * 100:+.1f}%)")
    print(f"  P&L       {pnl:>+10.2f}  ({(last / entry - 1) * 100:+.2f}%)"
          f"  banked {banked:+.2f}  scaled {st.get('scaled', False)}")
    print(f"  pressure  10-bar {fmt(p10)}   30-bar {fmt(p30)}")
    if stop is None:
        print(f"  exit leg  none -- no stop armed in mode {mode}; the "
              f"ladder is the only exit")
    else:
        print(f"  exit leg  {stop:>10.4f}  <- {leg}  "
              f"({(last / stop - 1) * 100:+.2f}% away)")
        if mode == "c37":
            m = pw.MODES[mode]
            print(f"            hard {entry * m['hard']:.4f}  trail "
                  f"{peak * (1 - pw.trail_width(mode, p10)[0]):.4f}"
                  f"  scale-out {entry * m['scale_at']:.4f} "
                  f"{'REACHED' if peak >= entry * m['scale_at'] else 'not reached'}")
        elif mode == "ptrail":
            print(f"            legs arm only on pressure: 10% from peak "
                  f"at <= {pw.P_LO:+.1f} ({peak * 0.9:.4f}), 40% at >= "
                  f"{pw.P_HI:+.1f} ({peak * 0.6:.4f}); none between")
    print(f"  ladder    first rung {sess['ladder'][0]:%H:%M} in "
          f"{mins:+.0f} min; rungs "
          + ",".join(f"{x:%H:%M}" for x in sess["ladder"]))
    print(f"  size cap  {cap} sh per rung (20% x trailing-10 vol "
          f"{int(vol10)}); {shares} sh would need "
          f"{'1 rung' if cap >= shares else f'{shares / cap:.1f} rungs' if cap else 'the FINAL rung'}")
    # intrabar replay from entry with the leg active AT EACH BAR
    run_peak, breach = entry, None
    off = len(bars_all) - len(held)
    for i, b in enumerate(held):
        run_peak = max(run_peak, b["h"])
        p_i = pw.pressure(bars_all[max(0, off + i - 9):off + i + 1])
        lvl, leg_i = pw.stop_level(mode, entry, run_peak, p_i)
        if lvl is not None and b["l"] <= lvl:
            breach = (b["ts"], b["l"], lvl, leg_i)
            break
    if breach:
        print(f"  *** INTRABAR BREACH at {breach[0]:%H:%M} ET: low "
              f"{breach[1]:.4f} <= {breach[2]:.4f} ({breach[3]}) -- the "
              f"watcher should have booked this; check its log ***")
    else:
        low_bar = min(held, key=lambda b: b["l"])
        print(f"  no breach since entry; lowest print {low_bar['l']:.4f} at "
              f"{low_bar['ts']:%H:%M} ET")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("legacy", nargs="*")
    ap.add_argument("--exit-mode", choices=sorted(pw.MODES),
                    default=os.environ.get("EXIT_MODE", "c37").lower())
    ap.add_argument("--clock")
    ap.add_argument("--date")
    ap.add_argument("--data-root")
    a = ap.parse_args(argv)
    paths = pw.Paths(a.data_root)
    clock = pw.Clock(ddate.fromisoformat(a.date) if a.date else None,
                     a.clock)
    today = clock.today()
    if len(a.legacy) >= 4:                       # ad-hoc, no state file
        sym, entry, shares, ebu = a.legacy[:4]
        st = pw.new_state(sym, float(entry), int(shares), today,
                          entry_bar_utc=ebu)
        report(sym.upper(), st, a.exit_mode, paths, clock)
        return
    files = ([paths.pos_file(a.legacy[0])] if a.legacy
             else paths.all_pos_files())
    if not files or not any(f.exists() for f in files):
        print(f"BOOK EMPTY -- no position files in {paths.state}")
        return
    for f in files:
        if not f.exists():
            print(f"{f.name}: not open")
            continue
        try:
            st = pw.load_state(f, today)
        except pw.StaleState as e:
            print(f"{e}  (skipped by posn; the watcher will refuse it)")
            continue
        report(st["sym"], st, a.exit_mode, paths, clock)
        print()


if __name__ == "__main__":
    main()
