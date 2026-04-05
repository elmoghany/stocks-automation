---
description: Check halal compliance for stocks using the 3 financial criteria
---

## Halal Compliance Definition

A stock is halal if it passes ALL 3 criteria:

### 1. Interest-Bearing Loans (Debt / Market Cap)
- **Individual limit:** <= 10%
- Calculated as: Total Debt / Market Capitalization
- Source: Quarterly balance sheet → "Total Debt" line item

### 2. Interest-Bearing Deposits (Cash / Market Cap)
- **Individual limit:** <= 10%
- Calculated as: (Cash + Cash Equivalents + Short Term Investments) / Market Capitalization
- Source: Quarterly balance sheet → "Cash Cash Equivalents And Short Term Investments" line item

### 3. Combined Interest Rule
- **Combined limit:** <= 20%
- Loans% + Deposits% combined must be <= 20%
- Example: 12% loans + 2% deposits = 14% combined → HALAL (under 20%)
- Example: 15% loans + 8% deposits = 23% combined → HARAM (over 20%)
- This allows flexibility: one can be above 10% if the other compensates

### 4. Haram Revenue (Unlawful Income / Total Revenue)
- **Limit:** < 5%
- Includes: interest income, alcohol, pork, gambling, tobacco, weapons, adult entertainment, conventional financial services
- Calculated as: Interest Income / (Quarterly Revenue × 4)
- Source: Quarterly income statement → "Interest Income" or "Net Interest Income" / "Total Revenue"
- Most non-financial companies have 0-1% haram revenue from bank interest on cash holdings

## How to Check

```bash
# Quick check from yfinance quarterly statements
python -c "
import yfinance as yf
t = yf.Ticker('AMD')
bs = t.quarterly_balance_sheet
inc = t.quarterly_income_stmt
info = t.info
# Pull: Total Debt, Cash+Inv, Interest Income, Total Revenue, Market Cap
# Calculate ratios and compare to thresholds
"
```

## Steps

1. Pull latest quarterly balance sheet and income statement
2. Get current market cap from live quote
3. Calculate:
   - Loans% = Total Debt / Market Cap × 100
   - Deposits% = Cash+Investments / Market Cap × 100
   - Combined% = Loans% + Deposits%
   - Haram% = Interest Income / (Quarterly Revenue × 4) × 100
4. Check:
   - Loans% <= 10% OR combined <= 20% → PASS
   - Deposits% <= 10% OR combined <= 20% → PASS
   - Haram% < 5% → PASS
5. Also verify the company is not in a haram industry (banking, alcohol, gambling, pork, weapons, adult entertainment)

## Re-check Frequency

- Run quarterly after each earnings report
- Also check if a stock's market cap drops significantly (ratios increase when mcap drops)
