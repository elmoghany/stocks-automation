"""LEGACY-7: anatomy of the worst 10% of honest legs (R4, C37F-hf3) and a
causal veto scan.  Reads the table built by lm7_feat.py.

Veto thresholds are fitted on YEAR 1 of the POOLED table (both strategies)
and then read in all four cells (R4/C37F x Y1/Y2); Y2 is the hold-out.
'saved' = -sum(gross of vetoed legs) at a $10k ticket (first order: no
replacement leg).  'excess' = saved minus what dropping the same number of
legs at random saves (n_vetoed x cell mean) -- the part that is selection.
"""
import pickle
import sys
from pathlib import Path

import numpy as np

T = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r"C:/Users/MYPC~1/AppData/Local/Temp/claude/C--cornell-stocks-automation/"
    r"20a29bc8-aa0d-497e-a600-4db3499b8240/scratchpad/lm7_table.pkl")
COST = 30.0      # $ per round trip at $10k = 15 bps/side (gapper central)
rows = pickle.load(open(T, "rb"))

CONT = ["gap7", "gap_open", "pm_dvol", "pm_high_gain", "pm_bars", "pc", "dvol60",
        "prior_range", "prevrange", "ret5", "shares", "gain_now", "coil", "hi_gain",
        "dvol_now", "vwap_dist", "pressure30", "pressure10", "orb_dist", "dens",
        "sigma1", "rvol_now", "vol5", "min_since_cross", "breadth", "gain_rank",
        "half_spread", "amihud", "fill_vs_prev", "min_of_day", "seq",
        "day_pnl_before", "mcap", "entry"]
for r in rows:
    r["mcap"] = r["shares"] * r["pc"] if np.isfinite(r.get("shares", np.nan)) else np.nan
    r["shares"] = r["shares"]


def c(r, k):
    return r.get("cat_" + k, 0.0) > 0


FLAGS = {
    "ANY_NEG_3d(5.02|f4sell|analyst|10q18h)": lambda r: c(r, "n_8k_5.02_3d") or c(r, "n_f4_sell_3d") or c(r, "n_analyst_3d") or c(r, "n_10q_18h"),
    "8k_5.02_3d": lambda r: c(r, "n_8k_5.02_3d"),
    "f4_sell_3d": lambda r: c(r, "n_f4_sell_3d"),
    "insider_sell_30d": lambda r: c(r, "insider_sell_30d"),
    "analyst_3d": lambda r: c(r, "n_analyst_3d"),
    "10q_18h": lambda r: c(r, "n_10q_18h"),
    "offering_news_3d": lambda r: c(r, "n_offering_3d"),
    "offering_news_18h": lambda r: c(r, "n_offering_18h"),
    "424b_3d": lambda r: c(r, "n_424b_3d"),
    "424b_10d": lambda r: c(r, "n_424b_10d"),
    "s3_10d": lambda r: c(r, "n_s3_10d"),
    "s1_10d": lambda r: c(r, "n_s1_10d"),
    "dilution_30d": lambda r: c(r, "dilution_30d"),
    "offer_news_30d": lambda r: c(r, "offer_news_30d"),
    "8k_3.02_10d": lambda r: c(r, "n_8k_3.02_10d"),
    "8k_1.01_3d": lambda r: c(r, "n_8k_1.01_3d"),
    "earn_fresh": lambda r: c(r, "earn_fresh_ev"),
    "earnings_news_18h": lambda r: c(r, "n_earnings_18h"),
    "f144_3d": lambda r: c(r, "n_f144_3d"),
    "sc13g_3d": lambda r: c(r, "n_sc13g_3d"),
    "legal_3d": lambda r: c(r, "n_legal_3d"),
    "delisting_10d": lambda r: c(r, "n_delisting_10d"),
    "halt_18h": lambda r: c(r, "n_halt_18h"),
    "any_catalyst_18h": lambda r: c(r, "any_catalyst_18h"),
    "no_news_18h": lambda r: r.get("cat_n_news_all_18h", 0) == 0,
    "quiet_10d": lambda r: r.get("cat_n_news_all_10d", 0) == 0 and r.get("cat_n_fil_all_10d", 0) == 0,
    "news_lt2h": lambda r: r.get("cat_hrs_since_news", 720) < 2,
    "prev_leg_lost": lambda r: r.get("prev_loss", 0) > 0,
    "same_sym_again": lambda r: r.get("same_sym_before", 0) > 0,
}

CELLS = [(s, y) for s in ("R4", "C37F") for y in (1, 2)]


def cell(s, y):
    return [r for r in rows if r["strat"] == s and r["y"] == y]


def stats_mask(rs, m):
    g = np.array([r["g10k"] for r in rs])
    m = np.asarray(m, bool)
    lo, hi = np.percentile(g, 10), np.percentile(g, 90)
    n = int(m.sum())
    saved = -g[m].sum()
    excess = saved + n * g.mean()
    tv = np.nan
    if n > 2 and (~m).sum() > 2:
        a, b = g[m], g[~m]
        tv = (a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return dict(n=n, frac=n / len(g), saved=saved, excess=excess,
                mean_v=g[m].mean() if n else np.nan, t=tv,
                los=int((m & (g <= lo)).sum()), wins=int((m & (g >= hi)).sum()),
                nlos=int((g <= lo).sum()))


def fmt(st):
    return (f"{st['n']:4d} ({st['frac']*100:4.1f}%) mean {st['mean_v']:+7.1f} t {st['t']:+5.2f} "
            f"saved {st['saved']:+8.0f} excess {st['excess']:+7.0f} L{st['los']}/{st['nlos']} W{st['wins']}")


def anatomy():
    print("=== ANATOMY: medians, worst10% / middle / best10% (gross $ per $10k) ===")
    for s in ("R4", "C37F"):
        rs = [r for r in rows if r["strat"] == s]
        g = np.array([r["g10k"] for r in rs])
        lo, hi = np.percentile(g, 10), np.percentile(g, 90)
        W = [r for r in rs if r["g10k"] <= lo]
        B = [r for r in rs if r["g10k"] >= hi]
        M = [r for r in rs if lo < r["g10k"] < hi]
        print(f"\n{s}: n={len(rs)} mean gross {g.mean():+.1f} net@15bps {g.mean()-COST:+.1f}; "
              f"worst10% cut {lo:+.0f} (sum {sum(r['g10k'] for r in W):+.0f}, n {len(W)}); "
              f"best10% cut {hi:+.0f} (sum {sum(r['g10k'] for r in B):+.0f})")
        rsn = {}
        for r in W:
            rsn[r["reason"]] = rsn.get(r["reason"], 0) + 1
        print("  worst exit reasons:", rsn)
        for k in CONT:
            def med(X):
                v = np.array([x.get(k, np.nan) for x in X], float)
                v = v[np.isfinite(v)]
                return np.median(v) if v.size else np.nan
            print(f"  {k:16s} {med(W):12.4g} {med(M):12.4g} {med(B):12.4g}")
        for nm, f in FLAGS.items():
            fw = np.mean([f(r) for r in W]); fm = np.mean([f(r) for r in M]); fb = np.mean([f(r) for r in B])
            print(f"  FLAG {nm:38s} {fw:5.2f} {fm:5.2f} {fb:5.2f}")


def flag_table():
    print("\n=== CATALYST / SEQUENCE FLAGS as vetoes (no fitting) ===")
    for nm, f in FLAGS.items():
        line = [f"{nm:38s}"]
        for s, y in CELLS:
            rs = cell(s, y)
            line.append(f"{s}Y{y}: " + fmt(stats_mask(rs, [f(r) for r in rs])))
        print("\n".join(line))


def scan():
    print("\n=== CONTINUOUS VETO SCAN: thresholds from pooled Y1 ===")
    y1 = [r for r in rows if r["y"] == 1]
    res = []
    for k in CONT:
        v1 = np.array([r.get(k, np.nan) for r in y1], float)
        v1 = v1[np.isfinite(v1)]
        if v1.size < 50:
            continue
        for q in (0.05, 0.1, 0.2, 0.8, 0.9, 0.95):
            th = float(np.quantile(v1, q))
            op = ">" if q > 0.5 else "<"
            out = {}
            for s, y in CELLS:
                rs = cell(s, y)
                x = np.array([r.get(k, np.nan) for r in rs], float)
                m = (x > th) if op == ">" else (x < th)
                out[(s, y)] = stats_mask(rs, m)
            y1ex = out[("R4", 1)]["excess"] + out[("C37F", 1)]["excess"]
            y2ex = out[("R4", 2)]["excess"] + out[("C37F", 2)]["excess"]
            allpos = all(out[c_]["excess"] > 0 for c_ in CELLS)
            res.append((y1ex, y2ex, allpos, k, op, th, out))
    res.sort(key=lambda z: -z[0])
    print("top 25 by pooled-Y1 excess (Y2 = hold-out):")
    for y1ex, y2ex, allpos, k, op, th, out in res[:25]:
        print(f"\n{k} {op} {th:.4g}  Y1ex {y1ex:+.0f}  Y2ex {y2ex:+.0f}  all4>0 {allpos}")
        for c_ in CELLS:
            print(f"   {c_[0]}Y{c_[1]}: {fmt(out[c_])}")
    print("\nall-four-cells-positive candidates:")
    for y1ex, y2ex, allpos, k, op, th, out in res:
        if allpos:
            print(f"  {k} {op} {th:.4g}  Y1ex {y1ex:+.0f} Y2ex {y2ex:+.0f} | " +
                  " | ".join(f"{c_[0]}Y{c_[1]} n{out[c_]['n']} mean{out[c_]['mean_v']:+.0f} sv{out[c_]['saved']:+.0f}" for c_ in CELLS))


if __name__ == "__main__":
    anatomy()
    flag_table()
    scan()
