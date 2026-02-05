"""All tunable parameters and configuration for the trading system."""

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_INI_PATH = os.path.join(BASE_DIR, "etrade_python_client", "config.ini")

TRADES_FILE = os.path.join(DATA_DIR, "trades.json")
WASH_SALE_FILE = os.path.join(DATA_DIR, "wash_sale_list.json")
PORTFOLIO_STATE_FILE = os.path.join(DATA_DIR, "portfolio_state.json")

# ---------------------------------------------------------------------------
# E*TRADE API
# ---------------------------------------------------------------------------
SANDBOX_BASE_URL = "https://apisb.etrade.com"
PROD_BASE_URL = "https://api.etrade.com"
ETRADE_AUTH_BASE = "https://api.etrade.com"
ETRADE_AUTHORIZE_URL = "https://us.etrade.com/e/t/etws/authorize?key={}&token={}"

QUOTE_BATCH_SIZE = 25  # max symbols per quote API call

# ---------------------------------------------------------------------------
# Polling / Timing
# ---------------------------------------------------------------------------
POLL_INTERVAL_SECONDS = 600  # 10 minutes
TOKEN_RENEW_MINUTES = 90     # renew access token every 90 min
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0

# ---------------------------------------------------------------------------
# Value Scoring Weights (must sum to 1.0)
# ---------------------------------------------------------------------------
SCORE_WEIGHT_PE = 0.25
SCORE_WEIGHT_EPS_GROWTH = 0.25
SCORE_WEIGHT_REVENUE_GROWTH = 0.15
SCORE_WEIGHT_PROFIT_MARGIN = 0.10
SCORE_WEIGHT_DEBT_EQUITY = 0.10
SCORE_WEIGHT_FAIR_VALUE_GAP = 0.15

FUNDAMENTAL_GATE_THRESHOLD = 40  # minimum value score to buy

# ---------------------------------------------------------------------------
# Trading Window
# ---------------------------------------------------------------------------
WINDOW_LOOKBACK_DAYS = 60
WINDOW_HALF_WIDTH = 0.05  # +/- 5% around median = 10% window

# Window position thresholds
STRONG_BUY_THRESHOLD = 0.20
BUY_THRESHOLD = 0.35
SELL_THRESHOLD = 0.65
STRONG_SELL_THRESHOLD = 0.80

# ---------------------------------------------------------------------------
# Sector Rotation
# ---------------------------------------------------------------------------
SECTOR_PERF_PERIOD_DAYS = 60
SECTOR_MIN_ALLOCATION = 0.15  # 15%
SECTOR_MAX_ALLOCATION = 0.55  # 55%

# ---------------------------------------------------------------------------
# Portfolio / Risk
# ---------------------------------------------------------------------------
MAX_POSITIONS = 20
MAX_POSITION_PCT = 0.05     # 5% of portfolio per stock
WASH_SALE_LOSS_THRESHOLD = 100.0  # minimum loss ($) to trigger wash sale rule
WASH_SALE_BLOCK_DAYS = 30

# ---------------------------------------------------------------------------
# Signal Generator
# ---------------------------------------------------------------------------
BUY_SCORE_THRESHOLD = 60
STRONG_BUY_SCORE_THRESHOLD = 70
SELL_SCORE_THRESHOLD = 50    # sell when value weakens below this
COLLAPSE_SCORE_THRESHOLD = 30  # sell regardless of window if score < this

# ---------------------------------------------------------------------------
# Historical Data
# ---------------------------------------------------------------------------
HISTORICAL_PERIOD = "1y"  # yfinance period for historical data
