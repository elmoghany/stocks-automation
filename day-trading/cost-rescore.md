# COST-RESCORE (2026-10-01): when does each line's best config turn profitable?

Part of PESSIMISM-AUDIT, run in parallel with it. The question: at what execution cost does each line's best config turn profitable, and what does it earn at plausible costs? Halal is ignored. Every line is re-scored on its own saved universe, with no halal step added.

## Verdict

**At ≤ 4 bps/side, five configs are positive in both years (or both halves of their held-out year) and beat their random controls at the 100th percentile:**

- CHAMPION-REPLAY R4
- CATALYST-MINER R15
- RL-SCOUT v2 approach-4 seed 0
- UNIVERSE-QUOTES rank-for-the-fill
- CLOSE-MOMENTUM REV|15:30→15:59|k7

Two of them don't survive a plausible cost:

- **CM breaks even at 5.0 bps/side.**
- **UQ's second half breaks even at 4.1 bps/side.**

The other two wide-universe survivors are thin:

- R15 trades **0.25 tickets a day** (112 tickets in 448 days).
- RL2 is one held-out year and 305 tickets.

R4 is a gapper-pool config, where the plausible cost is 18–29 bps/side, not 4. At its own fills' cost (28.75 bps) it earns +$1,531/month. But year 2 is +$96/month, ex-best-day is −$1,231, and five legs carry the P&L.

**Best $/month at a plausible cost:**

| config | cost | $/month |
|---|---|---:|
| R4 | own-fill cost 28.75 | **+$1,485–1,531** (not credible, see above) |
| CAT R15 | central 9 | **+$690** |
| RL2 | central 6 | **+$609** |
| UQ | central 6 | **+$560** (second half negative) |

**Distance from $7,500/month:**

- The best credible single config (R15, about +$700) is **about 11× short**.
- R4 is about 5× short, but only if its tail is believed.
- Adding all three wide-universe survivors at central cost (R15 + RL2 + UQ ≈ +$1,860/month) is still **4× short**. That sum is also not account-feasible as-is (one position at a time).

The incumbent flat 10 bps did hide real money:

- CM is +$399/month at 4 bps and −$1,925 at 10.
- OU top-600 is +$1,699 at 4 and −$823 at 10.
- UQ is +$836 at 4 and +$6 at 10.

But it doesn't hide a $7,500/month strategy. Evidence-based costs are 6 bps all-day and 9 at the open (PESSIMISM-AUDIT), or 8 bps per LIVE-COST-TRUTH (12 on entry, 4 on exit). At those costs only R15, RL2 and UQ-overall stay positive, and each is worth hundreds of dollars a month, not thousands.

**Two items for PESSIMISM-AUDIT:**

1. **A cost-pricing defect in COST-REBASE's RL-SCOUT v2 "measured" row.**
   - `plan/cr_engine.py:_m2t` assumes rl2's minute grid starts at 00:00 ET. It starts at **04:00** (`rl2/features.py:53` RTH_LO = 330 = 09:30).
   - So every RL2 fill was priced 4 hours early, at 05:51–11:56 ET instead of 09:51–15:56: premarket spreads and near-zero trailing volume under the √-impact term.
   - That is why its measured entry cost was 57 bps/side and the row −$59.97/ticket.
   - Priced at the correct minutes with PESSIMISM-AUDIT's evidence cost, the same 305 legs average **10.2 bps on entry and 21.6 on exit** (the exit figure includes +50 on the 82 after-16:00 exits), and the row is **+$16.07/ticket, +$404/month**.
2. **The live benchmark is negative before any cost.**
   - C37F-hf3 is **−$37.01/ticket at 0 bps** (the ledger carries no cost at all).
   - HOLD1-hf3 is −$134.28 at 0 bps.
   - No cost convention rescues the live rules.

## What was done

| step | how | exactness |
|---|---|---|
| WIDE-NET single, top-k per slot; CATALYST R15; CHAMPION R4; LIMIT-EXEC; OPEN-UNIVERSE | PESSIMISM-AUDIT's `plan/pa_rescore.py` line functions, imported; `summ` patched to add months-positive | wn/cat tables inverted exactly (`pnl = N(1+c0)·tgt` → gross ratio `R`); R4 from `pa_out/cp_r4_legs.json` (identity to the published $66,760.10 and all 30 control totals); lx/ou **linear between their stored zero-cost and flat-10 rows** (percentile is a normal approximation; no months-positive; no per-fill dump) |
| WIDE-NET top-k **@09:35, k names per day** (account-legal) | `crs_rescore.line_wn_day`: `wn_oos.pick(per="day")` + 30-seed slot-matched null | exact; added because the per-slot top-k is 27–63 tickets/day, over the $100k/day cap |
| CLOSE-MOMENTUM REV k7 | `cm_single.run` once per ranking (31 runs); the path is cost-free, so `net = gross − sh·(px_in+px_out)·b` | **96,028 trades, 0 fail the 10 bps identity**, no extended-hours leg |
| CHAMPION R5 + its 30 seeds | `plan/crs_cp.py`: re-run with no cost callable, legs dumped | **identity: −$75,804.91 = published, n 2,151 = 2,151, 30/30 control totals exact** |
| RL-SCOUT v2 approach-4 s0 + 30 seeds | `plan/crs_rl2.py`: cr_rerun.stage_rl2's own machinery, legs dumped (the path-cost-free proof is cr_engine's) | **305 tickets, $4,304.71 at 10 bps = published to the cent**; 82 exits after 16:00 keep +50 bps |
| UNIVERSE-QUOTES rank-for-the-fill + mirror + 30 seeds | `plan/crs_uq.py`: `uq_strat.run_many` with `price_ticket` wrapped to record N, fill, exit, ext, passive | **1,210 tickets, +$0.064/tkt at 10 bps = published, max per-ticket diff 0.0**; 100% passive entries (pay 0), no ext legs |
| VS2 W8RSd + a NEW 30-seed gate-matched control | `plan/crs_vs2.py`: one re-run at 10 bps with legs dumped; control = `rs_rand` (same market-red gate and minutes, random name), which W8RSd never had | 339 tickets, $6,135.81 vs harness $6,139.78 = published wy1+wy2 (entry prices are rounded to the cent in the ledger); hold-to-flatten, so no exit level depends on cost |
| C37F-hf3, HOLD1-hf3 | ledgers `data/massive/rotation_trades_*_hf3.json`; legacy slip (C37F 0, HOLD1 10 bps) undone: `fill = entry/(1+slip)` | path frozen (C37F's stops/trails are struck off entry; COST-REBASE route B bounds it); identity within 0.3–0.8% (cent-rounded ledger prices); **no full-period 30-seed control exists** — only COST-REBASE 4.7's 10 seeds × 40 days |
| Fill-specific evidence cost | `plan/crs_evid.py`: every rule fill priced with `pa_rescore.Evid` (cr_cost half-spread with no √-impact, + 4.4 bps before 10:30 else 3.1) at its own sym/date/minute; control at a flat b equal to the rule's mean | rule exact; control approximate |

Cost convention everywhere: b bps on both the entry and exit notional of every marketable leg. A resting-limit leg pays 0 (UQ entries; LX passive legs), as each line's own convention did. Extended-hours legs keep +50 bps; only RL2 has any (82 exits).

- **Y1** = before 2025-08-01; **Y2** = 2025-08-01 → 2026-08-01.
- Lines that only have a held-out year (WIDE-NET, UQ, RL2, LX) report that year's two calendar halves as **H1/H2** instead.
- $/month = total / (sessions / 21).
- Percentile = the rule's total against its own 30 seeds at the **same** b. Exceptions:
  - WN per-slot top-k uses 12 seeds, as published.
  - LX and OU use a normal approximation.

## Summary: every config × cost

Columns:

- **Central cost** is PESSIMISM-AUDIT's evidence-based verdict for the fill's bucket: 6 bps all-day, 9 at 09:30–10:30 (wide universe, $15k). For the gapper pool, it is the R4 fill-specific estimate (28.75, `pa_out/rescore_cp.json`).
- **Fill-specific EVID** prices each rule's own fills. It uses the production max-of-three half-spread, which PESSIMISM-AUDIT check 1c shows runs about 1.5–2× the median-of-three. So read it as the **upper** side of the plausible band. The true cost of each config sits between the two columns.

| config | tkts/day | $/mo @0 | $/mo @3 | $/mo @4 | $/mo @6 | $/mo @10 | both halves/years + @4? | pct vs random @4 | ex-best-day @4 | break-even bps/side (all · 1st · 2nd) | central cost (bps) → $/mo | fill-specific EVID bps → $/mo |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|---|
| CP R4 coil, no stop | 2.173 | +4,049 | +3,782 | +3,693 | +3,514 | +3,158 | yes (Y1/Y2 +5,634 / +2,200) | 100.0 | +43,719 | 45.4 · 68.2 · 28.4 | 28.75 (gapper) → +1,485 | 28.8 → +1,531 |
| CAT R15 fresh-earn & green @09:35 | 0.25 | +830 | +783 | +768 | +736 | +674 | yes (Y1/Y2 +621 / +855) | 100.0 | +14,384 | 53.1 · 58.8 · 50.4 | 9 (wide 09:35) → +690 | 34.1 → +294 |
| RL2 approach-4 s0 | 1.196 | +991 | +800 | +736 | +609 | +354 | yes (H1/H2 +904 / +570) | 100.0 | +4,939 | 15.6 · 27.1 · 10.5 | 6 (wide all-day) → +609 | 15.9 → +404 |
| UQ rank-for-the-fill (limit) | 4.821 | +1,390 | +975 | +836 | +560 | +6 | yes (H1/H2 +1,668 / +11) | 100.0 | +8,035 | 10.0 · 15.8 · 4.1 | 6 (wide all-day) → +560 | 6.5 → -406 |
| CM REV 15:30->15:59 k7 | 6.908 | +1,949 | +787 | +399 | -376 | -1,925 | yes (Y1/Y2 +573 / +573) | 100.0 | +4,525 | 5.0 · 5.5 · 5.5 | 6 (wide 15:30) → -375 | 8.0 → -1,083 |
| VS2 W8RSd green-on-red | 0.757 | +759 | +617 | +570 | +476 | +288 | no (Y1/Y2 +1,376 / -38) | 93.3 | +5,273 | 16.1 · 33.6 · 3.2 | 6 (wide all-day) → +476 | 20.5 → -200 |
| OU top600 ovn_prev+L (CAP100k) | 7.0 | +3,380 | +2,119 | +1,699 | +858 | -823 | no (Y1/Y2 -831 / +2,473) | 100.0 | +21,564 | 8.0 · 2.0 · 9.9 | 9 (open 09:30) → -403 | — |
| OU top600 ovn_prev+L (7x15k) | 7.0 | +3,732 | +2,408 | +1,966 | +1,084 | -682 | no (Y1/Y2 -588 / +2,698) | 100.0 | +26,536 | 8.5 · 2.7 · 10.1 | 9 (open 09:30) → -241 | — |
| WN LightGBM 1/day @09:35 | 1.0 | +494 | +324 | +268 | +155 | -70 | no (H1/H2 +771 / -231) | 96.7 | +1,238 | 8.8 · 18.1 · 0.0 | 9 (wide 09:35) → -14 | 24.8 → -953 |
| LX rest-then-cross (model) | 5.976 | +330 | +35 | -63 | -260 | -653 | — | 98.5 | -2,942 | 3.4 · — · — | 6 (wide all-day) → -260 | — |
| WN top-3 @09:35 | 3.0 | -488 | -963 | -1,121 | -1,438 | -2,071 | no (H1/H2 +793 / -3,019) | 36.7 | -16,879 | never (neg. at 0) · 9.3 · never (neg. at 0) | 9 (wide 09:35) → -1,913 | 23.5 → -4,381 |
| WN top-5 @09:35 | 5.0 | -528 | -1,300 | -1,557 | -2,072 | -3,102 | no (H1/H2 +734 / -3,830) | 46.7 | -21,947 | never (neg. at 0) · 7.0 · never (neg. at 0) | 9 (wide 09:35) → -2,844 | — |
| WN top-7 @09:35 | 7.0 | -513 | -1,590 | -1,949 | -2,668 | -4,104 | no (H1/H2 +100 / -3,982) | 63.3 | -29,566 | never (neg. at 0) · 4.3 · never (neg. at 0) | 9 (wide 09:35) → -3,745 | 20.6 → -8,246 |
| WN top-3 per slot (27/day, NOT legal) | 26.928 | -969 | -4,194 | -5,270 | -7,420 | -11,721 | no (H1/H2 -1,776 / -8,720) | 91.7 | -68,316 | never (neg. at 0) · 2.3 · never (neg. at 0) | 6 (wide all-day) → -7,420 | — |
| WN top-5 per slot (45/day, NOT legal) | 44.88 | -962 | -6,553 | -8,417 | -12,144 | -19,599 | no (H1/H2 -4,006 / -12,771) | 100.0 | -106,713 | never (neg. at 0) · 1.8 · never (neg. at 0) | 6 (wide all-day) → -12,144 | — |
| WN top-7 per slot (63/day, NOT legal) | 62.833 | -1,964 | -10,261 | -13,027 | -18,559 | -29,623 | no (H1/H2 -8,709 / -17,299) | 100.0 | -163,969 | never (neg. at 0) · 0.8 · never (neg. at 0) | 6 (wide all-day) → -18,559 | — |
| CP R5 coil, 10:00, stop -2% | 4.845 | -1,744 | -2,296 | -2,480 | -2,849 | -3,585 | no (Y1/Y2 -3,172 / -1,949) | 30.0 | -59,592 | never (neg. at 0) · never (neg. at 0) · never (neg. at 0) | 28.75 (gapper) → -7,038 | — |
| C37F-hf3 (live rules) | 4.142 | -3,219 | -3,934 | -4,172 | -4,649 | -5,603 | no (Y1/Y2 -2,973 / -5,094) | — | -99,892 | never (neg. at 0) · never (neg. at 0) · never (neg. at 0) | 28.75 (gapper) → -10,072 | — |
| HOLD1-hf3 | 0.993 | -2,801 | -2,973 | -3,031 | -3,146 | -3,376 | no (Y1/Y2 -3,240 / -2,870) | — | -79,771 | never (neg. at 0) · never (neg. at 0) · never (neg. at 0) | 28.75 (gapper) → -4,455 | — |

**Random controls (re-scored at the same b).**

- At 0 bps the wide-universe controls sit near zero (UQ −$1.49, WN −$3.12, CM **+$4.71**, OU +$0.22/ticket). The harness adds no drag.
- RL2's control is −$20.75 at 0 bps. It is not rate-matched (≈ 7 tickets/day against the rule's 1.2) and pays +50 on its own after-hours exits.
- The gapper controls are negative gross: R4's frame −$16.77, R5's −$9.42.
- Every surviving config's edge over its control is ≈ constant in b, because both pay the same toll. **The controls stay intact at every cost**: R4, R15, RL2, UQ and CM are at the 100th percentile from 0 to 12 bps, on total and on ex-best-day.
- The percentile of R15, R4 and VS2 does not move with b.

## Break-even cost (bps/side)

| config | all | year 1 / H1 | year 2 / H2 | binding |
|---|---:|---:|---:|---|
| CATALYST R15 @09:35 h60 | 53.1 | 58.8 | 50.4 | none below 50 bps; rate is the constraint (0.25/day) |
| CHAMPION R4 (gapper) | 45.4 | 68.2 | **28.4** | Y2, at its own fill cost (28.75) |
| VS2 W8RSd | 16.1 | 33.6 | **3.2** | Y2 |
| RL2 approach-4 s0 | 15.6 | 27.1 | **10.5** | H2 |
| UQ rank-for-the-fill | 10.0 | 15.8 | **4.1** | H2 |
| WIDE-NET LightGBM 1/day | 8.8 | 18.1 | **0.0** | H2 is zero gross |
| OPEN-UNIVERSE top600 (7×15k / CAP100k) | 8.5 / 8.0 | **2.7 / 2.0** | 10.1 / 9.9 | Y1 |
| CLOSE-MOMENTUM REV k7 | **5.0** | 5.5 | 5.5 | all |
| LIMIT-EXEC rest-then-cross (marketable legs only) | **3.4** | — | — | all (the published row is the held-out year only) |
| WIDE-NET top-3/5/7 (@09:35 or per slot), CHAMPION R5, C37F-hf3, HOLD1-hf3 | negative at 0 | | | no cost makes them positive |

Notes on the rows:

- **R4 is the only line whose break-even clears its plausible cost, and only in total.**
  - At 28.75 bps: per ticket **+$33.53**; Y1 **+$3,397/month**, Y2 **+$96/month**; ex-best-day **−$1,231**.
  - The top five legs (MNPR +$32k on 2024-10-24, YIBO, ARMP, SGN, RNAZ) are more than the whole P&L at flat 10 (CHAMPION-REPLAY Part 4).
  - It does not survive as a strategy at gapper costs.
- **R15** is the most cost-robust row in the repo, and the smallest.
  - Its fills are expensive: fresh-earnings names at 09:36 run 51 bps/side on entry by EVID. Even so it nets +$294/month, 12/22 months, both years positive.
  - It is 112 tickets.
  - It was picked from a bucket table (CATALYST-MINER Part 5), so it is an in-sample maximum over the rule set.
- **RL2** at EVID (10 bps entry, 22 exit incl. ext): +$404/month, 6/11 months, H1 +$672 / H2 +$137, ex-best-day +$1,012, 100th percentile.
  - Its exits after 16:00 (82 of 305) cost 50+ bps each.
  - Exiting at 15:59 instead of holding past the close is the first execution fix.
- **CM** is clean (both years +$573/month at 4 bps, 100th percentile, 96k-trade identity) but its break-even is 5.0. Its own fills cost 7.6 bps on entry (15:31) and 8.3 on exit (15:59) by EVID → −$1,083/month.
  - The exit at 15:59 could go to the closing auction instead.
  - **Unmeasured idea, not a result:** at ≈ 6 bps entry + ≈ 1 bps exit (mean 3.5/side), CM would be ≈ +$600/month.

## What this says about the cost question

1. **The 10 bps convention is not why the honest lines lose.** Moving from 10 to the evidence-based central (6 all-day, 9 at the open) does change some signs:
   - OU top-600 is +$1,084/month at 6, but it is −$241 at its own open-bucket 9, and its Y1 is negative from 3 bps.
   - CM turns positive only at ≤ 5 bps; LX only at ≤ 3.
   - The lines that survive the central cost (R15, RL2, UQ overall) earn $560–690/month each.
2. **Selection raises the cost.** A ranker's own fills are dearer than the universe mean:
   - wide-net LightGBM picks at 09:36: 31 bps entry by EVID;
   - R15: 51 bps;
   - VS2: 31 bps;
   - universe central: 9 at the open.
   - This is COST-REBASE 4.2's mechanism, seen again with the impact term removed.
   - **Configs whose apparent edge needs ≤ 4 bps are mostly picking the names that cost more than 4 bps.**
3. **The gapper pool is a different cost world** (LIVE-COST-TRUTH: entries in gappers ~11–15 bps half-spread alone; COST-REBASE: 28.5 bps full books). Every gapper config except R4 is negative at **zero** cost.

## Files

| | |
|---|---|
| `plan/crs_rescore.py` | the grid re-score (imports `pa_rescore.py`); → `plan/crs_rescore.json` |
| `plan/crs_evid.py` | fill-specific evidence-cost pricing; → `plan/crs_evid.json` |
| `plan/crs_cp.py` | CHAMPION R5 + 30-seed control leg dump → `plan/crs_cp_r5_legs.json` |
| `plan/crs_rl2.py` | RL2 approach-4 s0 + 30-seed control leg dump → `plan/crs_rl2_legs.json` |
| `plan/crs_uq.py` | UQ rank-for-the-fill + mirror + 30 seeds leg dump → `plan/crs_uq_legs.json` |
| `plan/crs_vs2.py` | VS2 W8RSd + new 30-seed gate-matched control, 3 shards → `plan/crs_vs2_legs_{a,b,c}.json` |
| `plan/crs_table.py`, `plan/crs_report.py` | the tables below and above |

`plan/*.json` is gitignored, so none of the outputs is committed. `python plan/crs_rescore.py` and `python plan/crs_evid.py` rebuild the summaries from the dumps; the dump scripts rebuild the dumps (R5 ≈ 2.5 min, UQ ≈ 5 min, VS2 ≈ 6 min in 3 shards, RL2 ≈ 1.5 min).

## Appendix: per-config × cost tables

Rows are bps/side. "Y1/Y2 $/mo" shows the H1/H2 per-ticket values for the WIDE-NET rows.

#### CHAMPION-REPLAY R5

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -17.14 | 4.845 | -1,744 | -2,449 | -1,202 | 5/22 | -44,082 | -9.42 | +26.7 |
| 2 | -20.76 | 4.845 | -2,112 | -2,810 | -1,575 | 5/22 | -51,837 | -13.57 | +30.0 |
| 3 | -22.57 | 4.845 | -2,296 | -2,991 | -1,762 | 4/22 | -55,714 | -15.65 | +30.0 |
| 4 | -24.38 | 4.845 | -2,480 | -3,172 | -1,949 | 4/22 | -59,592 | -17.73 | +30.0 |
| 6 | -28.00 | 4.845 | -2,849 | -3,534 | -2,322 | 4/22 | -67,347 | -21.88 | +30.0 |
| 8 | -31.62 | 4.845 | -3,217 | -3,895 | -2,696 | 4/22 | -75,102 | -26.03 | +40.0 |
| 10 | -35.24 | 4.845 | -3,585 | -4,257 | -3,069 | 4/22 | -82,858 | -30.18 | +46.7 |
| 12 | -38.86 | 4.845 | -3,954 | -4,619 | -3,442 | 3/22 | -90,613 | -34.34 | +56.7 |

break-even bps/side: {'all': -1.0, 'y1': -1.0, 'y2': -1.0}
identity: {'R5_flat_total_rerun': -75804.91, 'R5_flat_total_published': -75804.91, 'R5_n': [2151, 2151], 'rnd_flat_totals_match': True, 'net_flat_vs_10bps_reprice_maxdiff': 0.0}

#### RL-SCOUT v2 approach-4 seed 0

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +39.44 | 1.196 | +991 | — | +1,006 | 8/11 | +7,956 | -20.75 | +100.0 |
| 2 | +34.37 | 1.196 | +863 | — | +877 | 7/11 | +6,448 | -26.04 | +100.0 |
| 3 | +31.84 | 1.196 | +800 | — | +812 | 7/11 | +5,693 | -28.68 | +100.0 |
| 4 | +29.31 | 1.196 | +736 | — | +748 | 7/11 | +4,939 | -31.32 | +100.0 |
| 6 | +24.24 | 1.196 | +609 | — | +619 | 7/11 | +3,431 | -36.61 | +100.0 |
| 8 | +19.18 | 1.196 | +482 | — | +489 | 6/11 | +1,922 | -41.89 | +100.0 |
| 10 | +14.11 | 1.196 | +354 | — | +360 | 6/11 | +414 | -47.18 | +100.0 |
| 12 | +9.05 | 1.196 | +227 | — | +231 | 6/11 | -1,095 | -52.46 | +100.0 |

break-even bps/side: {'all': 15.57, 'y1': None, 'y2': 15.57}
identity: {'tickets': 305, 'published_tickets': 305, 'total_10bps': 4304.71, 'published_total': 4304.71, 'ext_in_legs': 0, 'ext_out_legs': 82}

#### C37F-hf3

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -37.01 | 4.142 | -3,219 | -2,024 | -4,138 | 6/22 | -79,747 | — | — |
| 2 | -42.49 | 4.142 | -3,696 | -2,498 | -4,616 | 6/22 | -89,820 | — | — |
| 3 | -45.23 | 4.142 | -3,934 | -2,736 | -4,855 | 5/22 | -94,856 | — | — |
| 4 | -47.97 | 4.142 | -4,172 | -2,973 | -5,094 | 5/22 | -99,892 | — | — |
| 6 | -53.45 | 4.142 | -4,649 | -3,448 | -5,572 | 5/22 | -109,964 | — | — |
| 8 | -58.93 | 4.142 | -5,126 | -3,923 | -6,051 | 5/22 | -120,036 | — | — |
| 10 | -64.41 | 4.142 | -5,603 | -4,398 | -6,529 | 4/22 | -130,109 | — | — |
| 12 | -69.89 | 4.142 | -6,079 | -4,873 | -7,007 | 4/22 | -140,181 | — | — |

break-even bps/side: {'all': -1.0, 'y1': -1.0, 'y2': -1.0}
identity: {'total_at_legacy_slip': -68056.12, 'ledger_pnl_sum': -67853.62}
control_40d_flat_per_ticket: {'y2025': -41.7, 'year': 33.2}

#### HOLD1-hf3

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -134.28 | 0.993 | -2,801 | -3,020 | -2,632 | 7/22 | -74,924 | — | — |
| 2 | -139.80 | 0.993 | -2,916 | -3,130 | -2,751 | 7/22 | -77,347 | — | — |
| 3 | -142.55 | 0.993 | -2,973 | -3,185 | -2,811 | 7/22 | -78,559 | — | — |
| 4 | -145.31 | 0.993 | -3,031 | -3,240 | -2,870 | 7/22 | -79,771 | — | — |
| 6 | -150.83 | 0.993 | -3,146 | -3,350 | -2,989 | 7/22 | -82,195 | — | — |
| 8 | -156.35 | 0.993 | -3,261 | -3,460 | -3,108 | 7/22 | -84,618 | — | — |
| 10 | -161.86 | 0.993 | -3,376 | -3,570 | -3,227 | 7/22 | -87,042 | — | — |
| 12 | -167.38 | 0.993 | -3,491 | -3,680 | -3,346 | 7/22 | -89,466 | — | — |

break-even bps/side: {'all': -1.0, 'y1': -1.0, 'y2': -1.0}
identity: {'total_at_legacy_slip': -71381.35, 'ledger_pnl_sum': -71945.59}
control_40d_flat_per_ticket: {'y2025': -342.6, 'year': -11.4}

#### CHAMPION-REPLAY R4

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +88.72 | 2.173 | +4,049 | +5,985 | +2,561 | 12/22 | +51,180 | -16.77 | +100.0 |
| 2 | +84.81 | 2.173 | +3,871 | +5,810 | +2,380 | 12/22 | +47,449 | -21.37 | +100.0 |
| 3 | +82.86 | 2.173 | +3,782 | +5,722 | +2,290 | 12/22 | +45,584 | -23.67 | +100.0 |
| 4 | +80.91 | 2.173 | +3,693 | +5,634 | +2,200 | 12/22 | +43,719 | -25.96 | +100.0 |
| 6 | +77.00 | 2.173 | +3,514 | +5,459 | +2,019 | 12/22 | +39,988 | -30.56 | +100.0 |
| 8 | +73.09 | 2.173 | +3,336 | +5,283 | +1,839 | 11/22 | +36,258 | -35.15 | +100.0 |
| 10 | +69.18 | 2.173 | +3,158 | +5,108 | +1,658 | 11/22 | +32,527 | -39.74 | +100.0 |
| 12 | +65.27 | 2.173 | +2,979 | +4,932 | +1,477 | 11/22 | +28,797 | -44.34 | +100.0 |

break-even bps/side: {'all': 45.41, 'y1': 68.22, 'y2': 28.36}
identity: {'R4_flat_total_rerun': 66760.1, 'R4_flat_total_published': 66760.1, 'R4_n_rerun': 965, 'R4_n_published': 965, 'rnd_flat_totals_match': True}

#### LIMIT-EXEC bid-rest3-mkt/tick3 model

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +2.63 | 5.976 | +330 | — | — | — | +1,759 | -4.61 | +95.9 |
| 2 | +1.06 | 5.976 | +133 | — | — | — | -592 | -7.08 | +97.5 |
| 3 | +0.28 | 5.976 | +35 | — | — | — | -1,767 | -8.32 | +98.1 |
| 4 | -0.51 | 5.976 | -63 | — | — | — | -2,942 | -9.55 | +98.5 |
| 6 | -2.07 | 5.976 | -260 | — | — | — | -5,293 | -12.03 | +99.2 |
| 8 | -3.64 | 5.976 | -457 | — | — | — | -7,644 | -14.50 | +99.5 |
| 10 | -5.21 | 5.976 | -653 | — | — | — | -9,994 | -16.97 | +99.8 |
| 12 | -6.78 | 5.976 | -850 | — | — | — | -12,345 | -19.44 | +99.9 |

break-even bps/side: {'all': 3.36, 'y1': None, 'y2': None}

#### OPEN-UNIVERSE top600 ovn_prev+L (7x15k)

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +25.39 | 7.0 | +3,732 | +1,176 | +4,464 | — | +62,008 | +0.22 | +100.0 |
| 2 | +19.38 | 7.0 | +2,849 | +294 | +3,581 | — | +44,272 | -5.78 | +100.0 |
| 3 | +16.38 | 7.0 | +2,408 | -147 | +3,139 | — | +35,404 | -8.78 | +100.0 |
| 4 | +13.38 | 7.0 | +1,966 | -588 | +2,698 | — | +26,536 | -11.78 | +100.0 |
| 6 | +7.37 | 7.0 | +1,084 | -1,471 | +1,815 | — | +8,799 | -17.78 | +100.0 |
| 8 | +1.37 | 7.0 | +201 | -2,353 | +932 | — | -8,937 | -23.78 | +100.0 |
| 10 | -4.64 | 7.0 | -682 | -3,235 | +49 | — | -26,674 | -29.78 | +100.0 |
| 12 | -10.65 | 7.0 | -1,565 | -4,117 | -834 | — | -44,410 | -35.78 | +100.0 |

break-even bps/side: {'all': 8.45, 'y1': 2.67, 'y2': 10.11}

#### OPEN-UNIVERSE top600 ovn_prev+L (CAP100k)

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +23.00 | 7.0 | +3,380 | +849 | +4,155 | — | +55,346 | +0.28 | +100.0 |
| 2 | +17.28 | 7.0 | +2,540 | +9 | +3,314 | — | +38,454 | -5.43 | +100.0 |
| 3 | +14.42 | 7.0 | +2,119 | -411 | +2,893 | — | +30,009 | -8.29 | +100.0 |
| 4 | +11.56 | 7.0 | +1,699 | -831 | +2,473 | — | +21,564 | -11.15 | +100.0 |
| 6 | +5.84 | 7.0 | +858 | -1,671 | +1,632 | — | +4,672 | -16.86 | +100.0 |
| 8 | +0.12 | 7.0 | +18 | -2,512 | +791 | — | -12,219 | -22.58 | +100.0 |
| 10 | -5.60 | 7.0 | -823 | -3,352 | -50 | — | -29,110 | -28.29 | +100.0 |
| 12 | -11.32 | 7.0 | -1,664 | -4,192 | -890 | — | -46,001 | -34.00 | +100.0 |

break-even bps/side: {'all': 8.04, 'y1': 2.02, 'y2': 9.88}

#### CATALYST-MINER R15 h60

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +158.11 | 0.25 | +830 | +666 | +928 | 14/22 | +15,704 | -11.12 | +100.0 |
| 2 | +152.16 | 0.25 | +799 | +644 | +892 | 14/22 | +15,044 | -16.01 | +100.0 |
| 3 | +149.18 | 0.25 | +783 | +632 | +873 | 14/22 | +14,714 | -18.46 | +100.0 |
| 4 | +146.21 | 0.25 | +768 | +621 | +855 | 14/22 | +14,384 | -20.90 | +100.0 |
| 6 | +140.26 | 0.25 | +736 | +598 | +818 | 14/22 | +13,724 | -25.79 | +100.0 |
| 8 | +134.30 | 0.25 | +705 | +576 | +781 | 14/22 | +13,064 | -30.68 | +100.0 |
| 10 | +128.35 | 0.25 | +674 | +553 | +744 | 14/22 | +12,403 | -35.57 | +100.0 |
| 12 | +122.40 | 0.25 | +643 | +530 | +707 | 14/22 | +11,743 | -40.46 | +100.0 |

break-even bps/side: {'all': 53.13, 'y1': 58.77, 'y2': 50.42}

#### CLOSE-MOMENTUM REV 15:30->15:59 k7

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +13.43 | 6.908 | +1,949 | +2,111 | +2,130 | 12/23 | +37,515 | +4.71 | +100.0 |
| 2 | +8.09 | 6.908 | +1,174 | +1,342 | +1,351 | 11/23 | +21,020 | -0.69 | +100.0 |
| 3 | +5.42 | 6.908 | +787 | +957 | +962 | 11/23 | +12,773 | -3.39 | +100.0 |
| 4 | +2.75 | 6.908 | +399 | +573 | +573 | 10/23 | +4,525 | -6.10 | +100.0 |
| 6 | -2.59 | 6.908 | -376 | -197 | -205 | 9/23 | -11,970 | -11.50 | +100.0 |
| 8 | -7.93 | 6.908 | -1,150 | -966 | -984 | 7/23 | -28,465 | -16.91 | +100.0 |
| 10 | -13.27 | 6.908 | -1,925 | -1,736 | -1,762 | 6/23 | -44,960 | -22.31 | +100.0 |
| 12 | -18.61 | 6.908 | -2,700 | -2,505 | -2,540 | 6/23 | -61,455 | -27.72 | +100.0 |

break-even bps/side: {'all': 5.03, 'y1': 5.49, 'y2': 5.47}
identity: {'trades_failing_10bps_identity_or_ext': 0, 'trades': 96028}

#### WIDE-NET model single

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +23.50 | 1.0 | +494 | H1 +47.09/tkt | H2 +0.10/tkt | 7/12 | +3,921 | -3.12 | +96.7 |
| 2 | +18.13 | 1.0 | +381 | H1 +41.90/tkt | H2 -5.45/tkt | 7/12 | +2,579 | -8.03 | +96.7 |
| 3 | +15.44 | 1.0 | +324 | H1 +39.30/tkt | H2 -8.22/tkt | 7/12 | +1,908 | -10.48 | +96.7 |
| 4 | +12.76 | 1.0 | +268 | H1 +36.70/tkt | H2 -11.00/tkt | 6/12 | +1,238 | -12.94 | +96.7 |
| 6 | +7.39 | 1.0 | +155 | H1 +31.51/tkt | H2 -16.54/tkt | 6/12 | -104 | -17.84 | +96.7 |
| 8 | +2.02 | 1.0 | +42 | H1 +26.32/tkt | H2 -22.09/tkt | 5/12 | -1,446 | -22.75 | +96.7 |
| 10 | -3.35 | 1.0 | -70 | H1 +21.13/tkt | H2 -27.64/tkt | 5/12 | -2,788 | -27.66 | +96.7 |
| 12 | -8.72 | 1.0 | -183 | H1 +15.94/tkt | H2 -33.19/tkt | 5/12 | -4,129 | -32.57 | +96.7 |

break-even bps/side: {'all': 8.75, 'y1': None, 'y2': None, 'oos_h1': 18.14, 'oos_h2': 0.04}

#### WIDE-NET model top3

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -1.71 | 26.928 | -969 | H1 +4.20/tkt | H2 -7.55/tkt | 8/12 | -17,101 | -2.18 | +66.7 |
| 2 | -5.52 | 26.928 | -3,119 | H1 +0.53/tkt | H2 -11.48/tkt | 5/12 | -42,708 | -7.02 | +75.0 |
| 3 | -7.42 | 26.928 | -4,194 | H1 -1.30/tkt | H2 -13.45/tkt | 3/12 | -55,512 | -9.44 | +83.3 |
| 4 | -9.32 | 26.928 | -5,270 | H1 -3.14/tkt | H2 -15.42/tkt | 3/12 | -68,316 | -11.86 | +91.7 |
| 6 | -13.12 | 26.928 | -7,420 | H1 -6.81/tkt | H2 -19.35/tkt | 1/12 | -93,923 | -16.70 | +100.0 |
| 8 | -16.92 | 26.928 | -9,570 | H1 -10.48/tkt | H2 -23.28/tkt | 0/12 | -119,530 | -21.54 | +100.0 |
| 10 | -20.73 | 26.928 | -11,721 | H1 -14.15/tkt | H2 -27.21/tkt | 0/12 | -145,137 | -26.38 | +100.0 |
| 12 | -24.53 | 26.928 | -13,872 | H1 -17.83/tkt | H2 -31.14/tkt | 0/12 | -170,744 | -31.22 | +100.0 |

break-even bps/side: {'all': -1.0, 'y1': None, 'y2': None, 'oos_h1': 2.29, 'oos_h2': -1.0}

#### WIDE-NET model top5

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -1.02 | 44.88 | -962 | H1 +3.47/tkt | H2 -5.45/tkt | 7/12 | -17,925 | -2.43 | +83.3 |
| 2 | -4.98 | 44.88 | -4,689 | H1 -0.39/tkt | H2 -9.50/tkt | 5/12 | -62,319 | -7.27 | +100.0 |
| 3 | -6.95 | 44.88 | -6,553 | H1 -2.32/tkt | H2 -11.53/tkt | 4/12 | -84,516 | -9.70 | +100.0 |
| 4 | -8.93 | 44.88 | -8,417 | H1 -4.25/tkt | H2 -13.55/tkt | 1/12 | -106,713 | -12.12 | +100.0 |
| 6 | -12.89 | 44.88 | -12,144 | H1 -8.10/tkt | H2 -17.60/tkt | 0/12 | -151,107 | -16.96 | +100.0 |
| 8 | -16.84 | 44.88 | -15,872 | H1 -11.96/tkt | H2 -21.65/tkt | 0/12 | -195,500 | -21.81 | +100.0 |
| 10 | -20.79 | 44.88 | -19,599 | H1 -15.82/tkt | H2 -25.70/tkt | 0/12 | -239,894 | -26.65 | +100.0 |
| 12 | -24.75 | 44.88 | -23,326 | H1 -19.68/tkt | H2 -29.76/tkt | 0/12 | -284,288 | -31.50 | +100.0 |

break-even bps/side: {'all': -1.0, 'y1': None, 'y2': None, 'oos_h1': 1.8, 'oos_h2': -1.0}

#### WIDE-NET model top7

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -1.49 | 62.833 | -1,964 | H1 +1.67/tkt | H2 -4.60/tkt | 6/12 | -32,419 | -2.40 | +75.0 |
| 2 | -5.68 | 62.833 | -7,496 | H1 -2.46/tkt | H2 -8.86/tkt | 4/12 | -98,194 | -7.24 | +100.0 |
| 3 | -7.78 | 62.833 | -10,261 | H1 -4.53/tkt | H2 -10.98/tkt | 2/12 | -131,081 | -9.66 | +100.0 |
| 4 | -9.87 | 62.833 | -13,027 | H1 -6.60/tkt | H2 -13.11/tkt | 1/12 | -163,969 | -12.08 | +100.0 |
| 6 | -14.07 | 62.833 | -18,559 | H1 -10.73/tkt | H2 -17.36/tkt | 0/12 | -229,744 | -16.93 | +100.0 |
| 8 | -18.26 | 62.833 | -24,091 | H1 -14.86/tkt | H2 -21.61/tkt | 0/12 | -295,519 | -21.77 | +100.0 |
| 10 | -22.45 | 62.833 | -29,623 | H1 -18.99/tkt | H2 -25.86/tkt | 0/12 | -361,294 | -26.62 | +100.0 |
| 12 | -26.64 | 62.833 | -35,154 | H1 -23.13/tkt | H2 -30.11/tkt | 0/12 | -427,069 | -31.46 | +100.0 |

break-even bps/side: {'all': -1.0, 'y1': None, 'y2': None, 'oos_h1': 0.81, 'oos_h2': -1.0}

#### WIDE-NET model top3 @09:35 (account-legal)

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -7.74 | 3.0 | -488 | H1 +22.04/tkt | H2 -37.28/tkt | 7/12 | -9,347 | -4.07 | +36.7 |
| 2 | -12.77 | 3.0 | -804 | H1 +17.31/tkt | H2 -42.60/tkt | 7/12 | -13,113 | -9.01 | +36.7 |
| 3 | -15.28 | 3.0 | -963 | H1 +14.94/tkt | H2 -45.26/tkt | 7/12 | -14,996 | -11.47 | +36.7 |
| 4 | -17.79 | 3.0 | -1,121 | H1 +12.58/tkt | H2 -47.92/tkt | 5/12 | -16,879 | -13.94 | +36.7 |
| 6 | -22.82 | 3.0 | -1,438 | H1 +7.85/tkt | H2 -53.24/tkt | 5/12 | -20,645 | -18.87 | +36.7 |
| 8 | -27.84 | 3.0 | -1,754 | H1 +3.12/tkt | H2 -58.56/tkt | 5/12 | -24,411 | -23.80 | +36.7 |
| 10 | -32.87 | 3.0 | -2,071 | H1 -1.62/tkt | H2 -63.88/tkt | 4/12 | -28,177 | -28.73 | +36.7 |
| 12 | -37.90 | 3.0 | -2,388 | H1 -6.35/tkt | H2 -69.20/tkt | 3/12 | -31,943 | -33.66 | +36.7 |

break-even bps/side: {'all': -1.0, 'y1': None, 'y2': None, 'oos_h1': 9.32, 'oos_h2': -1.0}

#### WIDE-NET model top5 @09:35 (account-legal)

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -5.02 | 5.0 | -528 | H1 +16.30/tkt | H2 -26.18/tkt | 5/12 | -9,684 | -4.10 | +46.7 |
| 2 | -9.93 | 5.0 | -1,042 | H1 +11.64/tkt | H2 -31.33/tkt | 5/12 | -15,815 | -9.03 | +46.7 |
| 3 | -12.38 | 5.0 | -1,300 | H1 +9.32/tkt | H2 -33.91/tkt | 5/12 | -18,881 | -11.50 | +46.7 |
| 4 | -14.83 | 5.0 | -1,557 | H1 +6.99/tkt | H2 -36.48/tkt | 4/12 | -21,947 | -13.97 | +46.7 |
| 6 | -19.73 | 5.0 | -2,072 | H1 +2.34/tkt | H2 -41.63/tkt | 4/12 | -28,079 | -18.90 | +46.7 |
| 8 | -24.64 | 5.0 | -2,587 | H1 -2.31/tkt | H2 -46.79/tkt | 4/12 | -34,210 | -23.83 | +46.7 |
| 10 | -29.54 | 5.0 | -3,102 | H1 -6.96/tkt | H2 -51.94/tkt | 4/12 | -40,342 | -28.76 | +46.7 |
| 12 | -34.44 | 5.0 | -3,616 | H1 -11.61/tkt | H2 -57.09/tkt | 3/12 | -46,474 | -33.70 | +46.7 |

break-even bps/side: {'all': -1.0, 'y1': None, 'y2': None, 'oos_h1': 7.01, 'oos_h2': -1.0}

#### WIDE-NET model top7 @09:35 (account-legal)

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | -3.49 | 7.0 | -513 | H1 +10.08/tkt | H2 -16.95/tkt | 7/12 | -12,481 | -5.75 | +63.3 |
| 2 | -8.37 | 7.0 | -1,231 | H1 +5.38/tkt | H2 -22.02/tkt | 6/12 | -21,023 | -10.68 | +63.3 |
| 3 | -10.82 | 7.0 | -1,590 | H1 +3.03/tkt | H2 -24.56/tkt | 6/12 | -25,294 | -13.15 | +63.3 |
| 4 | -13.26 | 7.0 | -1,949 | H1 +0.68/tkt | H2 -27.09/tkt | 5/12 | -29,566 | -15.62 | +63.3 |
| 6 | -18.15 | 7.0 | -2,668 | H1 -4.02/tkt | H2 -32.16/tkt | 4/12 | -38,108 | -20.55 | +63.3 |
| 8 | -23.03 | 7.0 | -3,386 | H1 -8.72/tkt | H2 -37.24/tkt | 3/12 | -46,651 | -25.49 | +63.3 |
| 10 | -27.92 | 7.0 | -4,104 | H1 -13.42/tkt | H2 -42.31/tkt | 2/12 | -55,193 | -30.42 | +66.7 |
| 12 | -32.81 | 7.0 | -4,823 | H1 -18.12/tkt | H2 -47.38/tkt | 2/12 | -63,736 | -35.36 | +70.0 |

break-even bps/side: {'all': -1.0, 'y1': None, 'y2': None, 'oos_h1': 4.29, 'oos_h2': -1.0}

#### UNIVERSE-QUOTES rank-for-the-fill (limit, h30)

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +13.73 | 4.821 | +1,390 | — | +1,390 | 9/12 | +14,620 | -1.49 | +100.0 |
| 2 | +10.99 | 4.821 | +1,113 | — | +1,113 | 9/12 | +11,327 | -4.33 | +100.0 |
| 3 | +9.63 | 4.821 | +975 | — | +975 | 9/12 | +9,681 | -5.75 | +100.0 |
| 4 | +8.26 | 4.821 | +836 | — | +836 | 9/12 | +8,035 | -7.17 | +100.0 |
| 6 | +5.53 | 4.821 | +560 | — | +560 | 8/12 | +4,742 | -10.00 | +100.0 |
| 8 | +2.80 | 4.821 | +283 | — | +283 | 8/12 | +1,449 | -12.84 | +100.0 |
| 10 | +0.06 | 4.821 | +6 | — | +6 | 8/12 | -1,844 | -15.67 | +100.0 |
| 12 | -2.67 | 4.821 | -270 | — | -270 | 6/12 | -5,137 | -18.51 | +100.0 |

break-even bps/side: {'all': 10.05, 'y1': None, 'y2': 10.05}
identity: {'tickets': 1210, 'per_ticket_10bps': 0.064, 'per_ticket_harness': 0.064, 'maxdiff': 0.0, 'passive_frac': 1.0, 'ext_legs': 0}
inverted: {'0': -6.84, '10': -21.61}

#### VS2 W8RSd

| bps/side | $/ticket | tkts/day | $/month | Y1 $/mo | Y2 $/mo | months + | ex-best-day | random $/tkt | pct vs random |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +47.74 | 0.757 | +759 | +1,562 | +152 | 11/23 | +9,278 | +2.01 | +93.3 |
| 2 | +41.81 | 0.757 | +664 | +1,469 | +57 | 10/23 | +7,275 | -3.84 | +93.3 |
| 3 | +38.85 | 0.757 | +617 | +1,423 | +9 | 10/23 | +6,274 | -6.76 | +93.3 |
| 4 | +35.89 | 0.757 | +570 | +1,376 | -38 | 9/23 | +5,273 | -9.69 | +93.3 |
| 6 | +29.96 | 0.757 | +476 | +1,283 | -133 | 9/23 | +3,270 | -15.54 | +93.3 |
| 8 | +24.03 | 0.757 | +382 | +1,190 | -228 | 9/23 | +1,268 | -21.39 | +93.3 |
| 10 | +18.10 | 0.757 | +288 | +1,097 | -323 | 9/23 | -735 | -27.24 | +93.3 |
| 12 | +12.17 | 0.757 | +193 | +1,004 | -418 | 9/23 | -2,737 | -33.09 | +93.3 |

break-even bps/side: {'all': 16.11, 'y1': 33.57, 'y2': 3.2}
identity: {'legs': 339, 'tickets': 339, 'total_10bps': 6135.81, 'total_harness': 6139.78}
