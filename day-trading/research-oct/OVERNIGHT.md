# OVERNIGHT — can selection harvest the overnight premium net of cost?

Agent OVERNIGHT, 2026-10-01. Research only; live paper untouched.
Code: `plan/on_panel.py, on_feat.py, on_lib.py, on_screen.py, on_port.py, on_final.py, on_hold.py, on_report.py, on_m1w.py, on_m1w_eval.py, on_fetch_picks.py`.
Logs/caches: `data/research_oct/on_*` (≈ 250 MB total, no keys written; not committed).

## Verdict (read this first)

**Selection works gross, but the edge is about the size of the toll. Not worth paper trading with real money as-is. A zero-capital shadow log is worth running, because the open question is execution cost, not signal.**

* The best honest rule (**buy the 20 worst 5-day losers at the close, sell at the next open**) earns **18.9 bp gross per night** against 5.2 bp for 20 random names from the same universe and 11.4 bp for 20 random *high-volatility* names. It beats the 30-seed random control at the 100th percentile in Y1, Y2 and OOS, and the volatility-matched control at the 100th/97th/80th. The selection is real.
* **Net at 6 bps/side** on $100k every night: **+$1,439/month** (Y1 +$848, Y2 +$1,838, OOS +$1,995). Win rate 52%, max drawdown **−$27k**, **t = 0.85**, ex-top-5-nights **−$12/night**. Strict settled cash ($50k a night, see Capital) halves that to **+$720/month**.
* **Net at 12 bps/side: negative in every split** (−$1,081/month overall).
* That is no better than simply holding the universe ($1.1–1.9k/month, harness-diagnostic.md §2), and it carries a 27% drawdown and an annualised Sharpe of 0.6. The profit depends on a handful of nights: 14 of 24 months were positive.
* Only cheap execution makes it interesting. If MOC/MOO auction fills really cost about 2 bps/side, the same rule makes +$3,119/month loose or +$1,560/month strict, with t = 1.83. That is an execution question the data here cannot settle: historical NBBO quotes return **HTTP 403** on this plan.

## Setup (what was held fixed)

* **Universe, point in time, delisted names included.** Every CS/ADRC ticker in Polygon grouped-daily (`data/massive/gd`, 563 sessions 2024-08-05 → 2026-09-30). Type comes from `/v3/reference/tickers`, both active=true and active=false. Eligible on day D if:
  * the prior close is ≥ $5;
  * the median dollar volume over the **20 sessions before D** is ≥ $20M;
  * it printed on D.

  That gives a median of **1,854 names per night** and 2,761 distinct names. Nothing about D's outcome enters. 2 of 10,020 picks had no next open (NEP, HOND); filling them with 0 changes nothing.
* **Prices.** Entry at the official close `c_D` (an MOC order). Exit at the official open `o_{D+1}`. gd `o` equals the 09:30 minute-bar open: the median absolute difference is 0.2 bp on 23.5k m1w symbol-days. gd is split-adjusted but not dividend-adjusted, so the overnight return is biased down by the dividend: a conservative bias. Close→open ratios within 3% of a split ratio with a move over 40% are dropped (357 rows).
* **Features.**
  * **PRE** features are known by D's 09:30 open: history through D−1 plus D's opening gap. They are fully causal for an order placed at 15:55.
  * **CLS** features use D's close, a 5-minute look-ahead. They were used for screening only and re-checked at 15:55 on the minute cache (see Execution).
* **Ties** are broken by a seeded random key, never by pool order.
* **Splits.** Y1 = 2024-10 → 2025-07 (208 nights), Y2 = 2025-08 → 2026-07 (251 nights), OOS = 2026-08 → 2026-09-29 (41 nights).
* **Costs.** 6 bps/side central and 12 bps/side stress, charged on both legs every night. A 2 bps/side "auction" row is labelled optimistic.
* **Controls.**
  * 30-seed random-N names per night from the same universe.
  * 30-seed **volatility-matched** random-N, drawn from the top vol20 quintile. Losers are high-volatility names, so this asks whether the rule beats its own risk bucket.
  * SPY close→open.

## Capital (cash account)

A sale at the 09:30 open settles T+1. Read strictly ("overnight positions use settled cash"), the morning's proceeds cannot fund that evening's buy. Two alternating $50k sleeves are then the most that can be deployed, so **$50k per night**: the "strict" rows. The "loose" rows deploy $100k every night. They assume the broker treats buying with proceeds that settle before the next sale as good-faith-compliant: proceeds settle D+2 and the sale is at D+2's open. That is the usual reading, but it is the account holder's call.

## 1. Baseline: the premium exists and is smaller than the toll

| $100k, close→open | gross bp/night Y1 / Y2 / OOS | $/month @6 bps (all) | @12 bps |
|---|---|---:|---:|
| SPY | 1.2 / 6.0 / 7.3 | −$1,656 | −$4,176 |
| universe equal-weight (≈1,850 names) | 2.0 / 6.9 / 8.3 | −$1,475 | −$3,995 |
| random 20 names (30-seed mean) | 2.1 / 7.5 / 6.6 | −$1,424 | — |
| random 20 high-vol names (30-seed mean) | 7.8 / 13.8 / 16.0 | −$119 | — |

A round trip at 6 bps/side is 12 bp, which is more than the whole unselected overnight premium (5 bp). Any profit has to come from selection.

## 2. Feature screen (decile means of the next close→open, bp, `data/research_oct/on_screen.log`)

Consistent in all three splits:

* **High volatility** (vol20, top decile 9.7 / 15.6 / 18.8 bp).
* **Tug-of-war** (past-20-day overnight minus intraday, top decile 6.3 / 13.1 / 21.1). This is the Lou-Polk-Skouras "overnight momentum".
* **Short-term losers.** rev5 bottom decile 7.6 / 14.6 / 29.3. The 5-day return is U-shaped in Y1, where both tails are high, and monotone in Y2/OOS. The prior-day intraday loser and today's gap-down behave the same way.
* **CLS: today's loser** (dret bottom decile 7.8 / 14.7 / 17.6).

Unstable or useless:

* **Overnight momentum on its own.** on_mom20 is monotone in Y1/Y2 but flat in OOS, and its top-N portfolios are **0th percentile in OOS**.
* **Prior-day gap** flips sign between Y2 and OOS.
* **Close location** is weakly reversed. **rvol** shows little.
* **Day-of-week and market regime** (SPY vs MA50, SPY 5-day return, SPY vol, VXX 5-day return, SPY gap) have no monotone, stable pattern. They were not used.
* **Size** (lmdv) is flat.

Earnings were not testable honestly. The only multi-year earnings calendar in the repo (`earnings_yf.json`) covers 2,045 symbols chosen because they once appeared in gapper pools, i.e. outcome-conditioned. Earnings-overnight rows show +81 / +151 / +92 bp, but that number is contaminated by how the symbols were chosen. `earnings_dates.json` only covers Jul–Aug 2026. It is not reported as a result.

## 3. Selectors × N (gross bp/night and percentile vs vol-matched control; $/month loose @ 6 bps)

| selector (PRE unless CLS) | N | Y1 | Y2 | OOS | $/mo Y1 / Y2 / OOS @6 |
|---|---:|---|---|---|---|
| **rev5_lo** (worst 5-day return) | 20 | 16.0 (p100) | 20.8 (p97) | 21.5 (p80) | +848 / +1,838 / +1,995 |
| rev5_lo | 10 | 20.4 (p100) | 15.0 (p63) | 14.9 (p47) | +1,761 / +634 / +612 |
| rev5_lo | 5 | 19.1 | 14.6 | 18.9 | +1,501 / +542 / +1,451 |
| vol+tug+rev5lo (z-sum) | 20 | 17.4 (p100) | 16.5 (p73) | 29.7 (p93) | +1,139 / +955 / +3,711 |
| gap_lo (today's gap-down) | 5 | 16.1 | 20.4 | 38.0 | +870 / +1,768 / +5,457 |
| vol+tug | 5 | 48.5 | 9.3 | **−15.0** | +7,667 / −573 / −5,670 |
| vol20_hi | 10 | 24.8 | 4.3 | 26.1 | +2,687 / −1,624 / +2,968 |
| onmom20_hi | 10 | 24.6 | 6.5 | **−11.6** | +2,648 / −1,148 / −4,958 |
| CLS:dret_lo (today's loser) | 10 | 22.6 (p100) | 27.3 (p100) | 20.0 (p67) | +2,229 / +3,220 / +1,683 |

Concentration (N = 5) gives the best single-year numbers and the worst instability: vol+tug N=5 is +$7.7k/month in Y1 and −$5.7k in OOS. Spreading over 20 names gives the most stable row. Going to N = 50 changes little (rev5_lo N=50: +$1,437/month, OOS +$3,191). Twelve selectors × four N values were tried, so treat the best row as selected from about 50.

CLS:dret_lo is the best gross row, but it is a close-based screen. On the minute cache the 15:55 version overlaps the close version on **91%** of picks and earns 19.6 vs 20.8 bp (§5). It is close to causal, but it was not run on the full universe at 15:55: the minute API was rate-limited (429) for the whole session. It remains a lead, not a result.

## 4. The best honest rule, exactly

> **Each trading day at 15:50–15:55 ET, from all US common stocks/ADRs with prior close ≥ $5 and median daily dollar volume over the prior 20 sessions ≥ $20M, rank by the 5-session return close(D−6) → close(D−1) and take the 20 lowest; break ties by a seeded random number. Submit equal-dollar market-on-close buys ($100k/20 = $5k each, or $2.5k each under strict settled cash). Sell everything at the next session's opening print (market-on-open). No stops, no filters, every night.**

| rev5_lo N=20, $100k loose | bps/side | nights | gross bp | $/night | **$/month** | win | max DD | ex-top-5 $/night | t |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Y1 | 6 | 208 | 16.0 | +40 | **+848** | 52% | −27,139 | −104 | 0.31 |
| Y2 | 6 | 251 | 20.8 | +88 | **+1,838** | 52% | −22,044 | −54 | 0.76 |
| OOS | 6 | 41 | 21.5 | +95 | **+1,995** | 54% | −5,435 | −216 | 0.50 |
| ALL | 6 | 500 | 18.9 | +69 | **+1,439** | 52% | −27,139 | −12 | 0.85 |
| Y1 | 12 | 208 | 16.0 | −80 | −1,672 | 48% | −31,224 | −224 | −0.61 |
| Y2 | 12 | 251 | 20.8 | −32 | −682 | 47% | −35,839 | −174 | −0.28 |
| OOS | 12 | 41 | 21.5 | −25 | −525 | 46% | −7,155 | −336 | −0.13 |
| ALL | 12 | 500 | 18.9 | −51 | −1,081 | 47% | −54,516 | −132 | −0.63 |
| ALL (auction-optimistic) | 2 | 500 | 18.9 | +149 | +3,119 | 54% | −25,619 | +68 | 1.83 |

* **Strict settled cash ($50k/night):** +$720/month at 6 bps (Y1 +$424 / Y2 +$919 / OOS +$998, max DD −$13.6k), −$540/month at 12 bps, +$1,560/month at 2 bps.
* **HALAL-PASS-only line.** This uses the present-day list (`halal_list.json`, 2026-09-17) applied retroactively, so it is a look-ahead list. rev5_lo N=20 nets +$759/month @6 bps. By split: **Y1 −$1,995**, Y2 +$2,262, OOS +$5,524. It is −$1,761/month at 12 bps, and only at the 10th percentile vs the vol-matched control in Y1. It is not robust.
* **Tail.**
  * Night standard deviation is $1,813, annualised Sharpe 0.6.
  * Worst nights: 2025-01-10 (−$7.4k) and 2025-04-02 (−$6.8k, tariff night).
  * Best night: 2026-07-29 (+$13.0k, a semis rebound; checked against minute bars, not a data error).
  * Worst month: 2025-04 at −$12.9k. 14 of 24 months were positive.

## 5. Execution timing (m1w minute cache, 191 causal halal names, 23.5k symbol-days)

| mean bp | 15:55 → close drift | close→09:30 open | close→09:31 open | close→09:35 | close→09:45 |
|---|---:|---:|---:|---:|---:|
| all names Y1 | −1.2 | 7.0 | 5.7 | 6.3 | 3.9 |
| all names Y2 | +0.4 | 13.2 | 10.2 | 12.4 | 11.9 |
| rev5-lowest 5 Y1 | −0.1 | 1.3 | 2.3 | 1.5 | −6.0 |
| rev5-lowest 5 Y2 | +1.6 | 16.9 | 20.3 | 30.9 | 28.2 |

* Buying at the 15:55 last trade or in the closing auction makes no systematic difference (|drift| ≤ 1.6 bp).
* Delaying the exit to 09:31–09:45 does not help reliably: it helps Y2 and hurts Y1. **Keep the opening print.** The m1w OOS has only 4 nights, so it is not shown.
* Spread cost could not be measured. `/v3/quotes` returns 403 on this plan, and the 1,500-pick minute fetch never got past 429s, so the numbers above come from the existing cache only. The 6 bps/side central figure comes from pessimism-audit.md for liquid names (half-spread mean 5.0, median 1–5). Losers are high-volatility names, which pushes their spread toward the upper end of that range. MOC/MOO auction fills pay no spread, which is the case for the 2 bps row, but the live broker (Robinhood) is not known to offer MOC/MOO orders; this needs checking.

## 6. Holding 2–5 sessions (rev5_lo; cohort exits at the open of D+k; capital/k loose, capital/(k+1) strict)

| N, hold | gross/cohort | strict $/month @6 (Y1 / Y2 / OOS / all) | strict @12 all |
|---|---:|---|---:|
| 20, 1 | 18.9 bp | +424 / +919 / +998 / **+720** | −540 |
| 20, 2 | 27.6 | +553 / +1,790 / −512 / **+1,090** | +250 |
| 20, 3 | 25.8 | +383 / +1,440 / −2,088 / +722 | +92 |
| 50, 2 | 35.7 | +1,024 / +2,384 / +400 / **+1,658** | **+818** |
| 50, 3 | 43.5 | +1,292 / +2,320 / −681 / +1,655 | +1,025 |
| 50, 5 | 45.3 | +1,285 / +1,557 / −2,160 / +1,165 | +745 |

Longer holds spread the toll over more drift, so they are the only cost-robust rows. But they are no longer an overnight strategy: they include the intraday legs, mostly collect the high-volatility bucket's beta (vol-matched random hold-2 gross: 16.3 / 27.1 / 9.7 bp vs the rule's ≈26.6 / 46.1 / 17.7), turn negative in OOS for holds ≥ 3, and were chosen after looking. **N=50, hold 2 is the one lead worth a pre-registered re-test.**

## 7. Adversarial self-audit of the positive result

1. **Look-ahead.**
   * rev5 uses closes D−6 and D−1 only.
   * Liquidity uses the 20 sessions before D, and the price filter uses the D−1 close.
   * The universe comes from that day's grouped-daily file, which includes delisted names. Present-day lists are used only in the labelled halal line.
   * Picks with a missing next open would be a survivorship leak, but there were 2 of 10,020; filling them with 0 changes the total by about $10/month.
   * Ties are broken by a seeded random key.
2. **Data artifacts.**
   * The split guard drops 357 rows.
   * The extreme nights were inspected (07-29, 07-30, 01-14, 01-10) and are real multi-name moves.
   * gd close vs the minute-bar last close: median difference 0.0 bp after removing 0.5% cache/gd adjustment mismatches.
3. **Is it just risk?** Partly. The volatility-matched control explains about 45% of the gross excess over the universe (vol-matched 11.4 bp vs universe 5.2 vs rule 18.9). The remaining ~7.5 bp beats that control at p100 / p97 / p80, which is the classic 1-week reversal anomaly (Lehmann 1990, Jegadeesh 1990).
4. **Statistics.** Gross t ≈ 2.3, net t = 0.85 @6 bps. About 50 selector/N combinations were tried, and OOS is only 41 nights. **The net result is not distinguishable from zero.**
5. **Tail dependence.** Ex-top-5 nights is negative in every split at 6 bps, the drawdown is 27% of capital, and the edge disappears at 12 bps.
6. **Bid-ask bounce.** The official close and open are auction prints, so buying "losers at the close" and selling at the open earns bounce only if you actually trade in the auctions. At market-order fills that bounce is part of what the 6–12 bps toll pays for.

## 8. Recommendation

* **Do not deploy capital.** At the measured toll the expectation (+$720 to +$1,439/month, t < 1) is no better than buy-and-hold of the universe and carries a 13–27% drawdown.
* **If the user wants one paper line from this:** a **zero-capital shadow log** of rev5_lo N=20 (picks at 15:50, the closing print, the opening print) **plus** the quoted bid/ask at 15:55 and 09:30 from the broker. Its only purpose is to measure the real round-trip cost on these 20 names. Above about 9 bps/side the line is dead. At ≤ 3 bps/side (auction access through a broker that supports MOC/MOO) it is worth a real pre-registered test, along with the N=50 hold-2 variant.
