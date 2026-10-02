"""LEADS-TEST lead 3: survivorship correction from lt_pmgap_fetch output.
Missing large-cap premarket crossers (never reached +10% in the session, so
absent from the panel) vs the panel's guarded events on the SAME dates.
    python plan/lt_pmgap_ana.py"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lt_lead3_ctl as K                                    # noqa: E402
import lt_lib as LL                                         # noqa: E402
import lt_lead3 as X3                                       # noqa: E402

ROOT = LL.ROOT
D = ROOT / "data/research_oct/pmgap"


def event(bars, pc):
    if not bars:
        return None
    c = np.full(720, np.nan)
    o = np.full(720, np.nan)
    h = np.full(720, np.nan)
    lo = np.full(720, np.nan)
    for m, oo, hh, ll, cc, vv in bars:
        if 0 <= m < 720:
            o[m], h[m], lo[m], c[m] = oo, hh, ll, cc
    pre = c[:330]
    hit = np.where(~np.isnan(pre) & (pre >= 1.10 * pc) & (pre >= 2.0))[0]
    if not len(hit) or hit[0] < 180:
        return None
    t = int(hit[0])
    em = next((m for m in range(t + 1, 331) if not np.isnan(c[m])), None)
    xm = next((m for m in range(360, 720) if not np.isnan(c[m])), None)
    if em is None or xm is None:
        return None
    import lt_lead3 as X
    return dict(t=t, ret=o[xm] / o[em] - 1, h_e=X.half(o, h, lo, c, em - 1),
                h_x=X.half(o, h, lo, c, xm - 1))


def main():
    files = sorted(D.glob("*.json"))
    dates = [f.stem for f in files]
    miss, cand, nobars = [], 0, 0
    for f in files:
        for s, v in json.loads(f.read_text()).items():
            cand += 1
            if v["bars"] is None:
                nobars += 1
                continue
            e = event(v["bars"], v["pc"])
            if e:
                e.update(date=f.stem, sym=s)
                miss.append(e)
    pan = [e for e in K.EV if K.sel(e) and e["date"] in set(dates)]
    print(f"dates {len(dates)}; candidates fetched {cand} (no bars {nobars}); missing post-07:00 large-cap "
          f"crossers {len(miss)}; panel guarded events on same dates {len(pan)}")
    for sp in ("Y1", "Y2", "OOS", "ALL"):
        a = [1e4 * e["x1000"] for e in pan if sp == "ALL" or LL.split_of(e["date"]) == sp]
        b = [1e4 * e["ret"] for e in miss if sp == "ALL" or LL.split_of(e["date"]) == sp]
        if not a:
            continue
        allv = a + b
        print(f"{sp}: panel n {len(a)} gross {np.mean(a):+.1f} | missing n {len(b)} gross "
              f"{np.mean(b) if b else float('nan'):+.1f} | share missing {len(b)/len(allv):.1%} | "
              f"corrected gross {np.mean(allv):+.1f} (bias {np.mean(a)-np.mean(allv):+.1f})")
    # HONEST pooled sample: census dates (whole market) + targeted dates
    # (panel events + the fetched missing names), central cost per leg
    def net(r, he, hx):
        return 1e4 * r - ((0.5 * he + 4.4) + (0.5 * hx + 4.4) * (1 + r))
    cen = [e for e in K.EV if e["census"] and K.sel(e)]
    pool = [(e["date"], net(e["x1000"], e["h_e"], e.get("h_x", e["h_e"])), 1e4 * e["x1000"]) for e in cen + pan]
    pool += [(e["date"], net(e["ret"], e["h_e"], e["h_x"]), 1e4 * e["ret"]) for e in miss]
    nd = len(set(dates) | set(X3.CENSUS))
    for sp in ("Y1", "Y2", "OOS", "ALL"):
        v = [x for x in pool if sp == "ALL" or LL.split_of(x[0]) == sp]
        if not v:
            continue
        g = np.array([x[2] for x in v]); c = np.array([x[1] for x in v])
        rng = np.random.default_rng(5)
        bd = {}
        for x in v:
            bd.setdefault(x[0], []).append(x[1])
        ks = list(bd)
        bs = [np.mean(np.concatenate([bd[k] for k in rng.choice(ks, len(ks))])) for _ in range(3000)]
        ndd = sum(1 for d in set(dates) | set(X3.CENSUS) if sp == "ALL" or LL.split_of(d) == sp)
        print(f"HONEST pooled {sp}: dates {ndd} n {len(v)} gross {g.mean():+.1f} central {c.mean():+.1f} "
              f"flat12 {np.mean(g - 24):+.1f} day-boot 90% CI central [{np.percentile(bs,5):+.0f}, {np.percentile(bs,95):+.0f}] "
              f"tr/mo {len(v)/max(ndd,1)*21:.1f} $/mo central {c.mean()*len(v)/max(ndd,1)*21:+,.0f} "
              f"ex-top5 $/tr {np.sort(c)[:-5].mean() if len(c) > 5 else float('nan'):+.1f}")
    print("missing events:", [(e["date"], e["sym"], round(1e4 * e["ret"])) for e in miss][:40])


if __name__ == "__main__":
    main()
