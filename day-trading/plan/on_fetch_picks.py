"""OVERNIGHT research: fetch 1-minute bars around the overnight hold for picked
(sym, D) pairs -- one request per pair, window D 15:40 ET -> D+1 09:50 ET.
Extracts only: p1555 (close of 15:54 bar), c1559 (last RTH bar close of D),
n_o930, n_o931 (opens of D+1 09:30 / 09:31 bars), n_c934, n_c944.
Cache: data/research_oct/on_picks_px.jsonl (append, resumable). Key never printed.
Usage: python plan/on_fetch_picks.py pairs.csv   (columns sym,date,ndate)
"""
import csv
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))
from shared import massive  # noqa: E402

OUT = ROOT / "data/research_oct/on_picks_px.jsonl"
ET = ZoneInfo("America/New_York")
LOCK = threading.Lock()


def ms(date, h, m):
    y, mo, d = map(int, date.split("-"))
    return int(datetime(y, mo, d, h, m, tzinfo=ET).timestamp() * 1000)


def get(url):
    for a in range(12):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(min(60, 3 * (a + 1)))
                continue
            if e.code == 404:
                return {}
            raise
        except Exception:
            time.sleep(3)
    return None


def one(sym, D, N):
    u = (f"{massive.BASE}/v2/aggs/ticker/{sym}/range/1/minute/{ms(D, 15, 40)}/{ms(N, 9, 50)}"
         f"?adjusted=true&sort=asc&limit=50000&apiKey={massive._key()}")
    d = get(u)
    if d is None:
        return {"sym": sym, "date": D, "err": 1}
    r = {"sym": sym, "date": D, "ndate": N}
    k = {n: ms(dd, h, m) for n, (dd, h, m) in {
        "1554": (D, 15, 54), "1559": (D, 15, 59), "930": (N, 9, 30), "931": (N, 9, 31),
        "934": (N, 9, 34), "944": (N, 9, 44)}.items()}
    for b in d.get("results") or []:
        t = b["t"]
        if t <= k["1554"]:
            r["p1555"] = b["c"]
        if t <= k["1559"]:
            r["c1559"] = b["c"]
        if t == k["930"]:
            r["n_o930"] = b["o"]
        if t == k["931"]:
            r["n_o931"] = b["o"]
        if k["930"] <= t <= k["934"]:
            r["n_c934"] = b["c"]
        if k["930"] <= t <= k["944"]:
            r["n_c944"] = b["c"]
    return r


def main():
    pairs = list(csv.DictReader(open(sys.argv[1])))
    done = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            j = json.loads(line)
            if not j.get("err"):
                done.add((j["sym"], j["date"]))
    todo = [(p["sym"], p["date"], p["ndate"]) for p in pairs if (p["sym"], p["date"]) not in done]
    print("todo", len(todo), "done", len(done), flush=True)
    n = 0
    with ThreadPoolExecutor(int(sys.argv[2]) if len(sys.argv) > 2 else 4) as ex, open(OUT, "a") as f:
        for r in ex.map(lambda p: one(*p), todo):
            with LOCK:
                f.write(json.dumps(r) + "\n")
                n += 1
                if n % 250 == 0:
                    f.flush()
                    print(n, len(todo), flush=True)
    print("FINISHED", n, flush=True)


if __name__ == "__main__":
    main()
