"""US equity market calendar guard for the paper-trading schedule
(user 2026-08-06: "run paper trader except weekends and holidays").

Every scheduled paper session calls this FIRST and aborts unless it
prints TRADING. Exit codes: 0 = trading day, 1 = not a trading day.

  python day-trading/plan/market_calendar.py            # today
  python day-trading/plan/market_calendar.py 2026-11-26 # a given date

Output line: "TRADING <date> full" | "TRADING <date> half (13:00 close)"
             | "NO-TRADE <date> weekend|holiday:<name>"
Second line (2026-09-01, live-tool fixes): "SESSION close=HH:MM ..." with
the session clock from session_times(); the launcher greps line 1 only.

Half days matter: the C30 flatten is already 13:00, but E01 must sell
at the 13:00 close instead of 16:00, and its close-out cron (16:06)
still works because it reads the OFFICIAL close quote either way.
NYSE holidays through 2027; extend HOLIDAYS before Jan 2028 (the
script prints a loud ERROR if asked about an uncovered year rather
than silently assuming the market is open).
"""

import sys
from datetime import date as ddate, time as dtime

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


def close_time(d: ddate) -> dtime:
    """Official close for a trading day: 13:00 on the listed half days,
    16:00 otherwise. Raises on an uncovered year or a non-trading day
    (a caller asking for the close of a holiday has a bug upstream)."""
    verdict, detail = status(d)
    if verdict != "TRADING":
        raise ValueError(f"{verdict} {detail}")
    return dtime(13, 0) if d.isoformat() in HALF_DAYS else dtime(16, 0)


def session_times(d: ddate) -> dict:
    """The session clock every live tool should read instead of hard-
    coding 16:00 / 15:00 / 14:30 / 14:00 (2026-09-01 live-tool fixes).

      close        official close (13:00 half day, else 16:00)
      exit_end     E01 exit window end = close - 1h on a full day; on a
                   half day the flatten IS the close
      entry_cutoff last minute a new ticket may be armed
      cross_cap    a +10% cross must print on a bar <= this to be
                   eligible (rotation_sim.rank_at parity)
      ladder       the flatten ladder (four probes before the close)

    Full day:  16:00 / 15:00 / 14:30 / 14:00 / [14:50,14:55,14:58,14:59]
    Half day:  13:00 / 13:00 / 12:00 / 11:30 / [12:50,12:55,12:58,12:59]
    Raises ValueError on ERROR (uncovered year) or a NO-TRADE day."""
    close = close_time(d)                 # raises on ERROR / NO-TRADE
    if close == dtime(13, 0):
        return {"close": dtime(13, 0), "exit_end": dtime(13, 0),
                "entry_cutoff": dtime(12, 0), "cross_cap": dtime(11, 30),
                "ladder": [dtime(12, 50), dtime(12, 55), dtime(12, 58),
                           dtime(12, 59)]}
    return {"close": dtime(16, 0), "exit_end": dtime(15, 0),
            "entry_cutoff": dtime(14, 30), "cross_cap": dtime(14, 0),
            "ladder": [dtime(14, 50), dtime(14, 55), dtime(14, 58),
                       dtime(14, 59)]}


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    d = ddate.fromisoformat(arg) if arg else ddate.today()
    verdict, detail = status(d)
    print(f"{verdict} {detail}")          # line 1 is grepped by the launcher
    if verdict == "TRADING":
        st = session_times(d)
        print(f"SESSION close={st['close']:%H:%M} exit_end="
              f"{st['exit_end']:%H:%M} entry_cutoff="
              f"{st['entry_cutoff']:%H:%M} cross_cap="
              f"{st['cross_cap']:%H:%M} ladder="
              + ",".join(f"{t:%H:%M}" for t in st["ladder"]))
    sys.exit(0 if verdict == "TRADING" else 1)


if __name__ == "__main__":
    main()
