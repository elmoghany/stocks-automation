"""THE DECISIVE TEST (2026-08-07): what does C35 actually earn if the
candidate is only allowed to trade once a CAUSAL rvol gate says it
qualifies?

The backtest selects candidates with FULL-DAY volume / 50-day average
>= 5 -- unknowable at 7AM. rvol_causal.py showed a projected measure
(cumulative / intraday-profile-fraction) recalls only ~32% of
qualifying names at 07:00, rising to 74% by 10:30. So live cannot
trade these names from the open.

Here each committed candidate is replayed with `entry_start` set to
the FIRST MINUTE at which its own projected rvol crosses the gate --
computed causally from its own bars and a market-wide per-minute
volume profile. Everything else is C35 unchanged. The gap versus the
$1,163,538 baseline is the honest cost of causality.

Also reports a fixed-time bracket (entries barred before 08:00 /
09:45 / 10:30) so the shape of the decay is visible.
"""

import copy
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plan"))
_spec = importlib.util.spec_from_file_location(
    "penny_x100", ROOT / "plan" / "penny_x100.py")
x = importlib.util.module_from_spec(_spec)
sys.modules["penny_x100"] = x
_spec.loader.exec_module(x)

M1 = ROOT / "data/massive/m1"
GATE = 5.0
PROFILE_F = ROOT / "data/massive/minute_volume_profile.json"


def build_minute_profile():
    """Market-wide mean share of a day's volume printed BY each minute
    of the session (7:00-16:00), from the cached 1-minute bars."""
    if PROFILE_F.exists():
        return {int(k): v for k, v in
                json.loads(PROFILE_F.read_text()).items()}
    acc = defaultdict(list)
    n = 0
    for f in M1.glob("*.csv"):
        try:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
        except Exception:
            continue
        if len(df) < 60 or df.index.tz is None:
            continue
        df.index = df.index.tz_convert("America/New_York")
        tot = float(df["Volume"].sum())
        if tot <= 0:
            continue
        n += 1
        mins = df.index.hour * 60 + df.index.minute
        cum = df["Volume"].cumsum() / tot
        seen = {}
        for m, c in zip(mins, cum):
            seen[int(m)] = float(c)
        run = 0.0
        for m in range(7 * 60, 16 * 60 + 1):
            run = seen.get(m, run)
            acc[m].append(run)
    prof = {m: sum(v) / len(v) for m, v in acc.items() if v}
    PROFILE_F.write_text(json.dumps({str(k): v for k, v in prof.items()}))
    print(f"built minute profile from {n:,} symbol-days", flush=True)
    return prof


PROFILE = build_minute_profile()


def gate_time(df, avg50):
    """First minute where PROJECTED full-day rvol crosses the gate."""
    if avg50 is None or avg50 <= 0:
        return None
    d = df.copy()
    d.index = d.index.tz_convert("America/New_York") \
        if d.index.tz is not None else d.index
    mins = d.index.hour * 60 + d.index.minute
    cum = d["Volume"].cumsum()
    for m, c in zip(mins, cum):
        frac = PROFILE.get(int(m))
        if not frac or frac <= 0.001:
            continue
        if (float(c) / frac) / avg50 >= GATE:
            return dtime(int(m) // 60, int(m) % 60)
    return None


BASE = dict(x.BYID["S095"])          # C35


def run(label, mode):
    """mode: None = baseline, a dtime = fixed start, 'causal' = per-day."""
    spec = copy.deepcopy(BASE)          # buy_set is a set -> not JSON-safe
    total, days, gated_out, times = 0.0, 0, 0, []
    _orig = x.sim_window

    def wrapper(w, c, sp, sub=None):
        nonlocal total, days, gated_out
        if mode == "causal":
            df = x.get_lazy(c["symbol"], str(w.index[0].date()))
            avg50 = (c.get("volume") / c["rvol"]) if c.get("rvol") else None
            gt = gate_time(df, avg50) if df is not None else None
            if gt is None:
                gated_out += 1
                return []                      # never qualifies -> no trade
            times.append(gt)
            sp.setdefault("sim", {})["entry_start"] = gt
        elif isinstance(mode, dtime):
            sp.setdefault("sim", {})["entry_start"] = mode
        tr = _orig(w, c, sp, sub)
        if tr:
            days += 1
        total += sum(t["pnl"] for t in tr)
        return tr

    x.sim_window = wrapper
    for lab in ("year", "y2025"):
        x.run_experiment(dict(spec), lab)
    x.sim_window = _orig
    extra = ""
    if mode == "causal":
        extra = f" | never qualified: {gated_out} days"
        if times:
            mm = sorted(t.hour * 60 + t.minute for t in times)
            med = mm[len(mm) // 2]
            extra += f" | median gate time {med//60:02d}:{med%60:02d}"
    print(f"{label:<34} ${total:>+12,.0f}  {days:>3} traded days{extra}",
          flush=True)
    return total


print("\nC35 UNDER A CAUSAL rvol GATE (2 backtest years, $100k/day cap)\n")
base = run("baseline (backtest selection)", None)
for t in (dtime(8, 0), dtime(9, 45), dtime(10, 30)):
    v = run(f"entries barred before {t.strftime('%H:%M')}", t)
    print(f"{'':34}  ({100*v/base:.0f}% of baseline)")
v = run("CAUSAL per-day projected gate", "causal")
print(f"{'':34}  ({100*v/base:.0f}% of baseline)  <- honest live expectation")
