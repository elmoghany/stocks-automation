# RESUME — LIMIT-EXEC (paused 2026-09-17 ~20:50 ET)

Agent line: **LIMIT-EXEC**. Audit: `limit-exec-audit.md` (Parts 0–4, 5.1, 5.2, 6, 7, 8, 9 done;
verdict table preliminary; Parts 5.3, 5.4, 10 and the h5/h60 sensitivity PENDING).
Code: `plan/lx_engine.py`, `plan/lx_frame.py`, `plan/lx_tables.py`, `plan/lx_orb.py`,
`plan/lx_relabel.py`, `plan/lx_poison.py`, `plan/lx_ident.py`, `plan/lx_report.py`.
Engine hook: `day-trading.py::simulate_trades` (`exit_mode`, `limit_entry`, `limit_exit`;
`entry_mode="limit_bid"` / `exit_mode="limit_ask"` sugar) — identity 507/507 flags-off,
`plan/idgate.py --rot` ALL EXACT.

## Findings so far (one paragraph)

End-to-end resting execution (bid 3 min cancel / ask 3 min, sized to the printed volume,
causal half-spread from `cr_cost`) takes the frame's zero-information baseline from
**−$27.36 ± 2.7 to −$3.50 ± 2.9 a ticket** (tick ladders −$1.91 ± 2.6, ex-best +$3,500) under the
flat convention (passive fills free), i.e. to ≈ $0 — but either leg alone is only worth its own fee
(−$12…−$19), and under COST-REBASE's measured convention (square-root impact charged on passive
fills too) the same ladders are −$24. Price improvement is +9.5 bps at entry / +6 bps at exit;
30-minute adverse selection on the entry side is ≈ −6.5 bps (net ≈ +3), the exit side has none
(clock-decided), so UNIVERSE-QUOTES' "cancels to a bp" is refuted in direction, confirmed in size.
The demonstrated skill does not survive the fill: WIDE-NET's +$17 edge becomes +$1…+$3 with both legs
resting (inverted 3rd pct, shuffled on the mean); rest-then-cross keeps +$11.76 (100th pct) at
−$5.21/ticket, −$653/month — the line's closest miss; the end-to-end-fill refit learns nothing
(1–5 LightGBM iterations, edge −$0.60). C37's ORB "buy the runner" is the 0th-percentile pick under a
resting bid (the fade fills). Honesty battery PASS (P1 0/8,442 leaks, P2 91 % moved, FastCost ==
CostModel 963/963 + 432/432, fills bounded by their limits 5,755/5,755). FAIL against $7,500/month.

## State per Part

| Part | status | file / output |
|---|---|---|
| 0 instrument | done | audit |
| 1 engine + fill rule | done | `plan/lx_engine.py` |
| 2 identity gates | done | `plan/lx_out/frame_ident.json`, `tables_ident.json`, `engine_identity.json` |
| 3 frame ladders (pass A 12 cfg × 30 seeds; pass B 26 cfg × 10 seeds) | done | `frame_ladderA_h30.json`, `frame_ladderB_h30.json` |
| 3.x h5 / h60 sensitivity | **RUNNING** (h5 150/448 at 20:43; h60 queued in the same chain) | `frame_sens_h5.json`, `frame_sens_h60.json` (logs `frame_sens_h5.log` / `_h60.log`, UTF-16) |
| 4 adverse selection | done | inside the frame jsons (`decomp`) |
| 5.1 wn model / UQ relabel | done | `tables_wn.json` |
| 5.2 end-to-end refit | done | `lx_label_h30.npz`, `lx_relabel_scores_s{0,1}.npy`, `tables_wn_refit.json` |
| 5.3 REV 15:30 k7 | **RUNNING** (100/224 at 20:43, stride 2, 10 seeds) | `tables_rev.json` (log `tables_rev2.log`, UTF-8) |
| 5.4 catalyst veto | **RUNNING** (250/379 at 20:43, 30 seeds) | `tables_veto.json` (log `tables_veto.log`, UTF-16) |
| 6 ORB wide + pool | done | `orb_wide.json`, `orb_pool.json` |
| 7 engine hook | done | `day-trading.py`, `plan/lx_ident.py` |
| 8 live-feasibility note | done | audit |
| 9 honesty battery | done | `poison.json` + audit |
| 10 conclusions | preliminary in audit; finalize after 5.3/5.4/h5/h60 | — |
| NOTES entry, index row | short "paused" entries written; replace when final | `NOTES-DAYTRADING.md`, `EXPERIMENTS-INDEX.md` |

## Relaunch commands (only if the running chains died; check the logs first)

```
cd C:\cornell\stocks-automation\day-trading
python plan/lx_tables.py --stage rev  --seeds 10 --workers 1 --stride 2 --tag rev --ladders "mkt/mkt,bid-rest3-cancel/mkt,bid-rest3-mkt/tick3,bid-rest3-cancel/ask-rest3"
python plan/lx_tables.py --stage veto --seeds 30 --workers 1 --tag veto
python plan/lx_frame.py --stage ladder --seeds 30 --workers 1 --hold 5  --tag sens --names "mkt/mkt,bid-rest3-cancel/ask-rest3,tick5-cancel/tick5"
python plan/lx_frame.py --stage ladder --seeds 30 --workers 1 --hold 60 --tag sens --names "mkt/mkt,bid-rest3-cancel/ask-rest3,tick5-cancel/tick5"
# render any landed json into markdown:
python plan/lx_report.py --frame frame_ladderA_h30.json --wn tables_wn.json --rev tables_rev.json --veto tables_veto.json --orb orb_wide.json,orb_pool.json
```
Then splice the rendered tables into `limit-exec-audit.md` at the **PENDING** markers (Parts 5.3,
5.4, 10 and the verdict table), finalize the NOTES entry and the index row, commit + push.
The refit needs `C:\cornell\venvs\rl\Scripts\python.exe` (lightgbm); everything else runs on the
default python. Logs written through PowerShell `>` are UTF-16 (`iconv -f UTF-16 -t UTF-8`).

## Caches and outputs

| path | what | size |
|---|---|---|
| `plan/lx_out/` | every json this line quotes (+ `_render_*.md`, logs) | small (< 50 MB) |
| `data/massive/lx_tape/{date}.npz` (+ `{date}_pool.npz`) | per-day npz mirror of the 1-second tape, built on first use | ~8 MB/day, 448 wide days + 111 pool days |
| `data/massive/trades/{SYM}_{DATE}.json.gz` | the 1-second tape (UNIVERSE-QUOTES + COST-REBASE), 71,713 symbol-days | ~1.6 GB |
| `data/massive/cost1/` | per-minute statistics for `cr_cost` / `FastCost`, 27,604 symbol-days | ~0.6 GB |
| `plan/uq_out/` | UNIVERSE-QUOTES scores/labels reused here (`relabel_scores_*`, `relabel_scores_shuf_s1.npy`) | unchanged |
| pre-edit engine copy for `plan/lx_ident.py` | `C:\Users\MYPC~1\AppData\Local\Temp\dt_pre_limitexec.py` (== commit 6ff91b1's `day-trading.py`) | 0.6 MB |

## Ranked next (after the pending rows land)

1. Live paper measurement of the two numbers no aggregate can settle: the half-spread at the post
   and our share of printed volume (`part`), with per-fill ledgers (Part 8 item 6).
2. Rest-then-cross for the wide-net ranker (`bid-rest3-mkt/tick3`, −$653/month) is the only shape
   where a ranker's edge survives; trade later in the day where the measured toll is lowest.
3. Do not post deeper; do not chase; three to five minutes is the plateau.
