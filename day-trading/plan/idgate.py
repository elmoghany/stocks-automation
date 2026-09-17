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
  * INTEREST-LEG REFINEMENT 2026-09-16 (same day, after the four-fix
    rebuild): halal_pt's 5% leg is now resolved by a four-rung ladder
    (vendor row under an 8%/yr plausibility cap -> EDGAR's own tagged
    interest -> the proven non-operating upper bound -> refuse) and its
    TTM window is defined by revenue alone. New anchors C37F-hf2 /
    HOLD1-hf2 in ROT_EXPECT (shard `hf2`); the -hf rows they replace
    are frozen history, un-reproducible on this engine, and kept
    because --rot asserts what the shard FILES say.
  * REGULAR-SESSION ELIGIBILITY EPOCH 2026-09-16: the rotation anchors
    now live HERE too, in ROT_EXPECT (--rot), with both the pre-epoch
    (RS_CROSS=0) and the new (RS_CROSS=1) values. The S095/Z104 gates
    above are UNAFFECTED by construction -- they walk gappers2 through
    penny_x100, which has no RS_CROSS path -- and were left alone.

Usage:
  python plan/idgate.py                # run all gates
  python plan/idgate.py S095 Z104     # subset
  python plan/idgate.py --rot         # the ROTATION anchors (C37F /
      HOLD1, both epochs) read back out of their shard result files.
      Cheap: it re-reads, it does not re-run. See ROT_EXPECT.
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

# ------------------------------------------------------------------
# ROTATION ANCHORS (plan/rotation_sim.py), checked with --rot
# ------------------------------------------------------------------
# REGULAR-SESSION ELIGIBILITY EPOCH 2026-09-16 (NOTES "MX-SERIES
# RETRACTION #2" and "REGULAR-SESSION ELIGIBILITY EPOCH"). The pool
# files' membership is the grouped-daily REGULAR-SESSION high >= +10%
# over prev_close, so day_candidates letting a PREMARKET cross make a
# name eligible was future-conditioned: the name is in the file only
# because the regular session WILL rally to +10% later. rotation_sim
# now takes the first bar at/after 09:30 with High >= 1.10 x prev_close
# as `cross` (RS_CROSS=1, the new default); RS_CROSS=0 reproduces the
# pre-epoch pool.
#
# THE OLD VALUES ARE KEPT and are still the reference for RS_CROSS=0:
#   C37F-fm  -121,234  (year -79,386 / y2025 -41,848, 2,148 tickets)
#   HOLD1-fm      -903 (year -14,387 / y2025 +13,484,   448 tickets)
# Re-verified 2026-09-16 02:35 on the current engine, shard rs_id:
# C37F-fm = -121,234 EXACT, and /c/tmp/rs/id.log is line-for-line
# identical to the 2026-09-02 fill-model log (/c/tmp/fm/c37.log).
# So RS_CROSS=0 is byte-neutral and the epoch shift below is the
# eligibility rule and only the eligibility rule.
#
# NEW REFERENCE (RS_CROSS=1, POOL_HYGIENE=1 HALAL_STRICT=1 PT_FILED=1),
# shard rs_bench, measured 2026-09-16 02:43:
#   C37F-rs  +28,352  (year +21,910 / y2025 +6,442, 2,048 tickets)
#   HOLD1-rs -50,852  (year -36,329 / y2025 -14,523,  448 tickets)
# C37F's whole pre-epoch loss was premarket entries (691 legs,
# -112,494); the causal universe cannot take them. READ THE CAVEAT IN
# NOTES BEFORE QUOTING C37F-rs AS AN EDGE: 274 of its 2,058 legs fill
# in the eligibility bar itself and carry +31,799 -- more than the
# whole total. The RS_DEFER=1 control (entry in the bar AFTER cross) is
# the number to use for expectancy claims; see ROT_EXPECT below.
#
# HALAL-FIX EPOCH 2026-09-16 (the "hf" rows below; NOTES section of the
# same date). The user's four halal decisions changed BOTH gates:
# strict 10/10/20 (all three legs bind), SIC 6000-6999 a hard FAIL
# (6770 blank checks excepted), the 5% test on TTM interest / TTM
# revenue over the same periods, and a missing statement row refusing
# instead of reading as 0. plan/edgar_backfill.py's tier-precedence debt
# bug was fixed and the EDGAR cache re-extracted in the same epoch, so
# data/pt_halal changed underneath the gate as well.
#
# CONSEQUENCE, STATED PLAINLY: **every pre-2026-09-16 rotation row in
# this table is FROZEN HISTORY.** The "fm" and "rs" rows can no longer
# be reproduced by re-running -- halal_pt is a different function now.
# They are kept because --rot asserts what the shard FILES still say,
# which is a real check (the files have not been rewritten), and
# because the deltas are the measurement. Do not re-run them expecting
# a match; the same treatment EXPECT_PRE already gets.
#
# The new anchors are the RS_DEFER=1 control -- the row the NOTES
# baseline is quoted from -- re-measured on the fixed gate:
#   C37F-hf / HOLD1-hf   RS_CROSS=1 RS_DEFER=1, shard `hf`
#   C37F-hfm             RS_CROSS=0 RS_DEFER=0, shard `hf_fm`
#
# MEASURED 2026-09-16 (logs /c/tmp/hf/{rot_hf,rot_hfm}.log):
#
#   config     total      year     y2025   tkts   $/tkt   traded days
#   C37F-hf   -42,778    -5,954   -36,824  1,337   -32     216 + 144
#   HOLD1-hf  -44,122    -8,518   -35,604    360  -123     216 + 144
#   C37F-hfm -118,826   -48,672   -70,154  1,460   -81     218 + 148
#
#   pre-fix reference (frozen, NOT reproducible on this engine):
#   C37F-df   -14,135   -10,919    -3,216  2,038    -7     445 traded
#   HOLD1-df -103,158   -56,412   -46,746    448  -230     445 traded
#   C37F-fm  -121,234   -79,386   -41,848  2,148   -56     445 traded
#
# READ THE SIGNS CAREFULLY, THEY DO NOT ALL POINT THE SAME WAY:
#   * C37F-hf is WORSE than C37F-df (-42,778 vs -14,135) and its
#     per-ticket loss is unchanged at -$32 vs -$7 -- the gate removed
#     701 tickets and the ones it removed were, on balance, the winners.
#     Year 1 IMPROVED (-10,919 -> -5,954); year 2 got much worse
#     (-3,216 -> -36,824). Do not quote either year alone.
#   * HOLD1-hf is much BETTER than HOLD1-df (+59,036), on 88 fewer
#     tickets: the halal-refused names were net losers for a
#     hold-to-flatten rule.
#   * C37F-hfm -118,826 CONFIRMS that RS_CROSS=0 no longer reproduces
#     -121,234. That is the expected and intended consequence of
#     changing the gate, not a break. The delta is small (+2,408) only
#     because the premarket book dominates that row.
# The traded-day count itself moved (445 -> 360 for the -hf rows):
# 85 days no longer have a single armable name. Ticket counts, not
# totals, are the honest unit of comparison across this epoch.
#
# THREE CAUSES ARE MIXED IN THESE ROWS and are NOT separated: the gate
# doctrine (strict 10/10/20, SIC 6xxx, TTM 5%, missing-row refusal), the
# EDGAR tier-precedence debt fix, and a pt_halal COVERAGE growth (the
# last extract+merge predated the 2026-08-22 m1 backfill; re-running it
# took the cache from 1,393 to 3,677 symbols and 11,990 to 33,555
# EDGAR-side quarters). See the NOTES section of this date.
ROT_EXPECT = {
    # (config, epoch, label): exact expected total
    ("C37F", "fm", "year"): -79_386,       # RS_CROSS=0, pre-epoch
    ("C37F", "fm", "y2025"): -41_848,
    ("HOLD1", "fm", "year"): -14_387,
    ("HOLD1", "fm", "y2025"): +13_484,
    ("C37F", "rs", "year"): +21_910,       # RS_CROSS=1, this epoch
    ("C37F", "rs", "y2025"): +6_442,
    ("HOLD1", "rs", "year"): -36_329,
    ("HOLD1", "rs", "y2025"): -14_523,
    # --- HALAL-FIX EPOCH 2026-09-16, measured this date ---
    # C37F-hf / HOLD1-hf: RS_CROSS=1 RS_DEFER=1, shard `hf`
    ("C37F", "hf", "year"): -5_954,        # 834 tkts, 216 traded days
    ("C37F", "hf", "y2025"): -36_824,      # 503 tkts, 144 traded days
    ("HOLD1", "hf", "year"): -8_518,       # 216 tkts
    ("HOLD1", "hf", "y2025"): -35_604,     # 144 tkts
    # C37F-hfm: RS_CROSS=0 RS_DEFER=0, shard `hf_fm` -- the row that
    # replaces the un-reproducible C37F-fm
    ("C37F", "hfm", "year"): -48_672,      # 917 tkts, 218 traded days
    ("C37F", "hfm", "y2025"): -70_154,     # 543 tkts, 148 traded days
    # --- INTEREST-LEG REFINEMENT 2026-09-16, measured this date ---
    # Same env as `hf` (RS_CROSS=1 RS_DEFER=1 POOL_HYGIENE=1
    # HALAL_STRICT=1 PT_FILED=1), shard `hf2`. What moved is halal_pt's
    # 5% leg ONLY: the TTM window is now defined by revenue alone (an
    # untagged interest line used to silently shorten it, and 17,718 of
    # 33,555 cached quarters carry no interest tag), and the leg is
    # resolved by the four-rung ladder -- vendor row under an 8%/yr
    # plausibility cap, EDGAR's own tagged interest (`intinc_edgar`),
    # the proven non-operating upper bound (`nonop`), then refuse.
    #
    # THE -hf ROWS ABOVE ARE NOW FROZEN HISTORY for the same reason the
    # -df rows are: halal_pt is a different function, so re-running
    # cannot reproduce them. They are kept because --rot asserts what
    # the shard FILES still say, and because the delta IS the
    # measurement.
    #
    #   config      total      year     y2025   tkts   $/tkt   traded
    #   C37F-hf2  -88,784   -47,689   -41,095  1,602   -55.4   236+178
    #   HOLD1-hf2 -75,474   -31,586   -43,888    415  -181.9   236+178
    #   ---- immediately-prior epoch, for the delta ----
    #   C37F-hf   -42,778    -5,954   -36,824  1,337   -32.0   216+144
    #   HOLD1-hf  -44,122    -8,518   -35,604    360  -122.6   216+144
    #
    # Traded days 360 -> 414 and C37F tickets 1,337 -> 1,602: the
    # refinement put 54 more days and 265 more tickets back in play, and
    # BOTH configs got worse -- C37F -$32 -> -$55 per ticket, HOLD1
    # -$123 -> -$182. Read it as one more instance of the standing
    # finding, not as an argument against the fix: on this pool the
    # halal-refused names keep turning out to have been net winners, and
    # NO config is positive per ticket on a causal universe either way.
    # Compliance is not an edge and was never claimed to be one.
    ("C37F", "hf2", "year"): -47_689,      # 923 tkts, 236 traded days
    ("C37F", "hf2", "y2025"): -41_095,     # 679 tkts, 178 traded days
    ("HOLD1", "hf2", "year"): -31_586,     # 237 tkts
    ("HOLD1", "hf2", "y2025"): -43_888,    # 178 tkts
    # --- HALAL-GATE-REVIEW 2026-09-17, shard `hf3` ---
    # Same env as hf/hf2 (RS_CROSS=1 RS_DEFER=1 POOL_HYGIENE=1
    # HALAL_STRICT=1 PT_FILED=1). What moved in halal_pt:
    #   * a missing DEBT or CASH row is looked up in the last filed
    #     quarter that carries it (_last_filed_pt, <= 460 days)
    #     instead of refusing the name on the spot;
    #   * _ttm_pt steps back past a NEWEST quarter that never tagged
    #     revenue instead of summing its 0.0 into TTM revenue, which
    #     understated revenue and inflated the 5% ratio;
    #   * a fourth interest rung, the CASH CEILING: 8%/yr x mean cash
    #     over the window is a PROVEN upper bound on interest income,
    #     so a ceiling under 5% of TTM revenue clears the leg even
    #     when no interest concept is tagged anywhere.
    # TWO DATA CAUSES RIDE ALONG and are NOT separated:
    # companyfacts.zip was refreshed 2026-08-14 -> 2026-09-17 and
    # re-extracted (symbols with >=1 complete quarter 3,677 -> 4,416,
    # 663 symbols gained a newer filed quarter), and pt_halal was
    # re-merged on top of it. The hf2 rows above are therefore FROZEN
    # HISTORY for the same reason the hf rows are: halal_pt is a
    # different function now.
    #
    # MEASUREMENT IN FLIGHT at the time of writing. The first attempt
    # (launched 15:57) was killed by the box at 17:50 with 200/251
    # days of C37F year walked and no result file, under ~40
    # concurrent python processes from other lines; re-launched
    # detached. Until the shard file exists, `--rot` prints
    # "MISSING -- re-run to refresh" for hf3, which is the correct
    # and honest state. Reproduce / refresh with:
    #   HALAL_STRICT=1 PT_FILED=1 POOL_HYGIENE=1 ROTTRADES=1
    #   MASSIVE_TH_INTERVAL=0.25 RS_CROSS=1 RS_DEFER=1 ROTSHARD=hf3
    #   python plan/rotation_sim.py C37F HOLD1
    #
    # PARTIAL CHECKPOINTS, kept because they are CHECKABLE: the
    # walk is deterministic and the re-launched run reproduced the
    # killed run's running total exactly at the first checkpoint.
    # C37F `year`, cumulative $ at each 50-day mark:
    #     50d  -14,913     150d  -35,234
    #    100d  -20,773     200d  -47,806
    # A future re-run that does not hit these four numbers is NOT
    # the same measurement and the epoch note above is wrong.
}
# Which shard file each epoch's rows live in (data/massive/).
ROT_SHARD = {"fm": "rotation_results_rs_id.json",
             "rs": "rotation_results_rs_bench.json",
             "hf": "rotation_results_hf.json",
             "hfm": "rotation_results_hf_fm.json",
             "hf2": "rotation_results_hf2.json",
             "hf3": "rotation_results_hf3.json"}
# The env each epoch's rows MUST have been produced under. pool_hygiene
# and halal_strict are required True for every epoch.
ROT_ENV = {"fm": {"rs_cross": False, "rs_defer": False},
           "rs": {"rs_cross": True, "rs_defer": False},
           "hf": {"rs_cross": True, "rs_defer": True},
           "hfm": {"rs_cross": False, "rs_defer": False},
           "hf2": {"rs_cross": True, "rs_defer": True},
           "hf3": {"rs_cross": True, "rs_defer": True}}
# Reproduce (from day-trading/, one process per epoch):
#   HALAL_STRICT=1 PT_FILED=1 POOL_HYGIENE=1 ROTTRADES=1 \
#     MASSIVE_TH_INTERVAL=0.25 RS_CROSS=0 ROTSHARD=rs_id \
#     python plan/rotation_sim.py C37F
#   ... RS_CROSS=1 ROTSHARD=rs_bench python plan/rotation_sim.py C37F HOLD1
#   ... RS_CROSS=1 RS_DEFER=1 ROTSHARD=hf \
#         python plan/rotation_sim.py C37F HOLD1      # halal-fix epoch
#   ... RS_CROSS=0 RS_DEFER=0 ROTSHARD=hf_fm \
#         python plan/rotation_sim.py C37F            # halal-fix epoch
#   ... RS_CROSS=1 RS_DEFER=1 ROTSHARD=hf2 \
#         python plan/rotation_sim.py C37F HOLD1   # interest-leg 09-16
#   ... RS_CROSS=1 RS_DEFER=1 ROTSHARD=hf3 \
#         python plan/rotation_sim.py C37F HOLD1   # gate-review 09-17


def _rot_gate():
    """Compare the rotation anchors against the shard result files.

    This does NOT re-run the ladder (a full C37F pass is ~90 min); it
    asserts that the files those runs left behind still carry the
    documented numbers, and that each was produced under the env the
    epoch claims. Re-run with the commands above to refresh them."""
    import json
    fails, seen = [], 0
    for epoch, fname in ROT_SHARD.items():
        p = ROOT / "data/massive" / fname
        if not p.exists():
            print(f"rot {epoch:<3} {fname}: MISSING -- re-run to refresh")
            continue
        res = json.loads(p.read_text())
        for (cfg, ep, lab), ref in sorted(ROT_EXPECT.items()):
            if ep != epoch or cfg not in res or lab not in res[cfg]:
                continue
            seen += 1
            v = res[cfg]
            got = v[lab]["total"]
            want = ROT_ENV.get(epoch, {})
            env_ok = (v.get("pool_hygiene") and v.get("halal_strict")
                      and all(bool(v.get(k)) == want[k] for k in want))
            ok = got == ref and env_ok
            print(f"rot {cfg}-{ep} {lab:<6} got {got:>+10,} "
                  f"expect {ref:>+10,}  "
                  f"{'EXACT' if ok else '** FAIL **'}"
                  + ("" if env_ok else "  (WRONG ENV)"))
            if not ok:
                fails.append((f"{cfg}-{ep}", lab, got, ref))
    if not seen:
        print("rot: no shard rows found -- nothing checked")
    return fails


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
    if "--rot" in sys.argv:
        rf = _rot_gate()
        if rf:
            print("\nROTATION ANCHOR FAILURES -- treat as bugs until "
                  "mechanically traced and re-baselined with a dated "
                  "note here + NOTES:")
            for g, lab, got, ref in rf:
                print(f"  {g} {lab}: {got:+,} vs {ref:+,} "
                      f"(delta {got - ref:+,})")
            sys.exit(1)
        print("\nrotation anchors: ALL EXACT")
        return
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
