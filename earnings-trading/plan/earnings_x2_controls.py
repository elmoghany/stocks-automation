"""Controls for the EARNINGS-X2 B-family (pre-earnings run-up):
last year was a bull tape, so a multi-session long hold earns market
drift no matter the catalyst. Two tests decide whether ET22/ET28 are an
earnings edge or beta:

  ET32 SPY-ADJUST: per event, subtract SPY's return over the same
       session window (lag entry -> last close pre-release).
  ET33 PLACEBO WINDOW: same symbols, same 5-session hold, but ending
       ~21 sessions BEFORE the release (mid-quarter, no catalyst),
       with the same strong+fin gate as ET28. If the placebo matches
       ET28's excess return, the "pre-earnings run-up" is just how
       these names drift, and the strategy is really momentum-beta.

Uses the cached events (earnings_x2_events.json) for dates/gates and
refetches daily closes per symbol (one yfinance call each).
"""

import json
import sys
import time
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
EV_C = ROOT / "data/earnings_x2_events.json"
LAG = 5


def main():
    events = json.loads(EV_C.read_text())
    spy = yf.Ticker("SPY").history(period="2y", auto_adjust=True)["Close"]
    spy.index = spy.index.tz_localize(None)
    sidx = spy.index

    by_sym = {}
    for e in events:
        if e.get(f"lag{LAG}"):
            by_sym.setdefault(e["sym"], []).append(e)

    rows = {"ET22_raw": [], "ET22_xs": [], "ET28_raw": [], "ET28_xs": [],
            "ET33_placebo_raw": [], "ET33_placebo_xs": []}
    for n, (sym, evs) in enumerate(sorted(by_sym.items())):
        try:
            h = yf.Ticker(sym).history(period="2y", auto_adjust=True)
            closes = h["Close"]
            closes.index = closes.index.tz_localize(None)
        except Exception:
            continue
        idx = closes.index
        for e in evs:
            post = pd.Timestamp(e["date"])
            if post not in idx:
                continue
            p = idx.get_loc(post)
            if p - LAG - 1 < 0:
                continue
            pre_i, ent_i = p - 1, p - 1 - LAG
            r = (closes.iloc[pre_i] / closes.iloc[ent_i] - 1) * 100
            # SPY over the same dates
            d0, d1 = idx[ent_i], idx[pre_i]
            s0 = spy[sidx <= d0]
            s1 = spy[sidx <= d1]
            if len(s0) == 0 or len(s1) == 0:
                continue
            m = (s1.iloc[-1] / s0.iloc[-1] - 1) * 100
            rows["ET22_raw"].append(r)
            rows["ET22_xs"].append(r - m)
            if e["strong"] and e["fin"]:
                rows["ET28_raw"].append(r)
                rows["ET28_xs"].append(r - m)
                # placebo: same-length hold ending 21 sessions earlier
                if p - 22 - LAG >= 0:
                    q_pre, q_ent = p - 22, p - 22 - LAG
                    pr = (closes.iloc[q_pre] / closes.iloc[q_ent] - 1) * 100
                    pd0, pd1 = idx[q_ent], idx[q_pre]
                    ps0, ps1 = spy[sidx <= pd0], spy[sidx <= pd1]
                    if len(ps0) and len(ps1):
                        pm = (ps1.iloc[-1] / ps0.iloc[-1] - 1) * 100
                        rows["ET33_placebo_raw"].append(pr)
                        rows["ET33_placebo_xs"].append(pr - pm)
        if n % 25 == 0:
            print(f"  {n}/{len(by_sym)}", flush=True)
        time.sleep(0.1)

    print()
    for k, v in rows.items():
        if not v:
            print(f"{k:<18} n=0")
            continue
        n_ = len(v)
        win = 100 * sum(1 for x in v if x > 0) / n_
        avg = sum(v) / n_
        print(f"{k:<18} n={n_:>4} win={win:5.1f}% avg={avg:+.3f}%"
              f"  tot(15k)=${sum(15000 * x / 100 for x in v):+,.0f}")
    (ROOT / "data/earnings_x2_controls.json").write_text(json.dumps(
        {k: [round(x, 3) for x in v] for k, v in rows.items()}))


if __name__ == "__main__":
    main()
