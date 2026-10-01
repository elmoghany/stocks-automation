"""LEGACY-6: ANATOMY OF WINNERS (2026-10-01).

Joins every honest leg of CHAMPION-REPLAY R4 (pa_out/cp_r4_legs.json, incl.
its 30 random-seed control legs in the same frame) and of C37F-hf3
(data/massive/rotation_trades_C37F_hf3.json) to ENTRY-TIME features only:
  * the causal cp_feat grid (value at grid minute m uses bars <= m and
    prior sessions only), taken at the last grid minute strictly before
    the entry minute (the engine decides at t, fills at the next print);
  * the catalyst corpus (cat_events.features_for: events with ts <= dec).
`gain_full` / `rvol_pool` (hindsight labels) are NEVER used.
Read-only on every input; writes only plan/lm6_out/.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ROOT = Path(r"C:\cornell\stocks-automation\day-trading")
sys.path.insert(0, str(ROOT / "plan"))
import cat_events as CE                                     # noqa: E402

FEAT = ROOT / "data/massive/cp_feat"
OUT = ROOT / "plan/lm6_out"
OUT.mkdir(exist_ok=True)
ET = ZoneInfo("America/New_York")
M_OPEN = 330
Y2 = "2025-08-01"

DYN = ["last", "gain_now", "coil", "hi_gain", "dvol_now", "vwap_dist",
       "pressure30", "pressure10", "orb_dist", "dens", "sigma1", "rvol_now"]
STA = ["pc", "pm_dvol", "pm_high_gain", "gap_open", "gap7", "pm_bars",
       "dvol60", "prior_range", "nhist", "ret5", "shares"]
CAT = ["any_catalyst_18h", "n_news_all_18h", "n_pr_18h", "n_offering_18h",
       "n_fda_18h", "n_contract_18h", "n_earnings_18h", "n_8k_8.01_3d",
       "n_424b_10d", "n_s3_10d", "dilution_30d", "hrs_since_news",
       "hrs_since_fil"]


def legs():
    d = json.loads((ROOT / "plan/pa_out/cp_r4_legs.json").read_text())
    rows = []
    for x in d["legs"]["R4"]:
        rows.append(dict(src="R4", date=x["date"], sym=x["sym"],
                         em=x["entry_min"], xm=x["exit_min"],
                         entry=x["entry"], exit=x["exit"], usd=x["gross"],
                         reason=x["reason"], tk=None))
    seen = set()
    for k, L in d["legs"].items():
        if not k.startswith("RND"):
            continue
        for x in L:
            key = (x["date"], x["sym"], x["entry_min"], x["exit_min"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(dict(src="RND", date=x["date"], sym=x["sym"],
                             em=x["entry_min"], xm=x["exit_min"],
                             entry=x["entry"], exit=x["exit"], usd=x["gross"],
                             reason=x["reason"], tk=None))
    h = json.loads((ROOT / "data/massive/rotation_trades_C37F_hf3.json").read_text())
    for x in h:
        et = datetime.fromisoformat(x["entry_time"])
        xt = datetime.fromisoformat(x["exit_time"])
        rows.append(dict(src="HF3", date=x["date"], sym=x["symbol"],
                         em=et.hour * 60 + et.minute - 240,
                         xm=xt.hour * 60 + xt.minute - 240,
                         entry=x["entry"], exit=x["exit"], usd=x["pnl"],
                         reason=x["reason"].split()[0], tk=x["ticket"]))
    return rows


def main():
    rows = legs()
    by_date = {}
    for r in rows:
        by_date.setdefault(r["date"], []).append(r)
    miss = 0
    for date, rs in sorted(by_date.items()):
        f = FEAT / f"{date}.npz"
        if not f.exists():
            for r in rs:
                r["ok"] = False
            miss += len(rs)
            continue
        z = np.load(f)
        F = {k: z[k] for k in z.files}
        syms = {s: i for i, s in enumerate(F["syms"].tolist())}
        grid = F["grid"]
        el = F["elig_last"]
        first = np.where(el.any(1), el.argmax(1), -1)
        n_elig = el.sum(0)
        n_gap10 = int(np.nansum(F["gap_open"] >= 0.10))
        for r in rs:
            i = syms.get(r["sym"])
            gi = int(np.searchsorted(grid, r["em"] - 1, "right") - 1)
            if i is None or gi < 0:
                r["ok"] = False
                miss += 1
                continue
            r["ok"] = True
            r["g"] = int(grid[gi])
            for k in DYN:
                r[k] = float(F[k][i, gi])
            for k in STA:
                r[k] = float(F[k][i])
            r["since_cross"] = (float(grid[gi] - grid[first[i]])
                                if 0 <= first[i] <= gi else np.nan)
            r["n_elig"] = int(n_elig[gi])
            r["n_gap10"] = n_gap10
            g_el = F["gain_now"][el[:, gi], gi]
            r["lead_rank"] = int(np.sum(g_el > F["gain_now"][i, gi]))
            r["mkt_gain_med"] = float(np.nanmedian(g_el)) if g_el.size else np.nan
    # catalyst features, grouped by symbol
    names = CE.feature_names()
    idx = {c: names.index(c) for c in CAT}
    bysym = {}
    for r in rows:
        if r.get("ok"):
            bysym.setdefault(r["sym"], []).append(r)
    for s, rs in bysym.items():
        ts = np.array([datetime.fromisoformat(r["date"]).replace(
            hour=4, tzinfo=ET).timestamp() + 60 * r["g"] for r in rs])
        X = CE.features_for(s, ts)
        for j, r in enumerate(rs):
            for c in CAT:
                r[c] = float(X[j, idx[c]])
            r["cat_cov"] = s in CE.corpus()
    out = [r for r in rows if r.get("ok")]
    for r in out:
        r["ret"] = r["exit"] / r["entry"] - 1.0
    (OUT / "legs_feat.json").write_text(json.dumps(out, default=float))
    print("rows", len(rows), "joined", len(out), "missing", miss)
    from collections import Counter
    print(Counter(r["src"] for r in out), Counter(r["src"] for r in rows))


if __name__ == "__main__":
    main()
