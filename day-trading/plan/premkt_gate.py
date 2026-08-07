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

# SUPERSEDED 2026-08-07 16:xx: the share-ratio floor is NOT size-neutral.
# Measured on real premarket bars after today's close:
#   TWLO  36,614 sh = 0.0162x avg50   (today's +$1,267 winner -> WOULD FAIL)
#   FRD      772 sh = 0.0091x
#   PUBM  27,787 sh = 0.0499x
# The backtest's median of 1.75x came from PENNY GAPPERS, which trade
# enormous premarket volume relative to their small normal size. Large
# caps do not, so one share-ratio cannot serve both. Premarket DOLLAR
# volume is size-neutral and was already calibrated:
#   $50k floor -> 73% of days, 72% of P&L kept   <- ADOPTED
#   $100k      -> 67% / 64%
#   $250k      -> 60% / 59%
# Today's names in dollars: TWLO ~$8.4M, NRXP ~$1.4M, PUBM ~$0.5M pass;
# FRD ~$37k fails.
DEFAULT_DOLLAR_FLOOR = 50_000.0
DEFAULT_FLOOR = 0.02      # legacy share-ratio, kept for reference only


def verdict_dollars(pm_volume, pm_vwap, floor=DEFAULT_DOLLAR_FLOOR):
    """PRIMARY GATE: premarket DOLLAR volume >= floor.

    Size-neutral, so it works on a $3 penny gapper and a $230 large cap
    alike -- unlike the share ratio, which rejected TWLO at 0.016x on a
    day it made +$1,267. Fails LOUDLY on unusable input rather than
    admitting."""
    try:
        pm_volume = float(pm_volume)
        pm_vwap = float(pm_vwap)
    except (TypeError, ValueError):
        return False, None, "ERROR: non-numeric input"
    if pm_vwap <= 0:
        return False, None, "ERROR: premarket price missing or zero"
    if pm_volume < 0:
        return False, None, "ERROR: negative premarket volume"
    dollars = pm_volume * pm_vwap
    if dollars >= floor:
        return True, dollars, (f"PASS premkt-dollars ${dollars:,.0f} "
                               f"(floor ${floor:,.0f})")
    return False, dollars, (f"FAIL premkt-dollars ${dollars:,.0f} "
                            f"(floor ${floor:,.0f}) -- no meaningful "
                            f"premarket footprint")


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
    """python premkt_gate.py PM_VOLUME PM_VWAP [FLOOR]      (dollar gate)
       python premkt_gate.py --ratio PM_VOLUME AVG50 [FLOOR] (legacy)"""
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    if args[0] == "--ratio":
        args = args[1:]
        floor = float(args[2]) if len(args) > 2 else DEFAULT_FLOOR
        ok, _, msg = verdict(args[0], args[1], floor)
    else:
        floor = float(args[2]) if len(args) > 2 else DEFAULT_DOLLAR_FLOOR
        ok, _, msg = verdict_dollars(args[0], args[1], floor)
    print(msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
