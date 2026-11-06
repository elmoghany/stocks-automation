"""Search better AMD buy signals: a second low, the day after earnings, and a market filter. Backtest only, no orders.

Only the buy side changes. Sells stay at the best money rule from amd_zone_search.py, so differences come from the buys. Signals use closes known that
day; report dates are known in advance. Signals within 10 bars of an earlier one count once. A signal is right if AMD closes 15% up before 15% down
(wide), or 10% up before 5% down (tight). Pass means 75% right in both parts: at least 3 signals before May 2025 and 5 after. The luck check slides the
signals along the dates 40 times and counts passes again. Money comes from a fast replay, filled at the next open, which matched Vibe-Trading earlier.
Each part is measured from daily value, so a trade across the split counts in each part only for its own days. Writes results/amd_buy_search.csv.
"""
import itertools
import json

import numpy as np
import pandas as pd
import yfinance as yf

import amd_zone_search as Z

idx, opens, closes = Z.idx, Z.opens, Z.closes
_, rsi, stoch, off, _ = Z.inputs
start, split, n = Z.start, Z.split, len(idx)
SELL = {"sell_s": 90, "sell_r": 60, "reach": 0, "sell_dn": 0.08, "min_days": 15}
_, _, _, _, stretch = Z.inputs
reports = sorted({int(idx.searchsorted(d)) for d in pd.to_datetime(json.loads((Z.RES / "earnings_dates.json").read_text(encoding="utf-8"))["AMD"]) if pd.Timestamp("2023-07-15") <= d <= idx[-1]})
oversold = (stoch < 25) & (rsi < 40)


def market(code):
    s = yf.download(code, start="2022-01-01", end=Z.END, auto_adjust=True, progress=False)["Close"].squeeze()
    s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
    return s.reindex(idx, method="ffill")


qqq, smh, amd = market("QQQ"), market("SMH"), pd.Series(closes, index=idx)
FILTERS = {
    "none": np.ones(n, dtype=bool),
    "QQQ above 100d": (qqq > qqq.rolling(100).mean()).values,
    "QQQ below 100d": (qqq < qqq.rolling(100).mean()).values,
    "QQQ above 200d": (qqq > qqq.rolling(200).mean()).values,
    "SMH above 200d": (smh > smh.rolling(200).mean()).values,
    "AMD above 200d": (amd > amd.rolling(200).mean()).values,
    "AMD below 200d": (amd < amd.rolling(200).mean()).values,
}


def second_low(bounce, tol, window, gain, confirm):
    """Oversold sets a first low. After a bounce, a return near it with higher RSI is the second low; buy then, or on a rise of confirm from it."""
    out, state, low, low_rsi, low_i, low2 = [], 0, 0.0, 0.0, 0, 0.0
    for i in range(start, n):
        x = closes[i]
        if state and i - low_i > window:
            state = 0
        if state == 0:
            if oversold[i]:
                state, low, low_rsi, low_i = 1, x, rsi[i], i
        elif state == 1:
            if x < low:
                low, low_rsi, low_i = x, rsi[i], i
            elif x >= low * (1 + bounce):
                state = 2
        elif state == 2:
            if x <= low * (1 + tol):
                if rsi[i] >= low_rsi + gain:
                    if confirm == 0:
                        out.append(i)
                        state = 0
                    else:
                        state, low2 = 3, x
                elif x < low:
                    state, low, low_rsi, low_i = 1, x, rsi[i], i
        elif state == 3:
            low2 = min(low2, x)
            if x >= low2 * (1 + confirm):
                out.append(i)
                state = 0
    return out


def after_report(reaction, move, setup):
    """Uses the next-day move after each report to decide: buy that day, on day 13, on the first oversold close, or on a 5% rise from the low since."""
    out = []
    for r in reports:
        if r + 1 >= n or r + 1 < start:
            continue
        react = closes[r + 1] / closes[r] - 1
        if (reaction == "down" and react > -move) or (reaction == "up" and react < move):
            continue
        last = min(r + 31, n)
        if setup == "next day":
            out.append(r + 1)
        elif setup == "day 13":
            if r + 13 < n:
                out.append(r + 13)
        elif setup == "oversold":
            hit = [i for i in range(r + 1, last) if oversold[i]]
            out += hit[:1]
        else:
            low = closes[r + 1]
            for i in range(r + 2, last):
                low = min(low, closes[i])
                if low < closes[r] * 0.95 and closes[i] >= low * 1.05:
                    out.append(i)
                    break
    return out


def zone(buy_s, buy_r, depth, buy_up):
    """The earlier buy zone, for comparison: oversold and at least depth below the 63-day high, at once or on a rise of buy_up from the low since."""
    out, armed, low, at = [], False, 0.0, 0
    for i in range(start, n):
        x = closes[i]
        if stoch[i] < buy_s and rsi[i] < buy_r and off[i] >= depth:
            if not armed:
                armed, low, at = True, x, i
            low = min(low, x)
        elif armed:
            low = min(low, x)
            if i - at > 30:
                armed = False
        if armed and (buy_up == 0 or x >= low * (1 + buy_up)):
            out.append(i)
            armed = False
    return out


def settings():
    for bounce, tol, window, gain, confirm in itertools.product((0.03, 0.05, 0.08), (0.02, 0.05, 0.10), (30, 60), (0, 3, 5), (0, 0.03)):
        yield "second low", f"bounce {bounce:.0%}, within {tol:.0%}, {window}d, RSI +{gain}, confirm {confirm:.0%}", second_low(bounce, tol, window, gain, confirm)
    for reaction, move, setup in itertools.product(("down", "up", "any"), (0, 0.03), ("next day", "day 13", "oversold", "5% off low")):
        if reaction == "any" and move:
            continue
        yield "after report", f"next day {reaction} {move:.0%}, {setup}", after_report(reaction, move, setup)
    for buy_s, buy_r, depth, buy_up in itertools.product((20, 25), (40, 45), (0, 0.15, 0.25), (0, 0.03, 0.05)):
        yield "zone", f"stoch<{buy_s}, RSI<{buy_r}, {depth:.0%} off high, up {buy_up:.0%}", zone(buy_s, buy_r, depth, buy_up)


def first_before(limit_up, limit_dn):
    """1 if a later close reaches the rise first, 0 if the fall first, nan if neither by the end."""
    out = np.full(n, np.nan)
    for i in range(n):
        later = closes[i + 1:] / closes[i] - 1
        up, dn = np.nonzero(later >= limit_up)[0], np.nonzero(later <= -limit_dn)[0]
        if len(up) or len(dn):
            out[i] = float(len(up) > 0 and (not len(dn) or up[0] < dn[0]))
    return out


wide, tight = first_before(0.15, 0.15), first_before(0.10, 0.05)


def thin(days):
    kept = []
    for i in sorted(days):
        if not kept or i - kept[-1] > 10:
            kept.append(i)
    return np.array(kept, dtype=int)


def replay(days):
    """In or out at each close: buys on the first signal while out, sells on the fixed rule."""
    want = np.zeros(n, dtype=bool)
    want[np.asarray(days, dtype=int)] = True
    pos = np.zeros(n)
    hold, armed, peak, since = False, False, 0.0, 0
    for i in range(start, n):
        x = closes[i]
        if not hold:
            if want[i] and i + 1 < n:
                hold, armed, since = True, False, 0
        else:
            since += 1
            if stoch[i] > SELL["sell_s"] and rsi[i] > SELL["sell_r"] and stretch[i] >= SELL["reach"]:
                if not armed:
                    armed, peak = True, x
                peak = max(peak, x)
            elif armed:
                peak = max(peak, x)
            if armed and x <= peak * (1 - SELL["sell_dn"]) and since >= SELL["min_days"]:
                hold, armed = False, False
        pos[i] = float(hold)
    return pos


def right(days, table):
    vals = table[days]
    vals = vals[~np.isnan(vals)]
    return float(vals.mean()) if len(vals) else np.nan, len(vals)


def measure(days):
    a, b = days[days < split], days[days >= split]
    out = {}
    for name, part in (("first", a), ("last", b)):
        out[f"{name}_wide"], out[f"{name}_n"] = right(part, wide)
        out[f"{name}_tight"], _ = right(part, tight)
    return out


def passes(m, key):
    return m[f"first_{key}"] >= 0.75 and m[f"last_{key}"] >= 0.75 and m["first_n"] >= 3 and m["last_n"] >= 5


def main():
    rows, signals = [], []
    for family, label, raw in settings():
        for fname, mask in FILTERS.items():
            days = thin([i for i in raw if mask[i]])
            if not len(days):
                continue
            pos = replay(days)
            money = Z.parts(pos)
            gaps = np.abs(days[:, None] - Z.buy_targets[None, :])
            rows.append({"family": family, "setting": label, "filter": fname, **measure(days), "caught": (gaps.min(axis=0) <= Z.NEAR).mean(), "near": (gaps.min(axis=1) <= Z.NEAR).mean(), "buys": int((np.diff(pos, prepend=0.0) > 0).sum()), "first_mult": money["first"], "last_mult": money["last"], "all_mult": money["all"]})
            signals.append(days)
    t = pd.DataFrame(rows).drop_duplicates(subset=["family", "setting", "filter"])
    t.to_csv(Z.RES / "amd_buy_search.csv", index=False)
    pd.set_option("display.width", 240, "display.max_columns", 30, "display.max_colwidth", 60, "display.max_rows", 80)
    fmt = lambda v: f"{v:.2f}"
    held = Z.held_parts()
    print(f"{len(t)} settings. AMD held: first {held['first']:.2f}x, last {held['last']:.2f}x, all {held['all']:.2f}x")
    span = lambda lo, hi, table: (np.nanmean(table[lo:hi]))
    print(f"every day, first part: wide {span(start, split, wide):.0%}, tight {span(start, split, tight):.0%}; last part: wide {span(split, n, wide):.0%}, tight {span(split, n, tight):.0%}")
    cols = ["family", "setting", "filter", "first_wide", "first_tight", "first_n", "last_wide", "last_tight", "last_n", "caught", "near", "buys", "first_mult", "last_mult", "all_mult"]
    for key in ("wide", "tight"):
        hits = t[(t[f"first_{key}"] >= 0.75) & (t[f"last_{key}"] >= 0.75) & (t.first_n >= 3) & (t.last_n >= 5)]
        rotated = []
        span_n = n - start
        for shift in np.linspace(40, span_n - 40, 40).astype(int):
            count = 0
            for days in signals:
                moved = np.sort(start + (days - start + shift) % span_n)
                if passes(measure(moved), key):
                    count += 1
            rotated.append(count)
        print(f"\npass both parts on {key}: {len(hits)}; slid signals: median {np.median(rotated):.0f}, range {min(rotated)}-{max(rotated)}; real beats {sum(len(hits) > r for r in rotated)} of 40")
        print(hits.groupby("family").size().to_string())
        print(hits.sort_values("all_mult", ascending=False).head(10)[cols].to_string(index=False, float_format=fmt))
    print("\nby family and filter, median multiples and how often right")
    print(t.groupby(["family", "filter"])[["first_wide", "last_wide", "first_mult", "last_mult", "all_mult", "caught", "near"]].median().round(2).to_string())
    print(f"\nbeat held: first {(t.first_mult > held['first']).sum()}, last {(t.last_mult > held['last']).sum()}, both {((t.first_mult > held['first']) & (t.last_mult > held['last'])).sum()}")
    both = t[(t.first_mult > held["first"]) & (t.last_mult > held["last"])]
    print(f"\nbeat held in both parts, by all-period money ({len(both)})")
    print(both.sort_values("all_mult", ascending=False).head(15)[cols].to_string(index=False, float_format=fmt))
    print("\nbest 8 by money, all periods")
    print(t.sort_values("all_mult", ascending=False).head(8)[cols].to_string(index=False, float_format=fmt))
    print("\nbest 8 catching the table's buys")
    ranked = t.assign(score=2 * t.caught * t.near / (t.caught + t.near).replace(0, np.nan))
    print(ranked.sort_values(["score", "all_mult"], ascending=False).head(8)[cols + ["score"]].to_string(index=False, float_format=fmt))
    for train, test in (("first", "last"), ("last", "first")):
        for by, col in (("right", f"{train}_wide"), ("money", f"{train}_mult")):
            pool = t[t[f"{train}_n"] >= (3 if train == "first" else 5)].sort_values([col, f"{train}_mult"], ascending=False)
            top, near = pool.iloc[0], pool.head(50)
            print(f"\nchosen by {by} on the {train} part: {top.family}, {top.setting}, {top['filter']}: {top[f'{train}_mult']:.2f}x, right {top[f'{train}_wide']:.0%} of {top[f'{train}_n']}. On the {test} part: {top[f'{test}_mult']:.2f}x (held {held[test]:.2f}x), right {top[f'{test}_wide']:.0%} of {top[f'{test}_n']}")
            print(f"  top 50 on the {test} part: median {near[f'{test}_mult'].median():.2f}x, right {near[f'{test}_wide'].median():.0%}; beat held {(near[f'{test}_mult'] > held[test]).sum()} of 50")


if __name__ == "__main__":
    main()
