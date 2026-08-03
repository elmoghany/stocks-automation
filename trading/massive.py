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
        from trading.win_cred import get_secret
        _KEY = get_secret("MASSIVE_KEY")
        if not _KEY:
            raise RuntimeError("MASSIVE_KEY not in Credential Manager")
    return _KEY


def _get(url: str, tries: int = 5) -> dict:
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15 * (attempt + 1))
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
