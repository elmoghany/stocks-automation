"""Penny-stock momentum day-trading strategy (Cameron Ross style).

The strategy in one line: find a low-float penny stock gapping up on fresh
morning news with huge relative volume, wait for the first dip after a strong
surge, buy when the dip reverses upward on a hammer-family candle (hammer,
inverted hammer, dragonfly doji) WITH momentum-volume confirmation (>=1.5x
trailing average volume), sell at 2x the risk (+$0.30 vs -$0.15 stop) or on a
strong bearish pattern while profitable. Defaults calibrated via candletest.

Screening rules (all must pass):
  1. Price between $2 and $16
  2. Breaking news TODAY between 7:00-10:00 AM ET
  3. Up at least +10% on the day
  4. Hot / high-demand sector (AI, biotech, ... configurable)
  5. Relative volume >= 5x the 50-day average volume
  8. Float under 16M shares

Trading rules:
  6. Avg gain per share $0.18, avg loss per share $0.15 (target/stop)
  7. Position size ~1150 shares
  9. 1-min candlestick entries/exits:
     bullish  = hammer, inverted hammer, dragonfly doji, bullish spinning top,
                bullish engulfing, tweezer bottom, morning star, rising three
     neutral  = doji
     bearish  = hanging man, shooting star, gravestone doji, bearish spinning
                top, bearish engulfing, tweezer top, evening doji star,
                three black crows, evening star, falling three

Usage:
  python penny-stocks.py screen SYM1 SYM2 ...     # run the 6-rule screener
  python penny-stocks.py patterns SYM             # label 1-min candles today
  python penny-stocks.py backtest SYM [--days N]  # sim surge-dip-reversal trades
                                                  # on recent 1-min data (max ~7d)

Data source: yfinance. Honest limitations: news timestamps are approximate and
incomplete, float data is patchy for small caps, and 1-min history only goes
back ~7 days -- a production version needs a real-time scanner feed.
"""

import argparse
import sys
from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

ET = ZoneInfo("America/New_York")

# ---------------------------------------------------------------------------
# Strategy configuration (rules 1-8)
# ---------------------------------------------------------------------------
PRICE_MIN = 2.00                 # rule 1
PRICE_MAX = 16.00
NEWS_START = dtime(7, 0)         # trading window, ET (buy AND sell inside it)
NEWS_END = dtime(10, 0)
NEWS_LOOKBACK_HOURS = 18         # rule 2: news within the last 18 hours
MIN_DAY_GAIN_PCT = 10.0          # rule 3
HOT_SECTORS = [                  # rule 4: substrings matched against
    "artificial intelligence",   # yfinance sector/industry, case-insensitive
    "software", "semiconductor", "technology",
    "biotech", "pharmaceutical", "drug", "health",
]
MIN_REL_VOLUME = 5.0             # rule 5: today vs 50-day avg volume
REL_VOLUME_LOOKBACK = 50
LOSS_PER_SHARE = 0.15            # rule 6: hard stop per share
REWARD_RISK = 2.0                # target = 2x the risk (was fixed $0.18)
GAIN_PER_SHARE = REWARD_RISK * LOSS_PER_SHARE          # 0.30
GAIN_PER_SHARE_MAX = GAIN_PER_SHARE + 0.02             # sell zone 0.30-0.32
POSITION_DOLLARS = 1000          # rule 7 (changed from 1150 shares to $1000
                                 # per trade; shares = $1000 // entry price)
MAX_FLOAT = 16_000_000           # rule 8

# surge/dip detection for the entry setup (rule 9 summary)
SURGE_PCT = 2.0                  # "strong surge": +2% within the window
SURGE_WINDOW_MIN = 10            # ...over at most 10 one-minute candles
DIP_MIN_CENTS = 0.05             # a real dip: >= 5c retrace from surge high

# DEFAULTS (calibrated 2026-08-01 via candletest on 7-10 AM ET gapper data):
# hammer-family entries + volume-reversal confirmation + strong-bearish exits
DEFAULT_BUY_SET = "hammer_family"
DEFAULT_SELL_MODE = "strong_if_profit"
ENTRY_VOL_MULT = 1.5             # reversal candle volume must be >= 1.5x ...
VOL_AVG_BARS = 20                # ... the trailing 20-bar average (momentum
                                 # volume reversal: buyers visibly stepping in)


# ---------------------------------------------------------------------------
# Candlestick pattern engine (rule 9) -- operates on 1-min OHLC bars
# ---------------------------------------------------------------------------

def _parts(o, h, l, c):
    body = abs(c - o)
    rng = max(h - l, 1e-9)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return body, rng, upper, lower


def is_doji(o, h, l, c):
    body, rng, _, _ = _parts(o, h, l, c)
    return body <= 0.1 * rng


def is_dragonfly_doji(o, h, l, c):
    body, rng, upper, lower = _parts(o, h, l, c)
    return body <= 0.1 * rng and lower >= 0.6 * rng and upper <= 0.1 * rng


def is_gravestone_doji(o, h, l, c):
    body, rng, upper, lower = _parts(o, h, l, c)
    return body <= 0.1 * rng and upper >= 0.6 * rng and lower <= 0.1 * rng


def is_hammer_shape(o, h, l, c):
    body, rng, upper, lower = _parts(o, h, l, c)
    return body > 0.1 * rng and lower >= 2 * body and upper <= body


def is_inverted_hammer_shape(o, h, l, c):
    body, rng, upper, lower = _parts(o, h, l, c)
    return body > 0.1 * rng and upper >= 2 * body and lower <= body


def is_spinning_top(o, h, l, c):
    body, rng, upper, lower = _parts(o, h, l, c)
    return (0.1 * rng < body <= 0.35 * rng
            and upper >= 0.25 * rng and lower >= 0.25 * rng)


def _bull(o, c):
    return c > o


def _bear(o, c):
    return c < o


class Candles:
    """Wraps a 1-min OHLC DataFrame and labels patterns per bar index."""

    def __init__(self, df: pd.DataFrame):
        self.o = df["Open"].values
        self.h = df["High"].values
        self.l = df["Low"].values
        self.c = df["Close"].values
        self.v = (df["Volume"].values if "Volume" in df
                  else np.zeros(len(df)))
        self.index = df.index
        self.n = len(df)

        # indicator signals (RSI-14 and MACD 12/26/9 on 1-min closes)
        closes = df["Close"]
        delta = closes.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        loss = (-delta).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        self.rsi = (100 - 100 / (1 + gain / loss)).values
        macd = (closes.ewm(span=12, adjust=False).mean()
                - closes.ewm(span=26, adjust=False).mean())
        sig = macd.ewm(span=9, adjust=False).mean()
        self.macd = macd.values
        self.macd_sig = sig.values

    def indicator_bullish(self, i):
        """RSI/MACD entry signals as pseudo-patterns."""
        out = []
        if i < 1:
            return out
        r0, r1 = self.rsi[i - 1], self.rsi[i]
        if not np.isnan(r0) and r0 < 30 <= r1:
            out.append("rsi_cross_up")          # RSI exits oversold upward
        m0 = self.macd[i - 1] - self.macd_sig[i - 1]
        m1 = self.macd[i] - self.macd_sig[i]
        if not np.isnan(m0) and m0 <= 0 < m1:
            out.append("macd_cross_up")         # MACD crosses above signal
        return out

    def indicator_bearish(self, i):
        out = []
        if i < 1:
            return out
        r0, r1 = self.rsi[i - 1], self.rsi[i]
        if not np.isnan(r0) and r0 > 70 >= r1:
            out.append("rsi_cross_down")        # RSI drops out of overbought
        m0 = self.macd[i - 1] - self.macd_sig[i - 1]
        m1 = self.macd[i] - self.macd_sig[i]
        if not np.isnan(m0) and m0 >= 0 > m1:
            out.append("macd_cross_down")       # MACD crosses below signal
        return out

    def volume_confirmed(self, i: int) -> bool:
        """Momentum volume reversal: bar i's volume >= ENTRY_VOL_MULT x the
        trailing VOL_AVG_BARS average. No volume data -> pass (best effort)."""
        j = max(0, i - VOL_AVG_BARS)
        avg = self.v[j:i].mean() if i > j else 0.0
        if avg <= 0:
            return True
        return self.v[i] >= ENTRY_VOL_MULT * avg

    def _bar(self, i):
        return self.o[i], self.h[i], self.l[i], self.c[i]

    def _in_downswing(self, i, bars=3):
        """Context filter: were the last few closes falling into bar i?"""
        j = max(0, i - bars)
        return i >= 1 and self.c[i - 1] < self.c[j]

    def _in_upswing(self, i, bars=3):
        j = max(0, i - bars)
        return i >= 1 and self.c[i - 1] > self.c[j]

    # ---------------- bullish (need dip context) ----------------
    def bullish_patterns(self, i):
        """Return list of bullish pattern names forming AT bar i."""
        out = []
        if i < 1:
            return out
        o, h, l, c = self._bar(i)
        po, ph, pl, pc = self._bar(i - 1)
        dip = self._in_downswing(i)

        if dip and is_hammer_shape(o, h, l, c):
            out.append("hammer")
        if dip and is_inverted_hammer_shape(o, h, l, c):
            out.append("inverted_hammer")
        if dip and is_dragonfly_doji(o, h, l, c):
            out.append("dragonfly_doji")
        if dip and is_spinning_top(o, h, l, c) and _bull(o, c):
            out.append("bullish_spinning_top")
        if (_bear(po, pc) and _bull(o, c)
                and o <= min(po, pc) and c >= max(po, pc)
                and abs(c - o) > abs(pc - po)):
            out.append("bullish_engulfing")
        if (dip and _bear(po, pc) and _bull(o, c)
                and abs(l - pl) <= 0.15 * max(h - l, ph - pl, 1e-9)):
            out.append("tweezer_bottom")
        if i >= 2:
            o0, h0, l0, c0 = self._bar(i - 2)
            mid_small = is_doji(po, ph, pl, pc) or is_spinning_top(po, ph, pl, pc)
            if (_bear(o0, c0) and mid_small and _bull(o, c)
                    and c >= (o0 + c0) / 2):
                out.append("morning_star")
        if i >= 4:
            o0, h0, l0, c0 = self._bar(i - 4)
            smalls_down = all(
                _bear(self.o[j], self.c[j])
                and self.c[j] > l0 and self.o[j] < h0
                for j in range(i - 3, i)
            )
            if _bull(o0, c0) and smalls_down and _bull(o, c) and c > c0:
                out.append("rising_three")
        return out

    # ---------------- bearish (need up-move context) ----------------
    def bearish_patterns(self, i):
        out = []
        if i < 1:
            return out
        o, h, l, c = self._bar(i)
        po, ph, pl, pc = self._bar(i - 1)
        up = self._in_upswing(i)

        if up and is_hammer_shape(o, h, l, c):
            out.append("hanging_man")
        if up and is_inverted_hammer_shape(o, h, l, c):
            out.append("shooting_star")
        if up and is_gravestone_doji(o, h, l, c):
            out.append("gravestone_doji")
        if up and is_spinning_top(o, h, l, c) and _bear(o, c):
            out.append("bearish_spinning_top")
        if (_bull(po, pc) and _bear(o, c)
                and o >= max(po, pc) and c <= min(po, pc)
                and abs(c - o) > abs(pc - po)):
            out.append("bearish_engulfing")
        if (up and _bull(po, pc) and _bear(o, c)
                and abs(h - ph) <= 0.15 * max(h - l, ph - pl, 1e-9)):
            out.append("tweezer_top")
        if i >= 2:
            o0, h0, l0, c0 = self._bar(i - 2)
            mid_doji = is_doji(po, ph, pl, pc)
            mid_small = mid_doji or is_spinning_top(po, ph, pl, pc)
            if (_bull(o0, c0) and mid_small and _bear(o, c)
                    and c <= (o0 + c0) / 2):
                out.append("evening_doji_star" if mid_doji else "evening_star")
        if i >= 2:
            crows = all(
                _bear(self.o[j], self.c[j])
                and (j == i - 2 or self.c[j] < self.c[j - 1])
                for j in range(i - 2, i + 1)
            )
            if up and crows:
                out.append("three_black_crows")
        if i >= 4:
            o0, h0, l0, c0 = self._bar(i - 4)
            smalls_up = all(
                _bull(self.o[j], self.c[j])
                and self.c[j] < h0 and self.o[j] > l0
                for j in range(i - 3, i)
            )
            if _bear(o0, c0) and smalls_up and _bear(o, c) and c < c0:
                out.append("falling_three")
        return out

    def neutral_patterns(self, i):
        o, h, l, c = self._bar(i)
        return ["doji"] if is_doji(o, h, l, c) else []


# ---------------------------------------------------------------------------
# Screener (rules 1-5, 8)
# ---------------------------------------------------------------------------

def screen_symbol(symbol: str, now_et: datetime | None = None) -> dict:
    """Run all screening rules on one symbol. Returns dict of checks."""
    now_et = now_et or datetime.now(ET)
    t = yf.Ticker(symbol)
    checks = {"symbol": symbol}

    try:
        daily = t.history(period="3mo")
    except Exception as e:
        checks["error"] = str(e)
        return checks
    if daily is None or len(daily) < 2:
        checks["error"] = "no daily data"
        return checks

    price = float(daily["Close"].iloc[-1])
    prev_close = float(daily["Close"].iloc[-2])
    day_gain = (price / prev_close - 1) * 100
    today_vol = float(daily["Volume"].iloc[-1])
    avg_vol = float(daily["Volume"].iloc[-(REL_VOLUME_LOOKBACK + 1):-1].mean())
    rel_vol = today_vol / avg_vol if avg_vol > 0 else 0.0

    checks["price"] = round(price, 2)
    checks["rule1_price_2_to_16"] = PRICE_MIN <= price <= PRICE_MAX
    checks["day_gain_pct"] = round(day_gain, 1)
    checks["rule3_up_10pct"] = day_gain >= MIN_DAY_GAIN_PCT
    checks["rel_volume"] = round(rel_vol, 1)
    checks["rule5_relvol_5x"] = rel_vol >= MIN_REL_VOLUME

    # rule 2: news within the last NEWS_LOOKBACK_HOURS (18h) -- best effort
    cutoff = now_et - timedelta(hours=NEWS_LOOKBACK_HOURS)
    news_hit = False
    news_title = ""
    try:
        for item in (t.news or []):
            content = item.get("content", item)
            ts = (content.get("pubDate") or content.get("displayTime")
                  or item.get("providerPublishTime"))
            if ts is None:
                continue
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts, ET)
            else:
                dt = pd.Timestamp(ts).tz_convert(ET).to_pydatetime()
            if dt >= cutoff:
                news_hit = True
                news_title = (content.get("title") or "")[:60]
                break
    except Exception:
        pass
    checks["rule2_news_18h"] = news_hit
    checks["news"] = news_title

    # rule 4 + 8: sector and float from ticker info
    sector = ""
    flt = None
    try:
        info = t.info or {}
        sector = f"{info.get('sector', '')} / {info.get('industry', '')}"
        flt = info.get("floatShares")
    except Exception:
        pass
    checks["sector"] = sector
    checks["rule4_hot_sector"] = any(
        s in sector.lower() for s in HOT_SECTORS)
    checks["float_m"] = round(flt / 1e6, 1) if flt else None
    checks["rule8_float_under_16m"] = (flt is not None and flt <= MAX_FLOAT)

    rules = [k for k in checks if k.startswith("rule")]
    checks["PASS"] = all(checks[k] for k in rules)
    return checks


def cmd_screen(symbols: list[str]) -> None:
    print(f"{'SYM':<6} {'PASS':<5} {'$':>6} {'1<16':>5} {'gain%':>6} {'r3':>3} "
          f"{'rvol':>5} {'r5':>3} {'news':>5} {'sector':>7} {'floatM':>7} {'r8':>3}")
    print("-" * 78)
    passed = []
    for sym in symbols:
        c = screen_symbol(sym.upper())
        if "error" in c:
            print(f"{sym.upper():<6} ERROR {c['error']}")
            continue
        b = lambda v: "Y" if v else "."
        print(f"{c['symbol']:<6} {('PASS' if c['PASS'] else '-'):<5} "
              f"{c['price']:>6.2f} {b(c['rule1_price_2_to_16']):>5} "
              f"{c['day_gain_pct']:>6.1f} {b(c['rule3_up_10pct']):>3} "
              f"{c['rel_volume']:>5.1f} {b(c['rule5_relvol_5x']):>3} "
              f"{b(c['rule2_news_18h']):>5} {b(c['rule4_hot_sector']):>7} "
              f"{(c['float_m'] if c['float_m'] is not None else '?'):>7} "
              f"{b(c['rule8_float_under_16m']):>3}")
        if c["PASS"]:
            passed.append(c["symbol"])
    print(f"\nPassed all rules: {passed or 'none'}")


def cmd_scan(size: int) -> None:
    """Discover candidates market-wide, then run the full 6-rule screen.

    Stage 1 (coarse, Yahoo screener API): US stocks $2-$16 up >=10% today,
    sorted by day volume. Stage 2: full rule check (news window, sector,
    float, 5x rvol) on each candidate.
    """
    candidates = []
    try:
        q = yf.EquityQuery("and", [
            yf.EquityQuery("btwn", ["intradayprice", PRICE_MIN, PRICE_MAX]),
            yf.EquityQuery("gt", ["percentchange", MIN_DAY_GAIN_PCT]),
            yf.EquityQuery("is-in", ["exchange", "NMS", "NYQ", "ASE", "NGM", "NCM"]),
        ])
        resp = yf.screen(q, sortField="dayvolume", sortAsc=False, size=size)
        candidates = [r["symbol"] for r in resp.get("quotes", [])]
        print(f"Stage 1: Yahoo screener found {len(candidates)} stocks "
              f"${PRICE_MIN:.0f}-${PRICE_MAX:.0f} up >={MIN_DAY_GAIN_PCT:.0f}%: "
              f"{', '.join(candidates) or 'none'}\n")
    except Exception as e:
        print(f"Custom screener query failed ({e}); falling back to "
              f"predefined day_gainers list...")
        try:
            resp = yf.screen("day_gainers", size=100)
            candidates = [r["symbol"] for r in resp.get("quotes", [])
                          if PRICE_MIN <= r.get("regularMarketPrice", 0) <= PRICE_MAX]
            print(f"Stage 1 (fallback): {len(candidates)} day-gainers in the "
                  f"price band: {', '.join(candidates) or 'none'}\n")
        except Exception as e2:
            print(f"Screener unavailable: {e2}")
            return

    if not candidates:
        print("No stocks in the market currently match price band + 10% gain."
              "\n(Normal outside weekday market hours -- gappers appear "
              "7-10 AM ET on news days.)")
        return

    print("Stage 2: full rule check on each candidate:")
    cmd_screen(candidates)


# ---------------------------------------------------------------------------
# Surge -> dip -> reversal trade simulation (rules 6, 7, 9)
# ---------------------------------------------------------------------------

# named buy-pattern sets for experimentation (candletest command)
BUY_SETS = {
    "all_bullish": None,  # None = accept every bullish pattern (default)
    "hammer_family": {"hammer", "inverted_hammer", "dragonfly_doji"},
    "engulfing_only": {"bullish_engulfing"},
    "multi_candle": {"morning_star", "rising_three", "tweezer_bottom"},
    "strong_reversal": {"bullish_engulfing", "hammer", "morning_star"},
}

# sell modes: how bearish patterns are used for the exit
SELL_MODES = {
    "target_stop_only": "exit only at +target / -stop",
    "bearish_if_profit": "bearish pattern exits only when profitable (default)",
    "strong_if_profit": "only engulfing/evening star/3 crows, when profitable",
    "bearish_always": "any bearish pattern exits immediately, even at a loss",
}
STRONG_BEARISH = {"bearish_engulfing", "evening_star", "evening_doji_star",
                  "three_black_crows"}


_USE_DEFAULT = object()  # sentinel: None must stay meaning "all patterns"


def simulate_trades(df1m: pd.DataFrame, verbose: bool = True,
                    buy_set=_USE_DEFAULT,
                    sell_mode: str = DEFAULT_SELL_MODE,
                    vol_confirm: bool = True,
                    max_trades: int | None = None,
                    sell_set: set | None = None,
                    same_day_exit: bool = True,
                    budget: float | None = None,
                    compound: bool = False,
                    target_pct: float | None = None,
                    stop_pct: float | None = None,
                    prev_close: float | None = None,
                    trail_pct: float | None = None) -> list[dict]:
    """Run the entry/exit state machine over 1-min bars of a single day.

    State machine:
      SCAN    -- look for a strong surge (+SURGE_PCT within SURGE_WINDOW_MIN)
      DIPPING -- surge found; wait for a dip >= DIP_MIN_CENTS off the high
      ARMED   -- dip in progress; buy on first bullish reversal candle
      LONG    -- in position; sell at +$0.18-0.20, stop -$0.15,
                 or bearish candlestick while profitable
    """
    cd = Candles(df1m)
    trades = []
    state = "SCAN"
    surge_high = 0.0
    entry = 0.0
    entry_i = -1
    budget_cur = budget if budget is not None else POSITION_DOLLARS

    for i in range(1, cd.n):
        price = cd.c[i]

        if state == "SCAN":
            j = max(0, i - SURGE_WINDOW_MIN)
            low_w = cd.l[j:i + 1].min()
            if low_w > 0 and (cd.h[i] / low_w - 1) * 100 >= SURGE_PCT:
                state = "DIPPING"
                surge_high = cd.h[i]

        elif state == "DIPPING":
            surge_high = max(surge_high, cd.h[i])
            if surge_high - price >= DIP_MIN_CENTS:
                state = "ARMED"

        elif state == "ARMED":
            if max_trades is not None and len(trades) >= max_trades:
                break                          # daily trade budget used up
            # rule 3 at ENTRY time: stock must be up >10% vs yesterday's
            # close at the moment we buy, not just at scan time
            if (prev_close is not None
                    and price < prev_close * (1 + MIN_DAY_GAIN_PCT / 100)):
                continue
            if cd.h[i] > surge_high:          # dip failed, new high: re-surge
                surge_high = cd.h[i]
                state = "DIPPING"
                continue
            pats = cd.bullish_patterns(i)
            if pats and vol_confirm and not cd.volume_confirmed(i):
                pats = []                      # reversal without volume: skip
            pats += cd.indicator_bullish(i)    # RSI/MACD (no vol filter)
            if buy_set is _USE_DEFAULT:
                pats = [p for p in pats if p in BUY_SETS[DEFAULT_BUY_SET]]
            elif buy_set is not None:
                pats = [p for p in pats if p in buy_set]
            if pats:                           # dip inverts upward -> BUY
                entry = price
                entry_i = i
                shares = int(budget_cur // entry)
                if shares < 1:
                    continue
                state = "LONG"
                peak = entry
                if verbose:
                    ts = cd.index[i].strftime("%m-%d %H:%M")
                    print(f"  BUY  {ts}  @{entry:.2f}  ({shares} sh = "
                          f"${shares * entry:,.0f})  pattern={pats[0]}")

        elif state == "LONG":
            # no-day-trade mode: selling is allowed only on a LATER day than
            # the buy (avoids PDT day-trade round trips). Note: this also
            # means the stop cannot execute until the next day -- overnight
            # gap risk is accepted by design in this mode.
            if (not same_day_exit
                    and cd.index[i].date() == cd.index[entry_i].date()):
                continue
            if trail_pct is not None:
                # trailing exit: ride the runner, sell on trail% retrace
                # from the highest price since entry (no fixed target)
                peak = max(peak, cd.h[i])
                target_lo = target_hi = float("inf")
                trail_px = peak * (1 - trail_pct / 100)
                stop = max(entry * (1 - (stop_pct or 5) / 100), trail_px)
            elif target_pct is not None:
                target_lo = target_hi = entry * (1 + target_pct / 100)
                stop = entry * (1 - (stop_pct or 1.5) / 100)
            else:
                target_lo = entry + GAIN_PER_SHARE
                target_hi = entry + GAIN_PER_SHARE_MAX
                stop = entry - LOSS_PER_SHARE
            exit_px = None
            reason = ""
            if cd.l[i] <= stop:
                exit_px, reason = stop, f"stop {stop - entry:+.2f}"
            elif cd.h[i] >= target_lo:
                exit_px = min(target_hi, cd.h[i])
                reason = f"target +{exit_px - entry:.2f}"
            elif sell_mode != "target_stop_only":
                bears = cd.bearish_patterns(i) + cd.indicator_bearish(i)
                if sell_set is not None:
                    bears = [b for b in bears if b in sell_set]
                elif sell_mode == "strong_if_profit":
                    bears = [b for b in bears if b in STRONG_BEARISH]
                if bears and (price > entry or sell_mode == "bearish_always"):
                    exit_px, reason = price, f"bearish {bears[0]}"
            if exit_px is not None:
                pnl = (exit_px - entry) * shares
                trades.append({
                    "entry_time": cd.index[entry_i], "entry": round(entry, 2),
                    "exit_time": cd.index[i], "exit": round(exit_px, 2),
                    "reason": reason, "pnl": round(pnl, 2),
                })
                if verbose:
                    ts = cd.index[i].strftime("%m-%d %H:%M")
                    print(f"  SELL {ts}  @{exit_px:.2f}  {reason}  "
                          f"P&L ${pnl:+,.2f}")
                if compound:
                    budget_cur += pnl
                state = "SCAN"

    # HARD RULE: whatever was bought in this session's bars is sold before
    # the session ends -- any open position is flattened at the last bar.
    # (For 7-10 AM window data that means sold by 10:00 AM the same day.)
    if state == "LONG":
        exit_px = cd.c[cd.n - 1]
        pnl = (exit_px - entry) * shares
        trades.append({
            "entry_time": cd.index[entry_i], "entry": round(entry, 2),
            "exit_time": cd.index[cd.n - 1], "exit": round(exit_px, 2),
            "reason": "window-close flatten", "pnl": round(pnl, 2),
        })
        if verbose:
            ts = cd.index[cd.n - 1].strftime("%m-%d %H:%M")
            print(f"  SELL {ts}  @{exit_px:.2f}  window-close flatten  "
                  f"P&L ${pnl:+,.2f}")

    return trades


def _enforce_price_band(symbol: str, df: pd.DataFrame) -> bool:
    """This strategy is ONLY for $2-$16 stocks (rule 1). Refuse others."""
    price = float(df["Close"].iloc[-1])
    if not (PRICE_MIN <= price <= PRICE_MAX):
        print(f"{symbol.upper()} is ${price:.2f} -- outside the ${PRICE_MIN:.0f}-"
              f"${PRICE_MAX:.0f} penny-stock band. This strategy does not apply:"
              f" the $0.18/-$0.15 per-share targets only make sense at penny"
              f" prices. Pick a $2-$16 stock (see: python penny-stocks.py screen).")
        return False
    return True


def cmd_backtest(symbol: str, days: int) -> None:
    # penny stocks are DAY-TRADED in the 7-10 AM ET window ONLY: shares
    # bought in the window are ALWAYS sold within the same day's window
    # (flattened by 10:00 AM at the latest -- never held past the window)
    window_data = _window_data([symbol], days)
    entry = window_data.get(symbol.upper())
    if not entry or entry["bars"].empty:
        print(f"No usable 7-10 AM window data for {symbol}")
        return
    w, prev_map = entry["bars"], entry["prev"]

    all_trades = []
    for day, day_df in w.groupby(w.index.date):
        if len(day_df) < 20:
            continue
        print(f"\n{symbol.upper()}  {day}  7-10 AM  "
              f"(open {day_df['Open'].iloc[0]:.2f}, "
              f"window close {day_df['Close'].iloc[-1]:.2f})")
        trades = simulate_trades(day_df, prev_close=prev_map.get(day))
        if not trades:
            print("  no setups triggered (or not up 10%+)")
        all_trades.extend(trades)

    if all_trades:
        pnl = sum(tr["pnl"] for tr in all_trades)
        ret_pct = pnl / POSITION_DOLLARS * 100
        print(f"\n{'=' * 60}")
        print(f"  {len(all_trades)} trades | {ret_pct:+.1f}% on "
              f"${POSITION_DOLLARS} | total P&L ${pnl:+,.2f}")


def cmd_candletest(symbols: list[str], days: int) -> None:
    """Grid-test buy-pattern sets x sell modes in the 7-10 AM ET window."""
    window_data = _window_data(symbols, days)
    if not window_data:
        print("No usable data.")
        return

    print(f"\nGrid: {len(BUY_SETS)} buy sets x {len(SELL_MODES)} sell modes, "
          f"7-10 AM ET only, ${POSITION_DOLLARS}/trade, "
          f"target +${GAIN_PER_SHARE:.2f} / stop -${LOSS_PER_SHARE:.2f}\n")

    rows = []
    for buy_name, buy_set in BUY_SETS.items():
        for sell_name in SELL_MODES:
            total_pnl = 0.0
            n_trades = 0
            n_wins = 0
            for sym, wd in window_data.items():
                w = wd["bars"]
                for day, day_df in w.groupby(w.index.date):
                    if len(day_df) < 20:
                        continue
                    trades = simulate_trades(day_df, verbose=False,
                                             buy_set=buy_set,
                                             sell_mode=sell_name,
                                             prev_close=wd["prev"].get(day))
                    total_pnl += sum(tr["pnl"] for tr in trades)
                    n_trades += len(trades)
                    n_wins += sum(1 for tr in trades if tr["pnl"] > 0)
            rows.append((total_pnl, n_trades, n_wins, buy_name, sell_name))

    rows.sort(reverse=True)
    print(f"{'BUY SET':<17} {'SELL MODE':<19} {'Trades':>6} {'Ret%':>6} "
          f"{'Total P&L':>10}")
    print("-" * 62)
    for pnl, n, w, bn, sn in rows:
        ret = pnl / POSITION_DOLLARS * 100
        print(f"{bn:<17} {sn:<19} {n:>6} {ret:>+5.1f}% {pnl:>+10,.2f}")
    best = rows[0]
    print(f"\nBest in window: buy={best[3]}, sell={best[4]} "
          f"-> ${best[0]:+,.2f} over {best[1]} trades")


def _window_data(symbols: list[str], days: int,
                 min_price: float | None = None) -> dict:
    """Fetch 1-min bars (incl. premarket) restricted to 7-10 AM ET.

    The $2-$16 band is checked PER DAY at that day's first window price --
    a stock that later ran to $20 still counts on the days it was in band
    (that is exactly when the strategy would have traded it).
    """
    out = {}
    for sym in symbols:
        t = yf.Ticker(sym.upper())
        # rule 8: float must be <= 16M shares -- oversized floats are not
        # tradeable under this strategy at all (unknown float passes,
        # best effort: yfinance float data is patchy for small caps)
        try:
            flt = (t.info or {}).get("floatShares")
        except Exception:
            flt = None
        if flt is not None and flt > MAX_FLOAT:
            print(f"{sym.upper()}: float {flt / 1e6:.1f}M > "
                  f"{MAX_FLOAT / 1e6:.0f}M limit, symbol excluded")
            continue
        df = t.history(period=f"{min(days, 7)}d", interval="1m", prepost=True)
        if df.empty:
            print(f"{sym}: no 1-min data, skipped")
            continue
        df.index = df.index.tz_convert(ET)
        w = df[(df.index.time >= NEWS_START) & (df.index.time < NEWS_END)]
        lo = min_price if min_price is not None else PRICE_MIN
        keep = []
        for day, day_df in w.groupby(w.index.date):
            open_px = float(day_df["Open"].iloc[0])
            if lo <= open_px <= PRICE_MAX:
                keep.append(day_df)
            else:
                print(f"  {sym.upper()} {day}: window open ${open_px:.2f} "
                      f"outside ${lo:.0f}-{PRICE_MAX:.0f} band, day skipped")
        w = pd.concat(keep) if keep else w.iloc[0:0]
        print(f"{sym.upper()}: {len(w)} one-min bars 7-10 AM ET across "
              f"{len({d for d in w.index.date})} in-band days")
        if len(w):
            # per window day, from daily bars: previous close (up->10% rule)
            # and relative volume vs the trailing 50-day average (5x rule)
            prev_map = {}
            rvol_map = {}
            try:
                daily = t.history(period="4mo")
                ddates = [d.date() for d in daily.index]
                dcloses = daily["Close"].values
                dvols = daily["Volume"].values
                for k in range(1, len(ddates)):
                    prev_map[ddates[k]] = float(dcloses[k - 1])
                    lo_k = max(0, k - REL_VOLUME_LOOKBACK)
                    avg = dvols[lo_k:k].mean()
                    rvol_map[ddates[k]] = float(dvols[k] / avg) if avg > 0 else 0.0
            except Exception:
                pass
            out[sym.upper()] = {"bars": w, "prev": prev_map, "rvol": rvol_map}
    return out


def cmd_gridtest(symbols: list[str], days: int) -> None:
    """Grid: buy-pattern set x trades-per-day cap, 7-10 AM ET window.

    '1 trade buy & 1 trade sell' = cap 1; 'n trades' = cap 2, 3, unlimited.
    Sell mode fixed at the calibrated default. $POSITION_DOLLARS per trade.
    """
    window_data = _window_data(symbols, days)
    if not window_data:
        print("No usable data.")
        return

    caps = [1, 2, 3, None]
    print(f"\nGrid: {len(BUY_SETS)} buy sets x trades/day caps {caps}, "
          f"7-10 AM ET, ${POSITION_DOLLARS}/trade, "
          f"sell={DEFAULT_SELL_MODE}, vol confirm on\n")

    rows = []
    for buy_name, buy_set in BUY_SETS.items():
        for cap in caps:
            total_pnl = 0.0
            n_trades = 0
            n_wins = 0
            n_days = 0
            for sym, wd in window_data.items():
                w = wd["bars"]
                for day, day_df in w.groupby(w.index.date):
                    if len(day_df) < 20:
                        continue
                    n_days += 1
                    trades = simulate_trades(
                        day_df, verbose=False, buy_set=buy_set,
                        sell_mode=DEFAULT_SELL_MODE, max_trades=cap,
                        prev_close=wd["prev"].get(day))
                    total_pnl += sum(tr["pnl"] for tr in trades)
                    n_trades += len(trades)
                    n_wins += sum(1 for tr in trades if tr["pnl"] > 0)
            rows.append((total_pnl, n_trades, n_wins, n_days, buy_name, cap))

    rows.sort(key=lambda r: r[0], reverse=True)
    print(f"{'BUY SET':<17} {'TRADES/DAY':>10} {'Trades':>7} {'Ret%':>6} "
          f"{'P&L/trade':>10} {'Total P&L':>10}")
    print("-" * 66)
    for pnl, n, w, nd, bn, cap in rows:
        ret = pnl / POSITION_DOLLARS * 100
        per = pnl / n if n else 0
        cap_s = "unlimited" if cap is None else str(cap)
        print(f"{bn:<17} {cap_s:>10} {n:>7} {ret:>+5.1f}% "
              f"{per:>+10.2f} {pnl:>+10,.2f}")
    best = rows[0]
    print(f"\nBest: buy={best[4]}, trades/day="
          f"{'unlimited' if best[5] is None else best[5]} "
          f"-> ${best[0]:+,.2f} over {best[1]} trades")


class EtradeVolumeFeed:
    """Live per-minute volume from E*TRADE quotes -- works in EXTENDED hours.

    yfinance premarket 1-min bars report Volume=0, which silently disables
    the volume-confirmation filter before 9:30. E*TRADE's quote API returns
    cumulative totalVolume in real time (and an ExtendedHourQuoteDetail block
    in pre/post market), so polling it and diffing consecutive samples gives
    true per-minute volume during 7-10 AM.

    Backtests still use yfinance: E*TRADE has NO historical intraday data.
    """

    def __init__(self, sandbox: bool = True):
        from trading.api_wrapper import ETradeSession
        self.sess = ETradeSession(sandbox=sandbox)
        if not self.sess._load_saved_token():
            raise RuntimeError(
                "No valid E*TRADE token. Run: python plan/sandbox_auth.py "
                "--auth (then --verifier CODE)")
        self.samples = {}   # sym -> list of (datetime_et, total_volume, last)

    def sample(self, symbols: list[str]) -> None:
        """Poll quotes once; append (now, totalVolume, lastPrice) per symbol."""
        now = datetime.now(ET)
        quotes = self.sess.get_quotes([s.upper() for s in symbols])
        for sym, qd in quotes.items():
            all_q = qd.get("All", {})
            ext = all_q.get("ExtendedHourQuoteDetail", {})
            total_vol = all_q.get("totalVolume")
            last = ext.get("lastPrice") or all_q.get("lastTrade")
            if total_vol is None:
                continue
            self.samples.setdefault(sym, []).append(
                (now, int(total_vol), float(last or 0)))

    def minute_volumes(self, symbol: str) -> dict:
        """Per-minute traded volume derived from cumulative totalVolume."""
        pts = self.samples.get(symbol.upper(), [])
        out = {}
        for k in range(1, len(pts)):
            t0, v0, _ = pts[k - 1]
            t1, v1, _ = pts[k]
            minute = t1.replace(second=0, microsecond=0)
            out[minute] = out.get(minute, 0) + max(0, v1 - v0)
        return out

    def volume_confirmed_live(self, symbol: str,
                              mult: float = ENTRY_VOL_MULT,
                              avg_bars: int = VOL_AVG_BARS) -> bool:
        """Live equivalent of Candles.volume_confirmed for the last minute."""
        mv = sorted(self.minute_volumes(symbol).items())
        if len(mv) < 2:
            return True    # not enough samples yet -- best effort pass
        *hist, (last_min, last_vol) = mv
        vols = [v for _, v in hist[-avg_bars:]]
        avg = sum(vols) / len(vols) if vols else 0
        if avg <= 0:
            return True
        return last_vol >= mult * avg


def cmd_volume(symbols: list[str], minutes: int, sandbox: bool) -> None:
    """Poll E*TRADE quotes and print derived per-minute volume (extended
    hours capable). Demonstrates the live volume feed end-to-end."""
    import time as _time
    try:
        feed = EtradeVolumeFeed(sandbox=sandbox)
    except Exception as e:
        print(f"E*TRADE feed unavailable: {e}")
        return
    env = "SANDBOX" if sandbox else "PROD"
    print(f"Polling {env} quotes every 15s for {minutes} min: "
          f"{', '.join(s.upper() for s in symbols)}  (Ctrl+C to stop)")
    end = datetime.now(ET) + timedelta(minutes=minutes)
    try:
        while datetime.now(ET) < end:
            feed.sample(symbols)
            for sym in symbols:
                sym = sym.upper()
                pts = feed.samples.get(sym, [])
                if pts:
                    _, tv, last = pts[-1]
                    conf = feed.volume_confirmed_live(sym)
                    print(f"  {datetime.now(ET).strftime('%H:%M:%S')} {sym}: "
                          f"last ${last:.2f}, cumVol {tv:,}, "
                          f"volConfirm={'Y' if conf else 'n'}")
            _time.sleep(15)
    except KeyboardInterrupt:
        pass
    for sym in symbols:
        mv = feed.minute_volumes(sym)
        if mv:
            print(f"\n{sym.upper()} per-minute volume (derived):")
            for minute, vol in sorted(mv.items()):
                print(f"  {minute.strftime('%H:%M')}  {vol:,}")


BULLISH_PATTERNS = ["hammer", "inverted_hammer", "dragonfly_doji",
                    "bullish_spinning_top", "bullish_engulfing",
                    "tweezer_bottom", "morning_star", "rising_three",
                    "rsi_cross_up", "macd_cross_up"]
BEARISH_PATTERNS = ["hanging_man", "shooting_star", "gravestone_doji",
                    "bearish_spinning_top", "bearish_engulfing",
                    "tweezer_top", "evening_star", "evening_doji_star",
                    "three_black_crows", "falling_three",
                    "rsi_cross_down", "macd_cross_down"]


def cmd_pairtest(symbols: list[str], days: int) -> None:
    """One table per ENTRY candle; rows = EXIT candle. 8 x 10 = 80 combos.

    Each combo: buy only on that one bullish pattern (with volume confirm),
    exit on that one bearish pattern while profitable, target/stop always on.
    """
    window_data = _window_data(symbols, days)
    if not window_data:
        print("No usable data.")
        return

    print(f"\n{len(BULLISH_PATTERNS)} entry x {len(BEARISH_PATTERNS)} exit = "
          f"{len(BULLISH_PATTERNS) * len(BEARISH_PATTERNS)} combos | "
          f"7-10 AM ET | ${POSITION_DOLLARS}/trade | "
          f"target +${GAIN_PER_SHARE:.2f} / stop -${LOSS_PER_SHARE:.2f} | "
          f"vol confirm on")

    all_rows = []
    for buy_p in BULLISH_PATTERNS:
        print(f"\n=== ENTRY: {buy_p} ===")
        print(f"{'EXIT PATTERN':<22} {'Trades':>6} {'Ret%':>6} "
              f"{'P&L/trade':>10} {'Total P&L':>10}")
        print("-" * 58)
        for sell_p in BEARISH_PATTERNS:
            pnl = 0.0
            n = 0
            wins = 0
            for sym, wd in window_data.items():
                w = wd["bars"]
                for day, day_df in w.groupby(w.index.date):
                    if len(day_df) < 20:
                        continue
                    trades = simulate_trades(
                        day_df, verbose=False, buy_set={buy_p},
                        sell_set={sell_p}, prev_close=wd["prev"].get(day))
                    pnl += sum(tr["pnl"] for tr in trades)
                    n += len(trades)
                    wins += sum(1 for tr in trades if tr["pnl"] > 0)
            ret = pnl / POSITION_DOLLARS * 100
            per = pnl / n if n else 0
            print(f"{sell_p:<22} {n:>6} {ret:>+5.1f}% {per:>+10.2f} {pnl:>+10,.2f}")
            all_rows.append((pnl, n, wins, buy_p, sell_p))

    all_rows.sort(key=lambda r: r[0], reverse=True)
    print(f"\n{'=' * 70}")
    print("  TOP 10 ENTRY/EXIT COMBINATIONS")
    print(f"{'=' * 70}")
    print(f"{'ENTRY':<22} {'EXIT':<22} {'Trades':>6} {'Ret%':>6} {'Total P&L':>10}")
    for pnl, n, wins, bp, sp in all_rows[:10]:
        ret = pnl / POSITION_DOLLARS * 100
        print(f"{bp:<22} {sp:<22} {n:>6} {ret:>+5.1f}% {pnl:>+10,.2f}")
    best = all_rows[0]
    print(f"\nBEST: entry={best[3]} exit={best[4]} -> ${best[0]:+,.2f} "
          f"over {best[1]} trades")


def cmd_optimize(symbols: list[str], days: int, start_cap: float,
                 min_price: float | None = None) -> None:
    """Hunt for 2x: percent target/stop grid, all-in compounding, one gapper
    per day (the provided symbol with the highest 7-10 AM volume that day)."""
    window_data = _window_data(symbols, days, min_price=min_price)
    if not window_data:
        print("No usable data.")
        return

    # pick THE gapper to trade each day: must be up >= 10% in the window
    # (rule 3); among eligible stocks pick the biggest gainer. Days with no
    # 10%+ gapper are NOT traded at all.
    day_pick = {}
    for sym, wd in window_data.items():
        w = wd["bars"]
        for day, day_df in w.groupby(w.index.date):
            if len(day_df) < 20:
                continue
            prev = wd["prev"].get(day)
            if not prev:
                continue
            gain = (float(day_df["High"].max()) / prev - 1) * 100
            rvol = wd["rvol"].get(day, 0.0)
            if gain < MIN_DAY_GAIN_PCT or rvol < MIN_REL_VOLUME:
                continue   # rules: up >=10% AND relative volume >= 5x
            if day not in day_pick or gain > day_pick[day][1]:
                day_pick[day] = (sym, gain, day_df, prev)
    days_sorted = sorted(day_pick)
    if not days_sorted:
        print("\nNo day had a 10%+ gapper among these symbols -- no trades.")
        return
    print(f"\nDay -> traded gapper (up>=10% AND rvol>=5x): " + ", ".join(
        f"{d} {day_pick[d][0]}(+{day_pick[d][1]:.0f}%)" for d in days_sorted))
    print(f"All-in compounding from ${start_cap:,.0f}, entries="
          f"{DEFAULT_BUY_SET}+vol confirm, sell={DEFAULT_SELL_MODE}, "
          f"7-10 AM ET, same-day exits\n")

    targets = [2, 3, 5, 8, 10, 15, 20, 30]
    stops = [1, 1.5, 2, 3, 5, 8]
    rows = []
    for tp in targets:
        for sp in stops:
            cap = start_cap
            n = 0
            for d in days_sorted:
                sym, _, day_df, prev = day_pick[d]
                trades = simulate_trades(
                    day_df, verbose=False, budget=cap, compound=True,
                    target_pct=tp, stop_pct=sp, prev_close=prev)
                cap += sum(tr["pnl"] for tr in trades)
                n += len(trades)
            rows.append((cap, n, f"+{tp}%", f"-{sp}%"))
    # trailing-exit configs (ride the runner) x entry style
    for trail in [10, 15, 20, 25]:
        for entry_name, bset, vc in [("hammer", _USE_DEFAULT, True),
                                     ("allpat", None, False)]:
            cap = start_cap
            n = 0
            for d in days_sorted:
                sym, _, day_df, prev = day_pick[d]
                trades = simulate_trades(
                    day_df, verbose=False, budget=cap, compound=True,
                    trail_pct=trail, stop_pct=5, prev_close=prev,
                    buy_set=bset, vol_confirm=vc)
                cap += sum(tr["pnl"] for tr in trades)
                n += len(trades)
            rows.append((cap, n, f"trail{trail}%", entry_name))
    # baseline: current cent-based defaults, compounded the same way
    cap = start_cap
    n = 0
    for d in days_sorted:
        sym, _, day_df, prev = day_pick[d]
        trades = simulate_trades(day_df, verbose=False, budget=cap,
                                 compound=True, prev_close=prev)
        cap += sum(tr["pnl"] for tr in trades)
        n += len(trades)
    rows.append((cap, n, "cents", "(def)"))

    rows.sort(key=lambda r: r[0], reverse=True)
    print(f"{'EXIT':>9} {'STOP/ENT':>9} {'Trades':>6} {'Final $':>10} "
          f"{'Ret%':>8}  {'2x?':>4}")
    print("-" * 52)
    for cap, n, tps, sps in rows:
        ret = (cap / start_cap - 1) * 100
        flag = "YES" if cap >= 2 * start_cap else ""
        print(f"{tps:>9} {sps:>9} {n:>6} {cap:>10,.2f} {ret:>+7.1f}%  {flag:>4}")
    best = rows[0]
    print(f"\nBest: {best[2]} / {best[3]} -> "
          f"${best[0]:,.2f} ({(best[0] / start_cap - 1) * 100:+.1f}%) "
          f"{'-- 2x REACHED' if best[0] >= 2 * start_cap else '-- 2x not reached in this sample'}")


def cmd_patterns(symbol: str) -> None:
    t = yf.Ticker(symbol.upper())
    df = t.history(period="1d", interval="1m", prepost=False)
    if df.empty:
        print(f"No 1-min data for {symbol}")
        return
    if not _enforce_price_band(symbol, df):
        return
    df.index = df.index.tz_convert(ET)
    cd = Candles(df)
    found = 0
    for i in range(cd.n):
        bulls = cd.bullish_patterns(i)
        bears = cd.bearish_patterns(i)
        neut = cd.neutral_patterns(i)
        if bulls or bears:
            ts = cd.index[i].strftime("%H:%M")
            tags = [f"+{p}" for p in bulls] + [f"-{p}" for p in bears]
            if neut:
                tags += [f"={p}" for p in neut]
            print(f"{ts}  {cd.c[i]:>8.2f}  {' '.join(tags)}")
            found += 1
    print(f"\n{found} pattern bars out of {cd.n} candles")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("scan", help="discover candidates market-wide, then screen")
    sc.add_argument("--size", type=int, default=50)

    s = sub.add_parser("screen", help="run the 6-rule screener on given symbols")
    s.add_argument("symbols", nargs="+")

    b = sub.add_parser("backtest", help="simulate surge-dip-reversal trades")
    b.add_argument("symbol")
    b.add_argument("--days", type=int, default=5)

    pt = sub.add_parser("patterns", help="label 1-min candles for today")
    pt.add_argument("symbol")

    ct = sub.add_parser("candletest",
                        help="grid-test candle buy/sell configs 7-10 AM ET")
    ct.add_argument("symbols", nargs="+")
    ct.add_argument("--days", type=int, default=5)

    gt = sub.add_parser("gridtest",
                        help="grid buy sets x trades/day cap, 7-10 AM ET")
    gt.add_argument("symbols", nargs="+")
    gt.add_argument("--days", type=int, default=5)

    pr = sub.add_parser("pairtest",
                        help="every entry candle x every exit candle (+RSI/MACD)")
    pr.add_argument("symbols", nargs="+")
    pr.add_argument("--days", type=int, default=5)

    op = sub.add_parser("optimize",
                        help="pct target/stop grid, compounding, hunt for 2x")
    op.add_argument("symbols", nargs="+")
    op.add_argument("--days", type=int, default=5)
    op.add_argument("--capital", type=float, default=1000.0)
    op.add_argument("--min-price", type=float, default=None,
                    help="experiment: override the $2 band floor")

    vo = sub.add_parser("volume",
                        help="live per-minute volume via E*TRADE (extended hours)")
    vo.add_argument("symbols", nargs="+")
    vo.add_argument("--minutes", type=int, default=5)
    vo.add_argument("--prod", action="store_true",
                    help="use PROD keys/token instead of sandbox")

    args = p.parse_args()
    if args.cmd == "scan":
        cmd_scan(args.size)
    elif args.cmd == "screen":
        cmd_screen(args.symbols)
    elif args.cmd == "backtest":
        cmd_backtest(args.symbol, args.days)
    elif args.cmd == "patterns":
        cmd_patterns(args.symbol)
    elif args.cmd == "candletest":
        cmd_candletest(args.symbols, args.days)
    elif args.cmd == "gridtest":
        cmd_gridtest(args.symbols, args.days)
    elif args.cmd == "pairtest":
        cmd_pairtest(args.symbols, args.days)
    elif args.cmd == "optimize":
        cmd_optimize(args.symbols, args.days, args.capital, args.min_price)
    elif args.cmd == "volume":
        cmd_volume(args.symbols, args.minutes, sandbox=not args.prod)


if __name__ == "__main__":
    main()
