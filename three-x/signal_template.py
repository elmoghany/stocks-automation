"""Signal library for Vibe-Trading's runner. sweep.py substitutes the PARAMS literal.

Every family decides from data up to and including the bar's close; Vibe's engine
shifts the signal one bar and fills at the next open. Long-only, weight <= 1 per
book: no margin, shorting or options (project hard rules).
"""
from typing import Dict

import numpy as np
import pandas as pd

PARAMS = {"family": "bh"}


def _rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _atr(df, n):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _latch(enter, leave):
    """Long from an enter bar until a leave bar; leave wins a tie."""
    out, on = [], False
    for e, x in zip(enter.fillna(False).values, leave.fillna(False).values):
        if x:
            on = False
        elif e:
            on = True
        out.append(1.0 if on else 0.0)
    return pd.Series(out, index=enter.index)


def _single(df, p):
    """Target exposure in [0, 1] for one stock."""
    f, c = p["family"], df["close"]
    if f == "amdcycle":
        return _amdcycle(df, p)
    if f == "bh":
        return pd.Series(1.0, index=c.index)
    if f == "sma_trend":
        return (c > c.rolling(p["n"]).mean()).astype(float)
    if f == "sma_cross":
        return (c.rolling(p["fast"]).mean() > c.rolling(p["slow"]).mean()).astype(float)
    if f == "donchian":
        return _latch(c > df["high"].shift().rolling(p["entry"]).max(),
                      c < df["low"].shift().rolling(p["exit"]).min())
    if f == "macd":
        m = c.ewm(span=p["fast"], adjust=False).mean() - c.ewm(span=p["slow"], adjust=False).mean()
        s = (m > m.ewm(span=p["signal"], adjust=False).mean()).astype(float)
        return s * (c > c.rolling(200).mean()).astype(float) if p.get("trend") else s
    if f == "rsi_pullback":
        trend = c > c.rolling(p.get("trend_n", 200)).mean()
        return _latch((_rsi(c, p["n"]) < p["th"]) & trend, c > c.rolling(p["exit_n"]).mean())
    if f == "bb_revert":
        mid, sd = c.rolling(p["n"]).mean(), c.rolling(p["n"]).std()
        enter = c < mid - p["k"] * sd
        if p.get("trend"):
            enter = enter & (c > c.rolling(200).mean())
        return _latch(enter, c > mid)
    if f == "atr_trail":
        enter = c > df["high"].shift().rolling(p["entry"]).max()
        atr = _atr(df, 20).values
        out, on, peak = [], False, 0.0
        for i, (ci, e) in enumerate(zip(c.values, enter.fillna(False).values)):
            if on:
                peak = max(peak, ci)
                if ci < peak - p["k"] * atr[i]:
                    on = False
            elif e:
                on, peak = True, ci
            out.append(1.0 if on else 0.0)
        return pd.Series(out, index=c.index)
    if f == "abs_mom":
        return (c.pct_change(p["n"]) > 0).astype(float)
    if f == "vol_target":
        vol = c.pct_change().rolling(20).std() * np.sqrt(252)
        w = (p["target"] / vol).clip(upper=1.0).fillna(0.0)
        return (w * (c > c.rolling(p["n"]).mean()).astype(float)).round(1)
    if f == "dip_buy":
        hi = c.rolling(252, min_periods=60).max()
        return _latch(c < hi * (1 - p["dd"]), c >= hi * (1 - p["exit_dd"]))
    if f == "gap_drift":
        # Earnings-style shock: gap up on heavy volume that holds into the close, then drift.
        gap = df["open"] / c.shift() - 1
        shock = (gap >= p["gap"]) & (c > df["open"]) & (df["volume"] > p["vol_mult"] * df["volume"].rolling(20).mean())
        out, on, age, stop = [], False, 0, 0.0
        for ci, lo, hit in zip(c.values, df["low"].values, shock.fillna(False).values):
            if hit:
                on, age, stop = True, 0, lo
            elif on:
                age += 1
                if age >= p["hold"] or ci < stop:
                    on = False
            out.append(1.0 if on else 0.0)
        return pd.Series(out, index=c.index)
    if f == "high_52w":
        return _latch(c >= c.rolling(252, min_periods=120).max() * (1 - p["near"]), c < c.rolling(p["exit_n"]).mean())
    if f == "squeeze":
        mid, sd = c.rolling(20).mean(), c.rolling(20).std()
        width = (4 * sd / mid)
        calm = width.rolling(120).rank(pct=True).shift() < p["pct"]
        return _latch(calm & (c > mid + 2 * sd), c < c.rolling(p["exit_n"]).mean())
    if f == "down_days":
        streak = (c < c.shift()).astype(int)
        for _ in range(p["days"] - 1):
            streak = streak * (c.shift(_ + 1) < c.shift(_ + 2)).astype(int)
        return _latch((streak > 0) & (c > c.rolling(200).mean()), c > c.shift())
    if f == "rs_leader":
        rel = c / df.attrs["bench"].reindex(c.index).ffill()
        return ((rel > rel.rolling(p["n"]).mean()) & (c > c.rolling(p["trend_n"]).mean())).astype(float)
    if f == "overnight":
        # Hourly bars: long from the last bar's open until the next morning's open.
        t = c.index.tz_localize(None) if c.index.tz is None else c.index.tz_convert("America/New_York").tz_localize(None)
        last_bar = pd.Series(t.date, index=c.index).shift(-2) != pd.Series(t.date, index=c.index)
        return last_bar.astype(float).where(pd.Series(t.date, index=c.index).shift(-1) == pd.Series(t.date, index=c.index), 0.0)
    if f == "external":
        # Dated decisions from an outside source (TradingAgents ratings), already mapped to weights.
        s = pd.Series({pd.Timestamp(k): float(v) for k, v in p["by_code"][df.attrs.get("code", "")].items()})
        return s.sort_index().reindex(c.index.tz_localize(None), method="ffill").fillna(0.0).set_axis(c.index)
    if f == "seasonal":
        return pd.Series(np.isin(c.index.month, p["months"]).astype(float), index=c.index)
    if f == "turn_of_month":
        idx = pd.Series(range(len(c)), index=c.index)
        ym = c.index.to_period("M")
        from_end = idx.groupby(ym).transform(lambda s: len(s) - 1 - (s - s.iloc[0]))
        from_start = idx.groupby(ym).transform(lambda s: s - s.iloc[0])
        return ((from_end < p["before"]) | (from_start < p["after"])).astype(float)
    raise ValueError(f)


def _amdcycle(df, p):
    """One stock or cash, deciding only at the last close of each week ("W") or month ("M"), from trade_from on.

    Report dates are used in advance: AMD announces them weeks ahead. Selling on the last decision before a report
    fills at the next open, so the position is gone before the report's after-close release.
      hold: bought once and held.
      earn: out from k decisions before the last decision before a report until w decisions after it.
      runup: in only from f decisions before the last decision before a report, until that decision ("before") or the
        first decision after the report ("through").
      after: in from a decisions after the first decision after a report, for b decisions.
      dip: buy after a fall of dd from the highest close of the past look bars, counting only bars since the last sale;
        with post=1 only within 20 bars after a report. Sold by target (+30, +50, +100%), a 25% trail from the high
        since buying, regaining the high from before the fall, or on the last decision before the next report.
      swing: from the study of AMD's turns (amd_turns.py). Buy when the 14-day RSI is at or below buy_rsi and the close
        is at least buy_gap below its 50-day average. Sell when RSI is at or above sell_rsi, the close is at least
        sell_gap above that average, and at least wait weeks have passed since the last report. With stop, also sell
        if the close falls that far below the purchase price.
    """
    close = df["close"]
    c = close.values
    days = pd.DatetimeIndex(close.index)
    days = days.tz_localize(None) if days.tz is not None else days
    days = days.normalize()
    n, rule = len(c), p["rule"]
    period = days.to_period("W-FRI" if p["cadence"] == "W" else "M")
    decide = np.append(period[1:] != period[:-1], True)
    dec = np.nonzero(decide)[0]
    start = int(days.searchsorted(pd.Timestamp(p["trade_from"])))
    reports = sorted({int(days.searchsorted(pd.Timestamp(d))) for d in p["reports"] if pd.Timestamp(d) <= days[-1]})
    last_before = {int(np.searchsorted(dec, r, "left")) - 1 for r in reports}
    pos = np.zeros(n)
    if rule == "hold":
        pos[start:] = 1.0
    elif rule == "swing":
        rsi, gap = _rsi(close, 14).values, (close / close.rolling(50).mean() - 1).values
        hold, cost = False, 0.0
        for i in range(n):
            if decide[i] and i >= start:
                if hold:
                    past = [r for r in reports if r < i]
                    since = i - past[-1] if past else 10 ** 6
                    target = rsi[i] >= p["sell_rsi"] and gap[i] >= p["sell_gap"] and since >= p["wait"] * 5
                    if target or (p.get("stop") and c[i] <= cost * (1 - p["stop"])):
                        hold = False
                elif rsi[i] <= p["buy_rsi"] and gap[i] <= -p["buy_gap"]:
                    hold, cost = True, c[i]
            pos[i] = float(hold)
    elif rule == "dip":
        hold, cost, peak, prior, last_sale = False, 0.0, 0.0, 0.0, 0
        where = {int(i): j for j, i in enumerate(dec)}
        for i in range(n):
            if hold:
                peak = max(peak, c[i])
            if decide[i] and i >= start:
                x = p["exit"]
                if hold:
                    leave = (c[i] >= cost * (1 + p["gain"]) if x == "target" else c[i] < peak * 0.75 if x == "trail"
                             else c[i] >= prior if x == "regain" else where[i] in last_before)
                    if leave:
                        hold, last_sale = False, i
                else:
                    high = c[max(last_sale, i - p["look"] + 1):i + 1].max()
                    near = not p.get("post") or any(r < i <= r + 20 for r in reports)
                    if c[i] <= high * (1 - p["dd"]) and near and not (x == "report" and where[i] in last_before):
                        hold, cost, peak, prior = True, c[i], c[i], high
            pos[i] = float(hold)
    else:
        flags = np.ones(len(dec)) if rule == "earn" else np.zeros(len(dec))
        for r in reports:
            before = int(np.searchsorted(dec, r, "left")) - 1
            after = int(np.searchsorted(dec, r, "right"))
            if rule == "earn":
                flags[max(before - p["k"], 0):after + p["w"] - 1] = 0.0
            elif rule == "runup":
                flags[max(before - p["f"], 0):before if p["sell"] == "before" else after] = 1.0
            else:
                flags[after + p["a"]:after + p["a"] + p["b"]] = 1.0
        state = pd.Series(np.nan, index=range(n))
        state.iloc[dec] = flags
        pos = state.ffill().fillna(0.0).values
        pos[:start] = 0.0
        first = dec[dec >= start][0]
        pos[start:first] = 0.0  # nothing is bought before the first decision in the window
    return pd.Series(pos, index=close.index)


def _rotate(data, codes, p):
    """Hold the stronger of the tradable names by n-day momentum.

    When neither has positive momentum: with p["cash"] go flat, otherwise keep the last pick.
    """
    closes = pd.concat([data[k]["close"].rename(k) for k in codes], axis=1).ffill()
    mom = closes.pct_change(p["n"])
    if p.get("vol_adj"):
        mom = mom / closes.pct_change().rolling(p["n"]).std()
    if p.get("trend_n"):
        mom = mom.where(closes > closes.rolling(p["trend_n"]).mean())
    best = mom.where(mom > 0).idxmax(axis=1)
    if p.get("cash"):
        best = best.fillna("")  # "" is flat; the ffill below must not bring the last pick back
    if p.get("every"):
        keep = pd.Series(range(len(best)), index=best.index) % p["every"] == 0
        best = best.where(keep).ffill()
    return {k: (best == k).astype(float) for k in codes}


def _switch(data, codes, p):
    """Hold one stock or cash, each for at least min_hold bars, deciding only on past closes.

    A stock qualifies with positive n-day momentum and, if trend_n is set, a close above that average.
    When free to act: leave a stock that stops qualifying for the strongest qualifier, or cash if there
    is none, and buy the strongest qualifier from cash. Unless sticky, also switch to a stronger stock.
    """
    closes = pd.concat([data[k]["close"].rename(k) for k in codes], axis=1).ffill()
    mom = closes.pct_change(p["n"])
    ok = mom > 0
    if p.get("trend_n"):
        ok &= closes > closes.rolling(p["trend_n"]).mean()
    m, q = mom.values, ok.values
    weights = np.zeros(m.shape)
    hold, since = -1, p["min_hold"]
    for i in range(len(m)):
        if since >= p["min_hold"]:
            scores = np.where(q[i], m[i], -np.inf)
            best = int(np.argmax(scores)) if q[i].any() else -1
            new = hold if hold >= 0 and q[i][hold] and p.get("sticky") else best
            if new != hold:
                hold, since = new, 0
        if hold >= 0:
            weights[i, hold] = 1.0
        since += 1
    return {k: pd.Series(weights[:, j], index=closes.index) for j, k in enumerate(codes)}


def _entry_rule(df, p):
    """When a stock may be bought, from past bars only.

    trend: positive 126-day momentum above the 200-day average.
    lthm: 25-day average above the 50-day with SPY above its 100-day (Bensdorp, Long Trend High Momentum).
    minervini: his trend template (above rising long averages, near the 52-week high, well off the low).
    breakout: new 55-day high on volume at least 1.3x normal, above the 50-day average.
    selloff: down 12.5% in 3 days while above the 150-day average (Bensdorp, Long Mean Reversion Selloff).
    dip: at least 15% below the 63-day high while above the 200-day average.
    """
    c, e = df["close"], p["entry"]
    sma = lambda n: c.rolling(n).mean()
    if e == "trend":
        return (c.pct_change(126) > 0) & (c > sma(200))
    if e == "lthm":
        spy = df.attrs["bench"].reindex(c.index).ffill()
        return (sma(25) > sma(50)) & (spy > spy.rolling(100).mean())
    if e == "minervini":
        s50, s150, s200 = sma(50), sma(150), sma(200)
        return ((c > s50) & (s50 > s150) & (s150 > s200) & (s200 > s200.shift(21))
                & (c >= 0.75 * c.rolling(252).max()) & (c >= 1.3 * c.rolling(252).min()))
    if e == "breakout":
        v = df["volume"]
        return (c >= c.rolling(55).max().shift(1)) & (v >= 1.3 * v.rolling(50).mean().shift(1)) & (c > sma(50))
    if e == "selloff":
        return (c > sma(150)) & (c / c.shift(3) - 1 <= -0.125)
    if e == "dip":
        return (c > sma(200)) & (c <= 0.85 * c.rolling(63).max())
    raise ValueError(e)


def _sleeve(close, ok, sma50, sma100, p, budget):
    """One account running the entry, exit and sizing rules over stocks in priority order.

    Returns the dollar value per stock, the cash and a state code that changes on every trade. Values
    drift with price, so "buy $50k and let it run" is not trimmed back to a fixed weight by the engine.
    """
    n, k = close.shape
    steps, fall, size = p.get("steps", 1), p.get("fall", 0.0), p["size"]
    value, cash_out, state = np.zeros((n, k)), np.zeros(n), np.zeros(n)
    cash, hold, shares, spent, stake, filled, since = budget, -1, 0.0, 0.0, 0.0, 0, p["min_hold"]
    last_buy, peak, lock = 0.0, 0.0, np.full(k, -1)
    for i in range(n):
        px = close[i]
        if hold >= 0:
            peak = max(peak, px[hold])
            if filled < steps and px[hold] <= last_buy * (1 - fall):  # buy the next step on this fall
                buy = min(stake / steps, cash)
                shares += buy / px[hold]
                spent, cash, filled, last_buy = spent + buy, cash - buy, filled + 1, px[hold]
            if since >= p["min_hold"]:
                cost = spent / shares
                x = p["exit"]
                leave = (px[hold] < sma50[i, hold] if x == "sma50" else px[hold] < sma100[i, hold] if x == "sma100"
                         else px[hold] < peak * 0.75 if x == "trail25"
                         else px[hold] >= cost * 1.5 or px[hold] < sma100[i, hold])
                better = hold > 0 and ok[i, 0] and lock[0] < i  # the first stock always takes priority
                if leave or better:
                    cash += shares * px[hold]
                    lock[hold] = i + p["min_hold"] if leave else i  # a stock just sold rests before rebuying
                    hold, shares, spent, filled, since = -1, 0.0, 0.0, 0, 0
        if hold < 0:
            for j in range(k):
                if ok[i, j] and lock[j] < i:
                    stake = cash * size
                    buy = stake / steps
                    hold, shares, spent, cash, filled, last_buy, peak, since = j, buy / px[j], buy, cash - buy, 1, px[j], px[j], 0
                    break
        if hold >= 0:
            value[i, hold] = shares * px[hold]
        cash_out[i], state[i] = cash, (hold + 1) * 10 + filled
        since += 1
    return value, cash_out, state


def _first(data, codes, p):
    """AMD is the first choice, the other stock the second; or half the money in each (mode "both")."""
    codes = sorted(codes, key=lambda k: k.split(".")[0] != "AMD")
    # Built from dicts: concat compares attrs, and the bench series stored there makes that fail.
    closes = pd.DataFrame({k: data[k]["close"] for k in codes})[codes].sort_index().ffill()
    ok = pd.DataFrame({k: _entry_rule(data[k], p) for k in codes})[codes].reindex(closes.index).fillna(False).astype(bool)
    if p.get("partner_by_year"):  # the second stock was chosen each January from earlier data only
        for year, name in p["partner_by_year"].items():
            rows = closes.index.year == int(year)
            for k in codes[1:]:
                if k.split(".")[0] != name:
                    ok.loc[rows, k] = False
        ok.loc[closes.index.year < min(int(y) for y in p["partner_by_year"]), codes[1:]] = False
    c = closes.values
    s50, s100 = closes.rolling(50).mean().values, closes.rolling(100).mean().values
    q = ok.values
    if p.get("mode") == "both":
        # Half for AMD, half for the second stock, which may be a different name each year.
        groups = [[0], list(range(1, len(codes)))]
        parts = [_sleeve(c[:, g], q[:, g], s50[:, g], s100[:, g], {**p, "size": 1.0}, 0.5) for g in groups]
        value = np.hstack([x[0] for x in parts])
        cash = sum(x[1] for x in parts)
        state = sum(x[2] * 100 ** j for j, x in enumerate(parts))
    else:
        value, cash, state = _sleeve(c, q, s50, s100, p, 1.0)
    total = value.sum(axis=1) + cash
    sig = {k: pd.Series(value[:, j] / total, index=closes.index) for j, k in enumerate(codes)}
    sig["__state__"] = pd.Series(state, index=closes.index)
    return sig


def _carver(c):
    """Trend strength from 0 to 1: EWMA 16/64 over price volatility, scaled as in Carver (pysystemtrade)."""
    ewmac = c.ewm(span=16, adjust=False).mean() - c.ewm(span=64, adjust=False).mean()
    vol = c.diff().ewm(span=36, adjust=False).std()
    return (ewmac / vol * 3.75 / 10).clip(0, 1)


def _book(close, ok, rank, stop, target, p, budget, blocked=None):
    """One account: the rules of _sleeve plus the additions in ladder.py, each switched on by p."""
    n, k = close.shape
    frame = pd.DataFrame(close)
    s50, s100 = frame.rolling(50).mean().values, frame.rolling(100).mean().values
    atr = frame.diff().abs().ewm(alpha=1 / 20, adjust=False).mean().values
    high = frame.rolling(p["reentry_high"]).max().shift(1).values if p.get("reentry_high") else None
    ret63 = frame.pct_change(63, fill_method=None).values
    steps, fall, size = p.get("steps", 1), p.get("fall", 0.0), p["size"]
    start, add_at = p.get("pyramid", (1.0, 0.0))
    need_losses, rest = p.get("cooldown", (0, 0))
    brake_dd, brake_rest = p.get("brake", (0.0, 0))
    stopped, losses, pause_until, top = np.zeros(k, dtype=bool), 0, -1, budget
    lock_gain, lock_trail = p.get("lock", (np.inf, 0.25))
    value, cash_out, state = np.zeros((n, k)), np.zeros(n), np.zeros(n)
    cash, hold, shares, spent, stake, filled, since = budget, -1, 0.0, 0.0, 0.0, 0, p["min_hold"]
    last_buy, peak, added, trades, lock = 0.0, 0.0, True, 0, np.full(k, -1)
    for i in range(n):
        px = close[i]
        if hold >= 0:
            peak = max(peak, px[hold])
            account = cash + shares * px[hold]
            top = max(top, account)
            if filled < steps and px[hold] <= last_buy * (1 - fall):
                buy = min(stake / steps * start, cash)
                shares += buy / px[hold]
                spent, cash, filled, last_buy = spent + buy, cash - buy, filled + 1, px[hold]
                trades += 1
            if not added and px[hold] >= spent / shares * (1 + add_at):  # add to a winner
                buy = min(stake * (1 - start), cash)
                shares += buy / px[hold]
                spent, cash, added = spent + buy, cash - buy, True
                trades += 1
            if p.get("forecast") and since > 0 and since % 21 == 0:  # resize to the trend's strength
                equity = cash + shares * px[hold]
                gap = target[i, hold] * size * equity - shares * px[hold]
                if target[i, hold] > 0 and abs(gap) > 0.1 * equity:
                    if gap > 0:
                        buy = min(gap, cash)
                        shares, spent, cash = shares + buy / px[hold], spent + buy, cash - buy
                    else:
                        part = -gap / (shares * px[hold])
                        shares, spent, cash = shares * (1 - part), spent * (1 - part), cash - gap
                    trades += 1
            cost = spent / shares
            early = p.get("early_stop") and peak < cost * 1.2 and px[hold] <= cost * (1 - p["early_stop"])
            early = early or (blocked is not None and blocked[i, hold])
            if since >= p["min_hold"] or early:
                x = p["exit"]
                leave = (px[hold] < s50[i, hold] if x == "sma50" else px[hold] < s100[i, hold] if x == "sma100"
                         else (px[hold] < peak - p["trail_k"] * atr[i, hold] if p.get("trail_k") else px[hold] < peak * 0.75) if x == "trail25"
                         else px[hold] >= cost * 1.5 or px[hold] < s100[i, hold])
                braking = brake_dd > 0 and account < top * (1 - brake_dd)
                leave = leave or stop[i] or braking or early or (peak >= cost * (1 + lock_gain) and px[hold] < peak * (1 - lock_trail))
                better = since >= p["min_hold"] and hold > 0 and ok[i, 0] and lock[0] < i
                if better and p.get("let_run") is not None:  # let the second stock run unless AMD is clearly stronger
                    better = px[hold] < s50[i, hold] or ret63[i, 0] - ret63[i, hold] > p["let_run"]
                if leave or better:
                    losses = losses + 1 if shares * px[hold] < spent else 0
                    if need_losses and losses >= need_losses:
                        pause_until, losses = i + rest, 0
                    if braking:
                        pause_until, top = i + brake_rest, shares * px[hold] + cash
                    stopped[hold] = leave
                    cash += shares * px[hold]
                    lock[hold] = i + p["min_hold"] if leave else i
                    hold, shares, spent, filled, since, added = -1, 0.0, 0.0, 0, 0, True
                    trades += 1
        if hold < 0 and i >= pause_until:
            order = [0] + sorted(range(1, k), key=lambda j: -rank[i, j]) if k > 2 else range(k)
            for j in order:
                if ok[i, j] and lock[j] < i and target[i, j] > 0 and not (high is not None and stopped[j] and not px[j] >= high[i, j]):
                    stopped[j] = False
                    stake = cash * size * target[i, j]
                    buy = stake / steps * start
                    hold, shares, spent, cash, filled, last_buy, peak, since = j, buy / px[j], buy, cash - buy, 1, px[j], px[j], 0
                    added = start >= 1.0
                    trades += 1
                    break
        if hold >= 0:
            value[i, hold] = shares * px[hold]
        cash_out[i], state[i] = cash, trades
        since += 1
    return value, cash_out, state


def _ladder(data, codes, p, market):
    """AMD first, a growth stock second; ladder.py adds one feature per version through p."""
    codes = sorted(codes, key=lambda k: k.split(".")[0] != "AMD")
    closes = pd.DataFrame({k: data[k]["close"] for k in codes})[codes].sort_index().ffill()
    ok = pd.DataFrame({k: _entry_rule(data[k], p) for k in codes})[codes].reindex(closes.index).fillna(False).astype(bool)
    if p.get("gap"):  # earnings-style shock: big gap up on heavy volume that holds to the close
        size, mult = p["gap"]
        for k in codes:
            d = data[k]
            shock = (d["open"] / d["close"].shift() - 1 >= size) & (d["close"] > d["open"]) & (d["volume"] > mult * d["volume"].rolling(50).mean().shift())
            ok[k] |= shock.reindex(closes.index).fillna(False).astype(bool)
    for label, names in (("partner_by_year", lambda v: [v]), ("pool_by_year", lambda v: v)):
        if p.get(label):
            for year, value in p[label].items():
                rows = closes.index.year == int(year)
                for k in codes[1:]:
                    if k.split(".")[0] not in names(value):
                        ok.loc[rows, k] = False
            ok.loc[closes.index.year < min(int(y) for y in p[label]), codes[1:]] = False
    if p.get("above50"):  # entry only while the stock is also above its 50-day average
        ok = ok & (closes > closes.rolling(50).mean())
    if p.get("rs"):  # entry only while the stock is beating the S&P 500
        rel = closes.div(data[codes[0]].attrs["bench"].reindex(closes.index).ffill(), axis=0)
        ok = ok & (rel > rel.rolling(p["rs"]).mean())
    if p.get("vol_cap"):  # the second stock is skipped while it is too wild
        vol = closes.pct_change(fill_method=None).rolling(63).std() * np.sqrt(252)
        ok[codes[1:]] = ok[codes[1:]] & (vol[codes[1:]] <= p["vol_cap"])
    others = codes[1:]
    daily = closes.pct_change(fill_method=None)
    if p.get("id_gate"):  # the second stock must have risen through many small gains, not a few jumps
        up, down = (daily > 0).rolling(252).mean(), (daily < 0).rolling(252).mean()
        ok[others] = ok[others] & (closes.pct_change(252, fill_method=None) > 0)[others] & ((up - down) >= p["id_gate"])[others]
    if p.get("overnight"):  # the trend must be built overnight, at least half of it
        n = p["overnight"]
        night = pd.DataFrame({k: np.log(data[k]["open"] / data[k]["close"].shift()) for k in codes})[codes].reindex(closes.index).rolling(n).sum()
        ok = ok & (night > 0) & (night >= 0.5 * np.log(closes / closes.shift(n)))
    if p.get("spike"):  # the second stock is skipped right after a lottery-like jump
        ok[others] = ok[others] & (daily.rolling(21).max() <= p["spike"])[others]
    qqq = market["QQQ"].reindex(closes.index).ffill()
    stop = pd.Series(False, index=closes.index)
    if p.get("regime"):
        stop = ~(qqq > qqq.rolling(p["regime"]).mean())
    if p.get("sector"):
        smh = market["SMH"].reindex(closes.index).ffill()
        ok[codes[0]] &= smh > smh.rolling(p["sector"]).mean()
    if p.get("rebound"):  # after a market fall: back above the 50-day average, buy AMD without waiting
        fell = (qqq / qqq.rolling(252, min_periods=60).max() - 1 <= -p["rebound"]).rolling(63, min_periods=1).max() > 0
        amd = closes[codes[0]]
        back = fell & (qqq > qqq.rolling(50).mean()) & (amd > amd.rolling(50).mean())
        ok[codes[0]] |= back
        stop = stop & ~back
    if p.get("fear_days"):  # fear on the VIX is fading: buy AMD without waiting for its trend
        calm = pd.Series(closes.index.strftime("%Y-%m-%d").isin(p["fear_days"]), index=closes.index)
        ok[codes[0]] |= calm
        stop = stop & ~calm
    ok = ok.apply(lambda col: col & ~stop)
    blocked = None
    if p.get("veto"):  # a bad earnings reaction: out next open, not bought again until the next report
        blocked = pd.DataFrame(False, index=closes.index, columns=codes)
        qq = qqq.values
        for k in codes:
            days = sorted(set(closes.index.searchsorted(pd.to_datetime(p["earn"].get(k.split(".")[0], [])))))
            c_k = closes[k].values
            for a, b in zip(days, days[1:] + [len(closes)]):
                if 1 <= a and a + 1 < len(closes) and c_k[a - 1] > 0:
                    if c_k[a + 1] / c_k[a - 1] - qq[a + 1] / qq[a - 1] <= -p["veto"]:
                        blocked.iloc[a + 1:b, blocked.columns.get_loc(k)] = True
        ok = ok & ~blocked
        blocked = blocked.values
    target = pd.DataFrame({k: _carver(closes[k]) for k in codes}) if p.get("forecast") else pd.DataFrame(1.0, index=closes.index, columns=codes)
    if p.get("second_size"):  # less money in the second choice than in AMD
        target[codes[1:]] = target[codes[1:]] * p["second_size"]
    rank = closes.pct_change(126, fill_method=None)
    if p.get("smooth"):  # steady climbers: 90-day log-regression slope times fit, no single huge jump
        logs = np.log(closes)
        line = pd.Series(np.arange(len(closes), dtype=float), index=closes.index)
        fit = logs.apply(lambda col: col.rolling(90).corr(line))
        slope = fit * logs.rolling(90).std() / line.rolling(90).std()
        rank = (np.exp(slope * 252) - 1) * fit ** 2
        ok[others] = ok[others] & (daily.abs().rolling(90).max() <= p["smooth"])[others]
    rank = rank.fillna(-np.inf)
    c, q, r, t, st = closes.values, ok.values, rank.values, target.values, stop.values
    if p.get("mode") == "both":
        groups = [[0], list(range(1, len(codes)))]
        parts = [_book(c[:, g], q[:, g], r[:, g], st, t[:, g], {**p, "size": 1.0}, 0.5, None if blocked is None else blocked[:, g]) for g in groups]
        value, cash, state = np.hstack([x[0] for x in parts]), parts[0][1] + parts[1][1], parts[0][2] + parts[1][2]
    else:
        value, cash, state = _book(c, q, r, st, t, p, 1.0, blocked)
    total = value.sum(axis=1) + cash
    sig = {k: pd.Series(value[:, j] / total, index=closes.index) for j, k in enumerate(codes)}
    sig["__state__"] = pd.Series(state, index=closes.index)
    return sig


def _topk(data, codes, p):
    """Hold the top k names of that year's eligible list by n-day momentum; rest in cash."""
    closes = pd.concat([data[k]["close"].rename(k) for k in codes], axis=1).ffill(limit=5)
    mom = closes.pct_change(p["n"])
    if p.get("vol_adj"):
        mom = mom / (closes.pct_change().rolling(p["n"]).std() * np.sqrt(p["n"]))
    if p.get("trend_n"):
        mom = mom.where(closes > closes.rolling(p["trend_n"]).mean())
    years = sorted(int(y) for y in p["elig"])
    elig = pd.DataFrame(False, index=closes.index, columns=closes.columns)
    for y in years:
        rows = closes.index.year <= y if y == years[0] else closes.index.year == y
        if len(years) == 1:
            rows = np.ones(len(closes), dtype=bool)
        cols = [k for k in p["elig"][str(y)] if k in elig.columns]
        elig.loc[rows, cols] = True
    mom = mom.where(elig).where(mom > 0)
    weights = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    for i in range(p["n"], len(closes), p["every"]):
        best = mom.iloc[i].dropna().nlargest(p["k"]).index
        row = pd.Series(0.0, index=closes.columns)
        row[list(best)] = 1.0 / p["k"]
        weights.iloc[i] = row
    weights = weights.ffill().fillna(0.0)
    return {k: weights[k] for k in codes}


class SignalEngine:
    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        p = PARAMS
        market = p.get("market", [])
        codes = [k for k in data_map if k not in (p.get("regime_code"), p.get("bench_code")) and k not in market]
        if p.get("bench_code"):
            for k in codes:
                data_map[k].attrs["bench"] = data_map[p["bench_code"]]["close"]
        if p["family"] == "rotate":
            sig = _rotate(data_map, codes, p)
        elif p["family"] == "first":
            sig = _first(data_map, codes, p)
            sig.pop("__state__")
        elif p["family"] == "ladder":
            sig = _ladder(data_map, codes, p, {m.split(".")[0]: data_map[m]["close"] for m in market})
            sig.pop("__state__")
        elif p["family"] == "switch":
            sig = _switch(data_map, codes, p)
        elif p["family"] == "topk":
            sig = _topk(data_map, codes, p)
        else:
            share = 1.0 / len(codes)
            for k in codes:
                data_map[k].attrs["code"] = k
            sig = {k: _single(data_map[k], p) * share for k in codes}
        if p.get("regime_code"):
            r = data_map[p["regime_code"]]["close"]
            on = (r > r.rolling(p["regime_n"]).mean()).astype(float)
            sig = {k: s * on.reindex(s.index).ffill().fillna(0.0) for k, s in sig.items()}
            sig[p["regime_code"]] = pd.Series(0.0, index=r.index)
        if p.get("bench_code"):
            sig[p["bench_code"]] = pd.Series(0.0, index=data_map[p["bench_code"]].index)
        for m in market:
            sig[m] = pd.Series(0.0, index=data_map[m].index)
        return sig
