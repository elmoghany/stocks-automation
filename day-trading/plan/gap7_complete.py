"""Complete a missing 7AM ET bar for RH-premarket-dark names from Polygon.

Written 2026-08-31 (Day 19), per the standing instruction: "RH premarket-dark
names read CALM-GAP FAIL from a missing 7AM bar: complete gap7 from
shared.massive.minute_bars (Polygon) and LOG the completion loudly."

The ranker fails CONSERVATIVE on a missing gap7, so a name RH simply did not
print at 07:00 is refused for a data reason rather than a market reason. This
reads Polygon's tape for the 07:00 ET minute and reports the true gap.

FEED-CALIBRATION WARNING (fix #8): Polygon and Robinhood disagree on premarket
volume by ~4x on the same symbol-day. This tool is used ONLY to answer "did the
7AM bar exist and at what PRICE" -- price levels, not volume thresholds. Never
feed a Polygon volume into an RH-calibrated gate.

Usage:
    python plan/gap7_complete.py SYM PREV_CLOSE [YYYY-MM-DD]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared import massive


def main():
    sym = sys.argv[1].upper()
    pc = float(sys.argv[2])
    date = sys.argv[3] if len(sys.argv) > 3 else "2026-08-31"

    df = massive.minute_bars(sym, date)
    if df is None or df.empty:
        print(f"ERROR: Polygon returned NO bars for {sym} on {date} -- "
              f"gap7 cannot be completed, CALM-GAP FAIL stands.")
        return

    seven = df.between_time("07:00", "07:00")
    print(f"{sym}  Polygon bars={len(df)}  "
          f"first={df.index[0]:%H:%M}  last={df.index[-1]:%H:%M} ET")
    if seven.empty:
        print(f"  NO 07:00 ET bar on Polygon either -- the name genuinely did "
              f"not trade at 7AM. CALM-GAP FAIL stands (real, not a data gap).")
    else:
        r = seven.iloc[0]
        gap = (r.Close / pc - 1) * 100
        print(f"  07:00 ET bar FOUND: O={r.Open} H={r.High} L={r.Low} "
              f"C={r.Close} V={int(r.Volume)}")
        print(f"  GAP7 COMPLETED: close {r.Close} vs prev_close {pc} "
              f"= {gap:+.2f}%")
        print(f"  calm-gap verdict: "
              f"{'PASS (<=20%)' if gap <= 20 else 'PASS only with the 35% top-name grace' if gap <= 35 else 'FAIL (>35%, grace cannot save it)'}")

    pre = df.between_time("04:00", "09:29")
    print(f"  premarket bars 04:00-09:29 ET: {len(pre)}, "
          f"volume {int(pre.Volume.sum()):,} (POLYGON basis - do not compare "
          f"to an RH-calibrated threshold)")
    if len(pre):
        print(f"  premarket high {pre.High.max()}  low {pre.Low.min()}")


if __name__ == "__main__":
    main()
