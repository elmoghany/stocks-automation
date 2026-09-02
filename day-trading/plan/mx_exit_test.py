"""MX-series (2026-09-02) -- proofs for the mean-reversion entry and the
TA sell triggers added to day-trading.py::simulate_trades.

fillmodel_test.py-style: synthetic tapes with a KNOWN expected bar, then
the poison (causality) harness on real days. Exits non-zero on failure.

  1. market_at_start: the entry is the OPEN of the first bar whose time
     >= entry_start (+10bps), tagged 'market-at-start'; nothing else
     fires; with no TA rule the only exit is the window-close flatten;
     entry_cutoff / max_trades are honoured; identity: with
     entry_mode='triggers' the tape's ORB entry is unchanged.
  2. vwap_exit: exits at the close of the first post-entry bar that
     closes below session VWAP (typical-price, 09:30 anchor) AFTER a
     post-entry bar closed above it; a tape that never closes above
     VWAP after entry does NOT exit (flatten only).
  3. rsi_exit=(14,70): exit bar == first i>entry with RSI[i-1] > 70 >=
     RSI[i], RSI recomputed independently here.
  4. macd_exit: exit bar == first i>entry with (macd-sig)[i-1] >= 0 >
     (macd-sig)[i].
  5. rand_exit=(30, tag): hold in [1,30] minutes, exit at the first bar
     >= entry + hold, reproducible for the same tag, different across
     tags.
  6. target_pct 5 with trail off: fixed take-profit fills through the
     gap-aware limit fill (max(target, Open), clamped).
  7. CAUSALITY: poison harness over real days with the MX kwarg sets
     (V, R, M, VB): every trade closed before the cut is byte-identical.

Usage: HALAL_STRICT=1 PT_FILED=1 POOL_HYGIENE=1 python plan/mx_exit_test.py
"""
import sys
from datetime import time as dtime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plan"))
import rotation_sim as rs                      # noqa: E402  (loads dt)

dt = rs.dt
SLIP = 0.001
BUD = 15_000.0
HOLD = dict(rs.EXIT_HOLD)
BASE = dict(verbose=False, max_trades=1, slippage_bps=10.0,
            entry_mode="market_at_start", entry_start=dtime(10, 0),
            halt_aware=False, **HOLD)


def tape(closes, start="2025-01-06 07:00", vol=50_000):
    """1-min bars from `closes`: Open = previous close, H/L bracket."""
    idx = pd.date_range(start, periods=len(closes), freq="1min",
                        tz="America/New_York")
    c = np.asarray(closes, dtype=float)
    o = np.concatenate(([c[0]], c[:-1]))
    h = np.maximum(o, c) * 1.002
    lo = np.minimum(o, c) * 0.998
    return pd.DataFrame({"Open": o, "High": h, "Low": lo, "Close": c,
                         "Volume": float(vol)}, index=idx)


def _i(df, hh, mm):
    return int(np.where(df.index.time == dtime(hh, mm))[0][0])


def t_market_at_start():
    n = 60 * 6                      # 07:00 .. 12:59
    df = tape([10.0] * n)
    tr = dt.simulate_trades(df, budget=BUD, **BASE)
    assert len(tr) == 1, tr
    t = tr[0]
    i0 = _i(df, 10, 0)
    assert t["entry_time"] == df.index[i0], t
    assert abs(t["entry"] - round(df["Open"].iloc[i0] * (1 + SLIP), 2)) < 1e-9, t
    assert t["trig"] == "market-at-start" and t["reason"] == "window-close flatten", t
    assert t["exit_time"] == df.index[-1], t
    # entry_cutoff before entry_start -> no entry at all
    assert dt.simulate_trades(df, budget=BUD, **dict(BASE, entry_cutoff=dtime(9, 0))) == []
    # halt-aware: a 5-min tape gap right at 10:00 defers the entry
    dfh = df.drop(df.index[i0:i0 + 5])
    trh = dt.simulate_trades(dfh, budget=BUD, **dict(BASE, halt_aware=True))
    assert trh and trh[0]["entry_time"].time() == dtime(10, 6), trh
    # identity: triggers mode on the same tape is untouched by entry_mode
    kw_trig = dict(BASE, entry_mode="triggers", orb=True, orb_bars=3)
    a = dt.simulate_trades(df, budget=BUD, **kw_trig)
    b = dt.simulate_trades(df, budget=BUD, **{k: v for k, v in kw_trig.items()
                                              if k != "entry_mode"})
    assert a == b, (a, b)
    print(f"  market_at_start: entry {t['entry_time']:%H:%M} @{t['entry']} "
          f"(open {df['Open'].iloc[i0]}), flatten {t['exit_time']:%H:%M}, "
          f"halt-deferred entry 10:06  OK")


def _vwap(df, anchor=dtime(9, 30)):
    m = df.index.time >= anchor
    tp = (df["High"] + df["Low"] + df["Close"]).values / 3.0
    v = df["Volume"].values
    out = np.full(len(df), np.nan)
    s = np.where(m)[0][0]
    pv = np.cumsum((tp * v)[s:])
    vv = np.cumsum(v[s:])
    out[s:] = pv / vv
    return out


def t_vwap():
    n = 60 * 6
    closes = [10.0] * n
    i0 = 180                       # 10:00
    for k in range(i0, i0 + 20):   # ride above VWAP
        closes[k] = 10.0 + 0.05 * (k - i0 + 1)
    for k in range(i0 + 20, n):    # collapse below it
        closes[k] = 9.0
    df = tape(closes)
    tr = dt.simulate_trades(df, budget=BUD, **dict(BASE, vwap_exit=True))
    vw = _vwap(df)
    c = df["Close"].values
    above = False
    exp = None
    for i in range(i0 + 1, n):
        if c[i - 1] > vw[i - 1]:
            above = True
        if above and c[i] < vw[i]:
            exp = i
            break
    assert exp is not None
    assert len(tr) == 1 and tr[0]["reason"].startswith("vwap-cross"), tr
    assert tr[0]["exit_time"] == df.index[exp], (tr[0]["exit_time"], df.index[exp])
    assert abs(tr[0]["exit"] - round(c[exp], 2)) < 1e-9, tr
    # never above VWAP after entry -> no vwap exit, flatten only
    closes2 = [10.0] * n
    for k in range(i0, n):
        closes2[k] = 9.5
    tr2 = dt.simulate_trades(tape(closes2), budget=BUD,
                             **dict(BASE, vwap_exit=True))
    assert len(tr2) == 1 and tr2[0]["reason"] == "window-close flatten", tr2
    print(f"  vwap_exit: exit bar {df.index[exp]:%H:%M} @{tr[0]['exit']} "
          f"(vwap {vw[exp]:.3f}); below-VWAP tape holds to flatten  OK")


def _rsi(c, period=14):
    s = pd.Series(c)
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    l = (-d).clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    return (100 - 100 / (1 + g / l)).values


def t_rsi():
    n = 60 * 6
    i0 = 180
    closes = [10.0] * n
    for k in range(i0, i0 + 25):
        closes[k] = 10.0 + 0.02 * (k - i0 + 1)     # RSI -> ~100
    for k in range(i0 + 25, n):
        closes[k] = closes[k - 1] - 0.03           # RSI falls through 70
    df = tape(closes)
    r = _rsi(df["Close"].values)
    exp = next(i for i in range(i0 + 1, n) if r[i - 1] > 70 >= r[i])
    tr = dt.simulate_trades(df, budget=BUD, **dict(BASE, rsi_exit=(14, 70)))
    assert len(tr) == 1 and tr[0]["reason"].startswith("rsi-cross"), tr
    assert tr[0]["exit_time"] == df.index[exp], (tr[0]["exit_time"], df.index[exp])
    assert abs(tr[0]["exit"] - round(closes[exp], 2)) < 1e-9, tr
    print(f"  rsi_exit(14,70): exit bar {df.index[exp]:%H:%M} "
          f"(rsi {r[exp-1]:.1f} -> {r[exp]:.1f})  OK")


def _macd(c):
    s = pd.Series(c)
    m = s.ewm(span=12, adjust=False).mean() - s.ewm(span=26, adjust=False).mean()
    return (m - m.ewm(span=9, adjust=False).mean()).values


def t_macd():
    n = 60 * 6
    i0 = 180
    closes = [10.0] * n
    for k in range(i0 - 30, i0 + 15):
        closes[k] = closes[k - 1] + 0.02
    for k in range(i0 + 15, n):
        closes[k] = closes[k - 1] - 0.02
    df = tape(closes)
    h = _macd(df["Close"].values)
    exp = next(i for i in range(i0 + 1, n) if h[i - 1] >= 0 > h[i])
    tr = dt.simulate_trades(df, budget=BUD, **dict(BASE, macd_exit=True))
    assert len(tr) == 1 and tr[0]["reason"] == "macd-cross", tr
    assert tr[0]["exit_time"] == df.index[exp], (tr[0]["exit_time"], df.index[exp])
    print(f"  macd_exit: exit bar {df.index[exp]:%H:%M} "
          f"(hist {h[exp-1]:+.4f} -> {h[exp]:+.4f})  OK")


def t_rand_exit():
    n = 60 * 6
    df = tape([10.0] * n)
    holds = set()
    for tag in ("mxs-0", "mxs-1", "mxs-2", "mxs-3"):
        tr = dt.simulate_trades(df, budget=BUD,
                                **dict(BASE, rand_exit=(30, tag)))
        tr2 = dt.simulate_trades(df, budget=BUD,
                                 **dict(BASE, rand_exit=(30, tag)))
        assert tr == tr2, "rand_exit not reproducible"
        assert len(tr) == 1 and tr[0]["reason"].startswith("rand-exit"), tr
        hold = int(tr[0]["reason"].split()[1][:-1])
        assert 1 <= hold <= 30, hold
        mins = (tr[0]["exit_time"] - tr[0]["entry_time"]).total_seconds() / 60
        assert mins == hold, (mins, hold)
        holds.add(hold)
    assert len(holds) > 1, "all tags drew the same hold"
    print(f"  rand_exit(30): holds {sorted(holds)} minutes, reproducible  OK")


def t_target():
    n = 60 * 6
    i0 = 180
    closes = [10.0] * n
    closes[i0 + 10] = 10.9            # bar gaps up through +5% (open 10.0)
    for k in range(i0 + 11, n):
        closes[k] = 10.9
    df = tape(closes)
    df.iloc[i0 + 10, df.columns.get_loc("Open")] = 10.8   # opens above target
    df.iloc[i0 + 10, df.columns.get_loc("Low")] = 10.75
    kw = dict(BASE, trail_pct=None, stop_pct=99, target_pct=5.0)
    tr = dt.simulate_trades(df, budget=BUD, **kw)
    assert len(tr) == 1 and tr[0]["reason"].startswith("target"), tr
    assert tr[0]["exit_time"] == df.index[i0 + 10]
    assert abs(tr[0]["exit"] - 10.8) < 1e-9, ("gap-up target must fill at "
                                              "the open 10.8", tr[0])
    print(f"  target_pct 5: gap-up bar fills at the open {tr[0]['exit']}  OK")


def _key(t):
    return (str(t["entry_time"]), t["entry"], str(t["exit_time"]),
            t["exit"], t["reason"], t["pnl"], t.get("shares"))


def poison(df, pc, kw, step=3):
    w = df[(df.index.time >= dtime(7, 0)) & (df.index.time < dtime(12, 0))]
    w = w.astype(float)
    clean = dt.simulate_trades(w, prev_close=pc, budget=BUD, **kw)
    if not clean:
        return 0, 0
    first = w.index.get_loc(clean[0]["entry_time"])
    breaches = tested = 0
    cols = ["Open", "High", "Low", "Close", "Volume"]
    for cut in range(first + 1, len(w), step):
        for val in (9e9, 1e-9):
            p = w.copy()
            p.iloc[cut:, [p.columns.get_loc(c) for c in cols]] = val
            tr = dt.simulate_trades(p, prev_close=pc, budget=BUD, **kw)
            lim = w.index[cut]
            a = [_key(t) for t in clean if t["exit_time"] < lim]
            b = [_key(t) for t in tr if t["exit_time"] < lim]
            tested += 1
            if a != b:
                breaches += 1
    return breaches, tested


def causality():
    days = [("TWG", "2025-09-11", 5.02), ("WFF", "2025-09-11", None),
            ("HSDT", "2025-06-11", None), ("BTCT", "2024-11-13", None),
            ("PCSA", "2025-06-17", None), ("NAMM", "2026-01-22", None),
            ("BNAI", "2026-06-05", None), ("SKYQ", "2026-04-02", None)]
    sets = {"V": rs.MX_EXIT["V"], "R": rs.MX_EXIT["R"], "M": rs.MX_EXIT["M"],
            "VB": rs.MX_EXIT["VB"], "P": rs.MX_EXIT["P"]}
    tot = n_all = 0
    for sym, date, pc in days:
        df = rs.bars_for(sym, date)
        if df is None:
            continue
        line = f"  poison {sym} {date}:"
        for name, xkw in sets.items():
            kw = dict(rs.SIMKW)
            kw.update(HOLD)
            kw.update(xkw)
            kw.update(slippage_bps=10.0, entry_mode="market_at_start",
                      entry_start=dtime(10, 0))
            b, n = poison(df, pc, kw)
            tot += b
            n_all += n
            line += f" {name} {b}/{n}"
        print(line, flush=True)
    print(f"  CAUSALITY (MX kwargs): {tot}/{n_all} breaches")
    assert tot == 0, "CAUSALITY BREACH in the MX exits"


def main():
    print("mx_exit_test (MX-series 2026-09-02)")
    t_market_at_start()
    t_vwap()
    t_rsi()
    t_macd()
    t_rand_exit()
    t_target()
    causality()
    print("mx_exit_test: ALL PASS")


if __name__ == "__main__":
    main()
