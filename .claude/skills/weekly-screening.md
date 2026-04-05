---
description: Run weekly trading list re-screening every Friday before market open
---

Weekly re-screening of the trading list. Updates scores for all PASS and top FAIL stocks.

## Stocks to Screen

PASS list (current 21):
LRCX, TSM, VRT, AMSC, AMD, LLY, ANET, FIX, TDW, TJX, MLI, RMD, HUBB, ETN, CDNS, DECK, AWI, ISRG, CTAS, BMI, FICO

FAIL list (watch for recovery):
JBL, ROST, PH, LMB, COST, ARM, MPWR, MANH, SHW, CEG

## Steps

1. **Fetch fresh data** for all PASS + top FAIL stocks using yfinance:
   - earningsGrowth, revenueGrowth, profitMargins, returnOnEquity
   - averageVolume
   - totalDebt, marketCap (for debt/mcap halal check)
   - totalCash (for cash/mcap halal check, must be < 30%)
   - operatingCashflow, netIncomeToCommon (for EQ = OCF/NI)
   - 5Y/3Y/1Y/6M price returns from history
   - YoY debt change from balance_sheet (for DT)

2. **Fetch SPY 1Y return** for relative strength benchmark.

3. **Recalculate scores** using the 10-metric formula (raw 0-115, normalized to 0-100):
   ```
   Raw = EG(20) + PM(14) + ROE(13) + VAL(11) + RG(12) + PERF(13) + VOL(9) + EQ(7) + DT(8) + RS(8)
   Score = Raw / 1.15
   ```
   Use the bracket tables defined in `plan/trading-list.md`.
   Calculation script: `plan/calc_scores.py`

4. **Check for status changes:**
   - Any PASS stock where EG turned negative? → Flag for potential downgrade
   - Any FAIL stock where EG turned strongly positive (>10%) with PM >10%? → Flag for potential upgrade
   - **Halal check** (see `/halal-check` skill for full definition):
     - Loans/MCap > 10% AND combined (loans+deposits) > 20%? → Flag halal violation
     - Cash/MCap > 10% AND combined > 20%? → Flag halal violation
     - Haram revenue (interest income / revenue) >= 5%? → Flag halal violation

5. **Present results as a comparison table:**
   ```
   | Stock | Last Score | New Score | Change | Alert |
   ```
   Only show stocks where score changed by more than 5 points, or where pass/fail status changed.

6. **Update `plan/trading-list.md`** with new scores if any material changes occurred (score change > 5 or status change).

7. **Earnings calendar check:** Flag any PASS stocks reporting earnings in the coming week. Earnings can cause sudden score changes.

## Do NOT

- Do not add new stocks to the list (user will provide new tickers separately)
- Do not remove stocks for Israel ties (already done)
- Do not change the scoring formula or brackets
