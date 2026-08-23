"""IDENTITY CHAIN, institutionalized (2026-08-21).

The idgate runs used to be ad-hoc (idgate6/7/8 lived only in NOTES).
This script IS the identity gate now: it re-runs the anchor configs and
compares against the expectation table below. Any mismatch is a BUG
until traced to a dated, documented cause (compliance ruling, coverage
fix); rationalizing an unexplained shift is forbidden.

EXPECTATION HISTORY (every re-baseline gets a dated note):
  * S095 513,965 / 649,573 -- unchanged since the S-campaign. Its pool
    is walk-8 by full-day gain over gappers2, ALL of which had bar
    files before the 2026-08-21 full backfill, so the coverage fix
    should not touch it.
  * Z104 y2025 420,935 -> 417,040 on 2026-08-14: compliance epoch
    (user haram-industry rulings flowed into the legacy gate's word
    list). NOT mechanical drift.
  * C37E (rotation chain) is gated by plan/rotation_sim.py runs, not
    here; post-backfill its causal pool grows the same way (C37F is
    its full-coverage successor -- identical params + env, new data).

Usage:
  python plan/idgate.py                # run all gates
  python plan/idgate.py S095 Z104     # subset
  python plan/idgate.py --prepool     # replay against the PRE-backfill
      file set (data/massive/m1_prebackfill_files.txt, hardlinked into
      data/massive/m1_pre) and compare to EXPECT_PRE. This is the
      mechanical trace for coverage-driven shifts: if a gate moved
      after the backfill, it must still reproduce its OLD value EXACTLY
      on the OLD file set, proving the delta is the data and only the
      data.
Paid-tier note: sets shared.massive._TH_INTERVAL = 0.25 in THIS
process so cache misses on the enlarged pool (pt_shares/pt_fin for
never-before-walked symbols) do not crawl at the free-tier 12.5s.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))
from shared import massive
massive._TH_INTERVAL = 0.25          # paid tier (verified 2026-08-20)

EXPECT = {
    # (gate, label): exact expected total
    ("S095", "year"): 513_965,
    ("S095", "y2025"): 649_573,
    # COVERAGE EPOCH 2026-08-22 (the full-breadth m1 backfill):
    # Z104's causal_cut pool grew ~13x and both years COLLAPSED --
    # year +225,646 -> -29,460 ; y2025 +417,040 -> -1,872.
    # The --prepool replay reproduced the OLD values EXACTLY on the
    # old file set (identity chain: ALL EXACT, /tmp logs 2026-08-22),
    # proving the delta is the data and only the data: Z104's
    # historical profit was substantially a bar-coverage artifact.
    # S095 is walk-cut over gappers2 (all pre-covered) and is
    # unmoved -- the strongest evidence the engine itself is stable.
    # Pre-coverage-epoch values (for --prepool): year 225,646 /
    # y2025 417,040 (itself the 2026-08-14 compliance re-baseline
    # from 420,935).
    ("Z104", "year"): -29_460,
    ("Z104", "y2025"): -1_872,
}

# Frozen historical expectations on the PRE-backfill file set (the
# --prepool replay). These never change again: they are the last
# numbers measured on the coverage-biased cache (2026-08-14 epoch).
EXPECT_PRE = {
    ("S095", "year"): 513_965,
    ("S095", "y2025"): 649_573,
    ("Z104", "year"): 225_646,
    ("Z104", "y2025"): 417_040,
}


def _build_prepool():
    """Hardlink the snapshotted pre-backfill files into m1_pre."""
    src = ROOT / "data/massive/m1"
    dst = ROOT / "data/massive/m1_pre"
    names = (ROOT / "data/massive/m1_prebackfill_files.txt") \
        .read_text().split()
    dst.mkdir(exist_ok=True)
    import os
    made = 0
    for n in names:
        d = dst / n
        if not d.exists():
            os.link(src / n, d)
            made += 1
    print(f"prepool: {len(names)} files ({made} linked now)", flush=True)
    return dst


def main():
    prepool = "--prepool" in sys.argv
    gates = [a for a in sys.argv[1:] if not a.startswith("--")] or \
        ["S095", "Z104"]
    spec_ = importlib.util.spec_from_file_location(
        "px", ROOT / "plan/penny_x100.py")
    px = importlib.util.module_from_spec(spec_)
    sys.modules["px"] = px
    spec_.loader.exec_module(px)
    exp = EXPECT
    if prepool:
        px.M1 = _build_prepool()     # module-global: rank_pool/get_lazy
        exp = EXPECT_PRE
    fails = []
    for g in gates:
        for lab in ("year", "y2025"):
            ref = exp[(g, lab)]
            out = px.run_experiment(
                dict(px.BYID[g], id=f"IDG{'P' if prepool else ''}_{g}"),
                lab)
            ok = out["total"] == ref
            print(f"idgate {g} {lab:<6} got {out['total']:>+10,} "
                  f"expect {ref:>+10,}  {'EXACT' if ok else '** FAIL **'}",
                  flush=True)
            if not ok:
                fails.append((g, lab, out["total"], ref))
    if fails:
        print("\nIDENTITY FAILURES -- treat as bugs until mechanically "
              "traced and re-baselined with a dated note here + NOTES:")
        for g, lab, got, ref in fails:
            print(f"  {g} {lab}: {got:+,} vs {ref:+,} "
                  f"(delta {got - ref:+,})")
        sys.exit(1)
    print("\nidentity chain: ALL EXACT")


if __name__ == "__main__":
    main()
