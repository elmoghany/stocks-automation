"""SWING-REVERSION data fetch (research only).

Fetches, into day-trading/data/research_oct/:
  gd_adj/YYYY-MM-DD.json.gz  grouped daily, adjusted=true, ONE consistent
                             snapshot (all files adjusted as of today), incl.
                             delisted names (grouped daily is point-in-time
                             membership). API history starts 2024-10-01.
  splits.json                Polygon splits with execution_date >= 2024-01-01
  tickers_ref.json           ticker -> type for active + inactive stocks
Key from Credential Manager (never printed).
"""
import gzip
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from shared.win_cred import get_secret  # noqa: E402

KEY = get_secret("MASSIVE_KEY")
OUT = ROOT / "data" / "research_oct"
GD = OUT / "gd_adj"
GD.mkdir(parents=True, exist_ok=True)
LOCK = threading.Lock()


def hit(url):
    sep = "&" if "?" in url else "?"
    for i in range(12):
        try:
            with urllib.request.urlopen(url + sep + "apiKey=" + KEY, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 + 2 * i)
                continue
            if e.code == 403:
                return None
            time.sleep(3)
        except Exception:
            time.sleep(3)
    raise RuntimeError("failed " + url.split("?")[0])


def fetch_day(d):
    p = GD / f"{d}.json.gz"
    if p.exists():
        return 0
    r = hit(f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{d}?adjusted=true")
    if r is None:
        return -1
    res = r.get("results") or []
    if not res:
        return 0  # holiday / weekend
    slim = [{k: x.get(k) for k in ("T", "o", "h", "l", "c", "v", "vw")} for x in res]
    tmp = p.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        json.dump(slim, f)
    tmp.replace(p)
    return len(slim)


def paged(url):
    out = []
    while url:
        r = hit(url)
        if r is None:
            break
        out += r.get("results") or []
        url = r.get("next_url")
    return out


def main():
    d0, d1 = date(2024, 10, 1), date(2026, 9, 30)
    days = []
    d = d0
    while d <= d1:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    n = [0]
    if "--gd" not in sys.argv:  # default: cached data/massive/gd is used (API 429 contention)
        days = []
    with ThreadPoolExecutor(4) as ex:
        for res in ex.map(fetch_day, days):
            n[0] += 1
            if n[0] % 50 == 0:
                print("days", n[0], "/", len(days), flush=True)
    sp = OUT / "splits.json"
    if not sp.exists():
        s = paged("https://api.polygon.io/v3/reference/splits?execution_date.gte=2005-01-01&limit=1000")
        sp.write_text(json.dumps(s))
        print("splits", len(s), flush=True)
    tr = OUT / "tickers_ref.json"
    if not tr.exists():
        ref = {}
        for active in ("true", "false"):
            rows = paged(f"https://api.polygon.io/v3/reference/tickers?market=stocks&active={active}&limit=1000")
            for x in rows:
                ref.setdefault(x["ticker"], []).append(
                    [x.get("type"), x.get("name"), active, x.get("delisted_utc"), x.get("primary_exchange")])
            print("tickers", active, len(rows), flush=True)
        tr.write_text(json.dumps(ref))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
