"""Score forecast CSVs on the 2024-01..2024-06 holdout (inside the allowed training period): mean abs error of the predicted
vs realised h-day log return, and Spearman IC. Usage: python holdout.py file.csv [file2.csv ...]; prints one line per file."""
import sys

import numpy as np
import pandas as pd

from common import amd, idx

c = amd.close
for p in sys.argv[1:]:
    f = pd.read_csv(p, parse_dates=["date"])
    out = []
    for h in (5, 10, 20):
        g = f[f.horizon == h].set_index("date").pred_ret
        real = (c.shift(-h) / c - 1).reindex(g.index)
        ok = real.notna() & (g.index <= "2024-06-30")
        a, b = np.log1p(g[ok]), np.log1p(real[ok])
        out.append((h, float((a - b).abs().mean()), float(a.rank().corr(b.rank()))))
    mae = float(np.mean([o[1] for o in out]))
    print(f"{p}\tMAE {mae:.4f}\t" + "\t".join(f"h{h} mae {m:.4f} ic {i:+.2f}" for h, m, i in out))
