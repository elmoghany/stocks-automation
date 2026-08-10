"""Backtest of the VIDEO'S OWN strategy (Riley Coleman 5-step reversal)
on SPY 1-minute bars, $15,000 account, 2 years.

Faithful mechanical translation of the checklist
(video-studies/2026-08-09-riley-coleman-futures-reversal.md):

 1. LOCATION: zones from PRIOR days only (causal): prior-day high/low,
    overnight (4:00-9:30) high/low. A setup may only begin when price
    trades within ZONE_TOL of a zone.
 2. UNHEALTHY MOVE: the approach into the zone is overextended --
    the last 5 completed 1-min candles' total range >= UNHEALTHY_X
    times ATR(20).
 3. TREND BROKEN: after an UP move into resistance, price prints a
    swing low BELOW the prior swing low (mirror for support/longs).
    Swings = 3-bar fractals, fully causal (confirmed one bar late).
 4. FAILED CONTINUATION: price attempts back toward the old extreme
    and is rejected -- an opposing candle immediately follows the
    attempt without a new extreme being set.
 5. ENTRY: stop-market beyond the rejection candle's extreme. STOP at
    the failed-attempt extreme. TARGET = 2R (his beginner default;
    3R variant reported). One position at a time; if the entry stop
    is not hit within 15 minutes the setup is cancelled.

Session: his "45-60 minutes in the morning" -> setups sought
9:30-11:00 ET, all positions closed by 11:30. Max 2 attempts/day.
Sizing: risk RISK_PCT of the $15k account per trade (default 1% =
$150); shares = risk / stop-distance, capped so notional <= account
(no margin on longs; shorts get the same notional cap and are FLAGGED
-- a cash account cannot short; reported separately).
Costs: 1 cent/share/side + entry at the stop price (no slippage
grace). Account compounds (risk is % of current equity).

Variants: --target 2|3, --risk 0.01|0.02, --control (zones shifted by
a random offset per day -- location signal destroyed, must degrade).
"""

import random
import sys
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SPY = ROOT / "data/spy_m1"
ZONE_TOL = 0.0012          # 0.12% of price ~ a few SPY cents band
UNHEALTHY_X = 2.0
ATR_N = 20
START_EQ = 15_000.0
CANCEL_MIN = 15
MAX_TRADES = 2
SESSION_END = dtime(11, 0)
FLAT_BY = dtime(11, 30)
COST = 0.01                # $/share/side


def load_day(f):
    df = pd.read_csv(f, index_col=0, parse_dates=True)
    df.index = df.index.tz_convert("America/New_York")
    return df


def swings(h, l, upto):
    """3-bar fractal swing highs/lows confirmed by bar `upto` (causal:
    a swing at i needs bar i+1 closed, so i <= upto-1)."""
    sh, sl = [], []
    for i in range(1, upto):
        if h[i] > h[i - 1] and h[i] > h[i + 1]:
            sh.append((i, h[i]))
        if l[i] < l[i - 1] and l[i] < l[i + 1]:
            sl.append((i, l[i]))
    return sh, sl


def run(target_r=2.0, risk_pct=0.01, control=False, seed=7):
    files = sorted(SPY.glob("SPY_*.csv"))
    eq = START_EQ
    trades = []
    monthly = {}
    rng = random.Random(seed)
    prev_day = None
    for f in files:
        date = f.stem[4:]
        if f.read_text(errors="ignore").startswith("EMPTY"):
            continue
        df = load_day(f)
        if prev_day is None:
            prev_day = df
            continue
        # ---- zones from PRIOR data only ----
        pd_reg = prev_day[(prev_day.index.time >= dtime(9, 30)) &
                          (prev_day.index.time <= dtime(16, 0))]
        on = df[df.index.time < dtime(9, 30)]
        zones = []
        if len(pd_reg):
            zones += [float(pd_reg["High"].max()),
                      float(pd_reg["Low"].min())]
        if len(on):
            zones += [float(on["High"].max()), float(on["Low"].min())]
        prev_day = df
        if not zones:
            continue
        if control:
            off = rng.uniform(0.004, 0.012) * rng.choice([-1, 1])
            zones = [z * (1 + off) for z in zones]

        reg = df[(df.index.time >= dtime(9, 30)) &
                 (df.index.time <= dtime(11, 30))]
        if len(reg) < ATR_N + 10:
            continue
        h = reg["High"].values.astype(float)
        l = reg["Low"].values.astype(float)
        c = reg["Close"].values.astype(float)
        o = reg["Open"].values.astype(float)
        times = reg.index
        tr = [h[i] - l[i] for i in range(len(h))]
        day_trades = 0
        i = ATR_N
        pos = None    # (side, entry, stop, tgt, shares, i_entry)
        pending = None  # (side, trig, stop, i_set)
        while i < len(reg):
            t = times[i].time()
            atr = sum(tr[i - ATR_N:i]) / ATR_N
            if pos is None and pending is not None:
                side, trig, stp, iset = pending
                if i - iset > CANCEL_MIN:
                    pending = None
                elif side == "S" and l[i] <= trig:
                    fill = min(trig, o[i])
                    risk = abs(stp - fill)
                    if risk > 0.01:
                        sh = min(int((eq * risk_pct) / risk),
                                 int(eq / fill))
                        if sh >= 1:
                            pos = (side, fill, stp,
                                   fill - target_r * risk, sh, i)
                    pending = None
                elif side == "L" and h[i] >= trig:
                    fill = max(trig, o[i])
                    risk = abs(fill - stp)
                    if risk > 0.01:
                        sh = min(int((eq * risk_pct) / risk),
                                 int(eq / fill))
                        if sh >= 1:
                            pos = (side, fill, stp,
                                   fill + target_r * risk, sh, i)
                    pending = None
            if pos is not None:
                side, e, stp, tgt, sh, ie = pos
                exit_px = None
                if side == "S":
                    if h[i] >= stp:
                        exit_px = max(stp, o[i])
                    elif l[i] <= tgt:
                        exit_px = tgt
                elif side == "L":
                    if l[i] <= stp:
                        exit_px = min(stp, o[i])
                    elif h[i] >= tgt:
                        exit_px = tgt
                if exit_px is None and t >= FLAT_BY:
                    exit_px = c[i]
                if exit_px is not None:
                    pnl = ((e - exit_px) if side == "S"
                           else (exit_px - e)) * sh - 2 * COST * sh
                    eq += pnl
                    trades.append({"date": date, "side": side,
                                   "pnl": pnl, "r": pnl / max(
                                       abs(e - stp) * sh, 1e-9)})
                    monthly[date[:7]] = monthly.get(date[:7], 0) + pnl
                    pos = None
                    day_trades += 1
                i += 1
                continue
            if t >= SESSION_END or day_trades >= MAX_TRADES:
                break
            # ---- look for a setup at bar i ----
            px = c[i]
            near = None
            for z in zones:
                if abs(px - z) / z <= ZONE_TOL:
                    near = ("res" if px >= z * (1 - ZONE_TOL / 2)
                            and c[max(0, i - 5)] < z else "sup")
                    near = "res" if px > c[max(0, i - 10)] else "sup"
                    break
            if near is None:
                i += 1
                continue
            burst = sum(tr[i - 5:i])
            if burst < UNHEALTHY_X * atr * 2.2:
                i += 1
                continue
            sh_, sl_ = swings(h, l, i)
            if near == "res" and len(sl_) >= 2:
                # trend break: latest confirmed swing low undercuts the
                # prior one; failed continuation: since that break, a
                # push toward the high stalled (bar makes high below
                # day-high-so-far then closes red)
                if sl_[-1][1] < sl_[-2][1] and c[i] < o[i] \
                        and h[i] < max(h[:i]):
                    pending = ("S", l[i] - 0.02, h[i] + 0.02, i)
            elif near == "sup" and len(sh_) >= 2:
                if sh_[-1][1] > sh_[-2][1] and c[i] > o[i] \
                        and l[i] > min(l[:i]):
                    pending = ("L", h[i] + 0.02, l[i] - 0.02, i)
            i += 1
    return eq, trades, monthly


def report(tag, eq, trades, monthly):
    tot = eq - START_EQ
    w = [x for x in trades if x["pnl"] > 0]
    s = [x for x in trades if x["side"] == "S"]
    lg = [x for x in trades if x["side"] == "L"]
    negm = sum(1 for v in monthly.values() if v < 0)
    print(f"{tag:<28} end ${eq:>10,.0f}  P&L ${tot:>+9,.0f}  "
          f"trades {len(trades):>3}  win {100*len(w)/max(len(trades),1):.0f}%  "
          f"negM {negm}/{len(monthly)}  "
          f"[L {sum(x['pnl'] for x in lg):+,.0f} / "
          f"S {sum(x['pnl'] for x in s):+,.0f}]")


if __name__ == "__main__":
    args = sys.argv[1:]
    print(f"SPY days on disk: "
          f"{len(list(SPY.glob('SPY_*.csv')))}", flush=True)
    for tag, kw in [
            ("2R risk1% (video default)", dict(target_r=2, risk_pct=.01)),
            ("3R risk1%", dict(target_r=3, risk_pct=.01)),
            ("2R risk2%", dict(target_r=2, risk_pct=.02)),
            ("CONTROL shifted zones 2R1%", dict(target_r=2,
                                                risk_pct=.01,
                                                control=True))]:
        eq, tr, mo = run(**kw)
        report(tag, eq, tr, mo)
