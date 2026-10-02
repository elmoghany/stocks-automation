"""LEADS-TEST lead 3 tables from data/research_oct/lt_lead3_events.json.
    python plan/lt_lead3_report.py"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lt_lib as LL                                         # noqa: E402
import cp_lib as L                                          # noqa: E402

ROOT = LL.ROOT
EV = json.loads((ROOT / "data/research_oct/lt_lead3_events.json").read_text())
import lt_lead3 as X                                        # noqa: E402
for _e in EV:      # recompute mcap with the present-scaled fallback
    _e["mcap"], _e["mcap_ok"], _e["sh_src"] = X.mcap_check(_e["sym"], _e["date"], _e["pc"])
DATES = L.panel_dates()
CEN = sorted({e["date"] for e in EV if e["census"]})
HAL = L.halal_set()
rng = np.random.default_rng(3)


def nd(dates):
    o = {sp: sum(1 for d in dates if LL.split_of(d) == sp) for sp in ("Y1", "Y2", "OOS")}
    o["ALL"] = len(dates)
    return o


def legs(rows, ex="x1000"):
    out = []
    for r in rows:
        ret = r.get(ex)
        if ret is None:
            continue
        hx = r.get("h_x", r["h_e"])
        cen = (0.5 * r["h_e"] + 4.4) + (0.5 * hx + 4.4) * (1 + ret)
        out.append(dict(date=r["date"], sym=r["sym"], g=1e4 * ret,
                        n_c=1e4 * ret - cen, n_12=1e4 * ret - 12 * (2 + ret),
                        n_25=1e4 * ret - 25 - 12 * (1 + ret)))
    return out


def base(r):
    return (not r["early"]) and r["pool_ok"] and r.get("em") is not None


import os
SRC = os.environ.get("LT_SRC") or None   # None = any source; "pit" = PIT shares only


def big(r):
    return (r["mcap_ok"] == "ok" and r["mcap"] is not None and r["mcap"] >= 2e9
            and (SRC is None or r["sh_src"] == SRC))


def line(name, rows, ndd, ex="x1000"):
    Lg = legs(rows, ex)
    s = LL.summ(Lg, ndd)
    for sp in ("Y1", "Y2", "OOS", "ALL"):
        x = s[sp]
        if not x.get("n"):
            continue
        v = np.array([y["n_c"] for y in Lg if sp == "ALL" or LL.split_of(y["date"]) == sp])
        g = np.array([y["g"] for y in Lg if sp == "ALL" or LL.split_of(y["date"]) == sp])
        t = g.mean() / (g.std(ddof=1) / np.sqrt(len(g))) if len(g) > 2 else np.nan
        n25 = np.mean([y["n_25"] for y in Lg if sp == "ALL" or LL.split_of(y["date"]) == sp])
        print(LL.fmt_row(name, s, sp) + f" t(gross) {t:+.2f}; median {np.median(g):+.0f}; PM-25bps {n25:+.1f}")
    return Lg


def hdr():
    print("| line | split | n | gross $/tr | central $/tr | flat12 $/tr | tr/mo | $/mo central | $/mo flat12 | ex-top5 $/mo | notes |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")


def main():
    pm = [r for r in EV if base(r)]
    print(f"events (first premarket +10% close 07:00-09:29, pool hygiene ok): {len(pm)}; "
          f"census dates {len(CEN)}: {CEN}")
    from collections import Counter
    print("mcap status, all post-07:00 crossers:", Counter(r["mcap_ok"] for r in pm))
    print("mcap status, census:", Counter(r["mcap_ok"] for r in pm if r["census"]))
    print("shares source among mcap>=2B ok:", Counter(r["sh_src"] for r in pm if big(r)))
    amb = [r for r in pm if r["mcap_ok"] == "split-ambiguous"]
    print("split-ambiguous rejected (sample):", [(r["date"], r["sym"], round((r["mcap"] or 0) / 1e9, 1)) for r in amb[:12]])
    print("largest mcaps accepted:", sorted([(round(r["mcap"] / 1e9, 1), r["sym"], r["date"]) for r in pm if big(r)])[-8:])

    print("\n## 1. HONEST: census dates (whole market, never-confirmers included)\n")
    hdr()
    cen = [r for r in pm if r["census"]]
    ndc = nd(CEN)
    for lab, f in (("all post-07:00 crossers", lambda r: True),
                   ("mcap>=2B (split-safe)", big),
                   ("mcap>=2B & dv60>=5M", lambda r: big(r) and r["dv60"] >= 5e6),
                   ("mcap>=2B & dv60>=5M & spread<=10", lambda r: big(r) and r["dv60"] >= 5e6 and r["half"] <= 10),
                   ("... & sigma1<=0.017 (full stack)", lambda r: big(r) and r["dv60"] >= 5e6 and r["half"] <= 10
                    and np.isfinite(r["sig"]) and r["sig"] <= 0.017)):
        rows = [r for r in cen if f(r)]
        npm = sum(1 for r in rows if not r["rth_confirm"])
        print(f"\n**{lab}** — n={len(rows)}, never confirm in RTH: {npm}; names: "
              + ", ".join(sorted({r['sym'] for r in rows}))[:400])
        hdr()
        for ex in ("x0930", "x1000", "x1030", "xstack"):
            line(f"{lab} -> {ex}", rows, ndc, ex)

    print("\n## 2. PANEL (all 466 dates; survivors only = names whose RTH high reached +10%)\n")
    pan = [r for r in pm if r["inpool"]]
    ndp = nd(DATES)
    for lab, f in (("mcap>=2B (split-safe)", big),
                   ("mcap>=2B & dv60>=5M", lambda r: big(r) and r["dv60"] >= 5e6),
                   ("mcap>=2B & dv60>=5M & spread<=10", lambda r: big(r) and r["dv60"] >= 5e6 and r["half"] <= 10),
                   ("full stack", lambda r: big(r) and r["dv60"] >= 5e6 and r["half"] <= 10
                    and np.isfinite(r["sig"]) and r["sig"] <= 0.017)):
        rows = [r for r in pan if f(r)]
        print(f"\n**PANEL {lab}** n={len(rows)}")
        hdr()
        for ex in ("x1000",):
            line(f"PANEL {lab} -> {ex}", rows, ndp, ex)
    print("\n## 3. Survivorship bias on the census days (same days, panel subset vs whole market), gross $/tr at 10:00\n")
    for lab, f in (("all", lambda r: True), ("mcap>=2B", big), ("mcap>=2B & dv60>=5M", lambda r: big(r) and r["dv60"] >= 5e6)):
        a = [1e4 * r["x1000"] for r in cen if f(r) and r.get("x1000") is not None]
        b = [1e4 * r["x1000"] for r in cen if f(r) and r["inpool"] and r.get("x1000") is not None]
        print(f"{lab:22s} whole-market n {len(a):4d} mean {np.mean(a) if a else np.nan:+7.1f} | panel-subset n {len(b):4d} "
              f"mean {np.mean(b) if b else np.nan:+7.1f} | bias {np.mean(b) - np.mean(a) if a and b else np.nan:+7.1f}")
    print("\n## 4. Halal-PASS only (present-day list), panel mcap>=2B & dv60>=5M, 10:00 exit\n")
    rows = [r for r in pan if big(r) and r["dv60"] >= 5e6 and r["sym"] in HAL]
    hdr()
    line("halal-PASS panel", rows, ndp)
    print("\n## 5. Per-event list, census mcap>=2B\n")
    for r in sorted([r for r in cen if big(r)], key=lambda r: (r["date"], r["t"])):
        print(r["date"], r["sym"], f"mcap {r['mcap']/1e9:.1f}B dv60 {r['dv60']/1e6:.0f}M cross {L.GRID_START//60 + (r['t'])//60:02d}:{r['t']%60:02d} "
              f"half {r['half']:.1f} sig {r['sig']:.4f} ->10:00 {1e4*(r['x1000'] or 0):+.0f} bps rth_confirm {r['rth_confirm']} pool {r['inpool']}")


if __name__ == "__main__":
    main()
