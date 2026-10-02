"""OVERNIGHT research: execution-timing + 15:55-causality checks on the m1w
(causal wide halal, 191 names) minute cache.

1) Entry: official close (gd c, the MOC price) vs the last price at 15:55
   (p1555). Reports the 15:55->close drift overall and for reversal picks.
2) Exit: official open (gd o) vs 09:31 open, 09:35 and 09:45 closes.
3) CLS-feature causality: rank today's loser by dret at the CLOSE (screen,
   5-min look-ahead) vs by dret at 15:55 (causal); compare picks/returns.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from on_lib import OUT, split_of  # noqa: E402


def main():
    px = pd.read_parquet(OUT / "on_m1w_px.parquet")
    f = pd.read_parquet(OUT / "on_feat.parquet")
    gd = pd.read_parquet(OUT / "on_gd_panel.parquet")[["date", "sym", "o", "c"]]
    gd = gd.sort_values(["sym", "date"])
    gd["ndate"] = gd.groupby("sym").date.shift(-1)
    gd["no"] = gd.groupby("sym").o.shift(-1)
    m = px.merge(gd, on=["sym", "date"], how="inner")
    nx = px.rename(columns={c: "n_" + c for c in px.columns if c not in ("sym",)})
    nx = nx.rename(columns={"n_date": "ndate"})
    m = m.merge(nx[["sym", "ndate", "n_o930", "n_o931", "n_c934", "n_c944"]], on=["sym", "ndate"], how="inner")
    m = m.merge(f[["sym", "date", "rev5", "pc", "vol20", "dret"]], on=["sym", "date"], how="inner")
    m = m[(m.p1555 > 0) & (m.c > 0) & (m.no > 0)]
    # split-adjustment mismatches between the minute cache and gd (~0.5% of rows): drop
    ok = ((m.c / m.c1559 - 1).abs() < 0.05) & ((m.no / m.n_o930 - 1).abs() < 0.05)
    print("dropped (cache/gd adjustment mismatch):", int((~ok).sum()))
    m = m[ok]
    m["drift_1555_close"] = m.c / m.p1555 - 1
    m["on_close_open"] = m.no / m.c - 1
    m["on_1555_open"] = m.no / m.p1555 - 1
    for k in ("n_o931", "n_c934", "n_c944"):
        m[f"on_close_{k}"] = m[k] / m.c - 1
    m["sp"] = split_of(m.date)
    print("rows", len(m), "dates", m.date.nunique(), "names/day", round(m.groupby("date").size().median()))
    bp = lambda s: round(s.mean() * 1e4, 2)  # noqa: E731
    print("\n[1/2] all m1w names, mean bp:")
    cols = ["drift_1555_close", "on_close_open", "on_1555_open", "on_close_n_o931", "on_close_n_c934", "on_close_n_c944"]
    print(m.groupby("sp")[cols].mean().mul(1e4).round(2).to_string())
    print("gd o vs 09:30 bar open |diff| median bp:", bp((m.no / m.n_o930 - 1).abs()))
    # reversal picks inside m1w: bottom 5 rev5 per date
    rng = np.random.default_rng(3)
    m["tb"] = rng.random(len(m))
    for lab, key in (("rev5_lo", "rev5"), ("dret_lo@close", "dret")):
        p = m.sort_values(["date", key, "tb"]).groupby("date").head(5)
        print(f"\n[1/2] {lab} N=5 within m1w, mean bp:")
        print(p.groupby("sp")[cols].mean().mul(1e4).round(2).to_string())
    # [3] causal dret at 15:55
    m["dret1555"] = m.p1555 / m.pc - 1
    a = m.sort_values(["date", "dret", "tb"]).groupby("date").head(5)
    b = m.sort_values(["date", "dret1555", "tb"]).groupby("date").head(5)
    ov = pd.merge(a[["date", "sym"]], b[["date", "sym"]], on=["date", "sym"]).shape[0] / len(a)
    print(f"\n[3] dret_lo N=5: pick overlap close-ranked vs 15:55-ranked = {ov:.3f}")
    for lab, p, col in (("close-ranked, buy close", a, "on_close_open"),
                        ("15:55-ranked, buy close (MOC)", b, "on_close_open"),
                        ("15:55-ranked, buy 15:55", b, "on_1555_open")):
        print(f"   {lab:32s}", p.groupby("sp")[col].mean().mul(1e4).round(2).to_dict(),
              "ALL", bp(p[col]))
    print("   universe m1w eq-wt close->open", m.groupby("sp").on_close_open.mean().mul(1e4).round(2).to_dict())


if __name__ == "__main__":
    main()
