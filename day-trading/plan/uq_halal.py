"""UNIVERSE+QUOTES (2026-09-16) -- constraint 1, stage 2: the halal gate,
unchanged, asked about 4.5x more names.

WHAT THE WIDE-NET FUNNEL ACTUALLY MEASURED
  4,575 liquid names/day -> 728 "labelled" -> 61 halal-PASS. The audit
  read the middle number as `data/pt_halal` statement coverage. It is
  not. Measured here on the same caches:

    screen symbols (union, 448 days)              6,371
    ... with a point-in-time statement file        3,099
    ... with a NON-EMPTY industry/sector LABEL     1,270

  and `industry_clean` under HALAL_STRICT REFUSES an empty label ("an
  unknown industry is not evidence of compliance"). So the binding
  constraint is the LABEL, and the label has exactly two sources in the
  gate: `sector_raw` in data/backtest60/rules_ytd.json (1,270 of the
  screen) and the `industry` field of data/pt_halal/{SYM}.json (58).

  data/sic_codes.json -- already on disk, EDGAR `submissions` SIC codes
  and DESCRIPTIONS for 11,134 tickers -- covers 5,671 of the 6,371. A SIC
  description ("State Commercial Banks", "Malt Beverages", "Services-
  Prepackaged Software") is the same KIND of object as `sector_raw`: a
  present-day business-activity label for a classification that
  essentially never moves. Feeding it in widens the labelled pool 4.5x.

HOW IT IS FED IN, AND WHY THIS IS NOT A GATE CHANGE
  Exactly as plan/rl2/halal2.py feeds in a de-campaigned share count: the
  module is loaded, and a DATA source it reads is replaced in memory. No
  rule is edited, no threshold moves, no file on disk is rewritten.
    * `m.VER` gains `sector_raw` = the SIC description for symbols whose
      label would otherwise be empty. Symbols that already have a label
      keep it -- so every name in the incumbent 61/day universe is
      decided by exactly the same label it was decided by before.
    * `m.shares_asof` reads the rl2 cache, then the legacy cache, then
      (new) the EDGAR DEI cover-page share count with its FILING DATE.
      Precedence in that order, so again the incumbent universe is
      unchanged and only names the old caches never covered move.
    * `m.PT` is swapped for an in-memory mirror of data/pt_halal (19 MB)
      because the widened screen asks the gate 2.5 million questions and
      each one re-read a JSON file from disk.

THE GATE IS ALSO MADE STRICTER, NEVER LOOSER
  A SIC description is a WEAKER haram label than a vendor sector string
  in three places the doctrine cares about: SIC 3721 reads "Aircraft",
  not "Aerospace & Defense"; SIC 7812 reads "Services-Motion Picture &
  Video Tape Production", not "Entertainment"; SIC 2082 reads "Malt
  Beverages", which the keyword list does catch only by accident. So a
  name labelled ONLY by SIC also passes an explicit SIC-group screen
  (`haram_sic_fail`) that hard-fails the ordnance / aircraft / missile,
  motion-picture, amusement-and-gambling, tobacco and alcohol groups and
  the revenue-sensitive eating / drinking / lodging groups that the live
  doctrine resolves to CANNOT-VERIFY (= not tradeable). This can only
  REFUSE more than the gate would; it never admits a name the gate
  refused. Its bite is counted in the funnel.

Usage:  from uq_halal import load, haram_sic_fail
"""
import bisect
import gzip
import json
import os
from collections import defaultdict
from pathlib import Path

os.environ["HALAL_STRICT"] = "1"
os.environ["PT_FILED"] = "1"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SH_LEGACY = ROOT / "data" / "pt_shares"
SH_RL2 = HERE / "rl2" / "cache" / "shares"
PT = ROOT / "data" / "pt_halal"
SIC_F = ROOT / "data" / "sic_codes.json"
EDGAR_SHARES = HERE / "uq_out" / "shares_pt.json.gz"

_calls = {"exact": 0, "earlier": 0, "edgar": 0, "miss": 0}

# --- SIC groups the live doctrine hard-fails or cannot verify. Each entry
# names the doctrine word it stands in for, so the mapping is auditable.
HARAM_SIC = {
    (2080, 2085): "alcohol (brewer/distiller/winery)",
    (2100, 2199): "tobacco",
    (3480, 3489): "ordnance -> defense",
    (3720, 3729): "aircraft -> aerospace/defense",
    (3760, 3769): "guided missiles -> defense",
    (3795, 3795): "tanks -> defense",
    (7800, 7849): "motion pictures -> cinema/movie/entertainment",
    (7900, 7999): "amusement & recreation -> entertainment/gambling",
    (5810, 5819): "eating & drinking places -> REVENUE-SENSITIVE",
    (7000, 7011): "hotels & lodging -> REVENUE-SENSITIVE",
    (5180, 5182): "alcohol wholesale -> REVENUE-SENSITIVE",
}
_sic = None
_edgar_sh = None


def sic_table():
    global _sic
    if _sic is None:
        _sic = json.loads(SIC_F.read_text())
    return _sic


def haram_sic_fail(sym):
    """(fail, reason) under the supplementary SIC-group screen."""
    r = sic_table().get(sym) or {}
    s = str(r.get("sic") or "").strip()
    if not s.isdigit():
        return False, ""
    v = int(s)
    for (lo, hi), why in HARAM_SIC.items():
        if lo <= v <= hi:
            return True, f"SIC {v}: {why}"
    return False, ""


# ------------------------------------------------------------ shares
def _scan(d, out):
    if not d.is_dir():
        return
    for f in d.iterdir():
        n = f.name
        if not n.endswith(".json") or "_" not in n[:-5]:
            continue
        sym, dt = n[:-5].rsplit("_", 1)
        if len(dt) == 10 and dt[4] == "-":
            out[sym].append((dt, d))


_by_sym = None


def _index():
    global _by_sym
    if _by_sym is not None:
        return _by_sym
    d = defaultdict(list)
    _scan(SH_RL2, d)
    _scan(SH_LEGACY, d)
    for s in d:
        seen, keep = set(), []
        for dt, src in sorted(d[s], key=lambda t: (t[0], t[1] != SH_RL2)):
            if dt in seen:
                continue
            seen.add(dt)
            keep.append((dt, src))
        d[s] = keep
    _by_sym = d
    return d


def _edgar():
    global _edgar_sh
    if _edgar_sh is None:
        if EDGAR_SHARES.exists():
            with gzip.open(EDGAR_SHARES, "rt") as f:
                _edgar_sh = json.load(f)
        else:
            _edgar_sh = {}
    return _edgar_sh


def _plus1(d):
    from datetime import date as _d, timedelta as _td
    try:
        return (_d.fromisoformat(d[:10]) + _td(days=1)).isoformat()
    except ValueError:
        return "9999-12-31"


def shares_asof_uq(sym, date):
    """Point-in-time share count. Precedence, not a union:
      1. plan/rl2/cache/shares   (the de-campaigned monthly anchor grid)
      2. data/pt_shares          (the legacy exact-date cache)
      3. EDGAR DEI cover page, usable the day AFTER its filing date
    1 and 2 are nearest-earlier by AS-OF date, which is stale but never
    future. 3 is nearest-earlier by FILING date + 1 day -- the identical
    availability rule `penny_ax11b_massive._filed_usable` applies to the
    statements themselves.
    """
    lst = _index().get(sym)
    if lst:
        i = bisect.bisect_right([t[0] for t in lst], date)
        if i:
            use, src = lst[i - 1]
            try:
                val = json.loads((src / f"{sym}_{use}.json").read_text())
            except Exception:
                val = None
            if val:
                _calls["exact" if use == date else "earlier"] += 1
                return val
    ser = _edgar().get(sym)
    if ser:
        av = [_plus1(f) for f, _v in ser]
        i = bisect.bisect_right(av, date)
        if i:
            _calls["edgar"] += 1
            return ser[i - 1][1]
    _calls["miss"] += 1
    return None


# ------------------------------------------------------- in-memory pt_halal
class _MemFile:
    __slots__ = ("_t",)

    def __init__(self, t):
        self._t = t

    def exists(self):
        return self._t is not None

    def read_text(self, *a, **k):
        return self._t


class _MemJson:
    """`json` with a memoized `loads`, everything else delegated.

    The widened screen asks the gate ~2 million questions and each one
    re-parses the same 4 KB statement file. `_MemDir` hands back the SAME
    str OBJECT every time for a given symbol, so memoizing on id(text) is
    exact (the dict that owns the string keeps it alive, so the id cannot
    be recycled). `halal_pt`, `_ttm_pt` and `_interest_leg_pt` only READ
    the parsed structure -- verified line by line -- so one shared parse
    is safe. Nothing else in the module's json use is on this path.
    """

    def __init__(self):
        self._c = {}
        import json as _j
        self._j = _j

    def loads(self, t, *a, **k):
        if a or k or not isinstance(t, str):
            return self._j.loads(t, *a, **k)
        k2 = id(t)
        v = self._c.get(k2)
        if v is None:
            v = self._j.loads(t)
            self._c[k2] = v
        return v

    def __getattr__(self, n):
        import json as _j
        return getattr(_j, n)


class _MemDir:
    """Path-shaped read-only mirror of data/pt_halal (19 MB)."""

    def __init__(self, d):
        self.d = {f.name: f.read_text(encoding="utf-8", errors="replace")
                  for f in d.glob("*.json")}

    def __truediv__(self, name):
        return _MemFile(self.d.get(name))


# ------------------------------------------------------------------ load
def load(inject_sic_labels=True, mem_pt=True):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pax11b_uq", ROOT / "plan" / "penny_ax11b_massive.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.HALAL_STRICT and m.PT_FILED, "gate must be STRICT + FILED"
    m.api = lambda *a, **k: None             # no network, ever
    m.shares_asof = shares_asof_uq
    if mem_pt:
        m.PT = _MemDir(PT)
        m.json = _MemJson()
    if inject_sic_labels:
        tab = sic_table()
        ver = dict(m.VER)
        n = 0
        for sym, r in tab.items():
            desc = str((r or {}).get("desc") or "").strip()
            if not desc:
                continue
            cur = (ver.get(sym) or {}).get("sector_raw") or ""
            if cur.strip():
                continue                    # incumbent label wins
            ver[sym] = {**(ver.get(sym) or {}), "sector_raw": desc,
                        "sector_src": "sic_codes.desc"}
            n += 1
        m.VER = ver
        m.SIC_LABELS_ADDED = n
    return m


def stats():
    return dict(_calls)


if __name__ == "__main__":
    m = load()
    print("SIC labels injected:", m.SIC_LABELS_ADDED)
    scr = json.loads((HERE / "rl2" / "out" / "screen_syms.json").read_text())
    lab = sum(1 for s in scr if m.industry_clean(s))
    sec = sum(1 for s in scr if m.sector_clean(s))
    hs = sum(1 for s in scr if haram_sic_fail(s)[0])
    print(f"screen {len(scr):,}: industry_clean PASS {lab:,}, "
          f"sector_clean PASS {sec:,}, extra HARAM-SIC fail {hs:,}")
    both = sum(1 for s in scr if m.industry_clean(s) and m.sector_clean(s)
               and not haram_sic_fail(s)[0])
    print(f"all three: {both:,}")
    print("shares probe:", [(s, shares_asof_uq(s, "2025-06-02"))
                            for s in scr[:5]])
