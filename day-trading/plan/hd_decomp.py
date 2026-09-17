"""HARNESS-DIAGNOSTIC control 1 + 2: overnight vs intraday, and buy-and-hold.

CONTROL 1 -- the known positive.  Lou, Polk & Skouras (2019, JFE, "A tug of
war: overnight versus intraday expected returns") and a long replication line
find that essentially ALL of the US equity return accrues close->open, while
open->close is flat or negative.  If our data and cost stack can see money
when money is there, this must show up here, with the right sign, on the same
names, over the same window.  It is measured, NOT adopted: the user's rule is
same-day, so the overnight leg is OUTSIDE the frame and is reported only as
the scale of what the frame is giving up.

CONTROL 2 -- buy-and-hold of the same universe over a window in which the
market rose.  If that is not positive the data or the universe is broken and
no other number here means anything.

CAUSALITY.  Universe membership for the pair (D-1, D) is read at D-1 -- the
day the overnight ticket is bought -- so nothing about D enters the choice.
gd rows are split-adjusted but NOT dividend-adjusted, which biases the
overnight leg DOWN by roughly the dividend yield; that is conservative for
the claim being made.

Usage:  python plan/hd_decomp.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_lib as H                                            # noqa: E402

MAXR = 0.5                    # sanity clip on a one-session return
UNIVERSES = ["halal_strict", "halal_wide", "liquid"]
ETFS = ["SPY", "SPUS", "HLAL", "SPSK", "SPRE", "UMMA", "SPWO"]


def year_of(d):
    return ("Y1", "Y2", "aug2026")[H.split_of(d)]


def series_stats(dates, vals, label):
    v = np.asarray(vals, float)
    ok = np.isfinite(v)
    d = [x for x, k in zip(dates, ok) if k]
    v = v[ok]
    out = {"label": label, "n_days": int(v.size),
           "mean_bp": round(float(v.mean()) * 1e4, 3),
           "median_bp": round(float(np.median(v)) * 1e4, 3),
           "sd_bp": round(float(v.std(ddof=1)) * 1e4, 2) if v.size > 2 else 0.0,
           "t": round(H.tstat(v), 2), "t_nw": round(H.nw_tstat(v), 2),
           "cum_pct": round(float(np.expm1(np.log1p(v).sum())) * 100, 2),
           "frac_pos": round(float((v > 0).mean()), 4)}
    for y in ("Y1", "Y2", "aug2026"):
        m = np.array([year_of(x) == y for x in d])
        if m.sum() > 2:
            out[y] = {"n": int(m.sum()),
                      "mean_bp": round(float(v[m].mean()) * 1e4, 3),
                      "t": round(H.tstat(v[m]), 2),
                      "cum_pct": round(float(np.expm1(np.log1p(v[m]).sum()))
                                       * 100, 2)}
    return out


def decompose(dates, O, C, sidx, mem, kind, hold=1):
    """Equal-weight overnight / intraday / close-close daily series.

    overnight(t) = O[t] / C[t-hold] - 1 on names eligible at t-hold
    intraday(t)  = C[t] / O[t]     - 1 on names eligible at t-1
    """
    on, intr, cc, nn, on_tk = [], [], [], [], []
    used = []
    for t in range(hold, len(dates)):
        d0, d1 = dates[t - hold], dates[t]
        names = mem.get(d0, set())
        if not names:
            continue
        j = np.array([sidx[s] for s in names if s in sidx], int)
        if j.size == 0:
            continue
        c0, o1, c1 = C[t - hold, j], O[t, j], C[t, j]
        r_on = o1 / c0 - 1.0
        r_in = c1 / o1 - 1.0
        r_cc = c1 / c0 - 1.0
        good = (np.isfinite(r_on) & np.isfinite(r_in) & np.isfinite(r_cc)
                & (np.abs(r_on) < MAXR * hold) & (np.abs(r_in) < MAXR)
                & (c0 > 0) & (o1 > 0) & (c1 > 0))
        if good.sum() < 5:
            continue
        used.append(d1)
        nn.append(int(good.sum()))
        on.append(float(r_on[good].mean()))
        intr.append(float(r_in[good].mean()))
        cc.append(float(r_cc[good].mean()))
        on_tk.append(float(np.mean([H.ticket_pnl(x, H.FEE_BPS)
                                    for x in r_on[good]])))
    return used, np.array(on), np.array(intr), np.array(cc), np.array(nn), \
        np.array(on_tk)


def dollar_row(used, r_on_daily, tickets_per_month=H.TICKETS_PER_MONTH):
    """$/ticket and $/month for a $15k overnight ticket at flat 10 bps/side."""
    net = np.array([H.ticket_pnl(x, H.FEE_BPS) for x in r_on_daily])
    gross = np.array([H.ticket_pnl(x, 0.0) for x in r_on_daily])
    half = np.array([H.ticket_pnl(x, 2.77) for x in r_on_daily])
    return {"n": int(net.size),
            "gross_per_ticket": round(float(gross.mean()), 2),
            "net10_per_ticket": round(float(net.mean()), 2),
            "net277_per_ticket": round(float(half.mean()), 2),
            "net10_per_month": round(float(net.mean()) * tickets_per_month, 2),
            "net277_per_month": round(float(half.mean()) * tickets_per_month,
                                      2),
            "gross_per_month": round(float(gross.mean()) * tickets_per_month,
                                     2),
            "t": round(H.tstat(net), 2)}


def main():
    dates = H.study_dates()
    print(f"[decomp] {len(dates)} study dates {dates[0]}..{dates[-1]}",
          flush=True)
    syms, O, C, V = H.gd_matrix(dates)
    sidx = {s: i for i, s in enumerate(syms)}
    print(f"[decomp] gd matrix {O.shape}", flush=True)

    res = {"dates": [dates[0], dates[-1]], "n_dates": len(dates),
           "universes": {}, "etfs": {}, "buy_and_hold": {}, "holds": {}}

    for kind in UNIVERSES:
        mem = H.members(kind, dates)
        sizes = [len(mem[d]) for d in dates]
        used, on, intr, cc, nn, on_tk = decompose(dates, O, C, sidx, mem, kind)
        r = {"universe": kind,
             "names_per_day": {"min": int(min(sizes)), "max": int(max(sizes)),
                               "median": int(np.median(sizes))},
             "names_used_median": int(np.median(nn)),
             "overnight": series_stats(used, on, f"{kind}/overnight"),
             "intraday": series_stats(used, intr, f"{kind}/intraday"),
             "close_close": series_stats(used, cc, f"{kind}/close-close"),
             "overnight_ticket": dollar_row(used, on),
             "intraday_ticket": dollar_row(used, intr)}
        res["universes"][kind] = r
        print(f"[decomp] {kind:13s} overnight {r['overnight']['mean_bp']:+8.2f} bp"
              f" t={r['overnight']['t']:+6.2f} cum {r['overnight']['cum_pct']:+9.1f}%"
              f" | intraday {r['intraday']['mean_bp']:+8.2f} bp"
              f" t={r['intraday']['t']:+6.2f} cum {r['intraday']['cum_pct']:+9.1f}%",
              flush=True)

    # multi-day overnight-inclusive holds on the strict-halal universe
    mem = H.members("halal_strict", dates)
    for hold in (1, 3, 5):
        used, on, intr, cc, nn, _ = decompose(dates, O, C, sidx, mem,
                                              "halal_strict", hold=hold)
        # close(t-hold) -> open(t) is the "hold `hold` sessions, sell at the
        # open" ticket; it spans `hold` overnights and `hold-1` full days
        res["holds"][f"{hold}d"] = {
            "close_to_open": series_stats(used, on, f"hold{hold}/close->open"),
            "ticket": dollar_row(used, on),
            "close_to_close": series_stats(used, cc, f"hold{hold}/close->close"),
            "ticket_cc": dollar_row(used, cc)}
        print(f"[decomp] hold {hold}d close->open "
              f"{res['holds'][f'{hold}d']['close_to_open']['mean_bp']:+8.2f} bp "
              f"${res['holds'][f'{hold}d']['ticket']['net10_per_ticket']:+8.2f}/tkt",
              flush=True)

    # ------------------------------------------------------------------ ETFs
    for s in ETFS:
        j = sidx.get(s)
        if j is None:
            res["etfs"][s] = {"missing": True}
            continue
        o, c = O[:, j], C[:, j]
        on = o[1:] / c[:-1] - 1.0
        intr = c / o - 1.0
        cc = c[1:] / c[:-1] - 1.0
        ok = np.isfinite(on) & np.isfinite(intr[1:]) & (np.abs(on) < MAXR)
        dd = [d for d, k in zip(dates[1:], ok) if k]
        res["etfs"][s] = {
            "overnight": series_stats(dd, on[ok], f"{s}/overnight"),
            "intraday": series_stats(dd, intr[1:][ok], f"{s}/intraday"),
            "close_close": series_stats(dd, cc[ok], f"{s}/close-close"),
            "overnight_ticket": dollar_row(dd, on[ok]),
            "intraday_ticket": dollar_row(dd, intr[1:][ok]),
            "buy_hold_pct": round(float(c[np.isfinite(c)][-1]
                                        / c[np.isfinite(c)][0] - 1) * 100, 2)}
        print(f"[decomp] {s:5s} overnight {res['etfs'][s]['overnight']['mean_bp']:+7.2f} bp"
              f" t={res['etfs'][s]['overnight']['t']:+6.2f}"
              f" | intraday {res['etfs'][s]['intraday']['mean_bp']:+7.2f} bp"
              f" t={res['etfs'][s]['intraday']['t']:+6.2f}"
              f" | B&H {res['etfs'][s]['buy_hold_pct']:+7.2f}%", flush=True)

    # ------------------------------------------------------- CONTROL 2: B&H
    nmon = len(dates) / H.DAYS_PER_MONTH
    for kind in UNIVERSES:
        mem = H.members(kind, dates)
        rets = []
        used = []
        for t in range(1, len(dates)):
            names = mem.get(dates[t - 1], set())
            j = np.array([sidx[s] for s in names if s in sidx], int)
            if j.size == 0:
                continue
            r = C[t, j] / C[t - 1, j] - 1.0
            g = np.isfinite(r) & (np.abs(r) < MAXR)
            if g.sum() < 5:
                continue
            rets.append(float(r[g].mean()))
            used.append(dates[t])
        rets = np.array(rets)
        eq = 100000.0 * np.cumprod(1.0 + rets)
        res["buy_and_hold"][kind] = {
            "n_days": int(rets.size),
            "final_on_100k": round(float(eq[-1]), 2),
            "total_pnl": round(float(eq[-1] - 100000.0), 2),
            "per_month": round(float(eq[-1] - 100000.0) / nmon, 2),
            "ann_pct": round((float(eq[-1] / 100000.0) ** (252.0 / rets.size)
                              - 1.0) * 100, 2),
            "max_dd_pct": round(float(np.min(eq / np.maximum.accumulate(eq))
                                      - 1.0) * 100, 2),
            "daily": series_stats(used, rets, f"{kind}/EW-daily")}
        b = res["buy_and_hold"][kind]
        print(f"[decomp] B&H {kind:13s} ${b['total_pnl']:+12,.0f} on $100k"
              f"  = ${b['per_month']:+9,.0f}/month  ({b['ann_pct']:+.2f}%/yr)",
              flush=True)
    for s in ("SPY", "SPUS", "HLAL"):
        j = sidx.get(s)
        if j is None:
            continue
        c = C[:, j]
        c = c[np.isfinite(c)]
        res["buy_and_hold"][s] = {
            "n_days": int(c.size),
            "total_pnl": round(float(100000.0 * (c[-1] / c[0] - 1)), 2),
            "per_month": round(float(100000.0 * (c[-1] / c[0] - 1)) / nmon, 2),
            "ann_pct": round((float(c[-1] / c[0]) ** (252.0 / c.size) - 1.0)
                             * 100, 2)}
        b = res["buy_and_hold"][s]
        print(f"[decomp] B&H {s:13s} ${b['total_pnl']:+12,.0f} on $100k"
              f"  = ${b['per_month']:+9,.0f}/month  ({b['ann_pct']:+.2f}%/yr)",
              flush=True)

    p = H.write("decomp.json", res)
    print(f"[decomp] wrote {p}", flush=True)


if __name__ == "__main__":
    main()
