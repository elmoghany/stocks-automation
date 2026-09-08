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
        # List index support (2026-09-08, Day 22): armed.0.status etc.
        if isinstance(obj, list):
            try:
                obj = obj[int(p)]
            except (ValueError, IndexError):
                sys.exit(f"ERROR: list index {p!r} invalid (len {len(obj)})")
            continue
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

    # batch (2026-09-08, Day 22): one read-modify-write for many ops, because
    # PowerShell's --% token swallows the rest of the line so every inline-JSON
    # call had to be its own shell invocation.
    #   python plan/dayjson.py <date> batch @ops.json
    # ops.json = [["set"|"append", "dotted.path", <value>], ...]
    if op == "batch":
        raw = rest[0]
        if raw.startswith("@"):
            raw = Path(raw[1:]).read_text(encoding="utf-8")
        for bop, dotted, value in json.loads(raw):
            apply_op(doc, bop, dotted, value)
        json.dump(doc, open(path, "w", encoding="utf-8"), indent=2)
        return

    # PowerShell strips the inner double quotes out of a single-quoted argument,
    # so inline JSON on the command line is not survivable on this box (the
    # windows-shell-quirks lesson again). Prefer @file.
    raw = rest[1]
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text(encoding="utf-8")
    apply_op(doc, op, rest[0], json.loads(raw))
    json.dump(doc, open(path, "w", encoding="utf-8"), indent=2)


def apply_op(doc, op, dotted, value):
    parts = dotted.split(".")
    parent = dig(doc, parts[:-1], create=True)
    key = parts[-1]
    if isinstance(parent, list):
        key = int(key)
    if op == "append":
        if isinstance(parent, dict):
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


if __name__ == "__main__":
    main()
