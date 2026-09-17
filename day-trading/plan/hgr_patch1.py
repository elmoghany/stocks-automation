"""HALAL-GATE-REVIEW: one-shot source patch (kept for provenance)."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "day-trading.py"
s = p.read_text(encoding="utf-8")

old = ('            return (abs(float(cash_total))\n'
       '                    if cash_total is not None else None)')
new = (
    '            _lt = [r for r in (_row(bs, LTI_ROWS_A), _row(bs, LTI_ROWS_B))\n'
    '                   if r is not None]\n'
    '            _lv = []\n'
    '            for c in (_cols(bs) if bs is not None else []):\n'
    '                got = [float(r[c]) for r in _lt if not pd.isna(r[c])]\n'
    '                if got:\n'
    '                    _lv.append(max(got))\n'
    '            _base = (abs(float(cash_total))\n'
    '                     if cash_total is not None else 0.0)\n'
    '            # a fund/trust balance sheet often carries NO cash line\n'
    '            # and a very large investments line (ADX: no cash row,\n'
    '            # $3.0bn "Investments And Advances" against $34M of\n'
    '            # revenue). Those securities earn the income, so they\n'
    '            # belong in the ceiling base -- leaving them out would\n'
    '            # hand the cash-ceiling rung a base four orders of\n'
    '            # magnitude too small and PASS a bond fund on a proof\n'
    '            # that is simply false.\n'
    '            if _lv:\n'
    '                _base += sum(_lv) / len(_lv)\n'
    '            return _base or None')
assert s.count(old) == 1, ("plaus", s.count(old))
s = s.replace(old, new)

old2 = '            ttm_int, n_q = None, 1        # info revenue is already annual'
new2 = old2 + '\n            _cash_is_info[0] = True'
assert s.count(old2) == 1, "info"
s = s.replace(old2, new2)

old5 = ('    # ANNUAL TIER: one filed period ALREADY IS the twelve months, '
        'so the')
new5 = (
    '    # `info` is a vendor SUMMARY, not a statement: its `totalCash`\n'
    '    # is unreliable for funds and trusts and there is no interest\n'
    '    # field at all. Recorded so the cash-ceiling rung below can\n'
    '    # refuse to rest a PROOF on it (audit Bug 3 -- the info tier\n'
    '    # must not PASS).\n'
    '    _cash_is_info = [False]\n\n' + old5)
assert s.count(old5) == 1, "annualtier"
s = s.replace(old5, new5)

old6 = ('        if _pct is None and (ttm_rev or 0) > 0 and _cap is not None \\\n'
        '                and abs(_cap) > 0:')
new6 = ('        if _pct is None and (ttm_rev or 0) > 0 and _cap is not None \\\n'
        '                and abs(_cap) > 0 and not _cash_is_info[0]:')
assert s.count(old6) == 1, "rung4"
s = s.replace(old6, new6)

p.write_text(s, encoding="utf-8")
print("patched")
