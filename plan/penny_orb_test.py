"""Diagnose zero-trade days + test Opening-Range-Breakout (ORB) entries.

Part 1 -- diagnosis: for every qualifying YTD day, replay the gates and
report exactly why no trade happened (thin bars / never in band / never
up 10% at a bar / surge never armed / no dip / no pattern after dip).

Part 2 -- ORB: opening range = first 3 bars (15 min) of the 7-10 AM window
that printed volume; entry = stop-buy when price breaks the OR high while
band + up>=10% gates pass; exits identical to the default (trail 20%,
stop 5%, window-close flatten). Variants compared over the SAME days:
  A. current default (dip-reversal, all patterns)
  B. ORB only
  C. combined: whichever triggers first, both active all day
"""

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("pennystocks",
                                               ROOT / "day-trading.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

CACHE = ROOT / "data" / "backtest60"
IDIR = CACHE / "intraday"

gappers = json.loads((CACHE / "gappers_ytd.json").read_text())


def load_passing():
    sys.path.insert(0, str(ROOT / "plan"))
    spec = importlib.util.spec_from_file_location(
        "ytd", ROOT / "plan" / "penny_backtest_ytd.py")
    ytd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ytd)
    return ytd.filter_symbols(gappers), ytd.get_day_df


def or_breakout_sim(df, prev_close, budget=1000.0, or_bars=3,
                    trail=20.0, stop=5.0, combined=False):
    """ORB entry (+ optional dip-reversal combined) with trailing exits."""
    cd = ps.Candles(df)
    o, h, l, c, idx = cd.o, cd.h, cd.l, cd.c, cd.index
    n = cd.n
    # opening range: first or_bars bars WITH volume
    vol_bars = [i for i in range(n) if cd.v[i] > 0][:or_bars]
    if len(vol_bars) < or_bars:
        return []
    or_high = max(h[i] for i in vol_bars)
    or_end = vol_bars[-1]

    trades = []
    state = "FLAT"
    entry = peak = 0.0
    entry_i = -1
    shares = 0
    cash = budget
    # dip-machine state (combined mode)
    dstate = "SCAN"
    surge_high = 0.0

    def gates(px):
        if not (ps.PRICE_MIN <= px <= ps.PRICE_MAX):
            return False
        if prev_close and px < prev_close * (1 + ps.MIN_DAY_GAIN_PCT / 100):
            return False
        return True

    for i in range(1, n):
        px = c[i]
        if state == "FLAT":
            fill = None
            tag = ""
            # ORB: break of opening-range high (stop order semantics)
            if i > or_end and h[i] > or_high:
                cand = max(or_high, o[i])
                if gates(cand):
                    fill, tag = cand, "ORB"
                or_high = max(or_high, h[i])   # ratchet: next break higher
            # dip-reversal machine (combined mode only)
            if combined and fill is None:
                if dstate == "SCAN":
                    j = max(0, i - ps.SURGE_WINDOW_MIN)
                    lo_w = min(l[j:i + 1])
                    if lo_w > 0 and (h[i] / lo_w - 1) * 100 >= ps.SURGE_PCT:
                        dstate = "DIPPING"
                        surge_high = h[i]
                elif dstate == "DIPPING":
                    surge_high = max(surge_high, h[i])
                    if surge_high - px >= ps.DIP_MIN_CENTS:
                        dstate = "ARMED"
                elif dstate == "ARMED":
                    if h[i] > surge_high:
                        surge_high = h[i]
                        dstate = "DIPPING"
                    else:
                        pats = (cd.bullish_patterns(i)
                                + cd.indicator_bullish(i))
                        if pats and gates(px):
                            fill, tag = px, f"dip:{pats[0]}"
            if fill is not None:
                shares = int(cash // fill)
                if shares >= 1:
                    cash -= shares * fill
                    entry = peak = fill
                    entry_i = i
                    state = "LONG"
                    trades.append({"entry_time": idx[i], "entry": fill,
                                   "tag": tag, "pnl": 0.0, "open": True})
        else:
            peak = max(peak, h[i])
            trail_px = peak * (1 - trail / 100)
            stop_px = max(entry * (1 - stop / 100), trail_px)
            if l[i] <= stop_px and i > entry_i:
                fill = min(stop_px, o[i]) if o[i] < stop_px else stop_px
                cash += shares * fill
                trades[-1].update(pnl=(fill - entry) * shares, open=False)
                shares = 0
                state = "FLAT"
                dstate = "SCAN"
    if state == "LONG":
        fill = c[n - 1]
        cash += shares * fill
        trades[-1].update(pnl=(fill - entry) * shares, open=False)
    return trades


def diagnose(df, prev_close):
    """Why would the default dip-reversal take zero trades?"""
    cd = ps.Candles(df)
    n = cd.n
    if n < 8:
        return "thin window (<8 bars)"
    in_band = [i for i in range(n)
               if ps.PRICE_MIN <= cd.c[i] <= ps.PRICE_MAX]
    if not in_band:
        return (f"never in $2-16 band (range "
                f"{min(cd.l):.2f}-{max(cd.h):.2f})")
    up10 = [i for i in in_band
            if not prev_close
            or cd.c[i] >= prev_close * (1 + ps.MIN_DAY_GAIN_PCT / 100)]
    if not up10:
        mx = max(cd.c[i] for i in in_band)
        need = prev_close * 1.1 if prev_close else 0
        return (f"in band but never up 10% at a bar close "
                f"(max in-band close {mx:.2f} < needed {need:.2f} "
                f"-- prev_close {prev_close})")
    # surge armed?
    armed = False
    for i in range(1, n):
        j = max(0, i - ps.SURGE_WINDOW_MIN)
        lo_w = min(cd.l[j:i + 1])
        if lo_w > 0 and (cd.h[i] / lo_w - 1) * 100 >= ps.SURGE_PCT:
            armed = True
            break
    if not armed:
        return "surge never armed (+2% in window never happened)"
    pats_any = any((cd.bullish_patterns(i) + cd.indicator_bullish(i))
                   for i in up10)
    if not pats_any:
        return "no bullish pattern formed at an eligible bar"
    return "gates pass individually -- sequencing (dip/pattern timing) missed"


def main():
    final, get_day_df = load_passing()
    by_day = {}
    for cnd in final:
        if (cnd["date"] not in by_day
                or cnd["gain_pct"] > by_day[cnd["date"]]["gain_pct"]):
            by_day[cnd["date"]] = cnd

    tot = {"A": 0.0, "B": 0.0, "C": 0.0}
    ntr = {"A": 0, "B": 0, "C": 0}
    zero_diag = []
    print(f"{'date':<12}{'sym':<7}{'A dflt':>9} {'B ORB':>9} {'C both':>9}")
    print("-" * 50)
    for date in sorted(by_day):
        cnd = by_day[date]
        df = get_day_df(cnd["symbol"], date)
        if df is None:
            continue
        prev = cnd["prev_close"]
        a = ps.simulate_trades(df, verbose=False, buy_set=None,
                               vol_confirm=False, trail_pct=20, stop_pct=5,
                               prev_close=prev)
        b = or_breakout_sim(df, prev, combined=False)
        cmb = or_breakout_sim(df, prev, combined=True)
        pa = sum(t["pnl"] for t in a)
        pb = sum(t["pnl"] for t in b)
        pc = sum(t["pnl"] for t in cmb)
        tot["A"] += pa
        tot["B"] += pb
        tot["C"] += pc
        ntr["A"] += len(a)
        ntr["B"] += len(b)
        ntr["C"] += len(cmb)
        flag = ""
        if not a:
            reason = diagnose(df, prev)
            zero_diag.append((date, cnd["symbol"], cnd["gain_pct"], reason))
            flag = "  <-- zero-trade day"
        print(f"{date:<12}{cnd['symbol']:<7}{pa:>+9.2f} {pb:>+9.2f} "
              f"{pc:>+9.2f}{flag}")

    print(f"\n{'=' * 58}")
    print(f"  A default:  {ntr['A']:>3} trades  ${tot['A']:>+10.2f}")
    print(f"  B ORB only: {ntr['B']:>3} trades  ${tot['B']:>+10.2f}")
    print(f"  C combined: {ntr['C']:>3} trades  ${tot['C']:>+10.2f}")

    print(f"\n  ZERO-TRADE DAY DIAGNOSIS ({len(zero_diag)} days):")
    for date, sym, gain, reason in zero_diag:
        print(f"  {date} {sym:<6} +{gain:>6.1f}%  {reason}")


if __name__ == "__main__":
    main()
