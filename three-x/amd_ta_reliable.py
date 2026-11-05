"""Which AMD signals, alone or in pairs, are right at least 75% of the time? User's bar, 2026-11-05. No backtest.

Each signal is counted once per episode (firing again within 5 trading days is the same episode). Two measures:
  near: for a buy, the episode starts within 10 trading days of a real swing low of 15%+; for a sell, of a real high. Known only afterwards.
  works: for a buy, the close reaches +15% before -15%, within 63 trading days; for a sell, -15% before +15%. Unresolved cases are left out.
The same "works" test on every day gives the base rate, because AMD rose so much that a buy often works anyway.
Searched on 2025-2026, then checked on 2024, which played no part in the choice. Writes results/amd_ta_reliable.csv.
"""
import contextlib
import io
import itertools

import numpy as np
import pandas as pd

with contextlib.redirect_stdout(io.StringIO()):
    import amd_ta_study as S

MIN_SIGNALS, BAR = 5, 0.75
ERAS = {"2025-26": ("2025-01-01", "2026-11-06"), "2024": ("2024-01-01", "2024-12-31")}
c = S.c


def swings(close):
    v = close.values
    lows, highs, hi, lo, way = [], [], 0, 0, 0
    for i in range(1, len(v)):
        if v[i] > v[hi]:
            hi = i
        if v[i] < v[lo]:
            lo = i
        if way >= 0 and v[i] <= v[hi] * 0.85:
            highs.append(hi)
            way, lo = -1, i
        elif way <= 0 and v[i] >= v[lo] * 1.15:
            lows.append(lo)
            way, hi = 1, i
    return np.array(lows), np.array(highs)


full = c.values
position = {d: i for i, d in enumerate(c.index)}


def works(i, side):
    """True if the move goes the right way first, False if the wrong way first, None if neither within 63 bars."""
    base = full[i]
    for x in full[i + 1:i + 64]:
        if x >= base * 1.15:
            return side == "buy"
        if x <= base * 0.85:
            return side == "sell"
    return None


base_rate = {}
for era, (a, b) in ERAS.items():
    idx = c.loc[a:b].index
    for side in ("buy", "sell"):
        res = [works(position[d], side) for d in idx]
        res = [r for r in res if r is not None]
        base_rate[(era, side)] = float(np.mean(res))
    print(era, "base rate: a buy on any day works", f"{base_rate[(era, 'buy')]:.0%}", "; a sell on any day works", f"{base_rate[(era, 'sell')]:.0%}")


def score(flag, era, side):
    a, b = ERAS[era]
    close = c.loc[a:b]
    on = np.nonzero(flag.reindex(close.index).fillna(False).values)[0]
    starts, last = [], -99
    for i in on:
        if i - last > 5:
            starts.append(i)
        last = i
    lows, highs = swings(close)
    targets = lows if side == "buy" else highs
    near = np.mean([np.min(np.abs(targets - s)) <= 10 for s in starts]) if starts and len(targets) else np.nan
    found = np.mean([np.min(np.abs(np.array(starts) - t)) <= 10 for t in targets]) if starts and len(targets) else 0.0
    out = [works(position[close.index[s]], side) for s in starts]
    out = [r for r in out if r is not None]
    return {"signals": len(starts), "near": near, "found": found, "resolved": len(out), "works": float(np.mean(out)) if out else np.nan}


rows = []
for side, signals in (("buy", S.buy), ("sell", S.sell)):
    names = list(signals)
    combos = [(n,) for n in names] + list(itertools.combinations(names, 2))
    for combo in combos:
        flag = signals[combo[0]] if len(combo) == 1 else signals[combo[0]] & signals[combo[1]]
        s = score(flag, "2025-26", side)
        if s["signals"] < MIN_SIGNALS:
            continue
        check = score(flag, "2024", side)
        rows.append({"side": side, "signal": " + ".join(combo), "size": len(combo), **s, "signals_2024": check["signals"], "near_2024": check["near"], "works_2024": check["works"], "resolved_2024": check["resolved"]})
t = pd.DataFrame(rows)
t.to_csv(S.RES / "amd_ta_reliable.csv", index=False)
pd.set_option("display.width", 210, "display.max_columns", 20, "display.max_rows", 80, "display.max_colwidth", 60)
fmt = lambda v: f"{v:.2f}"
for side in ("buy", "sell"):
    part = t[t.side == side]
    singles, pairs = part[part["size"] == 1], part[part["size"] == 2]
    print(f"\n=== {side.upper()}: tested {len(singles)} single signals and {len(pairs)} pairs with at least {MIN_SIGNALS} signals on 2025-26")
    for label, col in (("near a real turn", "near"), ("works", "works")):
        print(f"{label} at 75%+: singles {(singles[col] >= BAR).sum()}, pairs {(pairs[col] >= BAR).sum()}")
    both = part[(part.near >= BAR) & (part.works >= BAR)]
    print(f"both measures at 75%+: {len(both)}; of those, also at 75%+ on works in 2024 with at least 3 resolved signals: {((both.works_2024 >= BAR) & (both.resolved_2024 >= 3)).sum()}")
    show = ["signal", "signals", "near", "found", "works", "resolved", "signals_2024", "near_2024", "works_2024", "resolved_2024"]
    print("\nbest singles by works")
    print(singles.sort_values(["works", "signals"], ascending=False).head(8)[show].to_string(index=False, float_format=fmt))
    print("\nboth measures at 75%+, most signals first")
    print(both.sort_values(["signals", "works"], ascending=False).head(15)[show].to_string(index=False, float_format=fmt))
    held = part[(part.works >= BAR) & (part.works_2024 >= BAR) & (part.resolved_2024 >= 3) & (part.resolved >= 5)]
    print(f"\nworks at 75%+ in both periods, at least 5 and 3 resolved: {len(held)}")
    print(held.sort_values(["found", "signals"], ascending=False).head(15)[show].to_string(index=False, float_format=fmt))
