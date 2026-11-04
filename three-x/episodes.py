"""How many separate market episodes do the walk-forward 3x windows come from?

Monthly restarts of a 12-month hold overlap heavily, so "9% of windows" can be one or two
stretches of luck. Also separates the fair test (rotation over a point-in-time list) from
pools that contain AMD because the user named it today.
"""
from pathlib import Path

import pandas as pd

RES = Path(__file__).parent / "results"
rows = []
for f in sorted(RES.glob("wf_*.csv")):
    wf = pd.read_csv(f, parse_dates=["start"])
    hits = wf[wf.mult >= 3].sort_values("start")
    # A new episode starts when a hit is more than 3 months after the previous one.
    episodes = int((hits.start.diff().dt.days.fillna(999) > 92).sum())
    by_year = wf.assign(y=wf.start.dt.year).groupby("y").mult.median()
    rows.append({"run": f.stem[3:], "n": len(wf), "hits": len(hits), "episodes": episodes,
                 "hit_years": ",".join(sorted({str(d.year) for d in hits.start})),
                 "picks_hit": ",".join(sorted({p.split("__")[0] for p in hits.pick})),
                 "y_pos": f"{(by_year > 1).sum()}/{len(by_year)}",
                 "median_last_3y": round(wf[wf.start >= "2022-11-01"].mult.median(), 2)})
out = pd.DataFrame(rows).sort_values("hits", ascending=False)
out.to_csv(RES / "walk_forward_episodes.csv", index=False)
pd.set_option("display.width", 200, "display.max_colwidth", 44)
print(out.head(24).to_string(index=False))
