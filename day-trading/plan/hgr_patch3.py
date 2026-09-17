"""HALAL-GATE-REVIEW: add the `--last-available` rescreen epoch (v3)."""
from pathlib import Path

p = Path(__file__).resolve().parent / "build_halal_universe.py"
s = p.read_text(encoding="utf-8")

old = ('CACHED_KEYS = ("halal", "verdict", "source", "loan_pct", "cash_pct",\n'
       '               "combined", "haram_pct", "haram_src", "interest_flags",\n'
       '               "fail_reason")')
new = ('CACHED_KEYS = ("halal", "verdict", "source", "loan_pct", "cash_pct",\n'
       '               "combined", "haram_pct", "haram_src", "interest_flags",\n'
       '               "last_available", "fail_reason")')
assert s.count(old) == 1, "keys"
s = s.replace(old, new)

old2 = 'INTEREST_KEYS = ("interest income", "HARAM>=5%")'
new2 = old2 + '''


# ------------------------------------------- LAST-AVAILABLE EPOCH (v3)
# USER RULING 2026-09-17: "For the missing statement, use the last
# available statement or check the Zoya website. Do not just reject it.
# Same for data drift."
#
# The gate change (day-trading.py::LAST_AVAIL_MAX_AGE_DAYS) only ever
# LOOSENS, in three ways and no others:
#   * a debt / cash / revenue row absent from the newest quarterly
#     column is looked up in that column's own older siblings, then the
#     ANNUAL statement, then EDGAR -- inside ~15 months;
#   * a name whose debt and cash never share one recent column reads
#     each leg from its own last filed column instead of refusing;
#   * a new interest rung PROVES the 5% leg from the 8%/yr ceiling on
#     cash when no interest line is tagged anywhere.
# So the names whose verdict can move are: everything refused as
# `unverified`, everything refused for want of fundamentals or a market
# cap (EDGAR may now answer), every current PASS (re-run to catch drift
# and to record the new evidence), every RATIO refusal whose ratios were
# computed from a partially-read balance sheet, and -- for the drift
# question the same ruling asks about -- every name the PRE-FIX list
# armed that is refused today.
DRIFT_KEYS = ("LOAN>10", "CASH>10", "COMBINED>20", "HARAM>=5%")


def _last_available_candidates(done, ruled):
    import os
    extr = ROOT / "data/edgar/extracted"
    try:
        have_edgar = {f[:-5] for f in os.listdir(extr) if f.endswith(".json")}
    except Exception:
        have_edgar = set()
    try:
        pre = set(json.loads(
            (ROOT / "data/halal_list.pre-2026-09-16.json").read_text())
            .get("symbols") or [])
    except Exception:
        pre = set()
    out = set()
    for s_, r in done.items():
        fr = r.get("fail_reason") or ""
        if r.get("halal") or r.get("source") in ("error", None):
            out.add(s_)
        elif fr.startswith("unverified") or fr.startswith("MARKET CAP"):
            out.add(s_)
        elif fr.startswith("NO FUNDAMENTALS") and s_ in have_edgar:
            out.add(s_)
        elif fr.startswith(DRIFT_KEYS):
            # a PRE-FIX ratio string ("LOAN>10+COMBINED>20") is a verdict
            # the fixed gate never re-ran; only the borderline ones can
            # move, and re-fetching 2,231 settled blowouts to confirm
            # them buys nothing.
            cb = r.get("combined")
            if "+COMBINED>20" in fr:
                if cb is not None and cb <= 30:
                    out.add(s_)
            else:
                out.add(s_)
    out |= {s_ for s_ in pre if s_ in done and not done[s_].get("halal")}
    return sorted(out | (ruled & set(done)))'''
assert s.count(old2) == 1, "keys2"
s = s.replace(old2, new2)

old3 = '''    if epoch == "interest-leg":'''
new3 = '''    if epoch == "last-available":
        stamp, flips_f = "v2", \\
            ROOT / "data/halal_flips_2026-09-17.last-available.json"
        baseline = dict(done)
        bak_u = UNI_F.with_name(f"{UNI_F.stem}.{stamp}{UNI_F.suffix}")
        if bak_u.exists():
            baseline = json.loads(bak_u.read_text())
        cands = _last_available_candidates(
            {s: (baseline.get(s) or done[s]) for s in done}, ruled)
        print(f"rescreen (last-available v3): {len(cands):,} candidates "
              f"({sum(1 for s in cands if (baseline.get(s) or {}).get('halal')):,}"
              f" v2 PASS, "
              f"{sum(1 for s in cands if (baseline.get(s) or {}).get('fail_reason','').startswith('unverified')):,}"
              f" refused as unverified, plus no-data names EDGAR may now "
              f"answer, borderline ratio refusals, the pre-fix armable "
              f"list for the drift question, and ruled names)", flush=True)
    elif epoch == "interest-leg":'''
assert s.count(old3) == 1, "epoch"
s = s.replace(old3, new3)

old4 = '''                     epoch=("interest-leg" if "--interest-leg" in sys.argv
                            else "2026-09-16"))'''
new4 = '''                     epoch=("last-available"
                            if "--last-available" in sys.argv
                            else "interest-leg"
                            if "--interest-leg" in sys.argv
                            else "2026-09-16"))'''
assert s.count(old4) == 1, "cli"
s = s.replace(old4, new4)

# restore-cause: name the new rungs
old5 = '''    if src.startswith("edgar-interest"):
        return f"{pre}EDGAR interest"'''
new5 = '''    if src.startswith("edgar-interest"):
        return f"{pre}EDGAR interest"
    if (rec.get("last_available") or {}):
        return (f"{pre}last-available statement ("
                + ", ".join(f"{k}: {v}" for k, v in
                            sorted((rec.get("last_available") or {}).items()))
                + ")")'''
assert s.count(old5) == 1, "restore"
s = s.replace(old5, new5)

p.write_text(s, encoding="utf-8")
print("patched build_halal_universe")
