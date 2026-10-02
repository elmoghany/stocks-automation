"""OVERNIGHT research: markdown tables for the chosen rule (rev5_lo) + controls.
Costs 2 (auction-optimistic, labelled), 6 (central), 12 (stress) bps/side.
Capital: loose = $100k every night; strict settled cash = $50k every night
(two alternating $50k sleeves; a sale at the 09:30 open settles T+1).
"""
import json
import sys

import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from on_lib import ROOT, by_split, load, nightly, pick_top  # noqa: E402


def row(lab, r, b, cap):
    out = []
    for k, v in by_split(r, b, cap=cap).items():
        out.append(f"| {lab} | {b} | {k} | {v['nights']} | {v['gross_bp']:.1f} | {v['usd_night']:+.0f} | "
                   f"{v['usd_month']:+,.0f} | {v['win']:.0%} | {v['maxdd']:,.0f} | {v['exTop5_night']:+.0f} | {v['t']:.2f} |")
    return out


def main():
    u = load()
    hal = set(json.loads((ROOT / "data/halal_list.json").read_text())["symbols"])
    hdr = ("| rule | bps/side | split | nights | gross bp/night | $/night | $/month | win | max DD $ | "
           "ex-top-5 $/night | t |\n|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    print("## loose capital ($100k every night)\n" + hdr)
    lines = []
    spy = u.groupby("date").spy_on1.first().dropna()
    for b in (6, 12):
        lines += row("SPY close->open", spy, b, 1e5)
    for n in (5, 10, 20):
        r = nightly(u, pick_top(u, -u.rev5, n, seed=11))
        for b in (2, 6, 12):
            lines += row(f"rev5_lo N={n}", r, b, 1e5)
    rh = nightly(u, pick_top(u, -u.rev5, 20, seed=11, mask=u.sym.isin(hal)))
    for b in (6, 12):
        lines += row("rev5_lo N=20 HALAL-PASS only (present-day list 2026-09-17, look-ahead)", rh, b, 1e5)
    print("\n".join(lines))
    print("\n## strict settled cash ($50k every night)\n" + hdr)
    r = nightly(u, pick_top(u, -u.rev5, 20, seed=11))
    out = []
    for b in (2, 6, 12):
        out += row("rev5_lo N=20 strict", r, b, 5e4)
    print("\n".join(out))
    # worst nights / tail
    usd = (r - 12e-4) * 1e5
    print("\nworst 5 nights @6bps:", usd.nsmallest(5).round(0).to_dict())
    print("best 5 nights @6bps:", usd.nlargest(5).round(0).to_dict())
    print("night std $", round(usd.std(), 0), "ann. Sharpe", round(usd.mean() / usd.std() * 252 ** .5, 2))
    m = (r.groupby(r.index.to_period("M")).sum() - 12e-4 * r.groupby(r.index.to_period("M")).size()) * 1e5
    print("months positive @6bps:", int((m > 0).sum()), "/", len(m))
    print(m.round(0).to_string())


if __name__ == "__main__":
    main()
