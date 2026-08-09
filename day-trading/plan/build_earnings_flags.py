"""Join earnings histories onto candidate-days -> causal flags.

For each novol candidate (symbol, trade date): was there an earnings
report in the PRIOR 24 hours (after-close yesterday / before-open
today), and how many consecutive beats preceded it? Both knowable in
advance of the trading day -- report schedules are published, past
surprises are history.

Rule: report timestamp T flags trade date D when
  * T's date == D and T's clock < 09:30  (BMO today), or
  * T's date == previous calendar day and T's clock >= 15:55 (AMC), or
  * T's date == D-1 with no usable clock (yfinance sometimes 00:00 --
    treated as AMC of that day, the common case for these names).
Beat streak counts consecutive surprise>0 quarters STRICTLY BEFORE T.

Output data/earnings_flags.json: {"SYM|D": {"streak": n}}
Only flagged days appear; absence == no fresh earnings.
"""

import json
from datetime import date as ddate, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EY = ROOT / "data/earnings_yf.json"
OUT = ROOT / "data/earnings_flags.json"


def main():
    hist = json.loads(EY.read_text())
    flags = {}
    days_by_sym = {}
    for lab in ("year", "y2025"):
        for c in json.loads(
                (ROOT / f"data/massive/gappers_novol_{lab}.json").read_text()):
            if c.get("hist_n", 99) >= 50:
                days_by_sym.setdefault(c["symbol"], set()).add(c["date"])
    n = 0
    for sym, days in days_by_sym.items():
        evs = hist.get(sym) or []
        for d in days:
            dd = ddate.fromisoformat(d)
            prev = (dd - timedelta(days=1)).isoformat()
            hit = None
            for e in evs:
                ed, et = e["ts"][:10], e["ts"][11:]
                if (ed == d and et < "09:30") or \
                   (ed == prev and (et >= "15:55" or et == "00:00")):
                    hit = e
                    break
            if hit is None:
                continue
            streak = 0
            for e in sorted(evs, key=lambda x: x["ts"], reverse=True):
                if e["ts"] >= hit["ts"]:
                    continue
                if e["surprise"] is not None and e["surprise"] > 0:
                    streak += 1
                else:
                    break
            flags[f"{sym}|{d}"] = {"streak": streak}
            n += 1
    OUT.write_text(json.dumps(flags))
    print(f"{n:,} earnings-day candidate flags "
          f"({len(days_by_sym):,} symbols scanned) -> {OUT.name}")


if __name__ == "__main__":
    main()
