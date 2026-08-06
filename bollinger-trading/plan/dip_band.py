"""BD-family (BD01-BD08): Bollinger-band ENTRY TIMING inside a -15%
dip (user 2026-08-05: "test bollinger bands entry on neg 15% dip").

The 15%-dip trigger is the book's only control-validated signal (TD06
+29.3%/trade vs +10.2% no-signal control on halal big tech). Question:
does requiring the dip day to ALSO sit at the low side of the bands
(%B thresholds) improve entries -- and do band exits beat the plain
60-session hold?

Common: close >= 15% below trailing 60-session high; enter next open;
one position per symbol; $50k; SLOT columns = user portfolio rule (one
slot at a time, R50 half-profit compounding, deepest %B wins ties).
  BD01 tech, 5y-strong, %B<=0.20, 60-session hold  (TD06 + band gate)
  BD02 tech, 5y-strong, %B<=0.00, 60s hold (below the lower band)
  BD03 tech, 5y-strong, %B<=0.30, 60s hold
  BD04 tech, 5y-strong, %B<=0.20, exit %B>=0.80 (cap 90)
  BD05 tech, 5y-strong, %B<=0.20, exit %B>=0.90 (cap 90)
  BD06 = BD01 + 5-day volume-pressure reversal confirm (P5 crosses >=0)
  BD07 ALL-halal universe (479), 5y-strong, %B<=0.20, 60s hold
  BD08 tech, NO 5y gate, %B<=0.20, 60s hold (isolates the gate)
Benchmark rows: TD06 (dip only, no band) recomputed inline.
Window Aug 2021..Jun 2026; data: cached data/ohlcv6y; sector map from
earnings-trading. Same-day both-directions ambiguity: band exits fill
next open (causal), no stops (TD08 showed stops hurt).
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

#      id     tech  strong  bmax  band_exit  vconf  hold_cap
VARIANTS = [
    ("BD01", True,  True,  0.20, None, False, 60),
    ("BD02", True,  True,  0.00, None, False, 60),
    ("BD03", True,  True,  0.30, None, False, 60),
    ("BD04", True,  True,  0.20, 0.80, False, 90),
    ("BD05", True,  True,  0.20, 0.90, False, 90),
    ("BD06", True,  True,  0.20, None, True,  60),
    ("BD07", False, True,  0.20, None, False, 60),
    ("BD08", True,  False, 0.20, None, False, 60),
    ("TD06", True,  True,  None, None, False, 60),   # benchmark: no band
]


def universes():
    halal = json.loads((ET / "data/earnings_halal_big.json").read_text())
    halal.update(json.loads(
        (ET / "data/earnings_halal_600.json").read_text()))
    sec = json.loads((ET / "data/sector_map.json").read_text())
    all_h = {s for s, ok in halal.items() if ok}
    tech = {s for s in all_h if sec.get(s, ["", ""])[0]
            in ("Technology", "Communication Services")}
    return all_h, tech


def run_sym(sym, df, is_tech, out):
    c, o, h, l, v = (df["Close"], df["Open"], df["High"], df["Low"],
                     df["Volume"])
    hi60 = c.rolling(60).max()
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    pctb = (c - (mid - 2 * sd)) / (4 * sd)
    mom5y = c / c.shift(1250) - 1
    rng = (h - l)
    sv = v * (2 * (c - l) - rng) / rng.where(rng > 0)
    p5 = sv.rolling(5).sum() / v.rolling(5).sum()
    idx = df.index
    n = len(df)
    for (vid, tech, strong, bmax, bexit, vconf, cap) in VARIANTS:
        if tech and not is_tech:
            continue
        i = 260
        while i < n - 1:
            ds = str(idx[i].date())
            if ds > HI:
                break
            ok = (ds >= LO and not pd.isna(hi60.iloc[i])
                  and (c.iloc[i] / hi60.iloc[i] - 1) * 100 <= -15)
            if ok and strong:
                ok = not pd.isna(mom5y.iloc[i]) and mom5y.iloc[i] >= 1.0
            if ok and bmax is not None:
                ok = not pd.isna(pctb.iloc[i]) and pctb.iloc[i] <= bmax
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
            last = min(e_i + cap, n - 1)
            exit_i = None
            if bexit is not None:
                for j in range(e_i, last):
                    if not pd.isna(pctb.iloc[j]) and pctb.iloc[j] >= bexit:
                        exit_i = j + 1
                        break
            if exit_i is None:
                exit_i = last
                px = c.iloc[last]
            else:
                px = o.iloc[exit_i]
            ret = (px / entry - 1) * 100
            out[vid].append(dict(
                sym=sym, entry_date=str(idx[e_i].date()),
                hold=exit_i - e_i + 1,
                pctb=round(float(pctb.iloc[i]), 3)
                if not pd.isna(pctb.iloc[i]) else 9.9,
                ret=round(ret, 3)))
            i = exit_i + 1


def main():
    all_h, tech = universes()
    out = {vid: [] for vid, *_ in VARIANTS}
    used = 0
    for f in sorted(CACHE.glob("*.csv")):
        sym = f.stem
        if sym not in all_h:
            continue
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
        except Exception:
            continue
        if len(df) < 600:
            continue
        used += 1
        run_sym(sym, df, sym in tech, out)
    print(f"universe: {used} halal ({len(tech)} tech) | ${BUDGET:,} | "
          f"{LO}..{HI}")
    print(f"{'id':<5} {'n':>5} {'win%':>5} {'avg%':>7} {'avgHold':>7} "
          f"{'tot$@50k':>12}  slot(R50, 1-at-a-time)")
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
        seq = sorted(evs, key=lambda e: (e["entry_date"], e["pctb"]))
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
        print(f"{vid:<5} {n_:>5} {win:>5.1f} {avg:>+7.2f} {hold:>7.1f} "
              f"{tot:>+12,.0f}  {taken} tr, {100*wins/max(1,taken):.0f}% "
              f"win, ${cum:+,.0f}, final slot "
              f"${50_000 + 0.5*max(0.0,cum):,.0f}", flush=True)
    (ROOT / "data/dip_band_results.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
