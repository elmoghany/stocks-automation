"""Rebuild a run_scan dump from a BASE dump by CARRYING every base row,
applying explicit updates/additions and EXPLICIT drops.
Usage:
    python plan/dump_carry.py BASE.json OUT.json \
        --drop TK [TK ...] --set "TICKER:PCT:LAST[:VOL[:NAME]]" ...
Written 2026-09-02 (Day 21). The saved scan lands in context (~30 KB) when
it does not spill, and ~80 of its ~95 rows are ETFs whose cells are
byte-identical cycle after cycle. dump_from_delta.py requires EVERY
surviving ticker to be re-listed, which is a 95-line transcription per
cycle and a typo surface. This tool inverts the contract: the base rows
survive unless named in --drop, and only rows whose numbers moved (or that
are new) are supplied via --set. The operator therefore owes a FULL ticker
diff (base vs live) for the --drop list -- that diff is the honest part, and
it is printed back so the ledger can show it. A new ticker must carry a
NAME (or be in the day's ticker_names.json registry); the type may be given
as a "!TYPE!" prefix on the name, as in dump_from_delta.
"""
import json
import sys
from pathlib import Path


def main():
    args = sys.argv[1:]
    base_p, out_p = args[0], args[1]
    drops, sets, mode = [], [], None
    for a in args[2:]:
        if a == "--drop":
            mode = "drop"; continue
        if a == "--set":
            mode = "set"; continue
        (drops if mode == "drop" else sets).append(a)
    base = json.load(open(base_p, encoding="utf-8"))
    rows = base["data"]["result"]["results"]
    by_tk = {r["ticker"].upper(): dict(r) for r in rows}
    reg_p = Path(base_p).parent / "ticker_names.json"
    registry = json.load(open(reg_p, encoding="utf-8")) if reg_p.exists() else {}

    drops = {d.upper() for d in drops}
    missing_drops = drops - set(by_tk)
    for d in drops:
        by_tk.pop(d, None)

    updated, added, errors = [], [], []
    for spec in sets:
        parts = spec.split(":")
        if len(parts) < 3:
            errors.append(f"{spec!r}: need TICKER:PCT:LAST"); continue
        tk, pct_s, last_s = parts[0].upper(), parts[1], parts[2]
        vol_s = parts[3] if len(parts) > 3 else "-"
        name = ":".join(parts[4:]) if len(parts) > 4 else None
        prev = by_tk.get(tk)
        itype = (prev or {}).get("instrument_type") or "EQUITY"
        if prev is None:
            if not name and tk in registry:
                name = f"!{registry[tk].get('type', 'EQUITY')}!{registry[tk]['name']}"
            if not name:
                errors.append(f"{tk}: new ticker with no NAME and not in the "
                              f"registry -- refusing to guess"); continue
            added.append(tk)
        else:
            updated.append(tk)
        if name and name.startswith("!"):
            itype, _, name = name[1:].partition("!")
        cols = dict((prev or {}).get("columns") or {})
        cols["Symbol"] = tk
        if name:
            cols["Name"] = name
        cols["% Change"] = repr(float(pct_s) / 100.0)
        cols["Last"] = last_s
        if vol_s != "-":
            cols["Volume"] = vol_s
        by_tk[tk] = {"ticker": tk,
                     "instrument_id": (prev or {}).get("instrument_id", ""),
                     "instrument_type": itype, "columns": cols}
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    out_rows = sorted(by_tk.values(),
                      key=lambda r: -float(r["columns"].get("% Change", 0)))
    json.dump({"data": {"result": {
        "scan_id": base["data"]["result"].get("scan_id", ""),
        "total_items": len(out_rows), "results": out_rows}}},
        open(out_p, "w"), indent=0)
    for r in out_rows:
        nm = r["columns"].get("Name")
        if nm:
            registry.setdefault(r["ticker"], {})["name"] = nm
            registry[r["ticker"]]["type"] = r.get("instrument_type", "EQUITY")
    json.dump(registry, open(reg_p, "w"), indent=0, sort_keys=True)
    print(f"wrote {len(out_rows)} rows -> {Path(out_p).name} "
          f"(base {len(rows)}, dropped {len(drops)}, updated {len(updated)}, "
          f"added {len(added)})")
    print(f"  dropped: {sorted(drops)}")
    if missing_drops:
        print(f"  WARNING: --drop named tickers not in base: {sorted(missing_drops)}")
    print(f"  updated: {updated}")
    if added:
        print(f"  added: {added}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
