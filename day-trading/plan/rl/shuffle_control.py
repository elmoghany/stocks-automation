"""RL-SERIES (2026-09-16): make the shuffled-labels control interpretable.

WHAT WENT WRONG THE FIRST TIME. `DayData.shuffled` permutes each symbol-day's
1-minute log returns and rebuilds the price path. A permutation preserves the
SUM of the returns, so the day's terminal price is unchanged while the path
between is randomized -- a Brownian bridge pinned at both ends. Entries at
the randomly-depressed points of such a path are mechanically pulled back up
to the fixed endpoint. Measured directly on 60 test days, with NO agent and
NO learning, one $15k ticket opened at a random eligible minute and held:

                       real panel      permuted panel
    hold 30 min        -$44.91         -$2.94
    hold 120 min       -$50.19         +$96.24
    hold to flatten    -$44.46         +$235.21   per ticket

So a positive P&L on the permuted panel is a property of the PANEL, not
evidence that the agent is reading the future. PPO-shuffle's +$280/ticket on
test sits essentially on top of the +$235/ticket that a scripted
buy-and-hold gets on the same panel.

THE CORRECT TEST is therefore not "is the shuffled agent positive" but
"does the shuffled agent BEAT ITS OWN PANEL'S BASELINES". This script
computes RANDOM x N and BUYFIRST on the shuffled panels, on the same splits
and with the same costs, so the RL rows can be read against them.

  python plan/rl/shuffle_control.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import env as E                                             # noqa: E402
import honesty as H                                         # noqa: E402

N_RANDOM = 10
SPLITS = ("val", "test", "extra")


def main():
    t0 = time.time()
    sp = E.split_files()
    out = {"n_random": N_RANDOM, "note": __doc__}
    # the normalizer must still come from a TRAIN panel, shuffled the same way
    tr = E.Dataset(sp["train"], transform="shuffle", seed=11, label="train")
    norm = tr.fit_norm()
    out["train"] = {}
    for split in SPLITS:
        if not sp.get(split):
            continue
        ds = E.Dataset(sp[split], transform="shuffle", seed=11, label=split)
        ds.set_norm(norm)
        rows = []
        for s in range(N_RANDOM):
            rows.append(E.run_epoch(
                E.TicketEnv(ds, norm=norm, shuffle_days=False, seed=s),
                E.random_policy(seed=s, p_trade=0.10), record=True))
        eager = [E.run_epoch(
            E.TicketEnv(ds, norm=norm, shuffle_days=False, seed=s),
            E.random_policy(seed=s, p_trade=0.35), record=True)
            for s in range(N_RANDOM)]
        bf = E.run_epoch(E.TicketEnv(ds, norm=norm, shuffle_days=False),
                         E.buy_first_policy, record=True)
        out[split] = {
            "RANDOM_shuffled": H.agg(rows),
            "RANDOM_EAGER_shuffled": H.agg(eager),
            "BUYFIRST_shuffled": {k: bf[k] for k in
                                  ("total_pnl", "pnl_per_ticket", "tickets",
                                   "sharpe_daily_ann", "max_dd")},
        }
        print(split,
              "random", round(out[split]["RANDOM_shuffled"]["total_pnl"]["mean"]),
              "eager", round(out[split]["RANDOM_EAGER_shuffled"]["total_pnl"]["mean"]),
              "buyfirst", round(bf["total_pnl"]),
              f"{time.time()-t0:.0f}s", flush=True)
    p = E.OUT / "shuffle_control.json"
    p.write_text(json.dumps(out, indent=1))
    print("wrote", p)


if __name__ == "__main__":
    main()
