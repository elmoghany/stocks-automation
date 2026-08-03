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
Script: `penny-stocks.py candletest / gridtest / pairtest` on SCYX/TCX/REPL.

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

## Untested candidates (queue)
- A2 + cap $10 (two changes: top-2 AND $2-10) — best-avg x best-total mix
- surge 3% on the current default (was +$47 at $1k sizing)
- multi-year validation on purchased data (Polygon) — cold-tape regime
