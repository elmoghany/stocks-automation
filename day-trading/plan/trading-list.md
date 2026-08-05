# Trading List

**Date:** 2026-04-03
**Method:** Halal compliance (loans/mcap <= 10%, cash/mcap <= 10%, combined <= 20%, haram revenue < 5%)
**Criteria:** Halal compliant + no financing companies + no haram revenue + no strong Israel ties + strong financials + strong earnings
**Tiers:** Tier 1 = investments to watch list (200B+), Tier 2-4 = smaller cap tiers

---

## Score Calculation

Raw score 0-115, normalized to 0-100 by dividing by 1.15.

### Formula

```
Raw = EG + PM + ROE + VAL + RG + PERF + VOL + EQ + DT + RS
     (0-20)(0-14)(0-13)(0-11)(0-12)(0-13)(0-9)(0-7)(0-8)(0-8) = 0-115

Score = Raw / 1.15  (normalized to 0-100)
```

### Metrics

| Metric | Max | Weight | What it measures |
|--------|-----|--------|------------------|
| **EG** | 20 | 17.4% | Earnings Growth -- are profits growing? |
| **PM** | 14 | 12.2% | Profit Margin -- business quality |
| **ROE** | 13 | 11.3% | Return on Equity -- capital efficiency |
| **VAL** | 11 | 9.6% | PEG Ratio -- are you overpaying for growth? |
| **RG** | 12 | 10.4% | Revenue Growth -- demand momentum |
| **PERF** | 13 | 11.3% | Price Performance (5Y/3Y/1Y/6M) -- proven track record |
| **VOL** | 9 | 7.8% | Avg Daily Volume -- can you trade it? |
| **EQ** | 7 | 6.1% | Earnings Quality (OCF/NI) -- are earnings real cash? |
| **DT** | 8 | 7.0% | Debt Trend -- is leverage improving or worsening? |
| **RS** | 8 | 7.0% | Relative Strength -- beating or losing to S&P 500? |

### Scoring Brackets

#### EG (max 20) -- Earnings Growth

| > 50% | > 20% | > 10% | > 5% | > 0% | > -10% | <= -10% |
|-------|-------|-------|------|------|--------|---------|
| 20 | 16 | 13 | 10 | 6 | 3 | 0 |

#### PM (max 14) -- Profit Margin

| > 30% | > 20% | > 15% | > 10% | > 5% | <= 5% |
|-------|-------|-------|-------|------|-------|
| 14 | 11 | 8 | 6 | 3 | 0 |

#### ROE (max 13) -- Return on Equity

| > 50% | > 30% | > 20% | > 10% | > 5% | <= 5% |
|-------|-------|-------|-------|------|-------|
| 13 | 10 | 8 | 5 | 3 | 0 |

#### VAL (max 11) -- PEG Ratio (PE / EG%)

| < 0.5 | < 1.0 | < 1.5 | < 2.0 | < 3.0 | >= 3.0 |
|-------|-------|-------|-------|-------|--------|
| 11 | 9 | 6 | 4 | 2 | 0 |

#### RG (max 12) -- Revenue Growth

| > 20% | > 10% | > 5% | > 0% | <= 0% |
|-------|-------|------|------|-------|
| 12 | 9 | 6 | 3 | 0 |

#### PERF (max 13) -- Price Performance

| Period | Top | Mid | Low | > 0% | <= 0% |
|--------|-----|-----|-----|------|-------|
| 5Y | > 200%: 4 | > 100%: 3 | > 50%: 2 | > 0%: 1 | 0 |
| 3Y | > 100%: 3 | > 50%: 2 | > 25%: 1 | | 0 |
| 1Y | > 50%: 3 | > 25%: 2 | > 0%: 1 | | 0 |
| 6M | > 25%: 3 | > 10%: 2 | > 0%: 1 | | 0 |

#### VOL (max 9) -- Average Daily Volume

| > 10M | > 5M | > 2M | > 1M | > 500K | > 100K | <= 100K |
|-------|------|------|------|--------|--------|---------|
| 9 | 7 | 5 | 4 | 3 | 2 | 0 |

#### EQ (max 7) -- Earnings Quality (OCF / Net Income)

| >= 1.5 | >= 1.2 | >= 1.0 | >= 0.8 | < 0.8 |
|--------|--------|--------|--------|-------|
| 7 | 5 | 3 | 1 | 0 |

#### DT (max 8) -- Debt Trend (YoY debt change)

| <= -10% | <= -5% | <= 0% | <= +5% | <= +10% | > +10% |
|---------|--------|-------|--------|---------|--------|
| 8 | 6 | 5 | 3 | 1 | 0 |

#### RS (max 8) -- Relative Strength (Stock 1Y return minus SPY 1Y return)

SPY 1Y benchmark: +14.3%

| > +60% | > +40% | > +20% | > 0% | > -15% | <= -15% |
|--------|--------|--------|------|--------|---------|
| 8 | 7 | 5 | 3 | 1 | 0 |

---

## PASS (21 stocks)

| # | Stock | Mkt | Tier | PE | PEG | EQ | DT | RS vs SPY | 6M | 1Y | 3Y | 5Y | Score |
|---|-------|-----|------|----|-----|----|----|-----------|----|----|----|----|------:|
| 1 | **LRCX** | Tech | T1 | 41.0 | 1.11 | 1.15 | -10% | +163% | +53% | +177% | +310% | +254% | 89 |
| 2 | **TSM** | Tech | T1 | 29.9 | 0.86 | 1.32 | +2% | +79% | +17% | +94% | +257% | +191% | 84 |
| 3 | **VRT** | Tech | T2 | 68.7 | 0.34 | 1.59 | +3% | +210% | +64% | +216% | +1695% | +1077% | 84 |
| 4 | **AMSC** | Energy | T4 | 11.0 | 0.00 | 0.15 | +24% | +63% | -47% | +72% | +684% | +70% | 76 |
| 5 | **AMD** | Tech | T1 | 75.3 | 0.35 | 1.81 | +74% | +76% | +22% | +90% | +100% | +150% | 76 |
| 6 | **LLY** | HC | T1 | 38.6 | 0.75 | 0.81 | +26% | -6% | +22% | +9% | +170% | +399% | 74 |
| 7 | **ANET** | Tech | T2 | 42.2 | 2.21 | 1.25 | -22% | +36% | -19% | +49% | +175% | +516% | 74 |
| 8 | **FIX** | Ind | T3 | 44.1 | 0.34 | 1.16 | +57% | +282% | +59% | +294% | +834% | +1641% | 74 |
| 9 | **TDW** | Energy | T4 | 27.6 | 0.05 | 1.13 | +7% | +79% | +52% | +88% | +102% | +554% | 68 |
| 10 | **TJX** | Ind | -- | 34.4 | 1.22 | 1.25 | +2% | +15% | +9% | +33% | +117% | +153% | 62 |
| 11 | **MLI** | Ind | T3 | 15.7 | 1.13 | 0.99 | -19% | +29% | +8% | +42% | +212% | +458% | 57 |
| 12 | **RMD** | HC | T3 | 21.8 | 1.50 | 1.29 | -2% | -15% | -18% | +1% | +7% | +18% | 53 |
| 13 | **HUBB** | Ind | T3 | 28.3 | 2.05 | 1.16 | +45% | +30% | +11% | +44% | +113% | +174% | 53 |
| 14 | **ETN** | Ind | -- | 32.9 | 1.74 | 1.09 | +7% | +13% | -6% | +27% | +118% | +169% | 52 |
| 15 | **CDNS** | Tech | T2 | 66.8 | 4.57 | 1.56 | +1% | -8% | -22% | +6% | +32% | +98% | 50 |
| 16 | **DECK** | Ind | T3 | 13.4 | 1.22 | 0.97 | +4% | -29% | -8% | -15% | +29% | +72% | 48 |
| 17 | **AWI** | Ind | T4 | 22.6 | 3.32 | 1.15 | -18% | -0% | -17% | +15% | +142% | +86% | 48 |
| 18 | **ISRG** | HC | T2 | 57.5 | 3.46 | 1.06 | N/A | -23% | +3% | -8% | +77% | +84% | 46 |
| 19 | **CTAS** | Ind | T2 | 36.5 | 3.76 | 1.14 | -0% | -32% | -17% | -16% | +59% | +107% | 44 |
| 20 | **BMI** | Ind | T4 | 30.9 | 3.22 | 1.30 | N/A | -36% | -16% | -22% | +29% | +65% | 39 |
| 21 | **FICO** | Tech | T3 | 38.8 | 5.04 | 1.15 | +38% | -57% | -31% | -43% | +52% | +116% | 37 |

---

## FAIL - Weak/Declining Earnings or Thin Margins (34 stocks)

| # | Stock | Mkt | Tier | PE | PEG | EQ | DT | RS | 6M | 1Y | 3Y | 5Y | Score | Fail Reason |
|---|-------|-----|------|----|-----|----|----|----|----|----|----|-----|------:|-------------|
| 22 | JBL | Tech | T3 | 33.1 | 0.34 | 2.14 | +3% | +68% | +16% | +82% | +199% | +383% | 78 | **PM 2.5%** |
| 23 | ROST | Ind | T2 | 32.1 | 2.80 | 1.41 | -1% | +51% | +38% | +68% | +113% | +84% | 61 | **PM 9.4%** |
| 24 | PH | Ind | T2 | N/A | N/A | 1.06 | -12% | +29% | +15% | +45% | +178% | +192% | 47 | **EG -9%** |
| 25 | LMB | Ind | T4 | N/A | N/A | 1.17 | +15% | -10% | -18% | +2% | +383% | +633% | 46 | **PM 6%** |
| 26 | COST | Ind | T1 | 45.3 | 3.26 | 1.76 | +0% | -8% | +9% | +8% | +110% | +199% | 46 | **PM 3%** |
| 27 | FTDR | Ind | T4 | N/A | N/A | 1.63 | -2% | +21% | -22% | +37% | +97% | -3% | 45 | **EG -84%** |
| 28 | MPWR | Tech | T3 | N/A | N/A | 1.35 | +54% | +60% | +13% | +74% | +111% | N/A | 44 | **EG -86.2%** |
| 29 | ARM | Tech | T2 | 183.8 | N/A | 1.90 | +58% | +14% | -2% | +27% | +115% | +115% | 43 | **EG -12.3%** |
| 30 | BKE | Ind | T4 | N/A | N/A | N/A | +3% | +26% | -10% | +42% | +86% | +112% | 41 | **EG +3.5%** |
| 31 | MANH | Tech | T4 | 63.0 | N/A | 1.77 | +18% | -39% | -37% | -25% | -11% | +11% | 41 | **EG 0%** |
| 32 | TT | Ind | T2 | N/A | N/A | 1.08 | -3% | +6% | -2% | +23% | +129% | +160% | 41 | **EG -0.5%** |
| 33 | DOCS | HC | T4 | N/A | N/A | 1.32 | -15% | -73% | -68% | -59% | -27% | -55% | 40 | **EG -16.2%** |
| 34 | IR | Ind | T3 | N/A | N/A | 2.33 | +1% | -18% | -7% | -3% | +40% | +57% | 40 | **PM 7.6%** |
| 35 | MLM | Ind | T3 | N/A | N/A | 1.80 | -2% | +6% | -7% | +21% | +73% | +76% | 39 | **EG -4.1%** |
| 36 | WMT | Ind | -- | N/A | N/A | 1.90 | +12% | +28% | +20% | +46% | +170% | +191% | 39 | **EG -19%** |
| 37 | AIT | Ind | T4 | N/A | N/A | 1.21 | -4% | +1% | +0% | +15% | +99% | +197% | 39 | **EG +5%** |
| 38 | SHW | Ind | T2 | N/A | N/A | 1.34 | +9% | -23% | -8% | -6% | +54% | +34% | 38 | **EG +1.4%** |
| 39 | CEG | Energy | T2 | N/A | N/A | 1.83 | +7% | +34% | -10% | +46% | +316% | +636% | 38 | **EG -48.9%** |
| 40 | PODD | HC | T3 | N/A | N/A | 2.30 | -31% | -35% | -33% | -20% | -33% | -20% | 38 | **EG +3.9%** |
| 41 | REGN | HC | T2 | N/A | N/A | 1.11 | +0% | +4% | +34% | +18% | -8% | +59% | 37 | **EG -2.6%** |
| 42 | GWW | Ind | T3 | N/A | N/A | 1.18 | -10% | -6% | +12% | +9% | +64% | +178% | 36 | **EG -2%** |
| 43 | ONTO | Tech | T4 | N/A | N/A | 2.40 | +15% | +42% | +45% | +55% | +121% | +188% | 36 | **EG -78.2%** |
| 44 | PNR | Ind | T3 | N/A | N/A | 1.25 | -0% | -17% | -23% | -2% | +68% | +44% | 34 | **EG +1.6%** |
| 45 | SNPS | Tech | T2 | N/A | N/A | 2.21 | +1988% | -25% | -20% | -12% | +2% | +55% | 30 | **EG -82%** |
| 46 | TSCO | Ind | T3 | N/A | N/A | 1.49 | +10% | -30% | -19% | -14% | +5% | +39% | 29 | **EG -2.2%** |
| 47 | SHOO | Ind | T4 | N/A | N/A | 3.63 | +218% | +11% | -3% | +26% | +0% | -2% | 27 | **EG -31.7%** |
| 48 | EXP | Ind | T4 | N/A | N/A | 1.34 | +14% | -32% | -22% | -18% | +32% | +39% | 24 | **EG -9.6%** |
| 49 | IOT | Tech | T3 | N/A | N/A | -25.9 | -9% | -34% | -18% | -21% | +69% | +24% | 24 | **Not profitable** |
| 50 | LII | Ind | T3 | N/A | N/A | 0.94 | +19% | -34% | -14% | -19% | +88% | N/A | 23 | **EG -17.9%** |
| 51 | PHM | Ind | T3 | N/A | N/A | 0.84 | +2% | -3% | -14% | +13% | +105% | +128% | 23 | **EG -42.1%** |
| 52 | AAON | Ind | T4 | N/A | N/A | 0.00 | +148% | -14% | -14% | +1% | +30% | +72% | 22 | **EG -68.6%** |
| 53 | SWVL | Tech | -- | N/A | N/A | 0.66 | -28% | -82% | -55% | -66% | +18% | -99% | 20 | **Not profitable** |
| 54 | TGLS | Ind | T4 | N/A | N/A | 0.85 | +57% | -54% | -37% | -39% | +16% | N/A | 19 | **EG -43.1%** |
| 55 | WSO | Ind | T3 | N/A | N/A | 1.23 | +7% | -44% | -11% | -28% | +26% | +54% | 17 | **EG -26%** |

---

## REMOVED - Israel Ties (15 stocks)

| Stock | Market | Tier | Reason for Removal |
|-------|--------|------|-------------------|
| NVDA | Tech | Tier 1 | 5,000+ employees, 7 R&D centers, Mellanox HQ, building 10,000-person campus |
| AAPL | Tech | Tier 1 | 2,000 engineers (Herzliya, Haifa, Jerusalem), multiple Israeli acquisitions |
| AMAT | Tech | Tier 1 | 2,200+ employees, largest R&D center outside US (Rehovot) |
| DELL | Tech | Tier 2 | 1,200+ employees, 4 R&D centers (Herzliya, Haifa, Beersheba), 200+ patents |
| AVGO | Tech | Tier 1 | Hundreds of employees, 8 centers across Israel, Israeli-registered subsidiary |
| KLAC | Tech | Tier 2 | Major R&D and manufacturing hub in Migdal HaEmek |
| MSI | Tech | Tier 2 | In Israel since 1964, R&D since 1972, supplies equipment to Israeli police/military |
| PANW | Tech | Tier 2 | ~1,500 employees, founded by Israeli (ex-Unit 8200), most products developed in Israel |
| TSLA | Tech | Tier 1 | R&D office in Israel, sales operations, FSD trial approved 2026 |
| CAT | Industrials | Tier 1 | D9 armored bulldozers to IDF, $295M sale approved Feb 2025 + financing arm |
| AXON | Tech | Tier 3 | ~1,800 Tasers sold to Israeli police, used by IDF and prison service |
| APP | Tech | Tier 2 | Acquired Israeli SafeDK, development center in Herzliya |
| NOW | Tech | Tier 2 | Acquired Israeli Armis for $7.75B (~950 employees), plus 3 other Israeli acquisitions |
| NTAP | Tech | Tier 3 | ~300 employees, Tel Aviv cloud center, acquired 4 Israeli companies ($800M+) |
| ADI | Tech | Tier 2 | Ships components to Elbit Systems (major IDF weapons supplier) |

## REMOVED - Haram Revenue (1 stock)

| Stock | Market | Tier | Reason |
|-------|--------|------|--------|
| MCO | Industrials | Tier 2 | Rates conventional debt/bonds (interest-based instruments) |

---

## NOTES

- TSM debt/mcap corrected via web sources (yfinance TWD/USD bug). Real: $34B / $1.64T = 2.1%.
- Stocks marked `--` in Tier = not assigned (TJX, ETN, WMT, SWVL, ISRG).
- Pass/fail is qualitative + score. Needs positive EG + PM > 5% to pass.
- EQ: AMSC (0.15) = turnaround risk, only 15% of earnings backed by cash.
- RS benchmarked against SPY 1Y return of +14.3%.
- Score calculation script: `plan/calc_scores.py`

---

## Summary

- **Total screened:** 55 stocks (16 removed)
- **PASS:** 21
- **FAIL:** 34
- **Removed (Israel ties):** 15
- **Removed (haram revenue):** 1 (MCO)
- **Top 5:** LRCX (89), TSM (84), VRT (84), AMSC (76), AMD (76)

### By Tier

| Tier | Total | Pass | Fail | Pass Rate |
|------|-------|------|------|-----------|
| Tier 1 (200B+) | 5 | 4 | 1 | 80% |
| Tier 2 | 9 | 5 | 4 | 56% |
| Tier 3 | 18 | 7 | 11 | 39% |
| Tier 4 | 13 | 4 | 9 | 31% |
| Unassigned | 4 | 3 | 1 | 75% |
