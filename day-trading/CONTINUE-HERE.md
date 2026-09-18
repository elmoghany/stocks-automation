# CONTINUE HERE — state saved 2026-09-17 ~21:00 ET (second pause)

The user paused the edge-search loop again ("save the state and cache … continue
later when I tell you to continue agents"). This file is the resume point. Read
it, then `EXPERIMENTS-INDEX.md`, then each `RESUME-*.md`.

## Backup on the big disk

`E:\stocks-automation-cache\2026-09-17\` — full copy of `day-trading/data`
(incl. `data/massive`: m1, m1w, m1o, m1c, m1etf, hd_bars, 1-second tape,
results shards, MANIFESTs ≈ 27.7 GB), the rest of `data/` (halal, EDGAR, news +
filings corpora, paper ledgers ≈ 2.8 GB) and `plan/` incl. every `*_out` results
folder (≈ 2.6 GB). Logs: `robocopy*.log` in that folder. C: was at 35 GB free.
If C: is ever wiped, restore from there; everything else is in git (`main`).

## Paused lines and their resume docs (each has exact relaunch commands)

| line | state at pause | resume doc |
|---|---|---|
| **OPEN-UNIVERSE** | universe (2,532 names/day), m1o cache (378,869 symbol-days, complete), cost model, Tests 1/4/5 + most of Test 2 done; Test 2 shuffle control + OOS stage and Test 3 (limit fills; tape fetch ~3,000/8,243) outstanding | `RESUME-OPEN-UNIVERSE.md` |
| **LIMIT-EXEC** | engine + poison + identity done; audit Parts 0–9; Parts 5.3/5.4/10 pending; REV/veto/h5-h60 chains were mid-run (outputs in `plan/lx_out/` if they finished) | `RESUME-LIMIT-EXEC.md` |
| **DIRECTION-DETECTOR** | not started (two feature modules written, untested); full plan in the doc | `RESUME-DIRECTION-DETECTOR.md` |
| CHAMPION-REPLAY, CATALYST-MINER, CLOSE-MOMENTUM, COST-REBASE, HARNESS-DIAGNOSTIC, UNIVERSE-QUOTES, WIDE-NET, RL-SCOUT v1/v2, VIDEO-MINER, HALAL-AUDITOR, HALAL-GATE-REVIEW | finished; see their audit files | `EXPERIMENTS-INDEX.md` |

Leftover background jobs from the paused lines were killed at the pause (all
resumable; commands in the resume docs). Still running on purpose: the halal
identity re-run `hf3` (detached python; `plan/idgate.py --rot` picks it up when
`data/massive/rotation_results_hf3.json` lands) and the daily paper session on
Task Scheduler.

## State of the search (numbers are honest-harness, measured or flat cost as marked)

- Verdict from HARNESS-DIAGNOSTIC stands: the harness is honest; the same-day,
  long-only, market-order frame's zero-information baseline is exactly the fee;
  the overnight premium replicates; buy-and-hold of the halal universe on $100k
  = $1.1–1.9k/month.
- CHAMPION-REPLAY: 91% of C37's $774k headline was bar coverage; premarket
  entries were worth +$150k to REMOVE (a premarket entry on the honest scanner
  list ≈ −$615/ticket); the champion's ranking key is negative, its stop is
  negative, its exit stack and "coil as an order" are positive; best row R4
  (+$69/tkt flat, +$3,035/mo, 5 legs carry 119%, −$90 measured). A perfect
  DIRECTION oracle re-ranking the same machinery would earn +$65k/mo flat and
  +$162/tkt at the measured toll — the frame can carry the target; direction
  (IC 0.05 achieved vs 0.188 needed) is the missing piece → DIRECTION-DETECTOR.
- OPEN-UNIVERSE: breadth LOWERS the ceiling (+$1,980 → +$1,015/mo zero-cost);
  depth matters (+$25/tkt edge on the 600 deepest books, ≈0 beyond); measured
  toll 4.3 bps/side on deep books but 15 bps/side at the 09:35–09:45 decisions
  the policies actually make; present-day halal list is worth $0.9–1.5k/mo to a
  RANDOM picker vs point-in-time (a retroactive-list inflation to remember).
- LIMIT-EXEC: resting both legs takes the random baseline −$27 → −$2…−$3.5/tkt
  flat (≈ 0) but −$24 measured; skill does not survive the fill (+$17 → +$1);
  closest −$5/tkt, −$653/mo.
- Best honest net numbers overall: CHAMPION-REPLAY R4 +$3,035/mo flat (not
  measured); CATALYST-MINER +$674 flat → +$3 measured; nothing near $7,500.

## Halal (live)

Gate repaired 2026-09-16/17; live list = 472 names (476 rebuilt minus 4 fund
tickers); user rulings 2026-09-17: thresholds stay strict 10/10/20; MSFT/GOOGL
kept (entertainment leg deferred). Open: five SIC mis-codes (IDCC, RGLD, TFPM,
TPL, USIO); currency bug on foreign filers (2 names); benchmark row hf3 pending.
Live benchmark in prompt/skill: −$215/traded day (C37F-hf2) until hf3 lands;
NOTE it is a GROSS number (COST-REBASE) — the measured-cost expectation for C37
rules is far worse.

## Open questions for the user (unchanged from the first pause, plus two)

1. Target: $7,500/mo is not reachable in the same-day/market-order frame on $100k
   (measured five ways). Re-set the target, relax same-day, add capital, or stop?
2. Execution: switch live to limit-at-bid entries + measured costs (largest lever,
   but LIMIT-EXEC shows the zero-information baseline only reaches ≈ $0, not +).
3. Live benchmark correction (gross vs measured) and whether to keep paper trading
   C37 rules at all.
4. Premarket entries live: kept, reported separately; the honest measurement says
   ≈ −$615/ticket — stop entering before 09:30?
5. Halal: SIC mis-codes; ATHR; the currency bug fix (do it).
6. NEW: DIRECTION-DETECTOR is the one line with a measured upside ceiling
   (+$162/tkt at measured toll if direction were predictable) — run it next.
7. NEW: the 1-second tape / m1o / m1c caches are large and on E:; keep C: free.

## Resume checklist

**2026-09-18 19:25: EVERYTHING IS OFF.** The in-session backup cron was cancelled and the
Task Scheduler tasks `\Stocks\C37MorningLaunch` and `\Stocks\C37Watchdog` were DISABLED
(`Enable-ScheduledTask -TaskPath '\Stocks' -TaskName C37MorningLaunch` / `C37Watchdog` to
resume daily paper trading). `HalalUniverseRefresh` (monthly) is still enabled.


`git pull` → read this file → `RESUME-*.md` → relaunch each line on Opus with
its name, autonomy rules, index-row rule, and adversarial audit before believing
any positive number → re-create the in-session 06:45 backup cron → re-arm the
/loop with the original mandate.
