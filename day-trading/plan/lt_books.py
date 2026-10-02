"""LEADS-TEST: re-score the live R15 and RL books with the hygiene stack.

Legs are the live-code parity replays (data/paper/parity/r15.json matched_list,
112 legs; rl.json live_trades, 87 legs, the live one-position $10k RTH config).
Bars: m1w -> m1 -> m1c via p3_lib.read_bars_csv (04:00-20:00 grid).

Per leg, at the decision minute t (R15: 09:35; RL: entry minute - 1):
  spread  = max(CS,AR)/2 on bars [t-29, t]            (<= 10 bps passes)
  dvol60  = cp_prior median $vol of prior 60 sessions (>= $5M passes)
  sigma1  = sd of 1-min log returns of printed closes 04:00..t, cp_feat
            definition (defined and <= 0.017 passes)
Variants (leg filter = skip and stay flat; R15 trades <= 1/day so this is the
rule's exact "skip the day"; for RL it is an approximation, the path could
re-enter later):
  own       the book's own exit (R15 10:36 open; RL its own rules)
  F         filters, own exit
  X         own entry, stack exit instead (5% close target -> next open,
            10% trail from highest high, bearish >= +1% -> next open, 15:00)
  FX        filters + stack exit
  O / FO    own exit OR stack exit, whichever comes first (overlay)
    python plan/lt_books.py
"""
import json
import sys
from pathlib import Path

import numpy as np

P = Path(__file__).resolve().parent
sys.path.insert(0, str(P))
import p3_lib as PL                                         # noqa: E402
import cp_prior as PR                                       # noqa: E402
import cp_cost as C                                         # noqa: E402
import cp_sim as S                                          # noqa: E402
import lt_lib as LL                                         # noqa: E402

ROOT = P.parent
M1030 = 10 * 60 + 30 - 240
M1500 = 15 * 60 - 240


class B:
    """minimal Day-like view for cp_sim._bearish / _prev_print."""

    def __init__(self, o, h, l, c, v):
        self.o = o[None, :]
        self.h = h[None, :]
        self.l = l[None, :]
        self.c = c[None, :]
        self.v = v[None, :]
        self.printed = ~np.isnan(self.c)


def bars(sym, date):
    for d in ("m1w", "m1", "m1c"):
        f = ROOT / f"data/massive/{d}/{sym}_{date}.csv"
        if f.exists():
            r = PL.read_bars_csv(f, date)
            if r is not None:
                return r
    return None


def half(b, m_end, win=30):
    o, h, l, c, v = b
    a, e = max(0, m_end - win + 1), m_end + 1
    sel = ~np.isnan(c[a:e])
    cs, ar = C._cs_ar(np.where(sel, o[a:e], np.nan), np.where(sel, h[a:e], np.nan),
                      np.where(sel, l[a:e], np.nan), np.where(sel, c[a:e], np.nan))
    vals = [x for x in (cs, ar) if x is not None and np.isfinite(x)]
    return max(max(vals) / 2.0, 1.0) if vals else 10.0


def sigma1(b, t):
    c = b[3][:t + 1]
    r = np.diff(np.log(c))
    ok = ~np.isnan(r)
    if ok.sum() <= 1:
        return np.nan
    return float(np.sqrt(np.mean(r[ok] ** 2)))


def stack_exit(b, em, entry, own_m=None, own_px=None):
    """first of (stack exit, own exit). own_m None = stack only."""
    o, h, l, c, v = b
    day = B(o, h, l, c, v)
    peak = h[em]
    pending = None
    end = M1500 if own_m is None else min(M1500, own_m)
    for m in range(em + 1, end + 1):
        if np.isnan(c[m]):
            continue
        if pending:
            return m, float(o[m]), pending
        if own_m is not None and m == own_m:
            return own_m, own_px, "own"
        lvl = peak * 0.9
        if l[m] <= lvl:
            return m, float(min(max(min(lvl, o[m]), l[m]), h[m])), "trail10"
        peak = max(peak, h[m])
        if c[m] >= entry * 1.05:
            pending = "target5"
        elif c[m] >= entry * 1.01 and S._bearish(day, 0, m):
            pending = "bearish"
    if own_m is not None and own_m <= M1500:
        return own_m, own_px, "own"
    if own_m is not None and own_m > M1500:
        # own exit later than 15:00 (RL flatten 15:59): overlay keeps own
        for m in range(M1500 + 1, own_m + 1):
            if np.isnan(c[m]):
                continue
            if pending:
                return m, float(o[m]), pending
        return own_m, own_px, "own"
    m = end
    while m > em and np.isnan(c[m]):
        m -= 1
    return m, float(c[m]), "flatten"


def leg_cost(b, em, xm, ret):
    he = half(b, em - 1)
    hx = half(b, xm - 1)
    ce = (0.5 * he + (4.4 if em < M1030 else 3.1))
    cx = (0.5 * hx + (4.4 if xm < M1030 else 3.1)) * (1 + ret)
    return 1e4 * (ret - (ce + cx) / 1e4), 1e4 * (ret - 12e-4 * (2 + ret))


def main():
    r15 = json.load(open(ROOT / "data/paper/parity/r15.json"))["matched_list"]
    rl = json.load(open(ROOT / "data/paper/parity/rl.json"))["live_trades"]
    books = {
        "R15": [dict(date=x["date"], sym=x["sym"], em=x["entry_min_live"],
                     ep=x["entry_live"], xm=x["exit_min_live"], xp=x["exit_live"],
                     t=9 * 60 + 35 - 240) for x in r15 if x["entry_min_live"] is not None],
        "RL": [dict(date=x["date"], sym=x["sym"], em=x["m_in"], ep=x["px_in"],
                    xm=x["m_out"], xp=x["px_out"], t=x["m_in"] - 1) for x in rl],
    }
    gdd = PR.gd_dates()
    out = {}
    for name, legs in books.items():
        ds = sorted({x["date"] for x in legs})
        lo, hi = ds[0], ds[-1]
        if name == "R15":
            span = [d for d in gdd if "2024-10-22" <= d <= hi]
        else:
            span = [d for d in gdd if lo <= d <= hi]
        nd = {sp: sum(1 for d in span if LL.split_of(d) == sp) for sp in ("Y1", "Y2", "OOS")}
        nd["ALL"] = len(span)
        rows = {k: [] for k in ("own", "F", "X", "FX", "O", "FO")}
        diag = []
        for x in legs:
            b = bars(x["sym"], x["date"])
            if b is None:
                continue
            pr = PR.load(x["date"]).get(x["sym"]) or {}
            dv = pr.get("dvol60") or 0
            hh = half(b, x["t"])
            sg = sigma1(b, x["t"])
            passF = (hh <= 10) and dv >= 5e6 and np.isfinite(sg) and sg <= 0.017
            diag.append(dict(sym=x["sym"], date=x["date"], half=hh, dv60=dv, sig=sg, passF=passF))
            em, ep = x["em"], x["ep"]
            variants = {
                "own": (x["xm"], x["xp"], "own"),
                "X": stack_exit(b, em, ep),
                "O": stack_exit(b, em, ep, x["xm"], x["xp"]),
            }
            for k, (xm, xp, why) in variants.items():
                ret = xp / ep - 1
                nc, n12 = leg_cost(b, em, min(xm, 959), ret)
                leg = dict(date=x["date"], sym=x["sym"], g=1e4 * ret, n_c=nc, n_12=n12, why=why)
                rows[k].append(leg)
                if passF:
                    rows["F" + ("" if k == "own" else k)].append(leg)
        out[name] = dict(nd=nd, rows=rows, diag=diag)
    (ROOT / "data/research_oct/lt_books.json").write_text(json.dumps(out, default=float))
    for name, o in out.items():
        print(f"\n## {name}  sessions {o['nd']}")
        print("| variant | split | n | gross $/tr | central $/tr | flat12 $/tr | tr/mo | $/mo central | $/mo flat12 | ex-top5 $/mo |")
        print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for k, L in o["rows"].items():
            s = LL.summ(L, o["nd"])
            for sp in ("ALL", "Y1", "Y2", "OOS"):
                print(LL.fmt_row(k, s, sp))
        npass = sum(d["passF"] for d in o["diag"])
        print(f"filters pass {npass}/{len(o['diag'])}; fail spread "
              f"{sum(d['half'] > 10 for d in o['diag'])}, dvol "
              f"{sum(d['dv60'] < 5e6 for d in o['diag'])}, sigma "
              f"{sum(not (np.isfinite(d['sig']) and d['sig'] <= .017) for d in o['diag'])}")


if __name__ == "__main__":
    main()
