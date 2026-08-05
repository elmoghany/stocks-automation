# Value-Based Stock Trading System - System Architecture

## Overview
Automated value trading system built on the existing E*TRADE Python client. Two modes: SIM (paper trading) and REAL (live). Polls every 10 minutes, uses fundamentals + price windows + sector rotation to decide buy/sell.

---

## Directory Structure
```
stocks-automation/
  etrade_python_client/          # UNTOUCHED
  etrade_api_documentation/      # UNTOUCHED
  trading/                       # ALL NEW CODE
    __init__.py
    config.py                    # All tunable parameters
    universe.py                  # 50 stocks in 3 sectors
    api_wrapper.py               # Programmatic E*TRADE API access (no input())
    data_pipeline.py             # yfinance historical + E*TRADE live quotes
    value_scorer.py              # Fundamental scoring (0-100)
    trading_window.py            # 10% price window calculator
    sector_rotation.py           # Inverse sector allocation
    signal_generator.py          # Combines all signals into buy/sell decisions
    order_executor.py            # SIM (JSON log) vs REAL (API orders)
    risk_manager.py              # Wash sale tracker + T+1 settlement
    portfolio_tracker.py         # Track holdings, cash, state
    main.py                      # Entry point + 10-min polling loop
  data/                          # Runtime state (gitignored)
    trades.json
    wash_sale_list.json
    portfolio_state.json
  requirements.txt               # UPDATED with new deps
```

---

## Stock Universe (50 stocks, 3 sectors)

**Tech (17):** AAPL, MSFT, GOOGL, AMZN, NVDA, META, AVGO, CRM, ADBE, AMD, INTC, CSCO, ORCL, TXN, QCOM, IBM, MU

**Energy (17):** XOM, CVX, COP, SLB, EOG, MPC, PSX, VLO, OXY, HAL, DVN, FANG, HES, BKR, KMI, WMB, OKE

**Minerals/Gold (16):** NEM, GOLD, FNV, WPM, AEM, GFI, KGC, AU, RGLD, AGI, FCX, SCCO, TECK, BHP, RIO, NUE

---

## Implementation Steps (build order)

### Step 1: `config.py` + `universe.py`
- All constants: thresholds, intervals, file paths, mode selection
- Stock lists with sector mapping and reverse lookup dict
- No dependencies, pure data

### Step 2: `api_wrapper.py`
- `ETradeSession` class wrapping OAuth1 auth (reuses `rauth` + `config.ini`)
- Programmatic methods: `authenticate()`, `renew_token()`, `get_account_list()`, `get_balance()`, `get_portfolio()`
- Calls same endpoints as existing client but without `input()` prompts
- Key existing code reference: `etrade_python_client/etrade_python_client.py` (OAuth flow), `accounts/accounts.py` (API URLs)

### Step 3: `data_pipeline.py`
- `fetch_historical(symbol)` - yfinance 1-year daily OHLCV
- `fetch_fundamentals_yf(symbol)` - PE, EPS growth, revenue growth, margins, debt/equity, analyst target, price-to-book
- `fetch_live_quotes(session, base_url, symbols)` - E*TRADE quote API, batched 25 at a time, `detailFlag=ALL`
- `parse_etrade_quote()` - Extract last_price, bid, ask, eps, pe, beta, market_cap, high52, low52
- `merge_fundamentals()` - Combine yfinance (growth metrics) + E*TRADE (real-time prices)

### Step 4: `value_scorer.py`
- `compute_value_score(fundamentals)` returns 0-100 score
- 6 components, weighted:
  - PE Ratio (25%) - lower is better, bracket scoring
  - EPS Growth (25%) - higher is better
  - Revenue Growth (15%) - higher is better
  - Profit Margin (10%) - higher is better
  - Debt/Equity (10%) - lower is better
  - Fair Value Gap (15%) - distance below analyst target
- `passes_fundamental_gate(score)` - must be >= 40 to buy
- Missing data defaults to neutral score (50)

### Step 5: `trading_window.py`
- `compute_trading_window(historical_df, lookback=60)` - median center +/- 5% = 10% window
- Returns: center, upper, lower, current_position (0.0-1.0), z_score, volatility
- `get_window_signal(window)` - position thresholds:
  - < 0.20 = STRONG_BUY, < 0.35 = BUY, 0.35-0.65 = HOLD, > 0.65 = SELL, > 0.80 = STRONG_SELL

### Step 6: `sector_rotation.py`
- `compute_sector_performance(symbols, historical, period=60)` - average return per sector
- `compute_sector_allocations(performances)` - inverse performance weighting
- Worst-performing sector gets highest allocation (buy low thesis)
- Clamped to 15%-55% per sector

### Step 7: `risk_manager.py`
- **WashSaleTracker**: If selling at $100+ loss, block symbol for 30 days. JSON persisted.
- **SettlementTracker**: T+1 tracking. Sold today = cash available tomorrow. Subtracts pending from available cash.
- **get_flags(symbol, portfolio)**: Returns wash_sale_blocked, max_positions_reached flags

### Step 8: `portfolio_tracker.py`
- `PortfolioTracker` class with holdings dict, cash, total value
- `sync_from_api()` - pulls real positions from E*TRADE portfolio endpoint
- `sync_from_sim()` - builds state from trade log JSON
- JSON persisted to `data/portfolio_state.json`

### Step 9: `order_executor.py`
- **SimExecutor**: Logs trades to `data/trades.json` with timestamp, action, symbol, qty, price, reason
- **RealExecutor**: Preview then place using E*TRADE API. LIMIT orders only. XML payloads matching existing `order/order.py` pattern exactly.
- `compute_position_size()` - budget per sector allocation, cap at 5% of portfolio per stock

### Step 10: `signal_generator.py`
- `generate_signal(symbol, value_score, window, allocation, is_held, risk_flags)` returns (Action, reason)
- Decision rules:
  1. Fundamental gate: score < 40 = never buy
  2. Wash sale blocked = no buy
  3. Max 20 positions = no buy
  4. BUY: value >= 60 AND window in buy zone
  5. STRONG_BUY: value >= 70 AND window in strong buy zone
  6. SELL: window in sell zone AND value weakening (< 50), OR fundamentals collapsed (< 30)
- `generate_all_signals()` - runs all 50 stocks, returns sorted by priority

### Step 11: `main.py`
- Parse args: `--mode SIM|REAL`, `--sandbox`
- OAuth authenticate, select account
- Fetch yfinance historical data once on startup
- **10-minute polling loop:**
  1. Renew token if 90+ min since last renew
  2. Skip if market closed (9:30 AM - 4:00 PM ET, weekdays)
  3. Fetch live quotes (2 API calls for 50 symbols)
  4. Score all stocks (value scorer)
  5. Compute windows (trading window)
  6. Compute sector allocations (sector rotation)
  7. Generate signals (signal generator)
  8. Execute buy/sell (order executor)
  9. Sync portfolio state
  10. Sleep until next cycle
- Graceful shutdown on Ctrl+C

### Step 12: Update `requirements.txt` + `.gitignore`
- Add: `yfinance`, `pandas`, `numpy`, `scipy`, `pytz`
- Add `data/` to `.gitignore`

---

## Key Design Decisions
- **No modification of existing code** - api_wrapper replicates the same HTTP calls programmatically
- **LIMIT orders only** - avoid slippage in automated trading
- **JSON state files** - simple, inspectable, no database
- **Conservative defaults** - fundamental gate at 40, must be BOTH cheap AND healthy to buy
- **yfinance for fundamentals** - richer data (growth, margins, analyst targets) than E*TRADE quotes alone
- **Token auto-renewal** every 90 min; at midnight ET, pauses until user re-authenticates

---

## Verification Plan
1. Run in SIM + sandbox mode first: `python trading/main.py --mode SIM --sandbox`
2. Verify historical data fetches for all 50 symbols
3. Verify value scores produce sensible 0-100 scores
4. Verify window calculations with known price data
5. Verify sector rotation shifts allocations correctly
6. Verify SIM trades log to `data/trades.json`
7. Test wash sale: simulate $100+ loss sell, confirm 30-day block
8. Test T+1: sell and confirm cash unavailable until next day
9. Test REAL mode in sandbox: verify preview + place order flow
10. Monitor full 10-min cycle end-to-end in SIM mode
