"""Complete a premarket-dark name's 7AM calm-gap from Polygon.

Usage:  python plan/complete_gap7.py DATE SYM:PREVCLOSE [SYM:PREVCLOSE ...]

WHY THIS EXISTS. The calm-gap gate compares the 07:00 ET price to the prior
close, and the ranker reads it from the Robinhood 1-minute bars. RH only
emits a bar for a minute in which the name actually traded, so a name that
is simply quiet before the open has NO 07:00 bar -- and the ranker, which
fails conservative by design, reports CALM-GAP FAIL. That is the correct
default for a missing input, but it is NOT a statement about the gap: it
permanently disqualifies a name for being illiquid at 07:00 rather than for
gapping too hard. Day 19 lost MOVE exactly this way.

WHAT IS AND IS NOT LEGITIMATE HERE. Parity fix #8 forbids applying a
threshold calibrated on one feed to numbers from another, because premarket
VOLUME differs ~4x between RH and Polygon on the same symbol-day. That
argument is about volume. The calm gap is a PRICE RATIO against the prior
close, and the two feeds agree on price to the cent. Completing the gap from
Polygon is therefore sound; completing a volume gate from Polygon would not
be. Nothing here is written into the RH bar CSVs -- the feeds stay separate,
and the completion is reported for the ledger, loudly, never silently
merged.
"""
import sys
from datetime import time as dtime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared import massive                                    # noqa: E402

SEVEN = dtime(7, 0)


def main():
    date, *pairs = sys.argv[1:]
    print(f"GAP7 COMPLETION from Polygon (shared.massive.minute_bars), "
          f"{date} -- price ratio only, NOT volume; RH bar files untouched")

    for spec in pairs:
        sym, pc_s = spec.split(":")
        sym, pc = sym.upper(), float(pc_s)
        try:
            df = massive.minute_bars(sym, date)
        except Exception as e:
            print(f"  {sym:<7} ERROR {type(e).__name__}: {e}")
            continue
        if df is None or df.empty:
            print(f"  {sym:<7} NO POLYGON BARS EITHER -- gap7 genuinely "
                  f"unavailable; CALM-GAP stays FAIL (not armable)")
            continue

        at7 = df[df.index.time <= SEVEN]
        if at7.empty:
            first = df.index[0]
            print(f"  {sym:<7} no bar at or before 07:00 (first Polygon "
                  f"print {first:%H:%M} ET) -- gap7 unavailable, CALM-GAP "
                  f"stays FAIL")
            continue

        bar = at7.iloc[-1]
        ts = at7.index[-1]
        px = float(bar["Close"])
        vol = float(bar.get("Volume") or 0)
        cum = float(at7["Volume"].sum())
        gap = (px / pc - 1.0) * 100.0
        exact = "EXACT 07:00 bar" if ts.time() == SEVEN else \
                f"last print at/before 07:00 ({ts:%H:%M} ET)"
        verdict = ("CALM (<=20%)" if gap <= 20 else
                   "CALM only under the 35% top-name grace" if gap <= 35
                   else "FAIL (>35%)")
        print(f"  {sym:<7} gap7 = {gap:+.2f}%  (7AM px {px:.4f} vs prev "
              f"close {pc:.4f})  [{exact}]  -> {verdict}")
        print(f"          COMPLETED FROM POLYGON -- RH had no 07:00 bar. "
              f"Record this substitution in the day ledger.")
        # SIZE BEHIND THE PRINT (added 2026-09-01 same session, after the
        # open falsified both of the day's completions). A gap is only as
        # real as the size that set it: AMCI's completed +10.21% rested on
        # a single 200-share trade and was gone by 09:30:30. Report the
        # size so a completion can never read as a solid quote.
        print(f"          SIZE {vol:,.0f} sh on that bar, {cum:,.0f} sh "
              f"cumulative to 07:00."
              + ("  *** WARNING: fewer than 1,000 shares set this gap -- "
                 "treat it as a single-lot mark, NOT a market price. ***"
                 if cum < 1000 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
