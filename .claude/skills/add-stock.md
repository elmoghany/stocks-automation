---
description: Add or remove a stock symbol from the trading universe
---

All symbols are defined in `trading/universe.py` in three lists: TECH, ENERGY, MINERALS. Lists are ordered roughly by market cap (largest first), not alphabetically.

Steps:
1. Confirm the ticker symbol and sector (Tech, Energy, Minerals). If removing, find which list it's in.
2. Read `trading/universe.py`.
3. For additions:
   - Add to the correct sector list. Place it by approximate market cap relative to existing entries (largest first). If unsure, append to end.
   - Verify the symbol isn't already in another sector list.
4. For removals:
   - Remove from its sector list.
   - Warn if the sector would drop below 5 stocks.
5. Run `python -m py_compile trading/universe.py`.
6. Run `python -c "from trading.universe import ALL_SYMBOLS, SECTORS; print(f'Total: {len(ALL_SYMBOLS)}'); [print(f'  {k}: {len(v)}') for k,v in SECTORS.items()]"` to show updated counts.
