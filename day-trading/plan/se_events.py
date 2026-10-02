"""SWING-EARNINGS step 3: the event table.

Event = an 8-K carrying item 2.02 (EDGAR acceptance time, UTC).  Clock:
  accepted (ET) before 09:30 of trading day D      -> day1 = D ("am")
  accepted at/after 16:00 of D, or on a non-trading day
                                                   -> day1 = next session ("pm")
  accepted 09:30..16:00 of a trading day           -> INTRADAY, excluded
A 2.02 filing within 10 calendar days of the symbol's previous kept one is
treated as an amendment / follow-up and dropped (first one wins).
Membership: the symbol must be PIT-liquid on day1 (se_panel.liq, prior-60
sessions only).  Splits: drop if a split execution date of the symbol lies
in [day1 - 90 calendar days, day1 + 20 sessions] (calendar-only rule).

Surprise (optional, subset only): RH (est/act) or yfinance Surprise(%) within
+-3 days of day1's report date.  NOTE the yf symbol list was the walk-16
gapper membership (outcome-flavoured), so surprise is tested only as a
secondary split, never as a universe.

Output data/research_oct/se_events.json  list of dicts
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "data" / "research_oct"
ET = ZoneInfo("America/New_York")


def main():
    P = np.load(OUT / "se_panel.npz")
    dates = P["dates"].tolist()
    di = {d: i for i, d in enumerate(dates)}
    syms = P["syms"].tolist()
    si = {s: j for j, s in enumerate(syms)}
    liq = P["liq"]
    ed = json.loads((OUT / "se_edgar_202.json").read_text())
    splits = json.loads((OUT / "se_splits.json").read_text())
    rh = json.loads((ROOT / "data" / "filings_hist" / "earnings_rh.json").read_text())
    yf = json.loads((ROOT / "data" / "earnings_yf.json").read_text())

    def surprise(sym, d):
        lo = (datetime.fromisoformat(d) - timedelta(days=3)).date().isoformat()
        hi = (datetime.fromisoformat(d) + timedelta(days=3)).date().isoformat()
        for r in rh.get(sym, []):
            if lo <= r["date"] <= hi and r.get("act") is not None and r.get("est") is not None:
                return (r["act"] - r["est"]) / max(abs(r["est"]), 0.01) * 100.0
        for r in yf.get(sym, []):
            if lo <= r["ts"][:10] <= hi and r.get("surprise") is not None:
                return float(r["surprise"])
        return None

    ev, cnt = [], {"filings": 0, "dup": 0, "intraday": 0, "out_of_range": 0,
                   "not_liquid": 0, "split": 0}
    for sym, rows in ed.items():
        if sym.startswith("_") or sym not in si:
            continue
        j = si[sym]
        last = None
        for acc, form in rows:
            cnt["filings"] += 1
            t = datetime.fromisoformat(acc.replace("Z", "+00:00")).astimezone(ET)
            if last is not None and (t - last).days < 10:
                cnt["dup"] += 1
                continue
            last = t
            dstr = t.date().isoformat()
            hm = t.hour * 60 + t.minute
            if dstr in di and 570 <= hm < 960:
                cnt["intraday"] += 1
                continue
            if dstr in di and hm < 570:
                d1, timing = di[dstr], "am"
            else:
                nx = [i for i in range(len(dates)) if dates[i] > dstr]
                if not nx:
                    cnt["out_of_range"] += 1
                    continue
                d1, timing = nx[0], "pm"
            if d1 < 61:
                cnt["out_of_range"] += 1
                continue
            if not liq[d1, j]:
                cnt["not_liquid"] += 1
                continue
            lo = (datetime.fromisoformat(dates[d1]) - timedelta(days=90)).date().isoformat()
            hi = dates[min(d1 + 20, len(dates) - 1)]
            if any(lo <= x <= hi for x in splits.get(sym, [])):
                cnt["split"] += 1
                continue
            ev.append({"sym": sym, "j": j, "d1": d1, "day1": dates[d1],
                       "accepted_et": t.strftime("%Y-%m-%d %H:%M"), "timing": timing,
                       "surprise": surprise(sym, dates[d1])})
    ev.sort(key=lambda e: (e["d1"], e["sym"]))
    (OUT / "se_events.json").write_text(json.dumps(ev))
    hrs = [int(e["accepted_et"][11:13]) for e in ev]
    print(cnt, "events", len(ev), "symbols", len({e["sym"] for e in ev}))
    print("am share", np.mean([e["timing"] == "am" for e in ev]).round(3),
          "accepted-hour histogram", np.bincount(hrs, minlength=24).tolist())
    print("with surprise", sum(e["surprise"] is not None for e in ev))
    by = {}
    for e in ev:
        by[e["day1"][:7]] = by.get(e["day1"][:7], 0) + 1
    print(sorted(by.items()))


if __name__ == "__main__":
    main()
