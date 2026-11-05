"""Can AMD make 20% or more every quarter? One trade per report, selling before the next report's usual fall (user order 2026-11-05).

First the ceiling: the most any perfectly timed trade could make between two reports. Then rules in Vibe-Trading, $100k, cash
between trades, next-open fills, 5 bp slippage, data through 2026-11-05. USER_RULE was set before any backtest of this family.
Fixing quarters already seen is fitting, so rules are also ranked on the first 8 quarters and scored on the last 4.

Usage: venvs/vt/Scripts/python amd_quarters.py. Writes results/amd_quarters.csv and results/amd_quarters_trades.csv.
"""
import importlib.util
import multiprocessing as mp
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import amd_cycle as A
import sweep

END = "2026-11-06"
WINDOWS = {"oct25": "2025-10-01", "3y": A.FROM}
USER_RULE = "day13_gap10_before15_sell20"
TIME_RULE = "time_d13_before15"  # time only, from the pattern's typical low and high; set before any backtest of it
DAYS, BEFORE = (1, 3, 5, 8, 10, 13, 15, 18, 20), (5, 10, 15, 20, 25, 30)
ENTRIES = {"day13": {"buy_on": "day13"}, "dip10": {"buy_on": "dip10"}, "bounce5": {"buy_on": "bounce", "bounce": 0.05}, "bounce10": {"buy_on": "bounce", "bounce": 0.10}}
EXITS = {"hold": {}, "sell20": {"target": 0.20, "exit": "sell"}, "sell30": {"target": 0.30, "exit": "sell"}, "trail20": {"target": 0.20, "exit": "trail", "trail": 0.10}}

spec = importlib.util.spec_from_file_location("signal_template", Path(__file__).parent / "signal_template.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def rule_list():
    out = {"hold": {"rule": "hold", "cadence": "W"}}
    for entry, e in ENTRIES.items():
        for gap in (0, 0.10):
            for before in (10, 15, 20):
                for name, x in EXITS.items():
                    out[f"{entry}_gap{int(gap * 100)}_before{before}_{name}"] = {"rule": "quarter", "cadence": "D", "gap_up": gap, "before_next": before, **e, **x}
    for day in DAYS:
        for before in BEFORE:
            base = {"rule": "quarter", "cadence": "D", "buy_on": "day", "day": day, "before_next": before}
            out[f"time_d{day}_before{before}"] = base
            if before > 3:
                out[f"time_d{day}_before{before}_pre3"] = {**base, "pre_leg": 3}
    return out


RULES = rule_list()


def job(window, name):
    return ["AMD"], {**A.BASE, "end": END, "trade_from": WINDOWS[window], **RULES[name], "tag": f"Q_{window}_{name}"}


def trades_of(name, frame, reports):
    """Each trade at next-open fills, placed in the quarter of the report before it. An unfilled signal is left out."""
    pos = rules._amdcycle(frame, job("3y", name)[1])
    change = pos[pos.diff().fillna(pos) != 0]
    rows, buy = [], None
    for day, val in change.items():
        later = frame.index[frame.index > day]
        if not len(later):
            continue
        fill = frame.open.loc[later[0]]
        if val:
            buy = (later[0], fill)
        elif buy:
            quarter = reports[reports <= buy[0]][-1]
            rows.append({"rule": name, "quarter": quarter.date(), "bought": buy[0].date(), "buy": buy[1], "sold": later[0].date(), "sell": fill, "gain": fill / buy[1] - 1})
            buy = None
    if buy:
        quarter = reports[reports <= buy[0]][-1]
        rows.append({"rule": name, "quarter": quarter.date(), "bought": buy[0].date(), "buy": buy[1], "sold": None, "sell": frame.close.iloc[-1], "gain": frame.close.iloc[-1] / buy[1] - 1})
    return rows


def main():
    os.environ["VIBE_TRADING_ALLOWED_RUN_ROOTS"] = str(sweep.RUNS)
    os.environ["VIBE_TRADING_DATA_CACHE"] = "0"  # today's bar is needed
    raw = yf.download("AMD", start=A.BASE["start"], end=END, auto_adjust=True, progress=False)
    frame = pd.DataFrame({"close": raw["Close"].squeeze(), "open": raw["Open"].squeeze()}).dropna()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    reports = pd.to_datetime([d for d in A.REPORTS]).sort_values()
    done = reports[reports >= "2023-10-01"]
    idx, c = frame.index, frame.close.values
    print("ceiling: the best single buy then sell between two reports, at closing prices")
    ceiling = []
    for a, b in zip(done[:-1], done[1:]):
        i, k = int(idx.searchsorted(a)), int(idx.searchsorted(b))
        best = max((c[y] / c[x] - 1, x, y) for x in range(i + 1, k) for y in range(x + 1, k + 1))
        ceiling.append(best[0])
        print(f"  {a.date()}: {best[0]:+.0%}, buy {idx[best[1]].date()} {c[best[1]]:.2f}, sell {idx[best[2]].date()} {c[best[2]]:.2f}, {k - best[2]} days before the next report")
    print(f"  quarters where even perfect timing could reach 20%: {sum(g >= .20 for g in ceiling)} of {len(ceiling)}")

    jobs = [job(w, n) for w in WINDOWS for n in RULES]
    with mp.Pool(4, initializer=sweep.init_worker) as pool:
        for name, status, err in pool.imap_unordered(sweep.run_one, jobs):
            if status == "error":
                print("ERROR", name, str(err)[:400])

    rows, all_trades = [], []
    quarters = [q.date() for q in done[:-1]]
    for name in RULES:
        out = {"rule": name}
        for window, begin in WINDOWS.items():
            eq = pd.read_csv(A.RES / "curves_amd" / f"AMD__amdcycle__Q_{window}_{name}.csv", usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
            eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
            eq = eq[~eq.index.duplicated()].loc[begin:]
            out[f"{window}_value"] = eq.iloc[-1]
            out[f"{window}_dd"] = float(np.min(eq / eq.cummax() - 1))
        if name != "hold":
            tr = pd.DataFrame(trades_of(name, frame, reports))
            all_trades.append(tr)
            gain = tr.groupby("quarter").gain.apply(lambda s: np.prod(1 + s) - 1).reindex(quarters).fillna(0.0)
            out.update({"q20": int((gain >= .20).sum()), "q_loss": int((gain < 0).sum()), "q_worst": gain.min(), "q_median": gain.median(), "first8_q20": int((gain.iloc[:8] >= .20).sum()), "first8": np.prod(1 + gain.iloc[:8]),
                        "last4_q20": int((gain.iloc[8:] >= .20).sum()), "last4": np.prod(1 + gain.iloc[8:]), "last4_worst": gain.iloc[8:].min()})
        rows.append(out)
    table = pd.DataFrame(rows)
    table.to_csv(A.RES / "amd_quarters.csv", index=False)
    pd.concat(all_trades).to_csv(A.RES / "amd_quarters_trades.csv", index=False)
    pd.set_option("display.width", 220, "display.max_columns", 20, "display.max_rows", 60)
    fmt = lambda v: f"{v:,.2f}"
    show = ["rule", "oct25_value", "oct25_dd", "3y_value", "3y_dd", "q20", "q_loss", "q_worst", "q_median", "last4_q20", "last4"]
    grid = table[table.rule != "hold"]
    hold = table[table.rule == "hold"].iloc[0]
    print(f"\nAMD held: since Oct 2025 ${hold.oct25_value:,.0f} (worst {hold.oct25_dd:.0%}); 3 years ${hold['3y_value']:,.0f} (worst {hold['3y_dd']:.0%})")
    print(f"{len(grid)} rules, {len(quarters)} quarters. Beat held: since Oct 2025 {(grid.oct25_value > hold.oct25_value).sum()}, 3 years {(grid['3y_value'] > hold['3y_value']).sum()}. Most quarters at 20%+: {grid.q20.max()}")
    print("\nrule set in advance")
    print(table[table.rule == USER_RULE][show].to_string(index=False, float_format=fmt))
    print("\nbest 6 by 3-year value")
    print(grid.sort_values("3y_value", ascending=False).head(6)[show].to_string(index=False, float_format=fmt))
    print("\nbest 6 by quarters at 20%+")
    print(grid.sort_values(["q20", "3y_value"], ascending=False).head(6)[show].to_string(index=False, float_format=fmt))
    print("\nbest 6 since Oct 2025")
    print(grid.sort_values("oct25_value", ascending=False).head(6)[show].to_string(index=False, float_format=fmt))
    pick = grid.sort_values(["first8_q20", "first8"], ascending=False).iloc[0]
    top = grid.sort_values(["first8_q20", "first8"], ascending=False).head(10)
    print(f"\nfair test, ranked on the first 8 quarters: {pick.rule} had {pick.first8_q20} of 8 at 20%+, {pick.first8:.2f}x; then in the last 4 quarters {pick.last4_q20} of 4 at 20%+, {pick.last4:.2f}x, worst {pick.last4_worst:.1%}. Top 10 median last 4: {top.last4.median():.2f}x")
    px = pd.Series(c, index=idx)
    print(f"AMD held: first 8 quarters {px.asof(done[8]) / px.asof(done[0]):.2f}x; last 4 quarters {px.asof(done[-1]) / px.asof(done[8]):.2f}x")
    timed = grid[grid.rule.str.startswith("time_")]
    plain = timed[~timed.rule.str.endswith("pre3")]
    print(f"\n=== time only: {len(timed)} rules. Beat held: since Oct 2025 {(timed.oct25_value > hold.oct25_value).sum()}, 3 years {(timed['3y_value'] > hold['3y_value']).sum()}. Most quarters at 20%+: {timed.q20.max()}")
    print("rule set in advance")
    print(table[table.rule == TIME_RULE][show].to_string(index=False, float_format=fmt))
    for label, value in (("3-year value in $k", "3y_value"), ("value since Oct 2025 in $k", "oct25_value")):
        print(f"\n{label}, by buy day after the report (rows) and days before the next report to sell (columns)")
        view = plain.assign(day=plain.rule.str.extract(r"_d(\d+)_")[0].astype(int), before=plain.rule.str.extract(r"before(\d+)")[0].astype(int))
        print((view.pivot(index="day", columns="before", values=value) / 1000).round(0).to_string())
    print("\nbest 6 time-only by 3-year value")
    print(timed.sort_values("3y_value", ascending=False).head(6)[show].to_string(index=False, float_format=fmt))
    print("\nbest 6 time-only by quarters at 20%+")
    print(timed.sort_values(["q20", "3y_value"], ascending=False).head(6)[show].to_string(index=False, float_format=fmt))
    pre = timed[timed.rule.str.endswith("pre3")]
    print(f"\nextra 3-day trade before reports: median 3-year value {pre['3y_value'].median():,.0f} with it, {plain['3y_value'].median():,.0f} without")
    pick = timed.sort_values(["first8_q20", "first8"], ascending=False).iloc[0]
    top = timed.sort_values(["first8_q20", "first8"], ascending=False).head(10)
    print(f"fair test, time only, ranked on the first 8 quarters: {pick.rule} had {pick.first8_q20} of 8 at 20%+, {pick.first8:.2f}x; then in the last 4 quarters {pick.last4_q20} of 4 at 20%+, {pick.last4:.2f}x, worst {pick.last4_worst:.1%}. Top 10 median last 4: {top.last4.median():.2f}x")
    for name in dict.fromkeys((TIME_RULE, USER_RULE, pick.rule, timed.sort_values("3y_value", ascending=False).rule.iloc[0], timed.sort_values(["q20", "3y_value"], ascending=False).rule.iloc[0])):
        tr = pd.concat(all_trades)
        print(f"\ntrades of {name}")
        print(tr[tr.rule == name].drop(columns="rule").to_string(index=False, float_format=lambda v: f"{v:.2f}"))


if __name__ == "__main__":
    main()
