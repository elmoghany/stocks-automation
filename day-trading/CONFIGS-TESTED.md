# Penny Strategy — Registry of All Tested Configurations

Every configuration simulated during calibration, with results and the
script that reproduces it. All tests: halal gate + up>=10% + rvol>=5x
enforced; $ figures are P&L over the stated window. Data windows differ
between experiments (noted) — compare within a table, not across tables.

DEFAULT AS OF 2026-08-03 (champion): $2-14 band, NO float limit, upward
sectors, 7AM-NOON window, TOP-2 gappers/day, $15k/position, 10% bar-volume
cap, ORB + all-bullish-pattern entries, trail 20%, stop 5%, same-day flat.
Measured +$55,495 over the Jun-Jul window (+$1,734/traded day).

---

## 1. Entry/exit pattern grids (2026-08-01, 1-min bars, 7-10AM, $1k/trade)
Script: `day-trading.py candletest / gridtest / pairtest` on SCYX/TCX/REPL.

- candletest (5 buy sets x 4 sell modes, 20 configs): hammer_family won all
  4 sell modes (+$437..+$908); best = hammer_family+strong_if_profit +$908.
  all_bullish/-engulfing/multi_candle/strong_reversal lost in most modes.
- With volume confirm added: hammer+strong +$713 (8t, 62%); vol filter
  lifted all_bullish from -$242 to +$322.
- gridtest (5 buy sets x caps 1/2/3/unlim, 20 configs): hammer 3/unlim
  +$74.36 best at $1k sizing; 1-trade/day LOSES (-$16).
- pairtest (10 entries x 12 exits = 120 combos): exits barely matter
  (target/stop fire first); best pairs hammer->any +$24.96 (1t),
  inverted_hammer->bearish_engulfing +$19.69 (5t, 60%), tweezer_bottom->
  tweezer_top +$13. RSI entry -$19; MACD entry worst (-$75..-$119);
  rising_three never formed. Conclusion: pattern families beat singles.

## 2. Reward/risk + sizing (2026-08-01/02)
- Fixed $0.18 target vs 2:1 (0.30/0.15): 0.18 made +$1,093 vs +$364
  across FCUV/SCYX/TCX regular hours (high win rate beats fat targets on
  scalps) — later superseded by trailing exits.
- 2x-day hunt (`optimize`): fixed % targets max +6.9%; TRAIL 20-25% +
  all-patterns turned $1,000 -> $1,996 (+99.6%) on FCUV's +836% day.
  Trail 15% only +4.3%; trail 10% negative.

## 3. 60-day market-wide (2026-08-02, 5-min bars, $1k/trade, 7-10AM)
Script: `plan/penny_backtest_60d.py` + `penny_backfill_rh.py`.
- A calibrated hammer default: +$308 (+30.8%).
- B trail20+all-patterns: +$1,810 (+181%). ADOPTED.

## 4. Sensitivity sweep, 26 variants (2026-08-02, $1k, 7-10AM)
Script: `plan/penny_sensitivity.py`. Baseline trail20/stop5/allpat +$1,525.
Improvements: top-2/day +$130; surge 3% +$47 (noise). No effect: band
ceiling $20/$30. Hurts: trail 25 -$59; trail 30 -$187; stop 8 -$42;
stop 10 -$33; stop 3 -$1,150; trail 15 -$1,341; trail 10 -$1,185;
max 1/day -$1,256; max 2 -$135; max 3 -$285; vol confirm ON -$354;
dip 10c -$196; dip 20c -$340; dip 2c ~0; surge 1% -$100; surge 5% -$133;
rvol>=8x -$413; rvol>=15x -$566; hammer-only -$66; strong_reversal -$141;
multi_candle -$124.

## 5. ORB test (2026-08-03, $1k, YTD sim days)
Script: `plan/penny_orb_test.py`. A dip-only +$1,594 (37t); B ORB-only
+$1,581 (19t); C combined +$2,224 (+39%). ADOPTED (orb=True).
Zero-day causes: 3 never-in-band (CPHI +2009% at $0.81-1.20), 5 never
+10% in window, 7 sequencing (fixed by ORB: RTB +$288, EGG +$301).

## 6. Scaling test (2026-08-03, ORB default, 10% vol cap)
Script: `plan/penny_scale_test.py` (top-1 / top-2):
$1k +$2,783/+$2,873; $5k +$11,075/+$11,653; $10k +$19,470/+$20,800;
$15k +$27,741/+$29,878; $20k +$35,957/+$38,819; $30k +$52,295/+$56,379.
Liquidity cap binds: 30x capital -> 18.8x profit. $5k day distribution:
avg +$461/traded day, median +$381, 7/34 days >=+$1k, 9/24 loss days.

## 7. Rule-relaxation V0-V6 + Ross (2026-08-03, $15k, Jun4-Jul30 set)
Scripts: `plan/penny_expand_test.py`, `penny_expand2.py`,
`ross_cameron_test.py`. (days / total / avg / worst)
- V0 $2-16 float 7-10AM:      18  +$21,084  +$1,171  -$1,500
- V1 no ceiling 7-10AM:       21  +$19,660    +$936  -$1,500
- V2 $2-16 float 7-NOON:      27  +$32,453  +$1,202  -$2,142
- V3 $2-16 float full day:    32  +$35,184  +$1,100  -$2,963
- V4 no-ceil full day:        35  +$31,073    +$888  -$2,963
- V5 NO FLOAT 7-10AM:         22  +$24,313  +$1,105  -$1,500
- V6 all relaxed:             38  +$39,739  +$1,046  -$3,750
- ROSS-HALAL (pullback 2R, 7-11:30, $2-20): 19 days -$14,988 (5W),
  worst -$4,286. (5-min mechanization caveat.)

## 8. Nine one-change variants of V2/V3/V6 (2026-08-03, $15k)
Script: `plan/penny_v_variants.py`.
- V2a noon+NOFLOAT+ceil16: 31  +$47,571  +$1,535  -$2,142  <- gen-1 champ
- V2b 1PM window:          28  +$37,799  +$1,350  -$2,892
- V2c trail 25:            27  +$21,313    +$789  -$1,770
- V3a nofloat full day:    38  +$44,607  +$1,174  -$3,750  (== V6a)
- V3b trail 25:            32  +$23,432    +$732  -$3,977
- V3c entries stop noon:   27  +$33,812  +$1,252  -$2,142
- V6b noceil nofloat noon: 34  +$41,236  +$1,213  -$2,142
- V6c trail 25:            38  +$28,948    +$762  -$3,977
Trail 25 lost in ALL bases (trail 20 confirmed 3x).

## 9. Second-gen variants from V2a (2026-08-03, $15k)
Script: `plan/penny_v2a_variants.py`.
- A1 window 7-11AM:        26  +$33,889  +$1,303  -$1,940
- A2 TOP-2 gappers:        33  +$55,373  +$1,678  -$2,142
- A3 stop 8%:              31  +$41,101  +$1,326  -$3,942
- B1 no PM entries:        31  +$47,385  +$1,529  -$2,142
- B2 window 7-2PM:         35  +$53,606  +$1,532  -$3,750
- B3 full-day top-2:       38  +$54,345  +$1,430  -$5,036
- C1 V6b top-2:            36  +$49,862  +$1,385  -$3,074
- C2 V6b ceil $30:         32  +$41,904  +$1,310  -$2,142
- C3 V6b entries stop 11:  32  +$33,006  +$1,031  -$1,940
- CAP14 (V2a $2-14):       30  +$47,819  +$1,594  -$2,142
- CAP12 (V2a $2-12):       28  +$42,013  +$1,500  -$2,142
- CAP10 (V2a $2-10):       27  +$47,197  +$1,748  -$2,142

## 10. Price-cap matrix on top-3 (2026-08-03, $15k)
Script: `plan/penny_cap_matrix.py`.
- A2 x $16: 33 +$55,373 +$1,678 | x $14: 32 +$55,495 +$1,734 <- CHAMPION
  | x $12: 31 +$46,763 +$1,508 | x $10: 29 +$51,606 +$1,780 (best avg)
- B3 x $16: 38 +$54,345 +$1,430 | $14: +$53,743 | $12: +$42,722
  | $10: +$36,985 (full day prefers looser caps)
- B2 x $16: 35 +$53,606 +$1,532 | $14: +$53,895 +$1,633 | $12: +$46,207
  | $10: +$42,950
The $12 dip is real everywhere: it chops $10-12 entries (BIYA/QTTB class).

## 11. FULL YEAR Aug 2025-Aug 2026 (2026-08-03, Massive 1-MIN bars, $15k)
Script: `plan/penny_year_backtest.py` (label "year"). 232 qualifying days.
- C1nocap  noceil noon top-2: 237d  +$174,134  +$735/d  worst -$8,809
- B2cap14  $2-14 7-2PM top-1: 207d  +$129,759  +$627/d  worst -$5,353
- B2cap16  $2-16 7-2PM top-1: 214d  +$129,709  +$606/d  worst -$5,353
- CAP14t1  $2-14 noon top-1:  194d  +$111,813  +$576/d  worst -$4,985
- V2a_t1   $2-16 noon top-1:  200d  +$108,939  +$545/d  worst -$4,985
- B3cap16  full-day top-2:    231d   +$98,906  +$428/d  worst -$9,518
- B3cap14  full-day top-2:    227d   +$96,148  +$424/d  worst -$9,518
- A2cap14  noon top-2 (dflt): 216d   +$95,925  +$444/d  worst -$8,809
- A2cap16  noon top-2:        220d   +$93,822  +$426/d  worst -$8,809
- A2cap10  noon top-2:        194d   +$60,296  +$311/d  worst -$7,007
Monthly (A2cap14): Apr-Jul26 +$111k; Aug25-Mar26 net -$15k (5 neg months).
CAUTION: ran on 1-MIN bars vs 5-MIN calibration -- granularity changes
vol-cap sizing, ORB range, surge window; see next section before comparing
per-day numbers to the 8-week results.

## 12. ADAPTATION SERIES "AX" (2026-08-03, both years, $15k/day, corrected)
Script: `plan/penny_adapt_experiments.py`. Baseline = live default
(C1 top-1 + calm-gap). One change each. IDs are unique and permanent.
              Y1 total  Y1 avg/d  Y2 total  Y2 avg/d  negm Y1/Y2
- AX00 baseline (live default) +$206,466  +$1,007  +$94,852  +$597  0 / 4
- AX01 dynamic sectors (monthly as-of ETF trends)
                               +$214,849  +$1,113  +$87,219  +$681  0 / 4
- AX03 adaptive calm-gap (trailing-median threshold)
                               +$182,890    +$963  +$88,582  +$615  0 / 4
- AX05 equity throttle (5d P&L<-$3k -> half size)
                               +$199,496    +$973  +$93,742  +$590  0 / 4
- AX07 day-2 continuation (fallback)
                               +$206,466  +$1,007  +$95,616  +$598  0 / 4
- AX09 two-shot morning        +$206,466  +$1,007  +$94,852  +$597  0 / 4 (never triggered)
Verdict: AX01 improves Y1 (+$8.4k) and Y2 avg/day (+$84/d) but trades 31
fewer Y2 days (total -$7.6k); others neutral-to-worse; none broke the
Y2 Jan-May desert (4 neg months everywhere).
QUEUED (not yet run): AX02 gapper-supply throttle, AX04 premarket
structure scoring, AX06 scale-out ladder, AX08 adaptive trail widening,
AX10 Finnhub news-tier gate.

## 13. AX ROUND 2 (2026-08-03, both years, $15k/day, 44 runs)
Script: `plan/penny_ax_round2.py`. (Y1 total / Y2 total vs AX00
$205,291 / $94,852; harness scans top-8 calm so AX00 differs slightly
from section 12.)
ADOPTED -> AX18 stop8+scaleout combo: Y1 +$209,935, Y2 +$104,174
(2 neg months -- best Y2 consistency). Components: AX16-stop8 (+$210.0k/
+$103.9k, improves BOTH years) and AX06 scale-out 1/3@+25% (+$204.9k/
+$100.2k, free Y1 + better Y2).
REJECTED: AX02 throttle (-$28k/-$11k rel), AX04 structure-scoring
(-$8k/-$27k), AX08 trail-widen (-$6k/0 -- never triggers Y2), AX12
cluster-sectors (+$6k/-$18k), AX14 top-N ALL N>1 dilute (N=1 optimal
both years; calm supply caps ~4/day), AX15 afternoon 2-8PM (Y1 +$619,
Y2 -$13,175 -- conclusively dead), AX16 trail 15/25/30 (20% peak both
years two-year-net; NOTE trail 25-30 BEATS 20 in Y2 alone: +$108k/
+$114k -- regime-conditional trail = future idea), AX16 stop3
(-$4k/-$35k), AX17a VWAP entry (-$131k/-$50k), AX17b EMA entry (worst).
NEUTRAL: AX13 no-sector filter -- IDENTICAL both years (sector rule
inert at top-of-book; monster-blocker is halal timing -> AX11).
QUEUED: AX10 news-tier, AX11 point-in-time halal (biggest lever).

## 14. TARGET CAMPAIGN (2026-08-03, pt-halal era, both years, $15k/day)
Scripts: penny_ax11_pt_halal.py, penny_ax11b_massive.py (+inline AX19).
- AX11  pt-halal yf-coverage:   Y1 +$164,855 (88d) / Y2 +$89,832 (75d)
- AX11b pt-halal Massive:       Y1 +$211,585 (135d,0negm) / Y2 +$105,474 (111d)
- AX19  +cond-trail walk-12:    Y1 +$191,952 / Y2 +$124,548 (1 negm)
- AX19b +cond-trail walk-8:     Y1 +$198,542 / Y2 +$121,195
- AX19c thresh 1.0 (ADOPTED):   Y1 +$199,999 / Y2 +$120,648
Note: pt-halal is the honest compliance basis; earlier sections used
today's-snapshot halal and OVERSTATE the compliant opportunity set.

## 15. AX20/AX21 WIDENED UNIVERSE + RECYCLING (2026-08-03/04)
Scripts: penny_ax20_discover.py, penny_ax20_backfill.py,
penny_ax21_recycle.py. Data: gappers2_{label}.json (no $75 cap, no
universe.json, hist_n recorded, gd/ raw cache), lazy m1 fetch.
- AX21  earliest-entry picker k=1 (old univ):  Y1 +$81k / Y2 +$57k (pick quality >> speed)
- AX21c commit+recycle k=0 (old univ):         Y1 +$210,579 / Y2 +$103,922 (BELOW baseline -> recycling DEAD)
- AX20  widened universe, walk-8, trail 20 (ADOPTED DEFAULT):
        Y1 +$244,899 (125d, 0 negm) / Y2 +$314,057 (142d, 1 negm)
        Both +$200k targets MET. Same machine as AX11b; only universe changed.

## 16. X100 CAMPAIGN (2026-08-04, 79/100 experiments + stacking)
Scripts: penny_x100.py (table-driven, X-RESULTS.md has full sorted
table), penny_x100_stack.py (composites). Anchor X091 = AX20 exact.
- PASS singles: X086 +$197.5k (uncapped size; fill caveat), X031
  +$79.6k (orb5), X085 +$66.9k (vf 0.20), X064 +$53.1k (1PM exits,
  sign-off), X087 +$52.8k (window 10min), X084, X032.
- Killed: X026 calm-gate-off (Y2 -$53k), all gain-band restrictions,
  entry cutoffs, max_trades caps, tight stops/trails.
- CHAMPION C02 (orb_bars=5, max_vol_frac=0.20, vol_frac_window=10,
  premarket-high stop-buy extra trigger, rest = AX20):
  Y1 +$357,311 (127d, 0 negm) / Y2 +$455,297 (143d, 0 negm).
- Ceiling C04 uncapped: +$394,761/+$482,998. Stress C05 (10bps):
  +$321,761/+$400,719. C06 (+1PM exits): +$357,991/+$482,047.
Deferred to next run: 21 fetch experiments (X009 news, X015-30
coverage, X075-82 splits, X095 control).

## 17. X200 CAMPAIGN (2026-08-04, gap sweep + volume pressure + C08)
Scripts: penny_x100.py (X201-X240, C08, 8x8 G-sweep), penny_x100_stack.py
(C10-C12). Baselines: X2xx/C08 vs C02; {cfg}G{n} vs own 20% gate.
- GAP SWEEP DEBUNKED: G>=40 rows +~$350k = ONE bad-data day (CIIT
  2026-03-09, 50x one-bar wick). Clean verdict: 20% gate stands.
- Pressure family: entry gates catastrophic; exits weak; TRAIL
  modulation wins (X219 +$48k, X218 +$31k, both 0 negm).
- C08 1PM exits +$62.5k (signed off). Controls X229/X230 failed (good).
- CHAMPION C11 = C02 + pressure-trail(10,0.3,0.3,12,30) + exits-1PM:
  Y1 +$390,687 (133d, 0 negm) / Y2 +$536,350 (147d, 1 negm).
  C10 (strict noon) +$378,765/+$481,805 0 negm both. C12 = C11@10bps:
  +$355,894/+$501,571.
Deferred: fetch queue (X009-X095 F-flagged), wick-hygiene guard.

## 18. X300 CAMPAIGN (2026-08-04, anatomy-driven, strict noon)
Scripts: penny_x100.py X301-X320, penny_x100_stack.py C20-C22.
- Controls: X318 shuffle -$114k FAIL(good); X317 walk-3 -$165k
  (walk-8 tail confirmed); X316/X315 post-hoc picks died.
- X319 wick-guard: $0.00 delta -> adopted (phantom-wick insurance).
- CHAMPION C21 (strict noon) = C02 + pressure-trail(10,.3,.3,10,40)
  + scale-out skip at P>=+0.3 + wick-guard 3x:
  Y1 +$395,243 / Y2 +$519,641, 0 negm both, holdout +$89.8k/+$100.5k,
  C22@10bps +$367,562/+$486,523.

## 19. COVERAGE FAMILY / MISC PROBES (2026-08-04/05)
- Fallback re-picks 8:30/9:00/9:30: -$60k..-$243k (abandons picks
  before the golden hour). Second-pick redeploy: zero (condition never
  fires). Conditional splits X075-X082: -$41k..-$154k all variants.
  min_hist 10/25: negative. Walk 12/16: +$12k both-year (below floor,
  shelf). X095 lag control: fails (good).
- X340/X341 news-tier (Y1-only): rank +$2.6k noise; required -$68k.
- X342/X343 day-2 continuation: identical to C21 (already captured).
- X335-X338 monster mode: neutral (pressure trail already does it).
- Earnings-drift (overnight, separate book): REJECTED -- reactions are
  zero-mean; historical hit-rates not sticky (plan/earnings_probe.py).

## Untested candidates (queue)
- A2 + cap $10 (two changes: top-2 AND $2-10) — best-avg x best-total mix
- surge 3% on the current default (was +$47 at $1k sizing)
- multi-year validation on purchased data (Polygon) — cold-tape regime

## 20. EARNINGS-TRADING BOOK ET01-ET11 (2026-08-05, last-year window)
- ET01 gap>=+3% buy open sell close: -$696 fail
- ET02 gap>=+5%: +$1,782 (prior year -$156: shaky, not adopted)
- ET03 gap<=-3% dip-buy open->close: +$5,182 PASS (prior yr +$7,358)
- ET04 gap<=-5% dip-buy: +$1,917 PASS
- ET05 gap>=+3% + 5y-strong: -$354 fail
- ET06 gap<=-3% dip-buy + 5y-strong: +$3,177 PASS (66.7% win, small n)
- ET07 control |gap|<3%: -$6,108 (control behaves)
- ET08 OVERNIGHT gap-up close->next close: +$9,900 (both yrs +) OVN shelf
- ET09 OVERNIGHT dip close->next close: -$6,202 fail
- ET10 pre-release entry sweep, sell close before release: ALL hours
  negative (-0.4..-0.9%/event; later = worse)
- ET11 pre-release entry sweep, hold through release: ALL hours negative
- Adopted: ET03/ET04/ET06 morning dip-buy watchlist (halal, gap<=-3%).
  Buy-before-earnings: dead at every hour (matches earnings_probe).

### 20b. ET01-ET09 CORRECTED (reaction-day convention fix, same day)
pm reporters now score the NEXT session (was: report day -- wrong).
- ET01 -$1,804 fail | ET02 +$1,268 thin | ET03 +$2,787 thin PASS
- ET04 -$782 fail (was +$1.9k) | ET05 -$1,860 fail | ET06 +$138 ~zero
- ET07 control +$10,377 (bull-tape beta warning) | ET08 OVN +$1,704
- ET09 OVN -$5,169 fail
Prior 20. numbers are ARTIFACTS of the wrong convention where marked.
ET12-ET31 (earnings_x2.py, big universe, gated variants) supersede.

## 21. EARNINGS-X2 ET12-ET33 (2026-08-05, 305 halal names, 1,227 events)
A: ET12 dip+beat open->close +$28,642 ADOPTED (ET31 miss-control ~0)
   ET13 +strong+fin +0.95%/ev | ET14-16 targets: all worse than close
   ET17 2-day: no gain | ET18/19 after-hours: -1.6%/ev HARMFUL
   ET20 pressure n=2 no-data | ET21 deep-dip +$2k weak
B: ET22-26 ladder raw +$21k..+$146k BUT ET32 SPY-adjust halves it and
   ET33 placebo (mid-quarter same-hold) reproduces ~73% of ET28's
   excess -> momentum beta, NOT an earnings edge. REJECTED for
   adoption (also exceeds 1-2-day hold cap).

## 22. EARNINGS-X3 ET40-ET70 ($50k slots, 2026-08-05)
- ET40 minute anchor +0.772%/ev (validates daily) | ET41 bounce-entry
  +0.52% worse | ET42 trail +0.16% | ET43 both -0.04% | ET44 stop-3%
  +0.58% -- penny mechanics REJECTED on large-cap earnings dips
- ET50 sc dip3 +$26.4k | ET51 sc dip5 +$41.6k (58.5% win) | ET53 thin
- ET52 combined 1-slot +$117,164 ~= big-only (no ceiling lift)
- ET60-62 sympathy: ALL negative, REJECT
- ET70a flat $50k 1-slot deepest: +$117,755/yr | ET70b compounding:
  $50k -> $433,593 (+767%), dd -21.9% -- ADOPTED PLAYBOOK basis

## E01 -- EARNINGS CHAMPION (registered 2026-08-05)

Permanent ID: **E01** (earnings book champion; cf. C21 in the day book).
Spec: each morning, among HALAL names (S&P900+600 universe, price >$2)
that BEAT EPS estimates and open <=-3% below prior close: buy the
DEEPEST dip at the 9:30 open with the full slot, sell at that day's
close. One slot/day. No pre-earnings buying, no after-hours entries,
no targets/stops/trails (all tested worse). Sizing: $50k flat
(+$117,755/yr backtested Aug25-Jul26, 99 trades, 62.6% win) or
compounded (E01c: $50k -> $433,593, +767%, max dd -21.9%).
Status: backtested one bull year; needs a paper season. Deepest-dip
slot rule + compounding chosen post-hoc -- revalidate next season.
Receipts: ET12/13 (edge + beat gate), ET31 (miss control ~0),
ET40-45 (mechanics reject), ET50-53 (small caps), ET60-62 (sympathy
reject), ET70 (sizing), ET32/33 (B-family beta controls).

## BL-family: buy-low/sell-high day trading vs E01 (2026-08-05, $50k/event)

bollinger-trading/plan/blsh_intraday.py -- limit-buy 2-3% below the
open on 5y-uptrend halal names (S&P900+600, 489 names), sell same-day
close; volume gates from prior-day pressure/rvol. Window Aug25-Jul26.
- BL01 dip2 strong: n=12,855 fills, 54.5% win, +0.116%/ev (+$745k
  ONLY if you fund every fill -- routinely 50+ concurrent $50k slots,
  $5M+ deployed; per-event edge is inside slippage noise).
- BL02 dip3: +0.163%/ev. BL04 +pressure>=0: +0.161%/ev (mild help).
- BL03 "recovery to open" exit: INVALID -- High >= Open is true by
  definition (the open is inside the day's range), so the target
  always "fills"; textbook OHLC look-ahead artifact. Discarded.
- BL05 NOT-strong control: +0.111%/ev ~= BL01's +0.116% -> the 5-year
  uptrend gate adds ~NOTHING to intraday dip-buying. (It was also
  beta, not edge, in ET28/ET33.)
- BL06 one $50k slot/day (rank by prior-day rvol): -$33,153. BL07
  (same, excluding earnings reaction days): -$11,334.
VERDICT vs E01: at equal capital (one slot/day) BL LOSES (-$33k vs
E01 +$117,755). Generic dips lack the catalyst; E01's edge needs the
earnings-beat information, not just "a strong stock dipped". No
rank-mining for a better BL06 picker -- 251 days would overfit.
BL book stays research-only; E01 remains the champion.

## C11 notes + 1PM re-adoption -> C23 DEFAULT (2026-08-05)

USER DECISION: "make c11 the default" -- the 1PM exit window (withdrawn
during X300 planning) is RE-ADOPTED.

What C11 is: C02 (orb5 + 20%/10-min sizing + PMH trigger) + two-sided
pressure trail (10, 0.30, 0.30, 12, 30) + exits extended to 1PM
(entries still end at noon). Born from the X219 trail family + C08's
signed-off 1PM window. Record: Y1 +$390,687 (133d, 0 negm), Y2
+$536,350 (147d, 1 negm). History: champion 2026-08-04, archived same
week when the user chose strict noon ("keep noon"), re-adopted
2026-08-05. Its 2,839 positions were the win-anatomy dataset (monsters
= 10% of days = ~47% of profit; golden hour 9-10AM; re-entry tail 31%).

C23 test (user: "ok test it"): the X300 improvements (trail widths
10/40, scale-out pressure-skip 0.30, wick guard) had never been
measured inside the 1PM window (X300 ran strict-noon). Result:
- C23 Y1 +$412,879 (0 negm) / Y2 +$579,988 (0 negm)
- vs C11: +$22,192 / +$43,638, dComb +$65,830 (>= $30k floor), negm
  improves (C11's one Y2 negative month disappears). C24 = C23@10bps:
  +$377,509 / +$539,670 (~91-93% kept).
ADOPTED DEFAULT: **C23** -- C11's window, X300's machinery. Reverting
to literal C11 = trail (12,30) + scale_out_pressure_skip None.
day-trading.py defaults + paper_watch (1PM flatten) + skill updated;
Paper Day 3 (2026-08-06) runs C23; E01 papers in parallel, separate
reporting.

## Half-profit reinvestment sizing (R50 policy, 2026-08-05)

USER DIRECTIVE: both books re-invest HALF of profits. slot = base +
0.5 x max(0, cumulative P&L); base never shrinks (losses only eat the
profit buffer). State: {book}/data/paper/slot_state.json, updated at
every close-out. Bases: C23 $15k, E01 $50k.
- E01 backtest under R50: +$208,787/yr vs +$117,755 flat (final slot
  $154k -- trivially fillable on S&P names). ADOPTED.
- C23 under R50: naive math explodes (avg +23.6%/day compounds to
  absurdity) -- NOT REAL: rule 13 (<= 20% of trailing 10-min volume)
  caps fills on penny gappers. Budget-scaling runs (15k/30k/60k/120k,
  plan/c23_budget_scaling.py) quantify the saturation; results to be
  registered when complete. Paper sessions apply R50 with rule 13
  intact, so live slots grow only as far as liquidity allows.

### C23 budget scaling + R50 trajectory (2026-08-05, follow-up)

Measured (plan/c23_budget_scaling.py; capture = share of linear scaling
retained under the 20%-of-10-min-volume cap):
- $30k: +$718k Y1 / +$1,078k Y2 (87% / 93% capture)
- $60k: +$1,198k / +$1,936k (73% / 83%)
- $120k: +$1,873k / +$3,328k (57% / 72%)
Sublinear but no hard wall through $120k. Note: Y2 gains 1 negative
month at every scaled budget (0 at $15k) -- size costs smoothness.
R50 simulation (day P&L interpolated across measured tiers, slot
FROZEN at the $120k measurement ceiling -- no extrapolation): the slot
reaches $120k within ~5 weeks, then rides there; 2-year total
+$4,964,801 vs +$992,866 flat-$15k. Practical reading: R50 on C23 =
"grow to max fillable size in ~a month, then earn ~$1.9-3.3M/yr at
that size" -- with growing fill-realism strain: the backtest assumes
clean fills inside the volume cap; at $120k slots that assumption is
doing heavy lifting. Slippage stress at scale untested (next: C24-style
10bps at $120k). Paper sessions enforce R50 + rule 13 naturally.

### C23 dynamic R50 backtest (true per-day compounding, 2026-08-05)

User: slot = $15k + half of cumulative profits, every day simulated AT
its actual slot (plan/c23_r50_dynamic.py; curve in
data/massive/c23_r50_curve.json).
RAW RESULT: +$37,443,510 over 2 years; slot $15k -> $19.4M (>=$120k in
5 weeks, >=$1M by month 3). NOT CREDIBLE AT SIZE:
- negative days 55% (vs ~21% at $15k); max DD -$11.9M; worst day
  -$2.1M -- the zero-negm character is destroyed;
- beyond ~$120k the fill model (trigger-price fills, zero market
  impact, 20% of 10-min volume) becomes fiction -- at $15M slots the
  strategy IS the market in these names.
RECOMMENDATION (pending user sign-off): adopt R50 WITH A SLOT CAP at
the measured-credible tier: slot = min($120k, $15k + 0.5 x cum). At
that cap the defensible 2-year figure is ~+$4.96M (tier-validated),
reached-cap in ~5 weeks, accepting 1 negative month in Y2 and the
$120k-tier fill caveats. Paper R50 runs uncapped for now ($15k base;
months away from the cap) -- decision needed only when cum profits
approach +$210k.
