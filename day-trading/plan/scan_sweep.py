"""Parse a run_scan MCP dump (spilled or saved) into the compact sweep report,
maintaining day-long NEW/GONE state and drop-lists.

Usage:
    python plan/scan_sweep.py <dump.json> <YYYY-MM-DD> <HH:MM>

Schema (verified live 2026-08-25): data.result.results[] each with ticker,
instrument_type (EQUITY for stocks AND funds -- useless), columns map with
"% Change" (RATIO, always x100), "Last", "Net change", "Name", "Volume".
Fund detection is by NAME only. State in data/paper_days/scan_state_{date}.json.
"""
import json, sys, re
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent
SPAC_PAT = re.compile(r"acquisition|blank.?check|capital investment corp|research alliance", re.I)
# NON-COMMON-STOCK (added 2026-08-31, Day 19). EOSEW "Eos Energy Enterprises,
# Inc. Warrant" crossed +18.2% and reached the candidate list: it is neither a
# fund nor a SPAC, so nothing dropped it, yet C37 eligibility requires COMMON
# STOCK. Warrants/rights/units also break the ranker's assumptions (their
# prev_close and coil are derivative of the underlying, not their own tape).
# Preferreds and notes are included for the same reason, and are additionally
# fixed-income in substance, which is a live halal question of its own.
NONCOMMON_PAT = re.compile(
    r"\bwarrants?\b|\brights?\b|\bunits?\b|\bpreferred\b|\bpfd\b|\bdepositary\b"
    r"|\bdebenture|\bnotes? due\b|\bsubordinated\b"
    # ADRhedged (2026-09-02, Day 21): "Arm Holdings PLC ADRhedged" (ARMH) is a
    # Precidian currency-hedged ADR wrapper product, not the issuer's common
    # stock; it reached the candidate list twice before this pattern existed.
    r"|adrhedged", re.I)
FUND_PAT = re.compile(
    r"ETF|ETN|\bfund\b|\btrust\b|ishares|proshares|direxion|vanguard|invesco|franklin|spdr"
    r"|microsectors|leverage shares|defiance|graniteshares|tradr |corgi |themes|tidal"
    r"|vistashares|webs |21shares|kraneshares|listed funds|ea series|first trust"
    r"|allspring|amplify|virtus|dbx|legg mason|pinnacle focused|\b[23]x\b|ultrashort|yieldboost", re.I)

def main():
    dump, date, hhmm = sys.argv[1:4]

    # STALE-DUMP GUARD (2026-09-01, Day 20). Dumps used to be named
    # scan_dump_{HHMM}.json with no date, so a session could -- and did --
    # sweep the PREVIOUS day's file of the same name and latch four of
    # yesterday's symbols into today's crossed set as NEW. Filenames are
    # date-scoped now, but naming is a convention and conventions slip;
    # this guard is independent of it. A dump last written on a different
    # calendar day than the one being swept is refused outright, because
    # the crossed set is a latch and a phantom entry never self-corrects.
    from datetime import date as _date
    mt = _date.fromtimestamp(Path(dump).stat().st_mtime).isoformat()
    if mt != date:
        print(f"ERROR: REFUSING STALE DUMP. {Path(dump).name} was last "
              f"written {mt} but is being swept as {date}. This is the "
              f"cross-day collision that injected 2026-08-31 symbols into "
              f"2026-09-01's latched crossed set. Re-fetch the scan.")
        return 1

    sp = DIR / "data" / "paper_days" / f"scan_state_{date}.json"
    st = json.load(open(sp)) if sp.exists() else {
        "candidates": {},
        "halal_fail": [], "fake_gap": [], "inherited_fail": [],
        "cannot_verify": [], "spac": []}

    raw = json.load(open(dump, encoding="utf-8"))
    data = raw.get("data", raw)
    res = data.get("result", data)
    rows = res.get("results") or []
    total = res.get("total_items")
    dropped = {k: [] for k in ("fund", "noncommon", "nonequity", "spac", "halal_fail", "fake_gap", "inherited_fail", "cannot_verify")}
    cands, unhealthy = {}, []

    for r in rows:
        cols = r.get("columns") or {}
        sym = (r.get("ticker") or cols.get("Symbol") or "").upper()
        name = str(cols.get("Name") or "")

        # NON-EQUITY ROWS (added 2026-09-01, Day 20). The scan returned UNI
        # "Uniswap" with instrument_type CRYPTO at 07:44. Every other filter
        # here classifies by NAME, and no name regex will ever catch a coin
        # -- but instrument_type does, and unlike the EQUITY value (which is
        # useless because it covers stocks AND funds alike) a non-EQUITY
        # value is decisive. C37 trades COMMON STOCK; a crypto row is not
        # eligible, has no prev_close or coil in the ranker's sense, and
        # cannot be halal-screened as an issuer.
        itype = str(r.get("instrument_type") or "EQUITY").upper()
        if itype != "EQUITY":
            dropped["nonequity"].append(f"{sym} [{itype}]")
            continue
        try:
            pct = float(cols.get("% Change")) * 100.0
            last = float(cols.get("Last"))
        except (TypeError, ValueError):
            unhealthy.append(f"{sym}: unparsable pct/last")
            continue

        if FUND_PAT.search(name):
            dropped["fund"].append(sym); continue
        if NONCOMMON_PAT.search(name):
            dropped["noncommon"].append(f"{sym} {pct:+.1f}%"); continue
        if sym in st["spac"] or SPAC_PAT.search(name):
            if sym not in st["spac"]:
                st["spac"].append(sym)
            dropped["spac"].append(sym); continue
        for lst in ("halal_fail", "fake_gap", "inherited_fail", "cannot_verify"):
            if sym in st[lst]:
                dropped[lst].append(f"{sym} {pct:+.1f}%")
                break
        else:
            prev = round(last / (1 + pct / 100), 4)
            nc = cols.get("Net change")
            if nc not in (None, ""):
                try:
                    prev2 = round(last - float(nc), 4)
                    if prev and abs(prev2 - prev) / prev > 0.01:
                        unhealthy.append(f"{sym}: prev_close mismatch {prev} vs {prev2}")
                    prev = prev2
                except (TypeError, ValueError):
                    pass
            cands[sym] = {"pct": round(pct, 2), "last": last, "prev_close": prev,
                          "vol": cols.get("Volume"), "name": name[:40]}

    prior = set(st["candidates"])
    new = sorted(set(cands) - prior)
    gone = sorted(prior - set(cands))
    for s, d in cands.items():
        d["first_seen"] = st["candidates"].get(s, {}).get("first_seen", hhmm)
        st["candidates"][s] = d
    json.dump(st, open(sp, "w"), indent=1)

    print(f"SWEEP {date} {hhmm}  rows={len(rows)}/{total}  candidates_now={len(cands)}")
    for s, d in sorted(cands.items(), key=lambda kv: -kv[1]["pct"]):
        tag = "  <<< NEW" if s in new else ""
        print(f"  {s:<6} {d['pct']:+8.2f}%  last {d['last']:<9} pc {d['prev_close']:<9} vol {d['vol']} | {d['name']}{tag}")
    print(f"NEW: {new or 'none'}   GONE-from-scan (still latched): {gone or 'none'}")
    drops = "; ".join(f"{k}({len(v)}): {' '.join(str(x) for x in v)}" for k, v in dropped.items() if v and k != "fund")
    print(f"dropped funds={len(dropped['fund'])}; {drops}")
    if unhealthy:
        print("UNHEALTHY: " + " | ".join(unhealthy))
    if len(rows) == 0:
        print("ERROR: scan returned zero rows")

if __name__ == "__main__":
    main()
