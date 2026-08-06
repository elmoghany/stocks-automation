"""BB-family (BB01-BB12): Bollinger-Band mean-reversion on the halal
universe, $50k/position, multi-day holds (user 2026-08-05).

Bands: 20-day SMA +/- 2 sigma. %B = (close - lower) / (upper - lower).
Buy the LOW side (%B <= 0 / 0.20 / 0.30), sell the HIGH side
(%B >= 0.80 / 0.90 / 1.00 / 0.50 mid-band). Gates: 200-day and 50-day
MAs (trend), and the 5-day volume-pressure P5 = sum(sv)/sum(vol) over
5 sessions with sv = v*(2(c-l)-(h-l))/(h-l) -- "buy volume vs sell
volume" reversal detection: BUY confirm = P5 crosses >= 0 while the
band signal is active; SELL accel = P5 < 0 while %B is already high.

All signals computed on day t's close; entries/exits fill at day t+1's
OPEN (causal). One position per symbol per variant; universal 90-
session time cap (BB11: 30). Universe: every cached halal name
(S&P900+600, data/ohlcv6y). Entries Aug 2021..Jun 2026.
CONTROL row: monthly no-signal entries, 30-session holds, same names.

PORTFOLIO RULE (user 2026-08-05): ONE slot at a time -- no second buy
until the open position exits -- with R50 compounding: slot = $50k +
half of cumulative profits (base never shrinks). Same-day competing
signals: the deepest %B wins. The SLOT columns report that portfolio;
per-event columns report raw signal quality.
"""

import json
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data/ohlcv6y"
BUDGET = 50_000
LO, HI = "2021-08-01", "2026-06-30"
CAP = 90

#      id     buyB  sellB  ma200 ma50  volconf volexit cap
VARIANTS = [
    ("BB01", 0.20, 0.80, False, False, False, False, CAP),
    ("BB02", 0.20, 0.90, False, False, False, False, CAP),
    ("BB03", 0.20, 1.00, False, False, False, False, CAP),
    ("BB04", 0.00, 0.80, False, False, False, False, CAP),
    ("BB05", 0.30, 0.80, False, False, False, False, CAP),
    ("BB06", 0.20, 0.80, True,  False, False, False, CAP),
    ("BB07", 0.20, 0.80, False, True,  False, False, CAP),
    ("BB08", 0.20, 0.80, True,  True,  False, False, CAP),
    ("BB09", 0.20, 0.80, False, False, True,  True,  CAP),
    ("BB10", 0.20, 0.90, True,  False, True,  True,  CAP),
    ("BB11", 0.20, 0.80, True,  False, False, False, 30),
    ("BB12", 0.20, 0.50, False, False, False, False, CAP),
]


def prep(df):
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    up, lo_ = mid + 2 * sd, mid - 2 * sd
    pctb = (c - lo_) / (up - lo_)
    ma200 = c.rolling(200).mean()
    ma50 = c.rolling(50).mean()
    rng = (h - l)
    sv = v * (2 * (c - l) - rng) / rng.where(rng > 0)
    p5 = sv.rolling(5).sum() / v.rolling(5).sum()
    return pctb, ma200, ma50, p5


def run_sym(sym, df, out):
    pctb, ma200, ma50, p5 = prep(df)
    o, c = df["Open"], df["Close"]
    idx = df.index
    n = len(df)
    for (vid, bB, sB, g200, g50, vconf, vexit, cap) in VARIANTS:
        i = 210
        while i < n - 1:
            ds = str(idx[i].date())
            if ds > HI:
                break
            ok = (ds >= LO and not pd.isna(pctb.iloc[i])
                  and pctb.iloc[i] <= bB)
            if ok and g200:
                ok = not pd.isna(ma200.iloc[i]) \
                    and c.iloc[i] > ma200.iloc[i]
            if ok and g50:
                ok = not pd.isna(ma50.iloc[i]) and c.iloc[i] > ma50.iloc[i]
            if ok and vconf:
                ok = not pd.isna(p5.iloc[i]) and p5.iloc[i] >= 0 \
                    and not pd.isna(p5.iloc[i - 1]) and p5.iloc[i - 1] < 0
            if not ok:
                i += 1
                continue
            e_i = i + 1
            entry = o.iloc[e_i]
            if entry <= 0 or pd.isna(entry):
                i += 1
                continue
            exit_i = None
            last = min(e_i + cap, n - 1)
            for j in range(e_i, last):
                sell = (not pd.isna(pctb.iloc[j])
                        and pctb.iloc[j] >= sB)
                if not sell and vexit and not pd.isna(pctb.iloc[j]) \
                        and pctb.iloc[j] >= sB - 0.2 \
                        and not pd.isna(p5.iloc[j]) and p5.iloc[j] < 0:
                    sell = True
                if sell:
                    exit_i = j + 1        # fill next open
                    break
            if exit_i is None:
                exit_i = last
                px = c.iloc[last]
            else:
                px = o.iloc[exit_i]
            ret = (px / entry - 1) * 100
            out[vid].append(dict(sym=sym, entry_date=str(idx[e_i].date()),
                                 hold=exit_i - e_i + 1,
                                 pctb=round(float(pctb.iloc[i]), 3),
                                 ret=round(ret, 3)))
            i = exit_i + 1


def main():
    syms = sorted(f.stem for f in CACHE.glob("*.csv"))
    out = {vid: [] for vid, *_ in VARIANTS}
    ctrl = []
    used = 0
    for sym in syms:
        try:
            df = pd.read_csv(CACHE / f"{sym}.csv", index_col=0,
                             parse_dates=True)
        except Exception:
            continue
        if len(df) < 600:
            continue
        used += 1
        run_sym(sym, df, out)
        # control: first session of each month, 30-session hold
        seen = set()
        o, c, idx = df["Open"], df["Close"], df.index
        for i, d in enumerate(idx[:-31]):
            ds = str(d.date())
            if not (LO <= ds <= HI):
                continue
            k = (d.year, d.month)
            if k in seen:
                continue
            seen.add(k)
            e = o.iloc[i + 1]
            if e > 0:
                ctrl.append((c.iloc[min(i + 31, len(df) - 1)] / e - 1) * 100)
    print(f"universe: {used} halal names | ${BUDGET:,}/position | "
          f"entries {LO}..{HI}")
    print(f"{'id':<5} {'n':>5} {'win%':>5} {'avg%':>7} {'avgHold':>7} "
          f"{'maxConc':>7} {'tot$':>12}  worst")
    for vid, *_ in VARIANTS:
        evs = out[vid]
        if not evs:
            print(f"{vid}: n=0")
            continue
        n_ = len(evs)
        win = 100 * sum(1 for e in evs if e["ret"] > 0) / n_
        avg = sum(e["ret"] for e in evs) / n_
        hold = sum(e["hold"] for e in evs) / n_
        tot = sum(BUDGET * e["ret"] / 100 for e in evs)
        events = []
        for e in evs:
            events.append((e["entry_date"], 1))
            end = (pd.Timestamp(e["entry_date"])
                   + pd.Timedelta(days=int(e["hold"] * 1.45) + 1))
            events.append((str(end.date()), -1))
        conc = cur = 0
        for _, delta in sorted(events):
            cur += delta
            conc = max(conc, cur)
        worst = min(evs, key=lambda e: e["ret"])
        # single-slot R50 portfolio: chronological greedy, deepest %B
        # first on ties, slot = 50k + half of cumulative profits
        seq = sorted(evs, key=lambda e: (e["entry_date"], e["pctb"]))
        free_at = None
        cum = 0.0
        taken = wins = 0
        for e in seq:
            start = pd.Timestamp(e["entry_date"])
            if free_at is not None and start < free_at:
                continue
            slot = 50_000 + 0.5 * max(0.0, cum)
            pnl = slot * e["ret"] / 100
            cum += pnl
            taken += 1
            wins += e["ret"] > 0
            free_at = start + pd.Timedelta(days=int(e["hold"] * 1.45) + 1)
        print(f"{vid:<5} {n_:>5} {win:>5.1f} {avg:>+7.2f} {hold:>7.1f} "
              f"{conc:>7} {tot:>+12,.0f}  {worst['sym']} "
              f"{worst['ret']:+.1f}%  | SLOT: {taken} trades, "
              f"{100*wins/max(1,taken):.0f}% win, R50 total "
              f"${cum:+,.0f}, final slot "
              f"${50_000 + 0.5*max(0.0,cum):,.0f}", flush=True)
    import statistics
    print(f"CTRL  {len(ctrl):>5} "
          f"{100*sum(1 for r in ctrl if r>0)/len(ctrl):>5.1f} "
          f"{statistics.fmean(ctrl):>+7.2f} {'30':>7} {'-':>7} "
          f"{'(no-signal monthly, 30s holds)':>12}")
    (ROOT / "data/bollinger_results.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
