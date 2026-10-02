# SWING-REVERSION: multi-day long-only swing families on a liquid US universe (2026-10-01)

**Question.** Now that multi-day holds are allowed (long-only, cash account, no shorting, options or margin), does any of the well-known swing families give a positive net result when tested honestly? The three families tested were Connors-style short-term mean reversion, 1-week reversal, and momentum/breakout continuation (included as a contrast).

**Short answer.** No family gives a stable edge over simply holding SPY.
- **Connors-style mean reversion and momentum/breakout fail** on the honest 2024-10 → 2026-09 tape.
- **The 1-week loser reversal looks excellent on the recent tape:** +$5.7k/month on $100k for the best grid cell (N5, 3-day hold), with positive alpha in Y1, Y2 and OOS. That result does not survive the 20-year check. On the S&P 500 from 2005 to 2024, its beta-adjusted alpha was **negative in 2010-14 and 2015-19 and about zero in 2020-24**, and its Sharpe ratio was below SPY's in 3 of 4 periods. This is despite a survivorship bias in the long data that flatters this strategy.
- **What the recent result really is:** a portfolio with a beta of about 2 to high-volatility names, during a 2-year speculative rebound regime.
- **Verdict:** not worth funding. It is worth at most a zero-cost shadow paper book, labelled as a regime bet (see the verdict at the end).

## Data and honesty rules

| item | how |
|---|---|
| Main tape | `data/massive/gd`: Polygon grouped daily, 2024-08-05 → 2026-09-30, 541 sessions. Membership is point-in-time and includes delisted names; 6,402 tickers were ever liquid. The API only serves history from 2024-10-01 (rolling 2 years; earlier dates return 403), so the existing cache was used. A fresh re-fetch was abandoned after 429 contention with the live paper book. |
| Splits | The cache was fetched with adjusted=true in blocks (bulk on 2026-08-03, then daily appends and re-fetches), so some splits appear unadjusted. For every Polygon split (`/v3/reference/splits`), the overnight jump that best matches the split ratio within E-40..E+3 sessions was found. If it matched within 0.10 log, the earlier history was rescaled; 65 fixes were made. Belt and braces: no signals within [E-5, E+25] sessions of any split. Residual >+150%/<-65% gaps inside the universe: 9 ticker-days. |
| Universe (U) | Common stock or ADR (Polygon reference, active plus inactive), 20-day median $ volume ≥ $25M, close ≥ $10, ≥ 55 of the last 60 sessions traded. Everything is computed with data ≤ the signal close. Median size is 1,603 names. "large" = top 500 by 20-day median $ volume. |
| Timing | The signal uses the close of day s. **Entry is at the OPEN of s+1.** Exit conditions are evaluated on a close and filled at the next open. A time stop H means H closes held, then a sell at the next open. Delisted names are closed at their last close. Ties are broken by seeded random jitter. A "close" mode (enter and exit at the close, as in Connors MOC) is reported only as an optimistic sensitivity. The gd open matches the 09:30 minute open (0.0000% median, per the open-universe audit). |
| Portfolio | $100k, max N concurrent positions (N=5 at $20k each, N=10 at $10k each), fixed dollars (no compounding), no re-entry while held. T+1 settlement never binds because every hold is ≥ 1 night. |
| Costs | 6 bps/side (pessimism-audit, liquid central), with a 12 bps/side stress row. |
| Splits of the sample | Y1 2024-10 → 2025-07 (10 months), Y2 2025-08 → 2026-07 (12 months), OOS 2026-08 → 2026-09 (2 months). |
| Controls | (a) 30 seeds of the same trades (same dates, holds and sizes) with the ticker swapped for a random member of the same universe on the signal day. (b) SPY buy-and-hold with $100k. (c) For the reversal: a vol-matched random control (same 20-day volatility quintile) and beta/alpha versus SPY on the daily mark-to-market curve. |
| Long check | 2005-01 → 2024-09, yfinance auto-adjusted daily bars for every ticker that was ever an S&P 500 member in the window. Membership is point-in-time (fja05680/sp500 start/end intervals). **626 of 939 tickers were found; 314 delisted or acquired names are missing, which is survivorship bias in favour of buying losers.** The universe is members with close ≥ $5 on the signal day; "large" equals the whole member set. |
| Halal | Selection ignores halal. The "HALAL-present-day" rows restrict both the strategy and its control to today's `halal_list.json` (472 names). **This is a hindsight list.** Its own random control earns +$1.5k to +$4.9k/month on the 2024-26 tape, so do not read those rows as an edge. |

Code: `plan/sr_fetch.py` (splits and ticker reference), `plan/sr_panel.py` (panel and split fixes), `plan/sr_long_fetch.py`, `plan/sr_lib.py` (features, engine, controls), `plan/sr_run.py` (main grid, `gd` or `long`), `plan/sr_robust.py` (reversal neighbourhood and random ordering), `plan/sr_volmatch.py`, `plan/sr_final.py`, `plan/sr_beta.py`. Caches and logs are in `data/research_oct/sr_*` and `data/research_oct/long/`.

## Benchmark

SPY buy-and-hold with $100k:

| period | $/month | max drawdown |
|---|---|---|
| Y1 | +$1,016 | −$20k |
| Y2 | +$1,515 | −$10k |
| OOS | +$1,044 | −$3k |
| L05-09 | +$33 | |
| L10-14 | +$1,736 | |
| L15-19 | +$1,213 | |
| L20-24 | +$1,608 | |

Any long-only, fully invested book has to beat this. The OOS period (Aug-Sep 2026) was poor for the equal-weight liquid universe: −5.1% in September against −0.6% for SPY. That is why most random controls are deeply negative in OOS.

## Family 1: short-term mean reversion (Connors-style). FAIL on the honest tape; decayed in the long check

Headline rows, open entry, 6 bps/side; 12 bps/side in brackets.

| rule | Y1 $/mo | Y2 $/mo | OOS $/mo | $/trade (Y2) | trades/mo (Y2) | win | max DD | ctl pct (all) |
|---|---|---|---|---|---|---|---|---|
| RSI2<5, close>MA200, exit close>MA5, H10, N10 | +535 (+380)* | −51 (−646) | −4,102 (−4,670) | −1 | 50 | 0.61 | −25k | p17 |
| RSI2<5, close>MA100, same exits, N5 | +753 (+320) | +776 (+169) | −2,326 (−2,865) | +31 | 25 | 0.63 | −39k | p57 |
| RSI2<10, close>MA100, exit RSI2>70, H5, N5 | +29 (−420) | +1,682 (+1,053) | −2,832 (−3,430) | +64 | 26 | 0.58 | −33k | p67 |
| down 3+ days, close>MA100, N10 | −1,615 | +109 | −3,335 | +2 | 49 | 0.58 | −34k | p3 |
| close<lower BB(20,2), close>MA100, N10 | −951 | +1,926 | −5,172 | +42 | 46 | 0.60 | −35k | p57 |
| 10-day low, close>MA100, N5 | +508 | +806 | −2,326 | +32 | 25 | 0.63 | −32k | p43 |

\* The MA200 filter needs 200 sessions, so in Y1 it only trades from late May 2025.

- **Recent tape:** every variant is roughly break-even to negative. None beats SPY in any split, the random-control percentiles sit at 3-73, and every ex-top-5 result is negative. The MOC "close" variant is not systematically better (it ranges from −$500 to +$600/month around the open version).
- **Long check, 2005-2024, survivorship-flattered:**
  - The classic RSI2<5 above MA200 with N10 makes +$886 / +$934 / +$64 / +$1,008 per month across the four periods. Its control percentiles are 100/83/40/(high), and its beta is about 0.3-0.6.
  - Alpha versus SPY was +$814 / +$187 / **−$535** / +$420 per month.
  - Every MR variant was flat to negative in 2015-19. In $ terms it never beat SPY buy-and-hold outside 2005-09.
  - The well-known effect is weak, decayed, and below a passive index for a fully invested $100k book.

## Family 2: 1-week reversal (5-day losers among the largest/most liquid). Strong on 2024-26, regime-dependent over 20 years

The standard weekly rebalance (buy the N worst 5-day losers in the top 500 at Monday's open, hold 5 days) gives:
- N10: −1,049 / +523 / +5,499 $/month, ALL +283, ctl pct 73.
- N5: −1,849 / +1,163 / +4,939 $/month.

These are noisy and Y1-negative.

The daily version (fill any free slot every morning with the most negative 5-day return in the top-K) is stronger. Here, open entry is at 6 bps/side (12 bps/side in brackets) and the universe random control is 30 seeds.

| rule (top-K, hold H, N slots) | Y1 $/mo | Y2 $/mo | OOS $/mo | trades/mo | $/trade (Y2) | win | max DD (Y1/Y2) | ex-top-5 ALL $/mo | ctl pct ALL |
|---|---|---|---|---|---|---|---|---|---|
| top500 H3 N5 | +2,794 (+2,012) | +6,974 (+6,139) | +12,615 (+11,767) | 35 | +202 | 0.53 | −33k / −37k | +3,725 | p100 |
| top500 H3 N10 | +1,592 (+810) | +3,504 (+2,672) | +11,104 (+10,257) | 69 | +51 | 0.50 | −38k / −31k | +2,311 | p100 |
| top500 H5 N5 | +2,185 (+1,716) | +1,897 (+1,395) | +4,515 (+3,972) | 21 | +91 | 0.51 | −38k / −46k | +635 | p97 |
| top500 H5 N10 | +4,757 (+4,286) | **−1,194** (−1,695) | +852 (+317) | 42 | −29 | 0.47 | −38k / −43k | +503 | p100 |
| top300 H3 N5 | +2,395 | +4,561 | +13,740 | 35 | +132 | 0.49 | −36k / −39k | +2,364 | p100 |
| top300 H5 N10 | +5,123 | +114 | +9,706 | 42 | +3 | 0.46 | −38k / −41k | +1,923 | p100 |

**Neighbourhood check** (`sr_robust.py`: K ∈ {300, 500, 1000}, H ∈ {3, 5, 10}, N ∈ {5, 10}; the loser threshold doesn't matter because slots are always full):
- **Overall:** 33 of 54 cells are positive in every split, and 23 of 54 beat SPY over each trade's own window (gross) in every split.
- **Top 1000:** collapses (+$470/month on average), so the effect lives in the very largest and most liquid names.
- **Hold length:** H3 > H5 ≈ H10.
- **Random ordering:** picking randomly among the qualifiers instead of ranking by the 5-day return averages +3.5k / +1.3k / +3.3k per month for N10. The edge is the loser set, not the exact rank.

### Adversarial audit of the best cell (top500, H3, N5)

1. **Is it just high-volatility exposure?** Partly. A vol-matched random control (same 20-day volatility quintile, same dates) earns +$725 / +$1,668 / +$6,043 per month on its own. The rule still beats it at the 80th / 100th / 90th percentile (ALL p100). For H5 N10 the same test gives only p50 overall.
2. **Beta.** On the daily mark-to-market curve, beta to SPY is **1.7 / 2.3 / 1.7**. Alpha is +$845 / +$4,019 / +$8,194 per month, positive in all three splits. Sharpe is 0.61 / 1.57 / 3.37, against SPY's 0.72 / 1.37 / 1.25.
3. **Tails and path.**
   - Monthly P&L swings by ±$15k-31k on a $100k book; 67% of months are positive.
   - Max drawdown is −$33k to −$37k, against −$20k for SPY.
   - Ex-top-5 is negative in Y1 (−$825/month).
   - Winners are the speculative high-beta complex: SMCI, MP, AXTI, AAOI, MARA, IONQ, QBTS.
   - Leaving out the April-2025 crash window keeps most of it (+$5.6k/month), so the result is not one event.
4. **The decisive test: 20 years of S&P 500.** Even though the survivorship bias works in this rule's favour, the same rule loses its alpha:

   | period | $/month | gross excess vs SPY per trade window, $/month | beta | alpha $/month | Sharpe (SPY) |
   |---|---|---|---|---|---|
   | 2005-09 | +1,067 | +1,661 | 1.60 | +571 | 0.22 (0.14) |
   | 2010-14 | +409 | +3 | 1.32 | **−1,266** | 0.20 (0.98) |
   | 2015-19 | +691 | +536 | 1.17 | **−461** | 0.32 (0.88) |
   | 2020-24 | +1,949 | +1,503 | 1.38 | +125 | 0.53 (0.75) |

   The other loser cells (H5/H10, N5/N10) look the same: positive $, but negative alpha in 2010-19, with drawdowns of −$90k to −$150k on $100k in 2008 and 2020. Short-term reversal pays in high-volatility, rebounding regimes (2008-09, 2020, 2024-26) and is a worse-than-index, higher-risk book otherwise.
5. **Costs and execution are not the problem.** 12 bps/side costs about $830/month at 35 trades/month. Market-on-open orders in top-500 names fill at the auction, so the 6 bps central estimate is reasonable.
6. **What remains unproven:** whether the 2024-26 alpha persists. OOS is only 2 months (+$12.6k/month, n = 70 trades), driven by a semiconductor/speculative rebound in September while the equal-weight universe fell 5%.

## Family 3: momentum / breakout continuation (the contrast). FAIL

| rule | Y1 $/mo | Y2 $/mo | OOS $/mo | ALL / ex-5 | ctl pct |
|---|---|---|---|---|---|
| new 52-week high (close ≥ prior 252-day high) on volume ≥ 1.5×, H10, N10 | n/a (warm-up) | +2,281 | −4,529 | +763 / −56 | p67 |
| 120-day high on volume, H10, N5 | +876 | +2,265 | −1,542 | +1,369 / −351 | p87 |
| gap ≥ 4% and hold (close ≥ open) on volume ≥ 2×, buy the next open, H3, N5 | −3,483 | −3,543 | +4,838 | −2,820 / −4,848 | p0 |
| same, H10, N10 | −984 | −1,809 | +2,551 | −1,102 / −2,418 | p10 |

Long check: the 52-week-high rule makes +$148 to +$547/month at ctl p13-87, and gap-and-hold is −$1.3k/month in 2020-24. Neither beats SPY. The day-1 gap-and-hold continuation loses money in both of the honest years, which is consistent with the reversal finding: liquid names mean-revert over days; they don't trend.

## The best honest rule, written exactly

> **LOSER5d-top500-H3-N5.** Run this every trading day after the close, using only data up to and including today's close.
> - **Universe:** US common stocks and ADRs with close ≥ $10, at least 55 of the last 60 sessions traded, ranked in the top 500 by 20-session median of close×volume.
> - **Signal:** for each name, r5 = close_today / close_5_sessions_ago − 1.
> - **Entry:** at the next open (market-on-open order), fill every empty slot, up to 5 positions of $20,000 each, with the names that have the lowest r5 and are not already held.
> - **Exit:** sell each position with a market-on-open order on the morning after its 3rd close held. There is no stop and no profit target.
> - **Exclusions:** skip a name if it has a split scheduled within the next 5 sessions or had one in the last 25.
>
> Honest 2024-10 → 2026-09 result at 6 bps/side: **+$2,794 / +$6,974 / +$12,615 per month** (Y1 / Y2 / OOS), $5,702/month overall, 35 trades/month, +$169/trade overall, 53% winners, max drawdown −$37k, ex-top-5 +$3,725/month, 100th percentile against the random-ticker control. At 12 bps/side: +$2,012 / +$6,139 / +$11,767. The halal-present-day line is +$2,150 / +$7,637 / +$14,513, but it is hindsight-biased; its own control makes +$2.0k / +$2.9k / +$2.5k.

## Verdict: worth paper trading?

- **Connors mean reversion: no.** It is break-even to negative on the honest tape, decayed in the long check, and always below SPY buy-and-hold.
- **Momentum/breakout: no.**
- **1-week loser reversal: not as an edge.** Its 2024-26 numbers are the best this campaign has produced on an honest, liquid, point-in-time tape. But two things undercut it:
  - It is a beta-~2 high-volatility book.
  - Its alpha was negative for the decade 2010-19 even on survivorship-flattered S&P data.

  If the user wants it in paper, run it only as a **zero-capital shadow book**. It is cheap: one batch of market-on-open orders a day and about 35 round trips a month. The kill rules should be judged on alpha against beta-adjusted SPY rather than raw dollars:
  - Retire it if the rolling 3-month alpha versus beta×SPY is < 0.
  - Retire it if the drawdown exceeds −$25k.

  Do not fund it on the strength of the 2024-26 tape.
- **For multi-day holds specifically: SPY buy-and-hold beat every swing family here on a risk-adjusted basis in most periods.** The reversal book only won in high-volatility rebound regimes.

## Appendix: full grids (generated from `data/research_oct/sr_results_{gd,long}.json`)

Cell format: `$/mo 6 bps (12 bps) ; trades/mo ; $/trade ; win rate ; max DD ; control percentile`. "large" means top 500 by $ volume (on `long`, it means all S&P members). Rows marked HALAL-present-day use the hindsight list.

### gd

| rule | Y1 | Y2 | OOS | ALL $/mo ; ex-top5 ; ctl pct |
|---|---|---|---|---|
| SPY buy-and-hold $100k | +1016 ; DD -20k | +1515 ; DD -10k | +1044 ; DD -3k | |
| MR-rsi2<5 ma200 x>ma5 H10 N5 | +649 (+497) ; 6/mo ; +103/tr ; w0.62 ; DD -4k ; p70 | -997 (-1567) ; 24/mo ; -42/tr ; w0.58 ; DD -39k ; p7 | -410 (-986) ; 24/mo ; -17/tr ; w0.52 ; DD -4k ; p70 | -262 ; -922 ; p13 |
| MR-rsi2<5 ma200 x>ma5 H10 N10 | +535 (+380) ; 13/mo ; +41/tr ; w0.68 ; DD -4k ; p60 | -51 (-646) ; 50/mo ; -1/tr ; w0.61 ; DD -25k ; p3 | -4102 (-4670) ; 48/mo ; -86/tr ; w0.45 ; DD -10k ; p47 | -145 ; -476 ; p17 |
| MR-rsi2<5 ma200 x>ma5 H10 N10 HALAL-present-day | +754 (+665) | +2274 (+1793) | +1030 (+513) | |
| MR-rsi2<5 ma100 x>ma5 H10 N5 | +753 (+320) ; 18/mo ; +42/tr ; w0.63 ; DD -39k ; p73 | +776 (+169) ; 25/mo ; +31/tr ; w0.63 ; DD -27k ; p30 | -2326 (-2865) ; 22/mo ; -103/tr ; w0.47 ; DD -8k ; p70 | +508 ; -522 ; p57 |
| MR-rsi2<5 ma100 x>ma5 H10 N10 | -574 (-960) ; 32/mo ; -18/tr ; w0.62 ; DD -30k ; p30 | -779 (-1361) ; 48/mo ; -16/tr ; w0.59 ; DD -30k ; p3 | -3380 (-3937) ; 46/mo ; -73/tr ; w0.44 ; DD -9k ; p40 | -910 ; -1418 ; p3 |
| MR-rsi2<5 ma100 x>ma5 H10 N10 HALAL-present-day | +1196 (+967) | +2602 (+2163) | -201 (-676) | |
| MR-rsi2<5 ma50 x>ma5 H10 N5 | +722 (+191) ; 22/mo ; +33/tr ; w0.62 ; DD -31k ; p77 | +47 (-559) ; 25/mo ; +2/tr ; w0.62 ; DD -28k ; p27 | -1771 (-2370) ; 25/mo ; -71/tr ; w0.48 ; DD -6k ; p80 | +177 ; -689 ; p67 |
| MR-rsi2<5 ma50 x>ma5 H10 N10 | -240 (-742) ; 42/mo ; -6/tr ; w0.61 ; DD -34k ; p73 | +298 (-284) ; 48/mo ; +6/tr ; w0.61 ; DD -24k ; p20 | -2874 (-3437) ; 47/mo ; -61/tr ; w0.52 ; DD -7k ; p63 | -191 ; -583 ; p33 |
| MR-rsi2<5 ma50 x>ma5 H10 N10 HALAL-present-day | +2317 (+2048) | +3443 (+3076) | -46 (-472) | |
| MR-rsi2<10 ma100 x>rsi70 H5 N5 | +29 (-420) ; 19/mo ; +2/tr ; w0.57 ; DD -33k ; p47 | +1682 (+1053) ; 26/mo ; +64/tr ; w0.58 ; DD -26k ; p80 | -2832 (-3430) ; 25/mo ; -113/tr ; w0.48 ; DD -9k ; p50 | +617 ; -577 ; p67 |
| MR-rsi2<10 ma100 x>rsi70 H5 N10 | +193 (-237) ; 36/mo ; +5/tr ; w0.54 ; DD -29k ; p63 | +873 (+242) ; 52/mo ; +17/tr ; w0.57 ; DD -17k ; p43 | -5333 (-5973) ; 54/mo ; -100/tr ; w0.38 ; DD -12k ; p27 | +72 ; -753 ; p40 |
| MR-rsi2<10 ma100 x>rsi70 H5 N10 HALAL-present-day | +513 (+172) | +1227 (+635) | +2067 (+1448) | |
| MR-rsi3<15 ma100 x>ma5 H10 N5 | -1964 (-2376) ; 17/mo ; -114/tr ; w0.65 ; DD -49k ; p10 | +581 (-17) ; 25/mo ; +23/tr ; w0.62 ; DD -33k ; p40 | +877 (+288) ; 24/mo ; +36/tr ; w0.57 ; DD -8k ; p90 | -454 ; -1169 ; p27 |
| MR-rsi3<15 ma100 x>ma5 H10 N10 | -47 (-442) ; 33/mo ; -1/tr ; w0.61 ; DD -34k ; p47 | +89 (-504) ; 49/mo ; +2/tr ; w0.61 ; DD -17k ; p27 | -3168 (-3731) ; 47/mo ; -67/tr ; w0.46 ; DD -10k ; p43 | -239 ; -905 ; p27 |
| MR-rsi3<15 ma100 x>ma5 H10 N10 HALAL-present-day | +959 (+714) | +2345 (+1877) | +2195 (+1672) | |
| MR-down3 ma100 x>ma5 H10 N5 | -165 (-618) ; 19/mo ; -9/tr ; w0.61 ; DD -40k ; p47 | -1 (-589) ; 24/mo ; -0/tr ; w0.61 ; DD -26k ; p17 | -3237 (-3764) ; 22/mo ; -147/tr ; w0.45 ; DD -8k ; p47 | -339 ; -1369 ; p23 |
| MR-down3 ma100 x>ma5 H10 N10 | -1615 (-2051) ; 36/mo ; -44/tr ; w0.60 ; DD -35k ; p7 | +109 (-481) ; 49/mo ; +2/tr ; w0.58 ; DD -20k ; p23 | -3335 (-3898) ; 47/mo ; -71/tr ; w0.47 ; DD -8k ; p40 | -897 ; -1406 ; p3 |
| MR-down3 ma100 x>ma5 H10 N10 HALAL-present-day | +1081 (+749) | +1062 (+489) | +3663 (+3025) | |
| MR-bbl ma100 x>ma5 H10 N5 | -1184 (-1505) ; 13/mo ; -88/tr ; w0.62 ; DD -41k ; p10 | +1015 (+452) ; 23/mo ; +43/tr ; w0.58 ; DD -18k ; p37 | -5623 (-6172) ; 23/mo ; -244/tr ; w0.50 ; DD -14k ; p17 | -454 ; -1034 ; p17 |
| MR-bbl ma100 x>ma5 H10 N10 | -951 (-1247) ; 25/mo ; -38/tr ; w0.58 ; DD -35k ; p23 | +1926 (+1376) ; 46/mo ; +42/tr ; w0.60 ; DD -13k ; p80 | -5172 (-5698) ; 44/mo ; -118/tr ; w0.43 ; DD -14k ; p20 | +136 ; -294 ; p57 |
| MR-bbl ma100 x>ma5 H10 N10 HALAL-present-day | +363 (+220) | +2982 (+2682) | +1954 (+1557) | |
| MR-low10 ma100 x>ma5 H10 N5 | +508 (+39) ; 20/mo ; +26/tr ; w0.66 ; DD -32k ; p63 | +806 (+195) ; 25/mo ; +32/tr ; w0.63 ; DD -27k ; p30 | -2326 (-2865) ; 22/mo ; -103/tr ; w0.47 ; DD -8k ; p67 | +421 ; -609 ; p43 |
| MR-low10 ma100 x>ma5 H10 N10 | -717 (-1156) ; 37/mo ; -20/tr ; w0.61 ; DD -31k ; p40 | -63 (-655) ; 49/mo ; -1/tr ; w0.59 ; DD -25k ; p17 | -3380 (-3937) ; 46/mo ; -73/tr ; w0.44 ; DD -9k ; p57 | -612 ; -1119 ; p13 |
| MR-low10 ma100 x>ma5 H10 N10 HALAL-present-day | +695 (+336) | +1294 (+714) | +2756 (+2136) | |
| MR-rsi2<5 notrend x>ma5 H10 N5 | -2187 (-2711) ; 22/mo ; -100/tr ; w0.58 ; DD -30k ; p10 | -401 (-991) ; 25/mo ; -16/tr ; w0.62 ; DD -34k ; p17 | +151 (-390) ; 22/mo ; +7/tr ; w0.51 ; DD -11k ; p80 | -1099 ; -2010 ; p7 |
| MR-rsi2<5 notrend x>ma5 H10 N10 | -67 (-605) ; 45/mo ; -1/tr ; w0.62 ; DD -22k ; p47 | +808 (+213) ; 50/mo ; +16/tr ; w0.65 ; DD -26k ; p40 | -1574 (-2113) ; 45/mo ; -35/tr ; w0.51 ; DD -11k ; p77 | +245 ; -323 ; p43 |
| MR-rsi2<5 notrend x>ma5 H10 N10 HALAL-present-day | +2336 (+1913) | +1275 (+734) | +3667 (+3034) | |
| MR-rsi2<5 ma100 large x>ma5 H10 N5 | -881 (-1255) ; 16/mo ; -56/tr ; w0.63 ; DD -33k ; p37 | -714 (-1250) ; 22/mo ; -32/tr ; w0.55 ; DD -42k ; p7 | -1430 (-1982) ; 23/mo ; -62/tr ; w0.50 ; DD -6k ; p50 | -843 ; -1538 ; p3 |
| MR-rsi2<5 ma100 large x>ma5 H10 N10 | -101 (-439) ; 28/mo ; -4/tr ; w0.63 ; DD -29k ; p40 | +876 (+359) ; 43/mo ; +20/tr ; w0.59 ; DD -21k ; p40 | +368 (-172) ; 45/mo ; +8/tr ; w0.52 ; DD -5k ; p73 | +427 ; -50 ; p40 |
| MR-rsi2<5 ma100 large x>ma5 H10 N10 HALAL-present-day | +268 (+128) | +4620 (+4322) | +2576 (+2251) | |
| WR-weekly-losers large H5 N5 | -1849 (-2220) ; 16/mo ; -119/tr ; w0.50 ; DD -45k ; p17 | +1163 (+732) ; 18/mo ; +65/tr ; w0.52 ; DD -35k ; p63 | +4939 (+4456) ; 20/mo ; +247/tr ; w0.55 ; DD -8k ; p90 | +223 ; -1467 ; p53 |
| WR-weekly-losers large H5 N10 | -1049 (-1421) ; 31/mo ; -34/tr ; w0.48 ; DD -45k ; p43 | +523 (+93) ; 36/mo ; +15/tr ; w0.51 ; DD -32k ; p40 | +5499 (+5016) ; 40/mo ; +137/tr ; w0.53 ; DD -7k ; p100 | +283 ; -643 ; p73 |
| WR-weekly-losers large H5 N10 HALAL-present-day | +1064 (+691) | +3669 (+3237) | +7328 (+6843) | |
| WR-daily-ret5<p5 large H5 N5 | +2185 (+1716) ; 20/mo ; +112/tr ; w0.51 ; DD -38k ; p87 | +1897 (+1395) ; 21/mo ; +91/tr ; w0.51 ; DD -46k ; p70 | +4515 (+3972) ; 22/mo ; +201/tr ; w0.53 ; DD -6k ; p93 | +2235 ; +635 ; p97 |
| WR-daily-ret5<p5 large H5 N10 | +4757 (+4286) ; 39/mo ; +122/tr ; w0.52 ; DD -38k ; p100 | -1194 (-1695) ; 42/mo ; -29/tr ; w0.47 ; DD -43k ; p3 | +852 (+317) ; 44/mo ; +19/tr ; w0.46 ; DD -9k ; p97 | +1456 ; +503 ; p100 |
| WR-daily-ret5<p5 large H5 N10 HALAL-present-day | +2854 (+2464) | +7187 (+6742) | +7196 (+6717) | |
| MO-52wHigh+vol1.5 H10 N5 | +0 (+0) ; 0/mo ; +0/tr ; w0.00 ; DD +0k ; p0 | +267 (+14) ; 10/mo ; +25/tr ; w0.45 ; DD -35k ; p23 | -4917 (-5166) ; 10/mo ; -468/tr ; w0.33 ; DD -14k ; p37 | -276 ; -1478 ; p23 |
| MO-52wHigh+vol1.5 H10 N10 | +0 (+0) ; 0/mo ; +0/tr ; w0.00 ; DD +0k ; p0 | +2281 (+2028) ; 21/mo ; +109/tr ; w0.51 ; DD -24k ; p70 | -4529 (-4772) ; 20/mo ; -221/tr ; w0.39 ; DD -10k ; p40 | +763 ; -56 ; p67 |
| MO-120dHigh+vol1.5 H10 N5 | +876 (+720) ; 6/mo ; +135/tr ; w0.49 ; DD -32k ; p73 | +2265 (+2011) ; 10/mo ; +216/tr ; w0.54 ; DD -44k ; p70 | -1542 (-1793) ; 10/mo ; -147/tr ; w0.48 ; DD -8k ; p77 | +1369 ; -351 ; p87 |
| MO-120dHigh+vol1.5 H10 N10 | -700 (-853) ; 13/mo ; -55/tr ; w0.42 ; DD -24k ; p47 | +1734 (+1481) ; 21/mo ; +83/tr ; w0.48 ; DD -44k ; p60 | -2094 (-2345) ; 21/mo ; -100/tr ; w0.43 ; DD -8k ; p53 | +401 ; -1246 ; p53 |
| MO-gap4hold+vol2 H3 N5 | -3483 (-4192) ; 30/mo ; -118/tr ; w0.47 ; DD -58k ; p0 | -3543 (-4294) ; 31/mo ; -113/tr ; w0.45 ; DD -62k ; p0 | +4838 (+4162) ; 28/mo ; +173/tr ; w0.54 ; DD -7k ; p100 | -2820 ; -4848 ; p0 |
| MO-gap4hold+vol2 H3 N10 | -3891 (-4494) ; 50/mo ; -77/tr ; w0.45 ; DD -51k ; p0 | -468 (-1127) ; 55/mo ; -9/tr ; w0.48 ; DD -24k ; p17 | +2831 (+2271) ; 46/mo ; +61/tr ; w0.49 ; DD -5k ; p97 | -1620 ; -2775 ; p3 |
| MO-gap4hold+vol2 H10 N5 | -3924 (-4153) ; 10/mo ; -409/tr ; w0.42 ; DD -69k ; p0 | -4565 (-4812) ; 10/mo ; -438/tr ; w0.46 ; DD -80k ; p0 | +3115 (+2861) ; 10/mo ; +297/tr ; w0.48 ; DD -10k ; p93 | -3658 ; -5444 ; p0 |
| MO-gap4hold+vol2 H10 N10 | -984 (-1213) ; 19/mo ; -52/tr ; w0.48 ; DD -41k ; p17 | -1809 (-2054) ; 20/mo ; -88/tr ; w0.45 ; DD -60k ; p0 | +2551 (+2309) ; 20/mo ; +128/tr ; w0.47 ; DD -7k ; p97 | -1102 ; -2418 ; p10 |

Close-entry (OPTIMISTIC MOC approximation) vs open-entry, ALL $/mo:
- MR-rsi2<5 ma200 x>ma5 H10 N5: close -17 vs open -262
- MR-rsi2<5 ma200 x>ma5 H10 N10: close +328 vs open -145
- MR-rsi2<5 ma100 x>ma5 H10 N5: close +547 vs open +508
- MR-rsi2<5 ma100 x>ma5 H10 N10: close -519 vs open -910
- MR-rsi2<5 ma50 x>ma5 H10 N5: close +567 vs open +177
- MR-rsi2<5 ma50 x>ma5 H10 N10: close -58 vs open -191
- MR-rsi2<10 ma100 x>rsi70 H5 N5: close +446 vs open +617
- MR-rsi2<10 ma100 x>rsi70 H5 N10: close +233 vs open +72
- MR-rsi3<15 ma100 x>ma5 H10 N5: close -394 vs open -454
- MR-rsi3<15 ma100 x>ma5 H10 N10: close +544 vs open -239
- MR-down3 ma100 x>ma5 H10 N5: close -459 vs open -339
- MR-down3 ma100 x>ma5 H10 N10: close -647 vs open -897
- MR-bbl ma100 x>ma5 H10 N5: close -252 vs open -454
- MR-bbl ma100 x>ma5 H10 N10: close +616 vs open +136
- MR-low10 ma100 x>ma5 H10 N5: close +294 vs open +421
- MR-low10 ma100 x>ma5 H10 N10: close -229 vs open -612
- MR-rsi2<5 notrend x>ma5 H10 N5: close -1061 vs open -1099
- MR-rsi2<5 notrend x>ma5 H10 N10: close +365 vs open +245
- MR-rsi2<5 ma100 large x>ma5 H10 N5: close -652 vs open -843
- MR-rsi2<5 ma100 large x>ma5 H10 N10: close +473 vs open +427

### long

| rule | L05-09 | L10-14 | L15-19 | L20-24 | ALL $/mo ; ex-top5 ; ctl pct |
|---|---|---|---|---|---|
| SPY buy-and-hold $100k | +33 ; DD -75k | +1736 ; DD -23k | +1213 ; DD -30k | +1608 ; DD -38k | |
| MR-rsi2<5 ma200 x>ma5 H10 N5 | +831 (+401) ; 18/mo ; +46/tr ; w0.63 ; DD -40k ; p97 | +821 (+342) ; 20/mo ; +41/tr ; w0.64 ; DD -19k ; p70 | -29 (-515) ; 20/mo ; -1/tr ; w0.59 ; DD -34k ; p23 | +1014 (+532) ; 20/mo ; +51/tr ; w0.63 ; DD -27k ; p93 | +655 ; +582 ; p100 |
| MR-rsi2<5 ma200 x>ma5 H10 N10 | +886 (+535) ; 29/mo ; +30/tr ; w0.65 ; DD -15k ; p100 | +934 (+522) ; 34/mo ; +27/tr ; w0.66 ; DD -18k ; p83 | +64 (-367) ; 36/mo ; +2/tr ; w0.60 ; DD -26k ; p40 | +1008 (+582) ; 35/mo ; +28/tr ; w0.64 ; DD -20k ; p100 | +720 ; +680 ; p100 |
| MR-rsi2<5 ma200 x>ma5 H10 N10 HALAL-present-day | +369 (+265) | +363 (+196) | +277 (+103) | +841 (+644) | |
| MR-rsi2<5 ma100 x>ma5 H10 N5 | +1410 (+999) ; 17/mo ; +83/tr ; w0.65 ; DD -20k ; p97 | +540 (+108) ; 18/mo ; +30/tr ; w0.64 ; DD -17k ; p40 | -576 (-1041) ; 19/mo ; -30/tr ; w0.58 ; DD -39k ; p0 | +1043 (+579) ; 19/mo ; +54/tr ; w0.62 ; DD -23k ; p100 | +598 ; +546 ; p97 |
| MR-rsi2<5 ma100 x>ma5 H10 N10 | +706 (+381) ; 27/mo ; +26/tr ; w0.64 ; DD -21k ; p100 | +701 (+337) ; 30/mo ; +23/tr ; w0.65 ; DD -14k ; p77 | -309 (-712) ; 34/mo ; -9/tr ; w0.59 ; DD -31k ; p0 | +890 (+489) ; 33/mo ; +27/tr ; w0.63 ; DD -23k ; p100 | +492 ; +458 ; p90 |
| MR-rsi2<5 ma100 x>ma5 H10 N10 HALAL-present-day | +200 (+109) | +385 (+248) | +218 (+72) | +543 (+367) | |
| MR-rsi2<5 ma50 x>ma5 H10 N5 | +520 (+171) ; 15/mo ; +36/tr ; w0.63 ; DD -32k ; p80 | +80 (-305) ; 16/mo ; +5/tr ; w0.62 ; DD -22k ; p13 | -693 (-1111) ; 17/mo ; -40/tr ; w0.58 ; DD -63k ; p0 | +600 (+188) ; 17/mo ; +35/tr ; w0.61 ; DD -42k ; p87 | +121 ; +60 ; p17 |
| MR-rsi2<5 ma50 x>ma5 H10 N10 | +554 (+283) ; 23/mo ; +25/tr ; w0.63 ; DD -21k ; p100 | +440 (+128) ; 26/mo ; +17/tr ; w0.64 ; DD -19k ; p67 | -474 (-822) ; 29/mo ; -16/tr ; w0.60 ; DD -41k ; p0 | +758 (+412) ; 29/mo ; +26/tr ; w0.63 ; DD -23k ; p97 | +314 ; +278 ; p93 |
| MR-rsi2<5 ma50 x>ma5 H10 N10 HALAL-present-day | +101 (+33) | +421 (+327) | -11 (-121) | +518 (+389) | |
| MR-rsi2<10 ma100 x>rsi70 H5 N5 | +773 (+222) ; 23/mo ; +34/tr ; w0.60 ; DD -32k ; p87 | +920 (+357) ; 23/mo ; +39/tr ; w0.62 ; DD -16k ; p73 | -559 (-1149) ; 25/mo ; -23/tr ; w0.57 ; DD -45k ; p3 | +827 (+241) ; 24/mo ; +34/tr ; w0.60 ; DD -34k ; p97 | +486 ; +414 ; p57 |
| MR-rsi2<10 ma100 x>rsi70 H5 N10 | +567 (+82) ; 40/mo ; +14/tr ; w0.60 ; DD -27k ; p40 | +650 (+133) ; 43/mo ; +15/tr ; w0.61 ; DD -19k ; p83 | -512 (-1055) ; 45/mo ; -11/tr ; w0.57 ; DD -43k ; p0 | +1009 (+454) ; 46/mo ; +22/tr ; w0.61 ; DD -29k ; p100 | +421 ; +375 ; p53 |
| MR-rsi2<10 ma100 x>rsi70 H5 N10 HALAL-present-day | +35 (-143) | +525 (+259) | +205 (-68) | +994 (+677) | |
| MR-rsi3<15 ma100 x>ma5 H10 N5 | +1024 (+594) ; 18/mo ; +57/tr ; w0.63 ; DD -30k ; p97 | +1068 (+602) ; 19/mo ; +55/tr ; w0.64 ; DD -16k ; p97 | -267 (-751) ; 20/mo ; -13/tr ; w0.58 ; DD -29k ; p10 | +1157 (+668) ; 20/mo ; +57/tr ; w0.63 ; DD -19k ; p97 | +740 ; +679 ; p93 |
| MR-rsi3<15 ma100 x>ma5 H10 N10 | +651 (+298) ; 29/mo ; +22/tr ; w0.62 ; DD -22k ; p97 | +621 (+224) ; 33/mo ; +19/tr ; w0.63 ; DD -16k ; p67 | -247 (-675) ; 36/mo ; -7/tr ; w0.59 ; DD -31k ; p3 | +978 (+548) ; 36/mo ; +27/tr ; w0.63 ; DD -17k ; p100 | +495 ; +460 ; p93 |
| MR-rsi3<15 ma100 x>ma5 H10 N10 HALAL-present-day | +312 (+205) | +487 (+326) | +262 (+95) | +773 (+571) | |
| MR-down3 ma100 x>ma5 H10 N5 | +1320 (+752) ; 24/mo ; +56/tr ; w0.64 ; DD -32k ; p100 | +412 (-168) ; 24/mo ; +17/tr ; w0.64 ; DD -23k ; p33 | -194 (-797) ; 25/mo ; -8/tr ; w0.62 ; DD -39k ; p7 | +908 (+299) ; 25/mo ; +36/tr ; w0.63 ; DD -32k ; p90 | +607 ; +546 ; p90 |
| MR-down3 ma100 x>ma5 H10 N10 | +899 (+385) ; 43/mo ; +21/tr ; w0.63 ; DD -32k ; p97 | +451 (-89) ; 45/mo ; +10/tr ; w0.64 ; DD -20k ; p23 | -199 (-767) ; 47/mo ; -4/tr ; w0.61 ; DD -30k ; p13 | +802 (+230) ; 48/mo ; +17/tr ; w0.63 ; DD -31k ; p87 | +484 ; +445 ; p87 |
| MR-down3 ma100 x>ma5 H10 N10 HALAL-present-day | +66 (-133) | +520 (+228) | +235 (-69) | +1033 (+687) | |
| MR-bbl ma100 x>ma5 H10 N5 | +366 (+58) ; 13/mo ; +29/tr ; w0.60 ; DD -37k ; p90 | +632 (+300) ; 14/mo ; +46/tr ; w0.63 ; DD -15k ; p90 | +102 (-281) ; 16/mo ; +6/tr ; w0.60 ; DD -23k ; p47 | +433 (+65) ; 15/mo ; +28/tr ; w0.60 ; DD -29k ; p87 | +383 ; +330 ; p93 |
| MR-bbl ma100 x>ma5 H10 N10 | +587 (+354) ; 19/mo ; +30/tr ; w0.62 ; DD -18k ; p100 | +353 (+96) ; 21/mo ; +17/tr ; w0.62 ; DD -14k ; p77 | +99 (-214) ; 26/mo ; +4/tr ; w0.61 ; DD -20k ; p37 | +283 (-18) ; 25/mo ; +11/tr ; w0.61 ; DD -36k ; p83 | +331 ; +302 ; p100 |
| MR-bbl ma100 x>ma5 H10 N10 HALAL-present-day | +123 (+74) | +341 (+252) | +362 (+263) | +271 (+157) | |
| MR-low10 ma100 x>ma5 H10 N5 | +813 (+234) ; 24/mo ; +34/tr ; w0.64 ; DD -42k ; p97 | +1228 (+652) ; 24/mo ; +51/tr ; w0.65 ; DD -19k ; p93 | -63 (-646) ; 24/mo ; -3/tr ; w0.61 ; DD -26k ; p23 | +1059 (+452) ; 25/mo ; +42/tr ; w0.64 ; DD -22k ; p90 | +756 ; +699 ; p100 |
| MR-low10 ma100 x>ma5 H10 N10 | +596 (+81) ; 43/mo ; +14/tr ; w0.63 ; DD -42k ; p97 | +919 (+387) ; 44/mo ; +21/tr ; w0.64 ; DD -17k ; p97 | -25 (-577) ; 46/mo ; -1/tr ; w0.61 ; DD -23k ; p23 | +1007 (+441) ; 47/mo ; +21/tr ; w0.63 ; DD -24k ; p93 | +619 ; +571 ; p97 |
| MR-low10 ma100 x>ma5 H10 N10 HALAL-present-day | +74 (-128) | +649 (+360) | +620 (+310) | +789 (+448) | |
| MR-rsi2<5 notrend x>ma5 H10 N5 | +1162 (+604) ; 23/mo ; +50/tr ; w0.62 ; DD -56k ; p100 | +989 (+451) ; 22/mo ; +44/tr ; w0.64 ; DD -20k ; p83 | -745 (-1299) ; 23/mo ; -32/tr ; w0.59 ; DD -60k ; p0 | +1301 (+733) ; 24/mo ; +55/tr ; w0.63 ; DD -67k ; p100 | +669 ; +493 ; p93 |
| MR-rsi2<5 notrend x>ma5 H10 N10 | +1437 (+935) ; 42/mo ; +34/tr ; w0.63 ; DD -33k ; p100 | +809 (+324) ; 40/mo ; +20/tr ; w0.65 ; DD -19k ; p57 | -348 (-867) ; 43/mo ; -8/tr ; w0.59 ; DD -35k ; p0 | +1329 (+804) ; 44/mo ; +30/tr ; w0.64 ; DD -59k ; p100 | +800 ; +690 ; p100 |
| MR-rsi2<5 notrend x>ma5 H10 N10 HALAL-present-day | +509 (+297) | +476 (+245) | +166 (-89) | +1238 (+951) | |
| MR-rsi2<5 ma100 large x>ma5 H10 N5 | +1410 (+999) ; 17/mo ; +83/tr ; w0.65 ; DD -20k ; p97 | +540 (+108) ; 18/mo ; +30/tr ; w0.64 ; DD -17k ; p40 | -576 (-1041) ; 19/mo ; -30/tr ; w0.58 ; DD -39k ; p0 | +1043 (+579) ; 19/mo ; +54/tr ; w0.62 ; DD -23k ; p100 | +598 ; +546 ; p97 |
| MR-rsi2<5 ma100 large x>ma5 H10 N10 | +706 (+381) ; 27/mo ; +26/tr ; w0.64 ; DD -21k ; p100 | +701 (+337) ; 30/mo ; +23/tr ; w0.65 ; DD -14k ; p77 | -309 (-712) ; 34/mo ; -9/tr ; w0.59 ; DD -31k ; p0 | +890 (+489) ; 33/mo ; +27/tr ; w0.63 ; DD -23k ; p100 | +492 ; +458 ; p90 |
| MR-rsi2<5 ma100 large x>ma5 H10 N10 HALAL-present-day | +200 (+109) | +385 (+248) | +218 (+72) | +543 (+367) | |
| WR-weekly-losers large H5 N5 | +217 (-223) ; 18/mo ; +12/tr ; w0.50 ; DD -145k ; p57 | +381 (-59) ; 18/mo ; +21/tr ; w0.52 ; DD -42k ; p27 | +577 (+137) ; 18/mo ; +31/tr ; w0.48 ; DD -48k ; p90 | +1405 (+968) ; 18/mo ; +77/tr ; w0.52 ; DD -98k ; p93 | +636 ; +337 ; p93 |
| WR-weekly-losers large H5 N10 | +532 (+91) ; 37/mo ; +15/tr ; w0.50 ; DD -135k ; p100 | +665 (+224) ; 37/mo ; +18/tr ; w0.52 ; DD -36k ; p87 | +272 (-168) ; 37/mo ; +7/tr ; w0.49 ; DD -37k ; p70 | +1918 (+1481) ; 36/mo ; +53/tr ; w0.52 ; DD -89k ; p100 | +833 ; +672 ; p100 |
| WR-weekly-losers large H5 N10 HALAL-present-day | -180 (-620) | +664 (+223) | +772 (+331) | +2181 (+1744) | |
| WR-daily-ret5<p5 large H5 N5 | +981 (+476) ; 21/mo ; +47/tr ; w0.51 ; DD -153k ; p97 | +1025 (+521) ; 21/mo ; +49/tr ; w0.52 ; DD -42k ; p63 | +244 (-259) ; 21/mo ; +12/tr ; w0.49 ; DD -42k ; p37 | +1148 (+644) ; 21/mo ; +55/tr ; w0.52 ; DD -103k ; p83 | +846 ; +489 ; p97 |
| WR-daily-ret5<p5 large H5 N10 | +613 (+108) ; 42/mo ; +15/tr ; w0.51 ; DD -145k ; p97 | +1228 (+723) ; 42/mo ; +29/tr ; w0.53 ; DD -39k ; p87 | +754 (+251) ; 42/mo ; +18/tr ; w0.51 ; DD -33k ; p83 | +1301 (+797) ; 42/mo ; +31/tr ; w0.52 ; DD -94k ; p93 | +970 ; +788 ; p100 |
| WR-daily-ret5<p5 large H5 N10 HALAL-present-day | -276 (-503) | +646 (+340) | +909 (+612) | +1622 (+1260) | |
| MO-52wHigh+vol1.5 H10 N5 | +415 (+238) ; 7/mo ; +56/tr ; w0.53 ; DD -32k ; p87 | +547 (+322) ; 9/mo ; +59/tr ; w0.57 ; DD -25k ; p13 | -14 (-238) ; 9/mo ; -2/tr ; w0.53 ; DD -24k ; p13 | -50 (-264) ; 9/mo ; -6/tr ; w0.51 ; DD -26k ; p7 | +228 ; +142 ; p17 |
| MO-52wHigh+vol1.5 H10 N10 | +148 (-9) ; 13/mo ; +11/tr ; w0.52 ; DD -31k ; p70 | +523 (+313) ; 17/mo ; +30/tr ; w0.56 ; DD -19k ; p57 | +306 (+97) ; 17/mo ; +18/tr ; w0.54 ; DD -15k ; p47 | +201 (+7) ; 16/mo ; +12/tr ; w0.52 ; DD -24k ; p20 | +295 ; +248 ; p43 |
| MO-gap4hold+vol2 H3 N5 | -505 (-690) ; 8/mo ; -65/tr ; w0.48 ; DD -68k ; p43 | +277 (+111) ; 7/mo ; +40/tr ; w0.57 ; DD -19k ; p93 | +526 (+309) ; 9/mo ; +58/tr ; w0.55 ; DD -15k ; p100 | -1304 (-1534) ; 10/mo ; -136/tr ; w0.47 ; DD -89k ; p0 | -238 ; -411 ; p30 |
| MO-gap4hold+vol2 H3 N10 | -326 (-427) ; 8/mo ; -39/tr ; w0.47 ; DD -40k ; p33 | +171 (+84) ; 7/mo ; +24/tr ; w0.57 ; DD -12k ; p93 | +238 (+120) ; 10/mo ; +24/tr ; w0.54 ; DD -8k ; p100 | -1369 (-1509) ; 12/mo ; -116/tr ; w0.46 ; DD -83k ; p0 | -308 ; -395 ; p0 |
| MO-gap4hold+vol2 H10 N5 | +635 (+498) ; 6/mo ; +112/tr ; w0.55 ; DD -80k ; p100 | +595 (+467) ; 5/mo ; +112/tr ; w0.52 ; DD -24k ; p70 | +239 (+90) ; 6/mo ; +39/tr ; w0.52 ; DD -33k ; p10 | +456 (+309) ; 6/mo ; +74/tr ; w0.55 ; DD -47k ; p40 | +481 ; +233 ; p77 |
| MO-gap4hold+vol2 H10 N10 | +479 (+391) ; 7/mo ; +65/tr ; w0.56 ; DD -47k ; p100 | +236 (+154) ; 7/mo ; +35/tr ; w0.52 ; DD -19k ; p93 | +287 (+184) ; 9/mo ; +33/tr ; w0.53 ; DD -15k ; p47 | +31 (-75) ; 9/mo ; +4/tr ; w0.53 ; DD -47k ; p3 | +261 ; +133 ; p77 |

Close-entry (OPTIMISTIC MOC approximation) vs open-entry, ALL $/mo:
- MR-rsi2<5 ma200 x>ma5 H10 N5: close +776 vs open +655
- MR-rsi2<5 ma200 x>ma5 H10 N10: close +806 vs open +720
- MR-rsi2<5 ma100 x>ma5 H10 N5: close +772 vs open +598
- MR-rsi2<5 ma100 x>ma5 H10 N10: close +571 vs open +492
- MR-rsi2<5 ma50 x>ma5 H10 N5: close +295 vs open +121
- MR-rsi2<5 ma50 x>ma5 H10 N10: close +390 vs open +314
- MR-rsi2<10 ma100 x>rsi70 H5 N5: close +770 vs open +486
- MR-rsi2<10 ma100 x>rsi70 H5 N10: close +584 vs open +421
- MR-rsi3<15 ma100 x>ma5 H10 N5: close +840 vs open +740
- MR-rsi3<15 ma100 x>ma5 H10 N10: close +588 vs open +495
- MR-down3 ma100 x>ma5 H10 N5: close +866 vs open +607
- MR-down3 ma100 x>ma5 H10 N10: close +734 vs open +484
- MR-bbl ma100 x>ma5 H10 N5: close +440 vs open +383
- MR-bbl ma100 x>ma5 H10 N10: close +331 vs open +331
- MR-low10 ma100 x>ma5 H10 N5: close +876 vs open +756
- MR-low10 ma100 x>ma5 H10 N10: close +755 vs open +619
- MR-rsi2<5 notrend x>ma5 H10 N5: close +667 vs open +669
- MR-rsi2<5 notrend x>ma5 H10 N10: close +754 vs open +800
- MR-rsi2<5 ma100 large x>ma5 H10 N5: close +772 vs open +598
- MR-rsi2<5 ma100 large x>ma5 H10 N10: close +571 vs open +492
