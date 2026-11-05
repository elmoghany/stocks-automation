"""Do more AMD signals pass 75% in both 2025-26 and 2024 than luck would give? And what dates sit behind the best survivors?

Runs the amd_ta_brainstorm.py search with the outcomes rotated by a random shift, then applies the same 2024 check, and compares the counts
with the real data. Prints each top survivor's signal dates, because signals bunched in one market fall are really one or two events.
"""
import numpy as np
import pandas as pd

import amd_ta_brainstorm as B

SHIFTS = 12
rng = np.random.default_rng(21)
idx, BAR, MIN_CHECK = B.idx, B.BAR, B.MIN_N_CHECK


def both(side, table, shift):
    wide, tight = B.outcomes[side]["wide"], B.outcomes[side]["tight"]
    found, _ = B.score_arrays(side, table, wide, tight, shift)
    w, t = np.roll(wide, shift), np.roll(tight, shift)
    m = B.masks["check"]
    pass_wide, pass_tight = 0, 0
    for combo, n, rw, nw, rt, nt in found:
        flag = table[combo[0]].reindex(idx).fillna(False).values.astype(bool) & m
        if len(combo) == 2:
            flag = flag & table[combo[1]].reindex(idx).fillna(False).values.astype(bool)
        s = B.starts_of(flag)
        cw, ct = w[s], t[s]
        cw, ct = cw[np.isfinite(cw)], ct[np.isfinite(ct)]
        if rw >= BAR and len(cw) >= MIN_CHECK and cw.mean() >= BAR:
            pass_wide += 1
        if rt >= BAR and len(ct) >= MIN_CHECK and ct.mean() >= BAR:
            pass_tight += 1
    return len(found), pass_wide, pass_tight


for side, table in (("buy", B.buy), ("sell", B.sell)):
    real = both(side, table, 0)
    fake = [both(side, table, int(rng.integers(40, B.n_all - 40))) for _ in range(SHIFTS)]
    print(f"{side}: real passes 2025-26 {real[0]}, also 2024 wide {real[1]}, tight {real[2]}", flush=True)
    print(f"  rotated, 2025-26: {sorted(x[0] for x in fake)}", flush=True)
    print(f"  rotated, also 2024 wide: {sorted(x[1] for x in fake)}; real beats {sum(real[1] > x[1] for x in fake)} of {SHIFTS}", flush=True)
    print(f"  rotated, also 2024 tight: {sorted(x[2] for x in fake)}; real beats {sum(real[2] > x[2] for x in fake)} of {SHIFTS}", flush=True)

t = pd.read_csv(B.RES / "amd_ta_brainstorm.csv")
picks = []
for side in ("buy", "sell"):
    part = t[t.side == side]
    tight = part[(part.tight >= BAR) & (part.tight_2024 >= BAR) & (part.tight_n_2024 >= MIN_CHECK)].sort_values(["n", "tight_n_2024"], ascending=False).head(8)
    wide = part[(part.wide >= BAR) & (part.wide_2024 >= BAR) & (part.wide_n_2024 >= MIN_CHECK)].sort_values(["n", "wide_n_2024"], ascending=False).head(8)
    picks += [(side, r) for r in pd.concat([tight, wide]).drop_duplicates("signal").itertuples()]
for side, r in picks:
    table = B.buy if side == "buy" else B.sell
    combo = r.signal.split(" + ")
    flag = table[combo[0]].reindex(idx).fillna(False).values.astype(bool)
    if len(combo) == 2:
        flag = flag & table[combo[1]].reindex(idx).fillna(False).values.astype(bool)
    print(f"\n{side}: {r.signal} | 2025-26 wide {r.wide:.2f} tight {r.tight:.2f} of {r.n} | 2024 wide {r.wide_2024:.2f} tight {r.tight_2024:.2f} of {r.n_2024}")
    for era in ("main", "check"):
        s = B.starts_of(flag & B.masks[era])
        w, ti = B.outcomes[side]["wide"][s], B.outcomes[side]["tight"][s]
        print("  " + " ".join(f"{idx[i].strftime('%y-%m-%d')}{'+' if b == 1 else '-' if b == 0 else '?'}{'+' if a == 1 else '-' if a == 0 else '?'}" for i, a, b in zip(s, w, ti)))
print("\nEach date is followed by tight then wide: + right, - wrong, ? not yet resolved.")
