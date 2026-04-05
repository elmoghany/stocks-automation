# Order Commands Summary

All commands run from the project root:
```
cd D:/mydata-2026/stocks-projects/stocks-automation
```

---

## Authentication

### First-time login (browser required)
Runs automatically when no saved session exists. A browser opens, you authorize,
and the token is saved to `data/.etrade_access_token.pkl` for future use.

```bash
python test_extended_order.py
```

### Two-phase login (for running through Claude Code)
Use this when Claude is placing the order on your behalf.

**Step 1** — open browser and save request token:
```bash
python test_extended_order.py --auth
```

**Step 2** — exchange the verifier code you got from the browser:
```bash
python test_extended_order.py --verifier YOUR_CODE --session REGULAR --account 0 --confirm
```

### Reuse saved session (no login needed)
After the first login, the access token is saved automatically.
All subsequent orders skip the browser entirely until the token expires.

---

## Placing Orders

### Default — Extended hours, -$5 below market, account 0, asks for confirmation
```bash
python test_extended_order.py
```

### Regular hours BUY (interactive confirmation)
```bash
python test_extended_order.py --session REGULAR
```

### Extended hours BUY (interactive confirmation)
```bash
python test_extended_order.py --session EXTENDED
```

### Skip confirmation prompt (auto-confirm)
```bash
python test_extended_order.py --session REGULAR --confirm
python test_extended_order.py --session EXTENDED --confirm
```

### Select a specific account (0 = first account, 1 = second, etc.)
```bash
python test_extended_order.py --session REGULAR --account 1 --confirm
```

---

## Changing Symbol, Quantity, or Price Offset

Edit the constants at the top of `test_extended_order.py`:

```python
SYMBOL       = "AMD"   # change to any ticker, e.g. "NVDA", "TSLA"
QUANTITY     = 1       # number of shares
PRICE_OFFSET = 5.00    # dollars below current market price
```

Examples:
- Buy 5 shares of NVDA at -$3 → set `SYMBOL="NVDA"`, `QUANTITY=5`, `PRICE_OFFSET=3.00`
- Buy AMD at -$10 → set `PRICE_OFFSET=10.00`

---

## Cancelling Orders

Cancel by order ID (replace `1722` with the actual order ID):

```python
# Run inline via python -c or in a script
from trading.api_wrapper import ETradeSession
etrade = ETradeSession(sandbox=False)
etrade._load_saved_token()
account = etrade.get_account_list()[0]
result = etrade.cancel_order(account, 1722)
print(result)
```

Or as a one-liner from the terminal:
```bash
python -c "
from trading.api_wrapper import ETradeSession
e = ETradeSession(sandbox=False); e._load_saved_token()
a = e.get_account_list()[0]
import json; print(json.dumps(e.cancel_order(a, 1722), indent=2))
"
```

---

## Session Types

| Session    | Hours (ET)          | Notes                              |
|------------|---------------------|------------------------------------|
| `REGULAR`  | 9:30 AM – 4:00 PM   | Standard market hours              |
| `EXTENDED` | 7:00 AM – 8:00 PM   | Pre/post market, LIMIT orders only |

- Extended hours only accepts `GOOD_FOR_DAY` limit orders
- If extended hours is closed, E*TRADE returns error 1513

---

## Order History (this session)

| Order ID | Symbol | Limit   | Offset | Session  | Status    |
|----------|--------|---------|--------|----------|-----------|
| 1722     | AMD    | $198.68 | -$4    | REGULAR  | Cancelled |
| 1723     | AMD    | $197.68 | -$5    | REGULAR  | Open      |
| 1724     | AMD    | $197.68 | -$5    | REGULAR  | Open      |
| 1725     | AMD    | $197.68 | -$5    | EXTENDED | Open      |
