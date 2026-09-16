"""RL-SERIES v2 (2026-09-16): point-in-time halal gate, offline, with a
DE-CAMPAIGNED point-in-time shares cache.

Same contract as plan/rl/halal_offline.py -- `load()` returns
plan/penny_ax11b_massive with the network stubbed out and `shares_asof`
replaced by an offline reader -- with ONE substantive change, which is the
whole reason this file exists.

WHY A SECOND SHARES CACHE
-------------------------
v1's confound, stated in rl-audit.md: `data/pt_shares` was populated by
EARLIER campaigns, which queried the names their rankers surfaced. Those
rankers were later shown to be future-conditioned ("MX-SERIES RETRACTION
#2"). Under nearest-earlier semantics a symbol becomes halal-EVALUABLE at
date D only if some campaign had queried it on or before D -- i.e. only
after it had already printed a +10% gap day. So the "halal universe"
silently reduces to "names that recently gapped", which is precisely the
outcome-conditioned pool v2 is supposed to escape.

The fix is to query shares for the WHOLE causal liquidity screen on a
fixed monthly anchor grid, so membership depends on nothing but the
screen. That backfill lives in `plan/rl2/backfill_shares.py` and writes
`plan/rl2/cache/shares/{SYM}_{YYYY-MM-DD}.json` -- a private directory, so
no concurrently-running halal job can be disturbed by it and vice versa.

`shares_asof_pt` reads BOTH directories (rl2 cache first, then the legacy
`data/pt_shares`) and takes the most recent as-of date STRICTLY <= `date`
from the union. A share count queried as of an earlier day was knowable on
that day, so nearest-earlier is stale but never future. A transport
failure is never cached (see backfill_shares.py), so a miss stays a miss
and, under HALAL_STRICT, halal_pt refuses -- live semantics.

WHAT IS STILL PRESENT-DAY (documented, not fixed here)
  * `industry_clean` reads a present-day sector/industry label
    (data/backtest60/rules_ytd.json + data/pt_halal/{sym}.json "industry").
  * `sector_clean` reads a present-day SIC code.
  Both are business-model classifications that essentially never move, and
  both are applied identically to every policy and every control, so they
  cannot create a return edge -- but they do mean a symbol with NO label
  is refused, and label coverage is itself uneven. Quantified in the
  coverage funnel written by plan/rl2/universe.py.
"""
import bisect
import json
import os
from collections import defaultdict
from pathlib import Path

os.environ["HALAL_STRICT"] = "1"
os.environ["PT_FILED"] = "1"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SH_LEGACY = ROOT / "data" / "pt_shares"
SH_RL2 = HERE / "cache" / "shares"

_by_sym = None
_calls = {"exact": 0, "earlier": 0, "miss": 0, "rl2": 0, "legacy": 0}


def _scan(d, out):
    if not d.is_dir():
        return
    for f in d.iterdir():
        n = f.name
        if not n.endswith(".json") or "_" not in n[:-5]:
            continue
        sym, dt = n[:-5].rsplit("_", 1)
        # skip the legacy YYYY-MM month key (the 2026-09-01 leak epoch)
        if len(dt) == 10 and dt[4] == "-":
            out[sym].append((dt, d))


def _index():
    global _by_sym
    if _by_sym is not None:
        return _by_sym
    d = defaultdict(list)
    _scan(SH_RL2, d)
    _scan(SH_LEGACY, d)
    for s in d:
        # (date, dir) sorted by date; rl2 wins ties because it sorts after
        # data/pt_shares only by accident, so de-dup explicitly instead.
        seen, keep = set(), []
        for dt, src in sorted(d[s], key=lambda t: (t[0], t[1] != SH_RL2)):
            if dt in seen:
                continue
            seen.add(dt)
            keep.append((dt, src))
        d[s] = keep
    _by_sym = d
    return d


def shares_asof_pt(sym, date):
    lst = _index().get(sym)
    if not lst:
        _calls["miss"] += 1
        return None
    i = bisect.bisect_right([t[0] for t in lst], date)
    if i == 0:
        _calls["miss"] += 1
        return None
    use, src = lst[i - 1]
    _calls["exact" if use == date else "earlier"] += 1
    _calls["rl2" if src == SH_RL2 else "legacy"] += 1
    try:
        val = json.loads((src / f"{sym}_{use}.json").read_text())
    except Exception:
        _calls["miss"] += 1
        return None
    if not val:
        _calls["miss"] += 1
        return None
    return val


def load():
    """plan/penny_ax11b_massive with the network removed and the
    point-in-time shares reader installed. Call m.halal_pt(sym, date,
    prev_close)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pax11b_rl2", ROOT / "plan" / "penny_ax11b_massive.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.HALAL_STRICT and m.PT_FILED, "gate must be STRICT + FILED"
    m.api = lambda *a, **k: None          # no network, ever
    m.shares_asof = shares_asof_pt
    return m


def stats():
    return dict(_calls)
