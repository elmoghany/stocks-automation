"""Massive (Polygon.io) market data client. Key: Credential Manager
MASSIVE_KEY. Zero deps beyond stdlib+pandas."""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

ET = ZoneInfo("America/New_York")
BASE = "https://api.polygon.io"
_KEY = None


def _key() -> str:
    global _KEY
    if _KEY is None:
        from .win_cred import get_secret
        _KEY = get_secret("MASSIVE_KEY")
        if not _KEY:
            raise RuntimeError("MASSIVE_KEY not in Credential Manager")
    return _KEY


_TH_LOCK = __import__("threading").Lock()
_TH_NEXT = [0.0]
# Default pacing stays the free-tier-safe 12.5s so nothing speeds up
# silently. The account moved to the PAID starter tier on 2026-08-20
# (verified: 8 calls in 5.4s, zero 429s); batch jobs that want the paid
# pace set MASSIVE_TH_INTERVAL (seconds between request starts) or
# assign massive._TH_INTERVAL in-process. 429s are still retried below,
# so a too-low interval degrades to slow, never to wrong.
import os as _os
_TH_INTERVAL = float(_os.environ.get("MASSIVE_TH_INTERVAL", "12.5"))


def _throttle():
    """Global pacing: space request starts so we never trip 429s."""
    with _TH_LOCK:
        now = time.monotonic()
        wait = _TH_NEXT[0] - now
        _TH_NEXT[0] = max(now, _TH_NEXT[0]) + _TH_INTERVAL
    if wait > 0:
        time.sleep(wait)


def _get(url: str, tries: int = 8) -> dict:
    for attempt in range(tries):
        _throttle()
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(3)
    raise RuntimeError(f"failed after {tries} tries: {url[:80]}")


def grouped_daily(date: str) -> list[dict]:
    """All US stocks' daily OHLCV for one date. [] on holidays."""
    d = _get(f"{BASE}/v2/aggs/grouped/locale/us/market/stocks/{date}"
             f"?adjusted=true&apiKey={_key()}")
    return d.get("results") or []


def minute_bars(symbol: str, date: str) -> pd.DataFrame | None:
    """Full-session 1-min bars (premarket volume included), ET index."""
    d = _get(f"{BASE}/v2/aggs/ticker/{symbol}/range/1/minute/{date}/{date}"
             f"?adjusted=true&sort=asc&limit=50000&apiKey={_key()}")
    res = d.get("results")
    if not res:
        return None
    df = pd.DataFrame(res)
    df["begins_at"] = (pd.to_datetime(df["t"], unit="ms", utc=True)
                       .dt.tz_convert(ET))
    df = df.rename(columns={"o": "Open", "h": "High", "l": "Low",
                            "c": "Close", "v": "Volume"})
    return (df.set_index("begins_at").sort_index()
            [["Open", "High", "Low", "Close", "Volume"]])
