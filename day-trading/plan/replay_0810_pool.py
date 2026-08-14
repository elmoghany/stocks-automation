"""Build the mini gappers pool + backfill m1 bars for the four live paper
days 2026-08-10..13, so plan/rotation_sim.py can be replayed over exactly
the days we paper-traded.

UNIVERSE = the paper ledgers, not a fresh discovery run. Every ticker-like
token in data/paper_days/{date}.{json,md} is collected, then kept only if
Polygon's daily bar for that date shows a real +10% DAY-HIGH cross over the
prior session's close with close >= $2 (the live scanner's filters: Last>$2,
%Change>0.10). That keeps the ledger as the source of truth for who crossed
and drops prose words that happen to be tickers but did not gap.

gain_pct is the DAY-HIGH gain -- computed the same way as the existing
data/massive/gappers_novol_*.json files, for shape compatibility. Under
C37H (causal_pool=True) gain_pct is NOT used to select the pool; it is
carried only so the record matches the other pool files.

2026-08-13 is not in Polygon's free tier yet (403, next-day), so that day is
built from data/rh_bars/*_2026-08-13.csv (Robinhood MCP pulls) with
prev_close taken from Polygon's 2026-08-12 daily close.

Writes data/massive/gappers_novol_replay0813.json and m1 CSVs.
Usage: python plan/replay_0810_pool.py [--build-pool] [--fetch]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent))

M1 = ROOT / "data/massive/m1"
RH = ROOT / "data/rh_bars"
PD = ROOT / "data/paper_days"
POOL_F = ROOT / "data/massive/gappers_novol_replay0813.json"
CACHE = ROOT / "data/massive/replay0813_grouped"

DAYS = ["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13"]
PREV = {"2026-08-10": "2026-08-07", "2026-08-11": "2026-08-10",
        "2026-08-12": "2026-08-11", "2026-08-13": "2026-08-12"}
TOK = re.compile(r"[A-Z]{2,5}(?:\.[A-Z])?")


def grouped(date):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{date}.json"
    if f.exists():
        return json.loads(f.read_text())
    from shared import massive
    g = massive.grouped_daily(date)
    f.write_text(json.dumps(g))
    return g


def ledger_tokens(date):
    acc = set()

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            acc.update(TOK.findall(o))
    walk(json.loads((PD / f"{date}.json").read_text(encoding="utf-8")))
    acc.update(TOK.findall((PD / f"{date}.md").read_text(encoding="utf-8")))
    return acc


def build_pool():
    out = []
    for date in DAYS:
        toks = ledger_tokens(date)
        prv = {r["T"]: r for r in grouped(PREV[date])}
        if date == "2026-08-13":
            # Polygon has no same-day free-tier data; use the Robinhood
            # minute bars already ingested for this date.
            import pandas as pd
            rows = []
            for sym in sorted(toks):
                f = RH / f"{sym}_{date}.csv"
                q = prv.get(sym)
                if not f.exists() or not q or q["c"] <= 0:
                    continue
                df = pd.read_csv(f)
                if df.empty:
                    continue
                pc = q["c"]
                hi, cl = float(df["high"].max()), float(df["close"].iloc[-1])
                if (hi / pc - 1) * 100 < 10 or cl < 2:
                    continue
                rows.append(dict(symbol=sym, date=date,
                                 gain_pct=round((hi / pc - 1) * 100, 1),
                                 prev_close=round(pc, 4), rvol=None,
                                 rvol30=None, band=True,
                                 open=float(df["open"].iloc[0]), high=hi,
                                 close=cl, volume=int(df["volume"].sum()),
                                 hist_n=99, src="rh_bars"))
            out += rows
        else:
            cur = {r["T"]: r for r in grouped(date)}
            for sym in sorted(toks):
                c, q = cur.get(sym), prv.get(sym)
                if not c or not q or q["c"] <= 0:
                    continue
                pc = q["c"]
                if (c["h"] / pc - 1) * 100 < 10 or c["c"] < 2:
                    continue
                out.append(dict(symbol=sym, date=date,
                                gain_pct=round((c["h"] / pc - 1) * 100, 1),
                                prev_close=round(pc, 4), rvol=None,
                                rvol30=None, band=True, open=c["o"],
                                high=c["h"], close=c["c"],
                                volume=int(c["v"]), hist_n=99,
                                src="polygon_grouped"))
    POOL_F.write_text(json.dumps(out, indent=1))
    for d in DAYS:
        print(f"  {d}: {sum(1 for c in out if c['date'] == d)} crossers")
    print(f"wrote {POOL_F} ({len(out)} rows)")
    return out


def fetch_bars():
    """Massive 1-min bars for 08-10..12; RH CSVs converted for 08-13."""
    import pandas as pd
    from shared import massive
    pool = json.loads(POOL_F.read_text())
    M1.mkdir(parents=True, exist_ok=True)
    todo = [(c["symbol"], c["date"]) for c in pool
            if not (M1 / f"{c['symbol']}_{c['date']}.csv").exists()]
    # PRIORITY: names on the live halal_list first. Only those can ever be
    # PICKED, so partial coverage still gives a faithful pick sequence; the
    # rest only affect rank-0 occupancy (and thus the 35% calm-gap grace).
    # This is an ORDERING, not a filter -- the tail is still fetched.
    hl = set(json.loads((ROOT / "data/halal_list.json").read_text())["symbols"])
    todo.sort(key=lambda x: (x[1] == "2026-08-13", x[0] not in hl, x[1], x[0]))
    print(f"{len(todo)} symbol-days to fetch "
          f"({sum(1 for s, _ in todo if s in hl)} on the halal list first)",
          flush=True)
    got = empty = rh = 0
    for i, (sym, date) in enumerate(todo, 1):
        f = M1 / f"{sym}_{date}.csv"
        try:
            if date == "2026-08-13":
                src = RH / f"{sym}_{date}.csv"
                if not src.exists():
                    f.write_text("EMPTY")
                    empty += 1
                    continue
                df = pd.read_csv(src)
                df["begins_at"] = pd.to_datetime(df["begins_at"], utc=True)
                df = (df.rename(columns={"open": "Open", "high": "High",
                                         "low": "Low", "close": "Close",
                                         "volume": "Volume"})
                        .set_index("begins_at").sort_index())
                df[["Open", "High", "Low", "Close", "Volume"]].to_csv(f)
                rh += 1
                continue
            df = massive.minute_bars(sym, date)
            if df is None or df.empty:
                f.write_text("EMPTY")
                empty += 1
                continue
            o = df.reset_index()
            o["begins_at"] = o["begins_at"].dt.tz_convert("UTC")
            o.to_csv(f, index=False)
            got += 1
        except Exception as e:
            print(f"ERROR {sym} {date}: {e}", flush=True)
        if i % 20 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] massive={got} rh={rh} empty={empty}",
                  flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or "--build-pool" in a:
        build_pool()
    if "--fetch" in a:
        fetch_bars()
