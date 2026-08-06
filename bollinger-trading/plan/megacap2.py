"""MC-family part 2 (user refinements 2026-08-06): dip band fixed at
12%-20% off the trailing 60-session high, and the FLEXIBLE-CAUSE tests
-- the trigger must work whether the dip comes from news, earnings, or
a MARKET CRASH:

  MC20-MC27 BAND SWEEP (user: "test different numbers"): dip bands
       [lower, upper] with lower in {8,10,12,15} x upper in {20,25},
       uptrend, 60-session hold (upper bound excludes broken charts)
  MC15a/b/c MARKET trigger only: QQQ >= {8,10,12}% off ITS 60d high
       -> buy every uptrend mega cap (no stock-level trigger), 60s
       hold, one position per symbol per crash episode
  MC16 CRASH OVERLAP: stock dip >= 12% while QQQ >= 10% off its high
  MC17 IDIOSYNCRATIC: stock dip >= 12% while QQQ within 5% of its high
Universe: the 18 halal >=$400B names. Uptrend = 5y >= +50% point-in-
time. $50k/position; slot columns = one-at-a-time R50. Entries
Aug 2021-Jun 2026. QQQ daily cached alongside the equity cache.
"""

import json
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
ET = ROOT.parent / "earnings-trading"
CACHE = ROOT / "data/ohlcv6y"
BUDGET = 50_000
LO, HI = "2021-08-01", "2026-06-30"


def load(sym):
    f = CACHE / f"{sym}.csv"
    if not f.exists():
        import yfinance as yf
        df = yf.Ticker(sym).history(period="6y", auto_adjust=True)
        df.index = df.index.tz_localize(None)
        df[["Open", "High", "Low", "Close", "Volume"]].to_csv(f)
    return pd.read_csv(f, index_col=0, parse_dates=True)


def mega_universe():
    halal = json.loads((ET / "data/earnings_halal_big.json").read_text())
    m = json.loads((ROOT / "data/mcap_map.json").read_text())
    return sorted(s for s, ok in halal.items()
                  if ok and (m.get(s) or 0) >= 400e9)


def slot_sim(evs):
    seq = sorted(evs, key=lambda e: e["entry_date"])
    free = None
    cum = 0.0
    taken = wins = 0
    for e in seq:
        st = pd.Timestamp(e["entry_date"])
        if free is not None and st < free:
            continue
        slot = 50_000 + 0.5 * max(0.0, cum)
        cum += slot * e["ret"] / 100
        taken += 1
        wins += e["ret"] > 0
        free = st + pd.Timedelta(days=int(e["hold"] * 1.45) + 1)
    return taken, wins, cum


def stat(label, evs):
    n = len(evs)
    if not n:
        print(f"{label}: n=0")
        return
    rets = [e["ret"] for e in evs]
    win = 100 * sum(1 for r in rets if r > 0) / n
    avg = sum(rets) / n
    tot = sum(BUDGET * r / 100 for r in rets)
    t, w, cum = slot_sim(evs)
    print(f"{label}  n={n:>4} win={win:5.1f}% avg={avg:+6.2f}% "
          f"tot=${tot:+11,.0f} | slot: {t} tr {100*w/max(1,t):3.0f}% "
          f"${cum:+,.0f}", flush=True)


def main():
    mega = mega_universe()
    qqq = load("QQQ")["Close"]
    qdd = (qqq / qqq.rolling(60).max() - 1) * 100   # market drawdown
    BANDS = [("MC20", 12, 20), ("MC21", 8, 20), ("MC22", 10, 20),
             ("MC23", 15, 20), ("MC24", 8, 25), ("MC25", 10, 25),
             ("MC26", 12, 25), ("MC27", 15, 25)]
    QTRIG = [("MC15a", 8), ("MC15b", 10), ("MC15c", 12)]
    out = {k: [] for k, *_ in BANDS}
    out.update({k: [] for k, _ in QTRIG})
    out.update({"MC16": [], "MC17": []})
    for sym in mega:
        df = load(sym)
        if len(df) < 1300:
            continue
        c, o = df["Close"], df["Open"]
        hi60 = c.rolling(60).max()
        mom5y = c / c.shift(1250) - 1
        idx = df.index
        n = len(df)
        state = {k: -1 for k in out}
        for i in range(260, n - 1):
            ds = str(idx[i].date())
            if not (LO <= ds <= HI):
                continue
            if pd.isna(hi60.iloc[i]) or pd.isna(mom5y.iloc[i]) \
                    or mom5y.iloc[i] < 0.5:
                continue
            dd = (c.iloc[i] / hi60.iloc[i] - 1) * 100
            q = qdd.get(idx[i])
            q = None if q is None or pd.isna(q) else float(q)
            trig = {k: (-up <= dd <= -lo_)
                    for k, lo_, up in BANDS}
            for k, th in QTRIG:
                trig[k] = q is not None and q <= -th
            trig["MC16"] = dd <= -12 and q is not None and q <= -10
            trig["MC17"] = dd <= -12 and q is not None and q >= -5
            for k, hit in trig.items():
                if not hit or i <= state[k]:
                    continue
                e_i = i + 1
                entry = o.iloc[e_i]
                last = min(e_i + 60, n - 1)
                out[k].append(dict(
                    sym=sym, entry_date=str(idx[e_i].date()),
                    hold=last - e_i + 1,
                    ret=round((c.iloc[last] / entry - 1) * 100, 3)))
                state[k] = last
    print(f"mega universe: {len(mega)} names | ${BUDGET:,} | {LO}..{HI}")
    BANDS = [("MC20", 12, 20), ("MC21", 8, 20), ("MC22", 10, 20),
             ("MC23", 15, 20), ("MC24", 8, 25), ("MC25", 10, 25),
             ("MC26", 12, 25), ("MC27", 15, 25)]
    for k, lo_, up in BANDS:
        stat(f"{k} dip {lo_:>4}-{up}% band, 60s hold", out[k])
    for k, th in [("MC15a", 8), ("MC15b", 10), ("MC15c", 12)]:
        stat(f"{k} QQQ>={th}% off (market trig) ", out[k])
    stat("MC16 stock>=12% AND QQQ>=10% off ", out["MC16"])
    stat("MC17 stock>=12%, QQQ near high   ", out["MC17"])
    (ROOT / "data/megacap2_results.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
