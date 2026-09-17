"""UNIVERSE+QUOTES (2026-09-16) -- constraint 1, stage 4: run the EXISTING
wide-net pipeline on the widened universe.

Not one line of plan/rl2/ or plan/wn_*.py is edited. Each stage imports
the incumbent module and REDIRECTS its input/output paths in memory,
which is the only difference between the two runs -- so any change in the
result is the universe, not the code.

  panel     plan/rl2/panel.py      UNI -> uq_out/universe, DAYS -> uq_out/days
  feat      plan/rl2/features.py   DAYS -> uq_out/days,    FEAT -> uq_out/feat
                                   (the volume profile is the FROZEN
                                   train-window cache in plan/rl2/out, NOT
                                   refitted -- refitting it on the wider
                                   universe would let test days inform
                                   their own relative-volume feature)
  table     plan/wn_table.py       FEAT -> uq_out/feat,    OUT  -> uq_out/wn
  model     plan/wn_model.py       via wn_lib.TAB/OUT -> uq_out/wn

plan/rl2/out/panel_stats.json is the one file the incumbent code writes
outside the redirected dirs; it is snapshotted and restored.

Usage:
  python plan/uq_wide.py --stage panel
  python plan/uq_wide.py --stage feat
  python plan/uq_wide.py --stage table
  python plan/uq_wide.py --stage model [--h h30]
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "uq_out"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "rl2"))

UNI = OUT / "universe"      # overridable with --uni (e.g. universe_s3)
DAYS = OUT / "days"
FEAT = OUT / "feat"
WN = OUT / "wn"


def stage_panel():
    import panel
    snap = ROOT / "plan" / "rl2" / "out" / "panel_stats.json"
    bak = OUT / "rl2_panel_stats_backup.json"
    if snap.exists() and not bak.exists():
        shutil.copyfile(snap, bak)
    panel.UNI = UNI
    panel.DAYS = DAYS
    DAYS.mkdir(parents=True, exist_ok=True)
    try:
        panel.main()
    finally:
        shutil.copyfile(OUT / "panel_stats_wide.json", snap) if False else None
        if bak.exists():
            shutil.copyfile(snap, OUT / "panel_stats_wide.json")
            shutil.copyfile(bak, snap)     # rl2's own file restored


def stage_feat():
    import features
    assert (ROOT / "plan" / "rl2" / "out" / "vol_profile.npy").exists(), \
        "the frozen train volume profile must already exist"
    features.DAYS = DAYS
    features.FEAT = FEAT
    FEAT.mkdir(parents=True, exist_ok=True)
    features.main()


def stage_table(smoke=0):
    import wn_table
    wn_table.FEAT = FEAT
    wn_table.OUT = WN
    WN.mkdir(parents=True, exist_ok=True)
    wn_table.build(smoke)


def stage_model(h="h30", seed=0, shuffle=False):
    """CAUTION, and the bug that cost a run: `wn_lib.Table.__init__` has
    `path=TAB` as a DEFAULT ARGUMENT, which is bound once at function
    definition. Reassigning `wn_lib.TAB` afterwards does nothing, and the
    first version of this stage silently refitted the walk-forward on the
    INCUMBENT table and wrote the scores into the widened directory (the
    give-away was train-row counts identical to the 61-name run:
    164,644 / 177,849 / 191,620). The subclass below rebinds the default,
    and the row counts are printed so the substitution is visible."""
    import wn_lib
    base = wn_lib.Table
    tab = WN / "table.npz"

    class WideTable(base):
        def __init__(self, path=tab):
            super().__init__(path)

    wn_lib.TAB = tab
    wn_lib.OUT = WN
    import wn_model
    wn_model.Table = WideTable
    wn_model.OUT = WN
    t = WideTable()
    print(f"widened table: {len(t.dates)} dates, {len(t.syms)} symbols, "
          f"{len(t.date_i):,} rows", flush=True)
    wn_model.stage_wf(h, seed, shuffle)


if __name__ == "__main__":
    a = sys.argv
    if "--uni" in a:
        # A strided subset of dates (every 3rd session, 150 of 448) is a
        # legitimate day-level SUBSAMPLE of the same causal universe: each
        # sampled day carries its FULL cross-section, so the cross-sectional
        # features and the ranking are untouched; only the number of days
        # (and so the power) falls. It exists because the widened universe
        # needs ~97k new symbol-days of 1-minute bars and the strided subset
        # needs 32k.
        UNI = OUT / a[a.index("--uni") + 1]
        DAYS = OUT / (a[a.index("--uni") + 1].replace("universe", "days"))
        FEAT = OUT / (a[a.index("--uni") + 1].replace("universe", "feat"))
        WN = OUT / (a[a.index("--uni") + 1].replace("universe", "wn"))
    st = a[a.index("--stage") + 1] if "--stage" in a else "panel"
    h = a[a.index("--h") + 1] if "--h" in a else "h30"
    if st == "panel":
        stage_panel()
    elif st == "feat":
        stage_feat()
    elif st == "table":
        stage_table(int(a[a.index("--smoke") + 1]) if "--smoke" in a else 0)
    elif st == "model":
        stage_model(h, shuffle="--shuffle" in a)
    else:
        raise SystemExit(f"unknown stage {st}")
