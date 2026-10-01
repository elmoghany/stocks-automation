# LEGACY-12 — size / price / float buckets on honest trades

**Question.** The old era (C34/C35/Z104/C37) tuned price bands ($2–14, $2–16, "no ceiling"), float caps and market-cap ranges. On HONEST trades, which buckets of entry price, causal size and prior liquidity still carry an edge after a spread-scaled cost, in both years?

**Answer in one line.** None, once the tail is set aside. **R4's whole gross P&L comes from 5 legs** (+$79,304 of +$79,625 per $10k notional). Those 5 legs are all thin names: dvol60 < $1M, priced $2–10. Without them every bucket is about zero or negative after costs, in all three samples.

What survives is a cost fact and a tail fact, not a bucket edge:
- **Cost fact:** thin names cost about 3× more per side.
- **Tail fact:** R4's coil ranking with no stop picks up the rare +50% legs in thin names about 4–7× more often than random picks do. The stops and trails in C37F-hf3 remove those legs entirely.

## Data and method (all causal)

| sample | source | n legs |
|---|---|---:|
| CHAMPION-REPLAY **R4** (coil rank, no stop, causal live-scanner universe, 444 sessions 2024-10-22..2026-07-31) | `plan/pa_out/cp_r4_legs.json` + per-leg evidence cost `cp_r4_evid.json` | 965 |
| **RND30**: the same machinery with random ranking, 30 seeds. This is a zero-skill picker in the same gapper universe. | same files | ~2,050 per seed |
| **C37F-hf3**: the live rules, honest ledger | `data/massive/rotation_trades_C37F_hf3.json` | 1,839 |

- **Features:** all known before the open, except entry price.
  - `dvol60` = median dollar volume over the prior 60 grouped-daily sessions, from `data/massive/cp_prior`.
  - `pdv` = prior-session dollar volume, from `data/massive/gd`.
  - `rvol1` = pdv / dvol60.
  - `nhist` = listing-age proxy.
  - PIT `shares` from `data/pt_shares/{sym}_{date}.json`, and `mcap` = shares × previous close. The present-day `rh_fundamentals` fallback is **not** used, because it leaks (OPEN-UNIVERSE).
  - PIT shares cover only **235/965** R4 legs (100% of hf3). Read R4 size buckets as small-n.
- **P&L:** each leg is normalised to **$10k notional** (gross = return × $10k). Months = 444/21 = 21.1. Y1 runs up to 2025-08-01.
- **Cost:** scaled per leg and per bucket.
  - "evid" is R4's own fill-specific cost: CS/AR half-spread at the fill minute, plus 4.4 bps impact before 10:30 or 3.1 after. Mean 28.75 bps/side. PESSIMISM-AUDIT treats it as the upper side.
  - **"central" = 0.65 × evid** (mean ≈ 18.7 bps/side for R4, inside the 12–18 band for gappers).
  - hf3 legs get the dvol60-bucket mean evid cost from the R4 + RND pool.
  - Evid cost by dvol60 bucket (bps/side, mean / median): **< $1M 44.3 / 34.8 · $1–5M 25.5 / 18.9 · $5–20M 18.7 / 14.2 · $20–100M 15.3 / 12.6 · ≥ $100M 13.5 / 11.6**.
  - Evid cost by price bucket is much flatter (25.6–34.9). **Liquidity, not price, sets the spread.**
- **Scripts:** `plan/lm12_buckets.py` (bucket tables → `lm12_out.log/json`), `lm12_filters.py` (post-hoc filters, controls, month bootstrap), `lm12_robust.py` (winsorised ±$500 and R4 ex-top-5), `lm12_liq.py` (liquidity floor and tail rates).

## Findings

### 1. R4 is a lottery in thin $2–10 names

R4's top-5 legs (per $10k):

| date | symbol | gross | price bucket | dvol60 | rvol1 |
|---|---|---:|---|---|---:|
| 2024-10-24 | MNPR | +21.4k | $5–10 | < $1M | 1.98 |
| 2024-12-09 | HUIZ | +7.9k | $2–5 | < $1M | 3.87 |
| 2025-01-27 | YIBO | +28.7k | $2–5 | < $1M | 3.13 |
| 2025-10-22 | ARMP | +9.3k | $5–10 | < $1M | 1.70 |
| 2025-12-01 | FLYE | +12.0k | $5–10 | < $1M | 0.04 |

- Excluding these 5 legs, R4 averages **+$0.33 per ticket gross**.
- Every "both years positive" bucket in the raw table is carried by them:
  - price $5–10: gross +196 (Y1 +163 / Y2 +230)
  - dvol60 < $1M: +154 (Y1 +185 / Y2 +124)
  - shares < 10M: +442
  - mcap < $50M: +513
- Ex-top-5 and winsorised at ±$500 (±5%), each of these flips:
  - price $5–10 → −11 (Y1 −32 / Y2 +11)
  - dvol60 < $1M → −27 (Y1 −44 / Y2 −11)
  - mcap < $50M → −48

### 2. Price bands are not an edge, only a spread proxy

Winsorised gross per $10k by price bucket:

| price | R4 ex-5 | RND30 | hf3 |
|---|---:|---:|---:|
| $2–5 | −43.5 | −2.4 | −21.4 |
| $5–10 | −10.7 | +0.4 | +13.2 |
| $10–20 | −11.5 | +1.5 | −1.5 |
| $20–50 | −6.9 | +8.4 | +19.9 |
| $50+ | +9.9 | −0.1 | −42.3 |

- No bucket is positive in all three samples and both years.
- At central cost, every price bucket is negative for every sample. The least negative is hf3 at $20–50: −11 net (Y1 −21 / Y2 −4).
- $2–5 is the worst for the body of the distribution. It is also where the lottery tail lives.

### 3. Size (PIT shares, causal mcap) adds nothing

- RND30 winsorised gross is between −2 and +17 in every mcap bucket.
- hf3 shows no monotone pattern, and its signs flip between years. Examples: shares < 10M is Y1 −78 / Y2 +146; mcap $50–300M is Y1 +62 / Y2 −50.
- R4 size cells have n = 2–90.
- This independently confirms OPEN-UNIVERSE: once membership is causal, **market cap adds nothing beyond liquidity**. The old float caps had nothing to find.

### 4. Liquidity removes the cost bleed but not the zero-skill drift

Results with a liquidity floor applied:

| rule | sample | legs/day | gross/tkt (Y1 / Y2) | net/tkt at central (Y1 / Y2) | $/month |
|---|---|---:|---|---|---:|
| dvol60 < $1M (thin) | RND30 | 1.14 | −5.9 (−21.7 / +9.1) | **−63.8** at 28.9 bps | |
| dvol60 ≥ $5M | RND30 | 0.99 | −2.0 (−8.8 / +1.2) | **−23.1** at 10.6 bps; −14.0 at 6 bps | |
| dvol60 ≥ $20M | RND30 | 0.60 | −0.8 | −19.8; −12.8 at 6 bps | |
| dvol60 ≥ $20M | R4 | 0.27 | +43 (**−9.2 / +74.6**) | +24.7 | +$143 |
| dvol60 ≥ $20M | hf3 | 1.30 | −2.0 (+21.9 / −11.7) | −20.9 | −$567 |

- A ≥ $5M floor cuts a zero-skill picker's loss by about **$40 per $10k ticket**, almost all of it spread.
- Liquid gappers still have **zero gross drift**, so nothing becomes positive without a real signal.
- **No liquid bucket is positive in both years for any sample.**

### 5. The real asymmetry is the tail, and it lives only in thin names

Legs ≥ +50% of ticket, per 1,000 legs:

| dvol60 bucket | sample | Y1 | Y2 |
|---|---|---:|---:|
| < $1M | R4 | **18.7** (5 of 267; ~0.7 expected at the random rate, P ≈ 0.0006) | **10.6** (3 of 283; ~1.25 expected, P ≈ 0.13) |
| < $1M | RND30 | 2.6 | 4.4 |
| < $1M | **hf3** | 2.4 | **0.0** |
| ≥ $1M | any sample | ≈ 0 (one +25% leg in RND per ~1,000) | ≈ 0 |

- hf3 is −8% stop / trail machinery, and it **erases the right tail**.
- CHAMPION-REPLAY already shows the same thing: removing the stop (R1 → R4) was worth +$37/ticket at flat 10.
- Break-even arithmetic for a thin-name lottery:
  - The body is −$37/ticket net (R4 thin, ex-top-5, central cost).
  - The average tail win is ≈ +$15.9k per $10k.
  - So break-even needs about **1 tail leg per 430 tickets**.
  - R4 achieved 1 per 69. Random achieves 1 per 230–380.

### 6. Post-hoc filters that look good but are tail artefacts

These are in-sample, so do not adopt them.

- **drop dvol60 $1–5M**: R4 gross +120 (Y1 +142 / Y2 +103), net at central **+$3,025/mo**, z +4.65 against seeds with the same filter, month-bootstrap P = 0.999.
  - It works only by concentrating weight on the thin tail bucket.
  - Winsorised RND30 in $1–5M is **+2.1**, so it is not a bad bucket.
- **keep rvol1 in [0.5, 5]**: R4 +$3,515/mo, but hf3 gets worse (−26.6 vs −19.1 gross).
- **price $5–10 only**: +$1,450/mo, all of it MNPR, ARMP and FLYE.
- **nhist < 60** (new listings): R4 gross +189, but Y1 +431 / Y2 **+1**.

What is robustly bad in all three samples and both years (winsorised):
- prior-session dollar volume < $1M: R4 −44 / −50, RND −27 / −19, hf3 −49 / −43. Net −82 to −103 at central.
- rvol1 < 0.5 (yesterday under half its 60-day median): R4 −130 / −90, RND −46 / −19, hf3 −78 / −46.

Both describe names with the widest spreads and no follow-through. Both are valid **vetoes** for any non-lottery gapper line.

## TAKEAWAYS

### 1. Liquidity veto for any "grind" gapper line (cost hygiene, not alpha)

**Rule:** skip a candidate if `dvol60 < $5M` (median $ volume over the prior 60 sessions), or `pdv < $1M`, or `pdv / dvol60 < 0.5`. All three are known pre-open.

**Expected effect at $10k tickets:**
- Moves a zero-skill picker from −$64 to −$23 per ticket at central cost. That is about **+$40/ticket saved**, ≈ +$900/month at 1 ticket/day of avoided bleed.
- It does **not** make anything positive by itself.
- It is worth having in the live paper code for any rule whose edge is measured on the body of the distribution rather than the tail.

**Test:** re-run `cp_sim` R4 and the 30 seeds with the veto applied **inside the universe**, so freed slots are refilled rather than dropped as they were in this post-hoc analysis. Price each leg at evid cost. Gate: same or better percentile versus seeds and lower per-leg cost, in both years.

### 2. Thin-name tail capture, as a deliberate small-ticket lottery

**Rule:** among `dvol60 < $1M` gappers on the live scanner, take the coil-ranked top name. Use **no fixed stop, no tight trail, no take-profit cap**: bearish-pattern exit or the 15:55 flatten, as in R4.

**Expected value at $10k tickets:**
- In sample: +$107/ticket net at central cost, **+$2,788/month** at 1.24 tickets/day.
- The body is −$37/ticket. The edge exists only if the ≥ +50% tail rate stays ≳ 1 per 400 tickets (in sample it was 1 per 69; random is 1 per 230–380).
- Honest prior: break-even to modest, with very lumpy months. Five legs carried 22 months.

**Test:** count ≥ +50% legs per 1,000 for R4-thin against RND30-thin on the **OOS dates** (`cp_run.dates(oos=True)`) and on any further forward paper. The pass condition is the tail rate, not $/month. Pass if R4-thin ≥ 2× random **and** ≥ 1 per 400.

### 3. Never put a stop or trail on thin names

This applies to any line that trades gappers with `dvol60 < $1M`.
- In this sample, hf3's stop/trail cut the ≥ +50% tail from 2.6–4.4 per 1,000 (random, no stop) to 2.4 in Y1 and **0** in Y2.
- The ≤ −15% tail is also 0, but the body still loses (−9 gross, −67 net at central).

**Expected value:** this is the R1 → R4 delta, **+$37/ticket** at flat 10 (CHAMPION-REPLAY).

**Test:** a `cp_sim` A/B of R4 with and without the −8% stop, split by dvol60 < $1M versus ≥ $1M. The prediction is that the stop costs money only in the thin bucket.

## DISCARD

- **Market-cap and float/share-count buckets.** No causal pattern in any sample. PIT coverage is thin for R4, and the present-day snapshot leaks. The old float caps and "low-float runner" filters have nothing to find.
- **Price bands as an edge** ($2–14, $2–16, $5–10, "drop $10–50"). Price is a spread proxy, and every price "edge" is the 5 tail legs.
- **Excluding the dvol60 $1–5M "dead zone"**. +$3k/month in sample is tail concentration; the random bucket is flat.
- **rvol1 band filters** beyond the < 0.5 veto (hf3 contradicts), and **new-listing (nhist < 60)** preference (Y1 only).
- **Any $/month figure from R4 or its buckets that includes MNPR / YIBO / FLYE / ARMP / HUIZ** without a tail-rate argument.
