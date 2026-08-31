"""Mutate the day's paper ledger JSON from the command line.

Written 2026-08-31 (Day 19). Rewriting the whole day file by hand on every
cycle is how a ledger silently loses an earlier entry; this makes each write a
read-modify-write of ONE path instead.

Usage:
    python plan/dayjson.py <date> append <dotted.path> <json-value>
    python plan/dayjson.py <date> set    <dotted.path> <json-value>
    python plan/dayjson.py <date> show   [<dotted.path>]

<json-value> is parsed as JSON; pass it as a single argument. Intermediate keys
are created as dicts. `append` requires the target to be a list (or absent).
"""
import json, sys
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "data" / "paper_days"


def dig(obj, parts, create=False):
    for p in parts:
        if p not in obj:
            if not create:
                sys.exit(f"ERROR: path segment {p!r} not found")
            obj[p] = {}
        obj = obj[p]
    return obj


def main():
    date, op, *rest = sys.argv[1:]
    path = D / f"{date}.json"
    doc = json.load(open(path, encoding="utf-8"))

    if op == "show":
        node = dig(doc, rest[0].split(".")) if rest else doc
        print(json.dumps(node, indent=1)[:4000])
        return

    # PowerShell strips the inner double quotes out of a single-quoted argument,
    # so inline JSON on the command line is not survivable on this box (the
    # windows-shell-quirks lesson again). Prefer @file.
    raw = rest[1]
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text(encoding="utf-8")
    dotted, value = rest[0], json.loads(raw)
    parts = dotted.split(".")
    parent = dig(doc, parts[:-1], create=True)
    key = parts[-1]

    if op == "append":
        parent.setdefault(key, [])
        if not isinstance(parent[key], list):
            sys.exit(f"ERROR: {dotted} is {type(parent[key]).__name__}, not a list")
        parent[key].append(value)
        print(f"appended to {dotted} (now {len(parent[key])} items)")
    elif op == "set":
        parent[key] = value
        print(f"set {dotted}")
    else:
        sys.exit(f"ERROR: unknown op {op!r}")

    json.dump(doc, open(path, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
