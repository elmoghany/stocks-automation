"""OVERNIGHT research: shared evaluation helpers (portfolio sim, controls, stats)."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/research_oct"
SPLITS = {"Y1": ("2024-10-01", "2025-07-31"), "Y2": ("2025-08-01", "2026-07-31"),
          "OOS": ("2026-08-01", "2026-12-31")}
CAP = 100_000.0


def load():
    u = pd.read_parquet(OUT / "on_feat.parquet")
    return u[u.oh1.notna()].reset_index(drop=True)


def split_of(d):
    s = pd.Series("", index=d.index)
    for k, (a, b) in SPLITS.items():
        s[(d >= a) & (d <= b)] = k
    return s


def pick_top(u, score, n, seed=0, asc=False, mask=None):
    """Top-n rows per date by score; ties broken by seeded random (never pool order)."""
    rng = np.random.default_rng(seed)
    x = u[["date"]].copy()
    x["s"] = (score if not asc else -score).values
    x["tb"] = rng.random(len(x))
    if mask is not None:
        x = x[mask.values]
    x = x[np.isfinite(x.s)]
    x = x.sort_values(["date", "s", "tb"], ascending=[True, False, False])
    return x.groupby("date").head(n).index


def nightly(u, idx, col="oh1"):
    """Equal-weight nightly portfolio gross return per date."""
    return u.loc[idx].groupby("date")[col].mean()


def stats(r, bps, cap=CAP, legs=2.0):
    """r: gross per-night return series. cost bps/side, legs sides per night."""
    net = r - legs * bps / 1e4
    usd = net * cap
    if len(usd) == 0:
        return {}
    cum = usd.cumsum()
    dd = (cum - cum.cummax()).min()
    months = max(len(usd) / 21.0, 1e-9)
    srt = usd.sort_values(ascending=False)
    return {"nights": len(usd), "gross_bp": r.mean() * 1e4, "usd_night": usd.mean(),
            "usd_month": usd.sum() / months, "win": (usd > 0).mean(), "maxdd": dd,
            "t": usd.mean() / (usd.std(ddof=1) / np.sqrt(len(usd))) if len(usd) > 2 else np.nan,
            "exTop5_night": srt.iloc[5:].mean() if len(srt) > 5 else np.nan,
            "total": usd.sum()}


def by_split(r, bps, **kw):
    out = {}
    sp = split_of(pd.Series(r.index, index=r.index))
    for k in SPLITS:
        out[k] = stats(r[sp == k], bps, **kw)
    out["ALL"] = stats(r, bps, **kw)
    return out


def fmt(row):
    return (f"{row.get('nights',0):4d}n g={row.get('gross_bp',np.nan):6.1f}bp "
            f"${row.get('usd_night',np.nan):7.1f}/nt ${row.get('usd_month',np.nan):8.0f}/mo "
            f"win={row.get('win',np.nan):.2f} dd=${row.get('maxdd',np.nan):8.0f} "
            f"t={row.get('t',np.nan):5.2f} ex5=${row.get('exTop5_night',np.nan):6.1f}")
