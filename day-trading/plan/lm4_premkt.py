"""LEGACY-4 (premarket). Analysis only, no fetching, no edits elsewhere.

Part A  -- the HONEST premarket scanner list (12 whole-market census days,
           data/massive/cp/premkt_census.json + bars in m1/m1c). For every
           premarket +10% crosser: causal features AT THE CROSS MINUTE and the
           outcome of a live premarket entry under several exits. Is any
           causal subset positive?
Part B  -- pre-open FILTER for regular-session entries: join every honest
           RTH leg (plan/pa_out/cp_r4_legs.json: R4 + 30 random-entry seeds,
           cp_sim post-retraction fills, RS_CROSS universe) to that
           name-day's premarket features (data/massive/cp/rows.npz static
           columns, all fixed at 09:29) and bucket leg returns.
Part C  -- same buckets on the panel's exit-agnostic forward returns
           (rows at 09:35 / 10:00, r60 and r1500).

    python plan/lm4_premkt.py > plan/lm4_out.txt
"""
import json
import pickle
import sys
from collections import defaultdict
from datetime import date as ddate, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cp_premkt as PM                                      # noqa: E402
import cp_prior as P                                        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ET = ZoneInfo("America/New_York")
M_OPEN, M_1500 = PM.M_OPEN, PM.M_1500
TICKET = 10_000.0


def ts_of(date, m):
    d = ddate.fromisoformat(date)
    t = datetime(d.year, d.month, d.day, 4, 0, tzinfo=ET) + timedelta(minutes=int(m))
    return t.timestamp()


def prev_close_ts(date):
    d = ddate.fromisoformat(date) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return datetime(d.year, d.month, d.day, 16, 0, tzinfo=ET).timestamp()


def first_print_at(pr, m):
    for k in range(m, PM.NMIN):
        if pr[k]:
            return k
    return None


def tstat(day_means):
    a = np.asarray(day_means, float)
    if len(a) < 3 or a.std(ddof=1) == 0:
        return np.nan
    return a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))


# ---------------------------------------------------------------- Part A
def part_a():
    rows = json.load(open(ROOT / "data/massive/cp/premkt_census.json"))
    rows = [r for r in rows if r["kind"] != "RTH-CROSSER" and "entry" in r]
    ev = pickle.load(open(ROOT / "data/massive/cat/events.pkl", "rb"))
    ctx_cache = {}
    out = []
    for r in rows:
        s, d = r["sym"], r["date"]
        b = PM.read_bars(s, d)
        if b is None:
            continue
        o, h, l, c, v = b
        pr = np.isfinite(c)
        m0 = r["pm_cross_min"]
        nxt = first_print_at(pr, m0 + 1)
        if nxt is None:
            continue
        e = o[nxt]
        if d not in ctx_cache:
            ctx_cache[d] = P.load(d) or {}
        cx = ctx_cache[d].get(s) or {}
        dv = np.nan_to_num(c[:m0 + 1]) * v[:m0 + 1]
        dvol_x = dv.sum()
        vw = dv.sum() / max(v[:m0 + 1].sum(), 1)
        sh = P.shares(s, d)
        # catalyst: any timestamped event between prior close and the cross
        t1, t0 = ts_of(d, m0), prev_close_ts(d)
        cov = s in ev
        cat = np.nan
        if cov:
            cat = float(any(((a > t0) & (a <= t1)).any()
                            for a in ev[s].values() if len(a)))
        f = dict(
            kind=r["kind"], date=d, sym=s,
            cross_hhmm=(m0 + 240) // 60 * 100 + (m0 + 240) % 60,
            cross_min=m0,
            dvol_x=dvol_x,
            rel_x=dvol_x / cx["dvol60"] if cx.get("dvol60") else np.nan,
            px=e, mcap=(sh * r["pc"]) if sh else np.nan,
            vwap_prem=r["pm_cross_px"] / vw - 1 if vw > 0 else np.nan,
            nbars_x=int(pr[:m0 + 1].sum()), cat=cat, cov=cov,
        )
        # exits ------------------------------------------------------
        def ex_at(mm):
            k = first_print_at(pr, max(mm, nxt + 1))
            return (o[k] / e - 1) if k is not None and k <= M_1500 else np.nan
        f["x_open"] = ex_at(M_OPEN)
        f["x_0945"] = ex_at(M_OPEN + 15)
        f["x_1000"] = ex_at(M_OPEN + 30)
        seg = [k for k in range(nxt + 1, M_1500 + 1) if pr[k]]
        f["x_1500"] = (c[seg[-1]] / e - 1) if seg else np.nan
        # -8% stop, flatten 15:00 (gap-through fills at min(stop, open))
        stp, res = e * 0.92, f["x_1500"]
        for k in seg:
            if l[k] <= stp:
                res = min(stp, o[k]) / e - 1
                break
        f["x_stop8"] = res
        # held to open but bail if price ever trades under premarket VWAP
        out.append(f)
    return out


def bucket_table(rows, key, edges, labels, rets, cost_bps):
    print(f"\n#### by {key}\n")
    hdr = "| bucket | n | days | " + " | ".join(
        f"{x} gross bps" for x in rets) + " | best net $/tkt @" + \
        f"{cost_bps}bps/side | days+ (best) | t(day) |"
    print(hdr)
    print("|" + "---|" * (hdr.count("|") - 1))
    for lo, hi, lab in zip(edges[:-1], edges[1:], labels):
        sub = [r for r in rows if np.isfinite(r.get(key, np.nan))
               and lo <= r[key] < hi]
        if not sub:
            continue
        g = {x: np.nanmean([r[x] for r in sub]) * 1e4 for x in rets}
        bx = max(rets, key=lambda x: g[x])
        dm = defaultdict(list)
        for r in sub:
            if np.isfinite(r[bx]):
                dm[r["date"]].append(r[bx])
        dmeans = [np.mean(v) for v in dm.values()]
        net = (g[bx] - 2 * cost_bps) / 1e4 * TICKET
        print(f"| {lab} | {len(sub)} | {len(dm)} | " + " | ".join(
            f"{g[x]:+.0f}" for x in rets) +
            f" | {net:+.0f} ({bx}) | {sum(1 for x in dmeans if x > 0)}"
            f"/{len(dmeans)} | {tstat(dmeans):+.2f} |")


def report_a(A):
    rets = ["x_open", "x_0945", "x_1000", "x_stop8", "x_1500"]
    print("# PART A -- live premarket entries on the honest scanner list "
          "(12 census days)\n")
    for kind in ("ALL", "PM-AND-RTH", "PM-ONLY"):
        sub = A if kind == "ALL" else [r for r in A if r["kind"] == kind]
        print(f"- {kind}: n={len(sub)} " + ", ".join(
            f"{x} {np.nanmean([r[x] for r in sub])*1e4:+.0f}bps "
            f"(med {np.nanmedian([r[x] for r in sub])*1e4:+.0f})"
            for x in rets))
    inf = np.inf
    C = 25   # premarket per-side cost (spreads wider than RTH 12-18)
    bucket_table(A, "cross_min", [0, 120, 180, 240, 300, 330],
                 ["04:00-05:59", "06:00-06:59", "07:00-07:59", "08:00-08:59",
                  "09:00-09:29"], rets, C)
    bucket_table(A, "rel_x", [0, .05, .2, .5, 1, 3, inf],
                 ["<5%", "5-20%", "20-50%", "50-100%", "1-3x", ">3x"], rets, C)
    bucket_table(A, "dvol_x", [0, 1e5, 5e5, 2e6, 1e7, inf],
                 ["<$100k", "$100k-500k", "$0.5-2M", "$2-10M", ">$10M"],
                 rets, C)
    bucket_table(A, "mcap", [0, 5e7, 3e8, 2e9, 1e10, inf],
                 ["<50M", "50-300M", "300M-2B", "2-10B", ">10B"], rets, C)
    bucket_table(A, "px", [0, 5, 20, 100, inf],
                 ["<$5", "$5-20", "$20-100", ">$100"], rets, C)
    bucket_table(A, "vwap_prem", [-inf, 0, .03, .08, inf],
                 ["below PM VWAP", "0-3% above", "3-8% above", ">8% above"],
                 rets, C)
    bucket_table(A, "cat", [-.5, .5, 1.5], ["no event", "event since close"],
                 rets, C)
    bucket_table(A, "nbars_x", [0, 10, 40, 120, inf],
                 ["<10 bars", "10-40", "40-120", ">120"], rets, C)
    # best-looking conjunctions (all causal at the cross)
    print("\n#### conjunctions\n")
    combos = {
        "rel>=1x & cross>=08:00": lambda r: r["rel_x"] >= 1 and r["cross_min"] >= 240,
        "mcap>=2B": lambda r: r["mcap"] >= 2e9,
        "mcap>=2B & cat": lambda r: r["mcap"] >= 2e9 and r["cat"] == 1,
        "dvol_x>=$10M": lambda r: r["dvol_x"] >= 1e7,
        "dvol_x>=$2M & px>=$5": lambda r: r["dvol_x"] >= 2e6 and r["px"] >= 5,
        "cat & rel>=1x": lambda r: r["cat"] == 1 and r["rel_x"] >= 1,
        "cross>=09:00 & rel>=1x": lambda r: r["cross_min"] >= 300 and r["rel_x"] >= 1,
    }
    for name, fn in combos.items():
        sub = [r for r in A if all(np.isfinite([r["rel_x"], r["mcap"] if "mcap" in name else 0]))
               and fn(r)]
        if not sub:
            continue
        print(f"- {name}: n={len(sub)} days={len({r['date'] for r in sub})} "
              f"PM-ONLY share {np.mean([r['kind']=='PM-ONLY' for r in sub]):.0%}; "
              + ", ".join(f"{x} {np.nanmean([r[x] for r in sub])*1e4:+.0f}"
                          for x in rets))


# ---------------------------------------------------------------- Part B
def static_table():
    z = np.load(ROOT / "data/massive/cp/rows.npz")
    cols = json.load(open(ROOT / "data/massive/cp/cols.json"))
    ci = {c: i for i, c in enumerate(cols)}
    X, sym, di, dates = z["X"], z["sym"], z["date"], z["dates"]
    st = {}
    keep = ["pc", "pm_dvol", "pm_high_gain", "gap_open", "gap7", "pm_bars",
            "dvol60", "shares", "prior_range", "ret5"]
    for i in range(len(sym)):
        k = (str(dates[di[i]]), str(sym[i]))
        if k in st:
            continue
        st[k] = {c: float(X[i, ci[c]]) for c in keep}
    return st, (X, sym, di, dates, z["tt"], ci)


def derive(f):
    g = dict(f)
    g["rel_pm"] = f["pm_dvol"] / f["dvol60"] if f["dvol60"] > 0 else np.nan
    g["fade_pmhi"] = (1 + f["gap_open"]) / (1 + f["pm_high_gain"]) - 1
    g["drift7"] = (1 + f["gap_open"]) / (1 + f["gap7"]) - 1
    g["pmx"] = float(f["pm_high_gain"] >= 0.10)
    g["mcap"] = f["shares"] * f["pc"]
    return g


BUCKETS = [
    ("rel_pm", [0, .02, .1, .3, 1, np.inf],
     ["<2%", "2-10%", "10-30%", "30-100%", ">=1x"]),
    ("pm_dvol", [-1, 1e5, 1e6, 5e6, np.inf],
     ["<$100k", "$0.1-1M", "$1-5M", ">$5M"]),
    ("gap_open", [-np.inf, 0, .05, .10, .20, .40, np.inf],
     ["<0", "0-5%", "5-10%", "10-20%", "20-40%", ">40%"]),
    ("fade_pmhi", [-np.inf, -.20, -.10, -.03, np.inf],
     ["<-20% off PM high", "-20..-10%", "-10..-3%", "within 3% of PM high"]),
    ("drift7", [-np.inf, -.05, .05, np.inf],
     ["faded >5% 07:00->09:29", "flat +-5%", "built >5%"]),
    ("pmx", [-.5, .5, 1.5], ["no PM +10% print", "PM +10% crosser"]),
    ("mcap", [0, 5e7, 3e8, 2e9, np.inf], ["<50M", "50-300M", "300M-2B", ">2B"]),
    ("pc", [0, 5, 20, np.inf], ["<$5", "$5-20", ">$20"]),
    ("pm_bars", [-1, 30, 150, np.inf], ["<30", "30-150", ">150"]),
]


def part_b(st, cost_bps=15):
    L = json.load(open(ROOT / "plan/pa_out/cp_r4_legs.json"))
    dates = L["dates"]
    half = dates[len(dates) // 2]
    print("\n\n# PART B -- pre-open features vs honest RTH legs "
          f"(cp_sim, RS_CROSS universe, 444 sessions; net @{cost_bps} "
          "bps/side, $10k ticket)\n")
    for grp, keys in (("R4 (coil rank)", ["R4"]),
                      ("RND x30 (random eligible pick)",
                       [k for k in L["legs"] if k.startswith("RND")])):
        legs = []
        miss = 0
        for k in keys:
            for g in L["legs"][k]:
                f = st.get((g["date"], g["sym"]))
                if f is None:
                    miss += 1
                    continue
                q = derive(f)
                q["ret"] = g["gross"] / (g["entry"] * g["shares"])
                q["date"] = g["date"]
                q["early"] = g["entry_min"] < M_OPEN + 30
                legs.append(q)
        base = np.mean([q["ret"] for q in legs]) * 1e4
        print(f"\n## {grp}: {len(legs)} legs (unmatched {miss}); "
              f"mean gross {base:+.0f} bps = net "
              f"{(base-2*cost_bps):+.0f} bps = ${(base-2*cost_bps):+.1f}/tkt*"
              f"(10k/1e4)\n")
        for key, edges, labs in BUCKETS:
            print(f"\n#### {key}\n")
            print("| bucket | legs | gross bps | net $/tkt | 1st half net | "
                  "2nd half net | days+ | t(day) | entry<10:00 net |")
            print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
            for lo, hi, lab in zip(edges[:-1], edges[1:], labs):
                sub = [q for q in legs if np.isfinite(q[key])
                       and lo <= q[key] < hi]
                if len(sub) < 20:
                    continue
                gr = np.mean([q["ret"] for q in sub]) * 1e4
                nt = lambda s: ((np.mean([q["ret"] for q in s]) * 1e4
                                 - 2 * cost_bps) if s else np.nan)
                h1 = nt([q for q in sub if q["date"] < half])
                h2 = nt([q for q in sub if q["date"] >= half])
                ea = nt([q for q in sub if q["early"]])
                dm = defaultdict(list)
                for q in sub:
                    dm[q["date"]].append(q["ret"] - 2 * cost_bps / 1e4)
                dmean = [np.mean(v) for v in dm.values()]
                print(f"| {lab} | {len(sub)} | {gr:+.0f} | {nt(sub):+.0f} | "
                      f"{h1:+.0f} | {h2:+.0f} | "
                      f"{sum(x > 0 for x in dmean)}/{len(dmean)} | "
                      f"{tstat(dmean):+.2f} | {ea:+.0f} |")
        yield grp, legs


# ---------------------------------------------------------------- Part C
def part_c(st, pan):
    X, sym, di, dates, tt, ci = pan
    print("\n\n# PART C -- exit-agnostic forward return of every eligible "
          "name (panel), bps gross\n")
    for t in (935, 1000):
        idx = np.where(tt == t)[0]
        recs = []
        for i in idx:
            f = st.get((str(dates[di[i]]), str(sym[i])))
            q = derive(f)
            q["r60"] = float(X[i, ci["r60"]])
            q["r1500"] = float(X[i, ci["r1500"]])
            q["d"] = int(di[i])
            recs.append(q)
        print(f"\n## decision {t}: {len(recs)} rows; all r60 "
              f"{np.nanmean([q['r60'] for q in recs])*1e4:+.0f} r1500 "
              f"{np.nanmean([q['r1500'] for q in recs])*1e4:+.0f}\n")
        print("| feature | bucket | n | r60 bps | r1500 bps | r1500 median |")
        print("|---|---|---:|---:|---:|---:|")
        for key, edges, labs in BUCKETS:
            for lo, hi, lab in zip(edges[:-1], edges[1:], labs):
                sub = [q for q in recs if np.isfinite(q[key])
                       and lo <= q[key] < hi]
                if len(sub) < 50:
                    continue
                a = np.array([q["r60"] for q in sub])
                b = np.array([q["r1500"] for q in sub])
                print(f"| {key} | {lab} | {len(sub)} | "
                      f"{np.nanmean(a)*1e4:+.0f} | {np.nanmean(b)*1e4:+.0f} | "
                      f"{np.nanmedian(b)*1e4:+.0f} |")


if __name__ == "__main__":
    A = part_a()
    pass
    report_a(A)
    st, pan = static_table()
    for _ in part_b(st):
        pass
    part_c(st, pan)
