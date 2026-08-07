"""PREMARKET-COMPUTABLE ACTIVITY GATE (2026-08-07) -- replaces the
broken live rvol check.

THE HISTORY, so nobody re-introduces the bug:
  * The backtest gate is full-day volume / 50-day average >= 5. That is
    unknowable before the close.
  * Live was computing cumulative-so-far / full-day average, which at
    10:53 scored PN at 0.9 when its real figure was 16.1 -- it rejected
    a name the simulator made +$1,333 on.
  * The first fix attempt projected the full day by dividing by a
    market-wide intraday profile. That failed too: the premarket share
    of a day has mean 5.1% but MEDIAN 0.1%, so dividing by it amplified
    noise. Gating on it cost 42% of the edge.
  * What works is far simpler: compare premarket volume DIRECTLY to the
    stock's normal FULL-DAY volume. No profile, no projection.
    Measured live on 2026-08-07 at 09:15, before the open:
      NAMI 39.7x   DOCS 6.5x   DSY 2.3x   TWLO 2.0x   FRD 1.8x
    Nine of ten candidates had already traded more than a normal day's
    volume premarket.

BACKTEST CALIBRATION (plan/premkt_signals.py, 282 traded days,
$939,232 of C35 P&L on days with premarket bars):
    threshold   days kept   P&L kept
      0.02         83%        84%     <- DEFAULT
      0.05         76%        72%
      0.10         68%        59%
      0.50         54%        44%
      1.00         48%        40%
Retention FALLS as the threshold rises, so this must be used as a
PERMISSIVE FLOOR, not a selector. Its job is to exclude names with
essentially no premarket footprint -- nothing more. The real filtering
is done by the other gates (>= +10% gain, 7AM calm-gap, halal, price).
Compare 84% retained here against 58% for the projection approach.

HONEST LIMIT: this is calibrated on candidates that ALREADY passed the
backtest's full-day rvol gate, so it measures how many good days the
floor keeps -- NOT how many junk names it lets through. The
false-positive rate is unmeasured.

Usage (the agent supplies the numbers; only it can call Robinhood):
    python plan/premkt_gate.py PREMARKET_VOLUME AVG50_DAILY_VOLUME
Exit code 0 = PASS, 1 = FAIL. Prints the ratio and the verdict.
"""

import sys

DEFAULT_FLOOR = 0.02      # premarket volume as a multiple of a normal DAY


def verdict(pm_volume, avg50_daily, floor=DEFAULT_FLOOR):
    """Return (passed, ratio, message). Never raises on bad input --
    it returns a loud FAIL so a data problem cannot silently admit."""
    try:
        pm_volume = float(pm_volume)
        avg50_daily = float(avg50_daily)
    except (TypeError, ValueError):
        return False, None, "ERROR: non-numeric input"
    if avg50_daily <= 0:
        return False, None, "ERROR: 50-day average volume missing or zero"
    if pm_volume < 0:
        return False, None, "ERROR: negative premarket volume"
    ratio = pm_volume / avg50_daily
    if ratio >= floor:
        return True, ratio, (
            f"PASS premkt-activity {ratio:.3f}x a normal day "
            f"(floor {floor})")
    return False, ratio, (
        f"FAIL premkt-activity {ratio:.3f}x a normal day "
        f"(floor {floor}) -- no meaningful premarket footprint")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    floor = float(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_FLOOR
    ok, ratio, msg = verdict(sys.argv[1], sys.argv[2], floor)
    print(msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
