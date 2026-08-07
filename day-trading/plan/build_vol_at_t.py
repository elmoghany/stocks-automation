"""CAUSAL volume numerator: cumulative volume as of a decision time.

WHY (2026-08-07): the backtest's selection rule is full-day volume /
50-day average >= 5. Full-day volume is unknowable at 07:30, so the
rule cannot be executed live -- and the live scan has been using a
DIFFERENT rule (Robinhood 30-day RelVolume on prior-session volume),
which is how TWLO reached us at a true 2.05x on our own measure.

This builds the honest numerator: volume actually printed between the
session start and time T, for every cached candidate-day.

BAR GRANULARITY (repo policy, and what was asked for): the VOLUME
measurement is taken on 5-MINUTE buckets, aggregated here from the local
1-minute cache -- exact, not resampled-with-interpolation. Entries and
exits are untouched and still run on 1-minute bars. A 5-minute bucket is
included only if the bucket has CLOSED by T, so nothing peeks.

Session accumulation starts at 04:00 ET (pre-market counts -- our
entries can fire from 07:00, so the pre-market tape is part of the
day's participation).

Output: data/massive/vol_at_t.json
    {"SYM|YYYY-MM-DD": {"0700": v, "0730": v, ..., "full": v}}
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
M1 = ROOT / "data/massive/m1"
OUT = ROOT / "data/massive/vol_at_t.json"

SESSION_START = 4 * 60                      # 04:00 ET
DECISION_TIMES = [(7, 0), (7, 30), (8, 0), (8, 30), (9, 0),
                  (9, 30), (10, 0), (10, 30), (11, 0), (12, 0)]


def main():
    out, skipped = {}, 0
    files = sorted(M1.glob("*.csv"))
    print(f"{len(files):,} cached candidate-days", flush=True)
    for n, f in enumerate(files, 1):
        sym, date = f.stem.rsplit("_", 1)
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
        except Exception:
            skipped += 1
            continue
        if not len(df) or df.index.tz is None or "Volume" not in df:
            skipped += 1
            continue
        df.index = df.index.tz_convert("America/New_York")
        mins = df.index.hour * 60 + df.index.minute
        df = df[mins >= SESSION_START]
        if not len(df):
            skipped += 1
            continue
        mins = df.index.hour * 60 + df.index.minute
        # 5-minute buckets, labelled by the minute the bucket CLOSES.
        bucket_close = (mins // 5) * 5 + 5
        vol = pd.Series(df["Volume"].values).groupby(
            pd.Series(bucket_close.values)).sum()
        rec = {}
        for hh, mm in DECISION_TIMES:
            t = hh * 60 + mm
            # only buckets fully closed at or before T
            rec[f"{hh:02d}{mm:02d}"] = float(vol[vol.index <= t].sum())
        rec["full"] = float(df["Volume"].sum())
        out[f"{sym}|{date}"] = rec
        if n % 1000 == 0:
            print(f"  {n:,}/{len(files):,}", flush=True)
    OUT.write_text(json.dumps(out))
    print(f"wrote {len(out):,} symbol-days -> {OUT.name} "
          f"({skipped:,} skipped as unusable)", flush=True)

    # sanity: what fraction of the day is done by each decision time?
    print("\nMEDIAN SHARE OF THE DAY'S VOLUME ALREADY PRINTED BY TIME T")
    for hh, mm in DECISION_TIMES:
        k = f"{hh:02d}{mm:02d}"
        sh = sorted(r[k] / r["full"] for r in out.values() if r["full"] > 0)
        if sh:
            print(f"  {hh:02d}:{mm:02d}  median {100*sh[len(sh)//2]:>6.2f}%"
                  f"   p90 {100*sh[int(len(sh)*.9)]:>6.2f}%")


if __name__ == "__main__":
    main()
