"""SWING-EARNINGS step 5: event-level study + portfolio simulation.

Inputs (all under data/research_oct): se_panel.npz, se_events.json, m1/part_*.npz
Everything that conditions an entry is computed from information printed
BEFORE the fill:
  O    entry = OPEN of the 09:31 bar (gap = gd open / prev close, known at 09:30)
  M5   entry = OPEN of the 09:36 bar (first print 09:36..09:40), green@09:35 known
  M30  entry = OPEN of the 10:01 bar (first print 10:01..10:05), green@10:00 known
  C    entry = day-1 official CLOSE (gd c, MOC); conditions use the 15:55 minute
       close and volume through 15:55 (an MOC order is placeable until 15:50/15:55)
Exits: C0 = day-1 close (intraday entries only), Ok / Ck = open / close of
session day1+k, k in {1,2,3,5,10}; H60 = open of the first print >= 10:36
(M5 only, the R15 exit).  A symbol that stops printing before the exit is
flattened at its last printed close (no survivorship drop).  Horizons running
past the last panel date are censored (not traded).
Costs per side = base (6 or 12 bps) + impact, impact = Y * sigma20 *
sqrt(notional / ADV20$), Y = 0.5 (PESSIMISM-AUDIT: the textbook Y=1 daily form
over-charges ~3x on $15k orders; event-day volume is 3-5x ADV20, which this
ignores -- conservative).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "data" / "research_oct"
SPLITS = [("Y1", "2024-10-01", "2025-07-31"), ("Y2", "2025-08-01", "2026-07-31"),
          ("OOS", "2026-08-01", "2026-12-31")]
HOLDS = [1, 2, 3, 5, 10]
Y_IMPACT = 0.5
MINUTE_END = "2026-08-06"     # last date of the outcome-blind m1o cache
FULL_OOS_TAPE = False         # set True only if every top-600 OOS tape was fetched


def split_of(d):
    for n, lo, hi in SPLITS:
        if lo <= d <= hi:
            return n
    return None


class Data:
    def __init__(self):
        P = np.load(OUT / "se_panel.npz")
        self.dates = P["dates"].tolist()
        self.syms = P["syms"].tolist()
        for k in ("o", "h", "l", "c", "v", "liq", "adv20", "sig20", "ma20ok"):
            setattr(self, k, P[k])
        self.D = len(self.dates)
        self.spy = self.syms.index("SPY")
        self.ev = json.loads((OUT / "se_events.json").read_text())
        t6 = json.loads((OUT / "se_top600.json").read_text())
        self.t600 = {(s_, d) for d, ss in t6.items() for s_ in ss}
        self.r15m = r15_members()
        self.m1 = {}
        for f in sorted((OUT / "se_m1").glob("part_*.npz")):
            z = np.load(f)
            for k, a in zip(z["keys"].tolist(), z["a"]):
                self.m1[k] = a

    def last_close(self, j, d_from, d_to):
        """close at d_to, or the last printed close in (d_from, d_to]."""
        for d in range(d_to, d_from - 1, -1):
            x = self.c[d, j]
            if not np.isnan(x):
                return float(x)
        return float("nan")

    def exit_px(self, j, d1, k, which):
        d = d1 + k
        if d >= self.D:
            return float("nan"), None
        x = self.o[d, j] if which == "O" else self.c[d, j]
        if np.isnan(x):
            x = self.last_close(j, d1, d)
        return float(x), d


def first_print(a, k0, k1, row=0):
    for k in range(k0, k1 + 1):
        if not np.isnan(a[row, k]):
            return float(a[row, k])
    return float("nan")


def ffill(a, k, row=1):
    for i in range(k, -1, -1):
        if not np.isnan(a[row, i]):
            return float(a[row, i])
    return float("nan")


def build_table(X):
    """One row per (event, entry type) with all features + gross returns."""
    rows = []
    for e in X.ev:
        j, d1 = e["j"], e["d1"]
        pc = float(X.c[d1 - 1, j])
        o1 = float(X.o[d1, j])
        c1 = float(X.c[d1, j])
        if not (pc > 0 and o1 > 0 and c1 > 0):
            continue
        sp = split_of(e["day1"])
        if sp is None:
            continue
        a = X.m1.get(f"{e['sym']}|{e['day1']}")
        if a is not None:
            # unit fix: minute caches were split-adjusted on other dates than gd
            lastc = ffill(a, 389)
            if lastc > 0 and abs(math.log(c1 / lastc)) > 0.02:
                a = a.copy()
                a[:2] *= c1 / lastc
        base = {"sym": e["sym"], "j": j, "d1": d1, "day1": e["day1"], "split": sp,
                "timing": e["timing"], "surprise": e["surprise"],
                "gap": o1 / pc - 1.0,
                "tr20": pc / float(X.c[d1 - 21, j]) - 1.0 if X.c[d1 - 21, j] > 0 else np.nan,
                "tr60": pc / float(X.c[d1 - 61, j]) - 1.0 if X.c[d1 - 61, j] > 0 else np.nan,
                "regime": bool(X.ma20ok[d1]), "adv": float(X.adv20[d1, j]),
                "sig": float(X.sig20[d1, j])}
        ents = {}
        v1 = float(X.v[d1, j])
        day1f = {"ret_e": c1 / o1 - 1.0, "ret_pc": c1 / pc - 1.0,
                 "evol": v1 * c1 / max(base["adv"], 1.0)}
        # daily-bar entries: every event
        ents["O"] = (o1, {})                 # 09:30 open; only PRE-OPEN conditions allowed
        ents["C"] = (c1, dict(day1f))        # day-1 close (MOC), day-1 bar observable
        if d1 + 1 < X.D:
            ents["N"] = (float(X.o[d1 + 1, j]), dict(day1f))   # day-2 open, fully causal
        h60 = float("nan")
        if a is not None:                    # minute-tape entries: covered events only
            e931 = first_print(a, 1, 5)
            ents["O1"] = (e931, {})
            m935 = ffill(a, 5)
            e936 = first_print(a, 6, 10)
            ev935 = np.nansum(a[2, :6]) * o1 / max(base["adv"], 1.0)
            ents["M5"] = (e936, {"ret_e": m935 / o1 - 1.0, "evol": ev935})
            m1000 = ffill(a, 30)
            e1001 = first_print(a, 31, 35)
            ev1000 = np.nansum(a[2, :31]) * o1 / max(base["adv"], 1.0)
            ents["M30"] = (e1001, {"ret_e": m1000 / o1 - 1.0, "evol": ev1000})
            h60 = first_print(a, 66, 389)
            if np.isnan(h60):
                h60 = ffill(a, 389)
        for en, (px, f) in ents.items():
            if not (px > 0):
                continue
            key_ = (e["sym"], e["day1"])
            if en in ("O1", "M5", "M30") and ((key_ not in X.t600 and key_ not in X.r15m)
                                             or (e["day1"] > MINUTE_END and not FULL_OOS_TAPE)):
                continue          # minute tapes are complete ONLY on the causal top-600 set
            r = dict(base)
            r.update(f)
            r["entry"] = en
            r["px"] = px
            r["minute"] = a is not None
            r["t600"] = (e["sym"], e["day1"]) in X.t600
            r["r15u"] = (e["sym"], e["day1"]) in X.r15m
            g = {}
            if en not in ("C", "N"):
                g["C0"] = (c1 / px - 1.0, d1)
            if en == "M5" and h60 > 0:
                g["H60"] = (h60 / px - 1.0, d1)
            for k in HOLDS:
                for w in "OC":
                    if en == "N" and w == "O" and k == 1:
                        continue
                    x, dx = X.exit_px(j, d1, k, w)
                    if dx is not None and x > 0:
                        g[f"{w}{k}"] = (x / px - 1.0, dx)
            r["g"] = g
            rows.append(r)
    return rows


def impact(r, notional):
    s, adv = r["sig"], r["adv"]
    if not (s > 0 and adv > 0):
        s, adv = 0.03, 5e6
    return Y_IMPACT * s * math.sqrt(notional / adv) * 1e4


def net_ret(r, ex, base_bps, notional):
    g = r["g"][ex][0]
    cs = (base_bps + impact(r, notional)) * 1e-4
    return (1.0 + g) * (1.0 - cs) / (1.0 + cs) - 1.0


# --------------------------------------------------------------- conditions
def _g(k, f):
    return lambda r: (k in r) and r[k] is not None and not (isinstance(r[k], float) and np.isnan(r[k])) and f(r[k])


C_ALL = {
    "all": lambda r: True,
    "gap>0": _g("gap", lambda x: x > 0), "gap<0": _g("gap", lambda x: x < 0),
    "gap>2%": _g("gap", lambda x: x > .02), "gap>5%": _g("gap", lambda x: x > .05),
    "gap<-2%": _g("gap", lambda x: x < -.02), "gap<-5%": _g("gap", lambda x: x < -.05),
    "regime": lambda r: r["regime"], "tr20>0": _g("tr20", lambda x: x > 0),
    "tr20<0": _g("tr20", lambda x: x < 0),
    "surp>0": _g("surprise", lambda x: x > 0), "surp<0": _g("surprise", lambda x: x < 0),
}
C_INTRA = {
    "green": _g("ret_e", lambda x: x > 0), "red": _g("ret_e", lambda x: x < 0),
    "green&gap>0": lambda r: C_INTRA["green"](r) and r["gap"] > 0,
    "green&gap>2%": lambda r: C_INTRA["green"](r) and r["gap"] > .02,
    "green&gap<0": lambda r: C_INTRA["green"](r) and r["gap"] < 0,
    "green&regime": lambda r: C_INTRA["green"](r) and r["regime"],
    "green&evol>hi": lambda r: C_INTRA["green"](r) and r.get("evol", 0) > (0.15 if r["entry"] == "M5" else 0.35),
    "green&tr20>0": lambda r: C_INTRA["green"](r) and (r["tr20"] or 0) > 0,
    "green&surp>0": lambda r: C_INTRA["green"](r) and C_ALL["surp>0"](r),
}
C_CLOSE = {
    "day1 up": _g("ret_pc", lambda x: x > 0), "day1 down": _g("ret_pc", lambda x: x < 0),
    "day1>+3%": _g("ret_pc", lambda x: x > .03), "day1>+7%": _g("ret_pc", lambda x: x > .07),
    "day1<-3%": _g("ret_pc", lambda x: x < -.03), "day1<-7%": _g("ret_pc", lambda x: x < -.07),
    "o->c green": _g("ret_e", lambda x: x > 0),
    "day1>+3%&o->c green": lambda r: C_CLOSE["day1>+3%"](r) and r["ret_e"] > 0,
    "day1>+3%&vol>2x": lambda r: C_CLOSE["day1>+3%"](r) and r["evol"] > 2,
    "day1>+3%&regime": lambda r: C_CLOSE["day1>+3%"](r) and r["regime"],
    "gap>0&o->c green": lambda r: r["gap"] > 0 and C_CLOSE["o->c green"](r),
    "gap<0&o->c green": lambda r: r["gap"] < 0 and C_CLOSE["o->c green"](r),
    "day1 up&surp>0": lambda r: C_CLOSE["day1 up"](r) and C_ALL["surp>0"](r),
    "day1<-3%&tr20>0": lambda r: C_CLOSE["day1<-3%"](r) and (r["tr20"] or 0) > 0,
}


PREOPEN = ("all", "regime", "tr20>0", "tr20<0", "surp>0", "surp<0")


def conds_for(entry):
    c = dict(C_ALL)
    if entry == "O":
        c = {k: v for k, v in C_ALL.items() if k in PREOPEN}
        c["am"] = lambda r: r["timing"] == "am"
        c["pm"] = lambda r: r["timing"] == "pm"
    if entry in ("M5", "M30"):
        c.update(C_INTRA)
    if entry in ("C", "N"):
        c.update(C_CLOSE)
    return c


EXITS = {"O": ["C0"] + [f"{w}{k}" for k in HOLDS for w in "OC"],
         "O1": ["C0"] + [f"{w}{k}" for k in HOLDS for w in "OC"],
         "N": [f"{w}{k}" for k in HOLDS for w in "OC" if (w, k) != ("O", 1)],
         "M5": ["H60", "C0"] + [f"{w}{k}" for k in HOLDS for w in "OC"],
         "M30": ["C0"] + [f"{w}{k}" for k in HOLDS for w in "OC"],
         "C": [f"{w}{k}" for k in HOLDS for w in "OC"]}


def stat(x):
    x = np.asarray(x)
    if len(x) < 2:
        return {"n": int(len(x)), "bps": float(np.mean(x) * 1e4) if len(x) else float("nan"),
                "t": float("nan"), "win": float("nan")}
    return {"n": int(len(x)), "bps": float(x.mean() * 1e4),
            "t": float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))),
            "win": float((x > 0).mean())}


def grid(rows, base_bps=6.0, notional=10_000.0):
    """{(entry, cond, exit): {split: stat}} on net returns."""
    by_entry = {}
    for r in rows:
        by_entry.setdefault(r["entry"], []).append(r)
    out = {}
    for en, rs in by_entry.items():
        for cn, f in conds_for(en).items():
            sel = [r for r in rs if f(r)]
            for ex in EXITS[en]:
                res = {}
                for sp in ("Y1", "Y2", "OOS"):
                    x = [net_ret(r, ex, base_bps, notional) for r in sel
                         if r["split"] == sp and ex in r["g"]]
                    res[sp] = stat(x)
                out[(en, cn, ex)] = res
    return out


# --------------------------------------------------------------- controls
SLOT = {"O": 0, "O1": 0, "N": 0, "M5": 1, "M30": 2, "C": 3}


def entry_day(r):
    return r["d1"] + (1 if r["entry"] == "N" else 0)


def event_days(X):
    s = {}
    for e in X.ev:
        s.setdefault(e["j"], []).append(e["d1"])
    return s


def control_draws(X, sel, ex, base_bps, notional, seeds=30, evd=None):
    """Same symbols / same split / same entry clock (open or close) / same hold,
    on a RANDOM non-earnings day (no event of the symbol within +-10 sessions).
    Intraday entries (O/M5/M30) are proxied by the session OPEN on the control
    day (no minute tape there).  Returns list of per-seed mean net returns and
    the pooled SPY-over-the-same-window mean for the rule's own trades."""
    evd = evd or event_days(X)
    split_rng = {}
    for n, lo, hi in SPLITS:
        idx = [i for i, d in enumerate(X.dates) if lo <= d <= hi and i >= 61]
        split_rng[n] = (idx[0], idx[-1]) if idx else (None, None)
    w, k = ex[0], (0 if ex in ("C0", "H60") else int(ex[1:]))
    if ex == "H60":
        return None
    means = []
    for sd in range(seeds):
        rng = np.random.default_rng(1000 + sd)
        x = []
        for r in sel:
            j = r["j"]
            lo, hi = split_rng[r["split"]]
            bad = set()
            for d in evd.get(j, []):
                bad.update(range(d - 10, d + 11))
            for _ in range(20):
                d = int(rng.integers(lo, hi + 1))
                kk = k - 1 if r["entry"] == "N" else k
                if d in bad or not X.liq[d, j] or d + kk >= X.D:
                    continue
                en = X.c[d, j] if r["entry"] == "C" else X.o[d, j]
                xp = X.c[d + kk, j] if w == "C" else X.o[d + kk, j]
                if not (en > 0 and xp > 0):
                    continue
                g = xp / en - 1.0
                cs = (base_bps + impact(r, notional)) * 1e-4
                x.append((1 + g) * (1 - cs) / (1 + cs) - 1)
                break
        means.append(float(np.mean(x)) if x else float("nan"))
    return means


def spy_same_window(X, r, ex):
    """SPY return over the trade's own window (intraday entries -> SPY open)."""
    s = X.spy
    d1 = r["d1"]
    en = X.c[d1, s] if r["entry"] == "C" else X.o[entry_day(r), s]
    if ex in ("C0", "H60"):
        xp = X.c[d1, s]
    else:
        k = int(ex[1:])
        if d1 + k >= X.D:
            return float("nan")
        xp = X.c[d1 + k, s] if ex[0] == "C" else X.o[d1 + k, s]
    return float(xp / en - 1.0)


# --------------------------------------------------------------- portfolio
def portfolio(X, sel, ex, base_bps, S, N, cash0=100_000.0, seed=0, rank=None):
    """Cash account, settled-cash rule (T+1), at most N concurrent positions of
    fixed notional S.  Candidates at the same (day, clock slot) are taken in a
    seeded-random order, or by `rank` (a causal key, larger first).
    Returns (trades list, daily MTM equity array over the split's days)."""
    rng = np.random.default_rng(seed)
    cands = {}
    for r in sel:
        if ex not in r["g"]:
            continue
        key = (entry_day(r), SLOT[r["entry"]])
        cands.setdefault(key, []).append(r)
    if not cands:
        return [], np.array([cash0])
    xd = {"C0": None, "H60": None}
    d_lo = min(k[0] for k in cands)
    d_hi = max(r["g"][ex][1] for v in cands.values() for r in v)
    settled, pending, opn, trades = cash0, [], [], []
    eq = []
    for d in range(d_lo, d_hi + 1):
        settled += sum(a for a, sd in pending if sd <= d)
        pending = [(a, sd) for a, sd in pending if sd > d]
        for slot in range(4):
            # exits first (their cash settles next session)
            keep = []
            for p in opn:
                xslot = 2 if ex == "H60" else (3 if ex[0] == "C" else 0)
                if p["xd"] == d and xslot == slot:
                    proceeds = S * (1 + p["net"])
                    pending.append((proceeds, d + 1))
                    trades.append(p)
                else:
                    keep.append(p)
            opn = keep
            cl = cands.get((d, slot), [])
            if cl:
                if rank is None:
                    order = rng.permutation(len(cl))
                    cl = [cl[i] for i in order]
                else:
                    tie = rng.random(len(cl))
                    cl = [cl[i] for i in sorted(range(len(cl)), key=lambda i: (-rank(cl[i]), tie[i]))]
                for r in cl:
                    if len(opn) >= N or settled < S - 1e-6:
                        break
                    settled -= S
                    net = net_ret(r, ex, base_bps, S)
                    opn.append({"sym": r["sym"], "day1": r["day1"], "d1": entry_day(r),
                                "xd": r["g"][ex][1], "net": net, "pnl": S * net,
                                "j": r["j"], "px": r["px"], "entry": r["entry"]})
        # mark-to-market at the close (open positions at close price, gross)
        mtm = 0.0
        for p in opn:
            c = X.c[d, p["j"]]
            if not (c > 0):
                c = X.last_close(p["j"], p["d1"], d)
            mtm += S * (c / p["px"]) if c > 0 else S
        eq.append(settled + sum(a for a, _ in pending) + mtm)
    return trades, np.array(eq)


def maxdd(eq):
    if len(eq) == 0:
        return 0.0
    pk = np.maximum.accumulate(eq)
    return float((eq - pk).min())


MONTHS = {"Y1": 9.0, "Y2": 12.0, "OOS": 2.0}   # Y1 starts 2024-10-30 (60-session warm-up)


# --------------------------------------------------------------- reports
def r15_syms():
    u = set()
    for p in (HERE / "rl2" / "out" / "universe").glob("*.json"):
        u |= {r["symbol"] for r in json.loads(p.read_text())}
    return u


def r15_members():
    """{(sym, date)} -- R15's own causal wide universe, per date (448 dates
    2024-10-22..2026-08-06; no membership file after that)."""
    m = set()
    for p in (HERE / "rl2" / "out" / "universe").glob("*.json"):
        d = p.stem
        m |= {(r["symbol"], d) for r in json.loads(p.read_text())}
    return m


def halal_syms():
    d = json.loads((ROOT / "data" / "halal_list.json").read_text())
    s = d["symbols"]
    return set(s if isinstance(s, list) else s.keys())


def fmt(st):
    if not st or st["n"] == 0:
        return "   n=0"
    return f"{st['bps']:+7.1f}bp t{st['t']:+5.2f} w{st['win']:.2f} n{st['n']}"


def cmd_grid(X, rows):
    out = {}
    for b in (0.0, 6.0, 12.0):
        G = grid(rows, b, 10_000.0)
        out[str(b)] = {"|".join(k): v for k, v in G.items()}
    (OUT / "se_grid.json").write_text(json.dumps(out))
    G = out["6.0"]
    keys = [k for k, v in G.items() if v["Y1"]["n"] >= 40 and v["Y2"]["n"] >= 40]
    both = [k for k in keys if G[k]["Y1"]["bps"] > 0 and G[k]["Y2"]["bps"] > 0]
    print(f"rules with n>=40 in Y1 and Y2: {len(keys)}; positive in both @6bp: {len(both)}")
    print("\nTOP 25 by Y1 mean (selection on Y1 only) @6 bps + impact($10k):")
    for k in sorted(keys, key=lambda k: -G[k]["Y1"]["bps"])[:25]:
        v = G[k]
        print(f"{k:42s} Y1 {fmt(v['Y1'])} | Y2 {fmt(v['Y2'])} | OOS {fmt(v['OOS'])}")
    print("\nTOP 25 by min(Y1,Y2) t-stat:")
    for k in sorted(keys, key=lambda k: -min(G[k]["Y1"]["t"], G[k]["Y2"]["t"]))[:25]:
        v = G[k]
        print(f"{k:42s} Y1 {fmt(v['Y1'])} | Y2 {fmt(v['Y2'])} | OOS {fmt(v['OOS'])}")


def cmd_r15ext(X, rows):
    """Part (a): the R15 entry (M5, green@09:35) held longer."""
    mem = r15_members()
    cov = {sp: [0, 0] for sp in ("Y1", "Y2", "OOS")}
    for r in rows:
        if r["entry"] == "O" and (r["sym"], r["day1"]) in mem:
            cov[r["split"]][0] += 1
            cov[r["split"]][1] += r["minute"]
    print("R15-universe events / with minute tape per split:", cov)
    allcov = {sp: [0, 0] for sp in ("Y1", "Y2", "OOS")}
    for r in rows:
        if r["entry"] == "O":
            allcov[r["split"]][0] += 1
            allcov[r["split"]][1] += r["minute"]
    print("broad events / with minute tape per split:", allcov)
    for lab, rs in (("causal top-600 liquid set (minute tapes complete there)",
                     [r for r in rows if r["t600"]]),
                    ("R15 universe (rl2 wide halal PIT membership ON day1; ends 2026-08-06)",
                     [r for r in rows if (r["sym"], r["day1"]) in mem])):
        sel = [r for r in rs if r["entry"] == "M5" and C_INTRA["green"](r)]
        print(f"\n(a) M5 green@09:35 entry -- {lab}: {len(sel)} events")
        for ex in EXITS["M5"]:
            line = f"  {ex:4s}"
            for b in (0.0, 6.0, 12.0):
                xs = {sp: [net_ret(r, ex, b, 10_000.0) for r in sel
                           if r["split"] == sp and ex in r["g"]] for sp in ("Y1", "Y2", "OOS")}
                line += f" | @{b:>4}: " + " ".join(f"{sp} {np.mean(x)*1e4:+6.1f}" if x else f"{sp}   na"
                                                for sp, x in xs.items())
            n = sum(ex in r["g"] for r in sel)
            print(line + f"  n={n}")


def select(rows, entry, cond, universe=None):
    f = conds_for(entry)[cond]
    return [r for r in rows if r["entry"] == entry and f(r)
            and (universe is None or r["sym"] in universe)]


def cmd_rule(X, rows, entry, cond, ex, rankname=None):
    sel = select(rows, entry, cond)
    rank = None
    if rankname == "gap":
        rank = lambda r: r["gap"]
    elif rankname == "ret_pc":
        rank = lambda r: r.get("ret_pc", 0)
    print(f"\nRULE {entry} | {cond} | exit {ex} | tie-break {'seeded random' if rank is None else rankname}")
    evd = event_days(X)
    # event level + controls
    for b in (6.0, 12.0):
        for sp in ("Y1", "Y2", "OOS"):
            s_ = [r for r in sel if r["split"] == sp and ex in r["g"]]
            if not s_:
                continue
            x = np.array([net_ret(r, ex, b, 10_000.0) for r in s_])
            spy = np.array([spy_same_window(X, r, ex) for r in s_])
            ctl = control_draws(X, s_, ex, b, 10_000.0, seeds=30, evd=evd) or [float("nan")]
            cv = [c for c in ctl if not np.isnan(c)]
            pct = (np.mean([x.mean() > c for c in cv]) * 100) if cv else float("nan")
            exn = np.sort(x)[:-5].mean() if len(x) > 5 else float("nan")
            print(f"  @{b:>4}bp {sp:3s} n{len(x):4d} mean {x.mean()*1e4:+6.1f}bp ($ {x.mean()*1e4:+.0f}/10k) "
                  f"t{stat(x)['t']:+.2f} win {np.mean(x>0):.2f} ex-top5 {exn*1e4:+6.1f}bp | "
                  f"SPY same window {np.nanmean(spy)*1e4:+6.1f}bp | random-day control "
                  f"{np.nanmean(ctl)*1e4:+6.1f}bp (rule pct {pct:.0f})")
    return sel, rank


def cmd_port(X, sel, ex, rank=None, halal=None, seeds=10):
    res = {}
    for b in (6.0, 12.0):
        for S, N in ((10_000, 10), (10_000, 5), (25_000, 4), (50_000, 2)):
            for sp in ("Y1", "Y2", "OOS"):
                s_ = [r for r in sel if r["split"] == sp and (halal is None or r["sym"] in halal)]
                agg = []
                for sd in range(seeds):
                    tr, eq = portfolio(X, s_, ex, b, S, N, seed=sd, rank=rank)
                    p = np.array([t["pnl"] for t in tr])
                    if len(p) == 0:
                        agg.append((0, 0, 0, 0, 0, 0))
                        continue
                    ex5 = p.sum() - np.sort(p)[-5:].sum() if len(p) > 5 else float("nan")
                    agg.append((len(p), p.mean(), p.sum() / MONTHS[sp], (p > 0).mean(), maxdd(eq), ex5))
                a = np.array(agg, float)
                m = a.mean(0)
                res[(b, S, N, sp)] = m.tolist() + [a[:, 2].std()]
                print(f"  @{b:>4}bp ${S//1000}k x{N:2d} {sp:3s} trades {m[0]:5.0f} ({m[0]/MONTHS[sp]:5.1f}/mo) "
                      f"$/trade {m[1]:+7.1f}  $/month {m[2]:+8.0f} (sd {a[:, 2].std():5.0f})  win {m[3]:.2f}  "
                      f"maxDD {m[4]:+8.0f}  ex-top5 total {m[5]:+8.0f}")
    return res


def spy_bh(X):
    s = X.spy
    for sp, lo, hi in SPLITS:
        idx = [i for i, d in enumerate(X.dates) if lo <= d <= hi and i >= 61]
        r = X.c[idx[-1], s] / X.o[idx[0], s] - 1
        eq = X.c[idx, s] / X.o[idx[0], s] * 100_000
        print(f"  SPY buy&hold {sp}: {r*100:+.1f}% = ${r*100_000/MONTHS[sp]:+,.0f}/month on $100k, "
              f"maxDD ${maxdd(eq):+,.0f}")


def main():
    X = Data()
    rows = build_table(X)
    import os
    if os.environ.get("SE_UNI") == "t600":
        rows = [r for r in rows if r["t600"]]
        print("UNIVERSE: causal top-600 by prior-60 median $vol")
    if os.environ.get("SE_UNI") == "r15":
        rows = [r for r in rows if r["r15u"]]
        print("UNIVERSE: R15's own wide halal PIT universe (per-date membership)")
    print(f"events {len(X.ev)}; minute tapes {len(X.m1)}; rows {len(rows)}")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        cmd_grid(X, rows)
    elif cmd == "r15":
        cmd_r15ext(X, rows)
    elif cmd == "rule":
        entry, cond, ex = sys.argv[2], sys.argv[3], sys.argv[4]
        rk = sys.argv[5] if len(sys.argv) > 5 else None
        sel, rank = cmd_rule(X, rows, entry, cond, ex, rk)
        print(" portfolio, all names:")
        cmd_port(X, sel, ex, rank)
        print(" portfolio, halal-PASS only (data/halal_list.json = PRESENT-DAY list):")
        cmd_port(X, sel, ex, rank, halal=halal_syms(), seeds=3)
        spy_bh(X)


if __name__ == "__main__":
    main()
