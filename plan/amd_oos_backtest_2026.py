"""AMD walk-forward backtest: train on Aug 2015 - Jul 2025, test OOS on Aug 2025 - Jul 2026.

Rules of the experiment (per user request):
- $100,000 starting capital, invested from end of July 2025 to end of July 2026.
- Parameters are LEARNED using only the last 10 years BEFORE Aug 2025.
- Data from Aug 2025 onward is touched only to evaluate the frozen strategies.
- All-in per trade (100% of capital), whole shares, LIMIT-style fills, no leverage,
  no shorting. Signal-based strategies execute at next day's open (no lookahead).

Strategy families tested (each optimized on train, then frozen):
  1. Buy & Hold (benchmark)
  2. Never-Lose dip/rip: buy dip% below recent high, sell at +sell%, never sell at loss
  3. Dip/rip + stop-loss
  4. Dip/rip + max-hold time exit
  5. Dip/rip with 200-SMA trend filter
  6. SMA crossover
  7. RSI mean reversion
  8. Bollinger band reversion

For each family we keep two picks: "max" (best 10y compound on train) and
"robust" (best median of the 10 individual train years). Both are tested OOS.
"""

import json
import os

import numpy as np
import pandas as pd

CSV = os.path.join(
    r"C:\Users\MYPC~1\AppData\Local\Temp\claude",
    r"C--cornell-stocks-automation\20a29bc8-aa0d-497e-a600-4db3499b8240\scratchpad",
    "amd_daily.csv",
)

TRAIN_END = "2025-07-31"   # last day usable for learning
TEST_START = "2025-08-01"
TEST_END = "2026-07-31"
CAPITAL = 100_000.0

# ---------------------------------------------------------------------------
# Data (module-level arrays, sims address by index range)
# ---------------------------------------------------------------------------

_df = pd.read_csv(CSV)
_df["Date"] = pd.to_datetime(_df["Date"], utc=True).dt.tz_localize(None).dt.normalize()
_df = _df.set_index("Date")[["Open", "High", "Low", "Close"]].dropna()
_df = _df[_df.index <= TEST_END]

O = _df["Open"].values.tolist()
H = _df["High"].values.tolist()
L = _df["Low"].values.tolist()
C = _df["Close"].values.tolist()
DATES = _df.index
N = len(_df)
SMA200 = _df["Close"].rolling(200).mean().values.tolist()

# RMAX[lb][i] = max close over the lb days BEFORE day i (excludes day i)
RMAX = {
    lb: _df["Close"].rolling(lb).max().shift(1).values.tolist()
    for lb in (3, 5, 10, 20)
}
# trend gate: yesterday's close above yesterday's 200-SMA
TREND_OK = [False] + [
    (not np.isnan(SMA200[i - 1])) and C[i - 1] > SMA200[i - 1] for i in range(1, N)
]


def idx(date_str):
    return int(DATES.searchsorted(date_str))


TRAIN_START_I = 0
TRAIN_END_I = idx(TEST_START)          # exclusive
TEST_START_I = idx(TEST_START)
TEST_END_I = N                          # exclusive

TRAIN_YEARS = [(idx(f"{y}-08-01"), idx(f"{y + 1}-08-01")) for y in range(2015, 2025)]


# ---------------------------------------------------------------------------
# Simulators
# ---------------------------------------------------------------------------

def _pack(equity, trades, wins, open_trade):
    eq = np.asarray(equity, dtype=float)
    peak = np.maximum.accumulate(eq)
    mdd = ((eq - peak) / peak).min() * 100 if len(eq) else 0.0
    return {
        "final": float(eq[-1]),
        "ret_pct": (float(eq[-1]) / CAPITAL - 1) * 100,
        "trades": len(trades),
        "wins": wins,
        "win_rate": (wins / len(trades) * 100) if trades else 0.0,
        "max_dd": float(mdd),
        "open_trade": open_trade,
        "avg_hold": float(np.mean([t[2] for t in trades])) if trades else 0.0,
        "trade_list": trades,
    }


def sim_dip_rip(s, e, dip, sell, lookback, stop=None, max_hold=None,
                trend_filter=False):
    cash = CAPITAL
    shares = 0
    entry = 0.0
    entry_i = -1
    trades = []
    wins = 0
    equity = [0.0] * (e - s)
    rmax = RMAX[lookback]
    buy_frac = 1 - dip / 100.0

    for i in range(s, e):
        if shares == 0:
            rh = rmax[i]
            if rh == rh and (not trend_filter or TREND_OK[i]):
                target = rh * buy_frac
                fill = None
                if O[i] <= target:
                    fill = O[i]
                elif L[i] <= target:
                    fill = target
                if fill is not None and fill > 0:
                    shares = int(cash // fill)
                    if shares > 0:
                        cash -= shares * fill
                        entry = fill
                        entry_i = i
        elif i > entry_i:
            tgt = entry * (1 + sell / 100.0)
            stp = entry * (1 - stop / 100.0) if stop else None
            fill = win = None
            # gap handling: open beyond a level fills at the open
            if stp is not None and O[i] <= stp:
                fill, win = O[i], False
            elif O[i] >= tgt:
                fill, win = O[i], True
            elif stp is not None and L[i] <= stp:
                # conservative: if both levels touched intraday, assume stop first
                fill, win = stp, False
            elif H[i] >= tgt:
                fill, win = tgt, True
            elif max_hold and (i - entry_i) >= max_hold:
                fill = C[i]
                win = fill > entry
            if fill is not None:
                cash += shares * fill
                trades.append((DATES[entry_i].date(), DATES[i].date(),
                               round(entry, 2), round(fill, 2), i - entry_i))
                if win:
                    wins += 1
                shares = 0
        equity[i - s] = cash + shares * C[i]

    open_trade = None
    if shares > 0:
        open_trade = {"entry_date": str(DATES[entry_i].date()),
                      "entry": round(entry, 2), "last": round(C[e - 1], 2),
                      "unreal_pct": (C[e - 1] / entry - 1) * 100,
                      "hold_days": e - 1 - entry_i}
    return _pack(equity, trades, wins, open_trade)


def sim_signal(s, e, buy_arr, sell_arr):
    """Close-signal strategy: signal at day i-1 close -> trade at day i open."""
    cash = CAPITAL
    shares = 0
    entry = 0.0
    entry_i = -1
    trades = []
    wins = 0
    equity = np.empty(e - s)

    for i in range(s, e):
        if shares == 0:
            if i >= 1 and buy_arr[i - 1]:
                shares = int(cash // O[i])
                if shares > 0:
                    cash -= shares * O[i]
                    entry = O[i]
                    entry_i = i
        elif i > entry_i and sell_arr[i - 1]:
            cash += shares * O[i]
            trades.append((DATES[entry_i].date(), DATES[i].date(),
                           round(entry, 2), round(O[i], 2), i - entry_i))
            if O[i] > entry:
                wins += 1
            shares = 0
        equity[i - s] = cash + shares * C[i]

    open_trade = None
    if shares > 0:
        open_trade = {"entry_date": str(DATES[entry_i].date()),
                      "entry": round(entry, 2), "last": round(C[e - 1], 2),
                      "unreal_pct": (C[e - 1] / entry - 1) * 100,
                      "hold_days": e - 1 - entry_i}
    return _pack(equity, trades, wins, open_trade)


def sim_bh(s, e):
    shares = int(CAPITAL // O[s])
    cash = CAPITAL - shares * O[s]
    equity = cash + shares * np.asarray(C[s:e])
    return _pack(equity,
                 [(DATES[s].date(), DATES[e - 1].date(),
                   round(O[s], 2), round(C[e - 1], 2), e - 1 - s)], 1, None)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

def rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    ag = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    al = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return 100 - 100 / (1 + ag / al)


# ---------------------------------------------------------------------------
# Train/test harness
# ---------------------------------------------------------------------------

def eval_train(runner):
    full = runner(TRAIN_START_I, TRAIN_END_I)
    yearly = [runner(ys, ye)["ret_pct"] for ys, ye in TRAIN_YEARS]
    return full["final"] / CAPITAL, yearly, float(np.median(yearly))


RESULTS = {}


def register(name, params_desc, runner, train_stats=None):
    mult, yearly, med = train_stats or eval_train(runner)
    RESULTS[name] = {
        "params": params_desc, "train_mult": mult,
        "train_yearly": yearly, "train_med": med,
        "test": runner(TEST_START_I, TEST_END_I),
    }


def grid_pick(name, combos, desc_fn):
    """combos: list of (mult, med, yearly, params_tuple, runner)."""
    by_mult = max(combos, key=lambda x: x[0])
    by_med = max(combos, key=lambda x: x[1])
    for tag, pick in (("max", by_mult), ("robust", by_med)):
        mult, med, yearly, params, runner = pick
        register(f"{name} [{tag}]", desc_fn(*params), runner,
                 train_stats=(mult, yearly, med))


def main():
    print(f"Data: {DATES[0].date()} .. {DATES[-1].date()}  ({N} days)")
    print(f"Train idx [{TRAIN_START_I}, {TRAIN_END_I}), Test idx [{TEST_START_I}, {TEST_END_I})")

    register("Buy & Hold", "buy first day, hold", sim_bh)

    dips = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0]
    sells = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20, 25]
    lookbacks = [3, 5, 10, 20]

    def dip_grid(extra_grid, make_runner):
        combos = []
        for dip in dips:
            for sp in sells:
                for lb in lookbacks:
                    for extra in extra_grid:
                        runner = make_runner(dip, sp, lb, extra)
                        mult, yearly, med = eval_train(runner)
                        combos.append((mult, med, yearly, (dip, sp, lb, extra), runner))
        return combos

    print("Grid: Never-Lose dip/rip...")
    grid_pick("Never-Lose dip/rip",
              dip_grid([None], lambda d, s2, lb, _:
                       lambda s, e: sim_dip_rip(s, e, d, s2, lb)),
              lambda d, s2, lb, _: f"dip {d}%, sell +{s2}%, lb {lb}d")

    print("Grid: dip/rip + stop-loss...")
    grid_pick("Dip/rip + stop-loss",
              dip_grid([8, 10, 15, 20], lambda d, s2, lb, st:
                       lambda s, e: sim_dip_rip(s, e, d, s2, lb, stop=st)),
              lambda d, s2, lb, st: f"dip {d}%, sell +{s2}%, lb {lb}d, stop -{st}%")

    print("Grid: dip/rip + time exit...")
    grid_pick("Dip/rip + time exit",
              dip_grid([10, 20, 40, 60], lambda d, s2, lb, mh:
                       lambda s, e: sim_dip_rip(s, e, d, s2, lb, max_hold=mh)),
              lambda d, s2, lb, mh: f"dip {d}%, sell +{s2}%, lb {lb}d, exit {mh}d")

    print("Grid: dip/rip + 200SMA filter...")
    grid_pick("Dip/rip + 200SMA filter",
              dip_grid([None], lambda d, s2, lb, _:
                       lambda s, e: sim_dip_rip(s, e, d, s2, lb, trend_filter=True)),
              lambda d, s2, lb, _: f"dip {d}%, sell +{s2}%, lb {lb}d, >200SMA")

    register("Current wave_config (AMD)", "dip 2.5%, sell +10%, lb 5d",
             lambda s, e: sim_dip_rip(s, e, 2.5, 10.0, 5))

    print("Grid: SMA cross...")
    combos = []
    for fast in [5, 10, 20, 50]:
        for slow in [20, 50, 100, 200]:
            if fast >= slow:
                continue
            f = _df["Close"].rolling(fast).mean()
            sl = _df["Close"].rolling(slow).mean()
            buy = ((f > sl) & (f.shift(1) <= sl.shift(1))).values
            sellsig = ((f < sl) & (f.shift(1) >= sl.shift(1))).values
            runner = (lambda b, s2: lambda s, e: sim_signal(s, e, b, s2))(buy, sellsig)
            mult, yearly, med = eval_train(runner)
            combos.append((mult, med, yearly, (fast, slow), runner))
    grid_pick("SMA cross", combos, lambda f, sl: f"SMA{f}/SMA{sl}")

    print("Grid: RSI reversion...")
    r = rsi(_df["Close"])
    combos = []
    for blo in [20, 25, 30, 35, 40]:
        for shi in [55, 60, 65, 70, 75]:
            buy = (r < blo).values
            sellsig = (r > shi).values
            runner = (lambda b, s2: lambda s, e: sim_signal(s, e, b, s2))(buy, sellsig)
            mult, yearly, med = eval_train(runner)
            combos.append((mult, med, yearly, (blo, shi), runner))
    grid_pick("RSI reversion", combos, lambda b, s2: f"buy RSI<{b}, sell RSI>{s2}")

    print("Grid: Bollinger...")
    mid = _df["Close"].rolling(20).mean()
    std = _df["Close"].rolling(20).std()
    combos = []
    for nstd in [1.5, 2.0, 2.5]:
        for exit_at in ["mid", "upper"]:
            lower = mid - nstd * std
            up = mid + nstd * std
            buy = (_df["Close"] < lower).values
            sellsig = (_df["Close"] > (mid if exit_at == "mid" else up)).values
            runner = (lambda b, s2: lambda s, e: sim_signal(s, e, b, s2))(buy, sellsig)
            mult, yearly, med = eval_train(runner)
            combos.append((mult, med, yearly, (nstd, exit_at), runner))
    grid_pick("Bollinger", combos, lambda n2, x: f"buy < {n2}sd, sell @ {x}")

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    bh = RESULTS["Buy & Hold"]["test"]
    print(f"\nRESULTS (train = Aug2015-Jul2025, test = Aug2025-Jul2026, $100K)\n")
    hdr = (f"{'Strategy':<28} {'Params (frozen pre-Aug25)':<36} "
           f"{'Train10y':>9} {'MedYr%':>7} | {'Trades':>6} {'Win%':>5} "
           f"{'Final $':>11} {'Ret%':>8} {'MaxDD%':>7} {'vsB&H $':>10}")
    print(hdr)
    print("-" * len(hdr))
    for name, res in RESULTS.items():
        t = res["test"]
        print(f"{name:<28} {res['params']:<36} "
              f"{res['train_mult']:>8.1f}x {res['train_med']:>6.1f}% | "
              f"{t['trades']:>6} {t['win_rate']:>4.0f}% "
              f"{t['final']:>11,.0f} {t['ret_pct']:>+7.1f}% {t['max_dd']:>6.1f}% "
              f"{t['final'] - bh['final']:>+10,.0f}")
        if t["open_trade"]:
            ot = t["open_trade"]
            print(f"{'':<28}   OPEN since {ot['entry_date']}: ${ot['entry']} -> "
                  f"${ot['last']} ({ot['unreal_pct']:+.1f}%, {ot['hold_days']}d held)")

    path = os.path.join(os.path.dirname(CSV), "amd_oos_results.json")
    with open(path, "w") as f:
        json.dump(RESULTS, f, indent=2, default=str)
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
