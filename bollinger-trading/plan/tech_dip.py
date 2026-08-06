"""TD-family (TD01-TD10): buy 15%-dips in HALAL BIG TECH on long-term
uptrends, $50k/position, multi-day holds ALLOWED (user 2026-08-05
explicitly waived same-day for this book).

Universe: the halal S&P900 set intersected with Technology /
Communication Services sectors (plus AMZN/TSLA-style adjacents if
halal) -- "big tech".
Trigger day t: close is >= DIP% below the trailing 60-session high AND
the 5-year gate holds point-in-time (5y total return >= +100% at t).
Entry: next session's OPEN (causal). One open position per symbol.
Exits (the 10 variants):
  TD01 +10% target, else time-out close at 60 sessions
  TD02 +15% target, 60s cap          TD03 +20% target, 60s cap
  TD04 full recovery to the prior 60d high, 90s cap
  TD05 pure time exit: close after 20 sessions
  TD06 pure time exit: close after 60 sessions
  TD07 deeper entry: 20% dip, +15% target, 60s cap
  TD08 = TD02 + stop-loss -10% (same-day both -> stop first, conservative)
  TD09 = TD02 but only if close > 200-day SMA at trigger (trend intact)
  TD10 = TD02 + capitulation volume (trigger-day vol >= 1.5x 50d avg)
Window: entries Aug 2021 .. Jun 2026 (5 years incl. the 2022 bear);
open positions force-closed at the last bar. Data: cached 6y daily
OHLCV (data/ohlcv6y, built by blsh_intraday.py); sector map from
earnings-trading/data/sector_map.json.
Reported per variant: n, win%, avg%/trade, avg hold days, total $ at
$50k, max concurrent positions (capital planning), worst trade.
"""

import json
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
ET = ROOT.parent / "earnings-trading"
CACHE = ROOT / "data/ohlcv6y"
BUDGET = 50_000
LO, HI = "2021-08-01", "2026-06-30"


def universe():
    halal = json.loads((ET / "data/earnings_halal_big.json").read_text())
    sec = json.loads((ET / "data/sector_map.json").read_text())
    syms = [s for s, ok in halal.items() if ok
            and sec.get(s, ["", ""])[0] in
            ("Technology", "Communication Services")]
    return sorted(syms)


def load_sym(sym):
    f = CACHE / f"{sym}.csv"
    if not f.exists():
        import yfinance as yf
        try:
            df = yf.Ticker(sym).history(period="6y", auto_adjust=True)
            df.index = df.index.tz_localize(None)
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df.to_csv(f)
        except Exception:
            return None
    try:
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        return df if len(df) > 1300 else None
    except Exception:
        return None


VARIANTS = [
    # (id, dip%, target%, stop%, time_cap, needs_200sma, needs_vol, recovery)
    ("TD01", 15, 10, None, 60, False, False, False),
    ("TD02", 15, 15, None, 60, False, False, False),
    ("TD03", 15, 20, None, 60, False, False, False),
    ("TD04", 15, None, None, 90, False, False, True),
    ("TD05", 15, None, None, 20, False, False, False),
    ("TD06", 15, None, None, 60, False, False, False),
    ("TD07", 20, 15, None, 60, False, False, False),
    ("TD08", 15, 15, -10, 60, False, False, False),
    ("TD09", 15, 15, None, 60, True, False, False),
    ("TD10", 15, 15, None, 60, False, True, False),
]


def run_sym(df, out):
    c, o, h, l, v = (df["Close"], df["Open"], df["High"], df["Low"],
                     df["Volume"])
    hi60 = c.rolling(60).max()
    sma200 = c.rolling(200).mean()
    vavg = v.rolling(50).mean()
    mom5y = c / c.shift(1250) - 1
    idx = df.index
    open_until = {vid: -1 for vid, *_ in VARIANTS}
    for i in range(len(df) - 1):
        d = idx[i]
        ds = str(d.date())
        if not (LO <= ds <= HI):
            continue
        if pd.isna(hi60.iloc[i]) or pd.isna(mom5y.iloc[i]):
            continue
        if mom5y.iloc[i] < 1.0:
            continue
        dip_pct = (c.iloc[i] / hi60.iloc[i] - 1) * 100
        for vid, dip, tgt, stop, cap, sma_g, vol_g, recov in VARIANTS:
            if i <= open_until[vid]:
                continue                      # one position at a time
            if dip_pct > -dip:
                continue
            if sma_g and (pd.isna(sma200.iloc[i])
                          or c.iloc[i] <= sma200.iloc[i]):
                continue
            if vol_g and (pd.isna(vavg.iloc[i])
                          or v.iloc[i] < 1.5 * vavg.iloc[i]):
                continue
            e_i = i + 1
            entry = o.iloc[e_i]
            if entry <= 0 or pd.isna(entry):
                continue
            tgt_px = (entry * (1 + tgt / 100) if tgt else
                      (hi60.iloc[i] if recov else None))
            stop_px = entry * (1 + stop / 100) if stop else None
            exit_i, ret = None, None
            last = min(e_i + cap, len(df) - 1)
            for j in range(e_i, last + 1):
                if stop_px is not None and l.iloc[j] <= stop_px:
                    exit_i, ret = j, (stop_px / entry - 1) * 100
                    break                     # stop first (conservative)
                if tgt_px is not None and h.iloc[j] >= tgt_px:
                    exit_i, ret = j, (tgt_px / entry - 1) * 100
                    break
            if exit_i is None:
                exit_i = last
                ret = (c.iloc[last] / entry - 1) * 100
            open_until[vid] = exit_i
            out[vid].append(dict(date=ds, hold=exit_i - e_i + 1,
                                 ret=round(ret, 3),
                                 entry_date=str(idx[e_i].date())))


def main():
    syms = universe()
    print(f"halal big-tech universe: {len(syms)}: "
          f"{' '.join(syms[:20])}{' ...' if len(syms) > 20 else ''}",
          flush=True)
    out = {vid: [] for vid, *_ in VARIANTS}
    for n, sym in enumerate(syms):
        df = load_sym(sym)
        if df is None:
            continue
        per = {vid: [] for vid, *_ in VARIANTS}
        run_sym(df, per)
        for vid, evs in per.items():
            for e in evs:
                e["sym"] = sym
            out[vid] += evs
    print(f"\nTD tech-dip  ${BUDGET:,}/position  entries {LO}..{HI}"
          f"  (multi-day holds allowed)")
    print(f"{'id':<5} {'n':>4} {'win%':>5} {'avg%':>7} {'avgHold':>7} "
          f"{'maxConc':>7} {'tot$':>11}  worst")
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
        # max concurrent positions (capital requirement)
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
        print(f"{vid:<5} {n_:>4} {win:>5.1f} {avg:>+7.2f} {hold:>7.1f} "
              f"{conc:>7} {tot:>+11,.0f}  {worst['sym']} "
              f"{worst['ret']:+.1f}%", flush=True)
    (ROOT / "data/tech_dip_results.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
