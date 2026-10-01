"""LEGACY-2: coil as ENTRY TIMING. Reads plan/lm2_out/panel.npz.

Per (date, name), the row sequence over decision minutes is causal: a
rule may only use rows at or before the minute it acts on.
  NOW      -- enter at the name's first eligible decision minute
  RECLAIM  -- if first-eligible coil < LO, wait for the first later
              minute with coil >= HI (a fresh reclaim of the high)
  DIP      -- if first-eligible coil >= HI, wait for the first later
              minute with coil in [a, b) (buy the pullback)
Outcomes: r1500 (hold to 15:00) and r60, from the deferred fill.
"""
import numpy as np
import pandas as pd

import lm2_coil_analyze as A


def main():
    d = A.load()
    d = d.sort_values(["date", "i", "t"])
    g = d.groupby(["date", "i"], sort=False)
    first = g.head(1).copy()
    print("names", len(first))
    first["cb"] = pd.cut(first["coil"], A.COILB, labels=A.COILL, right=False)
    print("\n### first-eligible minute, by coil bucket (r1500 / r60)")
    for col in ["r1500", "r60"]:
        for yr in ["Y1", "Y2", "OOS"]:
            x = first[first["yr"] == yr]
            print(f" {col} {yr}: " + " | ".join(
                f"{c}:{A.dmean(x[x['cb'] == c], col)[0]*1e4:+5.0f}"
                f"(n{(x['cb'] == c).sum()})" for c in A.COILL))

    def rule(lo_first, hi_first, lo_wait, hi_wait, label, maxwait=120):
        out = []
        for (dt, i), gg in g:
            c0 = gg["coil"].iloc[0]
            if not (lo_first <= c0 < hi_first):
                continue
            t0 = gg["t"].iloc[0]
            later = gg[(gg["t"] > t0) & (gg["t"] <= t0 + maxwait)]
            hit = later[(later["coil"] >= lo_wait) & (later["coil"] < hi_wait)]
            now = gg.iloc[0]
            w = hit.iloc[0] if len(hit) else None
            out.append(dict(date=dt, yr=now["yr"], now15=now["r1500"],
                            now60=now["r60"],
                            wait15=np.nan if w is None else w["r1500"],
                            wait60=np.nan if w is None else w["r60"],
                            filled=w is not None,
                            wait_min=np.nan if w is None else w["t"] - t0))
        o = pd.DataFrame(out)
        print(f"\n### {label}: names {len(o)}, wait condition met "
              f"{o['filled'].mean():.2%}, median wait "
              f"{o['wait_min'].median():.0f} min")
        for yr in ["Y1", "Y2", "OOS"]:
            x = o[o["yr"] == yr]
            xf = x[x["filled"]]
            r = [A.dmean(x, "now15"), A.dmean(xf, "now15"),
                 A.dmean(xf, "wait15"), A.dmean(x[~x["filled"]], "now15"),
                 A.dmean(x, "now60"), A.dmean(xf, "wait60")]
            print(f"  {yr}: NOW all {r[0][0]*1e4:+5.0f}(t{r[0][1]:+.1f},n{len(x)})"
                  f" | NOW on met {r[1][0]*1e4:+5.0f} | WAIT {r[2][0]*1e4:+5.0f}"
                  f"(t{r[2][1]:+.1f},n{len(xf)}) | NOW never-met "
                  f"{r[3][0]*1e4:+5.0f} || r60 NOW {r[4][0]*1e4:+5.0f} "
                  f"WAIT {r[5][0]*1e4:+5.0f}")

    rule(0.0, 0.90, 0.97, 9, "RECLAIM: first coil<.90, wait coil>=.97")
    rule(0.0, 0.90, 0.99, 9, "RECLAIM: first coil<.90, wait coil>=.99")
    rule(0.90, 0.97, 0.99, 9, "RECLAIM: first coil .90-.97, wait coil>=.99")
    rule(0.97, 9, 0.90, 0.95, "DIP: first coil>=.97, wait coil .90-.95")
    rule(0.97, 9, 0.80, 0.90, "DIP: first coil>=.97, wait coil .80-.90")
    rule(0.97, 9, 0.995, 9, "CONFIRM: first coil>=.97, wait new coil>=.995 later")


if __name__ == "__main__":
    main()
