"""RL-SERIES (2026-09-16): offline, point-in-time halal gate.

plan/penny_ax11b_massive.halal_pt is the gate every campaign in this repo
uses (HALAL_STRICT=1 PT_FILED=1). It is reused VERBATIM here -- the ratio
test, the FILED-quarter selection and industry_clean are not reimplemented.
Two things are changed, both to remove network dependence and both in the
CAUSAL direction:

  1. plan.penny_ax11b_massive.api is stubbed to return None. No Polygon
     call is ever made, so nothing can be fetched with today's knowledge.
  2. shares_asof(sym, date) is replaced by an offline reader over
     data/pt_shares/{SYM}_{YYYY-MM-DD}.json:
         exact date cached      -> use it (true point-in-time)
         else NEAREST EARLIER   -> use the most recent cached as-of date
                                   STRICTLY <= `date`. A share count
                                   queried as of an earlier day was
                                   knowable on that day, so this is stale
                                   but never future.
         else                   -> None, which under HALAL_STRICT makes
                                   halal_pt refuse (live semantics:
                                   "missing data is a FAIL").
     The month-keyed legacy cache (the 2026-09-01 HALAL-LEAK EPOCH bug,
     which could answer an EARLIER date with a LATER query) is never read.

KNOWN CONFOUND, stated up front: data/pt_shares and data/pt_halal were
populated by EARLIER campaigns, which queried the names their rankers
surfaced. Those rankers were later shown to be future-conditioned
(NOTES "MX-SERIES RETRACTION #2"), so *which symbols have cached
fundamentals at all* is an arbitrary, campaign-shaped subset of the
gapper pool -- roughly 2.0k symbols with any dated share count and 1.4k
with a fundamentals file. This inflates or deflates ABSOLUTE numbers in
an unknown direction. It does NOT affect the comparison that the study
turns on, because the random-policy baseline, the shuffled-label control
and every RL agent all draw from the SAME eligible set with the SAME
fills.
"""
import bisect
import json
import os
from collections import defaultdict
from pathlib import Path

os.environ["HALAL_STRICT"] = "1"
os.environ["PT_FILED"] = "1"

ROOT = Path(__file__).resolve().parents[2]
SH = ROOT / "data" / "pt_shares"

_by_sym = None
_calls = {"exact": 0, "earlier": 0, "miss": 0}


def _index():
    global _by_sym
    if _by_sym is not None:
        return _by_sym
    d = defaultdict(list)
    for f in SH.iterdir():
        n = f.name
        if not n.endswith(".json"):
            continue
        stem = n[:-5]
        if "_" not in stem:
            continue
        sym, dt = stem.rsplit("_", 1)
        if len(dt) == 10 and dt[4] == "-":       # skip the legacy YYYY-MM key
            d[sym].append(dt)
    for s in d:
        d[s].sort()
    _by_sym = d
    return d


def shares_asof_offline(sym, date):
    idx = _index()
    lst = idx.get(sym)
    if not lst:
        _calls["miss"] += 1
        return None
    i = bisect.bisect_right(lst, date)
    if i == 0:
        _calls["miss"] += 1
        return None
    use = lst[i - 1]
    _calls["exact" if use == date else "earlier"] += 1
    try:
        val = json.loads((SH / f"{sym}_{use}.json").read_text())
    except Exception:
        _calls["miss"] += 1
        return None
    if not val:
        _calls["miss"] += 1
        return None
    return val


def load():
    """Import the engine module with the offline patches applied.

    Returns the module; call m.halal_pt(sym, date, prev_close).
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pax11b_rl", ROOT / "plan" / "penny_ax11b_massive.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.HALAL_STRICT and m.PT_FILED, "gate must be STRICT + FILED"
    m.api = lambda *a, **k: None          # no network, ever
    m.shares_asof = shares_asof_offline
    return m


def stats():
    return dict(_calls)
