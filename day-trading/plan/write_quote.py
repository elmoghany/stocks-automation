"""write_quote.py SYM BID ASK TS_UTC [DATE]

Writes data/paper/quotes_{DATE}.json ({SYM: {bid, ask, ts}}) for the
paper_watch.py ladder (QUOTE_STALE_S = 90). DATE defaults to today ET.
Exists because PowerShell 5.1 strips the inner double quotes of an inline
python -c JSON literal.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main(argv):
    sym, bid, ask, ts = argv[0].upper(), float(argv[1]), float(argv[2]), argv[3]
    day = argv[4] if len(argv) > 4 else datetime.now(
        ZoneInfo("America/New_York")).date().isoformat()
    path = Path(__file__).resolve().parent.parent / "data" / "paper" / f"quotes_{day}.json"
    doc = {}
    if path.exists():
        try:
            doc = json.loads(path.read_text(encoding="utf-8")) or {}
        except Exception:
            doc = {}
    doc[sym] = {"bid": bid, "ask": ask, "ts": ts}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc), encoding="utf-8")
    tmp.replace(path)
    print(f"quote {sym} bid {bid} ask {ask} ts {ts} -> {path.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
