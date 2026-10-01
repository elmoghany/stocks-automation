"""LEGACY-12: size / price / float buckets on HONEST trade dumps.

Inputs (read-only): plan/pa_out/cp_r4_legs.json + cp_r4_evid.json (CHAMPION-REPLAY
R4 + 30 random seeds, per-leg evidence cost), data/massive/rotation_trades_C37F_hf3.json,
data/massive/cp_prior/<date>.json.gz (prior-only dvol60/prevclose/nhist),
data/massive/gd/<date>.json.gz (prior-session dollar volume), data/pt_shares (PIT shares;
rh_fundamentals fallback deliberately NOT used -- present-day, leaks).
All features are known before the session opens (or at entry, for entry price).
Output: plan/lm12_out.json + printed tables.  $10k ticket normalisation.
"""
import gzip
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\cornell\stocks-automation\day-trading")
PA = ROOT / "plan/pa_out"
GD = ROOT / "data/massive/gd"
CPP = ROOT / "data/massive/cp_prior"
PTS = ROOT / "data/pt_shares"
Y1_END = "2025-08-01"
TK = 10_000.0

gd_dates = sorted(p.name.split(".")[0] for p in GD.glob("*.json.gz"))
_gd, _cp = {}, {}


def prev_gd(date):
    i = np.searchsorted(gd_dates, date) - 1
    return gd_dates[i] if i >= 0 else None


def gd_dv(date):
    if date not in _gd:
        with gzip.open(GD / f"{date}.json.gz", "rt", encoding="utf-8") as fh:
            _gd[date] = {r["T"]: (r.get("c") or 0) * (r.get("v") or 0) for r in json.load(fh) if r.get("T")}
        if len(_gd) > 30:
            _gd.pop(next(iter(_gd)))
    return _gd[date]


def cpp(date):
    if date not in _cp:
        f = CPP / f"{date}.json.gz"
        _cp[date] = json.load(gzip.open(f, "rt", encoding="utf-8")) if f.exists() else {}
        if len(_cp) > 30:
            _cp.pop(next(iter(_cp)))
    return _cp[date]


def pit_shares(sym, date):
    f = PTS / f"{sym}_{date}.json"
    if f.exists():
        try:
            return float(json.loads(f.read_text()))
        except Exception:
            return None
    return None


def feats(sym, date, entry):
    c = cpp(date).get(sym)
    pd = prev_gd(date)
    pdv = gd_dv(pd).get(sym) if pd else None
    sh = pit_shares(sym, date)
    pc = c[3] if c else None
    return dict(price=entry, dvol60=c[0] if c else None, nhist=c[2] if c else None,
                pdv=pdv, shares=sh, mcap=(sh * pc) if (sh and pc) else None,
                rvol1=(pdv / c[0]) if (pdv and c and c[0]) else None)


BK = {
    "price": [0, 2, 5, 10, 20, 50, 1e9],
    "dvol60": [0, 1e6, 5e6, 20e6, 100e6, 1e15],
    "pdv": [0, 1e6, 5e6, 20e6, 100e6, 1e15],
    "shares": [0, 10e6, 30e6, 100e6, 300e6, 1e15],
    "mcap": [0, 50e6, 300e6, 2e9, 10e9, 1e16],
    "rvol1": [0, 0.5, 1, 2, 5, 1e9],
    "nhist": [0, 59, 61, 1e9],
}


def bucket(k, v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "NA"
    e = BK[k]
    for a, b in zip(e[:-1], e[1:]):
        if a <= v < b:
            return f"{a:g}-{b:g}"
    return "NA"


def load_r4():
    L = json.loads((PA / "cp_r4_legs.json").read_text())
    E = json.loads((PA / "cp_r4_evid.json").read_text())
    out = {}
    for k, legs in L["legs"].items():
        ev = E["legs"][k]
        assert len(ev) == len(legs), k
        rows = []
        for a, b in zip(legs, ev):
            assert a["date"] == b["date"] and abs(a["gross"] - b["gross"]) < 1e-6
            n1 = a["entry"] * a["shares"]
            bps = b["cost_evid"] / b["notional2"] * 1e4      # per side, evidence (upper) cost
            rows.append(dict(date=a["date"], sym=a["sym"], entry=a["entry"],
                             ret=a["gross"] / n1, bps=bps, em=a["entry_min"]))
        out[k] = rows
    return out, L["ndays"]


def load_hf3():
    d = json.loads((ROOT / "data/massive/rotation_trades_C37F_hf3.json").read_text())
    return [dict(date=t["date"], sym=t["symbol"], entry=t["entry"],
                 ret=(t["exit"] - t["entry"]) / t["entry"], bps=None) for t in d]


def summ(rows, ndays, bps_fn):
    if not rows:
        return None
    g = np.array([r["ret"] * TK for r in rows])
    b = np.array([bps_fn(r) for r in rows])
    n = g - 2 * TK * b / 1e4
    y1 = [i for i, r in enumerate(rows) if r["date"] < Y1_END]
    y2 = [i for i, r in enumerate(rows) if r["date"] >= Y1_END]
    mo = ndays / 21.0
    f = lambda a, ix: float(np.mean(a[ix])) if ix else None
    days = defaultdict(float)
    for r, x in zip(rows, n):
        days[r["date"]] += x
    best = max(days.values())
    return dict(n=len(rows), gross=float(g.mean()), bps=float(b.mean()), net=float(n.mean()),
                net_mo=float(n.sum() / mo), net_exbest_mo=float((n.sum() - best) / mo),
                g_y1=f(g, y1), g_y2=f(g, y2), n_y1=f(n, y1), n_y2=f(n, y2),
                ny1=len(y1), ny2=len(y2), win=float((g > 0).mean()))


def main():
    r4, ndays = load_r4()
    hf3 = load_hf3()
    hf3_days = len({r["date"] for r in hf3})   # traded days; ledger spans same window
    # attach features
    cache = {}
    allsets = dict(r4)
    allsets["HF3"] = hf3
    keys = sorted({(r["date"], r["sym"]) for rows in allsets.values() for r in rows})
    for i, (d, s) in enumerate(keys):          # date-ordered: each gd/cp_prior file loaded once
        cache[(s, d)] = feats(s, d, None)
        if i % 5000 == 0:
            print("  feats", i, len(keys), flush=True)
    for k, rows in allsets.items():
        for r in rows:
            f = dict(cache[(r["sym"], r["date"])])
            f["price"] = r["entry"]
            r["f"] = f
    # coverage
    cov = {k: sum(1 for r in r4["R4"] if r["f"][k] is not None) for k in BK}
    covh = {k: sum(1 for r in hf3 if r["f"][k] is not None) for k in BK}
    print("coverage R4", len(r4["R4"]), cov, "HF3", len(hf3), covh)
    # cost-by-bucket model from ALL R4+random legs (evidence cost, per side)
    pool = [r for k, rows in r4.items() for r in rows]
    cost_tab = {}
    for k in ("price", "dvol60"):
        d = defaultdict(list)
        for r in pool:
            d[bucket(k, r["f"][k])].append(r["bps"])
        cost_tab[k] = {b: (float(np.mean(v)), float(np.median(v)), len(v)) for b, v in d.items()}
    pd2 = defaultdict(list)
    for r in pool:
        pd2[(bucket("price", r["f"]["price"]), bucket("dvol60", r["f"]["dvol60"]))].append(r["bps"])
    cmap = {kk: float(np.mean(v)) for kk, v in pd2.items() if len(v) >= 30}
    gmean = float(np.mean([r["bps"] for r in pool]))

    def hf3_bps(r):
        kk = (bucket("price", r["f"]["price"]), bucket("dvol60", r["f"]["dvol60"]))
        return cmap.get(kk, cost_tab["price"].get(kk[0], (gmean,))[0])

    res = {"cost_tab": cost_tab, "ndays": ndays, "hf3_days": hf3_days}
    rnd_keys = [k for k in r4 if k.startswith("RND")]
    for k in BK:
        res[k] = {}
        groups = defaultdict(lambda: defaultdict(list))
        for name, rows in allsets.items():
            for r in rows:
                groups[bucket(k, r["f"][k])][name].append(r)
        for b, g in sorted(groups.items()):
            R = summ(g.get("R4", []), ndays, lambda r: r["bps"])
            Rc = summ(g.get("R4", []), ndays, lambda r: 0.65 * r["bps"])   # central ~ 0.65x upper
            rnd = [r for kk in rnd_keys for r in g.get(kk, [])]
            RN = summ(rnd, ndays * len(rnd_keys), lambda r: r["bps"])
            H = summ(g.get("HF3", []), ndays, hf3_bps)
            res[k][b] = dict(R4=R, R4_central=Rc, RND=RN, HF3=H)
    (ROOT / "plan/lm12_out.json").write_text(json.dumps(res, indent=1, default=float))

    def fm(x, key, p=1):
        return "" if (x is None or x.get(key) is None) else f"{x[key]:.{p}f}"
    print("\ncost (evid upper, bps/side) by price:", {b: round(v[0], 1) for b, v in cost_tab["price"].items()})
    print("cost by dvol60:", {b: round(v[0], 1) for b, v in cost_tab["dvol60"].items()})
    for k in BK:
        print(f"\n== {k} ==  [R4: n gross net(evid) net(central) gY1 gY2 nY1c nY2c mo(central)] | [RND: n gross bps] | [HF3: n gross gY1 gY2 net]")
        for b, v in res[k].items():
            R, Rc, RN, H = v["R4"], v["R4_central"], v["RND"], v["HF3"]
            print(f"{b:>14} | R4 {fm(R,'n',0):>4} {fm(R,'gross'):>7} {fm(R,'net'):>7} {fm(Rc,'net'):>7} "
                  f"{fm(R,'g_y1'):>7} {fm(R,'g_y2'):>7} {fm(Rc,'n_y1'):>7} {fm(Rc,'n_y2'):>7} {fm(Rc,'net_mo',0):>6}"
                  f" | RND {fm(RN,'n',0):>5} {fm(RN,'gross'):>6} {fm(RN,'bps'):>5}"
                  f" | HF3 {fm(H,'n',0):>4} {fm(H,'gross'):>7} {fm(H,'g_y1'):>7} {fm(H,'g_y2'):>7} {fm(H,'net'):>7}")


if __name__ == "__main__":
    main()
