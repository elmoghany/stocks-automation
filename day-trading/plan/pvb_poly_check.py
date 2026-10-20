"""PAPER-VS-BT: data-source check. For every R4 / RL leg that paper traded
or the backtest took, replay the book's own exit code (p3_r4.watch_exit /
p3_rl.watch_exit, minute by minute on truncated bars) on Robinhood bars
(data/pvb/rhx, data/pvb/rh) and on Polygon bars (data/pvb/poly) and compare
model entry, exit minute, exit price and P&L per $10k ticket.
Writes data/pvb/poly_check.json.

    python plan/pvb_poly_check.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_lib as P                                          # noqa: E402
import p3_r4 as R                                           # noqa: E402
import p3_rl as RL                                          # noqa: E402

PV = P.DATA / "pvb"


def trunc(b, now):
    o, h, l, c, v = (x.copy() for x in b)
    for x in (o, h, l, c):
        x[now:] = np.nan
    v[now:] = 0
    return o, h, l, c, v


def replay(book, d, sym, grid, src):
    f = src / f"{sym}_{d}.csv"
    b = P.read_bars_csv(f, d)
    if b is None:
        return None
    t = P.parse_hhmm(grid)
    st = dict(sym=sym, decision_min=t, entry=None)
    fn = R.watch_exit if book == "r4" else RL.watch_exit
    for now in range(t + 2, P.NMIN + 1):
        if book == "rl" and st.get("entry") is None:
            st["entry"] = float("nan")
        r = fn(d, st, trunc(b, now), now)
        if r and r.get("px") is not None:
            me = st.get("model_entry")
            if me is None or not np.isfinite(me):
                return None
            sh = int(P.TICKET // me)
            return dict(entry=round(me, 4), exit=round(r["px"], 4),
                        exit_min=P.hhmm(r["min"]), reason=r["reason"],
                        gross_10k=round((r["px"] - me) * sh, 2))
    return None


def main():
    S = json.loads((PV / "summary.json").read_text())
    legs = set()
    for d, row in S["r4"]["days"].items():
        for x in row["paper"]:
            if x.get("grid"):
                legs.add(("r4", d, x["sym"], x["grid"]))
        for y in row["A_live"]:
            legs.add(("r4", d, y[0], y[1]))
    for d, row in S["rl"].items():
        for x in row["paper"]:
            legs.add(("rl", d, x[0], x[1]))
        for y in row["bars"]:
            legs.add(("rl", d, y["sym"], y["step"]))
    out = []
    for book, d, sym, g in sorted(legs, key=lambda k: (k[1], k[0], k[3])):
        rh = replay(book, d, sym, g, PV / ("rhx" if book == "r4" else "rh"))
        pg = replay(book, d, sym, g, PV / "poly")
        row = dict(book=book, date=d, sym=sym, grid=g, rh=rh, poly=pg)
        if rh and pg:
            row["diff_gross_10k"] = round(pg["gross_10k"] - rh["gross_10k"], 2)
            row["same_exit"] = (rh["exit_min"], rh["reason"]) == \
                (pg["exit_min"], pg["reason"])
        out.append(row)
        print(book, d, sym, g, "RH", rh and (rh["entry"], rh["exit_min"],
              rh["reason"], rh["exit"], rh["gross_10k"]), "| POLY",
              pg and (pg["entry"], pg["exit_min"], pg["reason"], pg["exit"],
                      pg["gross_10k"]), flush=True)
    both = [r for r in out if r.get("diff_gross_10k") is not None]
    summ = dict(legs=len(out), with_both=len(both),
                same_exit=sum(r["same_exit"] for r in both),
                mean_abs_diff_10k=round(float(np.mean([abs(r["diff_gross_10k"])
                                                       for r in both])), 2)
                if both else None,
                sum_diff_10k=round(sum(r["diff_gross_10k"] for r in both), 2))
    print(summ)
    (PV / "poly_check.json").write_text(json.dumps(dict(summary=summ, legs=out),
                                                   indent=1))


if __name__ == "__main__":
    main()
