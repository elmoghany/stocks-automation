"""PAPER-VS-BT, book R15: re-run the R15 rule (plan/p3_r15 functions) on the
11 paper days with an earnings calendar pulled AFTER the fact
(Robinhood get_earnings_calendar(start_date=2026-10-19, days=-18), 158 rows,
symbols in data/pvb/earnings_cal_1002_1019.txt; only ANGO 2026-10-08 am and
CHRN 2026-10-14 pm are in the 95-name universe, both with an EPS actual)
and full-day RTH bars (data/pvb/rh). Compares with the live session's own
calendar files and decisions. Writes data/pvb/r15_compare.json.

    python plan/pvb_r15.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_lib as L                                           # noqa: E402
import p3_r15 as R                                           # noqa: E402

DAYS = ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09",
        "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16",
        "2026-10-19"]
# universe rows of the after-the-fact calendar (eps actual present)
EVENTS = {"ANGO": [{"report_date": "2026-10-08", "timing": "am"}],
          "CHRN": [{"report_date": "2026-10-14", "timing": "pm"}]}
RHD = L.DATA / "pvb" / "rh"


def main():
    uni = R.universe()
    cal = set((L.DATA / "pvb" / "earnings_cal_1002_1019.txt").read_text().split())
    assert set(EVENTS) == cal & set(uni), cal & set(uni)
    out = {}
    for d in DAYS:
        fr = R.fresh_names(uni, EVENTS, d)
        rows = []
        pick = None
        for s, hrs in fr:
            b = L.read_bars_csv(RHD / f"{s}_{d}.csv", d)
            pr, ret, green = R.name_state(b)
            tr = R.model_trade(b) if b is not None else {}
            row = dict(sym=s, hrs=round(hrs, 2), printed_0935=pr,
                       ret_bp=None if math.isnan(ret) else round(ret * 1e4, 1),
                       green=green, hypothetical_trade=dict(
                           entry=tr.get("entry"), exit=tr.get("exit"),
                           pnl_9bps=round(R.pnl_of(tr, 9.0), 2)
                           if tr.get("entry") else None))
            rows.append(row)
            if pr and green:
                pick = s
                break
        live = (L.read_json(L.book_dir("r15") / f"decision_{d}.json", {})
                or {}).get("decision") or {}
        lev = L.read_json(R.earnings_file(d), {}) or {}
        out[d] = dict(fresh=[s for s, _ in fr], rows=rows, bt_pick=pick,
                      live_action=live.get("action"),
                      live_reason=live.get("reason"),
                      live_fresh=[x.get("sym") for x in live.get("fresh", [])],
                      live_candidates=live.get("candidates"),
                      live_calendar_universe_rows=[
                          (e["symbol"], e["report_date"], e["timing"])
                          for e in lev.get("events", []) if e.get("in_universe")])
        print(d, "fresh", out[d]["fresh"], "bt pick", pick, "| live",
              live.get("action"), out[d]["live_fresh"], rows, flush=True)
    (L.DATA / "pvb" / "r15_compare.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
