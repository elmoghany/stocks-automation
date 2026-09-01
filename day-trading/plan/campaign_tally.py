"""Sum the paper campaign's realised P&L across every day file.

Usage:  python plan/campaign_tally.py

SCOPE WARNING (2026-09-01). This reads data/paper_days/YYYY-MM-DD.json only,
and the earliest such file is 2026-08-10. Sessions before that were scored
under the older data/paper/ path and are NOT counted here, so this total is
NOT the campaign cumulative and must not be quoted as one. The authoritative
running figure is the cumulative_after recorded in the most recent day file
(Day 19: -720.82 over 16 scored days).

What this IS good for: verifying the chain. Its running sum through
2026-08-13 reproduces that file's own cumulative_after of -257.57 exactly,
which is how the per-day key mapping below was validated.

Reads data/paper_days/*.json, skipping obvious non-session artefacts
(BLOCKED-SKELETON and the like), and reports per-day P&L, the traded-day
count and the running total. Traded days are the denominator that the
$1,517 benchmark and the -$163 honest baseline are both quoted against, so
an ops-failure day with counts_as_traded_day=false must not dilute it.
"""
import json
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "paper_days"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def main():
    rows = []
    for p in sorted(DIR.glob("*.json")):
        if not DATE_RE.match(p.name):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print(f"  !! {p.name}: unreadable ({e})")
            continue
        # Earlier sessions wrote `pnl` as a dict (e.g. {realised:..., ...})
        # rather than a number. Prefer a scalar; otherwise dig for a
        # realised/total key; otherwise sum the trades.
        # Every session so far has named the day's P&L differently --
        # pnl (number), pnl.realized_usd, pnl.day_usd, pnl.gross_usd -- and
        # trades use pnl or pnl_usd. Try the known scalar keys in order,
        # then fall back to summing the trades. Anything still unresolved is
        # reported as UNKNOWN rather than silently counted as zero, because
        # a zero here would quietly flatter the cumulative.
        DAY_KEYS = ("realized_usd", "realised_usd", "day_usd", "gross_usd",
                    "net_usd", "total_usd", "realized", "total", "net")
        TRADE_KEYS = ("pnl_usd", "pnl", "realized_usd")
        pnl = d.get("pnl")
        if isinstance(pnl, dict):
            pnl = next((pnl[k] for k in DAY_KEYS
                        if isinstance(pnl.get(k), (int, float))), None)
        if not isinstance(pnl, (int, float)):
            trades = d.get("trades") or []
            vals = [next((t[k] for k in TRADE_KEYS
                          if isinstance(t.get(k), (int, float))), None)
                    for t in trades]
            pnl = sum(v for v in vals if v is not None) if trades else 0.0
            if trades and any(v is None for v in vals):
                print(f"  !! {p.name}: some trades have no recognisable "
                      f"P&L key -- day total may be understated")
        traded = d.get("counts_as_traded_day")
        if traded is None:
            traded = bool(d.get("trades"))
        rows.append((p.stem, float(pnl), bool(traded), len(d.get("trades") or [])))

    total = sum(r[1] for r in rows)
    traded_days = sum(1 for r in rows if r[2])
    print(f"{'date':<12} {'pnl':>10}  {'traded':>6}  tickets")
    for date, pnl, traded, n in rows:
        print(f"{date:<12} {pnl:>10.2f}  {str(traded):>6}  {n}")
    print("-" * 40)
    print(f"days on file      {len(rows)}")
    print(f"traded days       {traded_days}")
    print(f"cumulative P&L    ${total:,.2f}")
    if traded_days:
        print(f"per traded day    ${total / traded_days:,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
