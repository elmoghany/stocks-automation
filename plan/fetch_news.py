"""Fetch Finnhub company-news for the Y1 walk-pool candidate-days.
Cache: data/news_cache/{SYM}_{date}.json = {"n18": count of headlines
in the 18h before 7AM ET, "latest": unix ts}. Finnhub free tier: 60
calls/min; history reaches ~1 year (Y2 dates return empty -- fetched
anyway only if --y2 passed). Resumable (skip existing).
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from trading.win_cred import get_secret

KEY = get_secret("FINNHUB_KEY")
ET = ZoneInfo("America/New_York")
OUT = ROOT / "data" / "news_cache"
OUT.mkdir(parents=True, exist_ok=True)


def fetch(sym, date):
    f = OUT / f"{sym}_{date}.json"
    if f.exists():
        return False
    d = datetime.fromisoformat(date)
    frm = (d - timedelta(days=1)).date().isoformat()
    url = (f"https://finnhub.io/api/v1/company-news?symbol={sym}"
           f"&from={frm}&to={date}&token={KEY}")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            items = json.load(r)
    except Exception:
        time.sleep(5)
        return False
    cutoff_hi = datetime(d.year, d.month, d.day, 7, 0, tzinfo=ET).timestamp()
    cutoff_lo = cutoff_hi - 18 * 3600
    n18 = sum(1 for it in items
              if cutoff_lo <= it.get("datetime", 0) <= cutoff_hi)
    latest = max((it.get("datetime", 0) for it in items
                  if it.get("datetime", 0) <= cutoff_hi), default=0)
    f.write_text(json.dumps({"n18": n18, "latest": latest,
                             "total": len(items)}))
    return True


def main():
    labels = ["year"] + (["y2025"] if "--y2" in sys.argv else [])
    pairs = []
    for label in labels:
        gap = json.loads(
            (ROOT / f"data/massive/gappers2_{label}.json").read_text())
        by_day = {}
        for c in gap:
            if c.get("hist_n", 99) >= 50:
                by_day.setdefault(c["date"], []).append(c)
        for date, cs in sorted(by_day.items()):
            for c in sorted(cs, key=lambda x: -x["gain_pct"])[:8]:
                pairs.append((c["symbol"], date))
    pairs = sorted(set(pairs))
    print(f"{len(pairs)} candidate-days to ensure", flush=True)
    done = 0
    for n, (sym, date) in enumerate(pairs):
        if fetch(sym, date):
            done += 1
            time.sleep(1.05)   # 57/min, under the 60/min limit
        if n % 100 == 0:
            print(f"  {n}/{len(pairs)} ({done} fetched)", flush=True)
    print(f"done: {done} new fetches", flush=True)


if __name__ == "__main__":
    main()
