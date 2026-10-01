"""LEGACY-10 regime features. Every feature for trading day D uses ONLY data
through the close of the previous session (gd day D-1 and earlier).
Writes a pickle to the scratchpad path given as argv[1]."""
import gzip, json, os, sys, pickle
import numpy as np

GD = os.path.join(os.path.dirname(__file__), "..", "data", "massive", "gd")
files = sorted(f for f in os.listdir(GD) if f.endswith(".json.gz"))
dates = [f[:10] for f in files]
ETF = ("SPY", "QQQ", "IWM", "IWC", "XBI", "ARKK")
etf = {e: [] for e in ETF}
prevc = {}            # last close per ticker
hist = {}             # ticker -> list of last 20 closes (for small-cap MA breadth)
day = {}              # date -> dict of same-day stats (known after that close)
for f, d in zip(files, dates):
    rows = json.load(gzip.open(os.path.join(GD, f)))
    n_g10h = n_g10o = n_up = n_sc = n_ab20 = 0
    g_ret = []          # gapper (open-gap>=10%) close/open returns
    g_cl_hi = []        # gapper close location vs high
    sc_dv = 0.0
    big_run = 0         # close/prevc >= 1.5
    for r in rows:
        t = r.get("T"); c = r.get("c"); o = r.get("o"); h = r.get("h"); v = r.get("v") or 0
        if t is None or c is None:
            continue
        if t in etf:
            etf[t].append((d, o, h, r.get("l"), c))
        pc = prevc.get(t)
        if pc and pc > 0 and 1 <= pc <= 50 and v * c >= 2e5:
            if h / pc >= 1.10:
                n_g10h += 1
            if o and o / pc >= 1.10:
                n_g10o += 1
                g_ret.append(c / o - 1)
                g_cl_hi.append((c - o) / max(h - o, 1e-9) if h > o else 0.0)
            if c / pc >= 1.5:
                big_run += 1
        if pc and 1 <= c <= 20 and v * c >= 1e6:
            n_sc += 1
            n_up += c > pc
            sc_dv += v * c
            hh = hist.get(t)
            if hh and len(hh) >= 20:
                n_ab20 += c > np.mean(hh[-20:])
        prevc[t] = c
        hh = hist.setdefault(t, [])
        hh.append(c)
        if len(hh) > 21:
            del hh[0]
    day[d] = dict(n_g10h=n_g10h, n_g10o=n_g10o, big_run=big_run,
                  g_ret=float(np.median(g_ret)) if g_ret else np.nan,
                  g_hold=float(np.mean(g_cl_hi)) if g_cl_hi else np.nan,
                  sc_up=n_up / max(n_sc, 1), sc_ab20=n_ab20 / max(n_sc, 1),
                  sc_dv=sc_dv)

# per-ETF series
ser = {}
for e, L in etf.items():
    m = {x[0]: x for x in L}
    ser[e] = m

def etf_feats(e, i):
    """features from ETF e using dates[:i] (i.e. through dates[i-1])."""
    cl = [ser[e][x][4] for x in dates[:i] if x in ser[e]]
    if len(cl) < 51:
        return {}
    cl = np.array(cl)
    r = np.diff(np.log(cl))
    return {f"{e}_r1": cl[-1] / cl[-2] - 1, f"{e}_r5": cl[-1] / cl[-6] - 1,
            f"{e}_r20": cl[-1] / cl[-21] - 1,
            f"{e}_ma20": cl[-1] / cl[-20:].mean() - 1,
            f"{e}_ma50": cl[-1] / cl[-50:].mean() - 1,
            f"{e}_vol10": r[-10:].std() * np.sqrt(252),
            f"{e}_vol20": r[-20:].std() * np.sqrt(252),
            f"{e}_volratio": r[-5:].std() / max(r[-20:].std(), 1e-9)}

out = {}
for i, d in enumerate(dates):
    if i < 51:
        continue
    F = {}
    for e in ETF:
        F.update(etf_feats(e, i))
    if "IWM_r20" in F and "SPY_r20" in F:
        F["IWMvSPY_r20"] = F["IWM_r20"] - F["SPY_r20"]
        F["IWMvSPY_r5"] = F["IWM_r5"] - F["SPY_r5"]
    p = [day[x] for x in dates[i - 20:i]]
    y = p[-1]
    for k in ("n_g10h", "n_g10o", "big_run", "g_ret", "g_hold", "sc_up", "sc_ab20"):
        F[k + "_1"] = y[k]
        F[k + "_5"] = float(np.nanmean([q[k] for q in p[-5:]]))
    F["n_g10h_5v20"] = F["n_g10h_5"] / max(np.mean([q["n_g10h"] for q in p]), 1)
    F["sc_dv_5v20"] = np.mean([q["sc_dv"] for q in p[-5:]]) / np.mean([q["sc_dv"] for q in p])
    out[d] = F
pickle.dump(out, open(sys.argv[1], "wb"))
print(len(out), min(out), max(out), len(next(iter(out.values()))))
