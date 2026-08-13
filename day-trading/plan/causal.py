"""CausalView -- make lookahead impossible to write, not merely wrong.

WHY THIS EXISTS. On 2026-08-13 we priced a future signal that had been
sitting in the harness for days: the candidate pool was cut with
`sorted(cs, key=-gain_pct)[:16]`, and gain_pct is the DAY-HIGH gain. It
cost $108,867 (14%) of the champion's reported edge and nobody spotted
it, because a plain sort does not look like a leak.

The lesson from backtesting.py and zipline: a decision-time view of the
data should not be able to SEE the future at all. `next()` exposes only
a growing prefix; Pipeline makes you declare the trailing window. Then
the bug does not exist rather than being caught later.

Usage:
    cv = CausalView(df, symbol="BE", date="2026-08-12")
    bars = cv.upto(dtime(9, 30))     # everything at or before 09:30
    win  = cv.window(dtime(9, 30), 10)   # last 10 bars strictly BEFORE

    cv.future(...)   -> raises unless the caller passes
                        allow_lookahead="<reason>", which is reserved
                        for deliberately clairvoyant CONTROLS (e.g. the
                        VF20 leak detector) and is logged loudly.

Nothing here is a substitute for thinking. It closes the accidental
case: slicing that silently includes the current or later bars.
"""

from datetime import time as dtime


class LookaheadError(AssertionError):
    """Raised when a causal view is asked for data it must not see."""


class CausalView:
    """A DataFrame restricted to 'what was knowable by time t'.

    The frame must carry a tz-aware DatetimeIndex. Every accessor is
    explicit about whether the boundary bar is included, because the
    off-by-one AT the decision bar is the leak that actually happens:
    the entry bar's own range is a consequence of our trigger, so
    features must be built from bars strictly BEFORE it.
    """

    __slots__ = ("_df", "symbol", "date", "_peeks")

    def __init__(self, df, symbol=None, date=None):
        if df is None or len(df) == 0:
            raise ValueError(f"CausalView({symbol} {date}): empty frame")
        self._df = df
        self.symbol = symbol
        self.date = date
        self._peeks = []

    def __len__(self):
        return len(self._df)

    def upto(self, t, inclusive=True):
        """Bars at or before clock time `t` (inclusive by default).

        Use for state that legitimately includes the current bar's
        close -- e.g. 'price now', the running high, the coil ratio.
        """
        idx = self._df.index.time
        return self._df[idx <= t] if inclusive else self._df[idx < t]

    def before(self, ts):
        """Bars strictly before timestamp `ts`.

        Use for anything describing conditions AT a decision: the book
        state before we commit, the tape before our own trigger prints.
        """
        w = self._df[self._df.index < ts]
        if len(w) and w.index.max() >= ts:
            raise LookaheadError(
                f"{self.symbol} {self.date}: before({ts}) leaked "
                f"{w.index.max()}")
        return w

    def window(self, ts, n):
        """The last `n` bars strictly before `ts`, or None if short."""
        w = self.before(ts)
        if len(w) < n:
            return None
        tail = w.iloc[-n:]
        if tail.index.max() >= ts:
            raise LookaheadError(
                f"{self.symbol} {self.date}: window({ts},{n}) ends "
                f"{tail.index.max()} >= {ts}")
        return tail

    def first_cross_time(self, level, not_after=None):
        """When `level` was FIRST printed. Causal as a CONSTRAINT.

        Knowing a name crosses at 13:00 does not let us act at 07:00 --
        callers must gate on `cross > t -> skip`. It is a leak only if
        used to RANK or to pre-select the pool, which is exactly what
        the day-high pool cut did. Never feed this into a score.
        """
        for ts, hi in zip(self._df.index, self._df["High"].values):
            if not_after is not None and ts.time() > not_after:
                break
            if float(hi) >= level:
                return ts.time()
        return None

    def future(self, ts, n=None, allow_lookahead=None):
        """DELIBERATELY non-causal. Controls and leak detectors only."""
        if not allow_lookahead:
            raise LookaheadError(
                f"{self.symbol} {self.date}: future({ts}) requested "
                f"without allow_lookahead. If this is a control, pass "
                f"allow_lookahead='why'; otherwise you have a leak.")
        self._peeks.append((ts, allow_lookahead))
        print(f"LOOKAHEAD (declared): {self.symbol} {self.date} "
              f"future({ts}) -- {allow_lookahead}", flush=True)
        w = self._df[self._df.index >= ts]
        return w.iloc[:n] if n else w

    @property
    def declared_peeks(self):
        return list(self._peeks)


def self_test():
    """Prove the guard fires. A decorative assertion is worse than none."""
    import pandas as pd
    idx = pd.date_range("2026-08-13 09:30", periods=30, freq="1min",
                        tz="America/New_York")
    df = pd.DataFrame({"Open": 10.0, "High": 10.5, "Low": 9.5,
                       "Close": 10.0, "Volume": 1000.0}, index=idx)
    cv = CausalView(df, "TEST", "2026-08-13")
    ts = idx[20]
    ok = 0

    assert cv.window(ts, 10).index.max() < ts
    ok += 1
    assert cv.upto(dtime(9, 40)).index.max().time() <= dtime(9, 40)
    ok += 1
    assert cv.upto(dtime(9, 40), inclusive=False).index.max().time() \
        < dtime(9, 40)
    ok += 1
    assert cv.window(ts, 999) is None          # short window -> None
    ok += 1
    try:
        cv.future(ts)
        raise SystemExit("FAIL: undeclared future() did not raise")
    except LookaheadError:
        ok += 1
    f = cv.future(ts, 5, allow_lookahead="self-test control")
    assert f.index.min() >= ts and len(cv.declared_peeks) == 1
    ok += 1
    assert cv.first_cross_time(10.4) == idx[0].time()
    ok += 1
    print(f"CausalView self-test: {ok}/7 checks passed")


if __name__ == "__main__":
    self_test()
