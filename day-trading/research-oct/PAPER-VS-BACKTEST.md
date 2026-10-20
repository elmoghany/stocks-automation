# PAPER-VS-BT: does the backtest agree with paper trading? (2026-10-05 … 2026-10-19, 11 sessions)

Agent PAPER-VS-BT, 2026-10-19. Read-only: no orders, no live code touched. All money is at $10,000 per trade.

## The answer in plain English

**Partly.** It depends on the book.

| book | paper result (11 days) | backtest result, same 11 days | do the trades match? | verdict |
|---|---:|---:|---|---|
| **R4** | **−$1,698** on 12 trades (10-14 rebuilt) | **−$1,804** on 22 trades (independent full-day bars) | **No.** Only 1 of 12 paper trades is in the backtest (BCYC on 10-05) | **The totals agree, the trades do not** |
| **R15** | $0, 0 trades | $0, 0 trades | **Yes**, 11/11 days | **Agrees exactly** |
| **RL** | **−$97** on 4 trades (10-14 rebuilt) | **+$92** on 3 trades | **No.** 0 of 4 match exactly; the same name (ABUS) on 10-16, two steps apart | **The signal days agree, the trades do not** |
| all three | **−$1,795** | **−$1,712** | | |

What this means:

1. **The live code does what the backtest code does.** Replaying the live R4 code on the session's own saved inputs reproduces **10 of 10** live-track R4 entries (10-09 → 10-19), with the same names and the same grids. The same holds for R15 (11/11) and for the RL breadth series (on average within 0.001–0.003 of the live value). There is no logic bug that makes paper trade differently from the rules. There are four smaller bugs, listed at the end.
2. **The data the live session sees is not the data the backtest sees.** That is why the trades differ.
   - **R4** ranks gappers by "coil" (price / day's high). At a typical decision about 11 names (middle half: 6–18) sit within 0.5% of their high and about 5 sit exactly at it. The order among them depends on the exact second the price is read.
   - The live scanner's high also turned out to **leave out the premarket high**. Bars include it.
   - So the live top-ranked name matches the backtest's top-ranked name at only **36% of decision grids** (129 of 358).
   - **RL** trades only when market breadth drops below −2.38%. The live scan reads breadth about a minute later than the bar close, and the two differ by about 0.1–0.3%. That is enough to move the first entry by one or more 5-minute steps.
3. **Paper's R4 loss is normal for this strategy.**
   - The backtest of the live policy expects −$65/day, so about −$720 over 11 days. Paper lost −$1,698.
   - Across all 456 rolling 11-day windows of the 466-day backtest, 37% end at −$1,698 or worse. The median 11-day result is −$952, and 1 window in 10 ends below −$3,763.
   - **So −$1,698 is inside what the backtest predicts.** It is a little worse than the median, not an outlier.
4. **Live fills cost less than the backtest assumes.**
   - Paper's real fills (buy at the ask, sell at the bid) were only **$1.23 per trade worse** than the model fills. Measured against the mid price, the cost was about **$22 per round trip**.
   - The backtest charges about **$28 per round trip** (15 bps per side).
   - So fill cost is **not** why paper and the backtest differ.

## Per-day comparison

### R4 (gapper "coil" book)

Policy in force: **lockstep** (model + book veto, wait while the model holds) on 10-05 … 10-08; the **LIVE track** ("move on to the next candidate", PINNED filter) from 10-09.

"Backtest" = `p3_r4_live.live_sim`, the exact engine behind the −$30/trade, −$65/day `r4_live` expectation, fed with **full-day Robinhood 1-minute bars (04:00–15:05) for every +10% gapper of the day**, fetched after the close. Model fills, $10k, minus 15 bps per side.

"Saved replay" = the live code (`p3_r4.live_step` + `watch_exit`) re-run end-of-day on what the session itself saved (scan snapshots, its bars, its logged book checks).

| day | paper (official fills) | backtest on full bars (net) | same trade? | why different | saved replay = paper? |
|---|---|---|---|---|---|
| 10-05 (lockstep) | BCYC 10:20 → bearish 11:09: **+$206.64** | NU −17, **BCYC +220**, PBR.A −8, PBR −24, MODD −17: **+$154.66** | **BCYC yes** (1 of 5) | The backtest ranks NU (+14%, 9M shares) first at 09:35. The live scanner had MI first; MI was refused on spread/depth and then halted, and lockstep waited behind it. | lockstep day (new policy also takes BCYC) |
| 10-06 (lockstep) | GLWG 14:05 → flatten: **−$267.03** | ASTX +301, NTSK −407: **−$105.83** | no | Live model picks XHG/APUS/BESS were all vetoed on spread (paper waited); the backtest ranked ASTX first | lockstep (new policy also takes GLWG) |
| 10-07 (lockstep) | no trade (SMXT vetoed, PENU stale): **$0** | ASTN 09:35 → flatten: **−$168.90** | no | Backtest's spread proxy refused SMXT too, then took ASTN; live lockstep waited | — |
| 10-08 (lockstep) | no trade (CCG vetoed, PCRX stale): **$0** | CCG −363, ASTN +317: **−$46.11** | CCG was paper's model pick | The bar spread proxy **let CCG through**; the live quote showed a 13.95% spread | — |
| 10-09 | HUM 09:40 → flatten: **−$379.94** | AXTC 09:35 → flatten: **−$631.98** | no | Live refused ASTN/AXTC/NN/CIEX on real spread at 09:35; backtest's proxy passed AXTC | **yes** (HUM 09:40) |
| 10-12 | NOWL 09:35 → flatten: **−$987.84** | ASTT 09:35 (320 sh): **+$39.12** | no | Live refused ASTT on **DEPTH**, but that check ignored the share cap (bug 3): ASTT should have passed | **yes** (NOWL) |
| 10-13 | RAMZ 09:35 → flatten: **−$223.04** | ASTN +358, RIBB −42, CANG −517: **−$201.20** | no | Live refused ASTN on real spread (1.74%); the proxy passed it | **yes** (RAMZ) |
| 10-14 | QBTZ 09:35 → 15:00 flatten ≈ 29.615: **≈ +$736.67** (crash; rebuilt from bars) | ASTN +365, IONZ +22: **+$387.28** | no | Live refused ASTN on real spread again | **yes** (QBTZ) |
| 10-15 | SKDD 09:35 → flatten: **−$750.27** | DAMD +94, IREZ −939, USGG +39: **−$805.81** | no | Live scanner coil 1.000 for SKDD vs 0.975 on bars (premarket high left out, bug 1) | **yes** (SKDD) |
| 10-16 | IREZ +153.44, MSTZ 0.00, CORD +20.66, QBTZ +125.55: **+$299.65** | APLZ 09:35 (78 sh, held to close): **+$329.94** | no | Live refused APLZ on real spread (1.15%) | **yes** (all 4) |
| 10-19 | ASTX 09:45 → flatten: **−$332.64** | MRNX 09:35 (50 sh): **−$755.14** | no | MRNX was not in the live top 8. The live top 2 (TERG, MLCC) had scanner coil above 1.0 (bug 2), and INT was wrongly refused on DEPTH (bug 3) | **yes** (ASTX 09:45) |
| **total** | **−$1,697.80** (12 trades) | **−$1,803.97** (22 trades) | **1 / 12** | | **10 / 10** live-track |

The 11-day expectation (`r4_live`) was −$720 on about 24 trades.

**R4 MODEL / parity track** (unchanged backtest, no veto).
- Backtest on full bars: **−$2,219** on 27 legs.
- The model's first pick matched on 5 legs: BCYC (10-05), SMXT and PENU (10-07), CCG (10-08), ASTN (10-09). After 10-09 it matched on no day: COHQ vs XRPN, AIXI vs ASTN, QBTZ vs ASTN, SKDD vs DAMD, QXL vs APLZ, MLCC (stuck) vs MRNX.
- Paper's own parity book (official + shadow legs at refusal asks) was −$4,929 through 10-16. That uses a different fill convention, so it is not added up here.

### R15 (fresh earnings + green at 09:35)

| day | fresh in-universe earnings | paper | backtest | agree |
|---|---|---|---|---|
| 10-05, 06, 07, 09, 12, 13, 14, 16, 19 | none | no trade | no trade | yes |
| 10-08 | ANGO (10-08 am, 2.1 h old) | no trade: red −198 bp | no trade: red **−198.2 bp** | yes |
| 10-15 | CHRN (10-14 pm, 17.1 h old) | no trade: 09:35 bar unprinted, red −465 bp | no trade: unprinted, red **−465.4 bp** | yes |

- The calendar was pulled again after the fact (one call covering 10-02 … 10-19, 158 rows). Its in-universe events are the same two the live session ingested.
- For reference only (the rule says skip): ANGO would have lost about −$1,063 and CHRN made about +$1,047.
- Expected R15 activity was 0.248 trades/day, about 2.7 trades in 11 days. Zero is unlucky (about a 7% chance if trades arrive at random) but plausible: early-to-mid October is before most of this 95-name universe reports.

### RL (breadth sell-off + below VWAP)

| day | paper | backtest on full bars (net 6 bps) | why different |
|---|---|---|---|
| 10-14 | AMPX 13:10 → trail 14:11: −$307.50; BB 14:10 → 15:59 flatten ≈ 8.225: ≈ +$79.63 (crash, rebuilt). **≈ −$227.87** | ABUS 12:15 → 15:59 flatten: **+$90.48** | At 12:15 bar breadth was −0.0239, just past the −0.02379 gate; the live scan read −0.0230. Backtest entered 55 min earlier and so never held AMPX. At 14:10 live re-entry skipped AMPX because its 14:10 bar was not ingested yet; the rule would have re-entered AMPX, live took BB |
| 10-16 | ABUS 11:25 → tmax 15:36: +$130.90 (**2,380 sh; the rule's cap was 1,505**, bug 4); KOPN 15:35 → flatten: $0.00. **+$130.90** | ABUS 11:15 (337 sh) → tmax 15:21: +$13.45; AGEN 15:25 → flatten: −$12.31. **+$1.14** | Same name, two steps earlier. Bar breadth crossed the gate at 11:10 (−0.0261 vs live −0.0232) |
| other 9 days | no trade | no trade | Breadth never reached the gate in either. Closest: 10-12, −0.0212 on bars vs −0.0187 live |
| **total** | **−$96.97** (4 trades) | **+$91.62** (3 trades) | |

- Breadth, bars vs live state, mean absolute gap per step: 0.0006–0.0028 by day (max 0.0071).
- Expected over 11 days: 0.341 trades/day × $16.91 ≈ 3.8 trades, +$63.

## Where the dollars went (R4, 11 days)

A step-by-step ladder, each step changing one thing.

| step | total | change | what changed |
|---|---:|---:|---|
| expectation (`r4_live`, −$65.43/day) | −$720 | | |
| 1. backtest, live policy, full independent bars, bar spread proxy | **−$1,804** | | the backtest of these 11 days |
| 2. step 1 ranked the way the live scanner ranks (high = RTH only) | −$1,804 | $0 | the coil-definition bug did not change any traded leg on these days |
| 3. step 1 with the **real** refusals the session logged (spread/depth/halt) instead of the bar proxy | −$2,626 | **−$822** | the bar proxy passed ASTN (×2), APLZ, AXTC, CCG; the real quotes refused them. On these days the proxy was the lucky one |
| 4. the paper's own picks, model fills, $10k, minus 15 bps (saved replay; lockstep days = paper's legs) | −$1,931 | **+$695** | universe, coil and snapshot timing: live and backtest pick different names from the same near-tied top of the list |
| 5. paper at model fills, actual share counts, no cost charge | −$1,683 | +$248 | sizing (e.g. QBTZ 10-16 capped at 135 sh, not $10k) and dropping the 15 bp charge (~$28/trade) |
| 6. **paper, official quote fills** | **−$1,698** | **−$15** | live fills vs model fills: **−$1.23 per trade** |

Steps 3 and 4 are not additive with step 2 in any deeper sense. Each is the next run with one more input switched to what the session saw.

**Cause summary, R4:**
- (b) different pick, universe/coil/timing: 11 of 12 trades. ±$700 on these days, sign random.
- (b) different pick, real spread veto vs the bar proxy: 5 backtest legs. −$822 against the backtest here.
- (b) wrong DEPTH refusals (bug 3): 2 trades (10-12 NOWL instead of ASTT, 10-19 ASTX instead of INT). The paper book would have lost about **$1,330 less** (ASTT +$51 at 320 sh vs NOWL −$988; INT about −$40 at 100 sh vs ASTX −$333).
- (a) same trade, different fill: −$1.23/trade (−$15 total).
- (d) outage: 10-14 crash. QBTZ flattened in the rebuild at ≈ +$737; the official exit is unknown, about $20 lower at a typical spread.

## Data sources and coverage

| book | backtest data | coverage |
|---|---|---|
| R4 | **Universe:** Polygon (Massive) grouped-daily for 10-01 … 10-16 (`massive.grouped_daily` via `massive._get`, 12.5 s pacing): every clean ticker whose day high was ≥ 1.10 × the prior close and ≥ $2, union every name the live scanner returned that day. For 10-19 Polygon refused the same-day grouped file (403), so that day used the scanner names only, with pc = the 10-16 Polygon close. **Bars:** Robinhood `get_equity_historicals` 1-minute, `bounds=extended`, 04:00–15:05 ET, 10 names per call, fetched after the close (199 calls) | 1,898 of 1,936 symbol-days (98%). The 38 missing are unknown symbols or names with no prints |
| R15 | Robinhood earnings calendar re-pulled (10-02 … 10-19); Robinhood RTH 1-minute bars | complete |
| RL | Robinhood 1-minute RTH bars, all 95 universe names × 11 days (10 calls) | 1,045 / 1,045. VWAP starts at 09:30 instead of 04:00 (the rules measured 0/87 entries changed by this) |
| cross-check | Polygon 1-minute bars for every traded or backtest-picked leg | see below |

Polygon was the intended independent source. At 5 requests/minute (12.5 s per call), the ~1,900 gapper symbol-days would have taken about 6.6 hours. So Polygon supplied the universe (grouped-daily) and a per-leg price cross-check, and Robinhood supplied the bulk minute bars. Robinhood is the same vendor the live session reads, but these are complete after-the-close bars for every name, not the partial set the session fetched.

**Polygon cross-check** (`plan/pvb_poly_check.py`). Each book's own exit code was replayed minute by minute on Robinhood bars and on Polygon bars for every leg either side traded: 40 legs, 36 with both sources. 10-19 has no Polygon minute bars yet (403).

- **Same exit minute and reason: 26 of 36 (72%).** The mean P&L gap is **$56 per $10k ticket**. Polygon is +$855 higher in total, mostly on three thin names (RIBB 10-13 +$1,022, CCG 10-08 +$293, ASTN 10-13 −$140).
- **On the legs paper actually traded, the two sources agree:**
  - identical on BCYC, HUM, MSTZ and CORD (R4) and on AMPX, BB, ABUS and KOPN (RL);
  - within $10 on GLWG, NOWL, RAMZ, SKDD and IREZ.
- **The one that matters is the 10-14 rebuild of QBTZ.**
  - On Polygon bars a bearish-engulfing exit fires at 13:11 @ 28.90, about +$471 for paper's 362 shares.
  - On Robinhood bars there is no exit and it flattens at 29.615, about +$737.
  - The live watcher, which reads Robinhood, was still holding QBTZ at 14:36 when the PC crashed. So the Robinhood rebuild is the one consistent with the live book.
- So for these legs the data vendor moves a single leg by about $56. It does not explain why paper and the backtest pick different names.

## Is the expectation itself still right?

- **Harness check.** `plan/pvb_dist.py` re-ran the r4_live backtest over the 444 + 22 days and reproduced the published figures exactly: −$65.43/day on 968 in-sample trades.
- **Re-ranked the way the live scanner actually ranks** (high = RTH only):
  - in-sample: −$20.00/trade, −$45.32/day on 1,006 trades (vs −$30.01, −$65.43);
  - Aug-2026 OOS: −$46.62/trade (vs −$55.10).
- So bug 1 makes the live book rank slightly *better* than the backtest it is scored against. The difference is about +$10/trade, well inside the noise. The expectation does not need re-basing because of it.
- **11-day windows of the live-policy backtest:** median −$952, 25th percentile −$2,496, 10th percentile −$3,763, 5th percentile −$4,627. Paper's −$1,698 sits at the 37th percentile, and −$2,434 (the scoreboard without the 10-14 rebuild) at the 26th.

## Halal tag

- All 12 paper R4 trades were halal REFUSE-TO-EVALUATE, so the halal-PASS R4 total is $0 on 0 trades.
- RL: KOPN (10-16) was PASS, $0.00. ABUS, AMPX and BB were REFUSE-TO-EVALUATE. The halal-PASS RL total is $0.00 on 1 trade.
- Backtest legs were not halal-screened (selection ignores halal by mandate).

## Bugs found in live code / live data (NOT fixed; the 09:10 session runs this code)

1. **The R4 scanner's Coil omits the premarket high.**
   - The rules (step 3 and the deviation table) say coil = last / session high *including premarket*. The saved scan "P3 R4 gapper coil" (`0cc1cab3…`) column `HighAll`, which `plan/p3_r4.py:494-511 ingest_scan` takes as given, is the **regular-session high**.
   - Where premarket and RTH highs differ by more than 0.5%, the scan high matched the RTH high on **4,098 of 4,425 rows** (93%; per day 87–100%; `plan/pvb_coilcheck.py`, `data/pvb/coilcheck.json`).
   - Effect: premarket faders (MI, ITOC, DCX, QXL, SKDD, MXLL, AKTX) show coil 1.000 live but 0.61–0.98 on bars, and rank at the top.
   - Measured cost: about **+$10/trade in the live book's favour** on the 466-day backtest. It is a fidelity bug, not a money bug.
   - **Fix:** in `fd_from_snaps`, for names with 04:00 bars use coil = last / max(scan high, bar high 04:00..t), then re-rank; or switch the scan column to an all-session high if the scanner has one.
2. **Scanner Coil above 1.0 is accepted and ranks first.**
   - 76 rows on 10-05 and 10-19, e.g. TERG 1.117 and MLCC 1.080 at 10-19 09:35. The scan's last price was above its own high, on names with no RTH prints in the bars.
   - MLCC then **froze the MODEL track all day** (NEED_DATA loop: `run_live`, `plan/p3_r4.py:299-304`, has no `--no-bars` path; noted in the 10-19 EOD).
   - **Fix:** clamp coil to ≤ 1.0 in `ingest_scan` (`plan/p3_r4.py:501-503`), and let `--no-bars SYM` also skip the name on the model track.
3. **The R4 DEPTH check ignores the share cap.**
   - `plan/p3_r4.py:602` sets `want = int(TICKET // ask)`. The rules (LIVE track 2 and 4) say the depth test is ≥ 25% of the **intended** shares = floor(min($10k, shares_cap × ask) / ask). `:634` also prints `shares=want` (uncapped).
   - **Two wrong refusals:**
     - ASTT on 10-12: want 806, cap 320, depth 200 ≥ 80;
     - INT on 10-19: want 665, cap 100, depth 100 ≥ 25.
   - Counterfactual on those two days: about **+$1,330** for paper (ASTT/INT instead of NOWL/ASTX). The tickets would have been small, $1.5k–$4k, in illiquid names.
   - **Fix:** pass the screen's `shares_cap` into `check_book` and use want = floor(min(TICKET, cap × ask) / ask).
4. **The RL ENTER line carries no share cap.**
   - `plan/p3_rl.py:602-614` builds the ENTER action without the 20% volume cap. The engine applies the cap to the model leg (`:305-307`), but the prompt only caps "if given", so the agent bought floor($10k / ask).
   - **ABUS 10-16: 2,380 shares bought vs the rule's 1,505 (58% oversized).** It happened to add about +$48.
   - **Fix:** add `shares_cap=floor(volcap)` from the matching `pend_in` entry to the ENTER action.
5. **Minor, ops.** On 10-14 the live RL engine did not re-enter AMPX at 14:10 (rule-eligible) because AMPX's 14:10 bar had not been ingested when `--now 14:11` ran, so it took BB. This is the same ingest-lag lesson as 10-16.

## Caveats

- **R4 cannot be matched trade by trade from bars.** Its decision is a near-tie among about 11 names (middle half 6–18) sorted by a ratio that moves within the minute. Even the top-8 *set* overlaps only 5.2 of 8 per grid.
- **A backtest is a distribution, not a forecast of which name.** Totals agreeing within $106 on these days is partly luck: one day's standard deviation is $849.
- **The R4 bar spread proxy is too lenient on these days.** It passed five names whose live spread was 1.0–14% (AXTC 1.0%, ASTN 1.7% and 1.1%, APLZ 1.15%, CCG 13.95%). The expectation's −$30/trade relies on that proxy. A real-quote veto would refuse more of those names, which is how R4's edge was already known to vanish (LEGACY-15).
- **10-14 is rebuilt from bars** (QBTZ 15:00 flatten at the last print ≤ 15:00, 29.615; BB 15:59 close 8.225). The official exits are unknown.
- **Lockstep days (10-05 … 10-08)** ran the old R4 policy. Their paper trades are model legs that passed the book check, so the live-policy backtest is a counterfactual there.

## Files

- **Scripts**:
  - `plan/pvb_universe.py`, `pvb_poly_fetch.py` and `pvb_rh2csv.py` (data);
  - `pvb_r4.py` (backtests on full bars, `--coil rth`), `pvb_r4_saved.py` (saved-input replay), `pvb_r15.py` and `pvb_rl.py`;
  - `pvb_coilcheck.py`, `pvb_dist.py` (`--coil-rth`), `pvb_poly_check.py` and `pvb_compare.py` (tables).
- **Outputs** (not committed: bulky): `data/pvb/` holds `r4_bt_rhx.json`, `r4_bt_rhx_rthcoil.json`, `r4_saved.json`, `r15_compare.json`, `rl_compare.json`, `coilcheck.json`, `r4_live_daily*.json`, `poly_check.json` and `summary.json`, plus `rh/`, `rhx/` and `poly/` bars.
