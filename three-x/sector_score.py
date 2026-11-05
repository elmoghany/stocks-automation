"""Score AMD plus a partner from another sector against 2x in 12 months.

Rules fixed before any sector result was seen. All windows are 252 bars, restarted every 21.
Bars before the partner listed are excluded.

What counts (user order 2026-11-04):
  - A period is a hit only if it reached 2x AND the position changed at least once in it. A year all in
    cash, or all in one stock, is "idle" and can never be a hit.
  - Reference 1: AMD bought and held. Reference 2: half AMD, half the same partner, bought and held.

Tests, strongest last:
  1. hindsight: best config per partner. Shown only to explain the others. Not evidence.
  2. same_rule: one config applied to every partner, so no partner is picked by its result.
  3. holdout: choose config and partner on data through 2021 only, then score 2022 onward unchanged.
  4. walk_forward: each month pick on trailing data only, then hold 12 months.
  5. nested: at each start also choose the lookback and ranking from walk-forward windows already finished.

Slow pools hold only configs that decide about every 30 days or more, including the switch rule that holds
a stock or cash for at least 21 or 42 bars, and the AMD-first rules.

AMD-first rules (added at the user's request, before any of their results): AMD is bought whenever it
qualifies, the second stock otherwise. Sizing pools compare $100k, $50k, 3 or 4 steps on falls, and half in
each stock. The auto pool is the fair test of "growth and high volume": its second stock is chosen each January
from earlier data, so it does not assume we knew CEG or PLTR would win.

Pass mark: a rule "reliably" makes 2x if it hits in at least 50% of periods in the holdout, walk_forward or
nested test.

Usage: venvs/vt/Scripts/python sector_score.py
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import sweep

HERE = Path(__file__).parent
RES = HERE / "results"
TARGET, HOLD, STEP, COST = 2.0, 252, 21, 0.001
SECTOR_OF = {t: s for s, g in sweep.SECTORS.items() for names in g.values() for t in names}
ON_LIST = {t for g in sweep.SECTORS.values() for t in g["list"]}
AUTO = sweep.json.loads((RES / "growth_partner.json").read_text(encoding="utf-8"))
SECTOR_OF.update({label: "auto" for label in AUTO})
ON_LIST |= {label for label in AUTO if label.startswith("auto_")}  # chosen from the halal list

spec = importlib.util.spec_from_file_location("signal_template", HERE / "signal_template.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def curve(name):
    for folder in ("curves_sector", "curves"):
        path = RES / folder / f"{name}.csv"
        if path.exists():
            s = pd.read_csv(path, usecols=["timestamp", "equity"], parse_dates=["timestamp"], index_col="timestamp").equity
            s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
            return s[~s.index.duplicated()]
    return None


def partner(name):
    head = name.split("__")[0]
    return head.split("+")[1] if "+" in head else head


def rule(name):
    return name.split("__", 1)[1]


def load():
    all_jobs = sweep.sector_jobs() + sweep.switch_jobs() + sweep.first_jobs() + sweep.auto_jobs()
    jobs = {sweep.key(codes, cfg): (codes, cfg) for codes, cfg in all_jobs}
    frames = {n: s for n in jobs if (s := curve(n)) is not None}
    eq = pd.DataFrame(frames).sort_index().ffill(limit=5)
    return eq, {n: jobs[n] for n in eq.columns}


def changes(eq, jobs):
    """Cumulative count of position changes per config, recomputed from the rules on the same closes."""
    tickers = sorted({c for codes, _ in jobs.values() for c in codes} | {"QQQ", "SPY"})
    bars = yf.download(tickers, start="2012-01-01", end=sweep.END, auto_adjust=True, progress=False)
    bars.index = pd.DatetimeIndex(bars.index).tz_localize(None).normalize()
    raw, vol = bars["Close"], bars["Volume"]
    first = {t: raw[t].first_valid_index() for t in tickers}
    first.update({label: pd.Timestamp("2013-02-01") for label in AUTO})
    gate = (raw["QQQ"] > raw["QQQ"].rolling(200).mean()).astype(float)
    frames = {k: pd.DataFrame({"close": raw[k], "volume": vol[k]}).dropna() for k in tickers}
    out = {}
    for name, (codes, cfg) in jobs.items():
        data = {k: frames[k] for k in codes}
        if cfg["family"] == "first":
            for k in codes:
                data[k] = data[k].copy()
                data[k].attrs["bench"] = raw["SPY"]
            pos = rules._first(data, codes, cfg)["__state__"]
        else:
            sig = (rules._switch if cfg["family"] == "switch" else rules._rotate)(data, codes, cfg)
            pos = sig[codes[0]] + 2 * sig[codes[1]]
        if cfg.get("regime_code"):
            pos = pos * gate.reindex(pos.index).fillna(0.0)
        out[name] = (pos.diff().fillna(0) != 0).cumsum().reindex(eq.index, method="ffill").fillna(0)
    return pd.DataFrame(out)[list(eq.columns)], first, raw


def stats(mult, traded, ref1=None, ref2=None):
    """Hit rate and reference comparison over one set of periods."""
    m, t = np.asarray(mult, float), np.asarray(traded, bool)
    row = {"n": len(m), "pct_2x": float(((m >= TARGET) & t).mean()), "pct_idle": float((~t).mean()),
           "pct_loss": float((m < 1).mean()), "median": float(np.median(m)), "worst": float(m.min()), "best": float(m.max())}
    if ref1 is not None:
        r1, r2 = np.asarray(ref1, float), np.asarray(ref2, float)
        row.update({"r1_2x": float((r1 >= TARGET).mean()), "r1_med": float(np.nanmedian(r1)), "beat_r1": float((m > r1).mean()),
                    "r2_2x": float((r2 >= TARGET).mean()), "r2_med": float(np.nanmedian(r2)), "beat_r2": float((m > r2).mean())})
    return row


class Refs:
    def __init__(self, index, raw):
        self.index = index
        self.raw = raw.reindex(index, method="ffill", limit=5)
        self.amd = self.raw["AMD"].values

    def at(self, i, t):
        """12-month multiple of AMD held, and of half AMD and half the second stock held."""
        if t in AUTO:
            t = AUTO[t].get(str(self.index[i].year))
        r1 = self.amd[i + HOLD] / self.amd[i]
        other = self.raw[t].values if t in self.raw else None
        if other is None or not np.isfinite(other[i]) or not np.isfinite(other[i + HOLD]):
            return r1, r1
        return r1, 0.5 * (r1 + other[i + HOLD] / other[i])


def window_table(eq, chg, refs, first, name, start=None, end=None):
    """Every 12-month period of one config, optionally limited to starts in [start, end)."""
    t = partner(name)
    x, c, rows = eq[name].values, chg[name].values, []
    for i in range(0, len(eq) - HOLD, STEP):
        d = eq.index[i]
        if d < first[t] or (start and d < start) or (end and d >= end) or not (np.isfinite(x[i]) and np.isfinite(x[i + HOLD])):
            continue
        r1, r2 = refs.at(i, t)
        rows.append((d, x[i + HOLD] / x[i], c[i + HOLD] > c[i], r1, r2))
    return pd.DataFrame(rows, columns=["start", "mult", "traded", "r1", "r2"])


def walk(eq, chg, refs, first, cols, years, how):
    x, c, r = eq[cols].values, chg[cols].values, np.log(eq[cols]).diff().values
    firsts = np.array([first[partner(n)] for n in cols], dtype="datetime64[ns]")
    look, idx, rows = 252 * years, eq.index, []
    for i in range(look, len(idx) - HOLD, STEP):
        ok = (firsts <= np.datetime64(idx[i])) & np.isfinite(x[i - look]) & np.isfinite(x[i]) & np.isfinite(x[i + HOLD])
        ok &= c[i] > c[i - look]  # only rules that actually traded in the lookback may be chosen
        if not ok.any():
            continue
        if how == "return":
            score = x[i] / x[i - look]
        else:
            win = r[i - look + 1:i + 1]
            score = np.nanmean(win, axis=0) / np.nanstd(win, axis=0)
        score = np.where(ok & np.isfinite(score), score, -np.inf)
        j = int(np.argmax(score))
        path = x[i:i + HOLD + 1, j]
        r1, r2 = refs.at(i, partner(cols[j]))
        rows.append({"start": idx[i], "pick": cols[j], "mult": path[-1] / path[0] * (1 - COST), "traded": c[i + HOLD, j] > c[i, j],
                     "r1": r1, "r2": r2, "dd": float(np.nanmin(path / np.fmax.accumulate(path) - 1))})
    return pd.DataFrame(rows)


def nested(variants, score_name):
    mult = pd.DataFrame({k: v.set_index("start").mult for k, v in variants.items()}).sort_index()
    hit = pd.DataFrame({k: (v.mult >= TARGET) & v.traded for k, v in ((k, v.set_index("start")) for k, v in variants.items())}).reindex(mult.index)
    keyed = {k: v.set_index("start") for k, v in variants.items()}
    rows = []
    for t in mult.index:
        cut = t - pd.DateOffset(months=13)
        ok = [c for c in mult.columns if mult.loc[:cut, c].notna().sum() >= 24 and pd.notna(mult.at[t, c])]
        if not ok:
            continue
        if score_name == "share_2x":
            score = hit.loc[:cut, ok].astype(float).mean()
        elif score_name == "median":
            score = mult.loc[:cut, ok].median()
        else:
            score = mult.loc[:cut, ok].mean()
        pick = score.idxmax()
        row = keyed[pick].loc[t]
        rows.append({"start": t, "variant": pick, "pick": row.pick, "mult": row.mult, "traded": row.traded, "r1": row.r1, "r2": row.r2})
    return pd.DataFrame(rows)


def sizing_of(name):
    if "modeboth" in name:
        return "half in each"
    if "steps4" in name:
        return "4 steps on falls"
    if "steps3" in name:
        return "3 steps on falls"
    return "$50k" if "size0p5" in name else "$100k"


def main():
    fmt = lambda v: f"{v:.2f}"
    pd.set_option("display.width", 230, "display.max_colwidth", 44, "display.max_columns", 30)
    eq, jobs = load()
    chg, first, raw = changes(eq, jobs)
    refs = Refs(eq.index, raw)
    print("configs", eq.shape[1], "partners", len({partner(c) for c in eq.columns}), "bars", len(eq), eq.index[0].date(), eq.index[-1].date())

    # 1 and 2: per-config tables
    rows = []
    for c in eq.columns:
        w = window_table(eq, chg, refs, first, c)
        s = eq[c].dropna()
        s = s[s.index >= first[partner(c)]]
        rows.append({"config": c, "partner": partner(c), "sector": SECTOR_OF[partner(c)], "on_list": partner(c) in ON_LIST,
                     **stats(w.mult, w.traded, w.r1, w.r2), "last_12m": s.iloc[-1] / s.iloc[-HOLD - 1],
                     "max_dd": (s / s.cummax() - 1).min(),
                     "trades_per_y": (chg[c].iloc[-1] - chg[c][chg.index >= first[partner(c)]].iloc[0]) / (len(s) / 252)})
    table = pd.DataFrame(rows)
    table.to_csv(RES / "sector_hindsight.csv", index=False)
    show = ["config", "sector", "on_list", "n", "pct_2x", "pct_idle", "pct_loss", "median", "worst", "r1_2x", "r2_2x", "r2_med", "beat_r1", "beat_r2", "last_12m", "max_dd", "trades_per_y"]
    print("\n=== 1. HINDSIGHT: best config per partner (not evidence) ===")
    print(table.sort_values("pct_2x", ascending=False).groupby("partner").head(1)[show].to_string(index=False, float_format=fmt))

    same = table.groupby(table.config.map(rule)).agg(
        partners=("config", "size"), pct_2x=("pct_2x", "mean"), idle=("pct_idle", "mean"), loss=("pct_loss", "mean"), median=("median", "mean"),
        worst=("worst", "mean"), r1_2x=("r1_2x", "mean"), r2_2x=("r2_2x", "mean"), beat_r1=("beat_r1", "mean"), beat_r2=("beat_r2", "mean"),
        trades_per_y=("trades_per_y", "mean")).reset_index().sort_values("pct_2x", ascending=False)
    same.to_csv(RES / "sector_same_rule.csv", index=False)
    print("\n=== 2. SAME RULE on all partners, top 12 ===")
    print(same.head(12).to_string(index=False, float_format=fmt))
    print("\nby sector, using each rule's average over its partners, top rule per sector:")
    by = table.assign(rule=table.config.map(rule)).groupby(["sector", "rule"])[["pct_2x", "pct_idle", "median", "r2_2x", "beat_r1", "beat_r2"]].mean().reset_index()
    print(by.sort_values("pct_2x", ascending=False).groupby("sector").head(2).to_string(index=False, float_format=fmt))

    fm = table[table.config.str.contains("__first__")].copy()
    if len(fm):
        fm["entry"] = fm.config.str.extract(r"entry([a-z]+)")
        fm["exit"] = fm.config.str.extract(r"exit([a-z0-9]+)")
        fm["sizing"] = fm.config.map(sizing_of)
        cols = ["pct_2x", "pct_idle", "pct_loss", "median", "worst", "r1_2x", "r2_2x", "beat_r1", "beat_r2", "max_dd", "trades_per_y"]
        for by in ("entry", "exit", "sizing"):
            print(f"\nAMD-first rules, average by {by} (named partners and auto):")
            print(fm.groupby(by)[cols].mean().sort_values("pct_2x", ascending=False).to_string(float_format=fmt))
        print("\nAMD-first rules, average by second stock, top 12:")
        print(fm.groupby("partner")[cols].mean().sort_values("pct_2x", ascending=False).head(12).to_string(float_format=fmt))

    # 3: holdout, everything chosen on periods that finished by the end of 2021
    cut = pd.Timestamp("2022-01-01")
    last_train = cut - pd.Timedelta(days=366)
    train = []
    for c in eq.columns:
        w = window_table(eq, chg, refs, first, c, end=last_train)
        if len(w) >= 36:
            train.append({"config": c, "train_2x": ((w.mult >= TARGET) & w.traded).mean(), "train_median": w.mult.median()})
    train = pd.DataFrame(train)
    order = train.sort_values(["train_2x", "train_median"], ascending=False)
    picks = {"best by share of 2x": order.config.iloc[0], "best by median": train.sort_values("train_median", ascending=False).config.iloc[0]}
    slow_train = order[order.config.str.contains("__switch|every21")]
    picks["best slow rule"] = slow_train.config.iloc[0]
    rows = []
    for label, c in picks.items():
        w = window_table(eq, chg, refs, first, c, start=cut)
        rows.append({"choice": label, "config": c, **stats(w.mult, w.traded, w.r1, w.r2)})
    w = pd.concat([window_table(eq, chg, refs, first, c, start=cut) for c in order.config.head(10)])
    rows.append({"choice": "top 10 pooled", "config": ",".join(sorted({partner(c) for c in order.config.head(10)})), **stats(w.mult, w.traded, w.r1, w.r2)})
    hold = pd.DataFrame(rows)
    hold.to_csv(RES / "sector_holdout.csv", index=False)
    print("\n=== 3. HOLDOUT: chosen through 2021, scored 2022 on ===")
    print(hold.to_string(index=False, float_format=fmt))

    # 4 and 5
    cols_all = list(eq.columns)
    slow = [c for c in cols_all if "__switch" in c or "__first" in c or "every21" in c]
    first_cols = [c for c in cols_all if "__first" in c]
    pools = {"all": cols_all, "on_list": [c for c in cols_all if partner(c) in ON_LIST], "slow": slow,
             "slow_on_list": [c for c in slow if partner(c) in ON_LIST], "switch": [c for c in cols_all if "__switch" in c],
             "first": first_cols, "first_on_list": [c for c in first_cols if partner(c) in ON_LIST],
             "auto": [c for c in first_cols if partner(c) in AUTO],
             **{f"size {v}": [c for c in first_cols if sizing_of(c) == v] for v in ("$100k", "$50k", "3 steps on falls", "4 steps on falls", "half in each")},
             **{s: [c for c in cols_all if SECTOR_OF[partner(c)] == s] for s in sweep.SECTORS},
             **{f"slow_{s}": [c for c in slow if SECTOR_OF[partner(c)] == s] for s in sweep.SECTORS}}
    wf_rows, nest_rows = [], []
    for pool, cols in pools.items():
        if not cols:
            continue
        variants = {}
        for how in ("return", "sharpe"):
            for years in (1, 2, 3, 5):
                wf = walk(eq, chg, refs, first, cols, years, how)
                if wf.empty:
                    continue
                variants[f"{how}_{years}y"] = wf
                wf.to_csv(RES / f"sector_wf_{pool.replace(' ', '_').replace('$', '')}_{how}_{years}y.csv", index=False)
                wf_rows.append({"pool": pool, "rank_by": how, "look_y": years, **stats(wf.mult, wf.traded, wf.r1, wf.r2), "worst_dd": wf.dd.min()})
        for score in ("median", "share_2x", "mean"):
            r = nested(variants, score)
            if r.empty:
                continue
            r.to_csv(RES / f"sector_nested_{pool.replace(' ', '_').replace('$', '')}_{score}.csv", index=False)
            hits = r[(r.mult >= TARGET) & r.traded].sort_values("start")
            nest_rows.append({"pool": pool, "score": score, **stats(r.mult, r.traded, r.r1, r.r2), "first": r.start.min().date(),
                              "episodes": int((hits.start.diff().dt.days.fillna(999) > 92).sum()),
                              "hit_years": ",".join(sorted({str(d.year)[2:] for d in hits.start}))})
    wf_table, nest_table = pd.DataFrame(wf_rows), pd.DataFrame(nest_rows)
    wf_table.to_csv(RES / "sector_walk_forward.csv", index=False)
    nest_table.to_csv(RES / "sector_nested.csv", index=False)
    print("\n=== 4. WALK-FORWARD, return ranking ===")
    print(wf_table[wf_table.rank_by == "return"].drop(columns="rank_by").to_string(index=False, float_format=fmt))
    print("\n=== 5. NESTED: lookback and ranking also chosen in advance ===")
    print(nest_table.to_string(index=False, float_format=fmt))


if __name__ == "__main__":
    main()
