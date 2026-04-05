---
description: Place a manual stock order via test_extended_order.py
---

This uses `test_extended_order.py` to place a LIMIT BUY order. The script has constants at the top: SYMBOL, QUANTITY, PRICE_OFFSET (dollars below market price).

Steps:
1. Ask for: symbol, quantity, price offset, session type (REGULAR or EXTENDED, default EXTENDED), and account index (default 0) -- if not already provided.
2. Read the top of `test_extended_order.py` to see current SYMBOL, QUANTITY, PRICE_OFFSET values.
3. Update those constants to the requested values.
4. Show: "Will place a LIMIT BUY for {QTY} x {SYMBOL} at market minus ${OFFSET} on account {INDEX} during {SESSION} hours."
5. Ask the user for confirmation before running.
6. Check if a saved token exists (`data/.etrade_access_token_prod.pkl`). If yes, run directly:
   ```
   python test_extended_order.py --session {SESSION} --account {INDEX} --confirm
   ```
   If no saved token, tell the user to run the two-phase auth first:
   ```
   ! python test_extended_order.py --auth
   ```
   Then after they provide the verifier code:
   ```
   python test_extended_order.py --verifier CODE --session {SESSION} --account {INDEX} --confirm
   ```
7. Report the result (order ID, limit price, status).
