"""OVERNIGHT research (2026-10-01): build the point-in-time daily panel.

Input : data/massive/gd/*.json.gz (Polygon grouped daily, every ticker that
        printed that day -- delisted names included, nothing present-day).
        /v3/reference/tickers type=CS|ADRC, active true AND false (so delisted
        common stocks are kept) -> used only to drop ETFs/warrants/units/prefs.
Output: data/research_oct/on_gd_panel.parquet  (date, sym, o,h,l,c,v,vw,n)
        data/research_oct/on_ref_types.json     {sym: type}
No feature here looks at anything; this is raw data only.
"""
import gzip
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))
GD = ROOT / "data/massive/gd"
OUT = ROOT / "data/research_oct"
OUT.mkdir(parents=True, exist_ok=True)


def ref_types():
    f = OUT / "on_ref_types.json"
    if f.exists():
        return json.loads(f.read_text())
    from shared import massive
    massive._TH_INTERVAL = 0.0
    out = {}
    for typ in ("CS", "ADRC"):
        for act in ("true", "false"):
            u = (f"{massive.BASE}/v3/reference/tickers?market=stocks&type={typ}"
                 f"&active={act}&limit=1000")
            while u:
                d = massive._get(u + f"&apiKey={massive._key()}")
                for r in d.get("results") or []:
                    out.setdefault(r["ticker"], typ)
                u = d.get("next_url")
            print(typ, act, len(out), flush=True)
    f.write_text(json.dumps(out))
    return out


def main():
    types = ref_types()
    rows = []
    for p in sorted(GD.glob("*.json.gz")):
        D = p.name[:10]
        for r in json.load(gzip.open(p)):
            if r.get("T") in types:
                rows.append((D, r["T"], r.get("o"), r.get("h"), r.get("l"),
                             r.get("c"), r.get("v"), r.get("vw"), r.get("n")))
    df = pd.DataFrame(rows, columns="date sym o h l c v vw n".split())
    df["date"] = pd.to_datetime(df["date"])
    df.to_parquet(OUT / "on_gd_panel.parquet")
    print(df.shape, df.date.min(), df.date.max(), df.sym.nunique())


if __name__ == "__main__":
    main()
