"""Re-run the strongest buy rules from amd_buy_search.py in Vibe-Trading and write Lumibot jobs. Backtest only, no orders.

The buy dates come from close-only signals. They are passed as a list so both backtesters follow the same decisions. The sell rule is fixed. The plain
zone rule is included as a control, and should match the $578,183 found in amd_zone_search.py.

Usage: venvs/vt/Scripts/python amd_buy_verify.py <lumibot job path>
"""
import json
import multiprocessing as mp
import os
import sys

import numpy as np
import pandas as pd

import amd_buy_search as B
import amd_zone_search as Z
import sweep

FROM, RECENT = Z.FROM, "2025-05-01"
RULES = {
    "control": ("plain zone: stochastic<25, RSI<40", None, "none"),
    "zone_qqq": ("zone when QQQ is below its 100-day average", None, "QQQ below 100d"),
    "second_low": ("second low: 3% bounce, back within 10% of the low in 60 days, RSI 5 higher", None, "none"),
    "day13_200d": ("day 13 after each report when AMD is above its 200-day average", None, "AMD above 200d"),
}
RAW = {
    "control": B.zone(25, 40, 0, 0),
    "zone_qqq": B.zone(25, 40, 0, 0),
    "second_low": B.second_low(0.03, 0.10, 60, 5, 0),
    "day13_200d": B.after_report("any", 0, "day 13"),
}


def job(name, dates, window):
    return ["AMD"], {**Z.A.BASE, "end": Z.END, "trade_from": window, "rule": "buydates", "cadence": "D", "buy_dates": dates, **{k: B.SELL[k] for k in ("sell_s", "sell_r", "sell_dn", "min_days")}, "tag": f"BD_{name}_{window}"}


def value(name, window):
    eq = pd.read_csv(Z.RES / "curves_amd" / f"AMD__amdcycle__BD_{name}_{window}.csv", usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
    eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
    eq = eq[~eq.index.duplicated()].loc[window:]
    return eq.iloc[-1], float(np.min(eq / eq.cummax() - 1))


def trades(days):
    pos = B.replay(days)
    change = np.diff(pos, prepend=0.0)
    lines = []
    for b in np.nonzero(change > 0)[0]:
        later = np.nonzero((change < 0) & (np.arange(B.n) > b))[0]
        s = later[0] if len(later) else None
        end = B.closes[s] if s is not None else B.closes[-1]
        near_b = "near a table low" if np.abs(Z.buy_targets - b).min() <= Z.NEAR else ""
        near_s = "near a table high" if s is not None and np.abs(Z.sell_targets - s).min() <= Z.NEAR else ""
        lines.append(f"  {B.idx[b].strftime('%b %d %y')} {B.closes[b]:7.2f} -> {B.idx[s].strftime('%b %d %y') if s is not None else 'still held'} {end:7.2f} {end / B.closes[b] - 1:+7.1%}  {near_b} {near_s}".rstrip())
    return "\n".join(lines)


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
    os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
    plans = {}
    for name, (_, _, fname) in RULES.items():
        days = B.thin([i for i in RAW[name] if B.FILTERS[fname][i]])
        plans[name] = (days, [str(B.idx[i].date()) for i in days])
    jobs = [job(name, plans[name][1], w) for name in RULES for w in (FROM, RECENT)]
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        for name, status, err in pool.imap_unordered(sweep.run_one, jobs):
            if status == "error":
                print("ERROR", name, str(err)[:300])
    held = Z.held_parts()
    print(f"AMD held: first {held['first']:.2f}x, last {held['last']:.2f}x, all {held['all']:.2f}x")
    lb = []
    for name, (label, _, fname) in RULES.items():
        days, dates = plans[name]
        a, b = value(name, FROM), value(name, RECENT)
        money = Z.parts(B.replay(days))
        print(f"\n{name}: {label}\n  replay: first {money['first']:.2f}x, last {money['last']:.2f}x, all {money['all']:.2f}x")
        print(f"  Vibe-Trading from $100,000: since Aug 2023 ${a[0]:,.0f} (worst {a[1]:.0%}); since May 2025 ${b[0]:,.0f} (worst {b[1]:.0%})")
        print(trades(days))
        cfg = job(name, dates, FROM)
        lb.append({"name": sweep.key(*cfg), "codes": ["AMD"], "cfg": cfg[1], "start": FROM, "end": "2026-11-05"})
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(lb, f)


if __name__ == "__main__":
    main()
