"""Find signals that reproduce the buy-low, sell-high shapes in AMD_QUARTERS.md, from indicators only. Backtest only, no orders.

Targets are the buys and sells in amd_quarter_trades.py, known only afterwards. A rule catches a target with a signal within 10 trading days. The
shape score (F1) rewards catching targets and punishes false trades. A fast replay screens every setting: decided at the close, filled at the next open,
5 bp per side, which earlier matched Vibe-Trading in every year. Fair test: rank on days up to May 2025 and score after, then the reverse. Each part's
money comes from daily value, so a trade across the split counts in each part only for its own days. The winners are re-run in Vibe-Trading, and Lumibot checks them next. Writes results/amd_zone_search.csv.

Usage: venvs/vt/Scripts/python amd_zone_search.py <lumibot job path>
"""
import importlib.util
import itertools
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import amd_cycle as A
import sweep

HERE = Path(__file__).parent
RES = HERE / "results"
END, FROM, SPLIT = "2026-11-06", "2023-08-01", pd.Timestamp("2025-05-01")
BUYS = ["2023-10-26", "2024-04-19", "2024-08-07", "2025-01-28", "2025-04-08", "2025-09-05", "2025-12-17", "2026-03-03", "2026-05-07", "2026-09-03"]
SELLS = ["2024-03-07", "2024-07-10", "2024-10-08", "2025-03-25", "2025-07-30", "2025-10-29", "2026-01-23", "2026-05-01", "2026-06-30", "2026-10-06"]
NEAR = 10

spec = importlib.util.spec_from_file_location("signal_template", HERE / "signal_template.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)

raw = yf.download("AMD", start=A.BASE["start"], end=END, auto_adjust=True, progress=False)
frame = pd.DataFrame({k.lower(): raw[k].squeeze() for k in ("Open", "High", "Low", "Close", "Volume")}).dropna()
frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
idx = frame.index
opens, closes = frame.open.values, frame.close.values
inputs = rules._zone_inputs(frame)
start = int(idx.searchsorted(pd.Timestamp(FROM)))
buy_targets = np.array([idx.searchsorted(pd.Timestamp(d)) for d in BUYS])
sell_targets = np.array([idx.searchsorted(pd.Timestamp(d)) for d in SELLS])
split = int(idx.searchsorted(SPLIT))


def grid():
    for buy_s, buy_r, depth, buy_up, sell_s, sell_r, reach, sell_dn, min_days, stop in itertools.product((20, 25), (40, 45), (0, 0.15, 0.25), (0, 0.03, 0.05, -1), (80, 90), (60, 65, 70), (0, 0.15, 0.25), (0, 0.03, 0.05, 0.08, -1), (5, 15), (0, 0.25)):
        yield {"buy_s": buy_s, "buy_r": buy_r, "depth": depth, "buy_up": buy_up, "sell_s": sell_s, "sell_r": sell_r, "reach": reach, "sell_dn": sell_dn, "min_days": min_days, "stop": stop}


def shape(signals, targets):
    if not len(targets):
        return 0.0, 0.0, 0.0, 0
    if not len(signals):
        return 0.0, 0.0, 0.0, 0
    gaps = np.abs(signals[:, None] - targets[None, :])
    caught = (gaps.min(axis=0) <= NEAR).mean()
    right = (gaps.min(axis=1) <= NEAR).mean()
    return (2 * caught * right / (caught + right) if caught + right else 0.0), caught, right, len(signals)


def equity(pos):
    """Daily value of a position decided at each close and filled at the next open, 5 bp per side, so a date split cuts trades fairly."""
    was = np.r_[0.0, pos[:-1]]
    before = np.r_[0.0, was[:-1]]
    daily = np.ones(len(pos))
    daily[1:] = np.where((was[1:] == 1) & (before[1:] == 1), closes[1:] / closes[:-1], 1.0)
    daily[1:] = np.where((was[1:] == 1) & (before[1:] == 0), closes[1:] / opens[1:] * 0.9995, daily[1:])
    daily[1:] = np.where((was[1:] == 0) & (before[1:] == 1), opens[1:] / closes[:-1] * 0.9995, daily[1:])
    return np.cumprod(daily)


def parts(pos):
    eq = equity(pos)
    return {"first": eq[split - 1] / eq[start], "last": eq[-1] / eq[split - 1], "all": eq[-1] / eq[start]}


def held_parts():
    pos = np.zeros(len(closes))
    pos[start:] = 1.0
    return parts(pos)


def evaluate(p):
    pos = rules._zone_loop(*inputs, p, start)
    money = parts(pos)
    change = np.diff(pos, prepend=0.0)
    buys, sells = np.nonzero(change > 0)[0], np.nonzero(change < 0)[0]
    out = {}
    trades = []
    for b in buys:
        later = sells[sells > b]
        s = later[0] if len(later) else None
        fill_b = opens[b + 1] if b + 1 < len(opens) else closes[b]
        fill_s = (opens[s + 1] if s + 1 < len(opens) else closes[s]) if s is not None else closes[-1]
        trades.append((b, fill_s / fill_b * (1 - 0.001)))
    for name, lo, hi in (("first", start, split), ("last", split, len(idx)), ("all", start, len(idx))):
        bs, ss = buys[(buys >= lo) & (buys < hi)], sells[(sells >= lo) & (sells < hi)]
        bt, st = buy_targets[(buy_targets >= lo) & (buy_targets < hi)], sell_targets[(sell_targets >= lo) & (sell_targets < hi)]
        f_b, c_b, r_b, n_b = shape(bs, bt)
        f_s, c_s, r_s, n_s = shape(ss, st)
        mult = money[name]
        wins = [m > 1 for b, m in trades if lo <= b < hi]
        out.update({f"{name}_score": (f_b + f_s) / 2, f"{name}_buy_caught": c_b, f"{name}_buy_right": r_b, f"{name}_sell_caught": c_s, f"{name}_sell_right": r_s, f"{name}_buys": n_b, f"{name}_mult": mult, f"{name}_win": float(np.mean(wins)) if wins else np.nan})
    return {**p, **out}


def name_of(p):
    return "Z_" + "_".join(f"{k}{str(v).replace('.', 'p').replace('-', 'm')}" for k, v in p.items())


def job(p, window):
    return ["AMD"], {**A.BASE, "end": END, "trade_from": window, "rule": "zones", "cadence": "D", **p, "tag": f"{name_of(p)}_{window}"}


def vibe_value(p, window):
    eq = pd.read_csv(RES / "curves_amd" / f"AMD__amdcycle__{name_of(p)}_{window}.csv", usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
    eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
    eq = eq[~eq.index.duplicated()].loc[window:]
    return eq.iloc[-1], float(np.min(eq / eq.cummax() - 1))


def show_trades(p):
    pos = rules._zone_loop(*inputs, p, start)
    change = np.diff(pos, prepend=0.0)
    lines = []
    for b in np.nonzero(change > 0)[0]:
        later = np.nonzero((change < 0) & (np.arange(len(pos)) > b))[0]
        s = later[0] if len(later) else None
        near_b = "real low" if np.abs(buy_targets - b).min() <= NEAR else "false"
        near_s = ("real high" if np.abs(sell_targets - s).min() <= NEAR else "false") if s is not None else "open"
        end_price = closes[s] if s is not None else closes[-1]
        lines.append(f"  buy {idx[b].date()} {closes[b]:7.2f} ({near_b}), sell {str(idx[s].date()) if s is not None else 'holding':>10} {end_price:7.2f} ({near_s}), {end_price / closes[b] - 1:+.1%}")
    return "\n".join(lines)


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "1"
    os.environ["VIBE_TRADING_DATA_CACHE_ROOT"] = r"E:\strategy-repos\vt_cache"
    t = pd.DataFrame([evaluate(p) for p in grid()])
    t.to_csv(RES / "amd_zone_search.csv", index=False)
    pd.set_option("display.width", 230, "display.max_columns", 40, "display.max_rows", 60)
    fmt = lambda v: f"{v:.2f}"
    held = held_parts()
    print(f"{len(t)} settings. AMD held: first part {held['first']:.2f}x, last part {held['last']:.2f}x, all {held['all']:.2f}x. Targets: {len(buy_targets)} buys, {len(sell_targets)} sells")
    print(f"beat held on all: {(t.all_mult > held['all']).sum()}; on the first part {(t.first_mult > held['first']).sum()}; on the last part {(t.last_mult > held['last']).sum()}; on both parts {((t.first_mult > held['first']) & (t.last_mult > held['last'])).sum()}")
    params = ["buy_s", "buy_r", "depth", "buy_up", "sell_s", "sell_r", "reach", "sell_dn", "min_days", "stop"]
    short = params + ["all_score", "all_buy_caught", "all_buy_right", "all_sell_caught", "all_sell_right", "all_buys", "all_mult", "all_win", "first_mult", "last_mult"]
    print("\nbest 8 by shape score, all periods")
    print(t.sort_values(["all_score", "all_mult"], ascending=False).head(8)[short].to_string(index=False, float_format=fmt))
    print("\nbest 8 by money, all periods")
    print(t.sort_values("all_mult", ascending=False).head(8)[short].to_string(index=False, float_format=fmt))
    picks = {}
    for label, train, test in (("first to last", "first", "last"), ("last to first", "last", "first")):
        for by, col in (("shape", f"{train}_score"), ("money", f"{train}_mult")):
            order = t.sort_values([col, f"{train}_mult"], ascending=False)
            top = order.iloc[0]
            near = order.head(50)
            print(f"\nchosen by {by} on the {train} part: {train} {top[f'{train}_mult']:.2f}x (held {held[train]:.2f}x), score {top[f'{train}_score']:.2f}. On the {test} part: {top[f'{test}_mult']:.2f}x (held {held[test]:.2f}x), score {top[f'{test}_score']:.2f}, caught buys {top[f'{test}_buy_caught']:.0%}, sells {top[f'{test}_sell_caught']:.0%}, trades won {top[f'{test}_win']:.0%}")
            print(f"  top 50 on the {test} part: median {near[f'{test}_mult'].median():.2f}x; beat held {(near[f'{test}_mult'] > held[test]).sum()} of 50")
            picks[f"{by}, {label}"] = {k: top[k].item() if hasattr(top[k], "item") else top[k] for k in params}
    for col in params:
        print(f"\nby {col}: median multiple and score")
        print(t.groupby(col)[["first_mult", "last_mult", "all_mult", "all_score"]].median().round(2).to_string())
    picks["best shape, all periods"] = {k: t.sort_values(["all_score", "all_mult"], ascending=False).iloc[0][k].item() for k in params}
    picks["best money, all periods"] = {k: t.sort_values("all_mult", ascending=False).iloc[0][k].item() for k in params}
    jobs = [job(p, w) for p in picks.values() for w in (FROM, "2025-05-01")]
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        for name, status, err in pool.imap_unordered(sweep.run_one, jobs):
            if status == "error":
                print("ERROR", name, str(err)[:300])
    lb = []
    for label, p in picks.items():
        a = vibe_value(p, FROM)
        b = vibe_value(p, "2025-05-01")
        print(f"\n{label}: {p}\n  Vibe-Trading from $100,000: since Aug 2023 ${a[0]:,.0f} (worst {a[1]:.0%}); since May 2025 ${b[0]:,.0f} (worst {b[1]:.0%})")
        print(show_trades(p))
        lb.append({"name": sweep.key(*job(p, FROM)), "codes": ["AMD"], "cfg": job(p, FROM)[1], "start": FROM, "end": "2026-11-05"})
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(lb, f)


if __name__ == "__main__":
    main()
