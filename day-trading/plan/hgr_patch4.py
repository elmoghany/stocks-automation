"""HALAL-GATE-REVIEW: register the `hf3` rotation epoch in idgate.py."""
from pathlib import Path

p = Path(__file__).resolve().parent / "idgate.py"
s = p.read_text(encoding="utf-8")

old = ('    ("HOLD1", "hf2", "y2025"): -43_888,    # 178 tkts\n}')
new = (
    '    ("HOLD1", "hf2", "y2025"): -43_888,    # 178 tkts\n'
    '    # --- HALAL-GATE-REVIEW 2026-09-17, shard `hf3` ---\n'
    '    # Same env as hf/hf2 (RS_CROSS=1 RS_DEFER=1 POOL_HYGIENE=1\n'
    '    # HALAL_STRICT=1 PT_FILED=1). What moved in halal_pt:\n'
    '    #   * a missing DEBT or CASH row is looked up in the last filed\n'
    '    #     quarter that carries it (_last_filed_pt, <= 460 days)\n'
    '    #     instead of refusing the name on the spot;\n'
    '    #   * _ttm_pt steps back past a NEWEST quarter that never tagged\n'
    '    #     revenue instead of summing its 0.0 into TTM revenue, which\n'
    '    #     understated revenue and inflated the 5% ratio;\n'
    '    #   * a fourth interest rung, the CASH CEILING: 8%/yr x mean cash\n'
    '    #     over the window is a PROVEN upper bound on interest income,\n'
    '    #     so a ceiling under 5% of TTM revenue clears the leg even\n'
    '    #     when no interest concept is tagged anywhere.\n'
    '    # TWO DATA CAUSES RIDE ALONG and are NOT separated:\n'
    '    # companyfacts.zip was refreshed 2026-08-14 -> 2026-09-17 and\n'
    '    # re-extracted (symbols with >=1 complete quarter 3,677 -> 4,416,\n'
    '    # 663 symbols gained a newer filed quarter), and pt_halal was\n'
    '    # re-merged on top of it. The hf2 rows above are therefore FROZEN\n'
    '    # HISTORY for the same reason the hf rows are: halal_pt is a\n'
    '    # different function now.\n'
    '    #\n'
    '    # MEASUREMENT IN FLIGHT at the time of writing. The first attempt\n'
    '    # (launched 15:57) was killed by the box at 17:50 with 200/251\n'
    '    # days of C37F year walked and no result file, under ~40\n'
    '    # concurrent python processes from other lines; re-launched\n'
    '    # detached. Until the shard file exists, `--rot` prints\n'
    '    # "MISSING -- re-run to refresh" for hf3, which is the correct\n'
    '    # and honest state. Reproduce / refresh with:\n'
    '    #   HALAL_STRICT=1 PT_FILED=1 POOL_HYGIENE=1 ROTTRADES=1\n'
    '    #   MASSIVE_TH_INTERVAL=0.25 RS_CROSS=1 RS_DEFER=1 ROTSHARD=hf3\n'
    '    #   python plan/rotation_sim.py C37F HOLD1\n'
    '}')
assert s.count(old) == 1, "expect"
s = s.replace(old, new)

old2 = '             "hf2": "rotation_results_hf2.json"}'
new2 = ('             "hf2": "rotation_results_hf2.json",\n'
        '             "hf3": "rotation_results_hf3.json"}')
assert s.count(old2) == 1, "shard"
s = s.replace(old2, new2)

old3 = '           "hf2": {"rs_cross": True, "rs_defer": True}}'
new3 = ('           "hf2": {"rs_cross": True, "rs_defer": True},\n'
        '           "hf3": {"rs_cross": True, "rs_defer": True}}')
assert s.count(old3) == 1, "env"
s = s.replace(old3, new3)

old4 = '#         python plan/rotation_sim.py C37F HOLD1   # interest-leg 09-16'
new4 = (old4 + '\n'
        '#   ... RS_CROSS=1 RS_DEFER=1 ROTSHARD=hf3 \\\n'
        '#         python plan/rotation_sim.py C37F HOLD1   # gate-review 09-17')
assert s.count(old4) == 1, "cmd"
s = s.replace(old4, new4)

p.write_text(s, encoding="utf-8")
print("patched idgate")
