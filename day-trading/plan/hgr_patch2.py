"""HALAL-GATE-REVIEW: mirror the 2026-09-17 gate change into halal_pt."""
from pathlib import Path

p = Path(__file__).resolve().parent / "penny_ax11b_massive.py"
s = p.read_text(encoding="utf-8")

# 1) _ttm_pt: skip LEADING quarters that never tagged revenue instead of
#    scoring their 0.0 into the TTM.
old = ('        if picked and ("rev" in _q_miss(q)):\n'
       '            break                    # window stops, what we have '
       'stands')
new = ('        if "rev" in _q_miss(q):\n'
       '            if picked:\n'
       '                break            # window stops, what we have stands\n'
       '            # LAST-AVAILABLE STATEMENT (user ruling 2026-09-17):\n'
       '            # the NEWEST filed quarter not tagging revenue is not\n'
       '            # a reason to refuse -- it used to be silently summed\n'
       '            # in as a 0.0, understating TTM revenue and inflating\n'
       '            # the 5% ratio. Step back to the last quarter that\n'
       '            # actually filed the line.\n'
       '            continue')
assert s.count(old) == 1, "ttm"
s = s.replace(old, new)

# 2) the cash-ceiling rung, same proof as the live gate's rung 4
old2 = ('    if all(q.get("nonop") is not None for q in picked):\n'
        '        bp = abs(sum(q["nonop"] for q in picked)) / ttm_rev * 100\n'
        '        if bp < 5:\n'
        '            return bp, "upper-bound"\n'
        '    return None, None')
new2 = ('    if all(q.get("nonop") is not None for q in picked):\n'
        '        bp = abs(sum(q["nonop"] for q in picked)) / ttm_rev * 100\n'
        '        if bp < 5:\n'
        '            return bp, "upper-bound"\n'
        '    if base > 0:\n'
        '        # RUNG 4 -- THE CASH CEILING (user ruling 2026-09-17,\n'
        '        # same proof as day-trading.py::halal_check). Interest\n'
        '        # income cannot exceed 8%/yr on the cash that earns it,\n'
        '        # so a ceiling under 5% of TTM revenue clears the leg\n'
        '        # whatever the filer tagged -- and it is untagged for\n'
        '        # exactly that reason: the line is immaterial.\n'
        '        cb = abs(cap) / ttm_rev * 100\n'
        '        if cb < 5:\n'
        '            return cb, "upper-bound (max yield on cash)"\n'
        '    return None, None')
assert s.count(old2) == 1, "rung4"
s = s.replace(old2, new2)

# 3) halal_pt: a missing debt/cash row falls back to the last quarter
#    that filed it, inside the staleness bound, instead of refusing.
old3 = ('            if {"debt", "cash", "rev"} & set(_q_miss(sel)):\n'
        '                return False          # unverified: missing '
        'statement row\n'
        '            loan = sel["debt"] / mcap * 100\n'
        '            cash = sel["cash"] / mcap * 100')
new3 = ('            _m = {"debt", "cash"} & set(_q_miss(sel))\n'
        '            _dv = (_last_filed_pt(usable, "debt", date)\n'
        '                   if "debt" in _m else sel["debt"])\n'
        '            _cv = (_last_filed_pt(usable, "cash", date)\n'
        '                   if "cash" in _m else sel["cash"])\n'
        '            if _dv is None or _cv is None:\n'
        '                return False          # unverified: missing '
        'statement row\n'
        '            loan = _dv / mcap * 100\n'
        '            cash = _cv / mcap * 100')
assert s.count(old3) == 1, "halal_pt"
s = s.replace(old3, new3)

# 4) the helper itself
old4 = 'def _interest_leg_pt(picked, ttm_rev):'
new4 = ('# LAST-AVAILABLE STATEMENT (user ruling 2026-09-17). Same bound\n'
        '# and same doctrine as day-trading.py::LAST_AVAIL_MAX_AGE_DAYS:\n'
        '# a row the newest filed quarter does not tag is looked up in\n'
        '# the last quarter that DID tag it, within ~15 months, instead\n'
        '# of refusing the name outright. It is still never a zero.\n'
        'LAST_AVAIL_MAX_AGE_DAYS = 460\n'
        '\n'
        '\n'
        'def _last_filed_pt(usable, field, asof):\n'
        '    """Value of `field` from the most recent filed quarter that\n'
        '    vouches for it, or None if none does inside the bound."""\n'
        '    for q in reversed(usable):\n'
        '        if field in _q_miss(q):\n'
        '            continue\n'
        '        if _qspan(q["date"], asof) > LAST_AVAIL_MAX_AGE_DAYS:\n'
        '            return None\n'
        '        v = q.get(field)\n'
        '        return None if v is None else float(v)\n'
        '    return None\n'
        '\n'
        '\n'
        'def _interest_leg_pt(picked, ttm_rev):')
assert s.count(old4) == 1, "helper"
s = s.replace(old4, new4)

p.write_text(s, encoding="utf-8")
print("patched halal_pt")
