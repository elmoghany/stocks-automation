# Stocks Automation

Two trading systems: value-based (main.py) and wave trader (wave_main.py). E*TRADE API + yfinance.

## Critical Rules

- **Never commit** `etrade_python_client/config.ini` (API keys) or anything in `data/`
- `etrade_python_client/` is the original SDK -- never modify it
- LIMIT orders only (no market orders)
- `data/` is gitignored: trades, tokens, state files, logs
- Sandbox keys in env vars: `SANDBOX_API`, `SANDBOX_SECRET_API`
- Production keys in `config.ini`: `CONSUMER_KEY`, `CONSUMER_SECRET`

## Running

```bash
# Value trader (10-min polling, 50 stocks)
python trading/main.py --mode SIM --ignore-market-hours

# Wave trader (60-min polling, top 6 stocks, Never Lose strategy)
python -m trading.wave_main --mode SIM --ignore-hours

# E*TRADE auth (two-phase for Claude Code)
python test_extended_order.py --auth          # Phase 1: browser
python test_extended_order.py --verifier CODE # Phase 2: token
```

## Skills

See `.claude/skills/` for detailed docs on each feature. Key skills:
- `/wave-trader` -- run/manage wave trading system
- `/wave-backtest` -- backtest strategies and recalibrate
- `/weekly-screening` -- Friday re-screening of trading list
- `/halal-check` -- halal compliance (loans, deposits, haram revenue)
- `/place-order` -- manual order via test_extended_order.py
- `/tune-parameter` -- adjust config.py parameters
- `/add-stock` -- add/remove from universe
- `/analyze-trades` -- SIM trade performance analysis
