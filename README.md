# stocks-automation

Halal trading research monorepo -- three strategy books plus shared
utilities. Hard rules everywhere: halal screen (loans/mcap <=10%,
deposits <=10%, combined <=20%, haram revenue <5%, no haram industry),
no shorting, max $15k at risk.

## Layout

- `day-trading/` -- penny-gapper same-day momentum book (champion
  config C23: entries 7AM-noon, exits to 1PM ET; backtests Y1 +$413k /
  Y2 +$580k on $15k, zero negative months).
  `day-trading.py` engine + `plan/` experiment harness (X001-X343,
  C01-C22) + `data/paper/` daily paper-session records with per-gate
  decisions and same-day news snapshots.
- `earnings-trading/` -- earnings-reaction book (ET01-ET31): dip-buys
  after the report, pre-earnings timing sweeps, gated variants (beat +
  5y-strong + profitable + volume-pressure). Verdict so far: the edge,
  if any, is AFTER the news; buying before earnings loses at every
  entry hour.
- `bollinger-trading/` -- the original buy-low / sell-high wave+value
  system (E*TRADE API client, sector rotation, wave indicators).
  Predates the other two books.
- `shared/` -- cross-book utilities: Windows Credential Manager access
  (`win_cred.py`), throttled Massive/Polygon fetcher (`massive.py`).

Run day-trading tools as `python day-trading/day-trading.py <cmd>`
(data paths are anchored to the script). Experiment registries:
`day-trading/CONFIGS-TESTED.md`, notes in
`day-trading/NOTES-DAYTRADING.md` and `earnings-trading` sections
therein.
