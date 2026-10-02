"""OVERNIGHT research: intraday-at-15:55 validation on the causal wide halal
minute cache (data/massive/m1w, 191 names, point-in-time membership, 04:00-20:00).

Per (sym, D) extracts, from bars strictly BEFORE 15:55 ET (i.e. begins_at <= 15:54):
  p1555  = close of the 15:54 bar (last price known at 15:55)
  p1455  = close of the 14:54 bar
  o930   = open of the 09:30 bar
  hi/lo  = RTH high/low 09:30..15:54, vol1555 = RTH volume 09:30..15:54
and for the exit morning: open of 09:30, 09:31, closes at 09:35/09:45 bars (09:34/09:44 close).
Also the 15:59 close (last RTH minute) for entry-at-close comparison.
Output: data/research_oct/on_m1w_px.parquet
"""
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
M1W = ROOT / "data/massive/m1w"
OUT = ROOT / "data/research_oct"
ET, UTC = ZoneInfo("America/New_York"), ZoneInfo("UTC")


def utc_key(date, hh, mm):
    y, m, d = map(int, date.split("-"))
    t = datetime(y, m, d, hh, mm, tzinfo=ET).astimezone(UTC)
    return t.strftime("%Y-%m-%d %H:%M")


def parse(path, date):
    k = {n: utc_key(date, h, m) for n, (h, m) in {
        "930": (9, 30), "931": (9, 31), "934": (9, 34), "944": (9, 44), "1454": (14, 54),
        "1554": (15, 54), "1559": (15, 59), "1600": (16, 0)}.items()}
    r = {}
    hi, lo, vol = -1e18, 1e18, 0.0
    with open(path) as f:
        first = f.readline()
        if first.startswith("EMPTY"):
            return None
        for line in f:
            ts = line[:16]
            if ts < k["930"] or ts >= k["1600"]:
                continue
            p = line.split(",")
            o, h, l, c, v = float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[5])
            if ts == k["930"]:
                r["o930"] = o
            if ts <= k["931"] and "o931" not in r and ts >= k["931"]:
                r["o931"] = o
            if ts <= k["934"]:
                r["c934"] = c
            if ts <= k["944"]:
                r["c944"] = c
            if ts <= k["1454"]:
                r["p1455"] = c
            if ts <= k["1554"]:
                r["p1555"] = c
                hi, lo, vol = max(hi, h), min(lo, l), vol + v
            r["c1559"] = c
    if not r:
        return None
    r["hi1555"], r["lo1555"], r["vol1555"] = hi, lo, vol
    return r


def main():
    rows = []
    names = sorted(e.name for e in os.scandir(M1W) if e.name.endswith(".csv"))
    for i, n in enumerate(names):
        sym, date = n[:-4].rsplit("_", 1)
        r = parse(M1W / n, date)
        if r:
            rows.append({"sym": sym, "date": pd.Timestamp(date), **r})
        if i % 10000 == 0:
            print(i, len(names), flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(OUT / "on_m1w_px.parquet")
    print(df.shape, df.date.min(), df.date.max(), df.sym.nunique())


if __name__ == "__main__":
    main()
