"""PAPER-VS-BT, book RL: the RL backtest engine (plan/p3_rl.Engine, CFG_LIVE:
one position, $10k whole shares, <= 7 entries, 09:30-15:55, 15:59 flatten)
over the 11 paper days, three ways:

  bars   full-universe 1-minute RTH bars fetched after the fact (Robinhood
         get_equity_historicals, data/pvb/rh; all 95 names x 11 days).
         VWAP therefore starts 09:30, not 04:00 (rules: 0/87 entries change).
  saved  the live session's own inputs: scan snapshots + its rh_bars
         (p3_rl.SnapSrc), replayed end-of-day.
  paper  the live engine's state file data/paper/rl/state_{D}.json (its
         model trades and per-step breadth) and the official ledger fills.

Writes data/pvb/rl_compare.json and prints a per-day summary.

    python plan/pvb_rl.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_lib as P                                            # noqa: E402
import p3_rl as RL                                            # noqa: E402

DAYS = ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09",
        "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16",
        "2026-10-19"]
RHD = P.DATA / "pvb" / "rh"
COST = 6.0          # RL realistic cost, bps/side (p3_expectations)


def bars_src(date, syms, d=RHD):
    nan = np.full(P.NMIN, np.nan)
    arr = [[], [], [], [], []]
    miss = []
    for s in syms:
        b = P.read_bars_csv(d / f"{s}_{date}.csv", date)
        if b is None:
            miss.append(s)
        for k in range(5):
            arr[k].append(b[k] if b is not None else
                          (np.zeros(P.NMIN) if k == 4 else nan))
    return RL.BarSrc(syms, *[np.vstack(a) for a in arr]), miss


def net(t, bps=COST):
    return t["gross"] - (t["px_in"] + t["px_out"]) * t["sh"] * bps / 1e4


def run(src, syms):
    eng = RL.Engine(RL.CFG_LIVE, syms)
    eng.advance(src, P.NMIN)
    tr = [dict(sym=t["sym"], step=P.hhmm(t["step_in"]), fill=P.hhmm(t["m_in"]),
               px_in=round(t["px_in"], 4), sh=t["sh"],
               out=P.hhmm(t["m_out"]), px_out=round(t["px_out"], 4),
               reason=t["reason"], gross=round(t["gross"], 2),
               net6=round(net(t), 2)) for t in eng.st["trades"]]
    feat = eng.st.get("feat", {})
    return tr, feat


def main():
    syms = RL.universe_syms()
    out = {}
    for d in DAYS:
        src, miss = bars_src(d, syms)
        tb, fb = run(src, syms)
        ssrc = RL.SnapSrc(d, P.NMIN, syms)
        ts, fs = run(ssrc, syms)
        st = P.read_json(P.book_dir("rl") / f"state_{d}.json", {}) or {}
        fl = st.get("feat", {})
        tl = [dict(sym=t["sym"], step=P.hhmm(t["step_in"]),
                   px_in=round(t["px_in"], 4), sh=t["sh"],
                   out=P.hhmm(t["m_out"]), px_out=round(t["px_out"], 4),
                   reason=t["reason"], gross=round(t["gross"], 2))
              for t in st.get("trades", [])]
        # breadth agreement, bars vs live state, per step
        diffs, minb, minl = [], None, None
        for k, v in fb.items():
            if k in fl:
                diffs.append(abs(v["br"] - fl[k]["br"]))
        brb = {k: v["br"] for k, v in fb.items()}
        brl = {k: v["br"] for k, v in fl.items()}
        if brb:
            k = min(brb, key=brb.get)
            minb = (k, brb[k])
        if brl:
            k = min(brl, key=brl.get)
            minl = (k, brl[k])
        below_b = sorted(k for k, v in brb.items() if v < float(RL.BR_T))
        below_l = sorted(k for k, v in brl.items() if v < float(RL.BR_T))
        out[d] = dict(bars_trades=tb, saved_trades=ts, live_state_trades=tl,
                      missing_bars=miss,
                      breadth_absdiff_mean=round(float(np.mean(diffs)), 5)
                      if diffs else None,
                      breadth_absdiff_max=round(float(np.max(diffs)), 5)
                      if diffs else None,
                      min_breadth_bars=minb, min_breadth_live=minl,
                      steps_below_gate_bars=below_b,
                      steps_below_gate_live=below_l,
                      steps_bars=len(fb), steps_live=len(fl))
        print(d, "bars", [(t["sym"], t["step"], t["out"], t["reason"],
                           t["net6"]) for t in tb],
              "| saved", [(t["sym"], t["step"], t["out"]) for t in ts],
              "| live", [(t["sym"], t["step"], t["out"]) for t in tl],
              "| br min bars", minb, "live", minl,
              "| absdiff mean/max", out[d]["breadth_absdiff_mean"],
              out[d]["breadth_absdiff_max"], "| miss", len(miss), flush=True)
    (P.DATA / "pvb" / "rl_compare.json").write_text(
        json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
