"""Ross Cameron (Warrior Trading) style algorithm + HALAL rule, vs ours.

Ross's documented rules (warriortrading.com):
- Scanner: price $2-$20, gap/up >=10%, relative volume >=5x, LOW float,
  breaking-news catalyst; trades ~7:00-11:30 AM, best 9:30-10:30.
- Entry (bull flag / micro pullback): strong up move (flagpole), shallow
  1-3 candle pullback, BUY the break of the prior candle's high; STOP at
  the pullback low.
- Exit: sell HALF into strength at 2:1 reward:risk, move stop to
  breakeven, trail the rest under pullback lows. Flat by 11:30.

Halal rule added on top (user requirement). To isolate the trading STYLE,
both algorithms run on the SAME qualifying day pool (halal + float<=16M +
upward sectors + gap>=10% + rvol>=5x); Ross gets his own band ($2-20) and
window (7:00-11:30), ours keeps $2-16 / 7:00-10:00.

Position: $15,000, 10% bar-volume liquidity cap, one top gapper/day,
5-min bars (his 1-min charts are finer -- noted limitation).
"""

import importlib.util
import json
import sys
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "penny-stocks.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

sys.path.insert(0, str(ROOT / "plan"))
_espec = importlib.util.spec_from_file_location(
    "exp", ROOT / "plan" / "penny_expand_test.py")
exp = importlib.util.module_from_spec(_espec)
_espec.loader.exec_module(exp)
ytd = exp.ytd

CACHE = ROOT / "data" / "backtest60"
BUDGET = 15_000.0
VOL_FRAC = 0.10
MAX_ENTRIES = 5


def ross_sim(df, prev_close, price_max=20.0):
    """Micro pullback / bull flag on 5-min bars, half-out at 2R + trail."""
    cd = ps.Candles(df)
    o, h, l, c, v = cd.o, cd.h, cd.l, cd.c, cd.v
    n = cd.n
    trades = []
    entries = 0
    pos = None   # dict(shares, entry, stop, half_sold, realized)
    session_hi = 0.0
    pole_hi = 0.0
    pull = []    # indices of pullback bars

    def ok(px):
        if not (2.0 <= px <= price_max):
            return False
        if prev_close and px < prev_close * 1.10:
            return False
        return True

    for i in range(1, n):
        if pos is None:
            session_hi = max(session_hi, h[i])
            # flagpole: green bar making a session high
            if c[i] > o[i] and h[i] >= session_hi:
                pole_hi = h[i]
                pull = []
            elif pole_hi > 0:
                # pullback bars: lower highs / red, shallow (<50% of pole)
                if h[i] < pole_hi and len(pull) < 3:
                    pull.append(i)
                    continue
                # entry trigger: break of PRIOR bar's high after 1-3
                # pullback bars
                if pull and h[i] > h[pull[-1]] and entries < MAX_ENTRIES:
                    stop = min(l[j] for j in pull)
                    fill = max(h[pull[-1]], o[i])
                    if ok(fill) and fill > stop:
                        sh = int(BUDGET // fill)
                        if v[i] > 0:
                            sh = min(sh, int(v[i] * VOL_FRAC))
                        if sh >= 1:
                            pos = {"shares": sh, "entry": fill, "stop": stop,
                                   "half": False, "real": 0.0, "ei": i}
                            entries += 1
                            continue
                    pole_hi = 0.0
                    pull = []
        else:
            e_px = pos["entry"]
            risk = e_px - pos["stop"]
            # stop hit (gap-down aware)
            stop_fill = min(o[i], pos["stop"]) if o[i] < pos["stop"] \
                else pos["stop"]
            if l[i] <= pos["stop"]:
                pos["real"] += (stop_fill - e_px) * pos["shares"]
                trades.append(pos["real"])
                pos = None
                session_hi = max(session_hi, h[i])
                pole_hi = 0.0
                pull = []
                continue
            # half out at 2:1 into strength
            if not pos["half"] and h[i] >= e_px + 2 * risk:
                half = pos["shares"] // 2
                tgt = e_px + 2 * risk
                fill = max(tgt, o[i]) if o[i] > tgt else tgt
                pos["real"] += (fill - e_px) * half
                pos["shares"] -= half
                pos["half"] = True
                pos["stop"] = e_px          # breakeven stop on the rest
            # trail: raise stop under each new higher low (green bar)
            if pos["half"] and c[i] > o[i] and l[i] > pos["stop"]:
                pos["stop"] = l[i]
    if pos is not None:
        pos["real"] += (c[n - 1] - pos["entry"]) * pos["shares"]
        trades.append(pos["real"])
    return trades


def main():
    cands = ytd.filter_symbols(
        json.loads((CACHE / "gappers_ytd.json").read_text()))
    by_day = exp.day_pick(cands)

    rows = {"ours": [], "ross": []}
    for date, c in sorted(by_day.items()):
        df = exp.get_full_df(c["symbol"], date)
        if df is None:
            continue
        w_ours = df[(df.index.time >= dtime(7, 0))
                    & (df.index.time < dtime(10, 0))]
        w_ross = df[(df.index.time >= dtime(7, 0))
                    & (df.index.time < dtime(11, 30))]
        if len(w_ours) >= 8:
            tr = ps.simulate_trades(w_ours, verbose=False, buy_set=None,
                                    vol_confirm=False, trail_pct=20,
                                    stop_pct=5, prev_close=c["prev_close"],
                                    budget=BUDGET, orb=True,
                                    max_vol_frac=VOL_FRAC)
            if tr:
                rows["ours"].append(sum(t["pnl"] for t in tr))
        if len(w_ross) >= 8:
            tr = ross_sim(w_ross, c["prev_close"])
            if tr:
                rows["ross"].append(sum(tr))

    print(f"{'ALGORITHM':<34} {'days':>5} {'total P&L':>11} {'avg $/day':>10} "
          f"{'win/day':>9} {'>=+$1k':>6} {'worst':>10}")
    print("-" * 90)
    for name, label in [("ours", "OURS trail20+ORB, 7-10AM"),
                        ("ross", "ROSS-HALAL pullback 2R, 7-11:30")]:
        d = rows[name]
        n = len(d)
        tot = sum(d)
        wins = sum(1 for x in d if x > 0)
        big = sum(1 for x in d if x >= 1000)
        print(f"{label:<34} {n:>5} {tot:>+11.2f} {tot / n if n else 0:>+10.2f} "
              f"{wins:>4}/{n:<4} {big:>6} {min(d) if d else 0:>+10.2f}")


if __name__ == "__main__":
    main()
