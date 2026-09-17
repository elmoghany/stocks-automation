# CONTINUE HERE — state saved 2026-09-17 ~00:30 ET

The user paused the edge-search loop ("let's continue later. stop here for now").
This file is the resume point. Read it, then `EXPERIMENTS-INDEX.md`, then the
NOTES sections it links.

## Where things stand (one paragraph)

The loop target was net ≥ $7,500/month on $15k same-day tickets, halal-PASS
names only, no lookahead. Twelve research lines were run on an honest harness
(full-coverage minute bars, hygiene-cleaned pool, regular-session eligibility,
realistic gap-through fills, point-in-time halal, poison tests, seeded controls,
foresight positive controls). **Nothing came close, and HARNESS-DIAGNOSTIC
settled why: the harness is honest and the frame is empty.** The overnight
premium replicates on our own data (halal names +8.3 bp/day close-to-open,
−1.0 bp/day intraday, negative both years); buy-and-hold of the halal universe
on $100k is $1.1–1.9k/month — the entire equity premium on this capital; the
harness re-priced all 20 live trades within $7 of the live book (slightly
generous); a random ticket at zero cost earns ≈ $0, so the baseline loss is
exactly the fee. Break-even needs 6.7% of perfect 30-minute foresight, the
target 18.6%, demonstrated skill 2–6%. Even at zero cost the searchable ceiling
in this frame is ≈ +$1.4k/month above random (19% of target).

## Best honest numbers (net, OOS, controls passed unless noted)

| line | best | $/month net | note |
|---|---|---|---|
| CATALYST-MINER | fresh earnings + green at 09:35 → 10:35 | +$674 (flat cost) → **+$3 under measured cost** | post-hoc; 11× short |
| RL-SCOUT v2 | rule-search seed 0 | +$355 | 1 of 5 seeds; do not trade |
| WIDE-NET | rvol/breadth rule 09:45 | +$314 | 31 tickets |
| VIDEO-MINER | green-on-red rel. strength | +$267 (flat) → −$82/tkt measured | dies ex-best-day |
| UNIVERSE-QUOTES | rank-for-the-fill limit policy | +$7 | 100th pct, but 3rd pct under measured cost |
| CLOSE-MOMENTUM | late-day reversal k=7 | −$1,925 (**+$1,949 at zero cost**) | largest gross edge |
| COST-REBASE | wide-net refit on measured label | −$559 | best under measured costs |

## The two findings that change the accounting (COST-REBASE, 2026-09-17)

1. **C37F — the live benchmark — pays no toll.** `rotation_sim` applies
   `slippage_bps` only when a config sets `slip`; C37F never did. Every
   C37/C37F/MX/T/XH row is GROSS. Under measured costs C37F-hf2 is
   −$247/ticket (−$18k/month). The live benchmark line (−$215/day) is therefore
   too kind; the honest live expectation for C37 rules is far worse.
2. **Measured cost ≈ the flat 10 bps after all.** Half-spread is 2.77 bps
   (2–5× below 10) but square-root impact for a $15k ticket is ~9 bps at the
   median name; total 12.05 bps/side, above 10 on 63% of fills. Break-even IC
   at 7 tickets/day is 0.188 (achieved 0.033).

## Frame ablation — where the money is (HARNESS-DIAGNOSTIC control 5)

| constraint relaxed | Δ best policy $/mo | Δ random $/mo | reading |
|---|---:|---:|---|
| market orders → measured limit fills | +3,190 | +3,189 | pure fee; the biggest lever |
| same-day only → overnight allowed | +1,009 | +1,893 | drift, not edge; only window that pays |
| long-only → short allowed | +880 | 0 | luck of a bigger search; no edge |
| halal screen removed | −709 | −686 | **halal HELPS** |
| costs → zero | +4,412 | +4,411 | fee |

## Open questions for the user (answer these to resume)

1. **Target.** $7,500/month is not reachable in the same-day, long-only,
   market-order frame on $100k. Options: (a) re-set the target to the frame's
   honest ceiling (break-even to ~+$2k/month with limit fills); (b) relax the
   same-day rule (1–5-session holds reach the equity premium, ≈ +$1.2k/month on
   feasible capital — still not $7,500); (c) more capital (the equity premium
   scales; $7,500/month buy-and-hold needs ~$450–700k); (d) stop.
2. **Execution model.** Switch live paper (and the backtest convention) from
   market fills to limit-at-bid entries with the measured cost model? (+$3,190/mo
   of fee recovered; requires the watcher to post/cancel limits — code exists in
   plan/uq_*.py for the sim side only.)
3. **Live benchmark correction.** The prompt/skill benchmark (−$215/day) is a
   gross number; the honest C37 expectation under measured costs is ≈ −$18k/month.
   Keep paper trading C37 as-is, switch it to HOLD1/limit fills, or pause it?
4. **Premarket.** Live premarket entries have no honest backtest baseline (pool
   cannot contain premarket fade-and-die names). Currently kept and reported
   separately. Keep, or stop entering before 09:30?
5. **Halal rulings pending:** ATHR (fintech analytics vendor to equity+options
   traders; unverified split → currently FAIL by the binary rule).
6. **Data plan.** Massive quotes/trades endpoints are 403 on this plan; 1-second
   aggregates are entitled and sufficed. Upgrade only if true NBBO depth is
   needed later.
7. **Next input class.** Five input families (price/volume, liquidity,
   catalysts, filings, earnings) share one IC ceiling (~0.03–0.06). The agents'
   consensus next input must be dense every morning: order book / options flow
   (options are haram; book depth is live-only) — i.e. paper-first, not
   backtestable. Decide whether that is worth a live-measurement campaign.

## Resume checklist

- `git pull`; read `EXPERIMENTS-INDEX.md` (rows + the COST-REBASE correction line).
- Live: Task Scheduler `\Stocks\C37MorningLaunch` (06:20, WakeToRun) +
  `\Stocks\C37Watchdog` (09:35/10:30/11:30/12:00/13:30/14:45) keep running the
  paper session with the 415-name halal list and the corrected gate; the in-session
  06:45 backup cron dies with the Claude session — re-create it on resume.
- Login expiry kills headless sessions silently; the watchdog now alerts within
  the hour; `/login` then relaunch a takeover session.
- Agents run on Opus (session rule); every new line gets a name and must append
  its row to `EXPERIMENTS-INDEX.md`; adversarial code-path audit before believing
  any positive number (controls inherit leaks).
- Known one-time hygiene items: `pool_hygiene` rule 4 fires zero times (spec
  question); `SCREEN_EPOCH` now 2026-09-16; halal list backups `*.pre-*`.

## Files that carry the full record

`EXPERIMENTS-INDEX.md` · `NOTES-DAYTRADING.md` (sections dated 2026-09-16/17) ·
`harness-diagnostic.md` · `cost-rebase-audit.md` · `catalyst-audit.md` ·
`close-momentum-audit.md` · `universe-quotes-audit.md` · `widenet-audit.md` ·
`rl2-audit.md` · `rl-audit.md` · `halal-audit-2026-09-16.md` ·
`video-studies/` (55 files) · `data/paper_days/` (live ledgers).
