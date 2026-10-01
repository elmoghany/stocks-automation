"""LEGACY-9 step 2: where does the gross edge live, cheap or expensive names?
Reads plan/lm9_out/feat.json + the leg dumps. Pure arithmetic."""
import json, sys
from pathlib import Path
import numpy as np

P = Path(r"C:\cornell\stocks-automation\day-trading\plan")
ROOT = P.parent
T1030 = 10 * 60 + 30 - 240
Y2 = "2025-08-01"
F = json.load(open(P / "lm9_out/feat.json"))
R4 = json.load(open(P / "pa_out/cp_r4_legs.json"))
NDAYS = R4["ndays"]
MO = NDAYS / 21.0


def imp(m):
    return 4.4 if (m is not None and m < T1030) else 3.1


def frame(book):
    if book in R4["legs"]:
        L = R4["legs"][book]
        rows = [(v["date"], v["sym"], v["entry"], v["exit"], v["shares"], v["entry_min"], v["exit_min"]) for v in L]
    else:
        L = json.load(open(ROOT / f"data/massive/rotation_trades_{book}_hf3.json"))
        rows = []
        for v in L:
            et = v["entry_time"][11:16]; xt = v["exit_time"][11:16]
            em = int(et[:2]) * 60 + int(et[3:]) - 240
            xm = int(xt[:2]) * 60 + int(xt[3:]) - 240
            # undo legacy slip like COST-RESCORE: C37F 0, HOLD1 10 bps
            s = 0.0 if book == "C37F" else 10e-4
            rows.append((v["date"], v["symbol"], v["entry"] / (1 + s), v["exit"] / (1 - s), v["shares"], em, xm))
    out = []
    for (d, s, pe, px, sh, em, xm), f in zip(rows, F[book]):
        N = pe * sh
        if N <= 0 or f is None:
            continue
        r = px / pe - 1.0
        N10 = min(1e4, N)
        ce_u = f["h_e"] + imp(em); cx_u = (f["h_x"] if np.isfinite(f["h_x"]) else 50.0) + (imp(xm) if xm is not None and xm < 720 else 50.0)
        ce_c = 0.5 * f["h_e"] + imp(em); cx_c = 0.5 * (f["h_x"] if np.isfinite(f["h_x"]) else 50.0) + (imp(xm) if xm is not None and xm < 720 else 50.0)
        g = N10 * r
        out.append(dict(date=d, sym=s, g=g, r=r, N=N, N10=N10, em=em,
                        cost_u=N10 * (ce_u + cx_u * (1 + r)) / 1e4,
                        cost_c=N10 * (ce_c + cx_c * (1 + r)) / 1e4,
                        cost_15=N10 * 15 * (2 + r) / 1e4,
                        h_e=f["h_e"], hmin=f["hmin_e"], dv30=f["dv30"], dvday=f["dvday"],
                        px=pe, ce_u=ce_u, ce_c=ce_c))
    return out


def summ(rows, tag, ndays=NDAYS, seeds=1):
    if not rows:
        return f"| {tag} | 0 |"
    g = np.array([x["g"] for x in rows]); cc = np.array([x["cost_c"] for x in rows]); cu = np.array([x["cost_u"] for x in rows])
    c15 = np.array([x["cost_15"] for x in rows])
    nc = g - cc
    y1 = [x for x in rows if x["date"] < Y2]; y2 = [x for x in rows if x["date"] >= Y2]
    def mo(rs, nd):
        return sum(x["g"] - x["cost_c"] for x in rs) / (nd / 21.0) / seeds if rs else 0.0
    nd1 = sum(1 for d in R4["dates"] if d < Y2); nd2 = NDAYS - nd1
    byday = {}
    for x in rows:
        byday[x["date"]] = byday.get(x["date"], 0.0) + x["g"] - x["cost_c"]
    exbest = nc.sum() - max(byday.values())
    ce = np.mean([x["ce_c"] for x in rows])
    return (f"| {tag} | {len(rows)} | {len(rows)/ndays:.2f} | {g.mean():+.2f} | {ce:.1f} | {cc.mean():.2f} | {nc.mean():+.2f} | {(g-cu).mean():+.2f} | {(g-c15).mean():+.2f} | "
            f"{nc.sum()/MO/seeds:+,.0f} | {mo(y1, nd1):+,.0f} / {mo(y2, nd2):+,.0f} | {exbest/MO/seeds:+,.0f} | {(g>0).mean()*100:.0f}% |")


HDR = ("| set | n | tkt/day | gross $/tkt | entry central bps | cost $/tkt (central) | net $/tkt central | net $/tkt upper(EVID) | net $/tkt @15bps | "
       "$/mo central | Y1 / Y2 $/mo | ex-best-day $/mo | win |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|")


def qtab(rows, ctrl, key, qs, label):
    edges = np.percentile([x[key] for x in rows], qs)
    print(f"\n#### {label}: buckets by {key} (R4 edges = quintiles of R4 legs)\n")
    print("| bucket | R4 n | R4 gross $/tkt | R4 net central | RND n | RND gross $/tkt | R4−RND gross | R4 cost central $/tkt |\n|---|---:|---:|---:|---:|---:|---:|---:|")
    e = [-np.inf] + list(edges[1:-1]) + [np.inf]
    for a, b in zip(e[:-1], e[1:]):
        r = [x for x in rows if a <= x[key] < b]; c = [x for x in ctrl if a <= x[key] < b]
        rg = np.mean([x["g"] for x in r]) if r else np.nan
        cg = np.mean([x["g"] for x in c]) if c else np.nan
        print(f"| {a:,.1f}–{b:,.1f} | {len(r)} | {rg:+.2f} | {np.mean([x['g']-x['cost_c'] for x in r]):+.2f} | {len(c)} | {cg:+.2f} | {rg-cg:+.2f} | {np.mean([x['cost_c'] for x in r]):.2f} |")


def main():
    r4 = frame("R4")
    ctrl = [x for k in R4["legs"] if k.startswith("RND") for x in frame(k)]
    c37 = frame("C37F"); h1 = frame("HOLD1")
    print("calib: R4 mean EVID bps/side (upper, entry+exit)/2 =",
          round(np.mean([(x["cost_u"]) / x["N10"] * 1e4 / 2 for x in r4]), 2),
          " central", round(np.mean([(x["cost_c"]) / x["N10"] * 1e4 / 2 for x in r4]), 2),
          " entry upper mean", round(np.mean([x["ce_u"] for x in r4]), 1), "median", round(np.median([x["ce_u"] for x in r4]), 1))
    print("RND entry upper mean", round(np.mean([x["ce_u"] for x in ctrl]), 1), " C37F", round(np.mean([x["ce_u"] for x in c37]), 1))
    print("corr(h_e, log dv30) R4:", round(np.corrcoef([x["h_e"] for x in r4], np.log1p([x["dv30"] for x in r4]))[0, 1], 2))
    print("\n" + HDR)
    print(summ(r4, "R4 all"))
    print(summ(ctrl, "RND30 pooled (per-seed rate)", NDAYS * 30, 30))
    print(summ(c37, "C37F-hf3 all"))
    print(summ(h1, "HOLD1-hf3 all"))
    for key, lab in (("h_e", "entry half-spread bps"), ("dv30", "trailing-30m $ volume"), ("px", "price")):
        qtab(r4, ctrl, key, [0, 20, 40, 60, 80, 100], lab)
    qtab(c37, ctrl, "h_e", [0, 20, 40, 60, 80, 100], "C37F (control = R4 RND frame)")
    print("\n#### causal entry-cost filters (skip-and-stay-flat approximation)\n")
    print(HDR)
    for X in (8, 10, 12, 15, 20, 25, 35):
        print(summ([x for x in r4 if x["h_e"] <= X], f"R4 h_e<={X}"))
        print(summ([x for x in r4 if x["h_e"] > X], f"R4 h_e>{X}"))
    for X in (8, 10, 12, 15, 20):
        print(summ([x for x in ctrl if x["h_e"] <= X], f"RND30 h_e<={X}", NDAYS * 30, 30))
    for D in (2e5, 5e5, 1e6, 2e6):
        print(summ([x for x in r4 if x["dv30"] >= D], f"R4 dv30>={D/1e6:g}M"))
    for X in (10, 15, 20):
        print(summ([x for x in c37 if x["h_e"] <= X], f"C37F h_e<={X}"))
        print(summ([x for x in h1 if x["h_e"] <= X], f"HOLD1 h_e<={X}"))
    # top legs concentration within cheap subsets
    for X in (12, 15, 20):
        s = sorted([x["g"] - x["cost_c"] for x in r4 if x["h_e"] <= X], reverse=True)
        print(f"R4 h_e<={X}: total net central {sum(s):+,.0f}, top5 {sum(s[:5]):+,.0f}, ex-top5 {sum(s[5:]):+,.0f}")
    s = sorted([x["g"] - x["cost_c"] for x in r4], reverse=True)
    print(f"R4 all: total {sum(s):+,.0f} top5 {sum(s[:5]):+,.0f} ex-top5 {sum(s[5:]):+,.0f}")


if __name__ == "__main__":
    main()
