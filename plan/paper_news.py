"""Save the day's news for paper-session candidates (user directive
2026-08-05: keep each day's trading in files in the repo, with the news,
for later analysis).

For each symbol: Finnhub company-news from the prior day through the
given date -> data/paper/news/{date}/{SYM}.json with full headlines
(datetime ET, source, headline, summary truncated). Free tier reaches
back ~1 year, 60 calls/min (we space 1.1s).

Usage: python plan/paper_news.py DATE SYM [SYM ...]
       python plan/paper_news.py 2026-08-05 GTE INLF JLHL
Existing files are skipped (resumable); --force refetches.
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

ET = ZoneInfo("America/New_York")
KEY = get_secret("FINNHUB_KEY")


def fetch(sym, date, force=False):
    out_dir = ROOT / "data/paper/news" / date
    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / f"{sym}.json"
    if f.exists() and not force:
        return "skip"
    d = datetime.fromisoformat(date)
    frm = (d - timedelta(days=1)).date().isoformat()
    url = (f"https://finnhub.io/api/v1/company-news?symbol={sym}"
           f"&from={frm}&to={date}&token={KEY}")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            items = json.load(r)
    except Exception as e:
        print(f"  {sym}: {e}", flush=True)
        return "err"
    slim = [{
        "et": datetime.fromtimestamp(it.get("datetime", 0), tz=ET)
        .strftime("%Y-%m-%d %H:%M"),
        "source": it.get("source", ""),
        "headline": it.get("headline", ""),
        "summary": (it.get("summary") or "")[:300],
    } for it in sorted(items, key=lambda x: x.get("datetime", 0))]
    f.write_text(json.dumps({"symbol": sym, "date": date,
                             "count": len(slim), "items": slim},
                            indent=1), encoding="utf-8")
    return len(slim)


def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv
    if len(args) < 2:
        print(__doc__)
        return
    date, syms = args[0], [s.upper() for s in args[1:]]
    for sym in syms:
        r = fetch(sym, date, force)
        print(f"  {sym}: {r}", flush=True)
        if r not in ("skip",):
            time.sleep(1.1)


if __name__ == "__main__":
    main()
