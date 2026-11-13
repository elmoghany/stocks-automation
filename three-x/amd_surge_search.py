"""Search rules that catch fast AMD runs like Nov 2026 (report, fall, then +45% in a week). Backtest only, no orders.

Three buy families, decided at the close and filled at the next open, 5 bp per side:
  rebound   within K sessions after a report, AMD fell at least D below the report-day close, then closes U above its lowest close since
  breakout  within K sessions after a report, AMD closes above its highest close of the prior L sessions
  thrust    any day, AMD closes U above its lowest close of the last W sessions
  trend     in AMD by default: buy whenever out and AMD is above its 20- or 50-day average, which is above the 200-day
Sells: a trailing stop from the highest close since the buy, a cap on days held, or 7 sessions before the next report.
Optional filter: AMD above its 200-day average.

Honesty: nothing after the Nov 5, 2026 close is used to score or pick (the books started then). Picked on Aug 2023 to Nov 2026 (the user's
3 years), checked on 2013 to Jul 2023, and the reverse. Reliable means at least 75% of trades made money. The luck check gives each finalist
the same number of random buy days in the same years with the same sell, 300 times. This week's run is shown at the end only as an example.
Writes results/amd_surge_search.csv.
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).parent
RES = HERE / "results"
CACHE = RES / "amd_daily_2012_cache.csv"
END = "2026-11-13"
EARLY, RECENT, CUT = pd.Timestamp("2013-01-01"), pd.Timestamp("2023-08-01"), pd.Timestamp("2026-11-06")
COST = 0.0005

if CACHE.exists():
    f = pd.read_csv(CACHE, index_col=0, parse_dates=True)
else:
    raw = yf.download("AMD", start="2012-01-01", end=END, auto_adjust=True, progress=False)
    f = pd.DataFrame({k.lower(): raw[k].squeeze() for k in ("Open", "High", "Low", "Close", "Volume")}).dropna()
    f.index = pd.DatetimeIndex(f.index).tz_localize(None).normalize()
    f.to_csv(CACHE)
idx, o, c, n = f.index, f.open.values, f.close.values, len(f)
i_early, i_recent, i_cut = (int(idx.searchsorted(d)) for d in (EARLY, RECENT, CUT))
above200 = (f.close > f.close.rolling(200).mean()).values
rep = sorted({int(idx.searchsorted(d)) for d in pd.to_datetime(json.loads((RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"]) if d >= pd.Timestamp("2012-06-01")})
rep = [r for r in rep if r < n]
last_rep = np.full(n, -10_000)
next_rep = np.full(n, 10_000_000)
for r in rep:
    last_rep[r:] = r
for r in reversed(rep):
    next_rep[:r + 1] = np.minimum(next_rep[:r + 1], r)
# The next report date is published weeks ahead; after the last known report, count trading days to 2027-02-02.
tail = np.nonzero(next_rep > n)[0]
next_rep[tail] = tail + np.busday_count(idx[tail].values.astype("datetime64[D]"), np.datetime64("2027-02-02"))


def rebound(k, d, u):
    out = np.zeros(n, dtype=bool)
    for r in rep:
        if r + 1 >= n:
            continue
        base, low, fell = c[r], np.inf, False
        for i in range(r + 1, min(r + k + 1, n)):
            low = min(low, c[i])
            fell = fell or c[i] <= base * (1 - d)
            if fell and c[i] >= low * (1 + u):
                out[i] = True
                break
    return out


def breakout(k, lb):
    out = np.zeros(n, dtype=bool)
    for r in rep:
        for i in range(r + 1, min(r + k + 1, n)):
            if i >= lb and c[i] > c[i - lb:i].max():
                out[i] = True
                break
    return out


def thrust(w, u):
    out = np.zeros(n, dtype=bool)
    for i in range(w, n):
        out[i] = c[i] >= c[i - w:i + 1].min() * (1 + u)
    return out


def trend(fast):
    """In AMD by default: buy whenever out and AMD closes above its fast average while that is above the 200-day."""
    m, s = f.close.rolling(fast).mean(), f.close.rolling(200).mean()
    return ((f.close > m) & (m > s)).values


def entries():
    for fast in (20, 50):
        yield "trend", f"above {fast}d avg, {fast}d above 200d", trend(fast)
    for k, d, u in itertools.product((5, 10, 15), (0.0, 0.05, 0.10), (0.05, 0.08, 0.10, 0.15)):
        yield "rebound", f"within {k}d, fell {d:.0%}, up {u:.0%} off low", rebound(k, d, u)
    for k, lb in itertools.product((5, 10, 20), (20, 50)):
        yield "breakout", f"within {k}d, above {lb}d high", breakout(k, lb)
    for w, u in itertools.product((5, 10), (0.15, 0.20, 0.25)):
        yield "thrust", f"+{u:.0%} in {w}d", thrust(w, u)


EXITS = [{"trail": t, "cap": cap, "pre": pre} for t, cap, pre in itertools.product((0.10, 0.15, 0.20, 0.25, None), (20, 40, 60, None), (False, True)) if t or cap or pre]


def exit_name(x):
    bits = ([f"trail {x['trail']:.0%}"] if x["trail"] else []) + ([f"max {x['cap']}d"] if x["cap"] else []) + (["out 7d before report"] if x["pre"] else [])
    return ", ".join(bits)


def run(signal, x, lo, hi):
    """Buys on a signal while out; sells by the exit. Returns trades (buy bar, sell bar or None) and daily position, for bars lo..hi-1."""
    pos, trades = np.zeros(n), []
    hold, peak, at = False, 0.0, 0
    for i in range(lo, hi):
        if not hold:
            if signal[i] and i + 1 < n and not (x["pre"] and next_rep[i] - i <= 7):
                hold, peak, at = True, c[i], i
        else:
            peak = max(peak, c[i])
            out = (x["trail"] and c[i] <= peak * (1 - x["trail"])) or (x["cap"] and i - at >= x["cap"]) or (x["pre"] and next_rep[i] - i <= 7)
            if out:
                hold = False
                trades.append((at, i))
        pos[i] = float(hold)
    if hold:
        trades.append((at, None))
    return trades, pos


def trade_returns(trades, hi):
    out = []
    for b, s in trades:
        buy = o[b + 1]
        sell = o[s + 1] if s is not None and s + 1 < n else c[hi - 1]
        out.append(sell / buy * (1 - COST) ** 2 - 1)
    return np.array(out)


def money(pos, lo, hi):
    was = np.r_[0.0, pos[:-1]]
    before = np.r_[0.0, was[:-1]]
    d = np.ones(n)
    d[1:] = np.where((was[1:] == 1) & (before[1:] == 1), c[1:] / c[:-1], 1.0)
    d[1:] = np.where((was[1:] == 1) & (before[1:] == 0), c[1:] / o[1:] * (1 - COST), d[1:])
    d[1:] = np.where((was[1:] == 0) & (before[1:] == 1), o[1:] / c[:-1] * (1 - COST), d[1:])
    return float(np.prod(d[lo + 1:hi]))


def score(signal, x, lo, hi):
    trades, pos = run(signal, x, lo, hi)
    r = trade_returns(trades, hi)
    years = (hi - lo) / 252
    m = money(pos, lo, hi)
    return {"trades": len(r), "win": float((r > 0).mean()) if len(r) else np.nan, "avg": float(r.mean()) if len(r) else np.nan,
            "mult": m, "per_year": m ** (1 / years) - 1, "in_market": float(pos[lo:hi].mean())}


def luck(signal, x, lo, hi, draws=300, seed=7):
    """Share of random buy-day sets (same count, same years, same sell) whose average trade does at least as well."""
    trades, _ = run(signal, x, lo, hi)
    real = trade_returns(trades, hi)
    if not len(real):
        return np.nan
    rng = np.random.default_rng(seed)
    beat = 0
    for _ in range(draws):
        fake = np.zeros(n, dtype=bool)
        fake[rng.choice(np.arange(lo, hi - 2), size=len(real), replace=False)] = True
        t, _ = run(fake, x, lo, hi)
        r = trade_returns(t, hi)
        beat += r.mean() >= real.mean()
    return beat / draws


def main():
    held = {name: c[hi - 1] / c[lo] for name, lo, hi in (("early", i_early, i_recent), ("recent", i_recent, i_cut))}
    yrs = {"early": (i_recent - i_early) / 252, "recent": (i_cut - i_recent) / 252}
    print(f"AMD held: 2013 to Jul 2023 {held['early']:.1f}x ({held['early'] ** (1 / yrs['early']) - 1:+.0%}/yr); Aug 2023 to Nov 5 2026 {held['recent']:.2f}x ({held['recent'] ** (1 / yrs['recent']) - 1:+.0%}/yr)")
    rows, sigs = [], {}
    for fam, label, raw in entries():
        for filt in ("none", "AMD above 200d"):
            sig = raw & above200 if filt != "none" else raw
            sigs[(fam, label, filt)] = sig
            for x in EXITS:
                e, rc = score(sig, x, i_early, i_recent), score(sig, x, i_recent, i_cut)
                rows.append({"family": fam, "buy": label, "filter": filt, "sell": exit_name(x), **{f"early_{k}": v for k, v in e.items()}, **{f"recent_{k}": v for k, v in rc.items()}})
    t = pd.DataFrame(rows)
    t.to_csv(RES / "amd_surge_search.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 50, "display.max_rows", 100)
    cols = ["family", "buy", "filter", "sell", "recent_trades", "recent_win", "recent_avg", "recent_mult", "recent_in_market", "early_trades", "early_win", "early_avg", "early_mult"]
    fmt = lambda v: f"{v:.2f}"
    print(f"{len(t)} settings")
    print("\nby family: median of each part")
    print(t.groupby(["family", "filter"])[["recent_win", "recent_avg", "recent_mult", "early_win", "early_avg", "early_mult"]].median().round(2).to_string())
    ok = t[(t.recent_trades >= 5) & (t.early_trades >= 10)]
    rel = ok[(ok.recent_win >= 0.75) & (ok.early_win >= 0.75)]
    print(f"\nright 75%+ in both parts (5+ trades recent, 10+ early): {len(rel)} of {len(ok)}")
    print(rel.sort_values("recent_mult", ascending=False).head(15)[cols].to_string(index=False, float_format=fmt))
    for pick, other in (("recent", "early"), ("early", "recent")):
        pool = ok.sort_values(f"{pick}_mult", ascending=False)
        top = pool.iloc[0]
        top50 = pool.head(50)
        print(f"\npicked on {pick} money: {top.family}, {top.buy}, {top['filter']}, {top.sell}: {top[f'{pick}_mult']:.2f}x, right {top[f'{pick}_win']:.0%} of {top[f'{pick}_trades']}."
              f" On {other}: {top[f'{other}_mult']:.2f}x (held {held[other]:.2f}x), right {top[f'{other}_win']:.0%} of {top[f'{other}_trades']}")
        print(f"  top 50 on {other}: median {top50[f'{other}_mult'].median():.2f}x, right {top50[f'{other}_win'].median():.0%}, avg trade {top50[f'{other}_avg'].median():+.1%}")
    # Finalists: best reliable per family by recent money, plus the best by money each way, then a luck check in both parts.
    fin = pd.concat([rel.sort_values("recent_mult", ascending=False).groupby("family").head(2), ok.sort_values("recent_mult", ascending=False).head(2), ok.sort_values("early_mult", ascending=False).head(2), ok[ok.family == "trend"].sort_values("recent_mult", ascending=False).head(1)]).drop_duplicates(subset=["family", "buy", "filter", "sell"])
    xs = {exit_name(x): x for x in EXITS}
    print("\nfinalists, luck check (share of random buy days doing as well; under 5% is good)")
    out = []
    for _, r in fin.iterrows():
        sig, x = sigs[(r.family, r.buy, r["filter"])], xs[r.sell]
        le, lr = luck(sig, x, i_early, i_recent), luck(sig, x, i_recent, i_cut)
        trades, _ = run(sig, x, i_recent, n)
        recent = [(str(idx[b + 1].date()), round(float(o[b + 1]), 2), str(idx[s + 1].date()) if s is not None and s + 1 < n else "open", round(float(o[s + 1] if s is not None and s + 1 < n else c[-1]), 2)) for b, s in trades]
        nov = [tr for tr in recent if tr[0] >= "2026-11-01"]
        out.append({**r[cols].to_dict(), "luck_early": le, "luck_recent": lr, "nov_2026": nov})
        print(f"\n{r.family} | {r.buy} | {r['filter']} | {r.sell}")
        print(f"  recent: {r.recent_trades} trades, right {r.recent_win:.0%}, avg {r.recent_avg:+.1%}, {r.recent_mult:.2f}x (held {held['recent']:.2f}x), in market {r.recent_in_market:.0%}; luck {lr:.0%}")
        print(f"  early:  {r.early_trades} trades, right {r.early_win:.0%}, avg {r.early_avg:+.1%}, {r.early_mult:.2f}x (held {held['early']:.1f}x); luck {le:.0%}")
        print("  trades since Aug 2023 (buy fill, price, sell fill, price):")
        for tr in recent:
            print(f"    {tr}")
    pd.DataFrame(out).to_csv(RES / "amd_surge_finalists.csv", index=False)
    # Neighbours of the rebound rule: if only one exact setting works, it is likely luck.
    nb = t[(t.family == "rebound") & (t["filter"] == "none") & (t.sell == "out 7d before report")]
    print("\nrebound rule neighbours (sell 7 sessions before the next report, no filter)")
    print(nb[["buy", "recent_trades", "recent_win", "recent_avg", "recent_mult", "early_trades", "early_win", "early_avg", "early_mult"]].to_string(index=False, float_format=fmt))


if __name__ == "__main__":
    main()
