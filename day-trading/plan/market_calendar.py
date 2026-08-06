"""US equity market calendar guard for the paper-trading schedule
(user 2026-08-06: "run paper trader except weekends and holidays").

Every scheduled paper session calls this FIRST and aborts unless it
prints TRADING. Exit codes: 0 = trading day, 1 = not a trading day.

  python day-trading/plan/market_calendar.py            # today
  python day-trading/plan/market_calendar.py 2026-11-26 # a given date

Output line: "TRADING <date> full" | "TRADING <date> half (13:00 close)"
             | "NO-TRADE <date> weekend|holiday:<name>"

Half days matter: the C30 flatten is already 13:00, but E01 must sell
at the 13:00 close instead of 16:00, and its close-out cron (16:06)
still works because it reads the OFFICIAL close quote either way.
NYSE holidays through 2027; extend HOLIDAYS before Jan 2028 (the
script prints a loud ERROR if asked about an uncovered year rather
than silently assuming the market is open).
"""

import sys
from datetime import date as ddate

HOLIDAYS = {
    # 2026
    "2026-01-01": "New Year's Day",
    "2026-01-19": "Martin Luther King Jr. Day",
    "2026-02-16": "Presidents' Day",
    "2026-04-03": "Good Friday",
    "2026-05-25": "Memorial Day",
    "2026-06-19": "Juneteenth",
    "2026-07-03": "Independence Day (observed)",
    "2026-09-07": "Labor Day",
    "2026-11-26": "Thanksgiving",
    "2026-12-25": "Christmas",
    # 2027
    "2027-01-01": "New Year's Day",
    "2027-01-18": "Martin Luther King Jr. Day",
    "2027-02-15": "Presidents' Day",
    "2027-03-26": "Good Friday",
    "2027-05-31": "Memorial Day",
    "2027-06-18": "Juneteenth (observed)",
    "2027-07-05": "Independence Day (observed)",
    "2027-09-06": "Labor Day",
    "2027-11-25": "Thanksgiving",
    "2027-12-24": "Christmas (observed)",
}

HALF_DAYS = {
    "2026-11-27": "day after Thanksgiving",
    "2026-12-24": "Christmas Eve",
    "2027-11-26": "day after Thanksgiving",
}

COVERED_YEARS = (2026, 2027)


def status(d: ddate):
    ds = d.isoformat()
    if d.year not in COVERED_YEARS:
        return ("ERROR", f"{ds} outside the covered calendar "
                         f"{COVERED_YEARS} -- extend HOLIDAYS")
    if d.weekday() >= 5:
        return ("NO-TRADE", f"{ds} weekend")
    if ds in HOLIDAYS:
        return ("NO-TRADE", f"{ds} holiday:{HOLIDAYS[ds]}")
    if ds in HALF_DAYS:
        return ("TRADING", f"{ds} half (13:00 close) -- {HALF_DAYS[ds]}")
    return ("TRADING", f"{ds} full")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    d = ddate.fromisoformat(arg) if arg else ddate.today()
    verdict, detail = status(d)
    print(f"{verdict} {detail}")
    sys.exit(0 if verdict == "TRADING" else 1)


if __name__ == "__main__":
    main()
