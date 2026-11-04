"""Nested walk-forward: could the METHOD have been chosen in advance?

analyze2.py gives a table of walk-forward variants (pool x rank x lookback). Reading the best row
off that table is itself hindsight. Here, at each monthly start, only windows that had already
finished are used to pick a variant, and that variant's next 12-month result is scored.
"""
from pathlib import Path

import pandas as pd

RES = Path(__file__).parent / "results"
POOLS = {"all_variants": ("singles", "amd_pairs", "rotation_pit", "all_tradable"),
         "pit_only": ("pit_only",),  # the one pool that does not assume AMD, a name chosen today
         "rotation_pit": ("rotation_pit",),
         "pairs_only": ("amd_pairs",)}
MIN_HISTORY = 24  # finished windows needed before a variant can be judged


def load(pools):
    out = {}
    for f in RES.glob("wf_*.csv"):
        run = f.stem[3:]
        if run.startswith(pools):
            out[run] = pd.read_csv(f, parse_dates=["start"]).set_index("start").mult
    return pd.DataFrame(out).sort_index()


def nested(table, score):
    rows = []
    for t in table.index:
        done = table[table.index <= t - pd.DateOffset(months=13)]
        counts = done.notna().sum()
        ok = counts[counts >= MIN_HISTORY].index
        ok = [c for c in ok if pd.notna(table.at[t, c])]
        if not ok:
            continue
        pick = score(done[ok]).idxmax()
        rows.append({"start": t, "variant": pick, "mult": table.at[t, pick]})
    return pd.DataFrame(rows)


SCORES = {"median": lambda d: d.median(), "share_2x": lambda d: (d >= 2).mean(), "share_3x": lambda d: (d >= 3).mean(),
          "mean": lambda d: d.mean()}

if __name__ == "__main__":
    rows = []
    for pool_name, pools in POOLS.items():
        table = load(pools)
        for score_name, score in SCORES.items():
            r = nested(table, score)
            hits = r[r.mult >= 3].sort_values("start")
            rows.append({"pool": pool_name, "score": score_name, "n": len(r), "first": r.start.min().date(),
                         "pct_3x": (r.mult >= 3).mean(), "pct_2x": (r.mult >= 2).mean(), "pct_loss": (r.mult < 1).mean(),
                         "median": r.mult.median(), "worst": r.mult.min(), "best": r.mult.max(),
                         "episodes": int((hits.start.diff().dt.days.fillna(999) > 92).sum()),
                         "top_variant": r.variant.value_counts().index[0]})
            r.to_csv(RES / f"meta_{pool_name}_{score_name}.csv", index=False)
    out = pd.DataFrame(rows)
    out.to_csv(RES / "meta_walk_forward.csv", index=False)
    pd.set_option("display.width", 200, "display.max_colwidth", 30)
    print(out.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
