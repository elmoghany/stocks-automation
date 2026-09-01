"""Rebuild a run_scan dump from a previous dump plus this cycle's deltas.

Usage:
    python plan/dump_from_delta.py BASE.json OUT.json \
        "TICKER:PCT:LAST[:VOL[:NAME]]" ...

WHY. The saved scan returns ~75 rows of which ~61 are leveraged/thematic
ETFs whose cells are byte-identical cycle after cycle (they do not trade
premarket, so their stale %Change never moves). Re-transcribing all of them
by hand each cycle is expensive and -- more importantly -- is a place where
a typo silently changes what the sweep sees. Names are immutable per ticker,
so they are looked up in BASE; only the numbers that actually moved, and any
genuinely new ticker, need to be supplied.

RULES, so this can never quietly invent a row:
  * Every ticker present in OUT must be listed on the command line. A ticker
    in BASE that is not listed is DROPPED (it fell off the scan) -- that is
    the point, and it is what feeds scan_sweep's GONE detection.
  * A ticker not in BASE must supply a NAME, else it is a hard error. The
    name drives fund/SPAC/non-common classification, so guessing one would
    corrupt the drop-lists.
  * PCT is given as a PERCENT (e.g. 60.44) and written back as the ratio the
    scanner emits (0.6044), matching the live schema exactly.
  * VOL may be omitted ("-"), in which case it is carried from BASE and the
    row is flagged in the stderr summary so a stale volume is never mistaken
    for a fresh read.
"""
import json
import sys
from pathlib import Path


def main():
    base_p, out_p, *specs = sys.argv[1:]
    base = json.load(open(base_p, encoding="utf-8"))
    rows = base["data"]["result"]["results"]
    by_tk = {r["ticker"].upper(): r for r in rows}

    # PERSISTENT NAME REGISTRY (2026-09-01, Day 20). Tickers drop off the
    # scan and come back an hour later -- UNI, BMNZ, VACI and CRCD all did
    # it today. Each time, the ticker is absent from the immediately
    # preceding dump and the run aborts asking for a name that WAS supplied
    # earlier in the session. Names are immutable per ticker, so cache them
    # for the day. This never guesses: it only remembers what was already
    # given, and an unseen ticker still hard-fails.
    reg_p = Path(base_p).parent / "ticker_names.json"
    registry = {}
    if reg_p.exists():
        try:
            registry = json.load(open(reg_p, encoding="utf-8"))
        except Exception as e:
            print(f"WARNING: name registry unreadable ({e}) -- continuing "
                  f"without it", file=sys.stderr)
    for tk, r in by_tk.items():
        nm = (r.get("columns") or {}).get("Name")
        if nm:
            registry.setdefault(tk, {})["name"] = nm
            registry[tk]["type"] = r.get("instrument_type", "EQUITY")

    out_rows, carried_vol, new_tk, errors, recalled = [], [], [], [], []
    for spec in specs:
        parts = spec.split(":")
        if len(parts) < 3:
            errors.append(f"{spec!r}: need at least TICKER:PCT:LAST")
            continue
        tk, pct_s, last_s = parts[0].upper(), parts[1], parts[2]
        vol_s = parts[3] if len(parts) > 3 else "-"
        name = ":".join(parts[4:]) if len(parts) > 4 else None

        prev = by_tk.get(tk)
        remembered = registry.get(tk)
        if prev is None and not name and remembered:
            name = f"!{remembered.get('type', 'EQUITY')}!{remembered['name']}"
            recalled.append(tk)
        if prev is None and not name:
            errors.append(f"{tk}: not in base dump, not in the day's name "
                          f"registry, and no NAME supplied -- refusing to "
                          f"guess (name drives fund/SPAC/non-common "
                          f"classification)")
            continue
        if prev is None and tk not in recalled:
            new_tk.append(tk)

        # instrument_type is carried from the base, or taken from a
        # "!TYPE!" prefix on the name for a new row. It must NOT be
        # hardcoded to EQUITY: scan_sweep drops non-EQUITY rows (the
        # 2026-09-01 UNI/Uniswap CRYPTO case), and silently relabelling a
        # coin as EQUITY here would walk it straight past that guard.
        itype = (prev or {}).get("instrument_type") or "EQUITY"
        if name and name.startswith("!"):
            itype, _, name = name[1:].partition("!")

        cols = dict((prev or {}).get("columns") or {})
        cols["Symbol"] = tk
        if name:
            cols["Name"] = name
        cols["% Change"] = repr(float(pct_s) / 100.0)
        cols["Last"] = last_s
        if vol_s == "-":
            if prev:
                carried_vol.append(tk)
        else:
            cols["Volume"] = vol_s
        out_rows.append({"ticker": tk,
                         "instrument_id": (prev or {}).get("instrument_id", ""),
                         "instrument_type": itype,
                         "columns": cols})

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    json.dump({"data": {"result": {
        "scan_id": base["data"]["result"].get("scan_id", ""),
        "total_items": len(out_rows),
        "results": out_rows}}}, open(out_p, "w"), indent=0)

    for r in out_rows:
        nm = (r.get("columns") or {}).get("Name")
        if nm:
            registry.setdefault(r["ticker"], {})["name"] = nm
            registry[r["ticker"]]["type"] = r.get("instrument_type", "EQUITY")
    json.dump(registry, open(reg_p, "w"), indent=0, sort_keys=True)

    dropped = sorted(set(by_tk) - {r["ticker"] for r in out_rows})
    print(f"wrote {len(out_rows)} rows -> {Path(out_p).name}")
    if new_tk:
        print(f"  NEW tickers (name supplied): {new_tk}")
    if recalled:
        print(f"  name recalled from the day's registry (returned to the "
              f"scan after dropping off): {recalled}")
    if dropped:
        print(f"  dropped (off the scan): {dropped}")
    if carried_vol:
        print(f"  NOTE volume carried from base (not a fresh read) for "
              f"{len(carried_vol)} rows: {carried_vol[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
