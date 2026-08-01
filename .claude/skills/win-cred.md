---
description: Manage E*TRADE API keys in Windows Credential Manager via trading/win_cred.py
---

API keys are stored in the Windows Credential Manager (DPAPI-encrypted, per-user),
NOT in env vars or config files. Zero-dependency module: `trading/win_cred.py`
(stdlib ctypes only, no pip packages).

Stored secret names (prefix `stocks-automation/` inside Credential Manager):
- `ETRADE_PROD_KEY` / `ETRADE_PROD_SECRET`
- `ETRADE_SANDBOX_KEY` / `ETRADE_SANDBOX_SECRET`

## How the code gets keys

`trading.api_wrapper.resolve_consumer_keys(sandbox)` resolves in this order:
1. Windows Credential Manager (via `trading.win_cred.get_secret`)
2. Env vars `SANDBOX_API` / `SANDBOX_SECRET_API` (sandbox only)
3. `etrade_python_client/config.ini` (`CONSUMER_KEY` / `CONSUMER_SECRET`)

Both `ETradeSession` and `test_extended_order.py` use this — no manual key
handling needed anywhere.

## CLI usage

```bash
python -m trading.win_cred list                 # show stored names
python -m trading.win_cred get ETRADE_PROD_KEY  # print a value
python -m trading.win_cred set NEW_NAME         # prompts for value (keeps it out of shell history)
python -m trading.win_cred delete NAME
```

From Python:
```python
from trading.win_cred import get_secret, set_secret
key = get_secret("ETRADE_SANDBOX_KEY")
```

## Rules

- NEVER write key values into repo files, commit messages, or logs.
- When the user pastes a new key, store it with `set_secret` and redact the
  pasted value from any file it landed in.
- If a key rotates, just `set` again — it overwrites in place.
- Secrets are per-Windows-user: they do not survive OS reinstalls or transfer
  to other machines. Re-add them there with `set`.
- To inspect manually: Control Panel → Credential Manager → Windows Credentials
  → entries under `stocks-automation/`.
