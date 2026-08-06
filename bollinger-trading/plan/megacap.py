"""MC-family: $400B+ halal mega caps (user 2026-08-06).

Universe: halal S&P900 names with market cap >= $400B (yfinance
marketCap, cached data/mcap_map.json -- current caps, so the universe
is defined as-of-today; point-in-time caveat noted).

ARM A -- earnings-reaction variants (window Aug 2025-Jul 2026, from
earnings-trading/data/earnings_x2_events.json; $50k/event):
  MC01 E01 rules: beat + open <= -3%, buy open, sell close
  MC02 beat + open <= -2% (mega caps gap smaller)
  MC03 beat + ANY red open (< 0%)
  MC04 beat + gap UP >= +3%: buy open, sell close (continuation)
  MC05 beat + red open: buy reaction close, hold 5 sessions (drift)
  MC06 MISS + open <= -2%: dip-buy the miss (beat-gate control)
ARM B -- dip-from-the-TOP (not day dip): close >= X% below the
trailing 60-session high, X in {8, 10, 12.5, 15, 20}; UPTREND gate =
5y total return >= +50% point-in-time; enter next open; hold 60
sessions (the validated exit; stops/targets/bands all tested worse);
one position per symbol; entries Aug 2021-Jun 2026; $50k/position.
  MC10..MC14 = the five depths. CONTROL = monthly no-signal 60s holds.
Both arms also report the user portfolio rule: ONE slot at a time,
R50 half-profit compounding.
"""

import json
import time
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
ET = ROOT.parent / "earnings-trading"
CACHE = ROOT / "data/ohlcv6y"
MCAP_C = ROOT / "data/mcap_map.json"
BUDGET = 50_000
LO, HI = "2021-08-01", "2026-06-30"
DEPTHS = [(8, "MC10"), (10, "MC11"), (12.5, "MC12"), (15, "MC13"),
          (20, "MC14")]


def mega_universe():
    halal = json.loads((ET / "data/earnings_halal_big.json").read_text())
    names = sorted(s for s, ok in halal.items() if ok)
    m = json.loads(MCAP_C.read_text()) if MCAP_C.exists() else {}
    todo = [s for s in names if s not in m]
    if todo:
        import yfinance as yf
        for n, sym in enumerate(todo):
            try:
                m[sym] = (yf.Ticker(sym).info or {}).get("marketCap") or 0
            except Exception:
                m[sym] = 0
            if n % 25 == 0:
                print(f"  mcap {n}/{len(todo)}", flush=True)
                MCAP_C.write_text(json.dumps(m))
            time.sleep(0.1)
        MCAP_C.write_text(json.dumps(m))
    mega = sorted(s for s in names if (m.get(s) or 0) >= 400e9)
    print(f"mega universe (>=400B, halal): {len(mega)}: {' '.join(mega)}",
          flush=True)
    return mega


def slot_sim(evs, key="ret", hold_key="hold"):
    seq = sorted(evs, key=lambda e: e["entry_date"])
    free = None
    cum = 0.0
    taken = wins = 0
    for e in seq:
        st = pd.Timestamp(e["entry_date"])
        if free is not None and st < free:
            continue
        slot = 50_000 + 0.5 * max(0.0, cum)
        cum += slot * e[key] / 100
        taken += 1
        wins += e[key] > 0
        free = st + pd.Timedelta(days=int(e.get(hold_key, 1) * 1.45) + 1)
    return taken, wins, cum


def stat(label, evs, key="ret"):
    n = len(evs)
    if not n:
        print(f"{label}: n=0")
        return
    rets = [e[key] for e in evs]
    win = 100 * sum(1 for r in rets if r > 0) / n
    avg = sum(rets) / n
    tot = sum(BUDGET * r / 100 for r in rets)
    t, w, cum = slot_sim(evs, key)
    print(f"{label}  n={n:>4} win={win:5.1f}% avg={avg:+6.2f}% "
          f"tot=${tot:+11,.0f} | slot: {t} tr {100*w/max(1,t):3.0f}% "
          f"${cum:+,.0f}", flush=True)


def arm_a(mega):
    ev = json.loads((ET / "data/earnings_x2_events.json").read_text())
    ev = [e for e in ev if e["sym"] in mega]
    for e in ev:
        e["gap"] = (e["open"] / e["pre_close"] - 1) * 100
        e["ret"] = (e["close"] / e["open"] - 1) * 100
        e["entry_date"] = e["date"]
        e["hold"] = 1
    beats = [e for e in ev if e.get("surprise") is not None
             and e["surprise"] > 0]
    misses = [e for e in ev if e.get("surprise") is not None
              and e["surprise"] < 0]
    print(f"\nARM A -- mega-cap earnings (last yr): {len(ev)} events, "
          f"{len(beats)} beats")
    stat("MC01 beat dip<=-3%, open->close ",
         [e for e in beats if e["gap"] <= -3])
    stat("MC02 beat dip<=-2%             ",
         [e for e in beats if e["gap"] <= -2])
    stat("MC03 beat any red open         ",
         [e for e in beats if e["gap"] < 0])
    stat("MC04 beat gap-up>=+3% continue ",
         [e for e in beats if e["gap"] >= 3])
    # MC05: hold 5 sessions from reaction close (needs daily series)
    mc05 = []
    for e in beats:
        if e["gap"] >= 0:
            continue
        f = CACHE / f"{e['sym']}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        idx = df.index
        d = pd.Timestamp(e["date"])
        if d not in idx:
            continue
        p = idx.get_loc(d)
        if p + 5 >= len(df):
            continue
        mc05.append(dict(entry_date=e["date"], hold=5,
                         ret=(df["Close"].iloc[p + 5]
                              / df["Close"].iloc[p] - 1) * 100))
    stat("MC05 beat red: close->+5s drift", mc05)
    stat("MC06 MISS dip<=-2% (control)   ",
         [e for e in misses if e["gap"] <= -2])


def arm_b(mega):
    out = {vid: [] for _, vid in DEPTHS}
    ctrl = []
    for sym in mega:
        f = CACHE / f"{sym}.csv"
        if not f.exists():
            import yfinance as yf
            try:
                df = yf.Ticker(sym).history(period="6y", auto_adjust=True)
                df.index = df.index.tz_localize(None)
                df = df[["Open", "High", "Low", "Close", "Volume"]]
                df.to_csv(f)
            except Exception:
                continue
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
        except Exception:
            continue
        if len(df) < 1300:
            continue
        c, o = df["Close"], df["Open"]
        hi60 = c.rolling(60).max()
        mom5y = c / c.shift(1250) - 1
        idx = df.index
        n = len(df)
        for depth, vid in DEPTHS:
            open_until = -1
            for i in range(260, n - 1):
                if i <= open_until:
                    continue
                ds = str(idx[i].date())
                if not (LO <= ds <= HI):
                    continue
                if pd.isna(hi60.iloc[i]) or pd.isna(mom5y.iloc[i]):
                    continue
                if mom5y.iloc[i] < 0.5:            # uptrend gate
                    continue
                if (c.iloc[i] / hi60.iloc[i] - 1) * 100 > -depth:
                    continue
                e_i = i + 1
                entry = o.iloc[e_i]
                last = min(e_i + 60, n - 1)
                ret = (c.iloc[last] / entry - 1) * 100
                out[vid].append(dict(sym=sym,
                                     entry_date=str(idx[e_i].date()),
                                     hold=last - e_i + 1,
                                     ret=round(ret, 3)))
                open_until = last
        # control: monthly entries, 60s hold, no dip signal
        seen = set()
        for i, d in enumerate(idx[:-61]):
            ds = str(d.date())
            if not (LO <= ds <= HI):
                continue
            k = (d.year, d.month)
            if k in seen:
                continue
            seen.add(k)
            e = o.iloc[i + 1]
            if e > 0:
                ctrl.append((c.iloc[min(i + 61, n - 1)] / e - 1) * 100)
    print(f"\nARM B -- dip-from-top, 60-session holds, uptrend "
          f"(5y>=+50%), {LO}..{HI}")
    for depth, vid in DEPTHS:
        stat(f"{vid} dip>={depth:>4}% off 60d high", out[vid])
    import statistics
    print(f"CTRL monthly no-signal 60s holds: n={len(ctrl)} "
          f"win={100*sum(1 for r in ctrl if r>0)/len(ctrl):.1f}% "
          f"avg={statistics.fmean(ctrl):+.2f}%")
    (ROOT / "data/megacap_results.json").write_text(json.dumps(out))


def main():
    mega = mega_universe()
    arm_a(mega)
    arm_b(mega)


if __name__ == "__main__":
    main()
