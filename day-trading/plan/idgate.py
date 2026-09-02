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
  * FILL-MODEL EPOCH 2026-09-02: simulate_trades fills a stop at
    min(stop, Open) clamped to the bar, a limit at max(level, Open),
    and confirms a trail peak only on the following bar (causal).
    S095 513,965 / 649,573 -> 453,477 / 655,566 ; Z104 -29,460 /
    -1,872 -> -31,415 / -6,132. Both gates carry stops; the
    re-baseline is dated in EXPECT below and in NOTES. --prepool
    (EXPECT_PRE) is frozen at the PRE-epoch engine and now needs
    `git show a190a72^:day-trading/day-trading.py` to reproduce.
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
    # (S095 pre-fill-model-epoch: 513_965 / 649_573 -- see the
    # 2026-09-02 note below; the live values are at the end of the dict)
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
    # FILL-MODEL EPOCH 2026-09-02 (day-trading.py simulate_trades, the
    # $-best-day audit): a stop/trail now fills at min(stop, Open)
    # clamped to the bar (a gap through the stop fills at the open,
    # not at the stop level); a limit/target at max(level, Open); the
    # trail's peak is a bar's High only once the FOLLOWING bar has
    # printed (isolated-print + within-50% confirmation, strictly
    # causal; the X319 wick guard's next-close peek is gone); scale-
    # outs use the same fill rule. Both gates carry stops, so both
    # moved; HOLD-only configs are byte-identical (checked on the
    # rotation ladder: HOLD1/HOLD6/RHOLD6 unchanged to the dollar).
    # Pre-epoch values, measured 2026-09-01 23:48 under the halal-leak
    # epoch: S095 +513,965 / +649,573 ; Z104 -29,460 / -1,872.
    # Post-epoch (2026-09-02 02:13 run, /c/tmp/fm/idgate.log):
    #   S095 year +513,965 -> +453,477  (-60,488)
    #   S095 y2025 +649,573 -> +655,566 (+5,993)
    #   Z104 year  -29,460 -> -31,415   (-1,955)
    #   Z104 y2025  -1,872 -> -6,132     (-4,260)
    # This is a RE-BASELINE, not a break: plan/fillmodel_test.py proves
    # the new fills lie inside the bar and the peak is causal
    # (0/4,420 poison breaches); the old values are reproducible only
    # on the pre-epoch engine (git a190a72^).
    ("S095", "year"): 453_477,
    ("S095", "y2025"): 655_566,
    ("Z104", "year"): -31_415,
    ("Z104", "y2025"): -6_132,
    # HALAL-LEAK EPOCH 2026-09-01 (plan/penny_ax11b_massive.py): under
    # HALAL_STRICT the shares cache is keyed by the exact as-of date
    # and missing shares/prev_close REFUSE instead of falling back to
    # the present-day VER verdict; api() no longer caches transport
    # failures as null. These gates run NON-strict (the legacy month
    # key + VER fallback are kept for exactly this chain), so they are
    # unaffected BY CONSTRUCTION -- verified 2026-09-01 23:48:
    # S095 +513,965 / +649,573 EXACT, Z104 -29,460 / -1,872 EXACT,
    # "identity chain: ALL EXACT". The strict-path shift is measured on
    # the rotation chain instead: C37F (HALAL_STRICT=1 PT_FILED=1,
    # POOL_HYGIENE=0) pre-change -72,673 -> post-change value recorded
    # as "C37F-hl" in NOTES-DAYTRADING.md (2026-09-01).
}

# Frozen historical expectations on the PRE-backfill file set (the
# --prepool replay). These never change again: they are the last
# numbers measured on the coverage-biased cache (2026-08-14 epoch)
# AND on the pre-fill-model engine (before a190a72, 2026-09-02): a
# --prepool replay on the current engine will not reproduce them.
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
