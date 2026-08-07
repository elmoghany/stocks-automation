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

## C30 -- ADOPTED (2026-08-05): C23 strategy under capped half-reinvest sizing

Permanent ID: **C30** = C23 rules unchanged + R50-capped sizing:
  slot = min($120,000, $15,000 + 0.5 x max(0, cumulative P&L))
Base never shrinks; losses only eat the profit buffer; cap sits at the
highest liquidity-measured tier. Backtest (2yr, dynamic-at-tier):
~+$4,964,801 vs +$992,866 flat; cap reached in ~5 weeks; accepts 1
negative month in Y2 at scale; $120k-tier fill realism is THE thing
paper trading must validate (60s-later price recordings). C30 is the
live paper config from 2026-08-06 (slot state:
day-trading/data/paper/slot_state.json). E01 keeps uncapped R50
(large caps; no liquidity issue at these sizes).

## TD-family: halal big-tech 15%-dip buying, multi-day holds (2026-08-05)

bollinger-trading/plan/tech_dip.py -- user directive: buy 15% dips on
top-trend halal big tech, $50k/position, multi-day holds ALLOWED
(explicit same-day waiver for this book). Universe: 111 halal
Tech/Comm-Services names (S&P900 halal x sector map). Trigger: close
>= 15% below trailing 60-session high AND 5y return >= +100%
point-in-time; entry next open; one position per symbol. Entries
Aug 2021-Jun 2026 (includes the 2022 bear).
Results ($50k/position, ALL signals funded):
- TD01 +10% tgt/60s cap: n=207, 87.0% win, +6.58%/tr, 17d holds, +$681k
- TD02 +15% tgt: 80.6%, +8.56%, 24d, +$749k
- TD03 +20% tgt: 78.3%, +11.16%, 29d, +$876k
- TD04 recover-to-high/90s: 78.0%, +12.52%, 36d, +$882k
- TD05 20-session time exit: 65.2%, +7.97%, +$745k
- TD06 60-session time exit: 70.7%, +29.33%/trade, 55d, +$1,803,571 (best)
- TD07 20%-dip entry: 84.8%, +10.31%, +$474k (rarer, cleaner)
- TD08 +15%/-10% stop: 64.1%, +5.67%, +$654k (stop hurts -- dips wobble)
- TD09 +200SMA gate: 81.3%, +8.83%, +$614k (filters little)
- TD10 capitulation-volume gate: 71.9%, +$267k (over-filters)
CONTROL (no-dip monthly 60s holds, same names/window): +10.21%/hold,
61.3% win -> TD06's +29.33% is ~3x beta. REAL ALPHA -- unlike the BL
and pre-earnings families, the 15%-dip signal genuinely times these
names (deep dips on strong big tech mean-revert hard).
CAPITAL REALITY: signals cluster in crashes -- funding ALL signals
needs ~37-42 concurrent slots (~$2M). Constrained greedy sims:
- TD02: 1 slot +$44k / 4 slots +$145k / 8 slots +$255k (per ~5yr)
- TD06: 1 slot +$51k / 4 slots +$207k / 8 slots +$255k
i.e. ~$10-13k/yr per $50k slot at practical scale. Stop-losses hurt
(TD08); no exit variant beats simply holding 60 sessions.
STATUS: shelf/opportunistic -- strongest per-event stats in the
bollinger book; adoption needs a slot-count decision (capital beyond
the day/earnings books) and clustering tolerance (worst trade -46%,
2022-style periods tie up all slots at once).

## BB-family: Bollinger-Band mean-reversion + single-slot R50 (2026-08-05)

bollinger-trading/plan/bollinger_bands.py -- 12 variants on 479 halal
names (Aug 2021-Jun 2026): entry %B <= 0/0.20/0.30, exits %B >=
0.50/0.80/0.90/1.00, MA200/MA50 gates, 5-day volume-pressure reversal
confirm (buy side) and pressure-flip exit accel (sell side). $50k;
user portfolio rule: ONE slot at a time, R50 compounding, deepest %B
wins same-day ties.
- Per-event: all variants +1.3..+2.9%/trade, 64-71% win, ~13-38d
  holds. CONTROL (no-signal monthly 30-session holds): +2.79%/hold,
  55.6% win. Per-DAY efficiency: BB ~0.085%/day vs control 0.093%/day
  -> NO per-event alpha; the higher win% is just shorter holds. Unlike
  TD (3x control), band-touch timing adds nothing on this universe.
- Single-slot R50 outcomes SCATTER WILDLY across adjacent variants:
  BB01 (sell 0.80) +$1,053,172 but BB02 (sell 0.90) +$96,952 and BB03
  (sell 1.00) +$38,930; BB04 +$5k; BB12 (mid-band) -$32k. A result
  that flips 10x on a 0.1 threshold change is sequence luck, not
  edge (deepest-%B picking grabs falling knives: DAVE -88%, CVNA -79%
  events sit in every variant's tail). FAILS the adjacency guardrail.
- MA gates raise win% (BB08 83% slot win) but shrink totals; volume
  confirm (BB09/10) similar. Nothing beats its own neighbors robustly.
VERDICT: REJECT for adoption. Bands describe volatility, they do not
predict reversal here; the TD 15%-dip trigger (3x control) remains the
only validated buy-low signal in this book.

### TD-family under the user's single-slot R50 rule (same date)
One $50k slot, no new buy until exit, half-profit compounding,
~5-year window: TD06 +$59,886 (4 trades, 100% win), TD02 +$52,188
(8 trades, 88%), TD09 +$49,393, TD01 +$44,341 (13 trades, 85%),
others +$14k..+$39k. Reading: the single-slot constraint throttles TD
hard (4-13 trades in 5 years vs 123-231 signals) -- TD's value needs
multiple slots; at one slot it's ~$9-12k/yr, comparable to E01's base
year but far below C30. Slot scaling for TD = the open decision.

## BD-family: band-gated dip entries (2026-08-05)

bollinger-trading/plan/dip_band.py -- %B entry thresholds ON TOP of
the validated -15%-dip trigger, vs the TD06 benchmark (dip only,
60-session hold: +29.33%/trade, n=123).
- BD01 %B<=0.20: +28.95%, n=102 | BD02 %B<=0: +28.70%, n=66 |
  BD03 %B<=0.30: +30.62%, n=108 -- all within ~1pp of TD06 with FEWER
  events. Band geometry adds NOTHING to the dip trigger (noise).
- BD04/05 band exits (%B>=0.80/0.90): +8.5-9.2%/trade -- exits way too
  early; nothing beats the plain 60-session hold (3rd confirmation).
- BD06 + volume confirm: +30.31% but n=24 -- over-filtered.
- BD07 all-halal universe: +16.94% (n=324) -- tech bounces ~2x harder.
- BD08 NO 5y-strong gate: +8.53%, 57.6% win -- THE ISOLATION RESULT:
  the 5-year-strength gate is the alpha (29% vs 8.5%); the edge is
  "quality name knocked down 15%", not "price touched a band".
VERDICT: bands rejected as entry timing too (matches BB-family). The
book's validated recipe stays: halal big tech + 5y-strong + 15% dip +
60-session hold. Nothing else earns its complexity.

## MC-family: $400B+ halal mega caps (2026-08-06)

bollinger-trading/plan/megacap.py + megacap2.py. Universe: 18 halal
names >= $400B (AAPL ABBV AMAT AMZN AVGO COST CSCO GOOG GOOGL INTC
JNJ MA META MSFT NVDA TSLA V WMT; mcaps as-of-today, cached).
ARM A -- earnings variants (last yr, $50k/event): E01 DOES NOT
TRANSFER. MC01 (beat dip<=-3% open->close): +0.46%/ev, 36.4% win,
slot +$592. Any-red/-2% variants similar; gap-up continuation
-1.06%/ev; 5-session drift -1.18%/ev; miss-control n=6 inconclusive.
Mega-cap reactions are efficient -- the E01 edge lives in mid/small
caps. REJECT earnings arm on megas.
ARM B -- dip-from-top (any cause incl. crashes), uptrend 5y>=+50%,
60-session holds, entries Aug21-Jun26 vs CTRL +6.29%/hold (60.6% win):
- Depth sweep: 8% +5.91%/ev (62%) | 10% +6.91% (72.5%) | 12.5%
  +10.14% (74.2%) | 15% +11.80% (75.0%) | 20% +11.42% (n=11).
  Alpha starts at ~12%; below that it's control-level.
- Band sweep (user "12 to 20%... test different numbers"): 12-20%
  band +8.98%/ev n=33; 15-20% +11.79% n=23; upper 25 ~identical
  (few >20% dips in megas). Adjacent bands consistent (no BB-style
  scatter) -- the signal is robust to the exact numbers.
- FLEXIBLE-CAUSE decomposition:
  MC15 market-trigger only (QQQ >=10% off): +18.06%/hold, 78.6% win
  (n=14) -- buying ALL uptrend megas in a correction works with NO
  stock-level signal. QQQ>=8%: +15.0%. QQQ>=12%: never fired.
  MC16 CRASH OVERLAP (stock>=12% AND QQQ>=10%): +23.37%/hold, 87.5%
  win (n=8) -- the best per-event stats in the entire research
  program. Panic dips in quality megas are the premium buy.
  MC17 idiosyncratic (stock>=12%, QQQ near high): +9.96%/ev, 74.2%
  (n=31) -- single-name dips work too, about half as hard.
- Slot R50 (one-at-a-time): $15-47k per ~5yr -- like TD, slot-starved;
  the play is opportunistic deployment when the signal fires, not an
  always-on book.
VERDICT: adopt as the bollinger book's watchlist play alongside TD:
halal mega cap + 5y>=+50% + >=12% off the 60d high -> buy, hold 60
sessions; deploy hardest when the MARKET is also >=10% off its high
(crash overlap: 87.5% win, +23%/hold historically). Small n on the
crash rows (2022 + Apr'25 episodes) -- sizing judgment required.

## SCANNER AUDIT + FIX (2026-08-06, intraday)

User: "did the day trading buy anything? if not, check the code" -->
audit (day-trading/plan/scanner_audit.py) rebuilt the BACKTEST's
full-market discovery (Massive grouped-daily + our 50d rvol >= 5 +
high >= +10%, clean tickers, prev_close >= $2) for the paper days and
diffed it against every symbol the live RH scanner surfaced:
- Aug 4: backtest pool 20; scanner missed 6 OF THE TOP 8, including
  MOVE: +75.6% high, our-rvol 156, $7.4M volume, HALAL (comb 13.1%),
  CALM at 7AM (+6.9%) -- a full C23 qualifier, the backtest's #1 pick
  after halal-blocked AMIX, ~+69% from its 7AM price. A missed monster.
- Aug 5: scanner missed 2 of top 8 (SHPU +49%, BLMN +42%).
- ROOT CAUSE: the scan's RH 30-DAY rvol>5 filter disagrees with our
  50-day source-of-truth in both directions (showed DBGI noise, hid
  MOVE). Secondary: live protocol measured calm-gap at the 9:30 open
  instead of the backtest's 7AM (no missed trades from this in 3 days
  -- all rejects were pre-7AM-exhausted -- but corrected).
FIXES (all live as of 10:30 ET):
1. Scan 5f132877 filters reduced to Last>$2 + %change>+10% ONLY (139
   rows vs 7): the scanner is a FEED; every gate (our-50d rvol, 7AM
   calm-gap, halal, +10% at entry) is computed locally.
2. NO-SILENT-FALLBACKS policy (user directive): any stale/errored
   source or unmet intent => loud "ERROR:" line in the day log +
   day-JSON note; silent workarounds forbidden. Stale E*TRADE quote
   path: RH-bars recompute is now the authoritative rvol method.
3. Calm-gap measured at 7:00 AM ET everywhere (skill updated earlier).
Verdict on "is something wrong": the STRATEGY was fine; the FEED was
blind. 3-day no-trade streak was part tape (5 haram, 8 exhausted),
part scanner blindness (MOVE should have been traded Aug 4).

## Regression check after the 2026-08-06 fixes: FULL PASS

Fresh replays after the scanner fix, 7AM calm-gap alignment, bar-
granularity policy, and all default flips (C21->C11->C23):
- C23: Y1 +$412,879 (133d, 1,262 trades), Y2 +$579,988 (147d, 1,902
  trades) -- EXACT to the dollar vs the registered champion numbers.
- E01: +$117,755 (n=99) -- exact; ET12/13/31 rows identical.
The live-protocol bugs never touched the backtest path; code churn
introduced no drift. Paper Day 3 confirmed running the fixed protocol
(feed-only scan, local gates, 7AM calm-gap, loud-error policy) with
prior rejects re-evaluated under the corrected rule.

## C30 replay of the 3 paper days (2026-08-06, user: "backtest the 3 days")

day-trading/plan/replay_paper_days.py -- rebuilds the backtest's own
candidate pool from Massive grouped-daily and runs the UNMODIFIED
sim_window (C23 spec, $15k) over the live paper dates.

- 2026-08-04: pool 20. AMIX rejected halal (as live). MOVE COMMITTED
  (gain +75.6%, rvol 156, 7AM gap only +6.9%) -> 11 trades, day P&L
  **-$2,252.13**. The trade the scanner hid was a LOSER: first entry
  8:09 @ 18.30 banked +$2,903 on the morning pop, then MOVE faded all
  session and the re-entry ladder gave it all back (six stops).
  => The scanner bug SAVED $2,252 that day. It was still a real bug
  (blind is blind), but the "missed monster" narrative is wrong.
- 2026-08-05: pool 21, walk-8 all rejected -- 4 calm-gap (INLF +24.0%,
  JLHL +36.7%, GTE +46.9%, OESX +34.6% at 7AM), 4 halal (JDZG, SHPU,
  DBGI, BLMN) -> NO-TRADE DAY. **Exactly matches the live session**,
  including the two names the live scanner never showed (SHPU, BLMN
  would have died on halal anyway). Strong protocol validation.
- 2026-08-06: Massive grouped-daily 403 on same-day data (free-tier
  delay) -- ERROR logged, replay pending tomorrow.
2-day verified total: -$2,252.13 vs live paper $0. Live is AHEAD by
$2,252 -- by luck, not by rule. The honest read: 2 of 2 auditable
days reproduce the live decisions once the feed is corrected, and the
one divergence was a losing trade.

## C30 statistical deep-dive (2026-08-07) -- day-trading/plan/c30_stats.py

302 traded days, 3,164 positions, +$992,866 on a $15k slot.
DISTRIBUTION: mean $3,288/day, median $1,910, sd $5,744, skew +2.59,
kurtosis 17.8 (violently fat-tailed). p25 = $0 -- a quarter of traded
days make nothing. Top 10% of days = 47.8% of profit (matches the
earlier anatomy).
KELLY: day win rate 0.699, payoff 2.72 -> full Kelly 58.8% of
bankroll, half-Kelly 29.4%. At $15k risked per day that implies a
~$51k bankroll at half-Kelly -- i.e. the current slot is correctly
sized for a ~$50k account, and R50 growth to $120k implies a ~$400k
bankroll to stay at half-Kelly. Daily return on slot +21.9% (sd 38.3%)
-> annualized Sharpe 9.09. FLAG: a Sharpe of 9 is not a real-world
number (Medallion is ~2.5-3). It is what a capacity-limited niche
looks like in-sample, and it is the strongest argument that live fills
will be worse than the sim.
INDEPENDENCE: lag-1 autocorrelation +0.025 (lags 2/3/5 all < 0.13).
Day after a LOSS averages +$3,343 vs +$3,221 after a win; day after a
monster +$3,915. => Days are effectively INDEPENDENT. No basis for
tilting size after wins/losses; no hot hand, no hangover. (Confirms
the earlier monster-hangover null with a cleaner statistic.)
CALENDAR: Wed weakest (mean $2,418, 63% win) vs Mon $3,945 / Fri
$3,901; months range $1,344 (Mar) to $6,909 (Aug). n=55-70 per
weekday -- treat as noise unless it survives a control.
ENTRY HOUR: 9AM is the engine ($306k, mean $533, 66% win). NOON
ENTRIES ARE NEARLY WORTHLESS: 577 positions (18% of all) produce
$30,975 (3.1% of profit), mean $54/position -- roughly slippage-sized.
But positions EXITING after noon carry $191,196: the 1PM window earns
its keep on EXITS, not on new entries.
TRIGGERS: ORB = 1,442 positions and $736,241 (74% of all profit),
mean $511. PMH-break has the best mean ($550, 67% win) on only 99
shots. Bottom of the table: dragonfly_doji LOSES (-$1,186, n=60) and
inverted_hammer is below transaction cost (+$17/position, n=183);
rsi_cross_up n=32 is noise.
EXITS: bearish-pattern exits +$1,618,921 (n=1,450) and scale-outs
+$234,364 are the profit engine; STOPS are the entire loss column
(-$897,536 over 1,301 positions, mean -$690); noon/1PM flatten is
small (+$37,117, 44% win).
RE-ENTRY LADDER: positions #0-#3 = $697k of the $993k. #7 and #8 are
net negative (-$13.8k, -$11.5k) but #9+ is +$151,705 across 1,031
positions -- the deep tail is where monster days live, so capping
re-entries would cut the fat tail. Do NOT cap.
TRAIL EFFICIENCY (the biggest finding): median position peaks +7.80%
and we keep +1.96% -- a median capture ratio of 0.29. By peak size:
0-5% peaks capture NEGATIVE (median kept -7.9%); 5-15% keep 0.30;
15-40% keep 0.62; 40%+ keep 0.60. We give back ~40% of every big move
and small-peak positions systematically turn into losers.
ENTRY PRESSURE: corr(p_entry, pnl) = +0.086 overall, but the top
bucket is dramatic -- p_entry >= +0.30 averages $751/position (65%
win) vs $213-263 for every other bucket, on n=475. Prior work rejected
pressure as an entry GATE (it destroys ORB timing); it has never been
tested as a SIZING input.
DAY FEATURES: corr(P&L, #positions) = +0.305 (monster days are long
ladders); corr(P&L, hour of first entry) = -0.115 (earlier start =
better day).
DATA GAP (no silent fallback): the c23 trade dump omits g7 and rank,
so gap-band and pool-rank correlations could not be computed here --
re-dump with those fields before relying on sections 10/11.

### Ranked improvement hypotheses from the above (untested)
1. PRESSURE-SCALED SIZING (not gating): size up when p_entry >= +0.30,
   down otherwise. Strongest signal in the data (3x mean P&L).
2. BREAKEVEN / EARLY-EXIT for small-peak positions: 0-5% peaks have a
   negative capture ratio; a breakeven stop after +2-3% may convert a
   chunk of the -$897k stop column. (breakeven_at kwarg already exists.)
3. PATTERN PRUNING: drop dragonfly_doji (negative) and inverted_hammer
   (below cost). Expected small but free.
4. ENTRY CUTOFF at 11:30-12:00: noon entries are slippage-sized;
   under the 10bps stress they likely go negative. Keep 1PM EXITS.

## S-CAMPAIGN WAVE 1 (S000-S046, 2026-08-07): both families REJECTED

Anchor S000 reproduced C23 exactly (+$412,879 / +$579,988).

### A. Pressure-scaled sizing -- REJECTED as LEVERAGE, not signal
The headline looked strong: sizing 1.5x when p_entry >= 0.30 gave
+$16.9k / +$47.2k (dComb +$64.1k), and the whole threshold sweep
(0.20/0.30/0.40/0.50) agreed -- textbook adjacency, clean negm.
But the INVERTED control (S018: 0.5x on high pressure, 1.5x on LOW)
also gained (+$66.5k). Both directions winning = the effect is not
pressure. The decisive capital-neutrality controls settled it:
  S002 pressure-directed, avg capital 1.075x -> dComb +$64.1k
  S041 FLAT budget $16,126  (same 1.075x)    -> dComb +$60.1k
  S018 inverted, avg capital 1.162x          -> dComb +$66.5k
  S042 FLAT budget $17,425  (same 1.162x)    -> dComb +$133.4k
Flat capital MATCHES the pressure version at 1.075x (+4k = 6%, noise)
and DOUBLES the inverted one at 1.162x. Every "gain" in Family A is
the known capital-scaling curve (7.5% more capital -> +6.1% profit;
16.2% -> +13.4%, both slightly sublinear, consistent with the earlier
budget-scaling study). Pressure direction contributes nothing.
Supporting evidence: downsizing alone always loses (S009-S012, -$24k
to -$86k) and capital-neutral both-direction variants are flat to
negative (S013-S015). Shuffled control S017 failed correctly
(-$57k/-$172k) but was NOT sufficient -- only the inverted + flat-
budget controls exposed this. LESSON: any sizing experiment must be
compared against an equal-average-capital flat baseline, or leverage
masquerades as alpha. Adding that rule to the guardrails.

### B. Trail capture -- the leak is NOT patchable
- Breakeven stops (S019-S027, +2% to +8%): CATASTROPHIC and perfectly
  monotonic. +2% keeps 23% of baseline ($132,618 / $95,118 vs
  $412,879 / $579,988); +8% still far below (-$88k/-$217k).
- Time stops (S033-S036, 10/15/20/30 min): all worse, monotonic in the
  same direction.
=> The 0.29 capture ratio and the negative small-peak positions CANNOT
be fixed by exiting earlier: the same rule that rescues a small loser
ejects us from the monsters carrying 47% of profit. The give-back is
the PREMIUM PAID for the fat tail, not a bug. This closes the biggest
"improvement" lead from the statistical study.
- Tiered trail (S028-S032): Y2 +$32k..+$55k but Y1 -$4k..-$15k on all
  five variants -- consistent but year-split, fails the both-year rule.
- Scale-out timing (S037-S040, S043-S045): later banking trends better
  and peaks around +30-50%: +30% dComb +$11.1k, +35% +$19.5k, +45%
  +$23.3k, +50% +$30.5k -- the only survivors, all both-year positive
  with clean negm, but hovering at/below the +$30k floor. Marginal;
  candidate for the final stack test, not a standalone adoption.

NET: Wave 1 produced no adopted change. That is a success, not a
failure -- two evidence-backed leads that looked strong in-sample were
killed by controls before they reached live capital.

## S-CAMPAIGN WAVE 2 (S048-S071, 2026-08-07)

### C. Pattern pruning -- REJECTED (per-pattern P&L is statistical noise)
Nothing passed both years: drop dragonfly_doji +$5.7k/-$4.8k; drop
inverted_hammer -$6.8k/+$13.5k; drop both -$3.6k/+$7.6k; drop bottom-3
-$8.7k/+$3.1k; top-3/5/7 keeps all mixed-to-worse.
WHY -- t-tests on the per-position means that motivated this family:
  dragonfly_doji  n=60  mean -$20  se $192  t=-0.10
  inverted_hammer n=183 mean +$17  se  $74  t=+0.22
  rsi_cross_up    n=32  mean +$51  se $155  t=+0.33
Those "losing patterns" are indistinguishable from zero. Only ORB
(t=8.80), PMH-break (t=3.56) and bullish_engulfing (t=2.81) are
statistically real. The CONTROL nailed it: keeping ONLY the 3 worst
patterns (S057) scored +$413,412 in Y1 -- BEATING the top-3 keep
(S054, +$410,871). A ranking whose bottom beats its top is noise.
LESSON: never prune on unsigned per-bucket means; require |t| >= 2.
Also learned: patterns as a CLASS do earn their keep -- ORB/PMH only
(S052) loses $128k over two years and trades fewer days.

### D. Entry cutoffs -- REJECTED (monotonic, and it costs whole days)
11:00 -$84k/-$134k, 11:15, 11:30, 11:45 all worse, 12:00 still
+$1.5k/-$32.5k. The c30_stats finding (noon entries = 18% of positions
for 3.1% of profit) was TRUE but not ACTIONABLE: those positions are
still net positive, and cutting them removes whole trading days
(133->117 days at an 11:00 cutoff) because some days' only qualifying
entry arrives late. Same lesson as Wave 1: a low per-position mean
does not make a bucket removable.
Pattern-only cutoffs (S064-S067) were flat; 11:00 was the best at
+$14.1k/+$0.4k -- below the floor.

### D2. EXIT WINDOW -- FIRST GENUINE PASS OF THE S-CAMPAIGN
Extending only the EXIT edge (entries unchanged, still ending at noon)
is monotonically better out to 15:00:
  12:30  -$8.9k / -$16.4k     (worse)
  13:00  BASELINE C23          +$412,879 / +$579,988
  13:30  +$27.8k / +$9.7k   dComb +$37.5k  negm 0/12, 0/10   PASS
  14:00  +$38.5k / +$17.0k  dComb +$55.5k  negm 0/12, 1/10   fails negm
  15:00  +$93.1k / +$75.7k  dComb +$168.8k negm 0/12, 0/10   PASS (!)
S071 (15:00) is the strongest single result in the campaign: +17% on
the two-year total with ZERO negative months in either year, and days
traded rise 133->138 / 147->155 (late exits let more days qualify).
Adjacency is clean and monotone with a single dip at 12:30.
STATUS: NOT ADOPTED -- this is a TRADING-WINDOW CHANGE and the window
is the user's decision, not the optimizer's. History: the user
withdrew a 1PM extension once ("keep noon"), then re-adopted it
("make c11 the default"). Extending to 13:30/15:00 requires the same
explicit sign-off. Flagged for the user with the numbers above.
CAVEAT to weigh: a later flatten means positions are held into the
afternoon, which is a different liquidity/attention regime than the
morning the strategy was designed around, and the 15:00 variant holds
through the lunchtime lull. The backtest says it works; it has never
been paper-traded.

## S071 STANDALONE + C30 SIZING + pattern pruning under 15:00 (2026-08-07)

### S071 alone (C23 rules, exits to 15:00, entries still end at noon)
  Y1 +$505,982 (138d, $3,667/d, 0/12 negm)
  Y2 +$655,731 (155d, $4,231/d, 0/10 negm)
  2yr +$1,161,713 vs C23 +$992,866 = +$168,847 (+17.0%)
Daily return on the $15k slot rises 23.6%->24.4% (Y1) and
26.8%->28.2% (Y2). Days traded rise 133->138 and 147->155 because a
later flatten lets marginal days qualify.

### S071 under C30 sizing (the regime the live book actually uses)
  $60k slot:  Y1 +$1,460,034 / Y2 +$2,180,847  (vs 1PM $1,198,007 /
              $1,935,844) = +$507,030 over two years, +16.2%
  $120k cap:  Y1 +$2,318,597 / Y2 +$3,722,529  (vs 1PM $1,873,247 /
              $3,328,199) = +$839,680 over two years, +16.1%
KEY: the +17% edge is SIZE-STABLE -- ~+16% at both the mid tier and the
$120k liquidity cap, so the exit-window gain is NOT eaten by the
20%-of-volume constraint. The 1/10 negative month that appears at $60k
and $120k is a SIZE artifact, not a window artifact: the earlier 1PM
budget-scaling run showed the same 1/10 at those tiers.

### Pattern pruning under the 15:00 window -- REJECTED AGAIN
Re-measured on the S071 dump (4,102 positions) the two suspects ARE
negative here: dragonfly_doji -$5,074 (mean -$53, t=-0.41),
inverted_hammer -$6,152 (mean -$24, t=-0.41). Removing them anyway:
  S072 drop dragonfly_doji : +$9.3k / -$3.8k   mixed -> FAIL
  S073 drop inverted_hammer: -$7.0k / +$13.3k  mixed -> FAIL
  S074 drop BOTH           : -$0.7k / +$7.9k   mixed -> FAIL (dComb +$7.2k)
  S075 drop both + rsi     : -$7.3k / +$5.4k   mixed -> FAIL
  S076 CONTROL drop two GOOD patterns: +$7.2k Y1 -- i.e. dropping GOOD
       patterns helps Y1 as much as dropping bad ones. Noise confirmed.
WHY bucket attribution keeps failing here: the system is SEQUENTIAL,
not additive. Removing a losing entry does not just add its loss back
-- it changes every subsequent entry that day (the re-entry ladder
shifts), so a -$11,226 measured bucket is not $11,226 of recoverable
profit. Combined with |t| = 0.41, there is nothing to harvest.
CONCLUSION: keep all patterns. Prune only on |t| >= 2 AND a passing
both-year test -- neither condition is met by any pattern.

## Capital reality check + $100k flat results (2026-08-07)

USER: "i have 100k in my account... we can not trade more than 6.5 the
amount of 15k at a specific day."
VERIFIED IN THE DATA: max CONCURRENT positions across all 302 backtest
days = 2. The ~10.5 positions/day are SEQUENTIAL (buy, exit ~10 min
later, re-enter the same name with the same cash). So the slot is PEAK
EXPOSURE, not a per-day sum -- a $100k account is not limited to "6.5
slots"; it can run ONE slot up to ~$100k. The binding constraint is
liquidity (20%-of-10-min-volume), which we measured saturating near
$120k, not the account.
PRACTICAL REQUIREMENT (flagged to user): ~10 round-trips/day on the
same cash needs a MARGIN account -- in a cash account, T+1 settlement
makes the re-entry ladder impossible. At $100k the PDT minimum ($25k)
is satisfied, so unlimited day trades are permitted.

FLAT (no compounding) reference table, 2-year totals:
  slot    1PM exit (C23)     15:00 exit (S071)
  $15k    $  992,866         $1,161,713   (+17.0%)
  $60k    $3,133,851         $3,640,881   (+16.2%)
  $100k   $4,583,305         $5,339,841   (+16.5%)
  $120k   $5,201,446         $6,041,126   (+16.1%)
$100k detail -- C23: Y1 +$1,672,966 (133d) / Y2 +$2,910,339 (150d);
S071: Y1 +$2,064,938 (138d) / Y2 +$3,274,903 (158d). Negative months
1/10 in Y2 at $100k for BOTH configs -- a size artifact (present in
the 1PM budget-scaling run too), not caused by the later exit.
The exit-window gain is stable at ~+16-17% across every slot size.

## EXACT cash-account model + the 4 requested re-backtests (2026-08-07)

New kwarg `daily_deploy_cap` (day-trading.py): tracks actual cost basis
deployed per DAY and sizes the final ticket with whatever remains, then
blocks further entries until the next session -- the true T+1 cash-
account rule the user described ("100k is the max amount available to
trade... ok if we use 10k for the last trade"). So 6 x $15k + 1 x $10k
= $100k exactly. MIN_TICKET $1,000 prevents unrealistically tiny final
orders. Identity re-verified after the change: C23 unset reproduces
+$412,879 / +$579,988 with 1,262 / 1,902 trades.

RESULTS ($15k slot, FLAT, no compounding, 2-year totals):
  config                                        Y1        Y2       2yr
  C23 1PM  uncapped (margin)               412,879   579,988   992,866
  S091 C23 1PM  + $100k/day cap            382,792   489,421   872,213
  S094 C23 1PM  + cap + drop 2 patterns    383,303   505,385   888,688
  S071 15:00 uncapped (margin)             505,982   655,731 1,161,713
  S092 S071 15:00 + $100k/day cap          449,078   556,094 1,005,172
  S093 S071 15:00 + cap + drop 2 patterns  446,298   573,668 1,019,966
All six have ZERO negative months in both years.

READINGS
1. The cash cap costs 12.1% (C23: 992,866 -> 872,213) and 13.5%
   (S071: 1,161,713 -> 1,005,172). Margin would be worth ~$133-157k
   over two years; that is the price tag on T+1, not a recommendation.
2. The 15:00 exit still wins UNDER the cap: +$132,959 over C23-capped
   (872,213 -> 1,005,172, +15.2%). The later exit matters MORE when
   shots per day are rationed -- each of the ~6.5 tickets runs longer.
3. Pattern removal under the cap: C23 +$16,475 (Y1 +511, Y2 +15,964);
   S071 +$14,794 (Y1 -2,780, Y2 +17,574). BOTH still fail the both-year
   rule on one leg and sit far below the $30k floor -- consistent with
   the |t| = 0.41 measurement. Third independent rejection. KEEP ALL
   PATTERNS.
4. C30 is not a separate row: C30 = C23 + capped R50 sizing, and a hard
   $100k/day cash ceiling truncates exactly the slot growth R50 exists
   to produce, so under this constraint C30 collapses onto C23.
BEST CONFIGURATION FOR THE USER'S ACTUAL ACCOUNT:
  S092 = C23 rules + 15:00 exit + $100k/day cash cap
  = +$1,005,172 over two years ($449,078 / $556,094), 0/22 negative
  months, ~$3,254-3,588 per traded day on a $15k ticket.
STILL REQUIRES: user sign-off on the 15:00 window (a trading-window
change is the user's call), and it has never been paper-traded.

## C34 per-position-number analysis (2026-08-07) -- which Nth trade earns

Measured on the adopted config (S093 dump: 304 days, 2,180 positions,
+$1,019,966).
  trade#   n     total      mean   win%   cumulative share
    1    293  +201,974     +689    71%    20%
    2    290  +295,778   +1,020    76%    49%   <- BEST single slot
    3    286  +165,964     +580    65%    65%
    4    279  +116,239     +417    61%    76%
    5    269   +52,882     +197    57%    82%
    6    258   +62,681     +243    57%    88%
    7    244   +92,220     +378    62%    97%
    8    144    +9,564      +66    60%    98%
    9     67      -432       -6    46%    98%
   10+    50   +23,097            (n too small to read)

FINDINGS
1. The SECOND trade of the day is the best slot in the strategy --
   highest mean ($1,020 vs $689 for the first) AND highest win rate
   (76% vs 71%). Plausible mechanism: entry #1 is the probe that often
   gets stopped establishing the move; entry #2 buys the confirmed
   continuation. Worth a dedicated experiment (size the 2nd ticket up)
   -- but see the Wave 1 lesson: any such test needs an equal-capital
   flat control before it can be believed.
2. Trades 1-4 = 76% of profit; trades 1-7 = 97%. Trade 8 adds 1%,
   trade 9 is net NEGATIVE (-$432, 46% win).
3. THE CASH CAP IS ALMOST FREE. It binds on 80% of days and roughly
   halves position count (4,102 uncapped -> 2,180, 13.5/day -> 7.2/day)
   yet costs only ~12% of profit, because it truncates exactly the
   low-value tail (trades 8+ = 3% of profit). Under a $100k/day ceiling
   the strategy loses its worst trades first.
   => Margin would buy back the 4,102-2,180 = 1,922 discarded positions
   for ~$142k over two years, i.e. ~$74/position -- far below the
   average of the trades you already get. Low priority.
4. Corollary for live trading: if a day is going badly, the value is
   already banked by trade ~7; there is no need to force late entries
   to "make it back" -- trade 9 has a negative expectation.
