"""Penny-stock momentum day-trading strategy (Cameron Ross style).

The strategy in one line: find a low-float penny stock gapping up on fresh
morning news with huge relative volume, wait for the first dip after a strong
surge, buy when the dip reverses upward on a hammer-family candle (hammer,
inverted hammer, dragonfly doji) WITH momentum-volume confirmation (>=1.5x
trailing average volume), sell at 2x the risk (+$0.30 vs -$0.15 stop) or on a
strong bearish pattern while profitable. Defaults calibrated via candletest.

Screening rules (all must pass):
  1. Price between $2 and $14 (was $16; cap matrix 2026-08-03)
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
  python day-trading.py screen SYM1 SYM2 ...     # run the 6-rule screener
  python day-trading.py patterns SYM             # label 1-min candles today
  python day-trading.py backtest SYM [--days N]  # sim surge-dip-reversal trades
                                                  # on recent 1-min data (max ~7d)

Data source: yfinance. Honest limitations: news timestamps are approximate and
incomplete, float data is patchy for small caps, and 1-min history only goes
back ~7 days -- a production version needs a real-time scanner feed.
"""

import argparse
import json
import sys
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

ET = ZoneInfo("America/New_York")

# ---------------------------------------------------------------------------
# Robinhood data caches (populated via the robinhood-trading MCP by Claude --
# see .claude/skills/penny-morning.md). Both are gitignored under data/.
# ---------------------------------------------------------------------------
RH_BARS_DIR = Path("data/rh_bars")       # {SYM}_{YYYY-MM-DD}.csv 1-min bars
RH_FUND_FILE = Path("data/rh_fundamentals.json")  # {SYM: {...}} fundamentals
RH_SCAN_ID = "5f132877-7730-4a18-9e72-b3f0d2c9df83"  # saved Robinhood scan:
# Last $2-14, %Change>=10 (1d), RelVolume>=5x (30d), %Chg desc (no float filter)


def load_rh_fundamentals() -> dict:
    """Robinhood fundamentals cache: float, sector, industry, avg volumes."""
    try:
        with open(RH_FUND_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def load_rh_bars(symbol: str) -> pd.DataFrame | None:
    """Load cached Robinhood 1-min bars (REAL premarket volume, unlike
    yfinance). Files: data/rh_bars/{SYM}_{YYYY-MM-DD}.csv with columns
    begins_at (UTC), open, high, low, close, volume. Interpolated gap-fill
    bars must not be written to the cache."""
    files = sorted(RH_BARS_DIR.glob(f"{symbol.upper()}_*.csv"))
    if not files:
        return None
    df = pd.concat([pd.read_csv(f) for f in files])
    df["begins_at"] = (pd.to_datetime(df["begins_at"], utc=True)
                       .dt.tz_convert(ET))
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    df = df.set_index("begins_at").sort_index()
    return df[["Open", "High", "Low", "Close", "Volume"]]

# ---------------------------------------------------------------------------
# Strategy configuration (rules 1-8)
# ---------------------------------------------------------------------------
PRICE_MIN = 2.00                 # rule 1: $2 floor stays (sub-$2 = untradeable junk)
PRICE_MAX = float("inf")         # CEILING REMOVED 2026-08-03 (C1 adoption):
                                 # full-year 1-min backtest: no-ceiling
                                 # +$259,341 vs $14-cap +$163,989, ZERO
                                 # negative months vs 3 -- in cold months the
                                 # capped menu is junk while pricier gappers
                                 # still trend. Set 14.0/16.0 to re-cap.
TOP_GAPPERS_PER_DAY = 1          # $15k/day TOTAL (user constraint): top-1
                                 # x $15k beat top-2 x $7.5k (+$194k vs
                                 # +$143k/yr; worst -$5.1k vs -$5.7k)
MAX_GAP_AT_7AM = 20.0            # CALM-GAP RULE (2026-08-03 pattern study):
                                 # pick the highest-gain qualifying gapper
                                 # whose 7AM price is <= prev_close*1.20;
                                 # walk down the list (top-4) if the leader
                                 # opened hotter. Exhausted overnight gaps
                                 # (>20% at 7AM) bled -$100k/yr; the $2k+
                                 # days are INTRADAY developers. Full-year:
                                 # +$206,466, ZERO negative months.
NEWS_START = dtime(7, 0)         # trading window, ET (buy AND sell inside it)
NEWS_END = dtime(12, 0)          # extended 10:00 -> NOON 2026-08-03: V2 test
                                 # showed +54% total, best $/day (+$1,202);
                                 # the 10-12 stretch carries the second leg
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
MAX_FLOAT = None                 # rule 8 DROPPED 2026-08-03 (V2a adoption):
                                 # no-float-limit tested +$15k over V2 at
                                 # equal risk; float still displayed as info.
                                 # Set to e.g. 16_000_000 to re-enable.

# surge/dip detection for the entry setup (rule 9 summary)
SURGE_PCT = 2.0                  # "strong surge": +2% within the window
SURGE_WINDOW_MIN = 50            # 10->50 (2026-08-04 AX20 adoption): the
                                 # validated two-year backtests run 1-min
                                 # bars with a 50-bar surge window; 10 was
                                 # a 5-min-bar-era relic
DIP_MIN_CENTS = 0.05             # a real dip: >= 5c retrace from surge high

# DEFAULTS (recalibrated 2026-08-02 via the 60-day market-wide backtest:
# trail20+all-patterns +181% vs hammer default +30.8% on $1000):
# ALL bullish patterns for entry, no volume gate, ride with a 20% trailing
# stop / 5% hard stop. The old hammer calibration remains available to the
# experiment commands via BUY_SETS/SELL_MODES.
DEFAULT_ORB_BARS = 5             # C02 (2026-08-04): 5-min opening range
                                 # (15 was AX20; faster entry = +$79.6k/2yr)
DEFAULT_MAX_VOL_FRAC = 0.20      # C02: size up to 20% of trailing volume
DEFAULT_VOL_FRAC_WINDOW = 10     # ...measured over trailing 10 minutes
# C02 also adds a premarket-high stop-buy as an extra entry trigger
# (break of the premarket high, one-shot) -- pass extra_break_high.
DEFAULT_PRESSURE_TRAIL = (10, 0.30, 0.30, 12, 30)
                                 # C11 (2026-08-04): volume-pressure
                                 # modulated trail -- tighten to 12% when
                                 # rolling 10-min sell pressure <= -0.3,
                                 # widen to 30% when buy pressure >= +0.3
DEFAULT_ENTRY_END = dtime(12, 0)   # strict window: entries end noon
DEFAULT_EXIT_END = dtime(12, 0)    # 1PM extension tested (C11 +$66k/2yr)
                                 # but WITHDRAWN by user 2026-08-04 --
                                 # everything flat by NOON, same day
DEFAULT_TRAIL_PCT = 20.0         # trailing exit: sell on 20% retrace from peak
DEFAULT_STOP_PCT = 8.0           # 5->8 (2026-08-03 AX16/AX18: +$4.7k Y1,
                                 # +$9k Y2 -- survives weak-year shakeouts)
DEFAULT_SCALE_OUT_AT = 25.0      # AX06/AX18: bank 1/3 at +25%, trail rest
DEFAULT_SCALE_OUT_FRAC = 0.33
DEFAULT_BUY_SET = "hammer_family"     # used only by legacy experiment paths
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

        # buy/sell volume-pressure proxy (X200): per-bar signed volume by
        # intrabar close position; halted/one-price bars contribute 0
        # signed volume but full volume (dampen toward neutral)
        rng = self.h - self.l
        with np.errstate(divide="ignore", invalid="ignore"):
            pos = np.where(rng > 0,
                           (2 * (self.c - self.l) - rng) / rng, 0.0)
        self.sv = self.v * pos
        self.csv = np.concatenate(([0.0], np.cumsum(self.sv)))
        self.cv = np.concatenate(([0.0], np.cumsum(self.v)))

    def pressure(self, i, n, min_vol=20_000):
        """Rolling buy/sell pressure over bars [i-n+1, i], in [-1, 1].

        Returns None when the window's volume is below min_vol -- callers
        treat None as 'signal untrusted' (entry gates fail conservatively,
        exit/trail conditions no-op).
        """
        if i < 0:
            return None
        j = max(0, i - n + 1)
        vol = self.cv[i + 1] - self.cv[j]
        if vol < min_vol or vol <= 0:
            return None
        return (self.csv[i + 1] - self.csv[j]) / vol

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

def _etrade_session():
    """Load an authenticated E*TRADE session: PROD token first (real data),
    sandbox second. Returns None if no valid token exists."""
    try:
        from trading.api_wrapper import ETradeSession
    except Exception:
        return None
    for sandbox in (False, True):
        try:
            sess = ETradeSession(sandbox=sandbox)
            if sess._load_saved_token():
                return sess
        except Exception:
            continue
    return None


def etrade_live_metrics(symbols: list[str]) -> dict:
    """Real-time price/gain/rvol per symbol from ONE batched E*TRADE quote
    call (replaces delayed yfinance daily data for rules 1, 3, 5).

    Works in extended hours via ExtendedHourQuoteDetail. Symbols missing
    from the response (e.g. sandbox canned data) are simply absent -- the
    caller falls back to yfinance for those.
    """
    sess = _etrade_session()
    if sess is None:
        return {}
    out = {}
    try:
        quotes = sess.get_quotes([s.upper() for s in symbols])
        for sym, qd in quotes.items():
            all_q = qd.get("All", {})
            ext = all_q.get("ExtendedHourQuoteDetail", {})
            last = ext.get("lastPrice") or all_q.get("lastTrade")
            prev = all_q.get("previousClose")
            tv = ext.get("volume") or all_q.get("totalVolume")
            av = all_q.get("averageVolume")
            if not last or not prev:
                continue
            out[sym] = {
                "price": float(last),
                "day_gain": (float(last) / float(prev) - 1) * 100,
                "rel_volume": (float(tv) / float(av)) if tv and av else 0.0,
                "quote_status": qd.get("quoteStatus", "?"),
                "shares_outstanding": all_q.get("sharesOutstanding"),
            }
    except Exception:
        return {}
    return out


HARAM_INDUSTRY_WORDS = ["bank", "gambling", "casino", "alcohol", "brewer",
                        "distiller", "tobacco", "defense", "aerospace",
                        "insurance", "lending", "mortgage", "adult"]


def halal_check(symbol: str, t=None, mcap: float | None = None) -> dict:
    """Halal compliance (same criteria as plan/full_screen.py and the
    /halal-check skill): loans/mcap <= 10%, deposits/mcap <= 10%,
    combined <= 20% (one side may exceed 10% if combined stays under 20),
    haram revenue < 5% (interest income / annualized revenue), plus a
    haram-industry keyword screen. Uses yfinance quarterly statements --
    call lazily (2-3 API requests)."""
    t = t or yf.Ticker(symbol)

    def get_val(df, names):
        if df is None or df.empty:
            return 0
        for n in names:
            if n in df.index:
                v = df.iloc[df.index.get_loc(n), 0]
                if not pd.isna(v):
                    return float(v)
        return 0

    try:
        bs = t.quarterly_balance_sheet
        inc = t.quarterly_income_stmt
    except Exception:
        bs = inc = None
    if mcap is None:
        rh = load_rh_fundamentals().get(symbol.upper())
        mcap = (rh or {}).get("market_cap")
        if not mcap:
            try:
                mcap = (t.info or {}).get("marketCap")
            except Exception:
                mcap = None
    mcap = float(mcap or 0)

    total_debt = get_val(bs, ["Total Debt"])
    cash_total = get_val(bs, ["Cash Cash Equivalents And Short Term Investments"])
    total_rev = get_val(inc, ["Total Revenue", "Operating Revenue"])
    interest_inc = get_val(inc, ["Interest Income",
                                 "Interest Income Non Operating",
                                 "Net Interest Income"])
    annual_rev = total_rev * 4

    loan_pct = (total_debt / mcap * 100) if mcap > 0 else 0
    cash_pct = (cash_total / mcap * 100) if mcap > 0 else 0
    combined = loan_pct + cash_pct
    haram_pct = (abs(interest_inc) / annual_rev * 100) if annual_rev > 0 else 0

    loan_ok = loan_pct <= 10 or combined <= 20
    cash_ok = cash_pct <= 10 or combined <= 20
    combined_ok = combined <= 20
    haram_ok = haram_pct < 5

    # industry screen: RH cache sector/industry first, yfinance fallback
    rh = load_rh_fundamentals().get(symbol.upper())
    ind = f"{(rh or {}).get('sector', '')} {(rh or {}).get('industry', '')}"
    if not ind.strip():
        try:
            info = t.info or {}
            ind = f"{info.get('sector', '')} {info.get('industry', '')}"
        except Exception:
            ind = ""
    industry_ok = not any(w in ind.lower() for w in HARAM_INDUSTRY_WORDS)

    halal = loan_ok and cash_ok and combined_ok and haram_ok and industry_ok
    return {
        "loan_pct": round(loan_pct, 2),
        "cash_pct": round(cash_pct, 2),
        "combined": round(combined, 2),
        "haram_pct": round(haram_pct, 2),
        "halal": halal,
        "fail_reason": "" if halal else (
            "HARAM INDUSTRY" if not industry_ok else
            "LOAN>10+COMBINED>20" if not loan_ok else
            "CASH>10+COMBINED>20" if not cash_ok else
            "COMBINED>20" if not combined_ok else
            "HARAM>=5%"
        ),
    }


def _finnhub_key() -> str | None:
    try:
        from trading.win_cred import get_secret
        return get_secret("FINNHUB_KEY")
    except Exception:
        return None


def news_within_18h(symbol: str, t=None,
                    now_et: datetime | None = None) -> tuple[bool, str]:
    """Rule 2: any news in the last NEWS_LOOKBACK_HOURS?

    Primary: Finnhub /company-news (dated, reliable timestamps, free tier).
    Fallback: yfinance Ticker.news. Returns (hit, headline).
    """
    now_et = now_et or datetime.now(ET)
    cutoff = now_et - timedelta(hours=NEWS_LOOKBACK_HOURS)

    key = _finnhub_key()
    if key:
        try:
            import urllib.request
            frm = (now_et - timedelta(days=2)).date().isoformat()
            to = now_et.date().isoformat()
            url = (f"https://finnhub.io/api/v1/company-news?symbol="
                   f"{symbol.upper()}&from={frm}&to={to}&token={key}")
            import json as _json
            with urllib.request.urlopen(url, timeout=15) as r:
                items = _json.load(r)
            for it in items:
                dt = datetime.fromtimestamp(it.get("datetime", 0), ET)
                if dt >= cutoff:
                    return True, "FH: " + (it.get("headline") or "")[:56]
            # no Finnhub hit -> ALSO check Yahoo (both sources consulted)
        except Exception:
            pass   # fall through to yfinance

    t = t or yf.Ticker(symbol)
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
                return True, "YF: " + (content.get("title") or "")[:56]
    except Exception:
        pass
    return False, ""


def screen_symbol(symbol: str, now_et: datetime | None = None,
                  live: dict | None = None) -> dict:
    """Run all screening rules on one symbol. Returns dict of checks.

    `live` (from etrade_live_metrics) supplies REAL-TIME price/gain/rvol;
    without it, delayed yfinance daily data is used.
    """
    now_et = now_et or datetime.now(ET)
    t = yf.Ticker(symbol)
    checks = {"symbol": symbol}

    if live:
        price = live["price"]
        day_gain = live["day_gain"]
        rel_vol = live["rel_volume"]
        checks["source"] = "etrade-live"
    else:
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
        avg_vol = float(
            daily["Volume"].iloc[-(REL_VOLUME_LOOKBACK + 1):-1].mean())
        rel_vol = today_vol / avg_vol if avg_vol > 0 else 0.0
        checks["source"] = "yfinance"

    checks["price"] = round(price, 2)
    checks["rule1_price_2_to_16"] = PRICE_MIN <= price <= PRICE_MAX
    checks["day_gain_pct"] = round(day_gain, 1)
    checks["rule3_up_10pct"] = day_gain >= MIN_DAY_GAIN_PCT
    checks["rel_volume"] = round(rel_vol, 1)
    checks["rule5_relvol_5x"] = rel_vol >= MIN_REL_VOLUME

    # LAZY gate order (each stage runs only if everything before passed):
    #   free rules (price band, +10%, rvol -- one data source)
    #   -> HALAL (debt/deposits/haram revenue + industry, quarterlies)
    #   -> float + hot sector (t.info / RH cache)
    #   -> news (Finnhub + Yahoo)
    # Halal runs FIRST among the expensive gates so no time or API calls
    # are wasted collecting full data on stocks that are not halal.
    checks["news"] = ""
    checks["halal_fail"] = ""
    checks["sector"] = ""
    checks["float_m"] = None
    checks["rule9_halal"] = None
    checks["rule4_hot_sector"] = None
    checks["rule8_float_under_16m"] = None
    checks["rule2_news_18h"] = None

    free_ok = (checks["rule1_price_2_to_16"] and checks["rule3_up_10pct"]
               and checks["rule5_relvol_5x"])
    if free_ok:
        h = halal_check(symbol, t)
        checks["rule9_halal"] = h["halal"]
        checks["halal_fail"] = h["fail_reason"]
        checks["halal_detail"] = (f"loans {h['loan_pct']}% dep {h['cash_pct']}% "
                                  f"comb {h['combined']}% haram {h['haram_pct']}%")

    if checks["rule9_halal"]:
        # float + sector -- Robinhood cache first, yfinance info fallback
        sector = ""
        flt = None
        rh = load_rh_fundamentals().get(symbol.upper())
        if rh:
            sector = f"{rh.get('sector', '')} / {rh.get('industry', '')}"
            flt = rh.get("float")
        if not sector.strip(" /") or flt is None:
            try:
                info = t.info or {}
                if not sector.strip(" /"):
                    sector = (f"{info.get('sector', '')} / "
                              f"{info.get('industry', '')}")
                if flt is None:
                    flt = info.get("floatShares")
            except Exception:
                pass
        checks["sector"] = sector
        checks["rule4_hot_sector"] = any(
            s in sector.lower() for s in HOT_SECTORS)
        checks["float_m"] = round(flt / 1e6, 1) if flt else None
        checks["rule8_float_under_16m"] = (
            True if MAX_FLOAT is None
            else (flt is not None and flt <= MAX_FLOAT))

    if (checks["rule9_halal"] and checks["rule4_hot_sector"]
            and checks["rule8_float_under_16m"]):
        hit, title = news_within_18h(symbol, t, now_et)
        checks["rule2_news_18h"] = hit
        checks["news"] = title

    rules = [k for k in checks if k.startswith("rule")]
    checks["PASS"] = all(bool(checks[k]) for k in rules)
    return checks


def cmd_screen(symbols: list[str]) -> None:
    live = etrade_live_metrics(symbols)
    if live:
        print(f"(real-time price/gain/rvol via E*TRADE for: "
              f"{sorted(live)}; yfinance fallback for the rest)")
    print(f"{'SYM':<6} {'PASS':<5} {'$':>6} {'1<16':>5} {'gain%':>6} {'r3':>3} "
          f"{'rvol':>5} {'r5':>3} {'halal':>6} {'news':>5} {'sector':>7} "
          f"{'floatM':>7} {'r8':>3}")
    print("-" * 86)
    passed = []
    for sym in symbols:
        c = screen_symbol(sym.upper(), live=live.get(sym.upper()))
        if "error" in c:
            print(f"{sym.upper():<6} ERROR {c['error']}")
            continue
        b = lambda v: "-" if v is None else ("Y" if v else ".")
        print(f"{c['symbol']:<6} {('PASS' if c['PASS'] else '-'):<5} "
              f"{c['price']:>6.2f} {b(c['rule1_price_2_to_16']):>5} "
              f"{c['day_gain_pct']:>6.1f} {b(c['rule3_up_10pct']):>3} "
              f"{c['rel_volume']:>5.1f} {b(c['rule5_relvol_5x']):>3} "
              f"{b(c['rule9_halal']):>6} "
              f"{b(c['rule2_news_18h']):>5} {b(c['rule4_hot_sector']):>7} "
              f"{(c['float_m'] if c['float_m'] is not None else '?'):>7} "
              f"{b(c['rule8_float_under_16m']):>3}")
        if c.get("halal_fail"):
            print(f"{'':<6}   NOT HALAL: {c['halal_fail']}  "
                  f"({c.get('halal_detail', '')})")
        if c["PASS"]:
            passed.append(c["symbol"])
    print(f"\nPassed all rules: {passed or 'none'}")


def cmd_scan(size: int) -> None:
    """Discover candidates market-wide, then run the full 6-rule screen.

    Stage 1 (coarse, Yahoo screener API): US stocks in the $2-PRICE_MAX band up >=10% today,
    sorted by day volume. Stage 2: full rule check (news window, sector,
    float, 5x rvol) on each candidate.
    """
    candidates = []
    try:
        q = yf.EquityQuery("and", [
            yf.EquityQuery("btwn", ["intradayprice", PRICE_MIN,
                            min(PRICE_MAX, 10000.0)]),
            yf.EquityQuery("gt", ["percentchange", MIN_DAY_GAIN_PCT]),
            yf.EquityQuery("is-in", ["exchange", "NMS", "NYQ", "ASE", "NGM", "NCM"]),
        ])
        resp = yf.screen(q, sortField="dayvolume", sortAsc=False, size=size)
        candidates = [r["symbol"] for r in resp.get("quotes", [])]
        print(f"Stage 1: Yahoo screener found {len(candidates)} stocks "
              f"${PRICE_MIN:.0f}+{'' if PRICE_MAX == float('inf') else f'-{PRICE_MAX:.0f}'} up >={MIN_DAY_GAIN_PCT:.0f}%: "
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
              "7AM-noon ET on news days.)")
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
                    trail_pct: float | None = None,
                    orb: bool = False,
                    orb_bars: int = 3,
                    max_vol_frac: float | None = None,
                    vol_frac_window: int = 1,
                    entry_cutoff=None,
                    scale_out_at: float | None = None,
                    scale_out_frac: float = 0.33,
                    trail_widen_at: float | None = None,
                    trail_wide: float = 30.0,
                    breakeven_at: float | None = None,
                    time_stop_min: int | None = None,
                    atr_trail: tuple | None = None,
                    atr_stop: tuple | None = None,
                    add_at: float | None = None,
                    extra_break_high: float | None = None,
                    slippage_bps: float | None = None,
                    orb_fill_mode: str | None = None,
                    scale_out_2: tuple | None = None,
                    pressure_entry: tuple | None = None,
                    pressure_entry_patterns: tuple | None = None,
                    gap_gate_pressure: tuple | None = None,
                    pressure_exit: tuple | None = None,
                    pressure_trail: tuple | None = None,
                    pressure_reentry: tuple | None = None,
                    pressure_min_vol: float = 20_000,
                    scale_out_pressure_skip: float | None = None,
                    scale_out_frac_pressure: tuple | None = None,
                    pmh_rearm: bool = False,
                    entry_cutoff_patterns=None,
                    wick_guard: float | None = None,
                    pressure_shuffle: bool = False) -> list[dict]:
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
    scaled = False
    scaled2 = False
    added = False
    dyn_trail = None
    dyn_stop = None
    reentry_used = 0
    last_exit_reason = ""
    slip = (slippage_bps or 0) / 10_000.0
    _shuffle_rng = None
    if pressure_shuffle:
        import random as _rnd
        _shuffle_rng = _rnd.Random(str(cd.index[0]) if cd.n else "x")

    def _atr_pct(i, k, lo, hi):
        """k x ATR14 as % of price at bar i, clipped to [lo, hi]."""
        j0 = max(1, i - 13)
        trs = [max(cd.h[j] - cd.l[j], abs(cd.h[j] - cd.c[j - 1]),
                   abs(cd.l[j] - cd.c[j - 1])) for j in range(j0, i + 1)]
        atr = sum(trs) / len(trs) if trs else 0.0
        px = cd.c[i] or 1.0
        return min(hi, max(lo, k * atr / px * 100))

    # Opening-Range Breakout (second entry trigger, complements dip-reversal):
    # OR = first orb_bars bars that printed volume; stop-buy on a break of
    # the OR high (ratcheted up after each failed/gated break)
    or_high = None
    or_end = -1
    if orb:
        vol_bars = [i for i in range(cd.n) if cd.v[i] > 0][:orb_bars]
        if len(vol_bars) == orb_bars:
            or_high = max(cd.h[i] for i in vol_bars)
            or_end = vol_bars[-1]

    def _entry_ok(px):
        if not (PRICE_MIN <= px <= PRICE_MAX):
            return False
        if (prev_close is not None
                and px < prev_close * (1 + MIN_DAY_GAIN_PCT / 100)):
            return False
        return True

    def _hi(i):
        """High of bar i, wick-guarded (X319): a lone spike whose high
        exceeds wick_guard x the neighboring closes is ignored for
        peak/scale-out/trail tracking (CIIT one-bar 50x lesson)."""
        h = cd.h[i]
        if wick_guard is None:
            return h
        ref = max(cd.c[i], cd.c[i - 1] if i > 0 else cd.c[i],
                  cd.c[i + 1] if i + 1 < cd.n else cd.c[i])
        return min(h, ref * wick_guard)

    def _pressure_gates_ok(i, px, patterns_entry=False):
        """Entry-side pressure gates; use bars <= i-1 only (fills are
        intrabar, bar i's close is future info). None pressure = fail."""
        if pressure_entry is not None:
            p = cd.pressure(i - 1, pressure_entry[0], pressure_min_vol)
            if p is None or p < pressure_entry[1]:
                return False
        if patterns_entry and pressure_entry_patterns is not None:
            p = cd.pressure(i - 1, pressure_entry_patterns[0],
                            pressure_min_vol)
            if p is None or p < pressure_entry_patterns[1]:
                return False
        if gap_gate_pressure is not None and prev_close:
            n, t, gap_pct = gap_gate_pressure
            if px > prev_close * (1 + gap_pct / 100):
                p = cd.pressure(i - 1, n, pressure_min_vol)
                if p is None or p < t:
                    return False
        return True

    for i in range(1, cd.n):
        price = cd.c[i]

        # entry cutoff: after this time no NEW positions (exits continue)
        entries_open = (entry_cutoff is None
                        or cd.index[i].time() < entry_cutoff)

        # ORB entry: allowed from any flat state (extra_break_high adds a
        # second one-shot stop-buy level, e.g. the premarket high)
        brk = None
        if (entries_open and state in ("SCAN", "DIPPING", "ARMED")
                and (max_trades is None or len(trades) < max_trades)):
            if or_high is not None and i > or_end and cd.h[i] > or_high:
                brk = ("ORB", max(or_high, cd.o[i]))
                or_high = cd.h[i]      # ratchet for the next break
            elif extra_break_high is not None and cd.h[i] > extra_break_high:
                brk = ("PMH-break", max(extra_break_high, cd.o[i]))
                extra_break_high = cd.h[i] if pmh_rearm else None
                                          # X312 re-arm vs one-shot
            elif (pressure_reentry is not None and trades
                  and reentry_used < (pressure_reentry[2]
                                      if len(pressure_reentry) > 2 else 1)
                  and (len(pressure_reentry) < 4
                       or pressure_reentry[3] == "any"
                       or last_exit_reason.startswith("stop"))):
                pn, pt = pressure_reentry[0], pressure_reentry[1]
                p_prev = cd.pressure(i - 2, pn, pressure_min_vol)
                p_now = cd.pressure(i - 1, pn, pressure_min_vol)
                if (p_prev is not None and p_now is not None
                        and p_prev < pt <= p_now):
                    brk = ("P-reentry", cd.o[i])
                    reentry_used += 1
        if brk is not None:
            pat, fill = brk
            if orb_fill_mode == "close":
                fill = cd.c[i]         # pessimistic fill (X097)
            if _entry_ok(fill) and _pressure_gates_ok(i, fill):
                buy_budget = budget_cur * (0.5 if add_at is not None else 1.0)
                sh = int(buy_budget // fill)
                if max_vol_frac:
                    vbase = sum(cd.v[max(0, i - vol_frac_window + 1):i + 1])
                    if vbase > 0:
                        sh = min(sh, int(vbase * max_vol_frac))
                if sh >= 1:
                    shares = sh
                    entry = fill * (1 + slip)
                    entry_i = i
                    peak = entry
                    entry_trig = pat
                    entry_pressure = cd.pressure(i - 1, 10, 0)
                    scaled = scaled2 = added = False
                    if atr_trail:
                        dyn_trail = _atr_pct(i, *atr_trail)
                    if atr_stop:
                        dyn_stop = _atr_pct(i, *atr_stop)
                    state = "LONG"
                    if verbose:
                        ts = cd.index[i].strftime("%m-%d %H:%M")
                        print(f"  BUY  {ts}  @{entry:.2f}  ({shares} sh = "
                              f"${shares * entry:,.0f})  pattern={pat}")
                    continue

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
            # rule 1 at ENTRY time: price must be inside the $2-PRICE_MAX band at
            # the moment we buy (a $1.93 open that runs through $2+ is
            # tradeable once it is in band)
            if not (PRICE_MIN <= price <= PRICE_MAX):
                continue
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
            if pats and not entries_open:
                pats = []                      # past entry cutoff
            if (pats and entry_cutoff_patterns is not None
                    and cd.index[i].time() >= entry_cutoff_patterns):
                pats = []                      # patterns-only cutoff (X313)
            if pats and not _pressure_gates_ok(i, price, patterns_entry=True):
                pats = []                      # pressure gate not met
            if pats:                           # dip inverts upward -> BUY
                entry = price * (1 + slip)
                entry_i = i
                buy_budget = budget_cur * (0.5 if add_at is not None else 1.0)
                shares = int(buy_budget // entry)
                if max_vol_frac:
                    vbase = sum(cd.v[max(0, i - vol_frac_window + 1):i + 1])
                    if vbase > 0:
                        shares = min(shares, int(vbase * max_vol_frac))
                if shares < 1:
                    continue
                state = "LONG"
                peak = entry
                entry_trig = pats[0]
                entry_pressure = cd.pressure(i - 1, 10, 0)
                scaled = scaled2 = added = False
                if atr_trail:
                    dyn_trail = _atr_pct(i, *atr_trail)
                if atr_stop:
                    dyn_stop = _atr_pct(i, *atr_stop)
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
            if trail_pct is not None or dyn_trail is not None:
                # trailing exit: ride the runner, sell on trail% retrace
                # from the highest price since entry (no fixed target)
                peak = max(peak, _hi(i))
                # half-then-add: second half deployed once price confirms
                if (add_at is not None and not added
                        and cd.h[i] >= entry * (1 + add_at / 100)):
                    px_add = entry * (1 + add_at / 100) * (1 + slip)
                    sh2 = int((budget_cur * 0.5) // px_add)
                    if max_vol_frac:
                        vbase = sum(cd.v[max(0, i - vol_frac_window + 1):i + 1])
                        if vbase > 0:
                            sh2 = min(sh2, int(vbase * max_vol_frac))
                    if sh2 >= 1:
                        entry = (entry * shares + px_add * sh2) / (shares + sh2)
                        shares += sh2
                    added = True
                # AX06 scale-out ladder: bank a fraction at +scale_out_at%
                if (scale_out_at is not None and not scaled
                        and _hi(i) >= entry * (1 + scale_out_at / 100)):
                    # X310/X311: pressure-conditioned banking -- when
                    # buyers dominate, skip or soften the scale-out
                    _pp = None
                    if (scale_out_pressure_skip is not None
                            or scale_out_frac_pressure is not None):
                        _pp = cd.pressure(i, 10, pressure_min_vol)
                    if (scale_out_pressure_skip is not None and _pp is not None
                            and _pp >= scale_out_pressure_skip):
                        part = 0           # skip banking entirely (X310);
                        px = 0.0           # trail/stop still checked below
                    else:
                        eff_frac = scale_out_frac
                        if (scale_out_frac_pressure is not None
                                and _pp is not None
                                and _pp >= scale_out_frac_pressure[0]):
                            eff_frac = scale_out_frac_pressure[1]
                        px = entry * (1 + scale_out_at / 100) * (1 - slip)
                        part = int(shares * eff_frac)
                    if part >= 1:
                        pnl_part = (px - entry) * part
                        trades.append({"entry_time": cd.index[entry_i],
                                       "entry": round(entry, 2),
                                       "exit_time": cd.index[i],
                                       "exit": round(px, 2),
                                       "reason": f"scale-out +{scale_out_at}%",
                                       "pnl": round(pnl_part, 2),
                                       "trig": entry_trig,
                                       "p_entry": entry_pressure,
                                       "peak_pct": round((peak / entry - 1) * 100, 1)})
                        shares -= part
                        if compound:
                            budget_cur += pnl_part
                    scaled = True
                # optional second tier (X062)
                if (scale_out_2 is not None and not scaled2
                        and cd.h[i] >= entry * (1 + scale_out_2[0] / 100)):
                    px = entry * (1 + scale_out_2[0] / 100) * (1 - slip)
                    part = int(shares * scale_out_2[1])
                    if part >= 1:
                        pnl_part = (px - entry) * part
                        trades.append({"entry_time": cd.index[entry_i],
                                       "entry": round(entry, 2),
                                       "exit_time": cd.index[i],
                                       "exit": round(px, 2),
                                       "reason": f"scale-out2 +{scale_out_2[0]}%",
                                       "pnl": round(pnl_part, 2)})
                        shares -= part
                        if compound:
                            budget_cur += pnl_part
                    scaled2 = True
                # AX08 adaptive trail: widen once the runner proves itself
                eff_trail = dyn_trail if dyn_trail is not None else trail_pct
                if (trail_widen_at is not None
                        and peak >= entry * (1 + trail_widen_at / 100)):
                    eff_trail = trail_wide
                # X200 pressure-modulated trail (wins over trail_widen_at)
                if pressure_trail is not None:
                    pn, t_lo, t_hi, tight, wide = pressure_trail
                    pp = cd.pressure(i, pn, pressure_min_vol)
                    if _shuffle_rng is not None and pp is not None:
                        pp = _shuffle_rng.uniform(-1, 1)   # X318 control
                    if pp is not None:
                        if t_lo is not None and pp <= -t_lo:
                            eff_trail = tight
                        elif t_hi is not None and pp >= t_hi:
                            eff_trail = wide
                target_lo = target_hi = float("inf")
                trail_px = peak * (1 - eff_trail / 100)
                eff_stop_pct = dyn_stop if dyn_stop is not None else (stop_pct or 5)
                stop = max(entry * (1 - eff_stop_pct / 100), trail_px)
                # breakeven floor once the runner has proven itself
                if (breakeven_at is not None
                        and peak >= entry * (1 + breakeven_at / 100)):
                    stop = max(stop, entry)
            elif target_pct is not None:
                target_lo = target_hi = entry * (1 + target_pct / 100)
                stop = entry * (1 - (stop_pct or 1.5) / 100)
            else:
                target_lo = entry + GAIN_PER_SHARE
                target_hi = entry + GAIN_PER_SHARE_MAX
                stop = entry - LOSS_PER_SHARE
            exit_px = None
            reason = ""
            # time-stop: cut a position still flat/red after N minutes
            if (time_stop_min is not None and exit_px is None
                    and (cd.index[i] - cd.index[entry_i]).total_seconds()
                    >= time_stop_min * 60
                    and price <= entry):
                exit_px, reason = price, f"time-stop {time_stop_min}m"
            if exit_px is None and cd.l[i] <= stop:
                exit_px, reason = stop, f"stop {stop - entry:+.2f}"
            elif exit_px is None and cd.h[i] >= target_lo:
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
            # X200 pressure exit: sellers took over (bar-close fill,
            # so pressure at bar i itself is legitimate)
            if exit_px is None and pressure_exit is not None:
                pn, pt = pressure_exit[0], pressure_exit[1]
                pmode = pressure_exit[2] if len(pressure_exit) > 2 \
                    else "profit"
                pp = cd.pressure(i, pn, pressure_min_vol)
                if (pp is not None and pp <= -pt
                        and (pmode == "always" or price > entry)):
                    exit_px, reason = price, f"pressure-flip {pp:+.2f}"
            if exit_px is not None:
                pnl = (exit_px * (1 - slip) - entry) * shares
                trades.append({
                    "entry_time": cd.index[entry_i], "entry": round(entry, 2),
                    "exit_time": cd.index[i], "exit": round(exit_px, 2),
                    "reason": reason, "pnl": round(pnl, 2),
                    "trig": entry_trig, "p_entry": entry_pressure,
                    "peak_pct": round((peak / entry - 1) * 100, 1),
                })
                if verbose:
                    ts = cd.index[i].strftime("%m-%d %H:%M")
                    print(f"  SELL {ts}  @{exit_px:.2f}  {reason}  "
                          f"P&L ${pnl:+,.2f}")
                if compound:
                    budget_cur += pnl
                last_exit_reason = reason
                state = "SCAN"

    # HARD RULE: whatever was bought in this session's bars is sold before
    # the session ends -- any open position is flattened at the last bar.
    # (For 7AM-noon window data that means sold by NOON the same day.)
    if state == "LONG":
        exit_px = cd.c[cd.n - 1]
        pnl = (exit_px * (1 - slip) - entry) * shares
        trades.append({
            "entry_time": cd.index[entry_i], "entry": round(entry, 2),
            "exit_time": cd.index[cd.n - 1], "exit": round(exit_px, 2),
            "reason": "window-close flatten", "pnl": round(pnl, 2),
            "trig": entry_trig, "p_entry": entry_pressure,
            "peak_pct": round((peak / entry - 1) * 100, 1),
        })
        if verbose:
            ts = cd.index[cd.n - 1].strftime("%m-%d %H:%M")
            print(f"  SELL {ts}  @{exit_px:.2f}  window-close flatten  "
                  f"P&L ${pnl:+,.2f}")

    return trades


def _enforce_price_band(symbol: str, df: pd.DataFrame) -> bool:
    """This strategy is ONLY for PRICE_MIN-PRICE_MAX stocks (rule 1)."""
    price = float(df["Close"].iloc[-1])
    if not (PRICE_MIN <= price <= PRICE_MAX):
        print(f"{symbol.upper()} is ${price:.2f} -- outside the ${PRICE_MIN:.0f}-"
              f"{'no-cap' if PRICE_MAX == float('inf') else f'${PRICE_MAX:.0f}'} penny-stock band. This strategy does not apply:"
              f" the $0.18/-$0.15 per-share targets only make sense at penny"
              f" prices. Pick an in-band stock (see: python day-trading.py screen).")
        return False
    return True


def cmd_backtest(symbol: str, days: int) -> None:
    # penny stocks are DAY-TRADED in the 7AM-noon ET window ONLY: shares
    # bought in the window are ALWAYS sold within the same day's window
    # (flattened by NOON at the latest -- never held past the window)
    window_data = _window_data([symbol], days)
    entry = window_data.get(symbol.upper())
    if not entry or entry["bars"].empty:
        print(f"No usable 7AM-noon window data for {symbol}")
        return
    w, prev_map = entry["bars"], entry["prev"]

    all_trades = []
    for day, day_df in w.groupby(w.index.date):
        if len(day_df) < 20:
            continue
        print(f"\n{symbol.upper()}  {day}  7AM-noon  "
              f"(open {day_df['Open'].iloc[0]:.2f}, "
              f"window close {day_df['Close'].iloc[-1]:.2f})")
        # PENNY DEFAULT (60d backtest winner + ORB, +39% in testing):
        # all bullish patterns + opening-range breakout, no volume gate,
        # trail 20% from peak, hard stop -5%
        trades = simulate_trades(day_df, prev_close=prev_map.get(day),
                                 buy_set=None, vol_confirm=False,
                                 trail_pct=DEFAULT_TRAIL_PCT,
                                 stop_pct=DEFAULT_STOP_PCT, orb=True,
                                 scale_out_at=DEFAULT_SCALE_OUT_AT,
                                 scale_out_frac=DEFAULT_SCALE_OUT_FRAC)
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
    """Grid-test buy-pattern sets x sell modes in the 7AM-noon ET window."""
    window_data = _window_data(symbols, days)
    if not window_data:
        print("No usable data.")
        return

    print(f"\nGrid: {len(BUY_SETS)} buy sets x {len(SELL_MODES)} sell modes, "
          f"7AM-noon ET only, ${POSITION_DOLLARS}/trade, "
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
    """Fetch 1-min bars (incl. premarket) restricted to 7AM-noon ET.

    The price band is checked PER DAY at that day's first window price --
    a stock that later ran to $20 still counts on the days it was in band
    (that is exactly when the strategy would have traded it).
    """
    rh_fund = load_rh_fundamentals()
    out = {}
    for sym in symbols:
        t = yf.Ticker(sym.upper())
        # rule 8: float must be <= 16M shares -- oversized floats are not
        # tradeable under this strategy at all. Robinhood cache first
        # (authoritative), yfinance fallback (patchy); unknown float passes.
        flt = (rh_fund.get(sym.upper()) or {}).get("float")
        if flt is None:
            try:
                flt = (t.info or {}).get("floatShares")
            except Exception:
                flt = None
        if MAX_FLOAT is not None and flt is not None and flt > MAX_FLOAT:
            print(f"{sym.upper()}: float {flt / 1e6:.1f}M > "
                  f"{MAX_FLOAT / 1e6:.0f}M limit, symbol excluded")
            continue
        df = t.history(period=f"{min(days, 7)}d", interval="1m", prepost=True)
        if df.empty:
            print(f"{sym}: no 1-min data, skipped")
            continue
        df.index = df.index.tz_convert(ET)

        # merge cached Robinhood bars: RH rows win on overlapping minutes
        # (real premarket volume), yfinance fills everything else
        rh = load_rh_bars(sym)
        if rh is not None:
            df = pd.concat([df[~df.index.isin(rh.index)],
                            rh[["Open", "High", "Low", "Close", "Volume"]]]
                           ).sort_index()
            print(f"  {sym.upper()}: merged {len(rh)} Robinhood bars "
                  f"(real premarket volume)")

        w = df[(df.index.time >= NEWS_START) & (df.index.time < NEWS_END)]
        # keep a day if the band was REACHABLE during the window (entries
        # themselves are band-checked per bar inside simulate_trades)
        lo = min_price if min_price is not None else PRICE_MIN
        keep = []
        for day, day_df in w.groupby(w.index.date):
            day_hi = float(day_df["High"].max())
            day_lo = float(day_df["Low"].min())
            if day_hi >= lo and day_lo <= PRICE_MAX:
                keep.append(day_df)
            else:
                print(f"  {sym.upper()} {day}: window range ${day_lo:.2f}-"
                      f"${day_hi:.2f} never inside ${lo:.0f}+ band "
                      f"band, day skipped")
        w = pd.concat(keep) if keep else w.iloc[0:0]
        print(f"{sym.upper()}: {len(w)} one-min bars 7AM-noon ET across "
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
    """Grid: buy-pattern set x trades-per-day cap, 7AM-noon ET window.

    '1 trade buy & 1 trade sell' = cap 1; 'n trades' = cap 2, 3, unlimited.
    Sell mode fixed at the calibrated default. $POSITION_DOLLARS per trade.
    """
    window_data = _window_data(symbols, days)
    if not window_data:
        print("No usable data.")
        return

    caps = [1, 2, 3, None]
    print(f"\nGrid: {len(BUY_SETS)} buy sets x trades/day caps {caps}, "
          f"7AM-noon ET, ${POSITION_DOLLARS}/trade, "
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
    true per-minute volume during 7AM-noon.

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

    def bars(self, symbol: str) -> pd.DataFrame:
        """Build LIVE 1-min OHLCV candles from the polled quote samples.

        This replaces yfinance intraday bars for LIVE operation: real-time
        prices and true extended-hours volume. (Historical bars still come
        from yfinance -- E*TRADE keeps no history.) Feed the result straight
        into Candles for live pattern detection.
        """
        pts = self.samples.get(symbol.upper(), [])
        rows = {}
        prev_vol = None
        for ts, tv, last in pts:
            if last <= 0:
                continue
            minute = ts.replace(second=0, microsecond=0)
            r = rows.setdefault(minute, {"Open": last, "High": last,
                                         "Low": last, "Close": last,
                                         "Volume": 0})
            r["High"] = max(r["High"], last)
            r["Low"] = min(r["Low"], last)
            r["Close"] = last
            if prev_vol is not None:
                r["Volume"] += max(0, tv - prev_vol)
            prev_vol = tv
        if not rows:
            return pd.DataFrame(
                columns=["Open", "High", "Low", "Close", "Volume"])
        df = pd.DataFrame.from_dict(rows, orient="index").sort_index()
        return df

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


def cmd_livebars(symbol: str, minutes: int, sandbox: bool,
                 poll_seconds: int = 10) -> None:
    """LIVE 1-min candles + pattern detection via E*TRADE polling.

    Polls quotes every few seconds, assembles 1-min OHLCV bars, and after
    each completed minute runs the candlestick engine on the live bars --
    printing any bullish/bearish patterns as they form. This is item #1
    (intraday bars) replaced with E*TRADE for live operation.
    """
    import time as _time
    try:
        feed = EtradeVolumeFeed(sandbox=sandbox)
    except Exception as e:
        print(f"E*TRADE feed unavailable: {e}")
        return
    sym = symbol.upper()
    env = "SANDBOX" if sandbox else "PROD"
    print(f"LIVE bars for {sym} ({env}), polling every {poll_seconds}s for "
          f"{minutes} min... Ctrl+C to stop")
    end = datetime.now(ET) + timedelta(minutes=minutes)
    last_reported = None
    try:
        while datetime.now(ET) < end:
            feed.sample([sym])
            bars = feed.bars(sym)
            # report on the last COMPLETED minute (current one still forming)
            if len(bars) >= 2:
                done = bars.index[-2]
                if done != last_reported:
                    last_reported = done
                    cd = Candles(bars.iloc[:-1])
                    i = cd.n - 1
                    bulls = cd.bullish_patterns(i) + cd.indicator_bullish(i)
                    bears = cd.bearish_patterns(i) + cd.indicator_bearish(i)
                    vol_ok = cd.volume_confirmed(i)
                    b = bars.iloc[-2]
                    tags = ([f"+{p}" for p in bulls] + [f"-{p}" for p in bears]
                            or ["(no pattern)"])
                    print(f"  {done.strftime('%H:%M')}  "
                          f"O {b['Open']:.2f} H {b['High']:.2f} "
                          f"L {b['Low']:.2f} C {b['Close']:.2f} "
                          f"V {int(b['Volume']):,}  volOK={'Y' if vol_ok else 'n'}"
                          f"  {' '.join(tags)}")
            _time.sleep(poll_seconds)
    except KeyboardInterrupt:
        pass
    bars = feed.bars(sym)
    print(f"\nCollected {len(bars)} live 1-min bars for {sym}")
    if len(bars):
        print(bars.tail(10).to_string())


def cmd_livescreen(symbols: list[str], sandbox: bool) -> None:
    """REAL-TIME screen via E*TRADE quotes (works in extended hours).

    One batched quote call gives lastTrade (or ExtendedHourQuoteDetail
    price), previousClose, totalVolume and averageVolume -- so the price
    band, up>=10% and rvol>=5x rules are evaluated live, not on delayed
    Yahoo data. Sector/float (yfinance) and news (Finnhub) are only fetched
    for symbols that pass the live rules.
    """
    try:
        from trading.api_wrapper import ETradeSession
        sess = ETradeSession(sandbox=sandbox)
        if not sess._load_saved_token():
            print("No valid E*TRADE token. Run: python plan/sandbox_auth.py "
                  "--auth (then --verifier CODE)")
            return
    except Exception as e:
        print(f"E*TRADE unavailable: {e}")
        return

    env = "SANDBOX" if sandbox else "PROD"
    quotes = sess.get_quotes([s.upper() for s in symbols])
    print(f"\nLIVE E*TRADE screen ({env}, "
          f"{datetime.now(ET).strftime('%H:%M:%S ET')})")
    print(f"{'SYM':<6} {'status':<15} {'last':>7} {'prev':>7} {'gain%':>7} "
          f"{'r3':>3} {'rvol':>5} {'r5':>3} {'band':>5}")
    print("-" * 66)
    requested = [s.upper() for s in symbols]
    extra = [k for k in quotes if k not in requested]
    if extra:
        print(f"(note: sandbox returns canned symbols -- got {extra} "
              f"instead of some requested; use --prod for real data)")
    prepass = []
    for sym in requested + extra:
        qd = quotes.get(sym)
        if not qd:
            print(f"{sym:<6} NO QUOTE")
            continue
        all_q = qd.get("All", {})
        ext = all_q.get("ExtendedHourQuoteDetail", {})
        status = qd.get("quoteStatus", "?")
        last = ext.get("lastPrice") or all_q.get("lastTrade")
        prev = all_q.get("previousClose")
        tv = ext.get("volume") or all_q.get("totalVolume")
        av = all_q.get("averageVolume")
        if not last or not prev:
            print(f"{sym:<6} {status:<15} (no price data)")
            continue
        gain = (float(last) / float(prev) - 1) * 100
        rvol = (float(tv) / float(av)) if tv and av else 0.0
        r1 = PRICE_MIN <= float(last) <= PRICE_MAX
        r3 = gain >= MIN_DAY_GAIN_PCT
        r5 = rvol >= MIN_REL_VOLUME
        b = lambda v: "Y" if v else "."
        print(f"{sym:<6} {status:<15} {float(last):>7.2f} {float(prev):>7.2f} "
              f"{gain:>+6.1f}% {b(r3):>3} {rvol:>5.1f} {b(r5):>3} {b(r1):>5}")
        if r1 and r3 and r5:
            prepass.append(sym)

    if not prepass:
        print("\nNo symbol passes the live price/gain/rvol rules right now.")
        return
    print(f"\nLive pre-pass: {prepass} -- checking sector/float/news lazily...")
    for sym in prepass:
        c = screen_symbol(sym)
        ok = "PASS" if c.get("PASS") else "fail"
        print(f"  {sym}: sector={c.get('rule4_hot_sector')} "
              f"float={c.get('float_m')}M ok={c.get('rule8_float_under_16m')} "
              f"news18h={c.get('rule2_news_18h')} -> {ok} {c.get('news', '')}")


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
          f"7AM-noon ET | ${POSITION_DOLLARS}/trade | "
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
    per day (the provided symbol with the highest 7AM-noon volume that day)."""
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
          f"7AM-noon ET, same-day exits\n")

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
                        help="grid-test candle buy/sell configs 7AM-noon ET")
    ct.add_argument("symbols", nargs="+")
    ct.add_argument("--days", type=int, default=5)

    gt = sub.add_parser("gridtest",
                        help="grid buy sets x trades/day cap, 7AM-noon ET")
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

    ls = sub.add_parser("livescreen",
                        help="real-time rule screen via E*TRADE quotes")
    ls.add_argument("symbols", nargs="+")
    ls.add_argument("--prod", action="store_true")

    lb = sub.add_parser("livebars",
                        help="live 1-min candles + pattern detection via E*TRADE")
    lb.add_argument("symbol")
    lb.add_argument("--minutes", type=int, default=10)
    lb.add_argument("--prod", action="store_true")

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
    elif args.cmd == "livescreen":
        cmd_livescreen(args.symbols, sandbox=not args.prod)
    elif args.cmd == "livebars":
        cmd_livebars(args.symbol, args.minutes, sandbox=not args.prod)


if __name__ == "__main__":
    main()
