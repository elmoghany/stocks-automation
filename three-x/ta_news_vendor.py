"""Point-in-time news vendor for TradingAgents, on the Massive (Polygon) news endpoint.

Yahoo's news feed only reaches back a few days, so on a past analysis date TradingAgents has
no news at all. This registers a "massive" vendor that returns articles published inside the
requested window, never after it. Calls go through the repo's throttled client.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import massive  # noqa: E402

from tradingagents.dataflows import router  # noqa: E402

CACHE = Path(r"E:\strategy-repos\ta_cache\news")
CACHE.mkdir(parents=True, exist_ok=True)


def _articles(ticker, start, end, limit):
    """Articles published from start through end inclusive, newest first, cached on disk."""
    path = CACHE / f"{ticker or 'MARKET'}_{start}_{end}_{limit}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    query = {"published_utc.gte": f"{start}T00:00:00Z", "published_utc.lte": f"{end}T23:59:59Z",
             "order": "desc", "sort": "published_utc", "limit": limit, "apiKey": massive._key()}
    if ticker:
        query["ticker"] = ticker
    rows = massive._get(f"{massive.BASE}/v2/reference/news?{urlencode(query)}").get("results", [])
    keep = [{"published": r.get("published_utc", ""), "title": r.get("title", ""),
             "source": (r.get("publisher") or {}).get("name", ""), "summary": r.get("description", "")}
            for r in rows]
    path.write_text(json.dumps(keep), encoding="utf-8")
    return keep


def _render(header, rows):
    if not rows:
        return f"{header}\nNo articles were published in this window."
    body = "\n\n".join(f"[{r['published'][:10]}] {r['title']} ({r['source']})\n{r['summary']}" for r in rows)
    return f"{header}\n\n{body}"


def get_news_massive(ticker, start_date, end_date):
    rows = _articles(ticker, start_date, end_date, 20)
    return _render(f"News for {ticker}, {start_date} to {end_date}", rows)


def get_global_news_massive(as_of_date, look_back_days=None, limit=None):
    start = (datetime.strptime(as_of_date, "%Y-%m-%d") - timedelta(days=look_back_days or 7)).strftime("%Y-%m-%d")
    rows = _articles("SPY", start, as_of_date, limit or 10)
    return _render(f"Market news tagged SPY, {start} to {as_of_date}", rows)


def register(config):
    """Add the vendor and make it the news source for this run."""
    router.VENDOR_METHODS["get_news"]["massive"] = get_news_massive
    router.VENDOR_METHODS["get_global_news"]["massive"] = get_global_news_massive
    return {**config, "tool_vendors": {**config.get("tool_vendors", {}),
                                       "get_news": "massive", "get_global_news": "massive"}}
