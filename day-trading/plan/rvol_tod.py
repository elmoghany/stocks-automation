"""Time-of-day-adjusted relative volume.

WHY THIS EXISTS (2026-08-07, Paper Day 4): the live rvol gate was computing
cumulative-volume-so-far / full-day-50-session-average. Those two quantities
are not comparable. At 10:00 ET a stock has traded maybe 20% of its day, so
even a genuinely explosive name scores ~1.0 on that ratio and gets rejected.
Paper Day 3 rejected PN at "rvol 0.9" at 10:53 (cum 703k vs full-day avg
787k); PN's actual volume that day was 12,672,415 -- rvol 16.1 -- and the
simulator traded it for +$1,333. The gate was not strict, it was broken.

The fix is to compare like with like: today's cumulative volume up to clock
time T against the AVERAGE cumulative volume up to the SAME clock time T over
the recent sessions.

INPUT is a saved robinhood-trading get_equity_historicals tool result (5-minute
bars, bounds=extended, covering ~20 sessions plus today). Those payloads run to
hundreds of KB and are written to disk by the harness rather than shown inline,
which is exactly what we want -- this script parses the file.

Usage:
    python plan/rvol_tod.py RESULT_FILE SYM [--now HH:MM] [--session-start 04:00]

Prints one auditable line per symbol:
    SYM rvol_tod=X.XX (cum A vs same-time-avg B over N sessions)
        naive_fullday=Y.YY (cum A vs full-day-avg C)

NOTE ON SESSION START: cumulative volume is accumulated from --session-start
(default 04:00 ET, i.e. including pre-market) because our entries can fire from
07:00 and the pre-market tape is part of the day's participation. Pass
--session-start 09:30 to measure the regular session only.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def load_bars(path: str, symbol: str) -> list[dict]:
    """Pull the bar list for `symbol` out of a saved tool-result file.

    The file may be pure JSON or JSON embedded in harness framing, so we
    locate the outermost JSON object rather than assuming the whole file
    parses. Raises loudly on anything ambiguous -- no silent fallbacks.
    """
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    start = raw.find("{")
    if start < 0:
        raise SystemExit(f"ERROR: no JSON object found in {path}")
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(raw[start:])
    except ValueError as exc:
        raise SystemExit(f"ERROR: could not parse JSON in {path}: {exc}")

    results = payload.get("data", payload).get("results")
    if not results:
        raise SystemExit(f"ERROR: no 'results' array in {path}")

    for res in results:
        if res.get("symbol", "").upper() == symbol.upper():
            bars = res.get("bars") or []
            if not bars:
                raise SystemExit(f"ERROR: {symbol} present but has no bars")
            return bars
    have = ", ".join(r.get("symbol", "?") for r in results)
    raise SystemExit(f"ERROR: {symbol} not in {path} (has: {have})")


def cumulative_by_session(bars: list[dict], cutoff: dtime,
                          session_start: dtime) -> dict:
    """date -> cumulative volume from session_start up to (and including)
    the bar that begins before `cutoff`. Interpolated bars carry no volume
    and are skipped explicitly rather than trusted to be zero."""
    cum = defaultdict(float)
    for b in bars:
        if b.get("interpolated"):
            continue
        ts = datetime.fromisoformat(
            b["begins_at"].replace("Z", "+00:00")).astimezone(ET)
        t = ts.time()
        if t < session_start or t >= cutoff:
            continue
        cum[ts.date()] += float(b.get("volume") or 0)
    return dict(cum)


def full_day_by_session(bars: list[dict], session_start: dtime) -> dict:
    cum = defaultdict(float)
    for b in bars:
        if b.get("interpolated"):
            continue
        ts = datetime.fromisoformat(
            b["begins_at"].replace("Z", "+00:00")).astimezone(ET)
        if ts.time() < session_start:
            continue
        cum[ts.date()] += float(b.get("volume") or 0)
    return dict(cum)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("result_file")
    ap.add_argument("symbols", nargs="+")
    ap.add_argument("--now", default=None,
                    help="clock time ET as HH:MM (default: actual now)")
    ap.add_argument("--session-start", default="04:00")
    ap.add_argument("--sessions", type=int, default=20,
                    help="how many prior sessions to average")
    args = ap.parse_args()

    now_et = datetime.now(ET)
    if args.now:
        hh, mm = args.now.split(":")
        cutoff = dtime(int(hh), int(mm))
    else:
        cutoff = now_et.time()
    sh, sm = args.session_start.split(":")
    sess_start = dtime(int(sh), int(sm))
    today = now_et.date()

    for sym in args.symbols:
        bars = load_bars(args.result_file, sym)
        cum = cumulative_by_session(bars, cutoff, sess_start)
        full = full_day_by_session(bars, sess_start)

        today_cum = cum.get(today)
        if today_cum is None:
            print(f"ERROR: {sym} has no bars for {today} before "
                  f"{cutoff.strftime('%H:%M')} -- cannot compute rvol_tod")
            continue

        prior = sorted(d for d in cum if d < today)[-args.sessions:]
        if len(prior) < 5:
            print(f"ERROR: {sym} only {len(prior)} prior sessions in file "
                  f"-- refusing to compute rvol_tod on that")
            continue

        same_time_avg = sum(cum[d] for d in prior) / len(prior)
        prior_full = [full[d] for d in prior if d in full]
        full_avg = sum(prior_full) / len(prior_full) if prior_full else 0.0

        rvol_tod = today_cum / same_time_avg if same_time_avg else float("inf")
        naive = today_cum / full_avg if full_avg else float("inf")

        print(f"{sym} rvol_tod={rvol_tod:.2f} "
              f"(cum {today_cum:,.0f} vs same-time-avg {same_time_avg:,.0f} "
              f"over {len(prior)} sessions to {cutoff.strftime('%H:%M')} ET)")
        print(f"{'':>{len(sym)}} naive_fullday={naive:.2f} "
              f"(cum {today_cum:,.0f} vs full-day-avg {full_avg:,.0f})")
        print(f"{'':>{len(sym)}} GATE rvol_tod>5 -> "
              f"{'PASS' if rvol_tod > 5 else 'FAIL'}")


if __name__ == "__main__":
    main()
